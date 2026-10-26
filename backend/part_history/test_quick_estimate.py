"""Thin slice — drop a STEP/PDF in, get BOM + estimate + approved-supplier shortlist."""

import time
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from django.conf import settings
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command

from bom_agent.models import Bom
from part_history.models import Quote, Supplier
from part_history.shortlist import shortlist_row
from projects.models import Project

SAMPLE_STEP = (Path(settings.BASE_DIR).parent / "samples" / "bracket_assembly.step").read_bytes()


@pytest.fixture
def seeded(user):
    call_command("seed_part_history", user.username)
    return user


@pytest.fixture
def project(user):
    return Project.objects.create(name="New program", owner=user)


def row(**kw):
    return SimpleNamespace(**{"part_number": "", "material": "", **kw})


def test_seed_marks_sample_avl_and_adds_quotes(seeded):
    assert Supplier.objects.filter(is_approved=True).count() == 4
    assert not Supplier.objects.get(name="SAMPLE Precision Works").is_approved
    assert Quote.objects.count() == 4
    call_command("seed_part_history", seeded.username)  # repeatable
    assert Quote.objects.count() == 4


def test_shortlist_ranks_approved_suppliers_with_evidence(seeded):
    result = shortlist_row(seeded, row(part_number="ORB-1042", material="6061-T6"))

    names = [s["supplier"] for s in result["suppliers"]]
    assert names[0] == "SAMPLE Acme Machining"  # quoted and supplied this exact part
    assert "SAMPLE Precision Works" not in names  # cheaper, but not approved
    assert result["non_approved_left_out"] == 1
    acme = result["suppliers"][0]
    assert acme["best_quote"] == {"unit_price": "4.20", "lead_time_days": 12, "source": "SAMPLE seed data"}
    assert all(e["source"] for e in acme["evidence"])
    assert any("Supplied this part for SAMPLE Program Atlas 2022" in e["text"] for e in acme["evidence"])


def test_shortlist_uses_similar_parts(seeded):
    result = shortlist_row(seeded, row(part_number="ORB-1043"), ["ORB-1130"])
    assert [s["supplier"] for s in result["suppliers"]] == ["SAMPLE Sheetline Fab"]
    assert "similar part ORB-1130" in result["suppliers"][0]["evidence"][0]["text"]


def test_shortlist_empty_when_nobody_fits(seeded):
    assert shortlist_row(seeded, row(part_number="XYZ")) == {"suppliers": [], "non_approved_left_out": 0}


def _post(client, project, name="bracket_assembly.step", data=SAMPLE_STEP):
    upload = SimpleUploadedFile(name, data)
    with patch("part_history.views.upload_file_to_s3", return_value=f"projects/x/{name}"), \
            patch("part_history.views.describe_file.delay"):
        return client.post(
            "/api/parts/quick-estimate/", {"file": upload, "project_id": project.id}, format="multipart"
        )


def test_end_to_end_upload_to_estimate_and_shortlist(auth_client, seeded, project):
    started = time.monotonic()
    response = _post(auth_client, project)
    elapsed = time.monotonic() - started

    assert response.status_code == 201
    report = response.json()
    assert elapsed < 120 and report["elapsed_ms"] < 120_000  # AC: under 2 minutes
    assert report["bom"]["reference"] == Bom.objects.get().reference
    assert report["uses_sample_data"] is True

    by_pn = {r["part_number"]: r for r in report["rows"]}
    assert set(by_pn) == {"ORB-1042", "ORB-1043", "SHCS-M6X16", "Part1"}
    bracket = by_pn["ORB-1042"]
    # Every number shows its source
    assert bracket["row"]["sources"]["quantity"].startswith("STEP assembly structure")
    assert bracket["matches"][0]["cost"]["source"].startswith("part_cost_history_sample.csv row")
    assert bracket["shortlist"]["suppliers"][0]["best_quote"]["source"] == "SAMPLE seed data"
    assert bracket["estimate"]["unit_cost"]
    assert by_pn["SHCS-M6X16"]["shortlist"]["suppliers"][0]["supplier"] == "SAMPLE Fastenal Demo"


def test_report_for_an_existing_bom(auth_client, seeded, project):
    bom_id = _post(auth_client, project).json()["bom"]["id"]
    data = auth_client.get(f"/api/parts/quick-estimate/{bom_id}/").json()
    assert len(data["rows"]) == 4


def test_pdf_works_too(auth_client, seeded, project):
    from bom_agent.test_structured_bom import make_pdf

    pdf = make_pdf([(400, 100, "TITLE: BRACKET, MOUNTING"), (400, 86, "PART NO: ORB-1042"), (400, 72, "MATERIAL: 6061-T6")])
    report = _post(auth_client, project, "bracket.pdf", pdf).json()
    assert [r["part_number"] for r in report["rows"]] == ["ORB-1042"]
    assert report["bom"]["review_count"] == 1  # quantity was assumed from a title block


@pytest.mark.parametrize("name", ["drawing.dwg", "notes.txt"])
def test_rejects_unsupported_files(auth_client, project, name):
    assert _post(auth_client, project, name, b"x").status_code == 400


def test_project_must_belong_to_user(api_client, other_user, project):
    api_client.force_authenticate(other_user)
    assert _post(api_client, project).status_code == 404
