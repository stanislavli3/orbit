"""#27 (T1) — retrieval evaluation: Recall@1/5/10, Hit@k, MRR, nDCG@10 over a question file.

Retrievers scored (all at document level, doc ids from eval/corpus/manifest.csv):

  orbit_unified   ``assistant.search.unified_search`` — the retriever behind Ask Orbit
                  (files + BOM rows + parts + quotes + suppliers). Hits are merged by
                  score, as ``assistant.ask.build_context`` does, then mapped to the doc
                  they came from; supplier hits have no source doc and are dropped.
  orbit_chat_rag  ``assistant.rag.find_relevant_files`` — the project chat assistant's
                  retriever (uploaded files only; imported CSVs are unreachable by design).
  bm25_reference  Okapi BM25 over each file's raw text. A textbook lexical baseline for
                  context only, NOT part of Orbit.

The corpus is ingested through Orbit's real upload/import code (orbit_eval.ingest).
Without ANTHROPIC_API_KEY files get no AI description, so file embeddings are built
from file name + parsed metadata only — that is what a keyless deployment indexes.

Run:  backend/.venv/bin/python eval/retrieval_eval.py --questions eval/golden/synthetic_questions_v0.csv
"""

import argparse
import csv
import io
import json
import math
import re
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from orbit_eval.env import REPO, RESULTS, git_commit, has_api_key, setup  # noqa: E402
from orbit_eval.metrics import ranking_summary  # noqa: E402

K = 10


def load_questions(path) -> list[dict]:
    rows = list(csv.DictReader(open(path, newline="", encoding="utf-8")))
    for r in rows:
        missing = {"id", "question", "relevant_doc_ids"} - set(r)
        if missing:
            raise SystemExit(f"{path}: missing columns {missing}")
        r["relevant"] = {d.strip() for d in r["relevant_doc_ids"].split(";") if d.strip()}
    return rows


def dedupe(seq):
    seen, out = set(), []
    for x in seq:
        if x and x not in seen:
            seen.add(x)
            out.append(x)
    return out


# ── retrievers ───────────────────────────────────────────────────────────────

def orbit_unified(user, lookup, question: str) -> list[str]:
    from assistant.search import unified_search

    hits = [h for g in unified_search(user, question, limit=K)["groups"].values() for h in g]
    hits.sort(key=lambda h: h["score"], reverse=True)
    return dedupe(lookup(h) for h in hits)[:K]


def orbit_chat_rag(user, docs, question: str) -> list[str]:
    from assistant.rag import find_relevant_files

    by_file = {v["file_id"]: k for k, v in docs.items() if v["file_id"]}
    return dedupe(by_file.get(f.pk) for f in find_relevant_files(question, user, None, top_k=K))[:K]


def raw_text(doc: dict) -> str:
    data = (REPO / doc["path"]).read_bytes()
    if doc["file_type"] == "pdf":
        from pypdf import PdfReader

        return "\n".join(p.extract_text() or "" for p in PdfReader(io.BytesIO(data)).pages)
    if doc["file_type"] == "mat":
        from files_api.extractor import extract_metadata

        return f"{doc['name']} " + json.dumps(extract_metadata(doc["name"], data).get("variables", []))
    return f"{doc['name']}\n" + data.decode("utf-8", errors="ignore")


class BM25:
    def __init__(self, texts: dict[str, str], k1=1.5, b=0.75):
        self.toks = {d: re.findall(r"\w+", t.lower()) for d, t in texts.items()}
        self.avg = sum(len(t) for t in self.toks.values()) / len(self.toks)
        self.df = Counter(w for t in self.toks.values() for w in set(t))
        self.n, self.k1, self.b = len(self.toks), k1, b

    def rank(self, query: str) -> list[str]:
        q = re.findall(r"\w+", query.lower())
        scores = {}
        for d, toks in self.toks.items():
            tf, s = Counter(toks), 0.0
            for w in q:
                if w in tf:
                    idf = math.log(1 + (self.n - self.df[w] + 0.5) / (self.df[w] + 0.5))
                    s += idf * tf[w] * (self.k1 + 1) / (tf[w] + self.k1 * (1 - self.b + self.b * len(toks) / self.avg))
            scores[d] = s
        return [d for d, s in sorted(scores.items(), key=lambda x: -x[1]) if s > 0][:K]


