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

---

# Issue #64 — BOM results table & Excel download (Phase 3)

- [x] Inspect current BOM/project detail frontend flow and confirm API gaps for history/download metadata
- [x] Add minimal backend support for `GET /api/bom/runs/?project_id=<id>` and Excel metadata needed by the UI
- [x] Extend frontend BOM types/client usage for run history and Excel download payloads
- [x] Implement project-detail BOM results panel with sortable/filterable table and expandable supplier comparison rows
- [x] Add row-level risk badges, client-side status filter, and run history actions (`View` / `Download`)
- [x] Add Excel download button with presigned URL open behavior, file size, and generation timestamp
- [x] Run targeted verification (`manage.py`/frontend build or lint) and document results/follow-ups

## Review — Issue #64
- Added BOM run history support to the backend: `GET /api/bom/runs/?project_id=<id>` now returns the project’s runs, and `/api/bom/runs/<id>/excel/` now includes `url`, `file_size`, `generated_at`, and `filename`.
- Added [BomResultsPanel.tsx](/Users/amandafogel/Visual%20Studio%20Code/Orbit/apps/web/src/app/components/BomResultsPanel.tsx) for the Phase 3 UI: sortable/filterable BOM results table, expandable supplier quote sub-table, row risk badges, Excel header download action, and run history with `View` / `Download`.
- Wired [ProjectDetailPage.tsx](/Users/amandafogel/Visual%20Studio%20Code/Orbit/apps/web/src/app/components/ProjectDetailPage.tsx) to load BOM history/detail data, keep a selected run, show current results inline, and preserve the live research panel flow.
- Extended API typings in [types.ts](/Users/amandafogel/Visual%20Studio%20Code/Orbit/apps/web/src/api/types.ts) for `is_avl`, Excel metadata, and related BOM payloads; also cleaned up [BomLivePanel.tsx](/Users/amandafogel/Visual%20Studio%20Code/Orbit/apps/web/src/app/components/BomLivePanel.tsx) to satisfy the repo’s React hooks lint rule.
- Verification:
- `cd backend && ./.venv/bin/python -m pytest bom_agent/tests.py -q`
- `cd backend && ./.venv/bin/python manage.py check`
- `cd apps/web && npm run lint`
- `cd apps/web && npm run build`
- Follow-up: the `COTS` filter is derived client-side from sourced parts whose best quote has `tooling_cost === 0`, since there is no dedicated backend status for COTS today.

---

# Issue #65 — TeamRequest model & email draft/approve/send API (Phase 4)

- [x] Inspect BOM/team-contact backend surfaces and confirm API/state-machine gaps for team-request emails
- [x] Add `TeamRequest` model, serializer support, and migration
- [x] Implement draft generation/routing helpers with Claude Haiku rendering and deterministic fallback
- [x] Add draft/list/edit/approve/send/follow-up BOM email endpoints with approval guards and follow-up cap
- [x] Add automated backend tests for draft generation, editing, approval gating, send/send-all, and follow-up behavior
- [x] Run targeted verification and document results/follow-ups

## Review — Issue #65
- Added `TeamRequest` to [models.py](/Users/amandafogel/Visual%20Studio%20Code/Orbit/backend/bom_agent/models.py) plus migration [0006_teamrequest.py](/Users/amandafogel/Visual%20Studio%20Code/Orbit/backend/bom_agent/migrations/0006_teamrequest.py). The model stores denormalized recipient info, editable rendered email content, response timestamps, and follow-up counters.
- Added [team_requests.py](/Users/amandafogel/Visual%20Studio%20Code/Orbit/backend/bom_agent/team_requests.py) for question-to-contact routing, Haiku-backed draft rendering with a deterministic fallback template, per-contact follow-up counting, and the outbound send abstraction.
- Extended [serializers.py](/Users/amandafogel/Visual%20Studio%20Code/Orbit/backend/bom_agent/serializers.py), [bom_views.py](/Users/amandafogel/Visual%20Studio%20Code/Orbit/backend/bom_agent/bom_views.py), and [bom_urls.py](/Users/amandafogel/Visual%20Studio%20Code/Orbit/backend/bom_agent/bom_urls.py) to support:
- `POST /api/bom/runs/<id>/draft-emails/`
- `GET /api/bom/runs/<id>/emails/`
- `PATCH /api/bom/runs/<id>/emails/<eid>/`
- `POST /api/bom/runs/<id>/emails/<eid>/approve/`
- `POST /api/bom/runs/<id>/emails/approve-all/`
- `POST /api/bom/runs/<id>/emails/<eid>/send/`
- `POST /api/bom/runs/<id>/emails/send-all/`
- `POST /api/bom/runs/<id>/emails/<eid>/follow-up/`
- Verification:
- `cd backend && ./.venv/bin/python -m pytest bom_agent/tests.py -q`
- `cd backend && ./.venv/bin/python -m ruff check bom_agent/models.py bom_agent/serializers.py bom_agent/bom_views.py bom_agent/team_requests.py bom_agent/tests.py`
- `cd backend && ./.venv/bin/python manage.py check`
- Follow-up: the send path currently uses a swappable email transport abstraction implemented with Django’s email backend, so it is ready for a Gmail MCP-backed sender in #66 without changing the API/state machine.

