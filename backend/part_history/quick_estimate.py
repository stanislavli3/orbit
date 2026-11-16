"""The thin end-to-end slice: one file in, BOM + estimate + shortlist out.

Every number in the report carries its source: BOM values via each row's
``sources``, costs via the historical cost they came from, supplier prices
via the quote.
"""

from bom_agent.serializers import BomRowSerializer
from .cost_range import cost_range, default_margin, flag_summary, price_flag
from . import handoff
from .estimator import DEFAULT_INFLATION, estimate_bom
from .lead_time import lead_time_row, mark_bottleneck
from .should_cost import should_cost_row
from .shortlist import shortlist_row


def quick_report(bom, owner, *, k=3, inflation=DEFAULT_INFLATION, margin=None) -> dict:
    margin = default_margin() if margin is None else margin
    report = estimate_bom(bom, owner, k=k, inflation=inflation)
    if bom.source_file_id:
        handoff.record(bom, "cad_finished", at=bom.source_file.created_at)
    handoff.record(bom, "bom_shared", at=bom.created_at)
    rows = {row.id: row for row in bom.rows.all()}
    for entry in report["rows"]:
        row = rows[entry["row_id"]]
        entry["row"] = BomRowSerializer(row).data
        entry["should_cost"] = should_cost_row(row)
        entry["cost_range"] = cost_range(entry, entry["should_cost"])
        entry["price_flag"] = price_flag(row, entry["cost_range"], margin)
        similar = [m["part_number"] for m in entry["matches"]]
        entry["shortlist"] = shortlist_row(owner, row, similar)
        entry["lead_time"] = lead_time_row(owner, row, similar)
        if row.part_number:
            handoff.record(bom, "shortlist_ready", part_number=row.part_number)
    report["critical_path"] = mark_bottleneck(report["rows"])
    report["price_flags"] = flag_summary(report["rows"], margin)
    report["bom"] = {
        "id": bom.id,
        "reference": bom.reference,
        "status": bom.status,
        "error": bom.error,
        "source_name": bom.source_name,
        "review_count": sum(1 for r in report["rows"] if r["row"]["needs_review"]),
    }
    return report
