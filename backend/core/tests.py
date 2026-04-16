import pytest


@pytest.mark.django_db
def test_health_check_returns_ok(api_client):
    response = api_client.get("/api/health/")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


@pytest.mark.django_db
def test_health_check_is_public(api_client):
    """Health check must be reachable without authentication."""
    response = api_client.get("/api/health/")
    assert response.status_code == 200
