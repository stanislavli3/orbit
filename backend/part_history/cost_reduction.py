"""'Find a 10% cost reduction on this part' (SCRUM-60).

A rules-based assumption challenger, not a should-cost model: every suggestion
is built from the workspace's own part history (costs, quotes, materials) and
cites it. When ANTHROPIC_API_KEY is set, Claude may add engineering questions
on top; the ranked suggestions never depend on it.
"""

import json
import os
import re
from decimal import Decimal

from bom_agent.bom_extraction import find_material, infer_process
from .estimator import _words, estimate_row
from .models import Part, Quote

DEFAULT_TARGET = 0.10
# Rule-of-thumb savings where history can't price the change; shown as assumptions.
TOLERANCE_SAVING = 0.10
FASTENER_SAVING = 0.25
_TIGHT_TOLERANCE = re.compile(r"(?:±|\+/-)\s*0?\.(?:00\d|01)\b|\btight\b|\bground\b|\blapped\b", re.I)


def _money(value) -> str:
    return f"${Decimal(value):.2f}"


def _suggestion(kind, title, rationale, saving_pct, evidence, baseline, assumption=None):
    pct = max(0.0, min(saving_pct, 1.0))
    return {
        "kind": kind,
        "title": title,
        "rationale": rationale,
        "estimated_saving_pct": round(pct, 3),
        "estimated_saving_per_unit": f"{baseline * Decimal(str(pct)):.2f}" if baseline else None,
        "evidence": evidence,
        "assumption": assumption,
    }


def _cheaper_material(owner, row, baseline):
    """Similar parts (same words or process) in a different material that cost less."""
    row_mat = find_material(row.material)
    words = _words(row.description)
    process = row.process or infer_process(row.description, row.material)
    out = []
    for part in Part.objects.filter(workspace_owner=owner, costs__isnull=False).distinct().prefetch_related("costs"):
        mat = find_material(part.material)
        same_material = (mat and row_mat and mat[0] == row_mat[0]) or \
            part.material.strip().upper() == (row.material or "").strip().upper()
        if same_material or not part.material or not (words & _words(part.description)):
            continue
        if process and (part.process or infer_process(part.description, part.material)) != process:
            continue
        cost = part.costs.all()[0]
        if not baseline or cost.unit_cost >= baseline:
            continue
        pct = float(1 - cost.unit_cost / baseline)
        when = " ".join(str(x) for x in (cost.program, cost.model_year) if x)
        out.append(_suggestion(
            "material",
            f"Try {part.material} instead of {row.material or 'the current material'}",
            f"{part.part_number} ({part.description}) is a similar part in {part.material} and cost "
            f"{_money(cost.unit_cost)} vs this part's {_money(baseline)}. Check strength, finish and corrosion needs "
            f"before switching.",
            pct,
            [{"text": f"{part.part_number} in {part.material}: {_money(cost.unit_cost)} ({when})", "source": cost.source},
             {"text": f"This part's material: {row.material or 'not stated'}",
              "source": getattr(row, "sources", {}).get("material", "the BOM")}],
            baseline,
        ))
    return out


def _quotes(owner, row):
    pn = (row.part_number or "").upper()
    if not pn:
        return []
    return [q for q in Quote.objects.filter(workspace_owner=owner).select_related("part", "supplier")
            if q.part and q.part.part_number.upper() == pn]


def _cheaper_quote(quotes, row, baseline):
    """Cheapest quote at this BOM's volume (bulk quotes are the volume-break rule's job)."""
    quotes = [q for q in quotes if not q.quantity or q.quantity <= (row.quantity or 1)]
    if not quotes or not baseline:
        return []
    best = min(quotes, key=lambda q: q.unit_price)
    if best.unit_price >= baseline:
        return []
    note = "" if best.supplier.is_approved else " They are not on the approved vendor list, so qualify them first."
    return [_suggestion(
        "supplier",
        f"Re-source to {best.supplier.name}",
        f"{best.supplier.name} quoted this part at {_money(best.unit_price)}, below the {_money(baseline)} "
        f"estimate.{note}",
        float(1 - best.unit_price / baseline),
        [{"text": f"{best.supplier.name} quoted {_money(best.unit_price)}"
                  f"{f' at qty {best.quantity}' if best.quantity else ''} on {best.quoted_at.isoformat()}",
          "source": best.source}],
        baseline,
    )]


def _volume_break(quotes, row, baseline):
    """A quote at a higher quantity than this BOM uses, priced below the low-volume quotes."""
    qty = row.quantity or 1
    bulk = [q for q in quotes if q.quantity and q.quantity > qty]
    if not bulk:
        return []
    best = min(bulk, key=lambda q: q.unit_price)
    reference = baseline or min((q.unit_price for q in quotes if not q.quantity or q.quantity <= qty), default=None)
    if not reference or best.unit_price >= reference:
        return []
    return [_suggestion(
        "volume",
        f"Consolidate demand to qty {best.quantity}",
        f"This BOM uses {qty}; at qty {best.quantity} {best.supplier.name} quoted {_money(best.unit_price)} vs "
        f"{_money(reference)}. Combine with other programs or buy a blanket order.",
        float(1 - best.unit_price / reference),
        [{"text": f"{best.supplier.name}: {_money(best.unit_price)} at qty {best.quantity}", "source": best.source},
         {"text": f"Quantity {qty} on this BOM", "source": getattr(row, "sources", {}).get("quantity", "the BOM")}],
        baseline,
    )]


