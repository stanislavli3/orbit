import pytest
from django.contrib.auth.models import User
from rest_framework.test import APIClient

from projects.models import Project

from . import interference
from .models import ChangeEvent, ImmutableError, ProjectMember


def client_for(user):
    c = APIClient()
    c.force_authenticate(user=user)
    return c


@pytest.fixture
def team(db, user):
    project = Project.objects.create(name="P", owner=user)
    designer = User.objects.create_user("des", "des@example.com", "x")
    reviewer = User.objects.create_user("rev", "rev@example.com", "x")
    ProjectMember.objects.create(project=project, user=designer, role="designer")
    ProjectMember.objects.create(project=project, user=reviewer, role="reviewer")
    return project, designer, reviewer


def url(project, suffix=""):
    return f"/api/review/{project.id}/{suffix}"


def create_change(project, author, **extra):
    r = client_for(author).post(
        url(project, "changes/"), {"title": "Thicker bracket", "parts": ["ORB-1042"], **extra}, format="json"
    )
    assert r.status_code == 201, r.content
    return r.json()


# ── SCRUM-57: roles + approvals ────────────────────────────────────────────


def test_owner_assigns_roles_by_email(auth_client, team, other_user):
    project, _, _ = team
    r = auth_client.post(url(project, "members/"), {"email": other_user.email, "role": "reviewer"}, format="json")
    assert r.status_code == 201
    assert ProjectMember.objects.get(project=project, user=other_user).role == "reviewer"


def test_non_owner_cannot_assign_roles(team, other_user):
    project, designer, _ = team
    r = client_for(designer).post(url(project, "members/"), {"email": other_user.email, "role": "reviewer"}, format="json")
    assert r.status_code == 403


def test_outsider_cannot_see_project(team, other_user):
    project, _, _ = team
    assert client_for(other_user).get(url(project, "changes/")).status_code == 404


def test_reviewer_cannot_submit_change(team):
    project, _, reviewer = team
    r = client_for(reviewer).post(url(project, "changes/"), {"title": "x"}, format="json")
    assert r.status_code == 403


def test_full_approval_flow_records_history(team):
    project, designer, reviewer = team
    change = create_change(project, designer)
    assert change["state"] == "pending" and change["author"] == "des"

    r = client_for(reviewer).post(
        url(project, f"changes/{change['id']}/decision/"), {"decision": "approved", "comment": "LGTM"}, format="json"
    )
    assert r.status_code == 200
    body = r.json()
    assert body["state"] == "approved"
    assert [(e["actor"], e["action"], e["comment"]) for e in body["events"]] == [
        ("des", "created", ""), ("rev", "approved", "LGTM"),
    ]
    assert all(e["created_at"] for e in body["events"])

    # Decided changes cannot be re-decided.
    r = client_for(reviewer).post(url(project, f"changes/{change['id']}/decision/"), {"decision": "rejected"}, format="json")
    assert r.status_code == 409


def test_designer_and_owner_without_reviewer_role_cannot_approve(auth_client, team):
    project, designer, _ = team
    change = create_change(project, designer)
    for c in (client_for(designer), auth_client):
        r = c.post(url(project, f"changes/{change['id']}/decision/"), {"decision": "approved"}, format="json")
        assert r.status_code == 403


def test_author_cannot_approve_own_change(auth_client, team, user):
    project, _, _ = team
    ProjectMember.objects.create(project=project, user=user, role="reviewer")
    change = create_change(project, user)  # owner may submit; now also a reviewer
    r = auth_client.post(url(project, f"changes/{change['id']}/decision/"), {"decision": "approved"}, format="json")
    assert r.status_code == 403


def test_reject_and_invalid_decision(team):
    project, designer, reviewer = team
    change = create_change(project, designer)
    c = client_for(reviewer)
    assert c.post(url(project, f"changes/{change['id']}/decision/"), {"decision": "maybe"}, format="json").status_code == 400
    r = c.post(url(project, f"changes/{change['id']}/decision/"), {"decision": "rejected", "comment": "clash"}, format="json")
    assert r.json()["state"] == "rejected"


def test_audit_events_are_immutable(team):
    project, designer, _ = team
    create_change(project, designer)
    event = ChangeEvent.objects.get()
    event.comment = "tampered"
    with pytest.raises(ImmutableError):
        event.save()
    with pytest.raises(ImmutableError):
        event.delete()


# ── SCRUM-56: bounding-box interference ────────────────────────────────────


def test_sample_step_layout_parses():
    boxes, source = interference.load_layout()
    assert source.endswith("bracket_assembly_layout.step")
    by_id = {b.id: b for b in boxes}
    assert by_id["ORB-1043"].min == (0.0, 0.0, 4.0)
    assert by_id["ORB-1043"].max == (40.0, 30.0, 5.5)


def test_overlap_volume_and_touching_faces():
    boxes, _ = interference.load_layout()
    results = {r["part_b"]: r for r in interference.check(boxes, "ORB-1042")}
    assert results["ORB-1043"]["overlap_volume"] == pytest.approx(1200.0)  # 40 x 30 x 1
    assert results["SHCS-M6X16-1"]["overlap_volume"] == pytest.approx(180.0)  # 6 x 6 x 5
    assert results["Spacer-1"]["interferes"] is False  # shares a face only
    assert results["SHCS-M6X16-2"]["interferes"] is False


def test_interference_endpoint_records_check_and_event(team):
    project, designer, reviewer = team
    change = create_change(project, designer)
    r = client_for(reviewer).post(
        url(project, f"changes/{change['id']}/interference/"),
        {"manual_baseline_minutes": 45, "neighbours": ["ORB-1043", "Spacer-1"]}, format="json",
    )
    assert r.status_code == 201, r.content
    body = r.json()
    assert body["changed_part"] == "ORB-1042"  # defaults to the change's first part
    assert body["manual_baseline_minutes"] == 45
    assert body["elapsed_ms"] >= 0
    assert "bounding-box" in body["method"]
    assert [x["interferes"] for x in body["results"]] == [True, False]
    detail = client_for(designer).get(url(project, f"changes/{change['id']}/")).json()
    assert detail["events"][-1]["action"] == "interference_check"
    assert len(detail["interference_checks"]) == 1


def test_interference_with_custom_layout_and_unknown_part(team):
    project, designer, _ = team
    change = create_change(project, designer)
    c = client_for(designer)
    layout = [{"id": "A", "origin": [0, 0, 0], "size": [2, 2, 2]}, {"id": "B", "origin": [1, 1, 1], "size": [2, 2, 2]}]
    r = c.post(url(project, f"changes/{change['id']}/interference/"), {"changed_part": "A", "layout": layout}, format="json")
    assert r.json()["results"][0]["overlap_volume"] == 1.0
    r = c.post(url(project, f"changes/{change['id']}/interference/"), {"changed_part": "NOPE"}, format="json")
    assert r.status_code == 400
