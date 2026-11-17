# Orbit evaluation harness

Measures what ships on `main`. Covers BIS 372 deliverables #23 (cost instrumentation), #25 (extraction),
#27 (retrieval + answer quality), #28 (head-to-head), #30 (BOM agent) and #31 (COGS). Nothing in `eval/`
is imported by the product. Every harness boots Django against a throw-away SQLite file, so dev data is
never touched.

```bash
make eval                                    # everything, ~30 s without an API key
backend/.venv/bin/python eval/run_all.py --questions eval/golden/golden_v1.csv   # the frozen set, once it exists
backend/.venv/bin/python -m pytest -q eval/tests -p no:django                    # metric unit tests
```

| # | Command | Writes to `eval/results/` | Needs `ANTHROPIC_API_KEY`? |
|---|---|---|---|
| 23 | built in: `core.usage.tracked_create` logs every Claude call to `core.LlmUsage` and to the `orbit.usage` logger (`llm_usage {json}`) | n/a | to produce rows |
| 25 | `python eval/extraction_eval.py` | `extraction.json` | no (the extractor is rule-based) |
| 27 | `python eval/retrieval_eval.py --questions <csv> [--repeats 5]` | `retrieval.json` | no |
| 27 | `python eval/answer_quality.py --questions <csv> [--judge-model ...]` | `answer_quality.json`, `answer_labels_labeller{1,2}.csv` | for AI answers and the LLM judge |
| 27 | `python eval/kappa.py labeller1.csv labeller2.csv` (or `--judge answer_quality.json`) | stdout | no |
| 28 | `python eval/head_to_head.py build [--assistant-answers answers.csv]` then `... score --key h2h_key_SEALED.csv s1.csv s2.csv` | `h2h_blind_sheet*.csv`, `h2h_key_SEALED.csv`, `h2h_orbit_answers.json` | for AI answers |
| 30 | `python eval/agent_eval.py [--with-research]` | `agent.json`, `agent_failure_taxonomy.csv` | only `--with-research` |
| 31 | `python eval/cogs.py [--db <DATABASE_URL with LlmUsage rows>]` | `cogs.json` | no (uses measured rows when `--db` has them) |

Prefix every command with `backend/.venv/bin/` (or your venv's python).

## Corpus

`eval/corpus/manifest.csv` lists 13 documents: the 7 files in `samples/` and 6 **synthetic** files built
by `eval/corpus/build_corpus.py` (generated text PDFs and one STEP file restating facts from `samples/`).
Labels in `eval/corpus/labels/` were written by hand from the files themselves; each row says where the
value comes from. Process is never stored in these files, so process labels are judgment calls and are
marked as such. The corpus is small and synthetic: use it to prove the harness, not to make claims about
customer files.

## Question files

See `eval/golden/README.md`. `synthetic_questions_v0.csv` is a harness check, not the golden set.

## Head-to-head protocol (#28)

1. Freeze the golden set. Build the corpus the same way for both systems.
2. Orbit arm: run with `ANTHROPIC_API_KEY` set so Ask Orbit answers in AI mode (retrieval-only answers
   are recognisable and are not the product).
3. Assistant arm: either set the key (API arm: the same files as attachments, no Orbit retrieval) or
   upload `eval/corpus/files/*` + `samples/*` to the chosen assistant (ChatGPT, Claude.ai...), ask each
   question in a fresh chat, and save `id,answer` to a CSV for `--assistant-answers`.
4. `build` writes the blind sheet (shuffled, A/B randomised, system names stripped) and a sealed key.
   The AI lead never scores. Each of the two other teammates scores a copy alone.
5. `score` unblinds, reports correct-and-grounded rates per system, the pp difference (T6 target: 20 pp)
   and Cohen's kappa; resolve disagreements together and re-run `score` with the consensus sheet first.
