"""Lead-time estimate per BOM line and the critical-path part (SCRUM-61).

Each estimate names its data source: quotes on this exact part, quotes on the
similar parts the cost estimate matched, or no data. The longest line is the
bottleneck a program manager plans around.
"""

from statistics import median

from .models import Quote


def _days(quotes) -> int:
    return round(median(q.lead_time_days for q in quotes))


def lead_time_row(owner, row, similar_part_numbers=()) -> dict:
    quotes = Quote.objects.filter(workspace_owner=owner, lead_time_days__isnull=False).select_related("part", "supplier")
    part_number = (row.part_number or "").upper()
    exact = [q for q in quotes if part_number and q.part and q.part.part_number.upper() == part_number]
    if exact:
        basis, used = "quote_history", exact
        text = f"Median of {len(exact)} quoted lead time{'s' if len(exact) > 1 else ''} for this part"
    else:
        similar = {pn.upper() for pn in similar_part_numbers}
        used = [q for q in quotes if q.part and q.part.part_number.upper() in similar]
        basis = "similar_parts" if used else "no_data"
        text = (f"Median of {len(used)} quoted lead time{'s' if len(used) > 1 else ''} on similar parts "
                f"({', '.join(sorted({q.part.part_number for q in used}))})") if used else \
            "No quoted lead time for this part or similar parts"
    return {
        "days": _days(used) if used else None,
        "basis": basis,
        "source": text,
        "evidence": [
            {"text": f"{q.supplier.name} quoted {q.part.part_number}: {q.lead_time_days} days on {q.quoted_at.isoformat()}",
             "source": q.source}
            for q in used
        ],
        "is_bottleneck": False,
    }


def mark_bottleneck(rows) -> dict | None:
    """Flag the longest-lead line in place; return the critical-path summary."""
    timed = [r for r in rows if r["lead_time"]["days"] is not None]
    if not timed:
        return None
    worst = max(timed, key=lambda r: r["lead_time"]["days"])
    worst["lead_time"]["is_bottleneck"] = True
    days = worst["lead_time"]["days"]
    name = worst["part_number"] or worst["description"] or f"line {worst['line_no']}"
    return {"row_id": worst["row_id"], "part_number": name, "days": days,
            "source": worst["lead_time"]["source"],
            "summary": f"Critical path: {name}, {days} days",
            "rows_without_data": len(rows) - len(timed)}
