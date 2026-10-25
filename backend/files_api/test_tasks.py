"""Story 2 — durable task queue for uploaded-file processing."""

from unittest.mock import patch

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

from files_api.models import UploadedFile
from files_api.tasks import extract_file, recover_orphaned_jobs
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
