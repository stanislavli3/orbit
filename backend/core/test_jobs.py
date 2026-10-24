"""Story 4 — failure classification, retry cap, dead-lettering, alerting, crash-loop guard."""

import json
import logging
from unittest.mock import MagicMock, patch

import anthropic
import pytest
from botocore.exceptions import ClientError, EndpointConnectionError
from django.db import OperationalError
from django.utils import timezone

from core.alerts import send_alert
from core.jobs import (
    DEDUPE_WINDOW,
    MAX_RETRIES,
    MAX_UNFINISHED_STARTS,
    MonitoredTask,
    _register_start,
    is_transient,
    monitored_task,
    record_failure,
)
from core.models import JobAttempt, JobFailure

# The SDK's HTTP library differs between versions, so build its errors from mocks.
_REQUEST = MagicMock()
WEBHOOK = "https://hooks.example.test/services/T/B/x"


def _api_error(cls, status):
    response = MagicMock(status_code=status, request=_REQUEST)
    response.headers.get.return_value = None
    return cls("x", response=response, body=None)


def _s3_error(code, status):
    return ClientError(
        {"Error": {"Code": code, "Message": "m"}, "ResponseMetadata": {"HTTPStatusCode": status}},
        "GetObject",
    )


@pytest.mark.parametrize(
    "exc",
    [
        _api_error(anthropic.RateLimitError, 429),
        _api_error(anthropic.InternalServerError, 500),
        anthropic.APIConnectionError(request=_REQUEST),
        anthropic.APITimeoutError(request=_REQUEST),
        EndpointConnectionError(endpoint_url="http://localhost:4566"),
        _s3_error("SlowDown", 503),
        _s3_error("InternalError", 500),
        ConnectionResetError(),
        TimeoutError(),
        OperationalError("database is locked"),
    ],
)
def test_transient_errors_are_retryable(exc):
    assert is_transient(exc)


@pytest.mark.parametrize(
    "exc",
    [
        ValueError("bad input"),
        KeyError("x"),
        RuntimeError("boom"),
        _api_error(anthropic.BadRequestError, 400),
        _api_error(anthropic.AuthenticationError, 401),
        _s3_error("NoSuchKey", 404),
        OperationalError("no such table: nope"),
    ],
)
def test_permanent_errors_are_not_retried(exc):
    assert not is_transient(exc)


# ── A task that exercises the real decorator ─────────────────────────────────

_state = {"calls": 0, "fail_with": None, "fail_times": 0, "dead": []}


def _on_dead(args, exc):
    _state["dead"].append((args, type(exc).__name__))


@monitored_task("test_job", on_dead=_on_dead)
def sample_job(target_id):
    _state["calls"] += 1
    if _state["calls"] <= _state["fail_times"]:
        raise _state["fail_with"]
    return "ok"


@monitored_task("test_quiet_job", notify=False)
def quiet_job(target_id):
    raise ValueError("not worth a page")


@pytest.fixture(autouse=True)
def reset_state():
    _state.update(calls=0, fail_with=None, fail_times=0, dead=[])


@pytest.fixture
def webhook(settings):
    settings.ALERT_WEBHOOK_URL = WEBHOOK
    with patch("core.alerts.urlopen") as post:
        yield post


def test_transient_error_is_retried_then_succeeds(db, webhook):
    _state.update(fail_with=ConnectionError("blip"), fail_times=2)

    result = sample_job.apply(args=[7])

    assert result.successful()
    assert _state["calls"] == 3
    assert not JobFailure.objects.exists()
    assert _state["dead"] == []
    webhook.assert_not_called()


def test_retries_stop_at_the_cap_and_the_job_is_dead_lettered(
    db, webhook, django_capture_on_commit_callbacks
):
    _state.update(fail_with=ConnectionError("down"), fail_times=99)

    with django_capture_on_commit_callbacks(execute=True):
        result = sample_job.apply(args=[7])

    assert result.failed()
    assert _state["calls"] == MAX_RETRIES + 1  # not forever
    failure = JobFailure.objects.get()
    assert (failure.job_type, failure.target_id) == ("test_job", "7")
    assert failure.error_class == "ConnectionError"
    assert failure.attempts == MAX_RETRIES + 1
    assert "Traceback" in failure.traceback
    assert _state["dead"] == [((7,), "ConnectionError")]  # domain row gets marked failed
    webhook.assert_called_once()  # one alert, not one per attempt


def test_permanent_error_skips_retries(db, webhook, django_capture_on_commit_callbacks):
    _state.update(fail_with=ValueError("malformed"), fail_times=99)

    with django_capture_on_commit_callbacks(execute=True):
        result = sample_job.apply(args=[7])

    assert result.failed()
    assert _state["calls"] == 1
    assert JobFailure.objects.get().attempts == 1
    assert _state["dead"] == [((7,), "ValueError")]
    webhook.assert_called_once()


def test_direct_call_reraises_the_original_error_without_retrying(db):
    _state.update(fail_with=ConnectionError("blip"), fail_times=99)

    with pytest.raises(ConnectionError):
        sample_job(7)

    assert _state["calls"] == 1
    assert JobFailure.objects.count() == 1


