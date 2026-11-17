"""Optional supplier research beyond the approved list (SCRUM-70).

Everything returned here is UNVERIFIED: it is kept apart from the approved
shortlist, stored as a SupplierResearch record, and never creates a Supplier
or touches the approved vendor list.

With ANTHROPIC_API_KEY set, Claude + web_search (the same hosted tool as
bom_agent/research_pipeline.py) proposes suppliers with source URLs. Either
way, non-approved suppliers already in part history are included.
"""

import json
import os
import re

from bom_agent import research_pipeline
from bom_agent.bom_extraction import find_material
from core.usage import tracked_create
from .models import Supplier, SupplierResearch

NO_KEY_NOTE = ("Web research needs ANTHROPIC_API_KEY. Showing non-approved suppliers already in "
               "part history instead.")
MODEL = "claude-sonnet-4-6"


def _history_candidates(owner, row) -> list[dict]:
    part_number = (row.part_number or "").upper()
    material = find_material(row.material)
    out = []
    suppliers = Supplier.objects.filter(workspace_owner=owner, is_approved=False).prefetch_related(
        "quotes__part", "historical_costs__part")
    for s in suppliers:
        hits = []
        for q in s.quotes.all():
            quoted = q.part.part_number.upper() if q.part else ""
            q_mat = find_material(q.material)
            if part_number and quoted == part_number:
                what = "this part"
            elif material and q_mat and q_mat[0] == material[0]:
                what = f"the same material ({material[0]})"
            else:
                continue
            hits.append((q.unit_price, q.lead_time_days, f"Quoted {what}", q.source))
        for c in s.historical_costs.all():
            if part_number and c.part.part_number.upper() == part_number:
                hits.append((c.unit_cost, None, "Supplied this part", c.source))
        if not hits:
            continue
        price, lead, _, _ = min(hits, key=lambda h: h[0])
        out.append({
            "supplier": s.name,
            "unit_price": f"{price:.2f}",
            "lead_time_days": lead,
            "risk_notes": ["Not on the approved vendor list", *[f"{h[2]} ({h[3]})" for h in hits[:3]]],
            "sources": [h[3] for h in hits],
            "origin": "part_history",
            "verified": False,
        })
    return out


def _prompt(row) -> str:
    what = ", ".join(x for x in (row.part_number, getattr(row, "description", ""), row.material,
                                  getattr(row, "process", "")) if x)
    return (
        f"Find up to 4 suppliers that could make this part: {what}. Use web_search. "
        "Reply with ONLY a JSON array; each item: {\"supplier\": str, \"unit_price\": number or null (USD), "
        "\"lead_time_days\": int or null, \"risk_notes\": [str], \"sources\": [url]}. "
        "Every item must cite at least one source URL you actually found. Do not invent prices."
    )


def _parse(text: str) -> list[dict]:
    m = re.search(r"\[.*\]", text, re.S)
    if not m:
        return []
    try:
        items = json.loads(m.group(0))
    except json.JSONDecodeError:
        return []
    out = []
    for it in items if isinstance(items, list) else []:
        if not isinstance(it, dict) or not it.get("supplier"):
            continue
        sources = [s for s in it.get("sources") or [] if isinstance(s, str) and s.startswith("http")]
        if not sources:
            continue  # no source URL, no result
        price = it.get("unit_price")
        out.append({
            "supplier": str(it["supplier"])[:200],
            "unit_price": f"{float(price):.2f}" if isinstance(price, (int, float)) else None,
            "lead_time_days": it.get("lead_time_days") if isinstance(it.get("lead_time_days"), int) else None,
            "risk_notes": [str(n) for n in it.get("risk_notes") or []][:5],
            "sources": sources[:5],
            "origin": "web",
            "verified": False,
        })
    return out


def _web_candidates(row) -> list[dict]:
    response = tracked_create(
        research_pipeline._client(), path="agent", operation="supplier_web_research", target=f"bom_row:{row.pk}",
        model=MODEL,
        max_tokens=2048,
        tools=[{"type": "web_search_20250305", "name": "web_search", "max_uses": 3}],
        messages=[{"role": "user", "content": _prompt(row)}],
    )
    text = "".join(getattr(b, "text", "") for b in response.content if getattr(b, "type", "") == "text")
    return _parse(text)


def research_suppliers(owner, row) -> dict:
    approved = {n.lower() for n in Supplier.objects.filter(workspace_owner=owner, is_approved=True)
                .values_list("name", flat=True)}
    results, note, mode = [], "", "history"
    if os.getenv("ANTHROPIC_API_KEY"):
        mode = "web"
        try:
            results = [r for r in _web_candidates(row) if r["supplier"].lower() not in approved]
            note = "Found by Claude web search. Not verified: check every price, lead time and source."
        except Exception as exc:  # demo-grade: degrade to history
            note = f"Web research failed ({type(exc).__name__}); showing part history only."
    else:
        note = NO_KEY_NOTE
    seen = {r["supplier"].lower() for r in results}
    results += [r for r in _history_candidates(owner, row) if r["supplier"].lower() not in seen]
    record = SupplierResearch.objects.create(
        workspace_owner=owner, bom_row_id=row.id, mode=mode, note=note, results_json=results)
    return serialize(record)


def serialize(record) -> dict:
    return {
        "id": record.id, "row_id": record.bom_row_id, "mode": record.mode, "note": record.note,
        "status": "UNVERIFIED", "results": record.results_json, "created_at": record.created_at.isoformat(),
    }
