"""
Failure handling shared by every Celery task.

``@monitored_task`` replaces ``@shared_task``. A task that raises is handled in
one of three ways:

* **Transient** errors (rate limits, 5xx, dropped connections, a locked SQLite
  file) retry with exponential backoff, at most ``MAX_RETRIES`` times.
* Any other error, or the last failed retry, is **dead-lettered**: a structured
  log event, a ``JobFailure`` row (the admin is the one place to check), a
  webhook alert, and the task's ``on_dead`` hook marks its domain row failed.
* A job that keeps **killing the worker** never reaches Python's except
  blocks, so each start is counted in ``JobAttempt``; after
  ``MAX_UNFINISHED_STARTS`` the job is dead-lettered instead of redelivered
  forever.

Calling a task directly (``task(arg)``) never retries and re-raises, so tests
and management code see the original exception.
"""

import json
import logging
import traceback as tb
from datetime import timedelta

import anthropic
from botocore import exceptions as boto_exceptions
from celery import Task, shared_task
from celery.exceptions import TaskPredicate
from django.db import OperationalError, transaction
from django.db.models import F
from django.utils import timezone

from .alerts import send_alert
from .models import JobAttempt, JobFailure

logger = logging.getLogger("orbit.jobs")

MAX_RETRIES = 3
RETRY_BACKOFF_SECONDS = 30  # 30s, 60s, 120s
MAX_UNFINISHED_STARTS = 3
DEDUPE_WINDOW = timedelta(hours=1)

_S3_THROTTLE_CODES = {
    "Throttling",
    "ThrottlingException",
    "SlowDown",
    "RequestTimeout",
    "ServiceUnavailable",
}


def is_transient(exc: BaseException) -> bool:
    """True for errors that usually clear up on their own, so a retry is worthwhile."""
    if isinstance(
        exc,
        (
            anthropic.APIConnectionError,  # includes timeouts
            anthropic.RateLimitError,
            anthropic.InternalServerError,
            boto_exceptions.ConnectionError,
            boto_exceptions.ReadTimeoutError,
            ConnectionError,
            TimeoutError,
        ),
    ):
        return True
    if isinstance(exc, boto_exceptions.ClientError):
        status = exc.response.get("ResponseMetadata", {}).get("HTTPStatusCode", 0)
        code = exc.response.get("Error", {}).get("Code", "")
        return status >= 500 or code in _S3_THROTTLE_CODES
    # The worker is a second writer on SQLite; a lock clears when the other
    # writer commits. Other OperationalErrors (missing table...) won't.
    return isinstance(exc, OperationalError) and "locked" in str(exc).lower()


def record_failure(
    job_type: str,
    target_id,
    exc: BaseException,
    *,
    task_id: str = "",
    attempts: int = 1,
    notify: bool = True,
) -> JobFailure | None:
    """
    Log a structured failure event, store it in ``JobFailure`` and alert.

    Repeats of the same unresolved failure within ``DEDUPE_WINDOW`` fold into
    the existing row without a new alert, so a job that fails every cycle
    doesn't spam the channel. Never raises: it runs in error paths and must not
    mask the original error.
    """
    try:
        target = "" if target_id is None else str(target_id)
        error_class = type(exc).__name__
        message = str(exc)[:2000]
        trace = "".join(tb.format_exception(type(exc), exc, exc.__traceback__))[-8000:]
        logger.error(
            "job_failed %s",
            json.dumps(
                {
                    "job_type": job_type,
                    "target_id": target,
                    "task_id": task_id,
                    "error_class": error_class,
                    "error_message": message[:500],
                    "attempts": attempts,
                },
                sort_keys=True,
            ),
        )

        now = timezone.now()
        existing = JobFailure.objects.filter(
            job_type=job_type,
            target_id=target,
            error_class=error_class,
            resolved_at__isnull=True,
            last_seen_at__gte=now - DEDUPE_WINDOW,
        ).first()
        if existing:
            JobFailure.objects.filter(pk=existing.pk).update(
                occurrences=F("occurrences") + 1,
                last_seen_at=now,
                error_message=message,
                traceback=trace,
            )
            existing.refresh_from_db()
            return existing

        failure = JobFailure.objects.create(
            job_type=job_type,
            target_id=target,
            task_id=task_id,
            error_class=error_class,
            error_message=message,
            traceback=trace,
            attempts=attempts,
        )
        if notify:
            text = _alert_text(failure)
            transaction.on_commit(lambda: send_alert(text))
        return failure
    except Exception:
        logger.exception("record_failure_failed")
        return None


