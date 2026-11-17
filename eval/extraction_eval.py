"""#25 — field-level accuracy and confidence calibration of structured BOM extraction.

Runs ``bom_agent.bom_extraction.extract_bom_rows`` (the same function the upload
pipeline calls) on every corpus file with bom_role bom/negative, aligns rows to
the hand-written labels in corpus/labels/bom_ground_truth.csv and reports
precision / recall / F1 for part_number, quantity, material, process, revision.
Also scores MATLAB metadata extraction against corpus/labels/matlab_ground_truth.csv.

Scoring rules (also in the report):
  * Rows are aligned by normalized part number, then by the label's match_hint
    (a substring of the predicted description) for lines with no part number.
  * Blank = "no value". Correct non-blank -> TP. Wrong non-blank -> FP and FN.
    Predicted value where the label is blank -> FP. Missed value -> FN.
  * Unmatched predicted rows count every non-blank field as FP; unmatched
    labelled lines count every non-blank field as FN.
  * Material is compared after lenient normalization (AL/ALUMINUM/AISI/SAE
    prefixes dropped, STAINLESS [STEEL] -> SS, whitespace collapsed).
  * Quantity: integers compared exactly. Revision and part number: upper-cased.

Calibration (T4): the extractor emits one row-level ``confidence``; there is no
separate material confidence, so ECE is computed for row confidence against
"material correct" and against "all five fields correct". n is tiny; read the
bins, not the ECE.

Run:  backend/.venv/bin/python eval/extraction_eval.py [--out eval/results/extraction.json]
"""

import argparse
import csv
import json
import re
import sys
import time
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from orbit_eval.env import BACKEND, EVAL, REPO, RESULTS, git_commit  # noqa: E402
from orbit_eval.metrics import abstention_thresholds, calibration, prf, score_field  # noqa: E402

sys.path.insert(0, str(BACKEND))
FIELDS = ["part_number", "quantity", "material", "process", "revision"]


def norm_material(v: str) -> str:
    v = (v or "").upper().strip()
    if v in {"-", "N/A", "NA", "NONE"}:
        return v  # kept as-is: a dash is a value the extractor chose to store
    v = re.sub(r"\b(ALUMINI?UM|AL|AISI|SAE)\b[\s-]*", "", v)
    v = re.sub(r"\bSTAINLESS(\s+STEEL)?\b", "SS", v)
    v = re.sub(r"\bSS\s*(?=\d)", "SS ", v)
    return re.sub(r"\s+", " ", v).strip()


def norm(field: str, v) -> str:
    if v is None:
        return ""
    v = str(v).strip()
    if field == "material":
        return norm_material(v)
    if field == "quantity":
        return str(int(v)) if v.isdigit() else ""
    return v.upper()


def load_manifest():
    return {r["doc_id"]: r for r in csv.DictReader(open(EVAL / "corpus" / "manifest.csv"))}


def align(gold_rows, pred_rows):
    """Return [(gold or None, pred or None)]."""
    pairs, used = [], set()
    for g in gold_rows:
        match = None
        gpn = norm("part_number", g["part_number"])
        for i, p in enumerate(pred_rows):
            if i in used:
                continue
            if gpn and norm("part_number", p["part_number"]) == gpn:
                match = i
                break
            if not gpn and g.get("match_hint") and g["match_hint"].lower() in (p.get("description") or "").lower():
                match = i
                break
        if match is not None:
            used.add(match)
            pairs.append((g, pred_rows[match]))
        else:
            pairs.append((g, None))
    pairs += [(None, p) for i, p in enumerate(pred_rows) if i not in used]
    return pairs


def run_bom(manifest) -> dict:
    from bom_agent.bom_extraction import extract_bom_rows

    gold = defaultdict(list)
    for r in csv.DictReader(open(EVAL / "corpus" / "labels" / "bom_ground_truth.csv")):
        gold[r["doc_id"]].append(r)

    counts = {f: [0, 0, 0] for f in FIELDS}
    by_origin = defaultdict(lambda: {f: [0, 0, 0] for f in FIELDS})
    by_type = defaultdict(lambda: {f: [0, 0, 0] for f in FIELDS})
    line_records, per_doc = [], []
    for doc_id, m in manifest.items():
        if m["bom_role"] not in ("bom", "negative"):
            continue
        data = (REPO / m["path"]).read_bytes()
        t0 = time.perf_counter()
        pred = extract_bom_rows(data, m["file_type"])
        ms = (time.perf_counter() - t0) * 1000
        origin = "synthetic" if m["origin"].startswith("SYNTHETIC") else "repo sample"
        per_doc.append({"doc_id": doc_id, "file": m["path"], "origin": origin, "labelled_lines": len(gold[doc_id]),
                        "extracted_rows": len(pred), "extract_ms": round(ms, 2), "role": m["bom_role"]})
        for g, p in align(gold[doc_id], pred):
            rec = {"doc_id": doc_id, "origin": origin, "file_type": m["file_type"],
                   "gold_line": g["line"] if g else None,
                   "confidence": p["confidence"] if p else None, "flags": p["flags"] if p else None}
            all_ok = g is not None and p is not None
            for f in FIELDS:
                gv, pv = norm(f, g[f] if g else ""), norm(f, p[f] if p else "")
                if f == "quantity" and p and not g:
                    pv = str(p["quantity"])
                tp, fp, fn = score_field(gv, pv)
                for bucket in (counts[f], by_origin[origin][f], by_type[m["file_type"]][f]):
                    bucket[0] += tp
                    bucket[1] += fp
                    bucket[2] += fn
                rec[f] = {"gold": gv, "pred": pv, "ok": gv == pv}
                all_ok = all_ok and gv == pv
            rec["all_fields_ok"] = all_ok
            line_records.append(rec)

    def table(c):
        return {f: prf(*c[f]) for f in FIELDS}

    matched = [r for r in line_records if r["gold_line"] and r["confidence"] is not None]
    conf = [r["confidence"] for r in matched]
    mat_ok = [r["material"]["ok"] for r in matched]
    all_ok = [r["all_fields_ok"] for r in matched]
    return {
        "n_files": len(per_doc),
        "n_labelled_lines": sum(len(v) for v in gold.values()),
        "n_extracted_rows": sum(d["extracted_rows"] for d in per_doc),
        "n_unmatched_predictions": sum(1 for r in line_records if r["gold_line"] is None),
        "n_missed_lines": sum(1 for r in line_records if r["gold_line"] and r["confidence"] is None),
        "fields": table(counts),
        "by_origin": {k: table(v) for k, v in by_origin.items()},
        "by_file_type": {k: table(v) for k, v in by_type.items()},
        "calibration_material": calibration(conf, mat_ok),
        "calibration_all_fields": calibration(conf, all_ok),
        "abstention_material": abstention_thresholds(conf, mat_ok),
        "per_doc": per_doc,
        "lines": line_records,
    }


