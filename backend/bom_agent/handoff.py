"""Buyer handoff view of a BOM (SCRUM-69).

Read-only, buyer-facing: per line a plain-English explanation, a cost range,
the approved supplier shortlist and the open questions a buyer would
otherwise send back to engineering. Explanations are deterministic; Claude
may rewrite them when ANTHROPIC_API_KEY is set, but is never required.
"""

import json
import os

from bom_agent.bom_extraction import find_material

from .galvanic import galvanic_flags

PROCESS_WORDS = {
    "machined": "cut from solid stock on a CNC machine",
    "sheet metal": "laser-cut and bent from sheet metal",
    "casting": "cast, then finish-machined",
    "injection molded": "injection-molded plastic (needs a mold tool)",
    "purchased": "an off-the-shelf catalog part",
    "assembly": "a sub-assembly put together from other lines on this BOM",
}


def explain_row(row: dict) -> str:
    pn = row.get("part_number") or "This line"
    desc = (row.get("description") or "").strip()
    material = (row.get("material") or "").strip()
    process = row.get("process") or ""
    qty = row.get("quantity") or 1
    found = find_material(material)
    parts = [f"{pn} is {('a ' + desc.lower()) if desc else 'a part with no description yet'}"]
    if process in PROCESS_WORDS:
        parts.append(f"It is {PROCESS_WORDS[process]}")
    if material:
        family = f" ({found[1]})" if found and found[1].lower() not in material.lower() else ""
        parts.append(f"Material: {material}{family}")
    else:
        parts.append("Material is not stated")
    parts.append(f"{qty} needed per build")
    if row.get("spec"):
        parts.append(f"Must meet {row['spec']}")
    return ". ".join(parts) + "."


def open_questions(row: dict, rfq=None) -> list[str]:
    qs = []
    if not row.get("part_number"):
        qs.append("No part number: what should the PO reference?")
    if not row.get("description"):
        qs.append("No description: what is this part?")
    if not row.get("material"):
        qs.append("Material is not stated: which grade should suppliers quote?")
    if not row.get("process"):
        qs.append("Manufacturing process is unknown: machined, sheet metal, cast or bought?")
    if not row.get("spec") and row.get("process") != "purchased":
        qs.append("No tolerance / spec callout: is a general tolerance acceptable?")
    if not row.get("revision"):
        qs.append("No revision: which drawing revision should be quoted?")
    for flag in row.get("flags") or []:
        text = flag.get("message") if isinstance(flag, dict) else str(flag)
        if text:
            qs.append(f"Extraction flag: {text}")
    if rfq is not None:
        qs.extend(f"RFQ {a}" for a in rfq.assumptions)
    return qs


def _claude_explanations(lines: list[dict]) -> dict:
    """Optional rewrite of explanations by Claude. Silent fallback on any failure."""
    if not os.getenv("ANTHROPIC_API_KEY", "").strip() or not lines:
        return {}
    try:
        from bom_agent.team_requests import _client
        from core.usage import tracked_create

        payload = [{"row_id": l["row_id"], "part_number": l["part_number"], "description": l["description"],
                    "material": l["material"], "process": l["process"], "quantity": l["quantity"]} for l in lines]
        prompt = (
            "Rewrite each BOM line as one or two plain-English sentences a purchasing buyer understands "
            "(what it is, how it is made, what matters for buying). Do not invent facts. Return JSON only: "
            '{"<row_id>": "<explanation>", ...}\n' + json.dumps(payload)
        )
        response = tracked_create(
            _client(), path="enrichment", operation="handoff_explanations",
            model="claude-haiku-4-5-20251001", max_tokens=1500, messages=[{"role": "user", "content": prompt}]
        )
        data = json.loads(response.content[0].text.strip())
        return {int(k): str(v) for k, v in data.items()} if isinstance(data, dict) else {}
    except Exception:
        return {}


def build_handoff(bom, owner, *, environment: str = "general", occurrences=None) -> dict:
    from part_history.quick_estimate import quick_report

    report = quick_report(bom, owner)
    rfqs = {}
    for row in bom.rows.all():
        latest = row.rfq_drafts.order_by("-created_at").first()
        if latest:
            rfqs[row.id] = latest

    lines = []
    for entry in report["rows"]:
        row = entry["row"]
        est = entry.get("estimate")
        sc = entry["should_cost"]
        suppliers = entry["shortlist"]["suppliers"]
        lines.append({
            "row_id": entry["row_id"],
            "line_no": row["line_no"],
            "part_number": row["part_number"],
            "description": row["description"],
            "material": row["material"],
            "process": row["process"],
            "quantity": row["quantity"],
            "spec": row["spec"],
            "revision": row["revision"],
            "explanation": explain_row(row),
            "explanation_source": "rules",
            "cost": {
                "should_cost": {k: sc[k] for k in ("low", "expected", "high", "confidence")},
                "historical": {"unit_cost": est["unit_cost"], "based_on": est.get("based_on", [])} if est else None,
                "low": min([sc["low"]] + ([est["unit_cost"]] if est else []), key=float),
                "high": max([sc["high"]] + ([est["unit_cost"]] if est else []), key=float),
                "currency": "USD",
            },
            "supplier": suppliers[0] if suppliers else None,
            "alternates": [s["supplier"] for s in suppliers[1:]],
            "open_questions": open_questions(row, rfqs.get(entry["row_id"])),
        })

    for row_id, text in _claude_explanations(lines).items():
        for line in lines:
            if line["row_id"] == row_id and text.strip():
                line["explanation"], line["explanation_source"] = text.strip(), "claude"

    galvanic = galvanic_flags(lines, occurrences, environment)
    for flag in galvanic["flags"]:
        for line in lines:
            if line["part_number"] in flag["parts"]:
                line["open_questions"].append(
                    f"Material pair: {flag['title']} with "
                    f"{next(p for p in flag['parts'] if p != line['part_number'])} — how is the joint isolated?"
                )

    low = sum(float(l["cost"]["low"]) * (l["quantity"] or 1) for l in lines)
    high = sum(float(l["cost"]["high"]) * (l["quantity"] or 1) for l in lines)
    return {
        "bom": report["bom"],
        "lines": lines,
        "total": {"low": f"{low:.2f}", "high": f"{high:.2f}", "currency": "USD"},
        "open_question_count": sum(len(l["open_questions"]) for l in lines),
        "galvanic": galvanic,
        "uses_sample_data": report.get("uses_sample_data", False),
        "note": "Cost ranges combine an assumed should-cost model with historical costs; "
                "confirm with quotes before committing.",
    }
