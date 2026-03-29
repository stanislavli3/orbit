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
