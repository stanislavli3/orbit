# AGENTS.md — Orbit (AI Coding Agent Rules)

Orbit = agentic system that extracts metadata from engineering files (PDF drawings, CAD like STEP/IGES/STL, DXF, images) and produces:
1) a human-readable report
2) a canonical JSON profile with provenance + confidence
Goal: fast iteration WITHOUT corrupting data or inventing facts.

---

## 1) Golden Rules (non-negotiable)

### Always
- Prefer **deterministic extraction** first (parsers, CAD kernels, PDF text, OCR). LLM is for **merge/normalize/resolve**.
- For ANY extracted fact that becomes “data”, include:
  - `value`, `unit` (if applicable), `confidence` (0–1), `source_ref`, `evidence`, `method`
- If not supported by evidence: output **"Unknown"** (never guess).
- Keep changes **small and local** (small diffs, small files, minimal rewrites).
- Add/adjust tests when behavior changes.
- Run the relevant automated tests locally before pushing or opening a PR (for `apps/web/`, at minimum `cd apps/web && npm run build`).

### Never
- Never fabricate dimensions, materials, tolerances, revisions, part numbers, or units.
- Never “interpret” beyond evidence (e.g., assuming material from a part name).
- Never hard-code secrets, endpoints, or file paths that won’t exist in CI.
- Never modify lockfiles or add dependencies without asking first.

### Ask first
- Any new dependency, lockfile change, or major refactor
- Any deletion/rename of folders, pipelines, schemas
- Anything touching security/privacy, network calls, credential handling
- Changing canonical JSON schema fields (this breaks downstream)

---

## 2) Orbit Output Contract (canonical JSON)

All structured extraction output MUST follow this shape (add fields as needed, do not remove):

```json
{
  "file_id": "sha256:...",
  "file_type": "pdf|step|iges|stl|dxf|image|zip|unknown",
  "part": {
    "part_number": {
      "value": "123-ABC",
      "confidence": 0.86,
      "source_ref": "drawing.pdf#page=1#bbox=... OR step:AP214:entity=...",
      "evidence": "PN: 123-ABC",
      "method": "pdf_text|ocr|step_parser|merge_agent"
    }
  },
  "geometry": {
    "units": { "value": "mm", "confidence": 0.9, "source_ref": "...", "evidence": "...", "method": "..." },
    "bbox":  { "value": [0,0,0,10,20,30], "unit": "mm", "confidence": 0.8, "source_ref": "...", "evidence": "...", "method": "..." },
    "volume":{ "value": 123.4, "unit": "cm^3", "confidence": 0.7, "source_ref": "...", "evidence": "...", "method": "..." }
  },
  "warnings": [
    { "type": "conflict|missing|low_confidence|unit_mismatch", "message": "...", "refs": ["..."] }
  ]
}
```

## 10) Coding Style (Orbit)

### General
- Prefer **clarity over cleverness**.
- Keep functions **small** (target: <40 lines; split if bigger).
- Single responsibility per module. Avoid “god files”.
- Name things explicitly: `extract_title_block()`, `normalize_units()`, `validate_bbox()`.

### Python style (if Python)
- Python **3.10+** only.
- Type hints on **all** functions and public methods.
- Use `dataclasses` (or pydantic if already in repo) for structured data.
- Prefer returning **typed objects** over nested dicts in core logic; convert to JSON at boundaries.
- No bare `except:`. Catch specific exceptions.
- Avoid printing in library code; use the project logger.
- Never silently ignore errors in extraction. Return `Unknown` + warning instead.

### Error handling
- Fail fast on programmer errors (assertions/ValueError).
- For data issues: record `warnings[]` and continue when safe.
- All exceptions surfaced to the pipeline must include:
  - what file
  - which step
  - minimal context (no sensitive content)

### File organization
- Put IO at the edges: parsing, file reads, network calls in `io/` or worker modules.
- Keep pure logic in `core/` (easy to test).

### Dependencies
- Standard library first.
- Do not add new dependencies without approval.
- If adding a dependency is approved: justify it in the PR description and add minimal usage.

---

## 11) Comments & Documentation Rules

### Comments (when to write them)
Write comments for:
- Non-obvious decisions (“why”), not obvious mechanics (“what”).
- Edge cases and gotchas (OCR noise, unit ambiguity, STEP quirks).
- Safety rules and invariants (why we do `Unknown` instead of guessing).

Avoid:
- Restating code in English.
- Huge comment blocks instead of refactoring.

### Docstrings
- All public functions/classes must have docstrings including:
  - purpose
  - inputs/outputs
  - assumptions
  - warnings/confidence behavior (if extraction-related)

