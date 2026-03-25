import pytest
from projects.models import Project


# ── Fixtures ───────────────────────────────────────────────────────────────


@pytest.fixture
def project(db, user):
    return Project.objects.create(name="My Project", description="desc", owner=user)


@pytest.fixture
def other_project(db, other_user):
    return Project.objects.create(name="Other Project", description="", owner=other_user)


# ── List ───────────────────────────────────────────────────────────────────


@pytest.mark.django_db
def test_project_list_requires_auth(api_client):
    response = api_client.get("/api/projects/")
    assert response.status_code == 401


@pytest.mark.django_db
def test_project_list_returns_only_own_projects(auth_client, project, other_project):
    response = auth_client.get("/api/projects/")
    assert response.status_code == 200
    ids = [p["id"] for p in response.json()]
    assert project.id in ids
    assert other_project.id not in ids


@pytest.mark.django_db
def test_project_list_includes_file_count(auth_client, project):
    response = auth_client.get("/api/projects/")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["file_count"] == 0


# ── Create ─────────────────────────────────────────────────────────────────


@pytest.mark.django_db
def test_project_create_requires_auth(api_client):
    response = api_client.post("/api/projects/", {"name": "New"}, format="json")
    assert response.status_code == 401


@pytest.mark.django_db
def test_project_create_sets_owner(auth_client, user):
    response = auth_client.post("/api/projects/", {"name": "New Project"}, format="json")
    assert response.status_code == 201
    assert response.json()["owner"] == user.id
    assert Project.objects.filter(name="New Project", owner=user).exists()


# ── Detail ─────────────────────────────────────────────────────────────────


@pytest.mark.django_db
def test_project_detail_requires_auth(api_client, project):
    response = api_client.get(f"/api/projects/{project.id}/")
    assert response.status_code == 401


@pytest.mark.django_db
def test_project_detail_own_project(auth_client, project):
    response = auth_client.get(f"/api/projects/{project.id}/")
    assert response.status_code == 200
    assert response.json()["id"] == project.id
    assert response.json()["name"] == project.name


@pytest.mark.django_db
def test_project_detail_other_user_project_returns_404(auth_client, other_project):
    """Users must not be able to read other users' projects."""
    response = auth_client.get(f"/api/projects/{other_project.id}/")
    assert response.status_code == 404