def _cots(owner, row, baseline):
    """A custom-numbered part whose description matches a cheaper catalog/purchased part."""
    if infer_process(row.description, row.material) == "purchased":
        return []
    words = _words(row.description)
    out = []
    for part in Part.objects.filter(workspace_owner=owner, costs__isnull=False).distinct().prefetch_related("costs"):
        if part.part_number.upper() == (row.part_number or "").upper():
            continue
        if infer_process(part.description, part.material) != "purchased" or not (words & _words(part.description)):
            continue
        cost = part.costs.all()[0]
        if baseline and cost.unit_cost >= baseline:
            continue
        out.append(_suggestion(
            "cots",
            f"Use catalog part {part.part_number}",
            f"{part.part_number} ({part.description}) is a purchased standard part at {_money(cost.unit_cost)}; "
            f"a custom part costs {_money(baseline) if baseline else 'more to design and qualify'}.",
            float(1 - cost.unit_cost / baseline) if baseline else 0.0,
            [{"text": f"{part.part_number}: {_money(cost.unit_cost)}", "source": cost.source}],
            baseline,
        ))
    return out


def _tolerance(row, quotes, baseline):
    noted = [("BOM spec", row.spec, getattr(row, "sources", {}).get("spec", "the BOM"))] if getattr(row, "spec", "") else []
    noted += [(f"{q.supplier.name} quote", q.tolerance, q.source) for q in quotes if q.tolerance]
    tight = [n for n in noted if _TIGHT_TOLERANCE.search(n[1] or "")]
    if not tight:
        return []
    return [_suggestion(
        "tolerance",
        "Relax tolerances that aren't functional",
        "A tight tolerance is noted on this part. Ask whether every toleranced feature needs it; "
        "opening non-critical features can cut machining and inspection time.",
        TOLERANCE_SAVING,
        [{"text": f"{label}: {value}", "source": source} for label, value, source in tight],
        baseline,
        assumption=f"Saving is a {TOLERANCE_SAVING:.0%} rule of thumb, not priced from history",
    )]


def _fastener_count(row, baseline):
    qty = row.quantity or 1
    if infer_process(row.description, row.material) != "purchased" or qty < 4:
        return []
    return [_suggestion(
        "fastener_count",
        f"Challenge the fastener count ({qty})",
        f"{qty} of these per assembly. Fewer, larger fasteners or a snap/tab feature also cut assembly labour.",
        FASTENER_SAVING,
        [{"text": f"Quantity {qty}", "source": getattr(row, "sources", {}).get("quantity", "the BOM")}],
        baseline,
        assumption=f"Assumes removing {FASTENER_SAVING:.0%} of the fasteners",
    )]


def _claude_questions(row, suggestions) -> list[str]:
    """Optional: extra questions to challenge the design. Never required; failures are silent."""
    if not os.getenv("ANTHROPIC_API_KEY", "").strip():
        return []
    try:
        from bom_agent.team_requests import _client
        from core.usage import tracked_create

        prompt = (
            "You are a senior cost engineer. Given this part and rules-based suggestions, return a JSON list of up "
            "to 3 short questions that challenge the design assumptions. JSON only.\n"
            f"Part: {row.part_number} {row.description}; material {row.material}; qty {row.quantity}; spec "
            f"{getattr(row, 'spec', '')}\nSuggestions: {json.dumps([s['title'] for s in suggestions])}"
        )
        response = tracked_create(
            _client(), path="enrichment", operation="cost_reduction_questions", target=f"bom_row:{row.pk}",
            model="claude-haiku-4-5-20251001", max_tokens=300, messages=[{"role": "user", "content": prompt}]
        )
        questions = json.loads(response.content[0].text.strip())
        return [str(q) for q in questions][:3] if isinstance(questions, list) else []
    except Exception:
        return []


def find_cost_reduction(owner, row, *, target=DEFAULT_TARGET) -> dict:
    estimate = estimate_row(owner, row)["estimate"]
    quotes = _quotes(owner, row)
    if estimate:
        baseline, basis = Decimal(estimate["unit_cost"]), f"Cost estimate from {', '.join(estimate['based_on'])}"
    elif quotes:
        baseline, basis = min(q.unit_price for q in quotes), "Lowest quote on file for this part"
    else:
        baseline, basis = None, "No cost history for this part, so savings can't be priced"

    suggestions = (_cheaper_material(owner, row, baseline) + _cheaper_quote(quotes, row, baseline)
                   + _volume_break(quotes, row, baseline) + _cots(owner, row, baseline)
                   + _tolerance(row, quotes, baseline) + _fastener_count(row, baseline))
    suggestions.sort(key=lambda s: -s["estimated_saving_pct"])
    for rank, s in enumerate(suggestions, 1):
        s["rank"] = rank
        s["meets_target"] = s["estimated_saving_pct"] >= target
    return {
        "row_id": row.id,
        "part_number": row.part_number,
        "target_pct": target,
        "baseline": {"unit_cost": f"{baseline:.2f}" if baseline else None, "basis": basis},
        "suggestions": suggestions,
        "target_met": any(s["meets_target"] for s in suggestions),
        "questions": _claude_questions(row, suggestions),
        "disclaimer": "An assumption challenger built from your part history, not a should-cost model "
                      "(e.g. aPriori). Validate each idea with engineering before acting.",
    }
