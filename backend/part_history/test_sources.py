"""SCRUM-52 — Settings -> Workspace sources and AVL management."""

from part_history.models import ImportBatch, Supplier, WorkspaceSource


def test_add_toggle_and_delete_source(auth_client, user):
    res = auth_client.post(
        "/api/parts/sources/",
        {"kind": "local_folder", "name": "Drawings share", "location": "/mnt/drawings"},
        format="json",
    )
    assert res.status_code == 201
    sid = res.data["id"]
    assert res.data["enabled"] is True

    res = auth_client.patch(f"/api/parts/sources/{sid}/", {"enabled": False}, format="json")
    assert res.status_code == 200
    assert WorkspaceSource.objects.get(pk=sid).enabled is False

    dup = auth_client.post("/api/parts/sources/", {"kind": "local_folder", "name": "Drawings share"}, format="json")
    assert dup.status_code == 400

    assert auth_client.delete(f"/api/parts/sources/{sid}/").status_code == 204
    assert not WorkspaceSource.objects.exists()


def test_rejects_unknown_kind(auth_client):
    res = auth_client.post("/api/parts/sources/", {"kind": "ftp", "name": "x"}, format="json")
    assert res.status_code == 400


def test_overview_lists_imports_and_supplier_counts(auth_client, user):
    ImportBatch.objects.create(workspace_owner=user, filename="costs_2022.xlsx", imported_rows=12)
    Supplier.objects.create(workspace_owner=user, name="Acme", is_approved=True)
    Supplier.objects.create(workspace_owner=user, name="Beta")
    res = auth_client.get("/api/parts/sources/")
    assert res.status_code == 200
    assert res.data["cost_imports"][0]["filename"] == "costs_2022.xlsx"
    assert res.data["supplier_counts"] == {"total": 2, "approved": 1}
    assert any(k["value"] == "google_drive" for k in res.data["kinds"])


def test_approve_and_unapprove_supplier(auth_client, user):
    s = Supplier.objects.create(workspace_owner=user, name="Acme")
    res = auth_client.patch(f"/api/parts/suppliers/{s.id}/", {"is_approved": True, "approval_note": "QA audit 2026"}, format="json")
    assert res.status_code == 200
    s.refresh_from_db()
    assert s.is_approved and s.approval_note == "QA audit 2026"
    assert [x["name"] for x in auth_client.get("/api/parts/suppliers/?approved=true").data] == ["Acme"]
    auth_client.patch(f"/api/parts/suppliers/{s.id}/", {"is_approved": False}, format="json")
    assert auth_client.get("/api/parts/suppliers/?approved=true").data == []


def test_sources_and_suppliers_are_per_user(auth_client, other_user):
    theirs = WorkspaceSource.objects.create(workspace_owner=other_user, kind="google_drive", name="Their Drive")
    their_supplier = Supplier.objects.create(workspace_owner=other_user, name="Secret Co")
    assert auth_client.get("/api/parts/sources/").data["sources"] == []
    assert auth_client.patch(f"/api/parts/sources/{theirs.id}/", {"enabled": False}, format="json").status_code == 404
    assert auth_client.delete(f"/api/parts/sources/{theirs.id}/").status_code == 404
    assert auth_client.get("/api/parts/suppliers/").data == []
    assert auth_client.patch(f"/api/parts/suppliers/{their_supplier.id}/", {"is_approved": True}, format="json").status_code == 404