def _alert_text(failure: JobFailure) -> str:
    target = f" #{failure.target_id}" if failure.target_id else ""
    return (
        f":rotating_light: Orbit job failed: {failure.job_type}{target} "
        f"({failure.error_class}: {failure.error_message[:300]}) "
        f"after {failure.attempts} attempt(s). See Django admin → Job failures."
    )


def _register_start(job_type: str, target_id: str) -> bool:
    """Count a start. False once the job has started too often without finishing."""
    attempt, _ = JobAttempt.objects.get_or_create(job_type=job_type, target_id=target_id)
    if attempt.unfinished_starts >= MAX_UNFINISHED_STARTS:
        return False
    JobAttempt.objects.filter(pk=attempt.pk).update(
        unfinished_starts=F("unfinished_starts") + 1
    )
    return True


def _clear_starts(job_type: str, target_id: str) -> None:
    try:
        JobAttempt.objects.filter(job_type=job_type, target_id=target_id).delete()
    except Exception:
        logger.exception("clear_job_attempts_failed")


class MonitoredTask(Task):
    job_type = "job"
    notify = True
    on_dead = None  # staticmethod(args, exc): mark the task's domain row failed

    @staticmethod
    def _guard_enabled(request) -> bool:
        # Only a real worker delivery can crash-loop; eager runs and direct
        # calls share the caller's process.
        return not (request.is_eager or request.called_directly)

    def __call__(self, *args, **kwargs):
        # Read before Task.__call__ pushes its own (blank) request context.
        request = self.request
        target_id = str(args[0]) if args else ""
        guarded = self._guard_enabled(request)

        if guarded and not _register_start(self.job_type, target_id):
            self._dead_letter(
                args,
                RuntimeError(
                    f"Worker was lost {MAX_UNFINISHED_STARTS} times while running this job"
                ),
                request,
                attempts=MAX_UNFINISHED_STARTS,
            )
            _clear_starts(self.job_type, target_id)
            return None

        try:
            return super().__call__(*args, **kwargs)
        except TaskPredicate:
            raise  # Retry / Ignore / Reject: Celery control flow
        except Exception as exc:
            retries = request.retries or 0
            if not request.called_directly and is_transient(exc) and retries < self.max_retries:
                delay = RETRY_BACKOFF_SECONDS * 2**retries
                logger.warning(
                    "job_retry %s",
                    json.dumps(
                        {
                            "job_type": self.job_type,
                            "target_id": target_id,
                            "error_class": type(exc).__name__,
                            "retry": retries + 1,
                            "max_retries": self.max_retries,
                            "delay_seconds": delay,
                        },
                        sort_keys=True,
                    ),
                )
                raise self.retry(exc=exc, countdown=delay)
            self._dead_letter(args, exc, request, attempts=retries + 1)
            raise
        finally:
            if guarded:
                _clear_starts(self.job_type, target_id)

    def _dead_letter(self, args, exc, request, attempts: int) -> None:
        target_id = str(args[0]) if args else ""
        record_failure(
            self.job_type,
            target_id,
            exc,
            task_id=request.id or "",
            attempts=attempts,
            notify=self.notify,
        )
        if self.on_dead:
            try:
                self.on_dead(args, exc)
            except Exception:
                logger.exception("job_on_dead_hook_failed")


def monitored_task(job_type: str, *, on_dead=None, notify: bool = True):
    """``@shared_task`` with retry, dead-letter and alerting; see the module docstring."""
    return shared_task(
        base=MonitoredTask,
        max_retries=MAX_RETRIES,
        job_type=job_type,
        notify=notify,
        on_dead=staticmethod(on_dead) if on_dead else None,
    )
