"""SCRUM-59 — early estimates from the closest prior-program parts."""

from pathlib import Path
from types import SimpleNamespace

import pytest
from django.conf import settings
from django.core.management import call_command

from bom_agent.tasks import build_bom
from files_api.models import UploadedFile
from part_history.estimator import estimate_bom, estimate_row, similarity
from part_history.models import HistoricalCost, Part
from projects.models import Project

SAMPLE_STEP = (Path(settings.BASE_DIR).parent / "samples" / "bracket_assembly.step").read_bytes()
YEAR = 2026


def line(**kw):
    defaults = {"part_number": "", "description": "", "material": "", "process": "", "quantity": 1, "sources": {}}
    return SimpleNamespace(**{**defaults, **kw})


@pytest.fixture
def seeded(user):
    call_command("seed_part_history", user.username)
    return user


@pytest.fixture
def bom(user):
    project = Project.objects.create(name="New program", owner=user)
    file = UploadedFile.objects.create(
        project=project, uploaded_by=user, original_name="bracket_assembly.step",
        file_type="step", s3_key="k", file_size=1,
    )
    return build_bom(file, SAMPLE_STEP)


def test_same_part_number_uses_its_own_latest_cost_inflated(seeded):
    result = estimate_row(seeded, line(part_number="orb-1042", quantity=3), year=YEAR)

    assert result["confidence"] == "high"
    assert result["matches"][0]["reasons"] == ["Same part number"]
    # $4.35 in 2024, 3%/yr for 2 years = 4.6149
    assert result["estimate"] == {
        "unit_cost": "4.61", "quantity": 3, "extended_cost": "13.84", "currency": "USD", "based_on": ["ORB-1042"],
    }
    assert result["matches"][0]["cost"]["source"] == "part_cost_history_sample.csv row 3"


def test_similar_parts_come_with_reasons(seeded):
    result = estimate_row(
        seeded, line(part_number="ORB-1043", description="Cover Plate 16 GA", process="sheet metal"), year=YEAR
    )

    assert [m["part_number"] for m in result["matches"]] == ["ORB-1130", "ORB-1131"]
    assert result["matches"][0]["reasons"] == ["Same process (sheet metal)", "Description shares: cover, plate"]
    # (2.10 × 1.03³ + 2.40 × 1.03⁴) / 2
    assert result["estimate"]["unit_cost"] == "2.50"
    assert result["confidence"] == "medium"
    assert "Similarity-weighted average of 2 similar parts" in result["assumptions"]


def test_assumptions_are_visible_and_sample_data_is_flagged(seeded):
    result = estimate_row(seeded, line(part_number="ORB-1042", sources={"quantity": "STEP assembly structure"}), year=YEAR)
    assert result["assumptions"] == [
        "Inflation 3.0% a year, compounded from each cost's model year to 2026",
        "Same part number: uses ORB-1042's latest cost only",
        "Quantity 1 from STEP assembly structure",
        "⚠ Based on SAMPLE data, not real costs",
    ]
    assert result["uses_sample_data"] is True


def test_no_similar_part_gives_no_estimate(seeded):
    result = estimate_row(seeded, line(part_number="XYZ-1", description="Gearbox"), year=YEAR)
    assert (result["estimate"], result["confidence"], result["matches"]) == (None, "none", [])
    assert "No similar historical parts" in result["assumptions"][0]


def test_k_limits_matches(seeded):
    result = estimate_row(seeded, line(description="Bracket", material="6061-T6"), k=2, year=YEAR)
    assert len(result["matches"]) == 2


def test_inflation_is_configurable(seeded):
    flat = estimate_row(seeded, line(part_number="ORB-1042"), inflation=0, year=YEAR)
    assert flat["estimate"]["unit_cost"] == "4.35"


def test_cost_without_model_year_is_not_adjusted(user):
    part = Part.objects.create(workspace_owner=user, part_number="P-1", description="Widget")
    HistoricalCost.objects.create(workspace_owner=user, part=part, unit_cost=10, program="Old", source="s")
    result = estimate_row(user, line(part_number="P-1"), year=YEAR)
    assert result["estimate"]["unit_cost"] == "10.00"
    assert "No model year on P-1's cost, so it isn't inflation-adjusted" in result["assumptions"]


def test_similarity_material_family():
    part = Part(part_number="X", description="Block", material="7075-T6")
    score, reasons = similarity(line(material="6061-T6"), part)
    assert (score, reasons) == (0.15, ["Same material family (aluminum)"])


def test_estimate_whole_bom(seeded, bom):
    result = estimate_bom(bom, seeded, year=YEAR)

    by_pn = {r["part_number"]: r for r in result["rows"]}
    assert by_pn["SHCS-M6X16"]["estimate"]["extended_cost"] == "0.81"  # 4 × 0.18 × 1.03⁴
    assert by_pn["Part1"]["estimate"]["extended_cost"] == "2.25"  # 2 spacers, matched on description
    assert result["total"] == {
        "extended_cost": "10.17", "currency": "USD", "rows_estimated": 4, "rows_without_estimate": 0,
    }
    assert result["uses_sample_data"] is True


def test_estimate_api(auth_client, seeded, bom):
    data = auth_client.get(f"/api/parts/estimate/bom/{bom.pk}/?k=2&inflation=0").json()
    assert data["reference"] == bom.reference
    assert data["inflation"] == 0
    assert all(len(r["matches"]) <= 2 for r in data["rows"])


@pytest.mark.parametrize("query", ["k=0", "k=abc", "inflation=2", "inflation=x"])
def test_estimate_api_rejects_bad_parameters(auth_client, bom, query):
    assert auth_client.get(f"/api/parts/estimate/bom/{bom.pk}/?{query}").status_code == 400


def test_estimate_api_is_private(api_client, other_user, bom):
    api_client.force_authenticate(other_user)
    assert api_client.get(f"/api/parts/estimate/bom/{bom.pk}/").status_code == 404
