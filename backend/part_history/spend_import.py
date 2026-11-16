"""Import a supplier spend / invoice export (SCRUM-72).

Each row says which supplier was paid how much for which part. It becomes a
Quote (price, quantity, date, optional lead time) and a HistoricalCost, both
with source "<file> spend import row N", so the supplier shortlist, the cost
estimate and the lead-time estimate pick it up. Reuses the cost importer's
file reading, row-level errors and import batches.
"""

import re
from datetime import date, datetime

from django.db import transaction

from .importer import ImportFileError, _cost, read_rows
from .models import HistoricalCost, ImportBatch, Part, Quote, Supplier

SPEND_ALIASES = {
    "supplier": {"supplier", "vendor", "supplier name", "vendor name", "payee"},
    "part_number": {"part number", "part no", "part no.", "part #", "p/n", "pn", "item", "item number", "sku"},
    "description": {"description", "desc", "item description", "part name", "line description"},
    "quantity": {"quantity", "qty", "qty ordered", "units"},
    "unit_price": {"unit price", "price", "unit cost", "cost", "price (usd)", "unit price (usd)"},
    "date": {"date", "invoice date", "po date", "order date"},
    "reference": {"invoice", "invoice #", "invoice number", "po", "po #", "po number", "reference", "ref"},
    "lead_time_days": {"lead time", "lead time (days)", "lead time days", "lead_time_days"},
}


def _find_header(rows):
    for i, row in enumerate(rows[:10]):
        mapping = {}
        for col, cell in enumerate(row):
            name = str(cell).strip().lower()
            field = next((f for f, names in SPEND_ALIASES.items() if name in names), None)
            if field and field not in mapping.values():
                mapping[col] = field
        fields = set(mapping.values())
        if {"supplier", "unit_price"} <= fields and fields & {"part_number", "description"}:
            return i, mapping
    raise ImportFileError(
        "Couldn't find a header row with 'Supplier', 'Unit Price' and 'Part Number' or 'Description' columns."
    )


def _date(value: str):
    value = value.strip().split(" ")[0]
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%m/%d/%y", "%d.%m.%Y"):
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            pass
    return None


def validate(rows, header_index, mapping):
    valid, rejected = [], []
    for n, raw in enumerate(rows[header_index + 1 :], start=header_index + 2):
        if not any(str(c).strip() for c in raw):
            continue
        values = {f: (str(raw[i]).strip() if i < len(raw) else "") for i, f in mapping.items()}
        errors = []
        if not values.get("supplier"):
            errors.append("Missing supplier")
        if not values.get("part_number") and not values.get("description"):
            errors.append("Needs a part number or description")
        raw_price = values.get("unit_price", "")
        price = _cost(raw_price) if raw_price else None
        if not raw_price:
            errors.append("Missing unit price")
        elif price is None:
            errors.append(f"Unit price '{raw_price}' is not a number")
        elif price <= 0:
            errors.append("Unit price must be greater than 0")
        qty = None
        if values.get("quantity"):
            m = re.fullmatch(r"\d+(?:\.0+)?", values["quantity"].replace(",", ""))
            qty = int(float(values["quantity"].replace(",", ""))) if m else None
            if qty is None:
                errors.append(f"Quantity '{values['quantity']}' is not a whole number")
        when = None
        if values.get("date"):
            when = _date(values["date"])
            if when is None or when > date.today():
                errors.append(f"Date '{values['date']}' not understood")
        lead = None
        if values.get("lead_time_days"):
            m = re.fullmatch(r"(\d+)(?:\.0+)?(?:\s*days?)?", values["lead_time_days"], re.I)
            lead = int(m.group(1)) if m else None
            if lead is None:
                errors.append(f"Lead time '{values['lead_time_days']}' is not a number of days")
        if errors:
            rejected.append({"row": n, "errors": errors, "values": values})
        else:
            valid.append({"row": n, "values": values, "price": price, "qty": qty, "date": when, "lead": lead})
    return valid, rejected


def import_spend(owner, data: bytes, filename: str, *, dry_run=False, uploaded_by=None) -> dict:
    rows = read_rows(data, filename)
    header_index, mapping = _find_header(rows)
    valid, rejected = validate(rows, header_index, mapping)
    report = {
        "filename": filename, "dry_run": dry_run, "total_rows": len(valid) + len(rejected),
        "valid_rows": len(valid), "imported_rows": 0, "rejected": rejected, "batch_id": None,
        "suppliers_created": 0,
    }
    if dry_run:
        return report

    with transaction.atomic():
        batch = ImportBatch.objects.create(
            workspace_owner=owner, uploaded_by=uploaded_by, filename=filename, kind="spend",
            total_rows=report["total_rows"], imported_rows=len(valid), rejected_rows=len(rejected),
            rejected_json=rejected,
        )
        for entry in valid:
            v = entry["values"]
            part_number = (v.get("part_number") or v["description"])[:100]
            part = Part.objects.filter(workspace_owner=owner, part_number__iexact=part_number).first()
            if part is None:
                part = Part.objects.create(workspace_owner=owner, part_number=part_number,
                                           description=v.get("description", ""))
            elif not part.description and v.get("description"):
                part.description = v["description"]
                part.save(update_fields=["description", "updated_at"])
            supplier = Supplier.objects.filter(workspace_owner=owner, name__iexact=v["supplier"]).first()
            if supplier is None:
                # Spend history says we've paid them; it does NOT put them on the AVL.
                supplier = Supplier.objects.create(workspace_owner=owner, name=v["supplier"])
                report["suppliers_created"] += 1
            ref = f" ({v['reference']})" if v.get("reference") else ""
            source = f"{filename} spend import row {entry['row']}{ref}"
            when = entry["date"] or date.today()
            Quote.objects.create(
                workspace_owner=owner, supplier=supplier, part=part, unit_price=entry["price"],
                quantity=entry["qty"], lead_time_days=entry["lead"], quoted_at=when,
                source=source, import_batch=batch,
            )
            HistoricalCost.objects.create(
                workspace_owner=owner, part=part, unit_cost=entry["price"], supplier=supplier,
                model_year=when.year, program=v.get("reference", "")[:200], source=source, import_batch=batch,
            )
    report["imported_rows"] = len(valid)
    report["batch_id"] = batch.pk
    return report
