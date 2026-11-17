"""#27 (T2) — answer quality: faithfulness, relevance, citation correctness.

Generates Orbit's answer to every question through the shipped Ask Orbit path, then:

1. Always (no API key needed)
   * context_has_key_facts — automatic proxy: do the sources Orbit hands the model
     contain every ``key_facts`` substring for the question? A weak lexical proxy
     for "the answer was retrievable", not a quality score.
   * citation_validity — every [n] in the answer points at a source that exists.
   * Writes a human labelling sheet (one per labeller) for faithfulness /
     relevance / citation correctness. Two labellers fill it independently;
     ``kappa.py`` reports Cohen's kappa.
2. Only with ANTHROPIC_API_KEY
   * An LLM judge labels the same dimensions. Its labels are NOT reported as results
     until ``kappa.py --judge`` shows its agreement with the human labels.

Without a key Orbit answers in retrieval-only mode (a list of cited snippets), so the
judged dimensions are not meaningful for the product and the judge is skipped.

Run:  backend/.venv/bin/python eval/answer_quality.py [--questions ...] [--judge-model claude-sonnet-4-6]
"""

import argparse
import csv
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from orbit_eval.env import REPO, RESULTS, git_commit, has_api_key, rel, setup  # noqa: E402
from retrieval_eval import load_questions  # noqa: E402

LABEL_COLUMNS = [
    ("faithfulness", "grounded | ungrounded | fabricated"),
    ("relevance", "2 answers it | 1 partly | 0 not"),
    ("citation_correct", "yes | partly | no | n/a (no citations)"),
    ("correctness", "correct | partial | incorrect | refused"),
]

JUDGE_PROMPT = """You are grading one answer from an engineering-file assistant. Use ONLY the numbered sources and the
reference answer below. Reply with JSON only:
{{"faithfulness": "grounded|ungrounded|fabricated", "relevance": 0|1|2,
  "citation_correct": "yes|partly|no|n/a", "correctness": "correct|partial|incorrect|refused", "reason": "<one sentence>"}}
Definitions: grounded = every factual claim is supported by a source; ungrounded = some claim has no support but is
not contradicted; fabricated = a part number, quantity, dimension, price or material that appears in no source or
contradicts one. citation_correct = do the cited [n] sources support the sentences that cite them.

Question: {question}
Reference answer (hand-written from the files): {reference}
Sources:
{sources}
Answer to grade:
{answer}"""


def source_text(sources: list[dict]) -> str:
    return "\n".join(f"[{s['n']}] {s['title']}: {s['snippet']} (source: {s['citation']})" for s in sources)


def citation_validity(answer: str, sources: list[dict]) -> dict:
    cited = {int(n) for n in re.findall(r"\[(\d+)\]", answer)}
    valid = {s["n"] for s in sources}
    return {"cited": sorted(cited), "invalid": sorted(cited - valid), "ok": not (cited - valid)}


def judge(question, reference, sources, answer, model) -> dict:
    import os

    import anthropic

    from core.usage import tracked_create

    msg = tracked_create(
        anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"]), path="query", operation="eval_judge",
        model=model, max_tokens=300, messages=[{"role": "user", "content": JUDGE_PROMPT.format(
            question=question, reference=reference, sources=source_text(sources) or "(none)", answer=answer)}],
    )
    text = msg.content[0].text.strip()
    try:
        return json.loads(text[text.find("{"): text.rfind("}") + 1])
    except ValueError:
        return {"error": "unparseable judge output", "raw": text[:300]}


def write_label_sheets(items, out_dir: Path, n_labellers=2) -> list[str]:
    paths = []
    for k in range(1, n_labellers + 1):
        path = out_dir / f"answer_labels_labeller{k}.csv"
        with open(path, "w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh)
            w.writerow(["item_id", "question", "reference_answer", "answer", "sources"]
                       + [f"{c} ({hint})" for c, hint in LABEL_COLUMNS] + ["labeller", "notes"])
            for it in items:
                w.writerow([it["id"], it["question"], it["reference_answer"], it["answer"], source_text(it["sources"])]
                           + [""] * len(LABEL_COLUMNS) + [f"labeller{k}", ""])
        paths.append(rel(path))
    return paths


def main(argv=None) -> dict:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--questions", default=str(REPO / "eval" / "golden" / "synthetic_questions_v0.csv"))
    ap.add_argument("--judge-model", default="claude-sonnet-4-6")
    ap.add_argument("--out", default=str(RESULTS / "answer_quality.json"))
    args = ap.parse_args(argv)

    setup()
    from core.models import LlmUsage
    from orbit_eval.answers import orbit_answer
    from orbit_eval.ingest import ingest_corpus, make_user

    questions = load_questions(args.questions)
    user = make_user()
    ingest_corpus(user)
    usage_before = LlmUsage.objects.count()

    items = []
    for q in questions:
        a = orbit_answer(user, q["question"])
        ctx = source_text(a["sources"]).lower()
        facts = [f.strip() for f in q.get("key_facts", "").split(";") if f.strip()]
        item = {
            "id": q["id"], "question": q["question"], "reference_answer": q.get("reference_answer", ""),
            "answer": a["answer"], "mode": a["mode"], "sources": a["sources"], "latency_ms": a["latency_ms"],
            "context_has_key_facts": all(f.lower() in ctx for f in facts) if facts else None,
            "citations": citation_validity(a["answer"], a["sources"]),
        }
        if has_api_key() and a["mode"] == "ai":
            item["judge"] = judge(q["question"], item["reference_answer"], a["sources"], a["answer"], args.judge_model)
        items.append(item)

    scored = [i for i in items if i["context_has_key_facts"] is not None]
    report = {
        "deliverable": "#27 answer quality (T2)", "commit": git_commit(),
        "questions_file": Path(args.questions).name, "api_key_present": has_api_key(),
        "orbit_modes": sorted({i["mode"] for i in items}),
        "n_questions": len(items),
        "context_has_key_facts_rate": round(sum(i["context_has_key_facts"] for i in scored) / len(scored), 4) if scored else None,
        "n_context_scored": len(scored),
        "citation_validity_rate": round(sum(i["citations"]["ok"] for i in items) / len(items), 4) if items else None,
        "judge_ran": any("judge" in i for i in items),
        "judge_model": args.judge_model if any("judge" in i for i in items) else None,
        "llm_calls_logged": LlmUsage.objects.count() - usage_before,
        "mean_latency_ms": round(sum(i["latency_ms"] for i in items) / len(items), 1) if items else None,
        "items": items,
    }
    report["label_sheets"] = write_label_sheets(items, Path(args.out).parent)
    Path(args.out).write_text(json.dumps(report, indent=2))

    print(f"Answer quality: {len(items)} questions, Orbit mode(s) {report['orbit_modes']}, "
          f"API key {'present' if has_api_key() else 'absent'}")
    print(f"context contains all key facts: {report['context_has_key_facts_rate']} (n={len(scored)}, automatic proxy)")
    print(f"citation validity: {report['citation_validity_rate']}; LLM judge ran: {report['judge_ran']}")
    print("label sheets: " + ", ".join(report["label_sheets"]))
    return report


if __name__ == "__main__":
    main()
