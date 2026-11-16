"""SCRUM-71 call sheets, SCRUM-75 handoff timing, SCRUM-53 part compare."""

from datetime import timedelta
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

import pytest
from django.conf import settings
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.utils import timezone

from bom_agent.models import Bom, BomLineItem, BomResearchRun, BomRow
from bom_agent.research_pipeline import _handle_record_supplier_quote
from part_history import handoff
from part_history.models import HandoffStep, Part, Supplier
from projects.models import Project

SAMPLE_STEP = (Path(settings.BASE_DIR).parent / "samples" / "bracket_assembly.step").read_bytes()


@pytest.fixture
def seeded(user):
    call_command("seed_part_history", user.username)
    return user


@pytest.fixture
def project(user):
    return Project.objects.create(name="New program", owner=user)


@pytest.fixture
def bom(project):
    bom = Bom.objects.create(project=project, source_name="bracket.step", status="needs_review")
    BomRow.objects.create(bom=bom, line_no=1, part_number="ORB-1042", description="Bracket, Mounting",
                          material="6061-T6", process="CNC Machining", quantity=4,
                          sources={"quantity": "STEP NAUO #7"})
    BomRow.objects.create(bom=bom, line_no=2, part_number="ORB-1130", description="Cover", quantity=2)
    return bom


def _upload(client, project):
    upload = SimpleUploadedFile("bracket_assembly.step", SAMPLE_STEP)
    with patch("part_history.views.upload_file_to_s3", return_value="projects/x/b.step"), \
            patch("part_history.views.describe_file.delay"):
        return client.post("/api/parts/quick-estimate/", {"file": upload, "project_id": project.id},
                           format="multipart")


# ── SCRUM-71 call sheet ──────────────────────────────────────────────────────

def test_call_sheet_for_shortlisted_supplier(auth_client, seeded, bom):
    acme = Supplier.objects.get(name="SAMPLE Acme Machining")
    acme.contact_email = "sales@acme.example"
    acme.save()
    row = bom.rows.get(line_no=1)

    data = auth_client.get(f"/api/parts/call-sheet/?row_id={row.id}&supplier_id={acme.id}").json()

    assert data["supplier"]["contact_email"] == "sales@acme.example"
    assert "Bracket, Mounting (ORB-1042) in 6061-T6" in data["part_summary"]
    specs = {s["label"]: s for s in data["specs"]}
    assert specs["Material"]["value"] == "6061-T6"
    assert specs["Quantity per build"] == {"label": "Quantity per build", "value": "4", "source": "STEP NAUO #7"}
    assert specs["Tolerance / spec"]["value"] == "Confirm on call"
    assert data["volume_and_timing"]["last_lead_time_days"] == 12
    assert 5 <= len(data["questions"]) <= 7
    assert any("price breaks" in q for q in data["questions"])


def test_call_sheet_questions_follow_cons_and_missing_contact(auth_client, seeded, bom):
    sheetline = Supplier.objects.get(name="SAMPLE Sheetline Fab")
    row = bom.rows.get(line_no=2)
    data = auth_client.get(f"/api/parts/call-sheet/?row_id={row.id}&supplier_id={sheetline.id}").json()
    assert data["supplier"]["contact_email"] == "Confirm on call"
    assert 5 <= len(data["questions"]) <= 7


def test_call_sheet_rejects_unlisted_supplier_and_other_users(auth_client, api_client, other_user, seeded, bom):
    row = bom.rows.get(line_no=1)
    left_out = Supplier.objects.get(name="SAMPLE Precision Works")  # not approved
    assert auth_client.get(f"/api/parts/call-sheet/?row_id={row.id}&supplier_id={left_out.id}").status_code == 404
    assert auth_client.get("/api/parts/call-sheet/?row_id=x").status_code == 400
    api_client.force_authenticate(other_user)
    acme = Supplier.objects.get(name="SAMPLE Acme Machining")
    assert api_client.get(f"/api/parts/call-sheet/?row_id={row.id}&supplier_id={acme.id}").status_code == 404


# ── SCRUM-75 handoff timing ──────────────────────────────────────────────────

def test_quick_estimate_records_steps_automatically(auth_client, seeded, project):
    bom_id = _upload(auth_client, project).json()["bom"]["id"]
    steps = set(HandoffStep.objects.filter(bom_id=bom_id).values_list("step", flat=True))
    assert {"cad_finished", "bom_shared", "shortlist_ready"} <= steps

    data = auth_client.get(f"/api/parts/handoff/bom/{bom_id}/").json()
    part = data["parts"][0]
    assert part["steps"]["bom_shared"] and part["steps"]["shortlist_ready"]


