"""SCRUM-23 (version compare + conflict flags) and SCRUM-55 (affected neighbours)."""

from pathlib import Path
from unittest.mock import patch

import pytest
from django.conf import settings

from bom_agent.bom_extraction import extract_bom_rows
from bom_agent.design_change import assembly_occurrences, diff_rows, find_conflicts, neighbours
from bom_agent.models import Bom, BomRow
from bom_agent.tasks import build_bom
from files_api.models import UploadedFile
from projects.models import Project

SAMPLES = Path(settings.BASE_DIR).parent / "samples"
REV_A = (SAMPLES / "bracket_assembly.step").read_bytes()
REV_B = (SAMPLES / "bracket_assembly_rev_b.step").read_bytes()


def rows(data, bom_id, name):
    return [{**r, "id": n, "line_no": n, "bom": {"bom_id": bom_id, "reference": f"BOM-{bom_id}", "source_name": name}}
            for n, r in enumerate(extract_bom_rows(data, "step"), start=1)]


def row(bom_id, pn, **kw):
    return {"part_number": pn, "description": "", "material": "", "process": "", "quantity": 1, "spec": "",
            "revision": "", "line_no": 1, **kw, "bom": {"bom_id": bom_id, "reference": f"BOM-{bom_id}", "source_name": f"f{bom_id}"}}


# ── SCRUM-23 ─────────────────────────────────────────────────────────────────

def test_step_revision_is_read_from_the_formation():
    by_pn = {r["part_number"]: r for r in extract_bom_rows(REV_B, "step")}
    assert by_pn["ORB-1042"]["revision"] == "B"
    assert by_pn["ORB-1042"]["sources"]["revision"].startswith("STEP PRODUCT_DEFINITION_FORMATION")


def test_diff_lists_added_removed_and_changed_fields():
    diff = diff_rows(rows(REV_A, 1, "a.step"), rows(REV_B, 2, "b.step"))

    assert {a["part_number"] for a in diff["added"]} == {"ORB-1044", "ORB-1050"}
    assert [r["part_number"] for r in diff["removed"]] == ["Part1"]
    bracket = next(c for c in diff["changed"] if c["part_number"] == "ORB-1042")
    fields = {f["field"]: (f["before"], f["after"]) for f in bracket["fields"]}
    assert fields["material"] == ("6061-T6", "7075-T6")
    assert fields["revision"] == ("", "B")
    assert [c["bom_id"] for c in bracket["rows"]] == [1, 2]
    assert diff["summary"] == "2 added, 1 removed, 2 changed, 1 unchanged"


def test_conflicts_flag_mismatches_and_cite_rows():
    flags = find_conflicts([
        row(1, "ORB-1042", description="Bracket, Mounting", material="6061-T6", revision="A", spec="±0.05"),
        row(2, "orb 1042", description="Bracket, Mounting", material="7075-T6", revision="B", spec="±0.10", line_no=7),
        row(2, "ORB-2000", description="Hinge Pin"),
        row(3, "ORB-2001", description="Hinge Pin"),
        row(3, "ORB-3000", material="ABS"), row(1, "ORB-3000"),  # silence is not a contradiction
    ])
    kinds = sorted(f["kind"] for f in flags)
    assert kinds == ["material", "part_number", "part_number", "revision", "tolerance"]
    material = next(f for f in flags if f["kind"] == "material")
    assert material["detail"] == "ORB-1042: 6061-T6 vs 7075-T6"
    assert {(c["bom_id"], c["line_no"]) for c in material["citations"]} == {(1, 1), (2, 7)}
    assert any("Hinge Pin" in f["detail"] for f in flags)


def test_no_conflict_within_a_single_file():
    assert find_conflicts([row(1, "X-1", material="ABS"), row(1, "X-1", material="PA66")]) == []


# ── SCRUM-55 ─────────────────────────────────────────────────────────────────

def test_occurrences_carry_positions_from_step_placements():
    occs = assembly_occurrences(REV_B)
    assert len(occs) == 8
    cover = next(o for o in occs if o["part_number"] == "ORB-1043")
    assert cover["position"] == (0.0, 0.0, 12.0) and cover["parent"] == "ORB-1000"


def test_neighbours_by_distance():
    result = neighbours(REV_B, "ORB-1042", radius=40)
    assert result["method"] == "placement_distance"
    assert [p["part_number"] for p in result["parts"]] == ["ORB-1043", "SHCS-M6X16", "ORB-1044"]
    assert result["parts"][0]["distance"] == 12.0  # the far-away clip at x=220 is not listed


def test_neighbours_fall_back_to_assembly_structure_without_positions():
    result = neighbours(REV_A, "ORB-1042", radius=40)
    assert result["method"] == "assembly_structure"
    assert {p["part_number"] for p in result["parts"]} == {"ORB-1043", "SHCS-M6X16", "Part1"}


def test_neighbours_for_unknown_part():
    assert neighbours(REV_B, "NOPE", 10)["method"] == "not_in_assembly"


# ── API ──────────────────────────────────────────────────────────────────────

@pytest.fixture
def two_versions(db, user):
    project = Project.objects.create(name="Change review", owner=user)

    def make(name, data):
        f = UploadedFile.objects.create(project=project, uploaded_by=user, original_name=name, file_type="step",
                                        s3_key=f"projects/x/{name}", file_size=len(data))
        return build_bom(f, data)

    return make("bracket_assembly.step", REV_A), make("bracket_assembly_rev_b.step", REV_B)


def test_compare_endpoint(auth_client, two_versions):
    a, b = two_versions
    with patch("files_api.s3_service.download_file_from_s3", return_value=REV_B) as download:
        res = auth_client.get(f"/api/bom/structured/compare/?base={a.pk}&target={b.pk}&radius=40")
    assert res.status_code == 200
    body = res.json()
    download.assert_called_once_with(b.source_file.s3_key)
    assert body["assembly"]["bom_id"] == b.pk
    assert {c["part_number"] for c in body["changed"]} >= {"ORB-1042"}
    material = next(f for f in body["conflicts"] if f["kind"] == "material")
    assert {c["source_name"] for c in material["citations"]} == {"bracket_assembly.step", "bracket_assembly_rev_b.step"}
    assert body["recheck"]["ORB-1042"]["method"] == "placement_distance"
    assert "ORB-1050" in body["recheck"]  # added parts get neighbours too


def test_compare_requires_ids_and_ownership(auth_client, api_client, other_user, two_versions):
    a, b = two_versions
    assert auth_client.get("/api/bom/structured/compare/?base=x").status_code == 400
    api_client.force_authenticate(other_user)
    assert api_client.get(f"/api/bom/structured/compare/?base={a.pk}&target={b.pk}").status_code == 404


def test_revision_is_editable(auth_client, two_versions):
    a, _ = two_versions
    r = a.rows.first()
    res = auth_client.patch(f"/api/bom/structured/{a.pk}/rows/{r.pk}/", {"revision": "C"}, format="json")
    assert res.status_code == 200 and BomRow.objects.get(pk=r.pk).revision == "C"
