"""#28 (T6) — head-to-head: Orbit vs a general-purpose assistant, scored blind by the two non-AI-lead teammates.

Two subcommands.

  build   Answer every question with Orbit (shipped Ask Orbit path) and with the assistant arm,
          then write
            h2h_blind_sheet.csv   shuffled items; each answer randomly put in column A or B; no system names
            h2h_key_SEALED.csv    which system is A / B per item — keep away from the scorers until scoring is done
          Assistant answers come from EITHER --assistant-answers answers.csv (columns id, answer; collected by
          hand from e.g. ChatGPT or Claude.ai with the same corpus files uploaded) OR, with ANTHROPIC_API_KEY,
          the API arm in orbit_eval.answers.assistant_answer. With neither, a template sheet is written instead.
          The AI lead must not score; ``build`` never fills a score.

  score   python eval/head_to_head.py score --key h2h_key_SEALED.csv scorer1.csv scorer2.csv
          Unblinds and reports, per system, the share of items scored correct AND grounded (T6's metric,
          target >= 20 pp advantage), the full label distribution, and Cohen's kappa between the scorers.
          Disagreements are listed for a consensus pass; consensus labels are what gets reported.

Scoring scale (from the syllabus §7.1): correctness = correct | partial | incorrect | refused;
grounding = grounded | ungrounded | fabricated.
"""

import argparse
import csv
import json
import random
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from orbit_eval.env import REPO, RESULTS, git_commit, has_api_key, rel  # noqa: E402
from orbit_eval.metrics import cohens_kappa  # noqa: E402

SHEET_COLUMNS = [
    "item", "question", "reference_answer (from the files; check it)",
    "answer_A", "A_correctness (correct|partial|incorrect|refused)", "A_grounding (grounded|ungrounded|fabricated)",
    "answer_B", "B_correctness (correct|partial|incorrect|refused)", "B_grounding (grounded|ungrounded|fabricated)",
    "scorer", "notes",
]


def short(col: str) -> str:
    return col.split(" (")[0]


