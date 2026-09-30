# Worker

Orbit's background worker is a **Celery** process with a **Redis** broker. The
code lives in `backend/` rather than here, because the tasks read and write the
Django models:

| What                         | Where                           |
| ---------------------------- | ------------------------------- |
| Celery app + restart recovery| `backend/config/celery.py`      |
| Queue settings               | `backend/config/settings.py` (`CELERY_*`) |
| File description / extraction| `backend/files_api/tasks.py`    |
| BOM research, library ingest | `backend/bom_agent/tasks.py`    |

## Running it

- `make dev` starts Redis (via `docker-compose.yml`) and the worker together
  with everything else. The worker log is `.orbit-worker.log`.
- `make worker` runs just the worker in the foreground (start Redis first with
  `docker compose up -d redis`).
- `make dev-local` has no Redis, so jobs run inline in the web request
  (`CELERY_TASK_ALWAYS_EAGER=True`). That's fine for quick UI work, but a
  request that starts a BOM run won't return until the research finishes.

## Durability guarantees

- **Acks-late.** A job leaves Redis only after it finishes, so a crashed worker
  gets it redelivered.
- **Recovery on startup.** When a worker starts, it re-queues every job the
  database still shows as in flight: BOM runs in `researching` or
  `generating_report`, files in `processing`, and library docs in `pending` or
  `processing`.
- **Resumable research.** BOM research skips line items that are already
  `sourced` and clears partial quotes before redoing the rest, so a resumed run
  never duplicates quotes.
- **One copy at a time.** Each research enqueue gets a new `job_token`. An
  older delivery sees the mismatch and stops before its next line item.
- **Visible failure.** A job that errors sets its row to `failed` instead of
  disappearing.
