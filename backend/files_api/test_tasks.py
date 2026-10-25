"""Story 2 — durable task queue for uploaded-file processing."""

import json
from unittest.mock import patch

import pytest
from botocore.exceptions import ClientError
from django.core.files.uploadedfile import SimpleUploadedFile

from core.jobs import MAX_RETRIES
from core.models import JobFailure
from files_api.models import UploadedFile
from files_api.tasks import describe_file, extract_file, recover_orphaned_jobs
from projects.models import Project


@pytest.fixture
def project(db, user):
    return Project.objects.create(name="Queue Project", owner=user)


@pytest.fixture
def uploaded_file(project, user):
    return UploadedFile.objects.create(
        project=project, uploaded_by=user, original_name="part.step", file_type="step",
        s3_key="projects/1/part.step", file_size=10, status="uploaded",
    )


def test_upload_enqueues_description_after_commit(
    auth_client, project, django_capture_on_commit_callbacks
):
    upload = SimpleUploadedFile("part.step", b"ISO-10303-21;")
    with patch("files_api.views.upload_file_to_s3", return_value="projects/x/part.step"), \
            patch("files_api.views.describe_file.delay") as delay, \
            django_capture_on_commit_callbacks(execute=True):
        response = auth_client.post(
            "/api/files/upload/", {"file": upload, "project_id": project.id}, format="multipart"
        )
    assert response.status_code == 201
    delay.assert_called_once_with(response.json()["id"])


def test_extract_marks_processing_and_enqueues(
    auth_client, uploaded_file, django_capture_on_commit_callbacks
):
    with patch("files_api.views.extract_file.delay") as delay, \
            django_capture_on_commit_callbacks(execute=True):
        response = auth_client.post(f"/api/files/{uploaded_file.id}/extract/")

    assert response.status_code == 202
    uploaded_file.refresh_from_db()
    assert uploaded_file.status == "processing"
    delay.assert_called_once_with(uploaded_file.id)


def test_extract_failure_is_visible(uploaded_file):
    with patch("files_api.tasks.download_file_from_s3", side_effect=RuntimeError("s3 down")):
        with pytest.raises(RuntimeError):
            extract_file(uploaded_file.id)
    uploaded_file.refresh_from_db()
    assert uploaded_file.status == "failed"


def test_extract_of_deleted_file_is_a_no_op(uploaded_file):
    file_id = uploaded_file.id
    uploaded_file.delete()
    extract_file(file_id)  # must not raise


def test_recovery_requeues_only_processing_files(project, user, uploaded_file):
    stuck = UploadedFile.objects.create(
        project=project, uploaded_by=user, original_name="b.step", file_type="step",
        s3_key="projects/1/b.step", file_size=10, status="processing",
    )
    with patch("files_api.tasks.extract_file.delay") as delay:
        recover_orphaned_jobs()
    delay.assert_called_once_with(stuck.id)


# ── Story 4: failures are recorded, alerted and bounded ──────────────────────


def test_failed_extraction_reaches_the_alert_channel(
    uploaded_file, settings, django_capture_on_commit_callbacks
):
    settings.ALERT_WEBHOOK_URL = "https://hooks.example.test/services/T/B/x"
    with patch("files_api.tasks.download_file_from_s3", side_effect=RuntimeError("NoSuchKey")), \
            patch("core.alerts.urlopen") as post, \
            django_capture_on_commit_callbacks(execute=True):
        result = extract_file.apply(args=[uploaded_file.id])

    assert result.failed()
    uploaded_file.refresh_from_db()
    assert uploaded_file.status == "failed"
    failure = JobFailure.objects.get()
    assert (failure.job_type, failure.target_id) == ("file_extraction", str(uploaded_file.id))
    assert "NoSuchKey" in failure.error_message
    text = json.loads(post.call_args.args[0].data)["text"]
    assert "file_extraction" in text and "NoSuchKey" in text


def test_transient_s3_outage_retries_then_gives_up(uploaded_file):
    outage = ClientError(
        {"Error": {"Code": "SlowDown"}, "ResponseMetadata": {"HTTPStatusCode": 503}}, "GetObject"
    )
    with patch("files_api.tasks.download_file_from_s3", side_effect=outage) as download:
        result = extract_file.apply(args=[uploaded_file.id])

    assert result.failed()
    assert download.call_count == MAX_RETRIES + 1
    uploaded_file.refresh_from_db()
    assert uploaded_file.status == "failed"
    assert JobFailure.objects.get().attempts == MAX_RETRIES + 1


def test_failed_description_is_recorded_but_does_not_page(
    uploaded_file, settings, django_capture_on_commit_callbacks
):
    settings.ALERT_WEBHOOK_URL = "https://hooks.example.test/services/T/B/x"
    with patch("files_api.tasks.download_file_from_s3", side_effect=RuntimeError("boom")), \
            patch("core.alerts.urlopen") as post, \
            django_capture_on_commit_callbacks(execute=True):
        describe_file.apply(args=[uploaded_file.id])

    assert JobFailure.objects.get().job_type == "file_description"
    post.assert_not_called()
    uploaded_file.refresh_from_db()
    assert uploaded_file.status == "uploaded"  # still usable
