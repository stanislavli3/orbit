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
