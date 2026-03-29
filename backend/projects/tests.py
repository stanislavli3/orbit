import pytest
from projects.models import Project


# ── Fixtures ───────────────────────────────────────────────────────────────


@pytest.fixture
def project(db, user):
    return Project.objects.create(name="My Project", description="desc", owner=user)


@pytest.fixture
def other_project(db, other_user):
    return Project.objects.create(
        name="Other Project", description="", owner=other_user
    )


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
    response = auth_client.post(
        "/api/projects/", {"name": "New Project"}, format="json"
    )
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


# ── Search ──────────────────────────────────────────────────────────────────


@pytest.mark.django_db
def test_project_list_search_by_name(auth_client, user):
    Project.objects.create(name="Gearbox Assembly", owner=user)
    Project.objects.create(name="Pump Housing", owner=user)
    response = auth_client.get("/api/projects/?search=gear")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["name"] == "Gearbox Assembly"


@pytest.mark.django_db
def test_project_list_search_empty_returns_all(auth_client, project):
    response = auth_client.get("/api/projects/?search=")
    assert response.status_code == 200
    assert len(response.json()) == 1


# ── Rename (PATCH) ───────────────────────────────────────────────────────────


@pytest.mark.django_db
def test_project_rename(auth_client, project):
    response = auth_client.patch(
        f"/api/projects/{project.id}/", {"name": "Renamed"}, format="json"
    )
    assert response.status_code == 200
    assert response.json()["name"] == "Renamed"
    project.refresh_from_db()
    assert project.name == "Renamed"


@pytest.mark.django_db
def test_project_rename_requires_auth(api_client, project):
    response = api_client.patch(
        f"/api/projects/{project.id}/", {"name": "X"}, format="json"
    )
    assert response.status_code == 401


@pytest.mark.django_db
def test_project_rename_other_user_returns_404(auth_client, other_project):
    response = auth_client.patch(
        f"/api/projects/{other_project.id}/", {"name": "X"}, format="json"
    )
    assert response.status_code == 404


# ── Delete ───────────────────────────────────────────────────────────────────


@pytest.mark.django_db
def test_project_delete(auth_client, project):
    project_id = project.id
    response = auth_client.delete(f"/api/projects/{project_id}/")
    assert response.status_code == 204
    assert not Project.objects.filter(pk=project_id).exists()


@pytest.mark.django_db
def test_project_delete_requires_auth(api_client, project):
    response = api_client.delete(f"/api/projects/{project.id}/")
    assert response.status_code == 401
    assert Project.objects.filter(pk=project.id).exists()


@pytest.mark.django_db
def test_project_delete_other_user_returns_404(auth_client, other_project):
    response = auth_client.delete(f"/api/projects/{other_project.id}/")
    assert response.status_code == 404
    assert Project.objects.filter(pk=other_project.id).exists()
