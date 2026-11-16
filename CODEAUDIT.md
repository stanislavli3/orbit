✅ Working / fully implemented
Auth & core plumbing
Clerk JWT (RS256) verification against a real issuer, auto-provisions Django User records — clerk_auth.py
Health check endpoint at /api/health/ reporting Anthropic key presence
Projects & files
Project CRUD, ownership-scoped — projects
File upload → S3 (LocalStack locally), pure-Python STEP/DWG/DXF/IGES header parser (no native CAD runtime) — extractor.py
Claude Haiku file descriptions + engineering profile summaries — ai_description.py
Real embeddings for semantic search (falls back to hashed TF-IDF if no API key) — embeddings.py
History feed at /api/history/ (HistoryView in projects/views.py) — despite an older todo.md note saying it didn't exist yet, it's there now
BOM agent (the core product)
Full research pipeline actually calls Claude Sonnet with the real hosted web_search tool — this is genuine live supplier research, not mocked data — research_pipeline.py
Structured tool-calls record material specs, supplier quotes, and risk flags with retry/backoff on rate limits
Excel export: 5-sheet workbook with live formulas, conditional formatting, freeze panes via openpyxl — excel_export.py, validated by scripts/recalc.py
Team outreach: TeamRequest draft (Claude Haiku) → edit → approve → send → follow-up state machine
Gmail integration is real, not stubbed: encrypted token storage, OAuth start/callback, send, thread polling, reply parsing that resumes blocked research — gmail_integration.py
Assistant / RAG
Real Claude Sonnet chat with cosine-similarity retrieval over file embeddings, session history — rag.py
Frontend
Every route in routes.tsx is wired to a real component and real API calls via TanStack Query — Vault, project detail (BOM results table, email panel, analytics), extraction runs, library, settings (including a working Gmail connect/disconnect card), 3D part preview via react-three-fiber
No leftover mock/hardcoded data found anywhere in apps/web/src (grepped for mock/hardcoded/placeholder data — clean)
Tests: backend has real test coverage — bom_agent/tests.py (731 lines), files_api/tests.py (180), projects/tests.py (163); accounts/core are thin (15–17 lines).
🔧 Needs fixing
No real task queue. Both file extraction and BOM research run on Python threading.Thread(daemon=True) inside the Django process (confirmed in bom_views.py:327 and files_api/views.py), not Celery/RQ despite apps/worker existing as a placeholder. A server restart or crash mid-run silently loses that work, and it can't scale past one process.
Gmail OAuth needs real credentials to work outside local dev (GOOGLE_OAUTH_CLIENT_ID/SECRET are placeholders per the todo.md follow-up).
Minor: docker-compose.yml still carries the obsolete version: "3.8" key (harmless warning, not fixed despite being flagged in tasks/todo.md).
Minor: /workflows route just renders VaultPage as a stand-in (commented // Placeholder in routes.tsx) — not a distinct feature.
Minor: the "COTS" filter in BOM results is inferred client-side (quote's tooling_cost === 0) because there's no dedicated backend status for it yet.
❌ Not implemented
apps/api and apps/worker — empty .gitkeep placeholders. All backend logic currently lives in backend/, not a separate api/worker split.
packages/contracts — empty placeholder; no shared TS/Python type-contract package actually exists.
eval/, prompts/, storage/ — all empty .gitkeep scaffolds; no eval harness, prompt library, or storage abstraction has been built yet.
CD/deployment — docs/ci.md explicitly states this is "Not configured yet"; no deploy workflow of any kind.

