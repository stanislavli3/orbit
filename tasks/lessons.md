# Lessons

## Live-testing background workers against the dev DB
- **What happened (Story 2):** a stubbed Celery worker used to verify crash recovery also ran the startup recovery sweep, which picked up a real, long-orphaned BOM run (run 3) and wrote stub data into it. It had to be restored by hand.
- **Rule:** before starting any worker or recovery code against `backend/db.sqlite3`, query for existing rows in in-flight states (`BomResearchRun.status in researching/generating_report`, `UploadedFile.status=processing`, `LibraryDocument.ingest_status in pending/processing`). If there are any, point the test at a copy of the DB or scope the stub to the test's own rows. Never let stubbed work touch rows the test didn't create.
