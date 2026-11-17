"""Run every evaluation in order and write eval/results/summary.json.

  backend/.venv/bin/python eval/run_all.py [--questions eval/golden/<file>.csv] [--with-research]

Each harness also runs on its own; see eval/README.md. LLM-dependent steps (the LLM judge,
the general-assistant arm, the sourcing agent) run only when ANTHROPIC_API_KEY is set and
are reported as "not run" otherwise.
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from orbit_eval.env import REPO, RESULTS, git_commit, has_api_key, setup  # noqa: E402


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--questions", default=str(REPO / "eval" / "golden" / "synthetic_questions_v0.csv"))
    ap.add_argument("--with-research", action="store_true")
    args = ap.parse_args()
    setup()  # one throw-away DB shared by every harness in this process

    import agent_eval
    import answer_quality
    import cogs
    import extraction_eval
    import head_to_head
    import retrieval_eval

    out = {"commit": git_commit(), "api_key_present": has_api_key(), "questions": Path(args.questions).name}
    print("\n== #25 extraction =="); e = extraction_eval.main([])
    out["extraction_fields"] = e["bom"]["fields"]
    print("\n== #27 retrieval =="); r = retrieval_eval.main(["--questions", args.questions])
    out["retrieval_mean_over_repeats"] = r["across_repeats"]
    print("\n== #27 answer quality =="); a = answer_quality.main(["--questions", args.questions])
    out["answer_quality"] = {k: a[k] for k in ("orbit_modes", "context_has_key_facts_rate", "citation_validity_rate", "judge_ran")}
    print("\n== #28 head-to-head =="); h = head_to_head.main(["build", "--questions", args.questions])
    out["head_to_head"] = {k: h[k] for k in ("complete", "assistant_source", "blind_sheet")}
    print("\n== #30 BOM agent =="); g = agent_eval.main(["--with-research"] if args.with_research else [])
    out["agent"] = g["summary"]
    print("\n== #31 COGS =="); c = cogs.main([])
    out["cogs"] = {k: c[k] for k in ("unit_cost_sources", "per_customer_month")}
    (RESULTS / "summary.json").write_text(json.dumps(out, indent=2, default=str))
    print(f"\nwrote {RESULTS / 'summary.json'}")


if __name__ == "__main__":
    main()
