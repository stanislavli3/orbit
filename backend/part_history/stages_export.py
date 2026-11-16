"""Estimate stages per part as Excel (SCRUM-36).

Historical/surrogate estimate -> should-cost range (SCRUM-30) -> supplier
quotes, so leadership can see how each estimate firmed up. Built from live
data on every request.
"""

import io

from openpyxl import Workbook
from openpyxl.formatting.rule import FormulaRule
from openpyxl.styles import PatternFill

from bom_agent.excel_export import AMBER_FILL, GREEN_FILL, _set_widths, _style_sheet
from .estimator import estimate_row
from .models import Quote
from .should_cost import REFERENCE_NOTE, should_cost_row

RED_FILL = PatternFill("solid", fgColor="FFFFC7CE")
HEADERS = [
    "Line", "Part number", "Description", "Qty",
    "Historical estimate", "Historical confidence", "Historical basis",
    "Should-cost low", "Should-cost expected", "Should-cost high", "Should-cost basis",
    "Supplier", "Quote unit price", "Quoted on", "Quote source", "Quote vs should-cost",
]


def quote_status(price: float, low: float, high: float) -> str:
    if price < low:
        return "Beats"
    if price > high:
        return "Exceeds"
    return "Meets"


def build_stages_workbook(bom, owner) -> Workbook:
    wb = Workbook()
    sheet = wb.active
    sheet.title = "Estimate Stages"
    sheet.append(HEADERS)
    for row in bom.rows.all():
        hist = estimate_row(owner, row)
        sc = should_cost_row(row)
        est = hist["estimate"]
        base = [
            row.line_no, row.part_number, row.description, row.quantity,
            float(est["unit_cost"]) if est else None, hist["confidence"],
            "; ".join(hist["assumptions"]),
            float(sc["low"]), float(sc["expected"]), float(sc["high"]), "; ".join(sc["basis"]),
        ]
        quotes = list(Quote.objects.filter(workspace_owner=owner, part__part_number__iexact=row.part_number)
                      .select_related("supplier")) if row.part_number else []
        if not quotes:
            sheet.append(base + [None, None, None, None, "No quote yet"])
        for q in quotes:
            price = float(q.unit_price)
            sheet.append(base + [q.supplier.name, price, q.quoted_at, q.source,
                                 quote_status(price, float(sc["low"]), float(sc["high"]))])

    last = sheet.max_row
    if last > 1:
        rng = f"M2:M{last}"
        sheet.conditional_formatting.add(rng, FormulaRule(formula=['AND(ISNUMBER($M2),$M2<$H2)'], fill=GREEN_FILL))
        sheet.conditional_formatting.add(rng, FormulaRule(formula=['AND(ISNUMBER($M2),$M2>=$H2,$M2<=$J2)'], fill=AMBER_FILL))
        sheet.conditional_formatting.add(rng, FormulaRule(formula=['AND(ISNUMBER($M2),$M2>$J2)'], fill=RED_FILL))
    for r in range(2, last + 1):
        for col in "EHIJM":
            sheet[f"{col}{r}"].number_format = '"$"#,##0.00'
    _style_sheet(sheet)
    _set_widths(sheet, {"B": 16, "C": 30, "G": 50, "K": 60, "L": 22, "O": 24, "P": 16})
    sheet.freeze_panes = "E2"

    notes = wb.create_sheet("Notes")
    notes.append(["Note"])
    for text in [
        f"BOM {bom.reference}, regenerated from live data.",
        "Stages: historical estimate (similar past parts) -> should-cost range -> supplier quote.",
        "Quote colour: green = beats should-cost low, amber = within range, red = exceeds high.",
        f"Should-cost rates: {REFERENCE_NOTE}.",
    ]:
        notes.append([text])
    _style_sheet(notes)
    _set_widths(notes, {"A": 100})
    return wb


def render_stages_workbook(bom, owner) -> bytes:
    buf = io.BytesIO()
    build_stages_workbook(bom, owner).save(buf)
    return buf.getvalue()
