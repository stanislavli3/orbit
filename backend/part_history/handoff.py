"""CAD-to-quote handoff timing per part and per BOM (SCRUM-75).

Steps are recorded automatically when they happen in Orbit (first time wins)
or set by hand with a date (manual always wins). A part that has no time of
its own for a step uses the BOM-wide time.
"""

import csv
import io
from datetime import datetime, time
from statistics import median

from django.utils import timezone

from bom_agent.models import Bom, BomRow
from .models import HandoffStep

STEPS = [key for key, _ in HandoffStep.STEPS]
LABELS = dict(HandoffStep.STEPS)


def record(bom, step, *, part_number="", at=None) -> None:
    """Automatic record: keeps the first time a step happened."""
    HandoffStep.objects.get_or_create(
        bom=bom, part_number=part_number, step=step,
        defaults={"workspace_owner": bom.project.owner, "at": at or timezone.now()},
    )


def set_manual(bom, step, day, *, part_number="") -> HandoffStep:
    """A person's date for a step; replaces whatever was recorded."""
    at = timezone.make_aware(datetime.combine(day, time(12)))
    obj, _ = HandoffStep.objects.update_or_create(
        bom=bom, part_number=part_number, step=step,
        defaults={"workspace_owner": bom.project.owner, "at": at, "is_manual": True},
    )
    return obj


def record_quote_received(owner, part_number, at=None) -> None:
    """A quote came in for a part: mark it on every BOM of the owner that lists the part."""
    if not part_number:
        return
    rows = BomRow.objects.filter(bom__project__owner=owner, part_number__iexact=part_number).select_related(
        "bom__project"
    )
    for row in rows:
        record(row.bom, "quote_received", part_number=row.part_number, at=at)


def _hours(delta) -> float:
    return round(delta.total_seconds() / 3600, 1)


def _part_timeline(part_number, own, shared) -> dict:
    times = {s: own.get(s) or shared.get(s) for s in STEPS}
    done = [(s, times[s]) for s in STEPS if times[s]]
    intervals = [
        {"from": a, "to": b, "label": f"{LABELS[a]} → {LABELS[b]}", "hours": _hours(tb - ta)}
        for (a, ta), (b, tb) in zip(done, done[1:])
    ]
    slowest = max(intervals, key=lambda i: i["hours"]) if intervals else None
    return {
        "part_number": part_number,
        "steps": {s: (t.isoformat() if t else None) for s, t in times.items()},
        "manual": sorted(own.get("_manual", set()) | shared.get("_manual", set())),
        "intervals": intervals,
        "total_hours": _hours(done[-1][1] - done[0][1]) if len(done) > 1 else None,
        "slowest": slowest,
    }


def bom_timeline(bom) -> dict:
    by_part: dict[str, dict] = {}
    for h in bom.handoff_steps.all():
        entry = by_part.setdefault(h.part_number, {})
        entry[h.step] = h.at
        if h.is_manual:
            entry.setdefault("_manual", set()).add(h.step)
    shared = by_part.get("", {})
    part_numbers = list(dict.fromkeys(r.part_number for r in bom.rows.all() if r.part_number))
    parts = [_part_timeline(pn, by_part.get(pn, {}), shared) for pn in part_numbers]

    all_times = [t for e in by_part.values() for k, t in e.items() if k != "_manual"]
    per_step: dict[str, list[float]] = {}
    for p in parts:
        for i in p["intervals"]:
            per_step.setdefault(i["label"], []).append(i["hours"])
    slowest = max(per_step.items(), key=lambda kv: median(kv[1]), default=None)
    return {
        "bom_id": bom.id,
        "reference": bom.reference,
        "steps": [{"key": s, "label": LABELS[s]} for s in STEPS],
        "parts": parts,
        "total_hours": _hours(max(all_times) - min(all_times)) if len(all_times) > 1 else None,
        "slowest_step": {"label": slowest[0], "median_hours": round(median(slowest[1]), 1)} if slowest else None,
    }


def summary(owner) -> dict:
    """Median CAD-to-quote time across every part the owner has timed."""
    boms = Bom.objects.filter(project__owner=owner, handoff_steps__isnull=False).distinct().prefetch_related(
        "rows", "handoff_steps"
    )
    totals, per_step = [], {}
    for bom in boms:
        for p in bom_timeline(bom)["parts"]:
            if p["total_hours"] is not None:
                totals.append(p["total_hours"])
            for i in p["intervals"]:
                per_step.setdefault(i["label"], []).append(i["hours"])
    return {
        "parts_timed": len(totals),
        "median_total_hours": round(median(totals), 1) if totals else None,
        "median_step_hours": [{"label": k, "median_hours": round(median(v), 1)} for k, v in per_step.items()],
    }


def timeline_csv(timeline) -> str:
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(["BOM", "Part number", *[LABELS[s] for s in STEPS], "Total hours", "Slowest step"])
    for p in timeline["parts"]:
        writer.writerow([
            timeline["reference"], p["part_number"], *[p["steps"][s] or "" for s in STEPS],
            "" if p["total_hours"] is None else p["total_hours"],
            p["slowest"]["label"] if p["slowest"] else "",
        ])
    return out.getvalue()