def run_matlab(manifest) -> dict:
    from files_api.extractor import extract_metadata

    gold = list(csv.DictReader(open(EVAL / "corpus" / "labels" / "matlab_ground_truth.csv")))
    checks = []
    for doc_id in sorted({g["doc_id"] for g in gold}):
        m = manifest[doc_id]
        res = extract_metadata(Path(m["path"]).name, (REPO / m["path"]).read_bytes())
        if m["file_type"] == "m":
            found = {f["name"]: f for f in res.get("functions", [])}
            for g in (x for x in gold if x["doc_id"] == doc_id):
                f = found.get(g["name"])
                checks += [
                    {"doc_id": doc_id, "item": g["name"], "field": "name", "ok": f is not None},
                    {"doc_id": doc_id, "item": g["name"], "field": "inputs",
                     "ok": bool(f) and ";".join(f["inputs"]) == g["inputs"]},
                    {"doc_id": doc_id, "item": g["name"], "field": "outputs",
                     "ok": bool(f) and ";".join(f["outputs"]) == g["outputs"]},
                ]
            extra = set(found) - {g["name"] for g in gold if g["doc_id"] == doc_id}
            checks += [{"doc_id": doc_id, "item": e, "field": "name", "ok": False, "spurious": True} for e in extra]
        else:
            found = {v["name"]: v for v in res.get("variables", [])}
            for g in (x for x in gold if x["doc_id"] == doc_id):
                v = found.get(g["name"])
                checks += [
                    {"doc_id": doc_id, "item": g["name"], "field": "name", "ok": v is not None},
                    {"doc_id": doc_id, "item": g["name"], "field": "class", "ok": bool(v) and v["class"] == g["class"]},
                    {"doc_id": doc_id, "item": g["name"], "field": "shape",
                     "ok": bool(v) and "x".join(map(str, v["shape"])) == g["shape"]},
                ]
            extra = set(found) - {g["name"] for g in gold if g["doc_id"] == doc_id}
            checks += [{"doc_id": doc_id, "item": e, "field": "name", "ok": False, "spurious": True} for e in extra]
    return {"n_items": len(gold), "n_field_checks": len(checks),
            "n_correct": sum(c["ok"] for c in checks), "checks": checks}


def fmt(x):
    return "n/a" if x is None else f"{x:.2f}"


def main(argv=None) -> dict:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--out", default=str(RESULTS / "extraction.json"))
    args = ap.parse_args(argv)

    from orbit_eval.env import setup
    setup()  # extractor itself needs no DB, but importing Django models does
    manifest = load_manifest()
    report = {"deliverable": "#25", "commit": git_commit(), "synthetic_corpus": True,
              "bom": run_bom(manifest), "matlab": run_matlab(manifest)}
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(report, indent=2))

    b = report["bom"]
    print(f"BOM extraction: {b['n_files']} files, {b['n_labelled_lines']} labelled lines, "
          f"{b['n_extracted_rows']} extracted rows (SYNTHETIC/sample corpus, small n)")
    print(f"{'field':<12} {'TP':>3} {'FP':>3} {'FN':>3}  {'P':>5} {'R':>5} {'F1':>5}")
    for f, s in b["fields"].items():
        print(f"{f:<12} {s['tp']:>3} {s['fp']:>3} {s['fn']:>3}  {fmt(s['precision']):>5} {fmt(s['recall']):>5} {fmt(s['f1']):>5}")
    print(f"ECE (row confidence vs material correct, n={b['calibration_material']['n']}): {b['calibration_material']['ece']}")
    mm = report["matlab"]
    print(f"MATLAB metadata: {mm['n_correct']}/{mm['n_field_checks']} field checks correct over {mm['n_items']} items")
    print(f"wrote {args.out}")
    return report


if __name__ == "__main__":
    main()