---

# Issue #66 — Gmail MCP integration for outbound team emails

- [x] Inspect current TeamRequest/send flow, settings, and secure storage options for Gmail credentials
- [x] Add secure Gmail credential storage and TeamRequest metadata needed for Gmail send/reply tracking
- [x] Implement Gmail send/poll helpers with token refresh, encrypted credential handling, and message/thread tracking
- [x] Integrate TeamRequest send path with Gmail, expose overdue requests, and add reply polling / parsing / answer application flow
- [x] Resume blocked BOM research when parsed replies satisfy missing inputs
- [x] Add migration and automated tests for send metadata, overdue exposure, reply parsing/application, and poll workflow
- [x] Run targeted verification and document results/follow-ups

## Review — Issue #66
- Added secure Gmail credential storage in [models.py](/Users/amandafogel/Visual%20Studio%20Code/Orbit/backend/bom_agent/models.py) via `GmailCredential`, with encrypted access/refresh tokens and no plaintext token exposure. Added TeamRequest tracking fields for `question_key`, `line_item`, Gmail message/thread IDs, reply message ID, and last poll time; migration is [0007_teamrequest_gmail_message_id_and_more.py](/Users/amandafogel/Visual%20Studio%20Code/Orbit/backend/bom_agent/migrations/0007_teamrequest_gmail_message_id_and_more.py).
- Added [gmail_integration.py](/Users/amandafogel/Visual%20Studio%20Code/Orbit/backend/bom_agent/gmail_integration.py) for token encryption, OAuth refresh, Gmail send, thread polling, reply extraction, and parsed-answer application; [team_requests.py](/Users/amandafogel/Visual%20Studio%20Code/Orbit/backend/bom_agent/team_requests.py) now handles reply parsing, BOM field updates, and research resume triggers.
- Updated [views.py](/Users/amandafogel/Visual%20Studio%20Code/Orbit/backend/bom_agent/views.py) with a secure `GET/PATCH/DELETE /api/team/gmail/credential/` surface for per-user Gmail connection metadata, and updated [bom_views.py](/Users/amandafogel/Visual%20Studio%20Code/Orbit/backend/bom_agent/bom_views.py) / [bom_urls.py](/Users/amandafogel/Visual%20Studio%20Code/Orbit/backend/bom_agent/bom_urls.py) so:
- `POST /api/bom/runs/<id>/emails/<eid>/send/` sends through Gmail and stores `gmail_message_id`, `gmail_thread_id`, and `sent_at`
- `GET /api/bom/runs/<id>/emails/` exposes `is_overdue` for requests older than 48h in `sent`
- `POST /api/bom/runs/<id>/emails/poll/` performs on-demand reply polling and answer application
- Added background-compatible polling via [poll_bom_email_replies.py](/Users/amandafogel/Visual%20Studio%20Code/Orbit/backend/bom_agent/management/commands/poll_bom_email_replies.py), which can be scheduled externally to satisfy reply detection without a queue worker.
- Verification:
- `cd backend && ./.venv/bin/python -m pytest bom_agent/tests.py -q`
- `cd backend && ./.venv/bin/python -m ruff check bom_agent/models.py bom_agent/serializers.py bom_agent/views.py bom_agent/bom_views.py bom_agent/gmail_integration.py bom_agent/team_requests.py bom_agent/tests.py`
- `cd backend && ./.venv/bin/python manage.py check`
- Follow-up: the backend now supports secure Gmail credential storage and Gmail REST send/poll flows, but the actual OAuth consent/start callback flow for acquiring user Gmail tokens is still a separate UI/auth integration task if it does not already exist elsewhere.

---

# Issue #67 — Email draft composer & status tracker UI (Phase 4)

- [x] Inspect current BOM question/run UI and confirm the email API shapes needed by the composer/tracker
- [x] Extend frontend API types for TeamRequest and related email actions
- [x] Add a minimal discard endpoint hookup for draft deletion
- [x] Implement the email draft composer with editable recipient/subject/body, approve/send/discard actions, and approve-all
- [x] Implement the persistent email status tracker with auto-refresh, overdue follow-up CTA, and per-contact timeline/reply text
- [x] Wire the clarifying questions panel "Draft email to [Name]" action into the composer flow and keep BOM run data in sync
- [x] Run targeted backend/frontend verification and document results/follow-ups

