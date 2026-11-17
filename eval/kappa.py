"""Cohen's kappa between two labellers (or a labeller and the LLM judge) on the same items.

Works for every human-labelling sheet in eval/: answer-quality sheets (#27),
extraction relabelling (#25) and the blind head-to-head sheet (#28).
Columns are matched by the text before the first " (" so the hint in the header
("faithfulness (grounded | ungrounded | fabricated)") does not matter.

  python eval/kappa.py results/answer_labels_labeller1.csv results/answer_labels_labeller2.csv
  python eval/kappa.py sheet1.csv sheet2.csv --id item_id --columns correctness faithfulness
  python eval/kappa.py labeller1.csv --judge results/answer_quality.json   # judge vs human

Report n and kappa per column. Rule of thumb used in the plan: an LLM judge may only replace
human labels for a dimension where judge-vs-human kappa >= 0.6 on the double-labelled subset.
"""

import argparse
import csv
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from orbit_eval.metrics import cohens_kappa  # noqa: E402

DEFAULT_COLUMNS = ["faithfulness", "relevance", "citation_correct", "correctness", "grounding"]


def read(path, id_col):
    rows = {}
    with open(path, newline="", encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            rows[r[id_col]] = {k.split(" (")[0].strip(): (v or "").strip().lower() for k, v in r.items()}
    return rows


def main(argv=None) -> dict:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("a")
    ap.add_argument("b", nargs="?")
    ap.add_argument("--judge", help="answer_quality.json with judge labels, compared against sheet A")
    ap.add_argument("--id", default="item_id")
    ap.add_argument("--columns", nargs="*", default=DEFAULT_COLUMNS)
    args = ap.parse_args(argv)

    a = read(args.a, args.id)
    if args.judge:
        items = json.load(open(args.judge))["items"]
        b = {i["id"]: {k: str(v).lower() for k, v in i.get("judge", {}).items()} for i in items}
    elif args.b:
        b = read(args.b, args.id)
    else:
        raise SystemExit("give a second sheet or --judge")

    ids = sorted(set(a) & set(b))
    out = {}
    for col in args.columns:
        if not any(col in a[i] for i in ids):
            continue
        out[col] = cohens_kappa([a[i].get(col, "") for i in ids], [b[i].get(col, "") for i in ids])
        print(f"{col:<18} n={out[col]['n']:<4} kappa={out[col]['kappa']}  agreement={out[col]['observed_agreement']}")
    return out


if __name__ == "__main__":
    main()
