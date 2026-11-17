"""#31 (T7) — COGS per extraction / query / agent run, converted to cost per seat and gross margin.

Unit costs come from one of two places, and the report says which:

  measured   ``--db sqlite:///path`` or ``--db postgres://...``: averages of the LlmUsage rows that
             core.usage writes on every Claude call (#23). Extraction = summed per file (description +
             engineering profile), query = per call, agent = summed per BOM line (research steps + summary).
  sep6       No usage rows (no API key in the evaluation environment): the token profile from the
             6 Sep 2026 production cost model (register rows M1-M3), re-priced with core.usage.PRICES.
             These are NOT re-measured and are labelled as such everywhere.

Usage per customer (8 seats, 300 files, 600 questions, 150 BOM lines a month) is the Sep 6
archetype (register A1-A4): assumptions awaiting interview evidence. Candidate prices are
illustrative inputs for #17, not a recommendation.

Run:  backend/.venv/bin/python eval/cogs.py [--db sqlite:///backend/db.sqlite3]
"""

import argparse
import json
import os
import sys
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from orbit_eval.env import BACKEND, RESULTS, git_commit  # noqa: E402

sys.path.insert(0, str(BACKEND))
from core.usage import PRICE_SOURCE, cost_usd  # noqa: E402

# Sep 6 cost model, register M1-M3 (token profile per action). Not re-measured.
SEP6 = {
    "extraction": {"model": "claude-haiku-4-5", "in": 2130, "out": 305, "searches": 0,
                   "label": "M1 tokens per file ingestion (Sep 6 register)"},
    "query": {"model": "claude-sonnet-4-6", "in": 3100, "out": 420, "searches": 0,
              "label": "M2 tokens per question (Sep 6 register)"},
    "agent_line": {"model": "claude-sonnet-4-6", "in": 38650, "out": 2145, "searches": 5.5,
                   "label": "M3 tokens per sourced BOM line, 2 runs (Sep 6 register)"},
}
# Haiku closing summary per line: not itemised in tokens in the Sep 6 model; implied by its stated
# $0.2047 per line minus Sonnet tokens + 5.5 searches ($0.203125) = ~$0.0016.
SEP6_SUMMARY_USD = Decimal("0.0016")

ARCHETYPE = {"seats": 8, "files": 300, "questions": 600, "bom_lines": 150,
             "label": "Sep 6 archetype A1-A4 (assumption, awaiting interview evidence)"}
CANDIDATE_PRICES = [25, 39, 59]  # $/seat/month; 39 is H6's hypothesis. Illustrative only.
MARGIN_TARGET = Decimal("0.70")  # T7
# Sep 6 Section 6: cash platform cost excl. compliance and people, per customer per month.
PLATFORM_PER_CUSTOMER = {"pilot (5 customers)": Decimal("513") / 5, "growth (25)": Decimal("1645") / 25,
                         "scale (100)": Decimal("5183") / 100}


def sep6_unit_costs() -> dict:
    out = {}
    for k, v in SEP6.items():
        c = cost_usd(v["model"], v["in"], v["out"], web_searches=Decimal(str(v["searches"])))
        if k == "agent_line":
            c += SEP6_SUMMARY_USD
        out[k] = {"usd": c, "source": "sep6", "basis": v["label"], "n": "2 runs" if k == "agent_line" else "not stated"}
    return out


def measured_unit_costs(db_url: str) -> dict:
    """Average cost per action from LlmUsage rows in the database at ``db_url``."""
    os.environ["DATABASE_URL"] = db_url
    os.environ.setdefault("SECRET_KEY", "orbit-eval-only")
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    import django

    django.setup()
    from core.models import LlmUsage

    def summed_by_target(**filters) -> dict:
        totals = {}
        for row in LlmUsage.objects.filter(error="", **filters).values("target", "cost_usd"):
            totals[row["target"]] = totals.get(row["target"], Decimal(0)) + (row["cost_usd"] or 0)
        return totals

    out = {}
    files = summed_by_target(path="extraction")  # target = file name
    if files:
        out["extraction"] = {"usd": sum(files.values()) / len(files), "source": "measured", "n": f"{len(files)} files",
                             "basis": "LlmUsage path=extraction, description + profile summed per file"}
    queries = [r.cost_usd or 0 for r in LlmUsage.objects.filter(path="query", error="").exclude(operation__startswith="eval_")]
    if queries:
        out["query"] = {"usd": sum(queries) / len(queries), "source": "measured", "n": f"{len(queries)} queries",
                        "basis": "LlmUsage path=query (Ask Orbit + chat), per call"}
    lines = {k: v for k, v in summed_by_target(path="agent").items() if "/item:" in k}
    if lines:
        out["agent_line"] = {"usd": sum(lines.values()) / len(lines), "source": "measured", "n": f"{len(lines)} BOM lines",
                             "basis": "LlmUsage path=agent, research steps + summary summed per BOM line"}
    return out


