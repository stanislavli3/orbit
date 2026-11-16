"""Approved-supplier shortlist for a BOM line, with the evidence behind each pick."""

from datetime import date

from bom_agent.bom_extraction import find_material
from .models import Supplier


# A quote older than this is flagged as possibly out of date.
STALE_QUOTE_DAYS = 2 * 365


def _money(value) -> str:
    return f"${value:.2f}"


def shortlist_row(owner, row, similar_part_numbers=(), *, k=3, today=None) -> dict:
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
        score, evidence, best_quote, exact = 0, [], None, False
        for q in supplier.quotes.all():
            quoted = q.part.part_number.upper() if q.part else ""
            q_material = find_material(q.material)
            if part_number and quoted == part_number:
                score += 3
                exact = True
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
                best_quote = {
                    "unit_price": q.unit_price, "lead_time_days": q.lead_time_days,
                    "source": q.source, "quoted_at": q.quoted_at,
                }
        for c in supplier.historical_costs.all():
            supplied = c.part.part_number.upper()
            if supplied == part_number or supplied in similar:
                score += 2 if supplied == part_number else 1
                exact = exact or supplied == part_number
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
            "best_quote": {
                "unit_price": f"{best_quote['unit_price']:.2f}",
                "lead_time_days": best_quote["lead_time_days"],
                "source": best_quote["source"],
            } if best_quote else None,
            "evidence": evidence,
            "_exact": exact,
            "_quoted_at": best_quote["quoted_at"] if best_quote else None,
        })

    picks.sort(key=lambda p: (-p["score"], float(p["best_quote"]["unit_price"]) if p["best_quote"] else float("inf")))
    picks = picks[:k]
    _add_pros_cons(picks, today or date.today())
    for p in picks:
        p.pop("_exact", None)
        p.pop("_quoted_at", None)
    return {"suppliers": picks, "non_approved_left_out": left_out}


def _add_pros_cons(picks, today) -> None:
    """Plain-language trade-offs, judged against the other suppliers on the same shortlist."""
    priced = [float(p["best_quote"]["unit_price"]) for p in picks if p["best_quote"]]
    leads = [p["best_quote"]["lead_time_days"] for p in picks if p["best_quote"] and p["best_quote"]["lead_time_days"]]
    cheapest = min(priced) if priced else None
    fastest = min(leads) if leads else None
    for p in picks:
        pros, cons = [], []
        quote = p["best_quote"]
        if p["_exact"]:
            pros.append("Has quoted or supplied this exact part")
        else:
            cons.append("No history on this exact part, only similar parts or the same material")
        if quote:
            price = float(quote["unit_price"])
            if len(priced) > 1 and price == cheapest:
                pros.append("Lowest quoted price on this shortlist")
            elif cheapest and price > cheapest:
                cons.append(f"Quote is {round((price / cheapest - 1) * 100)}% above the cheapest option")
            lead = quote["lead_time_days"]
            if lead and len(leads) > 1 and lead == fastest:
                pros.append(f"Shortest lead time on this shortlist ({lead} days)")
            elif lead and fastest and lead > fastest:
                cons.append(f"Lead time {lead} days vs {fastest} for the fastest option")
            elif not lead:
                cons.append("No lead time on file")
            quoted_at = p["_quoted_at"]
            if quoted_at and (today - quoted_at).days > STALE_QUOTE_DAYS:
                cons.append(f"Quote is from {quoted_at.year}, so the price may have moved")
        else:
            cons.append("No quote on file, so price and lead time are unknown")
        if p["certifications"]:
            pros.append(f"Certified: {p['certifications']}")
        else:
            cons.append("No certifications on file")
        p["pros"], p["cons"] = pros, cons