def build(args) -> dict:
    from orbit_eval.env import setup

    setup()
    from orbit_eval.answers import assistant_answer, blind_text, orbit_answer
    from orbit_eval.ingest import ingest_corpus, make_user, manifest
    from retrieval_eval import load_questions

    questions = load_questions(args.questions)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    assistant = {}
    assistant_source = None
    if args.assistant_answers:
        assistant = {r["id"]: r["answer"] for r in csv.DictReader(open(args.assistant_answers, encoding="utf-8"))}
        assistant_source = f"manual CSV {Path(args.assistant_answers).name}"
    elif has_api_key():
        corpus = manifest()
        assistant = {q["id"]: assistant_answer(corpus, q["question"], args.assistant_model)["answer"] for q in questions}
        assistant_source = f"API arm, {args.assistant_model}, all corpus files in context"

    user = make_user()
    ingest_corpus(user)
    orbit = {q["id"]: orbit_answer(user, q["question"]) for q in questions}
    orbit_modes = sorted({a["mode"] for a in orbit.values()})
    (out_dir / "h2h_orbit_answers.json").write_text(json.dumps(orbit, indent=2))

    complete = bool(assistant) and all(q["id"] in assistant for q in questions)
    rng = random.Random(args.seed)
    order = list(questions)
    rng.shuffle(order)

    sheet = out_dir / ("h2h_blind_sheet.csv" if complete else "h2h_blind_sheet_TEMPLATE.csv")
    with open(sheet, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(SHEET_COLUMNS)
        key_rows = []
        for n, q in enumerate(order, start=1):
            if complete:
                pair = [("orbit", blind_text(orbit[q["id"]]["answer"])), ("assistant", blind_text(assistant[q["id"]]))]
                rng.shuffle(pair)
                key_rows.append({"item": n, "question_id": q["id"], "A": pair[0][0], "B": pair[1][0]})
                a_text, b_text = pair[0][1], pair[1][1]
            else:
                a_text = b_text = "(answer not generated yet: see eval/README.md, head-to-head)"
            w.writerow([n, q["question"], q.get("reference_answer", ""), a_text, "", "", b_text, "", "", "", ""])
    key_path = None
    if complete:
        key_path = out_dir / "h2h_key_SEALED.csv"
        with open(key_path, "w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=["item", "question_id", "A", "B"])
            w.writeheader()
            w.writerows(key_rows)

    report = {
        "deliverable": "#28 head-to-head (T6)", "commit": git_commit(), "questions_file": Path(args.questions).name,
        "n_questions": len(questions), "seed": args.seed, "orbit_modes": orbit_modes,
        "assistant_source": assistant_source, "blind_sheet": rel(sheet), "complete": complete,
        "key": rel(key_path) if key_path else None,
        "warning": None if "ai" in orbit_modes else
        "Orbit answered in retrieval-only mode (no API key): its answers are snippet lists, which a scorer can "
        "recognise, and they are not what the product does with AI on. Do not report a head-to-head built this way.",
    }
    (out_dir / "h2h_build.json").write_text(json.dumps(report, indent=2))
    print(json.dumps({k: v for k, v in report.items() if k != "warning"}, indent=2))
    if report["warning"]:
        print("WARNING:", report["warning"])
    return report


def score(args) -> dict:
    key = {r["item"]: r for r in csv.DictReader(open(args.key, encoding="utf-8"))}
    sheets = []
    for path in args.sheets:
        rows = {}
        for r in csv.DictReader(open(path, encoding="utf-8")):
            rows[r["item"]] = {short(k): (v or "").strip().lower() for k, v in r.items()}
        sheets.append(rows)

    items = sorted(set(key) & set.intersection(*(set(s) for s in sheets)), key=int)
    per_system = {"orbit": [], "assistant": []}
    kappas, disagreements = {}, []
    for dim in ("correctness", "grounding"):
        a_labels, b_labels = [], []
        for it in items:
            for slot in ("A", "B"):
                a_labels.append(sheets[0][it][f"{slot}_{dim}"])
                b_labels.append(sheets[-1][it][f"{slot}_{dim}"])
                if sheets[0][it][f"{slot}_{dim}"] != sheets[-1][it][f"{slot}_{dim}"]:
                    disagreements.append({"item": it, "slot": slot, "dimension": dim,
                                          "scorer1": sheets[0][it][f"{slot}_{dim}"],
                                          "scorer2": sheets[-1][it][f"{slot}_{dim}"]})
        kappas[dim] = cohens_kappa(a_labels, b_labels) if len(sheets) > 1 else None
    for it in items:
        for slot in ("A", "B"):
            system = key[it][slot]
            labels = sheets[0][it]  # scorer 1, or the consensus sheet when only one is given
            per_system[system].append((labels[f"{slot}_correctness"], labels[f"{slot}_grounding"]))

    summary = {}
    for system, labels in per_system.items():
        n = len(labels)
        cg = sum(1 for c, g in labels if c == "correct" and g == "grounded")
        summary[system] = {"n": n, "correct_and_grounded": cg, "rate": round(cg / n, 4) if n else None,
                           "correctness": dict(Counter(c for c, _ in labels)),
                           "grounding": dict(Counter(g for _, g in labels))}
    delta = None
    if summary["orbit"]["rate"] is not None and summary["assistant"]["rate"] is not None:
        delta = round(100 * (summary["orbit"]["rate"] - summary["assistant"]["rate"]), 1)
    report = {"n_items": len(items), "per_system": summary, "orbit_minus_assistant_pp": delta,
              "t6_target_pp": 20, "kappa": kappas, "disagreements": disagreements,
              "note": "Rates use the first sheet given; pass the consensus sheet first once disagreements are resolved."}
    print(json.dumps(report, indent=2))
    return report


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build")
    b.add_argument("--questions", default=str(REPO / "eval" / "golden" / "synthetic_questions_v0.csv"))
    b.add_argument("--assistant-answers")
    b.add_argument("--assistant-model", default="claude-sonnet-4-6")
    b.add_argument("--seed", type=int, default=372)
    b.add_argument("--out-dir", default=str(RESULTS))
    s = sub.add_parser("score")
    s.add_argument("--key", required=True)
    s.add_argument("sheets", nargs="+")
    args = ap.parse_args(argv)
    return build(args) if args.cmd == "build" else score(args)


if __name__ == "__main__":
    main()
