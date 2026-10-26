"""Import historical part costs from a CSV or Excel sheet (SCRUM-58).

Columns are matched by common names ("Part No", "P/N", "Unit Cost", "MY", ...).
Each row is validated on its own; bad rows are reported with their row number
and reasons, and good rows are imported anyway.
"""

import csv
import io
import re
from datetime import date
from decimal import Decimal, InvalidOperation

from django.db import transaction

from .models import HistoricalCost, ImportBatch, Part, Supplier

COLUMN_ALIASES = {
    "part_number": {"part number", "part no", "part no.", "part #", "part", "p/n", "pn"},
    "description": {"description", "desc", "part name", "name"},
    "material": {"material", "matl", "material spec"},
    "unit_cost": {"cost", "unit cost", "unit price", "price", "cost (usd)", "unit cost (usd)"},
    "model_year": {"model year", "my", "year"},
    "program": {"program", "program name", "vehicle program"},
    "supplier": {"supplier", "vendor"},
}


class ImportFileError(ValueError):
    """The whole file can't be imported (wrong type, missing columns)."""


def read_rows(data: bytes, filename: str) -> list[list[str]]:
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext == "csv":
        return list(csv.reader(io.StringIO(data.decode("utf-8-sig", errors="replace"))))
    if ext in ("xlsx", "xlsm"):
        import openpyxl

        try:
            wb = openpyxl.load_workbook(io.BytesIO(data), read_only=True, data_only=True)
        except Exception as exc:
            raise ImportFileError(f"Could not open the spreadsheet: {exc}") from exc
        rows = [
            ["" if c is None else str(c).strip() for c in row]
            for row in wb.worksheets[0].iter_rows(values_only=True)
        ]
        wb.close()
        return rows
    raise ImportFileError("Upload a .csv or .xlsx file.")


def _find_header(rows) -> tuple[int, dict[int, str]]:
    """The first of the top 10 rows that names a part number and a cost column."""
    for i, row in enumerate(rows[:10]):
        mapping = {}
        for col, cell in enumerate(row):
            name = str(cell).strip().lower()
            field = next((f for f, names in COLUMN_ALIASES.items() if name in names), None)
            if field and field not in mapping.values():
                mapping[col] = field
        fields = set(mapping.values())
        if {"part_number", "unit_cost"} <= fields:
            if not fields & {"model_year", "program"}:
                raise ImportFileError("Add a 'Model Year' or 'Program' column so costs can be dated.")
            return i, mapping
    raise ImportFileError("Couldn't find a header row with 'Part Number' and 'Cost' columns in the first 10 rows.")


def _cost(value: str) -> Decimal | None:
    cleaned = re.sub(r"[$,\s]|USD", "", value, flags=re.I)
    try:
        return Decimal(cleaned)
    except InvalidOperation:
        return None


def _model_year(value: str) -> int | None:
    m = re.fullmatch(r"(?:MY|FY)?\s*'?(\d{2}|\d{4})(?:\.0)?", value.strip(), re.I)
    if not m:
        return None
    year = int(m.group(1))
    year = 2000 + year if year < 100 else year
    return year if 1950 <= year <= date.today().year + 3 else None


def validate(rows, header_index, mapping) -> tuple[list[dict], list[dict]]:
    """Split data rows into valid ones and a rejected-row report."""
    valid, rejected, seen = [], [], {}
    for n, raw in enumerate(rows[header_index + 1 :], start=header_index + 2):
        if not any(str(c).strip() for c in raw):
            continue
        values = {field: (str(raw[i]).strip() if i < len(raw) else "") for i, field in mapping.items()}
        errors = []

        if not values.get("part_number"):
            errors.append("Missing part number")

        raw_cost = values.get("unit_cost", "")
        cost = _cost(raw_cost) if raw_cost else None
        if not raw_cost:
            errors.append("Missing cost")
        elif cost is None:
            errors.append(f"Cost '{raw_cost}' is not a number")
        elif cost <= 0:
            errors.append("Cost must be greater than 0")

        raw_year = values.get("model_year", "")
        year = _model_year(raw_year) if raw_year else None
        if raw_year and year is None:
            errors.append(f"Model year '{raw_year}' not understood")
        if not raw_year and not values.get("program"):
            errors.append("Needs a model year or a program")

        key = (values.get("part_number", "").upper(), values.get("program", "").lower(), year, cost)
        if not errors and key in seen:
            errors.append(f"Duplicate of row {seen[key]}")

        if errors:
            rejected.append({"row": n, "errors": errors, "values": values})
        else:
            seen[key] = n
            valid.append({"row": n, "values": values, "cost": cost, "model_year": year})
    return valid, rejected


def import_costs(owner, data: bytes, filename: str, *, dry_run=False, is_sample=False, uploaded_by=None) -> dict:
    rows = read_rows(data, filename)
    header_index, mapping = _find_header(rows)
    valid, rejected = validate(rows, header_index, mapping)
    report = {
        "filename": filename,
        "dry_run": dry_run,
        "total_rows": len(valid) + len(rejected),
        "valid_rows": len(valid),
        "imported_rows": 0,
        "rejected": rejected,
        "batch_id": None,
    }
    if dry_run:
        return report

    with transaction.atomic():
        batch = ImportBatch.objects.create(
            workspace_owner=owner,
            uploaded_by=uploaded_by,
            filename=filename,
            total_rows=report["total_rows"],
            imported_rows=len(valid),
            rejected_rows=len(rejected),
            rejected_json=rejected,
            is_sample=is_sample,
        )
        for entry in valid:
            values = entry["values"]
            part = Part.objects.filter(workspace_owner=owner, part_number__iexact=values["part_number"]).first()
            if part is None:
                part = Part.objects.create(
                    workspace_owner=owner,
                    part_number=values["part_number"],
                    description=values.get("description", ""),
                    material=values.get("material", ""),
                )
            else:
                changed = [f for f in ("description", "material") if not getattr(part, f) and values.get(f)]
                for field in changed:
                    setattr(part, field, values[field])
                if changed:
                    part.save(update_fields=[*changed, "updated_at"])
            supplier = None
            if values.get("supplier"):
                supplier, _ = Supplier.objects.get_or_create(workspace_owner=owner, name=values["supplier"])
            HistoricalCost.objects.create(
                workspace_owner=owner,
                part=part,
                unit_cost=entry["cost"],
                program=values.get("program", ""),
                model_year=entry["model_year"],
                supplier=supplier,
                source=f"{filename} row {entry['row']}",
                is_sample=is_sample,
                import_batch=batch,
            )
    report["imported_rows"] = len(valid)
    report["batch_id"] = batch.pk
    return report