def test_research_quote_records_quote_received(user, bom, project):
    run = BomResearchRun.objects.create(project=project, created_by=user)
    item = BomLineItem.objects.create(run=run, part_name="Bracket", part_number="ORB-1042")
    _handle_record_supplier_quote(item, run, {"supplier_name": "Acme", "unit_price": Decimal("4"), "moq": 10,
                                              "lead_time_days": 5, "is_avl": True})
    assert HandoffStep.objects.filter(bom=bom, part_number="ORB-1042", step="quote_received").exists()


def test_elapsed_slowest_manual_and_csv(auth_client, bom):
    start = timezone.now() - timedelta(days=10)
    handoff.record(bom, "cad_finished", at=start)
    handoff.record(bom, "bom_shared", at=start + timedelta(hours=2))
    handoff.record(bom, "shortlist_ready", part_number="ORB-1042", at=start + timedelta(hours=4))
    handoff.record(bom, "shortlist_ready", part_number="ORB-1042", at=start + timedelta(days=5))  # first wins

    response = auth_client.post(f"/api/parts/handoff/bom/{bom.id}/",
                                {"step": "quote_received", "date": (start + timedelta(days=3)).date().isoformat(),
                                 "part_number": "ORB-1042"}, format="json")
    assert response.status_code == 200
    part = next(p for p in response.json()["parts"] if p["part_number"] == "ORB-1042")
    assert [i["hours"] for i in part["intervals"]][:2] == [2.0, 2.0]
    assert part["slowest"]["label"] == "Shortlist ready → Quote received"
    assert part["manual"] == ["quote_received"]
    other = next(p for p in response.json()["parts"] if p["part_number"] == "ORB-1130")
    assert other["total_hours"] == 2.0  # inherits the BOM-wide steps
    assert response.json()["slowest_step"]["label"] == "Shortlist ready → Quote received"

    assert auth_client.post(f"/api/parts/handoff/bom/{bom.id}/", {"step": "nope", "date": "2026-01-01"},
                            format="json").status_code == 400
    assert auth_client.post(f"/api/parts/handoff/bom/{bom.id}/", {"step": "quote_accepted", "date": "x"},
                            format="json").status_code == 400

    csv = auth_client.get(f"/api/parts/handoff/bom/{bom.id}/?export=csv")
    assert csv["Content-Type"] == "text/csv"
    lines = csv.content.decode().splitlines()
    assert lines[0].startswith("BOM,Part number,CAD finished")
    assert len(lines) == 3

    summary = auth_client.get("/api/parts/handoff/summary/").json()
    assert summary["parts_timed"] == 2
    assert summary["median_total_hours"] is not None


def test_handoff_scoped_to_owner(api_client, other_user, bom):
    api_client.force_authenticate(other_user)
    assert api_client.get(f"/api/parts/handoff/bom/{bom.id}/").status_code == 404


# ── SCRUM-53 compare ─────────────────────────────────────────────────────────

def test_compare_two_parts_and_row_vs_part(auth_client, seeded, bom):
    old = Part.objects.get(part_number="ORB-1042")
    old.dimensions, old.mass = "120 x 40 x 3 mm", "0.12 kg"
    old.save()
    other = Part.objects.exclude(pk=old.pk).first()

    data = auth_client.get(f"/api/parts/compare/?a={other.id}&b={old.id}").json()
    rows = {r["key"]: r for r in data["rows"]}
    assert rows["dimensions"]["right"] == "120 x 40 x 3 mm"
    assert rows["unit_cost"]["right"].startswith("$")
    assert data["right"]["link"] == f"/api/parts/{old.id}/"
    assert data["right"]["sources"]["unit_cost"]

    row = bom.rows.get(line_no=1)
    data = auth_client.get(f"/api/parts/compare/?row_id={row.id}&b={old.id}").json()
    rows = {r["key"]: r for r in data["rows"]}
    assert rows["part_number"]["same"] and rows["material"]["same"]
    assert data["left"]["link"] == f"/boms/{bom.id}"


def test_compare_validation_and_scope(auth_client, api_client, other_user, seeded):
    part = Part.objects.first()
    assert auth_client.get(f"/api/parts/compare/?b={part.id}").status_code == 400
    assert auth_client.get(f"/api/parts/compare/?a={part.id}&row_id=1&b={part.id}").status_code == 400
    api_client.force_authenticate(other_user)
    assert api_client.get(f"/api/parts/compare/?a={part.id}&b={part.id}").status_code == 404


def test_import_reads_dimensions_and_mass(user):
    from part_history.importer import import_costs

    csv = b"Part Number,Unit Cost,Model Year,Dimensions,Weight\nX-1,2.50,2024,10 x 10 mm,0.2 kg\n"
    import_costs(user, csv, "c.csv")
    part = Part.objects.get(part_number="X-1")
    assert (part.dimensions, part.mass) == ("10 x 10 mm", "0.2 kg")