def test_non_notifying_task_is_recorded_but_does_not_alert(
    db, webhook, django_capture_on_commit_callbacks
):
    with django_capture_on_commit_callbacks(execute=True):
        quiet_job.apply(args=[3])

    assert JobFailure.objects.get().job_type == "test_quiet_job"
    webhook.assert_not_called()


def test_failure_logs_a_structured_event(db, caplog):
    with caplog.at_level(logging.ERROR, logger="orbit.jobs"):
        record_failure("test_job", 9, ValueError("bad file"), task_id="abc", attempts=2)

    message = caplog.records[0].getMessage()
    assert message.startswith("job_failed ")
    event = json.loads(message.removeprefix("job_failed "))
    assert event == {
        "job_type": "test_job",
        "target_id": "9",
        "task_id": "abc",
        "error_class": "ValueError",
        "error_message": "bad file",
        "attempts": 2,
    }


# ── Alert channel ────────────────────────────────────────────────────────────


def test_alert_posts_slack_compatible_json(settings):
    settings.ALERT_WEBHOOK_URL = WEBHOOK
    with patch("core.alerts.urlopen") as post:
        send_alert("hello")

    request = post.call_args.args[0]
    assert request.full_url == WEBHOOK
    assert request.get_method() == "POST"
    assert json.loads(request.data) == {"text": "hello"}


def test_alert_is_a_no_op_without_a_webhook(settings):
    settings.ALERT_WEBHOOK_URL = ""
    with patch("core.alerts.urlopen") as post:
        send_alert("hello")
    post.assert_not_called()


def test_alert_delivery_failure_never_raises(settings):
    settings.ALERT_WEBHOOK_URL = WEBHOOK
    with patch("core.alerts.urlopen", side_effect=OSError("slack is down")):
        send_alert("hello")  # must not raise


# ── De-duplication ───────────────────────────────────────────────────────────


def test_repeat_failures_fold_into_one_row_and_one_alert(
    db, webhook, django_capture_on_commit_callbacks
):
    with django_capture_on_commit_callbacks(execute=True):
        for _ in range(3):
            record_failure("email_poll", 4, RuntimeError("Gmail API error (429)"))

    failure = JobFailure.objects.get()
    assert failure.occurrences == 3
    webhook.assert_called_once()


def test_resolved_expired_or_different_failures_are_new_rows(
    db, webhook, django_capture_on_commit_callbacks
):
    with django_capture_on_commit_callbacks(execute=True):
        first = record_failure("email_poll", 4, RuntimeError("x"))
        JobFailure.objects.filter(pk=first.pk).update(resolved_at=timezone.now())
        record_failure("email_poll", 4, RuntimeError("x"))  # resolved: new row

        stale = JobFailure.objects.filter(resolved_at__isnull=True).get()
        JobFailure.objects.filter(pk=stale.pk).update(
            last_seen_at=timezone.now() - DEDUPE_WINDOW - DEDUPE_WINDOW
        )
        record_failure("email_poll", 4, RuntimeError("x"))  # window passed: new row
        record_failure("email_poll", 5, RuntimeError("x"))  # other target: new row

    assert JobFailure.objects.count() == 4
    assert webhook.call_count == 4


def test_record_failure_never_raises(db):
    with patch("core.jobs.JobFailure.objects") as manager:
        manager.filter.side_effect = RuntimeError("db down")
        assert record_failure("test_job", 1, ValueError("x")) is None


# ── Crash-loop guard ─────────────────────────────────────────────────────────


def test_unfinished_starts_are_counted_up_to_the_limit(db):
    results = [_register_start("test_job", "7") for _ in range(MAX_UNFINISHED_STARTS + 1)]
    assert results == [True] * MAX_UNFINISHED_STARTS + [False]


def _guard_on():
    return patch.object(MonitoredTask, "_guard_enabled", staticmethod(lambda request: True))


def test_job_that_keeps_killing_the_worker_is_dead_lettered_not_run(
    db, webhook, django_capture_on_commit_callbacks
):
    JobAttempt.objects.create(
        job_type="test_job", target_id="7", unfinished_starts=MAX_UNFINISHED_STARTS
    )

    with _guard_on(), django_capture_on_commit_callbacks(execute=True):
        assert sample_job(7) is None

    assert _state["calls"] == 0
    failure = JobFailure.objects.get()
    assert "lost" in failure.error_message
    assert _state["dead"] == [((7,), "RuntimeError")]
    assert not JobAttempt.objects.exists()  # a manual re-run starts clean
    webhook.assert_called_once()


def test_normal_exit_clears_the_start_count(db):
    with _guard_on():
        assert sample_job(7) == "ok"
    assert not JobAttempt.objects.exists()

    _state.update(fail_with=ValueError("x"), fail_times=99)
    with _guard_on(), pytest.raises(ValueError):
        sample_job(7)
    assert not JobAttempt.objects.exists()