def main(argv=None) -> dict:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--questions", default=str(REPO / "eval" / "golden" / "synthetic_questions_v0.csv"))
    ap.add_argument("--repeats", type=int, default=5, help="fresh ingests to average over")
    ap.add_argument("--out", default=str(RESULTS / "retrieval.json"))
    args = ap.parse_args(argv)

    setup()
    from orbit_eval.ingest import doc_lookup, ingest_corpus, make_user

    questions = load_questions(args.questions)
    repeats = []
    for rep in range(args.repeats):
        # Fresh ingest each repeat: Orbit embeds the parse timestamp with each file, so
        # file vectors (and occasionally rankings) differ run to run. Repeats measure that.
        user = make_user()
        docs = ingest_corpus(user)
        lookup = doc_lookup(docs)
        if rep == 0:
            bm25 = BM25({d: raw_text(v) for d, v in docs.items()})
        per_q, runs = [], {"orbit_unified": [], "orbit_chat_rag": [], "bm25_reference": []}
        for q in questions:
            ranked = {
                "orbit_unified": orbit_unified(user, lookup, q["question"]),
                "orbit_chat_rag": orbit_chat_rag(user, docs, q["question"]),
                "bm25_reference": bm25.rank(q["question"]),
            }
            for name, r in ranked.items():
                runs[name].append((r, q["relevant"]))
            per_q.append({"id": q["id"], "category": q.get("category", ""), "relevant": sorted(q["relevant"]), **ranked})
        repeats.append({"summary": {name: ranking_summary(r) for name, r in runs.items()}, "runs": runs, "per_q": per_q})

    runs, per_q = repeats[0]["runs"], repeats[0]["per_q"]
    variance = {}
    for name in runs:
        variance[name] = {}
        for metric in ("recall@1", "recall@5", "recall@10", "hit@5", "mrr", "ndcg@10"):
            vals = [r["summary"][name][metric] for r in repeats]
            variance[name][metric] = {"mean": round(sum(vals) / len(vals), 4), "min": min(vals), "max": max(vals)}

    by_cat = {}
    for cat in sorted({q.get("category", "") for q in questions}):
        idx = [i for i, q in enumerate(questions) if q.get("category", "") == cat]
        by_cat[cat] = {name: ranking_summary([runs[name][i] for i in idx]) for name in runs}

    report = {
        "deliverable": "#27 retrieval (T1)", "commit": git_commit(), "questions_file": str(Path(args.questions).name),
        "synthetic_questions": "synthetic" in Path(args.questions).name,
        "api_key_present": has_api_key(), "n_docs": len(docs),
        "note": "summary/by_category/per_question are from repeat 1; across_repeats gives mean/min/max over fresh ingests",
        "repeats": args.repeats, "summary": {name: ranking_summary(r) for name, r in runs.items()},
        "across_repeats": variance,
        "by_category": by_cat, "per_question": per_q,
    }
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(report, indent=2))

    print(f"Retrieval: {len(questions)} questions ({report['questions_file']}), {len(docs)} docs, "
          f"API key {'present' if report['api_key_present'] else 'absent'}")
    cols = ["recall@1", "recall@5", "recall@10", "hit@5", "mrr", "ndcg@10"]
    print(f"{'retriever':<16}" + "".join(f"{c:>10}" for c in cols))
    for name, v in report["across_repeats"].items():
        print(f"{name:<16}" + "".join(f"{v[c]['mean']:>10.3f}" for c in cols))
    print(f"(mean of {args.repeats} fresh ingests; recall@5 range orbit_unified "
          f"{variance['orbit_unified']['recall@5']['min']}-{variance['orbit_unified']['recall@5']['max']})")
    print(f"wrote {args.out}")
    return report


if __name__ == "__main__":
    main()
