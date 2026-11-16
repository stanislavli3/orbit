"""The thin end-to-end slice: one file in, BOM + estimate + shortlist out.

Every number in the report carries its source: BOM values via each row's
``sources``, costs via the historical cost they came from, supplier prices
via the quote.
"""

from bom_agent.serializers import BomRowSerializer
from .estimator import DEFAULT_INFLATION, estimate_bom
from .lead_time import lead_time_row, mark_bottleneck
from .should_cost import should_cost_row
from .shortlist import shortlist_row


def quick_report(bom, owner, *, k=3, inflation=DEFAULT_INFLATION) -> dict:
    report = estimate_bom(bom, owner, k=k, inflation=inflation)
    rows = {row.id: row for row in bom.rows.all()}
    for entry in report["rows"]:
        row = rows[entry["row_id"]]
        entry["row"] = BomRowSerializer(row).data
        entry["should_cost"] = should_cost_row(row)
        similar = [m["part_number"] for m in entry["matches"]]
        entry["shortlist"] = shortlist_row(owner, row, similar)
        entry["lead_time"] = lead_time_row(owner, row, similar)
    report["critical_path"] = mark_bottleneck(report["rows"])
    report["bom"] = {
        "id": bom.id,
        "reference": bom.reference,
        "status": bom.status,
        "error": bom.error,
        "source_name": bom.source_name,
        "review_count": sum(1 for r in report["rows"] if r["row"]["needs_review"]),
    }
    return report
