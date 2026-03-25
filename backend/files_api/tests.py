import pytest
from unittest.mock import patch
from django.core.files.uploadedfile import SimpleUploadedFile
from files_api.models import UploadedFile
from projects.models import Project


# ── Fixtures ───────────────────────────────────────────────────────────────


@pytest.fixture
def project(db, user):
    return Project.objects.create(name="Test Project", owner=user)


@pytest.fixture
def other_project(db, other_user):
    return Project.objects.create(name="Other Project", owner=other_user)


@pytest.fixture
def uploaded_file(db, project, user):
    return UploadedFile.objects.create(
        project=project,
        uploaded_by=user,
        original_name="part.step",
        file_type="step",
        s3_key="projects/1/test.step",
        file_size=1024,
        status="uploaded",
    )


@pytest.fixture
def mock_s3():
    """Prevent any real S3 calls during tests."""
    with patch("files_api.views.upload_file_to_s3", return_value="projects/test/fake.step") as m:
        yield m


def make_step_file(name="part.step", size=512):
    content = b"ISO-10303-21;" + b"x" * size
    return SimpleUploadedFile(name, content, content_type="application/octet-stream")


# ── File list ──────────────────────────────────────────────────────────────


@pytest.mark.django_db
def test_file_list_requires_auth(api_client, project):
    response = api_client.get(f"/api/files/project/{project.id}/")
    assert response.status_code == 401


@pytest.mark.django_db
def test_file_list_own_project(auth_client, project, uploaded_file):
    response = auth_client.get(f"/api/files/project/{project.id}/")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["original_name"] == "part.step"
    assert data[0]["status"] == "uploaded"


@pytest.mark.django_db
def test_file_list_other_project_returns_404(auth_client, other_project):
    """Users must not be able to list files for another user's project."""
    response = auth_client.get(f"/api/files/project/{other_project.id}/")
    assert response.status_code == 404


@pytest.mark.django_db
def test_file_list_does_not_expose_s3_key(auth_client, project, uploaded_file):
    """s3_key must never be returned to the client."""
    response = auth_client.get(f"/api/files/project/{project.id}/")
    assert response.status_code == 200
    assert "s3_key" not in response.json()[0]


# ── File upload ────────────────────────────────────────────────────────────


@pytest.mark.django_db
def test_file_upload_requires_auth(api_client, project):
    response = api_client.post(
        "/api/files/upload/",
        {"file": make_step_file(), "project_id": project.id},
        format="multipart",
    )
    assert response.status_code == 401


@pytest.mark.django_db
def test_file_upload_rejects_missing_file(auth_client, project):
    response = auth_client.post(
        "/api/files/upload/",
        {"project_id": project.id},
        format="multipart",
    )
    assert response.status_code == 400
    assert "file" in response.json()["error"].lower()


@pytest.mark.django_db
def test_file_upload_rejects_missing_project_id(auth_client):
    response = auth_client.post(
        "/api/files/upload/",
        {"file": make_step_file()},
        format="multipart",
    )
    assert response.status_code == 400
    assert "project_id" in response.json()["error"].lower()


@pytest.mark.django_db
def test_file_upload_rejects_disallowed_extension(auth_client, project):
    bad_file = SimpleUploadedFile("malware.exe", b"MZ", content_type="application/octet-stream")
    response = auth_client.post(
        "/api/files/upload/",
        {"file": bad_file, "project_id": project.id},
        format="multipart",
    )
    assert response.status_code == 400
    assert "Unsupported" in response.json()["error"]


@pytest.mark.django_db
def test_file_upload_rejects_other_users_project(auth_client, other_project):
    """User A must not be able to upload files to User B's project."""
    response = auth_client.post(
        "/api/files/upload/",
        {"file": make_step_file(), "project_id": other_project.id},
        format="multipart",
    )
    assert response.status_code == 404


@pytest.mark.django_db
def test_file_upload_rejects_oversized_file(auth_client, project, monkeypatch):
    """Files exceeding MAX_UPLOAD_BYTES must be rejected before reaching S3."""
    import files_api.views as views_module
    monkeypatch.setattr(views_module, "MAX_UPLOAD_BYTES", 10)

    big_file = SimpleUploadedFile("big.step", b"ISO-10303-21;" + b"x" * 100, content_type="application/octet-stream")
    response = auth_client.post(
        "/api/files/upload/",
        {"file": big_file, "project_id": project.id},
        format="multipart",
    )
    assert response.status_code == 400
    assert "MB" in response.json()["error"]


@pytest.mark.django_db
def test_file_upload_success(auth_client, project, mock_s3):
    """Valid upload creates a DB record and does not expose s3_key."""
    response = auth_client.post(
        "/api/files/upload/",
        {"file": make_step_file("part.step"), "project_id": project.id},
        format="multipart",
    )
    assert response.status_code == 201
    data = response.json()
    assert data["original_name"] == "part.step"
    assert data["file_type"] == "step"
    assert data["status"] == "uploaded"
    assert "s3_key" not in data
    assert UploadedFile.objects.filter(project=project, original_name="part.step").exists()
    mock_s3.assert_called_once()
