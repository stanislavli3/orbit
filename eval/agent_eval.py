"""#30 (T5) — BOM agent evaluation: task success, human interventions, failure taxonomy, cost and latency.

Task (one "run" = one BOM file x one supplier-reply scenario), verified on database
state, not on text (tau2-bench style):

  1. extract the BOM from the file (bom_agent.tasks.build_bom)
  2. per line: history-based estimate + approved-supplier shortlist
  3. per line: draft the RFQ from the row (rfq_views.draft_from_row), address it to the
     top shortlisted supplier, send it (demo mode: no Gmail)
  4. inject the scenario's supplier reply through rfq_loop.simulate_reply (or, for
     "silent", run escalate_silent_rfqs six days later)
  5. check every line reached the expected end state:
       quote   -> RFQ quoted, part_history Quote $4.85 / 21 days / MOQ 500, row sourced
       unclear -> needs_review (human review queue)
       decline -> declined, supplier excluded, next suppliers computed
       info    -> info_requested + needs_attention
       silent  -> escalated + needs_attention

Each line logs the human interventions the harness had to script to keep going
(no supplier candidate, missing supplier e-mail, unconfirmed quote-critical fields).
"Autonomous success" = end state correct AND no intervention AND the end state needs no person.

Workspaces:  cold     cost history + spend imported as-is (no supplier approved, no e-mails)
             curated  same, then every imported supplier approved and given an e-mail
                      (a one-time buyer setup step, scripted here)

``--with-research`` additionally runs the LLM sourcing agent (research_pipeline) per BOM;
it needs ANTHROPIC_API_KEY and is recorded as "not run" otherwise.

Run:  backend/.venv/bin/python eval/agent_eval.py
"""

import argparse
import csv
import json
import sys
import time
import uuid
from collections import Counter
from datetime import timedelta
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
from orbit_eval.env import REPO, RESULTS, git_commit, has_api_key, setup  # noqa: E402

SCENARIOS = ["quote", "unclear", "decline", "info", "silent"]
EXPECTED = {"quote": "quoted", "unclear": "needs_review", "decline": "declined",
            "info": "info_requested", "silent": "escalated"}
NEEDS_PERSON = {"unclear", "info", "silent", "decline"}  # decline: next RFQ is not sent automatically
PLACEHOLDER_EMAIL = "rfq-eval@example.invalid"

TAXONOMY = [
    ("extraction_no_rows", "BOM extraction returned no lines for a file that has a BOM"),
    ("no_supplier_candidate", "Shortlist empty: no approved supplier with history for the part or material"),
    ("supplier_email_missing", "Shortlisted supplier has no contact e-mail; RFQ cannot be sent"),
    ("critical_fields_unconfirmed", "RFQ sent with quote-critical fields 'to be confirmed' (tolerance, stock size, due date...)"),
    ("send_failed", "RFQ send raised or stored send_failed"),
    ("wrong_end_state", "Reply did not move the RFQ to the expected state"),
    ("reply_misparsed", "Quote committed with wrong price / lead time / MOQ"),
    ("research_api_error", "LLM sourcing agent: API error"),
    ("research_insufficient_data", "LLM sourcing agent flagged insufficient data"),
    ("research_zero_quotes", "LLM sourcing agent ended with no quotes and no flag"),
]
HARD_INTERVENTIONS = {"no_supplier_candidate", "supplier_email_missing"}


def bom_docs():
    return [m for m in csv.DictReader(open(REPO / "eval" / "corpus" / "manifest.csv")) if m["bom_role"] == "bom"]


