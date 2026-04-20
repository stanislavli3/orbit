# Task — Assistant RAG feature
- [x] Review backend/frontend state to align implementation approach
- [x] Backend: add `assistant` app (models, rag logic, view, urls), register in settings/urls
- [x] Backend: add `FileEmbedding` model + embedding helpers and hook into extraction flow
- [x] Frontend: wire Assistant page to real API with session, markdown, sources, loading/error handling; add dependency
- [x] Verification: migrations, API smoke, frontend build or lint; note follow-ups

## Review — Assistant RAG feature
- Added `assistant` app with chat session/message models, RAG utilities, and `/api/assistant/chat/` endpoint using Claude Sonnet with embedding fallback to hashed TF-IDF when API key is absent.
- Added `FileEmbedding` model plus embedding generation in extraction flow; similarity via numpy cosine over stored vectors.
- Frontend Assistant page now calls the API, streams markdown responses with source chips, keeps session IDs, handles loading/error (no API key), and sends suggested prompts immediately; new dependency `react-markdown`.
- Ran `python manage.py migrate` (SQLite) to create new tables and `npm run build` for the web app.
- Linters now clean: `ruff check .` and `npm run lint`.
- Formatting clean: `ruff format --check .`.
- Follow-ups: provide a real `ANTHROPIC_API_KEY` for live responses; re-process existing files to populate embeddings; optional: remove `version` field warning in docker-compose, run npm audit if desired.

---

# Task — README env files
- [x] Confirm README environment requirements vs current env files
- [x] Update `backend/.env` to match README (secret, hosts, Clerk issuer/JWT key, CORS origins, S3 defaults, optional Anthropic placeholder)
- [x] Create/fill `apps/web/.env` with Clerk publishable key and API URL
- [x] Verify values and note any missing real secrets needed from user

## Review — README env files
- Backend `.env` now mirrors README: new `SECRET_KEY`, CORS origins, LocalStack S3 (`orbit-local`), Clerk issuer/JWT placeholders, optional Anthropic key left blank.
- Frontend `.env` added with placeholder `VITE_CLERK_PUBLISHABLE_KEY` and `VITE_API_URL=http://localhost:8000`.
- Follow-up: replace Clerk placeholders with real publishable key and JWT public key; set `CLERK_ISSUER` to your actual Clerk issuer URL; add `ANTHROPIC_API_KEY` if AI descriptions are needed.

---

# Issue #18 — Replace hardcoded mock data with real API calls

---

## Windows make dev fix

- [x] Identify remaining Unix-only commands in `Makefile` that block `make dev` on Windows
- [x] Add Windows-specific implementations for `dev`, `_docker-up`, and `stop`
- [x] Verify `make dev` starts backend/frontend after Docker and LocalStack are available
- [x] Document the Windows run path and any remaining limitations

### Review

- `make dev` now starts LocalStack, creates the S3 bucket, runs migrations, and launches backend/frontend in background processes on Windows.
- Verified frontend log shows Vite serving on port 5173.
- Verified port 8000 is listening for the Django backend.
- Remaining non-blocking warning: `docker-compose.yml` still uses the obsolete `version` key.

**Branch:** `feat/issue-18-real-api-data`
**GitHub:** https://github.com/stanislavli3/orbit/issues/18

---

## Checklist

### Backend
- [ ] `backend/projects/views.py` — fix `AllowAny` → `IsAuthenticated` on `ProjectListCreateView`; add `ProjectRetrieveView` (owner-scoped `RetrieveAPIView`)
- [ ] `backend/projects/serializers.py` — add `file_count = SerializerMethodField()` (returns `obj.files.count()`)
- [ ] `backend/projects/urls.py` — add `path("<int:pk>/", ProjectRetrieveView.as_view(), name="project-detail")`

