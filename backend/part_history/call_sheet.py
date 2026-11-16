"""A phone call sheet for one shortlisted supplier and one BOM line (SCRUM-71)."""

from .estimator import estimate_row
from .models import Supplier
from .shortlist import shortlist_row

CONFIRM = "Confirm on call"


class NotShortlisted(Exception):
    pass


def _summary(row) -> str:
    what = row.description or "Part"
    parts = [f"{what} ({row.part_number})" if row.part_number else what]
    if row.material:
        parts.append(f"in {row.material}")
    if row.process:
        parts.append(f"made by {row.process.lower()}")
    return " ".join(parts) + f", {row.quantity} needed per build."


def _questions(pick, row) -> list[str]:
    """5-7 questions, starting with the gaps the shortlist's cons point at."""
    text = " ".join(pick["cons"]).lower()
    material = row.material or "this material"
    qs = []
    if "exact part" in text:
        qs.append(f"Have you made a part like this in {material}, and can you hold the tolerances we need?")
    else:
        qs.append("You've quoted this part before: has anything changed in how you'd make it?")
    if "no quote" in text or "price may have moved" in text or "above the cheapest" in text:
        qs.append(f"What would your unit price be today at {row.quantity} pieces?")
    qs.append("Where are your price breaks (e.g. 100 / 500 / 1,000 pieces), and is there a minimum order?")
    if "lead time" in text:
        qs.append("What lead time can you commit to for first articles and for production?")
    else:
        qs.append("Can you hold the lead time you quoted last time?")
    qs.append("Do you have capacity for this volume over the next few months?")
    if "certifications" in text:
        qs.append("Which certifications do you hold (e.g. ISO 9001, AS9100), and can you send copies?")
    else:
        qs.append(f"Are your certifications ({pick['certifications']}) current?")
    qs.append("Are you interested in quoting, and who should the RFQ go to?")
    return qs[:7]


def call_sheet(owner, row, supplier_id) -> dict:
    similar = [m["part_number"] for m in estimate_row(owner, row)["matches"]]
    shortlist = shortlist_row(owner, row, similar)
    pick = next((s for s in shortlist["suppliers"] if s["supplier_id"] == supplier_id), None)
    if pick is None:
        raise NotShortlisted("That supplier isn't on the shortlist for this line.")
    supplier = Supplier.objects.get(pk=supplier_id, workspace_owner=owner)
    sources = row.sources or {}

    def spec(label, value, field):
        return {"label": label, "value": str(value) if value else CONFIRM, "source": sources.get(field, "")}

    quote = pick["best_quote"]
    return {
        "supplier": {
            "id": supplier.id,
            "name": supplier.name,
            "contact_email": supplier.contact_email or CONFIRM,
            "certifications": supplier.certifications,
            "approval": pick["approval"],
        },
        "bom_reference": row.bom.reference,
        "line_no": row.line_no,
        "part_summary": _summary(row),
        "specs": [
            spec("Part number", row.part_number, "part_number"),
            spec("Material", row.material, "material"),
            spec("Process", row.process, "process"),
            spec("Quantity per build", row.quantity, "quantity"),
            spec("Tolerance / spec", row.spec, "spec"),
            {"label": "Finish / treatment", "value": CONFIRM, "source": ""},
        ],
        "volume_and_timing": {
            "quantity": row.quantity,
            "last_quote": f"${quote['unit_price']}" if quote else None,
            "last_lead_time_days": quote["lead_time_days"] if quote else None,
            "needed_by": CONFIRM,
        },
        "pros": pick["pros"],
        "cons": pick["cons"],
        "evidence": pick["evidence"],
        "questions": _questions(pick, row),
    }