def setup_workspace(username: str, curated: bool):
    from django.contrib.auth.models import User

    from part_history.importer import import_costs
    from part_history.models import Supplier
    from part_history.spend_import import import_spend
    from projects.models import Project

    user = User.objects.create(username=f"{username}-{uuid.uuid4().hex[:6]}")
    for doc, fn in (("samples/part_cost_history_sample.csv", import_costs), ("samples/supplier_spend_sample.csv", import_spend)):
        path = REPO / doc
        if fn is import_costs:
            fn(user, path.read_bytes(), path.name, is_sample=True)
        else:
            fn(user, path.read_bytes(), path.name)
    if curated:
        for s in Supplier.objects.filter(workspace_owner=user):
            s.is_approved = True
            s.contact_email = s.contact_email or f"quotes+{s.pk}@example.invalid"
            s.save()
    return user, Project.objects.create(name=f"agent eval {username}", owner=user)


def run_one(doc: dict, scenario: str, curated: bool, n: int) -> dict:
    from bom_agent import rfq_loop
    from bom_agent.rfq_views import draft_from_row
    from bom_agent.tasks import build_bom
    from core.models import LlmUsage
    from files_api.models import UploadedFile
    from part_history.estimator import estimate_row
    from part_history.models import Supplier
    from part_history.shortlist import shortlist_row

    user, project = setup_workspace(f"agent-{n}", curated)
    path = REPO / doc["path"]
    data = path.read_bytes()
    t0 = time.perf_counter()
    usage_start = LlmUsage.objects.count()

    f = UploadedFile.objects.create(project=project, uploaded_by=user, original_name=path.name,
                                    file_type=doc["file_type"], s3_key=f"agent-eval/{user.username}/{path.name}", file_size=len(data))
    bom = build_bom(f, data)
    run = {"run": f"{doc['doc_id']}-{scenario}-{'curated' if curated else 'cold'}", "doc_id": doc["doc_id"],
           "scenario": scenario, "workspace": "curated" if curated else "cold", "lines": [], "failures": []}
    rows = list(bom.rows.all())
    if not rows:
        run["failures"].append({"line": None, "category": "extraction_no_rows"})

    for row in rows:
        line = {"line_no": row.line_no, "part_number": row.part_number, "interventions": []}
        est = estimate_row(user, row)
        line["estimate"] = bool(est.get("estimate"))
        picks = shortlist_row(user, row)["suppliers"]
        line["shortlist_size"] = len(picks)

        rfq = draft_from_row(row, user)
        if picks:
            supplier = Supplier.objects.get(pk=picks[0]["supplier_id"])
            rfq.supplier_name, rfq.supplier_email = supplier.name, supplier.contact_email
        else:
            line["interventions"].append("no_supplier_candidate")
            rfq.supplier_name = "Supplier picked by a person (eval)"
        if not rfq.supplier_email:
            if picks:
                line["interventions"].append("supplier_email_missing")
            rfq.supplier_email = PLACEHOLDER_EMAIL
        rfq.save()
        if rfq.assumptions:
            line["interventions"].append("critical_fields_unconfirmed")
            line["unconfirmed_fields"] = len(rfq.assumptions)

        try:
            rfq_loop.send_rfq(rfq)
        except Exception as exc:
            line["end_state"] = "send_failed"
            line["error"] = f"{type(exc).__name__}: {exc}"[:200]
            run["failures"].append({"line": row.line_no, "category": "send_failed"})
            run["lines"].append(line)
            continue

        if scenario == "silent":
            later = rfq.sent_at + timedelta(days=6)
            rfq_loop.escalate_silent_rfqs(now=later)
        else:
            rfq_loop.simulate_reply(rfq, scenario)
        rfq.refresh_from_db()
        row.refresh_from_db()
        line["end_state"] = rfq.status
        ok = rfq.status == EXPECTED[scenario]
        if scenario == "quote" and ok:
            q = rfq.quote
            parsed_ok = (q is not None and q.unit_price == Decimal("4.85") and q.lead_time_days == 21
                         and q.quantity == 500 and row.sourcing_status == "sourced")
            if not parsed_ok:
                run["failures"].append({"line": row.line_no, "category": "reply_misparsed"})
            ok = ok and parsed_ok
        if scenario == "decline" and ok:
            excluded = {s.lower() for s in rfq.excluded_suppliers}
            ok = rfq.supplier_name.lower() in excluded and all(
                p["supplier"].lower() not in excluded for p in rfq.next_suppliers)
            line["next_suppliers"] = len(rfq.next_suppliers)
        if scenario in ("info", "silent"):
            ok = ok and rfq.needs_attention
        if not ok and rfq.status != EXPECTED[scenario]:
            run["failures"].append({"line": row.line_no, "category": "wrong_end_state"})
        line["state_ok"] = ok
        for i in line["interventions"]:
            run["failures"].append({"line": row.line_no, "category": i})
        run["lines"].append(line)

    run["latency_ms"] = round((time.perf_counter() - t0) * 1000, 1)
    calls = LlmUsage.objects.order_by("pk")[usage_start:]
    run["llm_calls"] = len(calls)
    run["llm_cost_usd"] = float(sum((c.cost_usd or 0) for c in calls))
    lines = run["lines"]
    run["n_lines"] = len(lines)
    run["task_success"] = bool(lines) and all(l.get("state_ok") for l in lines)
    run["hard_interventions"] = sum(1 for l in lines for i in l["interventions"] if i in HARD_INTERVENTIONS)
    run["soft_interventions"] = sum(1 for l in lines for i in l["interventions"] if i not in HARD_INTERVENTIONS)
    run["autonomous_success"] = (run["task_success"] and run["hard_interventions"] == 0
                                 and run["soft_interventions"] == 0 and scenario not in NEEDS_PERSON)
    # Same, but accepting RFQs that go out with "to be confirmed" fields (what demo mode does today).
    run["autonomous_if_unconfirmed_fields_accepted"] = (run["task_success"] and run["hard_interventions"] == 0
                                                        and scenario not in NEEDS_PERSON)
    return run


