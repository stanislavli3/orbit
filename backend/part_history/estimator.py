"""Early cost estimates from similar historical parts (SCRUM-59).

For a BOM line, find the closest parts that have a historical cost, say why
each one matched, inflation-adjust their latest cost to today, and average
them weighted by similarity. Every assumption is returned with the number.
"""

import re
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from bom_agent.bom_extraction import find_material, infer_process
from .models import Part

DEFAULT_INFLATION = 0.03
MIN_SCORE = 0.25  # weaker matches aren't shown or used
_STOP_WORDS = {"the", "and", "with", "for", "assy", "part"}
_CENTS = Decimal("0.01")


def _words(text: str) -> set[str]:
    return {w for w in re.findall(r"[a-z]+", (text or "").lower()) if len(w) > 2 and w not in _STOP_WORDS}


def _family(part_number: str) -> str | None:
    """ORB-1042 -> ORB-10: numbers that differ only in the last two digits."""
    m = re.match(r"([A-Z]+-?)(\d{3,})", (part_number or "").upper())
    return f"{m.group(1)}{m.group(2)[:-2]}" if m else None


def similarity(row, part: Part) -> tuple[float, list[str]]:
    """Score 0-1 with the reasons a person would give for the match."""
    if row.part_number and row.part_number.upper() == part.part_number.upper():
        return 1.0, ["Same part number"]

    score, reasons = 0.0, []
    row_mat, part_mat = find_material(row.material), find_material(part.material)
    if row_mat and part_mat and row_mat[0] == part_mat[0]:
        score += 0.35
        reasons.append(f"Same material ({row_mat[0]})")
    elif row_mat and part_mat and row_mat[1] == part_mat[1]:
        score += 0.15
        reasons.append(f"Same material family ({row_mat[1]})")
    elif row.material and row.material.strip().upper() == part.material.strip().upper():
        score += 0.35
        reasons.append(f"Same material ({row.material})")

    part_process = part.process or infer_process(part.description, part.material)
    if row.process and row.process == part_process:
        score += 0.15
        reasons.append(f"Same process ({row.process})")

    row_words, part_words = _words(row.description), _words(part.description)
    shared = row_words & part_words
    if shared:
        score += 0.35 * len(shared) / len(row_words | part_words)
        reasons.append("Description shares: " + ", ".join(sorted(shared)))

    family = _family(row.part_number)
    if family and family == _family(part.part_number):
        score += 0.1
        reasons.append(f"Same part-number family ({family}xx)")

    return round(min(score, 0.95), 2), reasons


def estimate_row(owner, row, *, k=3, inflation=DEFAULT_INFLATION, year=None) -> dict:
    year = year or date.today().year
    candidates = Part.objects.filter(workspace_owner=owner, costs__isnull=False).distinct().prefetch_related("costs")
    scored = sorted(((similarity(row, p), p) for p in candidates), key=lambda x: -x[0][0])

    matches = []
    for (score, reasons), part in scored:
        if score < MIN_SCORE or len(matches) == k:
            break
        cost = part.costs.all()[0]  # newest model year first
        years = max(year - cost.model_year, 0) if cost.model_year else 0
        adjusted = cost.unit_cost * Decimal(str((1 + inflation) ** years))
        matches.append({
            "part_id": part.id,
            "part_number": part.part_number,
            "description": part.description,
            "material": part.material,
            "similarity": score,
            "reasons": reasons,
            "cost": {
                "unit_cost": str(cost.unit_cost.quantize(_CENTS)),
                "model_year": cost.model_year,
                "program": cost.program,
                "source": cost.source,
                "is_sample": cost.is_sample,
            },
            "adjusted_unit_cost": str(adjusted.quantize(_CENTS, ROUND_HALF_UP)),
            "_adjusted": adjusted,
        })

    result = {"matches": matches, "estimate": None, "assumptions": [], "confidence": "none",
              "uses_sample_data": any(m["cost"]["is_sample"] for m in matches)}
    if not matches:
        result["assumptions"].append("No similar historical parts found; add costs for parts like this one.")
        return result

    used = matches[:1] if matches[0]["similarity"] == 1.0 else matches
    weight = sum(Decimal(str(m["similarity"])) for m in used)
    unit = sum(m["_adjusted"] * Decimal(str(m["similarity"])) for m in used) / weight
    quantity = row.quantity or 1

    assumptions = [f"Inflation {inflation:.1%} a year, compounded from each cost's model year to {year}"]
    if len(used) == 1 and used[0]["similarity"] == 1.0:
        assumptions.append(f"Same part number: uses {used[0]['part_number']}'s latest cost only")
    else:
        assumptions.append(f"Similarity-weighted average of {len(used)} similar part{'s' if len(used) > 1 else ''}")
    assumptions += [
        f"No model year on {m['part_number']}'s cost, so it isn't inflation-adjusted"
        for m in used if not m["cost"]["model_year"]
    ]
    quantity_source = getattr(row, "sources", {}).get("quantity", "the BOM")
    assumptions.append(f"Quantity {quantity} from {quantity_source}")
    if result["uses_sample_data"]:
        assumptions.append("⚠ Based on SAMPLE data, not real costs")

    top = matches[0]["similarity"]
    result.update(
        estimate={
            "unit_cost": str(unit.quantize(_CENTS, ROUND_HALF_UP)),
            "quantity": quantity,
            "extended_cost": str((unit * quantity).quantize(_CENTS, ROUND_HALF_UP)),
            "currency": "USD",
            "based_on": [m["part_number"] for m in used],
        },
        assumptions=assumptions,
        confidence="high" if top == 1.0 else "medium" if top >= 0.5 else "low",
    )
    for m in matches:
        m.pop("_adjusted")
    return result


def estimate_bom(bom, owner, *, k=3, inflation=DEFAULT_INFLATION, year=None) -> dict:
    year = year or date.today().year
    rows, total, missing, sample = [], Decimal("0"), 0, False
    for row in bom.rows.all():
        est = estimate_row(owner, row, k=k, inflation=inflation, year=year)
        rows.append({"row_id": row.id, "line_no": row.line_no, "part_number": row.part_number,
                     "description": row.description, "quantity": row.quantity, **est})
        sample = sample or est["uses_sample_data"]
        if est["estimate"]:
            total += Decimal(est["estimate"]["extended_cost"])
        else:
            missing += 1
    return {
        "bom_id": bom.id,
        "reference": bom.reference,
        "year": year,
        "inflation": inflation,
        "rows": rows,
        "total": {"extended_cost": str(total.quantize(_CENTS)), "currency": "USD",
                  "rows_estimated": len(rows) - missing, "rows_without_estimate": missing},
        "uses_sample_data": sample,
    }