### Frontend
- [ ] `cd apps/web && npm install @tanstack/react-query`
- [ ] `apps/web/src/app/App.tsx` — wrap with `<QueryClientProvider client={queryClient}>`; instantiate `queryClient` at module level
- [ ] `apps/web/src/api/types.ts` — **create** with `Project` and `UploadedFile` TypeScript interfaces
- [ ] `apps/web/src/app/components/VaultPage.tsx` — remove hardcoded `projects` array; add `useQuery` → `GET /api/projects/`; add loading skeleton (6 cards), error state, empty state
- [ ] `apps/web/src/app/components/ProjectDetailPage.tsx` — remove `projectData` Record; add 2 queries (`GET /api/projects/<id>/` + `GET /api/files/project/<id>/`); skeletons for header + file rows; Library tab → empty state with TODO comment
- [ ] `apps/web/src/app/components/HistoryPage.tsx` — add TODO comment at top only (no functional change — no backend endpoint exists)

---

## Key shapes

```ts
// Project (from GET /api/projects/ and GET /api/projects/<id>/)
{ id: number; name: string; description: string; owner: number; created_at: string; file_count: number }

// UploadedFile (from GET /api/files/project/<id>/)
{ id: number; project: number; uploaded_by: number; original_name: string;
  file_type: string; file_size: number;
  status: 'uploaded' | 'processing' | 'processed' | 'failed'; created_at: string }
```

## Status mapping (ProjectDetailPage file rows)
- `processed` → "Extracted" badge
- `uploaded` / `processing` → "Processing" badge
- `failed` → "Failed" badge (red)

---

## Verification
1. `cd backend && SECRET_KEY=x CLERK_ISSUER=x python manage.py check` → 0 issues
2. `cd apps/web && npm run build` → 0 TS errors
3. Manual: sign in → `/vault` shows real projects → click project → files load → Library tab shows empty state
4. `curl GET /api/projects/` (no auth) → 401 (AllowAny bug fixed)

---

# Issue #63 — Excel BOM workbook generation with openpyxl (Phase 3)

- [x] Inspect BOM run data shape, dependency availability, and test harness requirements for workbook generation
- [x] Implement workbook builder with 5 required sheets, formula cells, formatting, and conditional formatting
- [x] Integrate workbook generation/upload into BOM research completion and persist `BomResearchRun.excel_s3_key`
- [x] Verify `GET /api/bom/runs/<id>/excel/` returns a presigned URL for generated workbooks
- [x] Create `scripts/recalc.py` to validate workbook formulas and fail on formula/load errors
- [x] Add automated tests for workbook structure, formula placement, formatting markers, upload integration, and download endpoint
- [x] Run targeted verification and document results, gaps, and follow-ups

## Review — Issue #63
- Added `backend/bom_agent/excel_export.py` to build a 5-sheet BOM workbook with preserved Excel formulas, freeze panes, consistent styling, supplier conditional formatting, input coloring, research/source log rows, and risk matrix output.
- Wired `run_bom_research()` to generate/upload the workbook on completion, persist `BomResearchRun.excel_s3_key`, and enrich `research_log` entries with structured metadata useful for the workbook.
- Added `upload_bytes_to_s3()` in `backend/files_api/s3_service.py` for direct `.xlsx` uploads and kept the existing `/api/bom/runs/<id>/excel/` presigned download flow intact.
- Added `scripts/recalc.py` to validate workbook loadability, required sheet presence, and formula tokenization with zero formula errors.
- Verification:
- `./backend/.venv/bin/python -m ruff check backend/bom_agent/excel_export.py backend/bom_agent/research_pipeline.py backend/files_api/s3_service.py backend/bom_agent/tests.py scripts/recalc.py`
- `cd backend && ./.venv/bin/python -m pytest bom_agent/tests.py -q`
- `cd backend && ./.venv/bin/python manage.py check`
- `cd backend && ./.venv/bin/python ../scripts/recalc.py /tmp/bom-sample.xlsx`
- Follow-up: the requested example formula `=D2*F2` conflicts with the specified column order (`Qty` is column `E`), so the workbook uses `=E2*F2` for extended cost.