def run_research(doc: dict, n: int) -> dict:
    """LLM sourcing agent on one BOM. Only called with an API key."""
    from bom_agent.models import BomLineItem, BomResearchRun
    from bom_agent.research_pipeline import run_bom_research
    from bom_agent.tasks import build_bom
    from core.models import LlmUsage
    from files_api.models import UploadedFile

    user, project = setup_workspace(f"research-{n}", curated=True)
    path = REPO / doc["path"]
    data = path.read_bytes()
    f = UploadedFile.objects.create(project=project, uploaded_by=user, original_name=path.name,
                                    file_type=doc["file_type"], s3_key=f"research-eval/{user.username}/{path.name}", file_size=len(data))
    bom = build_bom(f, data)
    run = BomResearchRun.objects.create(project=project, created_by=user, status="researching")
    for row in bom.rows.all():
        BomLineItem.objects.create(run=run, part_name=row.description or row.part_number, part_number=row.part_number,
                                   material_spec=row.material, quantity=row.quantity)
    t0 = time.perf_counter()
    with patch("bom_agent.excel_export.upload_bom_workbook", return_value=""):
        run_bom_research(run.pk)
    run.refresh_from_db()
    calls = LlmUsage.objects.filter(target__startswith=f"bom_run:{run.pk}/")
    items = list(run.line_items.prefetch_related("quotes"))
    tags = []
    for item in items:
        if item.quotes.count() == 0:
            tags.append("research_insufficient_data" if item.status == "needs_input" else "research_zero_quotes")
    tags += ["research_api_error" for c in calls if c.error]
    return {
        "doc_id": doc["doc_id"], "status": run.status, "n_items": len(items),
        "sourced": sum(1 for i in items if i.status == "sourced"),
        "latency_s": round(time.perf_counter() - t0, 1), "llm_calls": calls.count(),
        "input_tokens": sum(c.input_tokens for c in calls), "output_tokens": sum(c.output_tokens for c in calls),
        "web_searches": sum(c.web_search_requests for c in calls),
        "cost_usd": float(sum((c.cost_usd or 0) for c in calls)), "failure_tags": tags,
    }