def per_customer(unit: dict, usage: dict) -> dict:
    files = unit["extraction"]["usd"] * usage["files"]
    questions = unit["query"]["usd"] * usage["questions"]
    lines = unit["agent_line"]["usd"] * usage["bom_lines"]
    total = files + questions + lines
    return {"files": files, "questions": questions, "bom_lines": lines, "total": total, "per_seat": total / usage["seats"]}


def main(argv=None) -> dict:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--db", help="DATABASE_URL holding LlmUsage rows from real runs")
    ap.add_argument("--out", default=str(RESULTS / "cogs.json"))
    args = ap.parse_args(argv)

    unit = sep6_unit_costs()
    if args.db:
        unit.update(measured_unit_costs(args.db))
    cust = per_customer(unit, ARCHETYPE)
    seat = cust["per_seat"]

    margins = []
    for price in CANDIDATE_PRICES:
        p = Decimal(price)
        row = {"price_per_seat": price, "ai_only_margin": float(1 - seat / p)}
        for name, platform in PLATFORM_PER_CUSTOMER.items():
            row[f"margin_with_platform_{name}"] = float(1 - (seat + platform / ARCHETYPE["seats"]) / p)
        margins.append(row)

    # Usage level where AI-only margin at each price drops below the T7 target, solving for BOM lines.
    breaks = []
    fixed_part = cust["files"] + cust["questions"]
    for price in CANDIDATE_PRICES:
        budget = (1 - MARGIN_TARGET) * Decimal(price) * ARCHETYPE["seats"] - fixed_part
        lines = budget / unit["agent_line"]["usd"] if budget > 0 else Decimal(0)
        breaks.append({"price_per_seat": price, "bom_lines_per_customer_month_at_70pct": int(lines),
                       "per_seat": round(float(lines) / ARCHETYPE["seats"], 1)})

    report = {
        "deliverable": "#31 COGS (T7)", "commit": git_commit(), "price_source": PRICE_SOURCE,
        "unit_costs": {k: {**v, "usd": float(v["usd"])} for k, v in unit.items()},
        "unit_cost_sources": sorted({v["source"] for v in unit.values()}),
        "usage": ARCHETYPE, "per_customer_month": {k: round(float(v), 2) for k, v in cust.items()},
        "margins": margins, "margin_breakpoints": breaks, "platform_per_customer": {k: float(v) for k, v in PLATFORM_PER_CUSTOMER.items()},
    }
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(report, indent=2))

    print(f"Unit costs ({', '.join(report['unit_cost_sources'])}; prices: {PRICE_SOURCE})")
    for k, v in unit.items():
        print(f"  {k:<11} ${float(v['usd']):.4f}  [{v['source']}] {v['basis']}")
    print(f"Per customer/month: ${float(cust['total']):.2f} (files ${float(cust['files']):.2f}, questions "
          f"${float(cust['questions']):.2f}, BOM lines ${float(cust['bom_lines']):.2f}); per seat ${float(seat):.2f}")
    for m in margins:
        print(f"  ${m['price_per_seat']}/seat: AI-only gross margin {m['ai_only_margin']:.1%}")
    for b in breaks:
        print(f"  ${b['price_per_seat']}/seat: margin < 70% above {b['bom_lines_per_customer_month_at_70pct']} BOM lines/customer/month")
    return report


if __name__ == "__main__":
    main()
