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

## Failure handling and alerts

Every task is declared with `@monitored_task(job_type)` (`backend/core/jobs.py`)
instead of `@shared_task`. When a job raises:

- **Transient errors** (rate limits, 5xx, dropped connections, a locked SQLite
  file) retry with exponential backoff (30s, 60s, 120s), at most 3 times.
- **Anything else, or the last failed retry,** is dead-lettered: it stops
  retrying, the task's row is marked `failed`, and the failure is recorded and
  alerted (below).
- **A job that keeps killing the worker** is counted at each start; after 3
  unfinished starts it is dead-lettered instead of redelivered forever.

Job types: `file_extraction`, `file_description`, `bom_research`,
`library_ingest`, plus `email_send` and `email_poll` (the Gmail calls in
`bom_agent`, which run in web requests and the `poll_bom_email_replies`
command rather than Celery).

Where a failure shows up:

1. **Logs.** One `job_failed {json}` line (`orbit.jobs` logger) with job type,
   target id, error class and message. Retries log `job_retry {json}`.
2. **Django admin → Job failures.** The one place to check. Each row has the
   traceback; repeats of the same unresolved failure within an hour fold into
   one row (`occurrences`). Use "Mark selected failures resolved" when handled.
3. **Webhook.** Set `ALERT_WEBHOOK_URL` in `backend/.env` to a Slack incoming
   webhook (or any service accepting `{"text": ...}`) and each new failure is
   posted there. `file_description` failures are admin-only (non-fatal).

Alert delivery never raises, so a down webhook can't break the job.