def write_taxonomy_template(runs, path: Path):
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["run", "line", "category (auto-tag)", "category definition", "human_confirmed_category",
                    "severity (blocks|degrades|cosmetic)", "labeller", "notes"])
        defs = dict(TAXONOMY)
        for r in runs:
            for fl in r["failures"]:
                w.writerow([r["run"], fl["line"], fl["category"], defs.get(fl["category"], ""), "", "", "", ""])


def main(argv=None) -> dict:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--with-research", action="store_true")
    ap.add_argument("--out", default=str(RESULTS / "agent.json"))
    args = ap.parse_args(argv)
    setup()

    docs = bom_docs()
    runs, n = [], 0
    for curated in (False, True):
        for doc in docs:
            for scenario in SCENARIOS:
                n += 1
                runs.append(run_one(doc, scenario, curated, n))

    research = {"ran": False, "reason": "ANTHROPIC_API_KEY not set" if not has_api_key() else "--with-research not given"}
    if args.with_research and has_api_key():
        research = {"ran": True, "runs": [run_research(d, i) for i, d in enumerate(docs)]}

    def summarise(rs):
        lines = [l for r in rs for l in r["lines"]]
        return {
            "n_runs": len(rs), "n_lines": len(lines),
            "task_success_rate": round(sum(r["task_success"] for r in rs) / len(rs), 4) if rs else None,
            "autonomous_success_rate": round(sum(r["autonomous_success"] for r in rs) / len(rs), 4) if rs else None,
            "autonomous_if_unconfirmed_fields_accepted_rate": round(
                sum(r["autonomous_if_unconfirmed_fields_accepted"] for r in rs) / len(rs), 4) if rs else None,
            "lines_needing_hard_intervention": sum(1 for l in lines if set(l["interventions"]) & HARD_INTERVENTIONS),
            "lines_with_unconfirmed_rfq_fields": sum(1 for l in lines if "critical_fields_unconfirmed" in l["interventions"]),
            "lines_with_estimate": sum(1 for l in lines if l.get("estimate")),
            "lines_with_shortlist": sum(1 for l in lines if l.get("shortlist_size")),
            "failure_counts": dict(Counter(f["category"] for r in rs for f in r["failures"])),
            "latency_ms_median": sorted(r["latency_ms"] for r in rs)[len(rs) // 2] if rs else None,
            "latency_ms_max": max(r["latency_ms"] for r in rs) if rs else None,
            "llm_calls": sum(r["llm_calls"] for r in rs), "llm_cost_usd": sum(r["llm_cost_usd"] for r in rs),
        }

    report = {
        "deliverable": "#30 BOM agent (T5)", "commit": git_commit(), "synthetic_corpus": True,
        "n_bom_files": len(docs), "scenarios": SCENARIOS,
        "summary": {ws: summarise([r for r in runs if r["workspace"] == ws]) for ws in ("cold", "curated")},
        "by_scenario": {f"{ws}/{s}": summarise([r for r in runs if r["workspace"] == ws and r["scenario"] == s])
                        for ws in ("cold", "curated") for s in SCENARIOS},
        "taxonomy": dict(TAXONOMY), "research_agent": research, "runs": runs,
    }
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(report, indent=2, default=str))
    write_taxonomy_template(runs, Path(args.out).parent / "agent_failure_taxonomy.csv")

    print(f"BOM agent: {len(docs)} BOM files x {len(SCENARIOS)} reply scenarios x 2 workspaces = {len(runs)} runs")
    for ws, s in report["summary"].items():
        print(f"  {ws:<8} task success {s['task_success_rate']:.2f}  autonomous {s['autonomous_success_rate']:.2f}  "
              f"lines {s['n_lines']}  hard-intervention lines {s['lines_needing_hard_intervention']}  "
              f"median latency {s['latency_ms_median']} ms  LLM calls {s['llm_calls']}")
        print(f"           failures {s['failure_counts']}")
    print(f"  LLM sourcing agent: {'ran' if research['ran'] else 'NOT RUN - ' + research['reason']}")
    return report


if __name__ == "__main__":
    main()