### TODOs
- Every TODO must include an owner + reason + follow-up pointer:
  - `# TODO(stanislav): handle rotated title blocks (issue #123)`

### Logging
- Use structured logs.
- Never log secrets or full proprietary file contents.
- Log extraction steps with: file_id, step_name, duration_ms, warnings_count.

---

## 12) Commit Message Rules (Conventional Commits)

Format:
- `type(scope): summary`

Types:
- `feat` = new feature
- `fix` = bug fix
- `refactor` = no behavior change, code restructure
- `perf` = performance improvement
- `test` = tests only
- `docs` = docs only
- `chore` = tooling/CI/build
- `ci` = CI changes

Scopes (Orbit examples):
- `pipeline`, `pdf`, `cad`, `dxf`, `schema`, `agents`, `validate`, `eval`, `cli`, `api`

Rules:
- Summary is **imperative** and < 72 chars.
- If the change is user-visible or risky, include a body:
  - what changed
  - why
  - how to test
- Reference issues when applicable: `refs #123` or `closes #123`.

Examples:
- `feat(pdf): extract title block fields with provenance`
- `fix(cad): correct unit normalization for STEP inches`
- `refactor(schema): introduce typed records for evidence fields`
- `test(validate): add regression for negative bbox`
- `docs(ai): document Unknown/confidence rules`

---

## 13) PR / Diff Rules (to keep velocity high)

- Prefer **small diffs** (<300 lines when possible).
- No drive-by formatting or mass renames unless requested.
- If prompts or schema changed:
  - attach eval results
  - mention what improved/regressed
- PR description must include:
  - what/why
  - how tested (exact commands)
  - any risks + rollback plan


## Repo Directory Guide (Orbit MVP)

This repo is intentionally minimal. Follow these rules so we don’t create a messy file jungle.

### Main directories and what they’re for
- `apps/`
  - Executable apps only.
  - `apps/api/` = Python backend (FastAPI). Routes + services. No extraction logic here.
  - `apps/worker/` = Python extraction runner (parsers + AI merge + validation). All extraction happens here.
  - `apps/web/` = TypeScript frontend (Vite React). UI only. Run `npm run build` before pushing changes here so CI/frontend stay green.

- `packages/`
  - Shared, reusable code only.
  - `packages/contracts/` = canonical schemas + API contracts. This is the single source of truth for data shapes.

- `prompts/`
  - Versioned prompts treated like code (reviewed, small diffs).
  - Do not embed long prompts inside random `.py` files; reference prompts by path.

- `docs/`
  - Human documentation (MVP scope, architecture, decisions, API usage).
  - If a rule affects how people/code behave, put it here or in `AGENTS.md`.

- `eval/`
  - Small golden examples + quick checks to prevent regressions (especially hallucinations).
  - Add cases only when you find a recurring failure.

- `storage/` (dev only)
  - Local uploads/artifacts. Must be gitignored. Never commit real files here.

---

## Agent Rules for Working in This Repo (No Mess)

### Always (structure discipline)
- Put new code in the correct top-level directory (`apps/`, `packages/`, `prompts/`, `docs/`, `eval/`).
- Prefer adding code to an existing module/file rather than creating a new file.
- Keep diffs small and local. Avoid repo-wide rewrites.

### File creation policy (strict)
- Do NOT create new folders unless explicitly requested.
- Do NOT create “misc”, “tmp”, “new”, “test2”, “draft”, “backup”, “old”, or date-stamped folders.
- Do NOT generate multiple alternative files (“v1”, “v2”, “final2”) — pick one approach.
- If you need a new file, create **at most 1–2 files per task** unless the task explicitly requires more.

### Before creating any new file, do this checklist
1) Can I implement this inside an existing file/module? If yes, do that.
2) If not, is there already a directory that matches this purpose? Use it.
3) Name the file by responsibility, not by experiment name:
   - ✅ `profile_service.py`, `extract_title_block.py`, `canonical_profile.schema.json`
   - ❌ `try_fix.py`, `temp_extractor.py`, `new_merge_logic2.py`

### When adding prompts
- Add prompts only in `prompts/`.
- Prompts must be short, specific, and diffable.
- Do not duplicate prompt text across files — reference the prompt file.

### When adding shared types/contracts
- Shared schemas/types go in `packages/contracts/`.
- Apps should import/use contracts rather than redefining types in multiple places.

### When you’re unsure where something goes
- STOP and propose a short plan (max 5 bullets) listing:
  - which directories you’ll touch
  - which files you’ll modify
  - which new files (if any) you’ll create
Then proceed with the minimal file count.

### Cleanup rule
- If you created a new helper file but ended up not using it: delete it before finishing.
- No orphaned files.
