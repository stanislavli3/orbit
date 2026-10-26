"""Approved-supplier shortlist for a BOM line, with the evidence behind each pick."""

from bom_agent.bom_extraction import find_material
from .models import Supplier


def _money(value) -> str:
    return f"${value:.2f}"


def shortlist_row(owner, row, similar_part_numbers=(), *, k=3) -> dict:
    """Rank approved suppliers by what they've done before.

    Quoted or supplied this exact part beats a similar part (from the
    estimate's matches), which beats having quoted the same material.
    """
    part_number = (row.part_number or "").upper()
    similar = {pn.upper() for pn in similar_part_numbers} - {part_number}
    material = find_material(row.material)

    picks, left_out = [], 0
    suppliers = Supplier.objects.filter(workspace_owner=owner).prefetch_related(
        "quotes__part", "historical_costs__part"
    )
    for supplier in suppliers:
        score, evidence, best_quote = 0, [], None
        for q in supplier.quotes.all():
            quoted = q.part.part_number.upper() if q.part else ""
            q_material = find_material(q.material)
            if part_number and quoted == part_number:
                score += 3
                what = "this part"
            elif quoted in similar:
                score += 2
                what = f"similar part {q.part.part_number}"
            elif material and q_material and q_material[0] == material[0]:
                score += 1
                what = f"the same material ({material[0]})"
            else:
                continue
            lead = f", {q.lead_time_days}-day lead time" if q.lead_time_days else ""
            evidence.append({
                "text": f"Quoted {what} at {_money(q.unit_price)}{lead} on {q.quoted_at.isoformat()}",
                "source": q.source,
            })
            if best_quote is None or q.unit_price < best_quote["unit_price"]:
                best_quote = {"unit_price": q.unit_price, "lead_time_days": q.lead_time_days, "source": q.source}
        for c in supplier.historical_costs.all():
            supplied = c.part.part_number.upper()
            if supplied == part_number or supplied in similar:
                score += 2 if supplied == part_number else 1
                what = "this part" if supplied == part_number else f"similar part {c.part.part_number}"
                when = " ".join(str(x) for x in (c.program, c.model_year) if x)
                evidence.append({"text": f"Supplied {what} for {when} at {_money(c.unit_cost)}", "source": c.source})
        if not score:
            continue
        if not supplier.is_approved:
            left_out += 1
            continue
        picks.append({
            "supplier_id": supplier.id,
            "supplier": supplier.name,
            "certifications": supplier.certifications,
            "approval": supplier.approval_note or "On the approved vendor list",
            "score": score,
            "best_quote": {**best_quote, "unit_price": f"{best_quote['unit_price']:.2f}"} if best_quote else None,
            "evidence": evidence,
        })

    picks.sort(key=lambda p: (-p["score"], float(p["best_quote"]["unit_price"]) if p["best_quote"] else float("inf")))
    return {"suppliers": picks[:k], "non_approved_left_out": left_out}