## Review — Issue #67
- Added [BomEmailPanel.tsx](/Users/amandafogel/Visual%20Studio%20Code/Orbit/apps/web/src/app/components/BomEmailPanel.tsx) to provide both Phase 4 UI surfaces: a draft composer modal with editable recipient/subject/body, approve/send/discard actions, approve-all, and a persistent status tracker with auto-refresh, overdue follow-up CTA, expandable timeline, and answered reply text.
- Updated [BomQuestionsPanel.tsx](/Users/amandafogel/Visual%20Studio%20Code/Orbit/apps/web/src/app/components/BomQuestionsPanel.tsx) so `Draft email to [Name]` opens the in-app draft composer instead of a `mailto:` link, using the generated TeamRequest draft that matches the current unresolved question.
- Wired [ProjectDetailPage.tsx](/Users/amandafogel/Visual%20Studio%20Code/Orbit/apps/web/src/app/components/ProjectDetailPage.tsx) to host the email panel for the active/selected BOM run and pass composer triggers from the clarifying questions flow.
- Extended [types.ts](/Users/amandafogel/Visual%20Studio%20Code/Orbit/apps/web/src/api/types.ts) with `TeamRequest` and related email action response types. Added a minimal backend discard action in [bom_views.py](/Users/amandafogel/Visual%20Studio%20Code/Orbit/backend/bom_agent/bom_views.py) so the requested `Discard` button can actually remove draft requests.
- Follow-up update: added `approved_at` to `TeamRequest` via [0008_teamrequest_approved_at.py](/Users/amandafogel/Visual%20Studio%20Code/Orbit/backend/bom_agent/migrations/0008_teamrequest_approved_at.py), set it in single/batch approval flows, exposed it in the serializer, covered it in tests, and now render it in the email timeline UI.
- Verification:
- `cd backend && ./.venv/bin/python -m pytest bom_agent/tests.py -q`
- `cd backend && ./.venv/bin/python -m ruff check bom_agent/bom_views.py bom_agent/tests.py`

---

# Gmail OAuth connect flow

- [x] Inspect current Clerk auth, Gmail credential API, and settings page integration points
- [x] Implement backend Gmail OAuth start/callback flow with secure state handling and credential persistence
- [x] Add frontend Gmail connection card with connect/disconnect/status handling in Settings
- [x] Verify backend tests plus frontend lint/build and document follow-ups

## Review — Gmail OAuth connect flow
- Added backend Gmail OAuth start/callback support in [views.py](/Users/amandafogel/Visual%20Studio%20Code/Orbit/backend/bom_agent/views.py) and [urls.py](/Users/amandafogel/Visual%20Studio%20Code/Orbit/backend/bom_agent/urls.py). `POST /api/team/gmail/oauth/start/` now returns a Google consent URL for the authenticated user with a signed state payload, and `GET /api/team/gmail/oauth/callback/` exchanges the authorization code, fetches the Gmail profile email, stores encrypted tokens, and redirects back to the frontend settings screen with a success/error status.
- Extended [gmail_integration.py](/Users/amandafogel/Visual%20Studio%20Code/Orbit/backend/bom_agent/gmail_integration.py) with OAuth helpers for authorization URL construction, code exchange, Gmail profile lookup, and shared redirect URI/scopes so the token acquisition path matches the existing send/refresh logic.
- Updated [SettingsPage.tsx](/Users/amandafogel/Visual%20Studio%20Code/Orbit/apps/web/src/app/components/SettingsPage.tsx) to include a dedicated Gmail integration card in Settings with `Connect Gmail`, `Reconnect Gmail`, and `Disconnect` actions, connected-account status, refresh-token indicator, and toast handling for OAuth callback completion. Added credential/OAuth response types in [types.ts](/Users/amandafogel/Visual%20Studio%20Code/Orbit/apps/web/src/api/types.ts).
- Verification:
- `cd backend && ./.venv/bin/python -m pytest bom_agent/tests.py -q`
- `cd backend && ./.venv/bin/python manage.py check`
- `cd backend && ./.venv/bin/python -m ruff check bom_agent/views.py bom_agent/gmail_integration.py bom_agent/urls.py bom_agent/tests.py`
- `cd apps/web && npm run lint`
- `cd apps/web && npm run build`
- Follow-up: to use the connect flow outside local development, set real `GOOGLE_OAUTH_CLIENT_ID` and `GOOGLE_OAUTH_CLIENT_SECRET`, and register the backend callback URL `/api/team/gmail/oauth/callback/` in the Google OAuth client configuration.
- `cd backend && ./.venv/bin/python manage.py check`
- `cd apps/web && npm run lint`
- `cd apps/web && npm run build`
