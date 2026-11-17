# eval/golden

Question files for the retrieval (#27) and head-to-head (#28) harnesses.

Format (CSV, UTF-8): `id, question, relevant_doc_ids` are required. `relevant_doc_ids` is a
`;`-separated list of doc ids from `eval/corpus/manifest.csv`. Optional columns used when present:
`category, reference_answer, key_facts` (`;`-separated substrings for the automatic context proxy).

| File | Status |
|---|---|
| `synthetic_questions_v0.csv` | **SYNTHETIC.** 20 questions written by the AI lead's agent from the sample corpus, *not* harvested from interviews. Use it to check the harness works. Do not report it as T1/T2/T6 evidence. |
| `golden_v1.csv` (to come) | The frozen 50-question golden set (#26), harvested from interviews by the AI lead + Area I. Freeze it (commit hash + date) before any run whose numbers are reported. |
