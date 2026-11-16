"""SCRUM-61 lead-time bottleneck and SCRUM-60 cost-reduction suggestions."""

from datetime import date
from types import SimpleNamespace

import pytest
from django.core.management import call_command

from bom_agent.models import Bom, BomRow
from part_history.cost_reduction import find_cost_reduction
from part_history.lead_time import lead_time_row, mark_bottleneck
from part_history.models import HistoricalCost, Part, Quote, Supplier
from part_history.quick_estimate import quick_report
from projects.models import Project


@pytest.fixture
def seeded(user):
    call_command("seed_part_history", user.username)
    return user


def row(**kw):
    return SimpleNamespace(**{"id": 1, "part_number": "", "description": "", "material": "", "process": "",
                              "quantity": 1, "spec": "", "sources": {}, **kw})


# ── SCRUM-61 ────────────────────────────────────────────────────────────────

def test_lead_time_sources(seeded):
    exact = lead_time_row(seeded, row(part_number="ORB-1042"))
    assert exact["days"] == 16 and exact["basis"] == "quote_history"  # median of 12 and 21
    assert len(exact["evidence"]) == 2 and all(e["source"] for e in exact["evidence"])

    similar = lead_time_row(seeded, row(part_number="ORB-1131"), ["ORB-1130"])
    assert similar["days"] == 9 and similar["basis"] == "similar_parts" and "ORB-1130" in similar["source"]

    none = lead_time_row(seeded, row(part_number="XYZ"))
    assert none == {"days": None, "basis": "no_data", "source": "No quoted lead time for this part or similar parts",
                    "evidence": [], "is_bottleneck": False}


def test_mark_bottleneck():
    rows = [{"row_id": i, "line_no": i, "part_number": pn, "description": "", "lead_time": {"days": d, "source": "s",
             "is_bottleneck": False}} for i, (pn, d) in enumerate([("A", 3), ("B", 21), ("C", None)])]
    cp = mark_bottleneck(rows)
    assert cp["summary"] == "Critical path: B, 21 days" and cp["rows_without_data"] == 1
    assert [r["lead_time"]["is_bottleneck"] for r in rows] == [False, True, False]
    assert mark_bottleneck(rows[2:]) is None


def test_quick_report_includes_lead_times(seeded):
    project = Project.objects.create(name="P", owner=seeded)
    bom = Bom.objects.create(project=project)
    BomRow.objects.create(bom=bom, line_no=1, part_number="ORB-1042", description="Bracket, Mounting", material="6061-T6")
    BomRow.objects.create(bom=bom, line_no=2, part_number="SHCS-M6X16", description="Screw SHCS M6x16", quantity=4)
    report = quick_report(bom, seeded)
    assert report["critical_path"]["summary"] == "Critical path: ORB-1042, 16 days"
    assert [r["lead_time"]["is_bottleneck"] for r in report["rows"]] == [True, False]


# ── SCRUM-60 ────────────────────────────────────────────────────────────────

@pytest.fixture
def history(user):
    acme = Supplier.objects.create(workspace_owner=user, name="Acme", is_approved=True)
    cheap = Supplier.objects.create(workspace_owner=user, name="Cheapo")
    bracket = Part.objects.create(workspace_owner=user, part_number="BR-100", description="Bracket mounting",
                                  material="7075-T6")
    alt = Part.objects.create(workspace_owner=user, part_number="BR-200", description="Bracket mounting short",
                              material="6061-T6")
    HistoricalCost.objects.create(workspace_owner=user, part=bracket, unit_cost="10.00", model_year=date.today().year,
                                  source="costs.xlsx row 2")
    HistoricalCost.objects.create(workspace_owner=user, part=alt, unit_cost="6.00", model_year=date.today().year,
                                  source="costs.xlsx row 3")
    Quote.objects.create(workspace_owner=user, supplier=acme, part=bracket, unit_price="10.00", quantity=10,
                         tolerance="±0.005", source="RFQ-1")
    Quote.objects.create(workspace_owner=user, supplier=acme, part=bracket, unit_price="8.50", quantity=500,
                         source="RFQ-2")
    Quote.objects.create(workspace_owner=user, supplier=cheap, part=bracket, unit_price="9.00", quantity=10,
                         source="RFQ-3")
    return user


def test_cost_reduction_ranked_and_cited(history, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    result = find_cost_reduction(history, row(part_number="BR-100", description="Bracket mounting",
                                              material="7075-T6", quantity=10))
    assert result["baseline"]["unit_cost"] == "10.00"
    kinds = [s["kind"] for s in result["suggestions"]]
    assert kinds == ["material", "volume", "supplier", "tolerance"]
    material = result["suggestions"][0]
    assert material["rank"] == 1 and material["estimated_saving_pct"] == 0.4 and material["meets_target"]
    assert material["estimated_saving_per_unit"] == "4.00"
    assert material["evidence"][0]["source"] == "costs.xlsx row 3"
    assert "not on the approved vendor list" in result["suggestions"][2]["rationale"]
    assert result["suggestions"][3]["assumption"]
    assert all(e["source"] for s in result["suggestions"] for e in s["evidence"])
    assert result["target_met"] and result["questions"] == []
    assert "not a should-cost model" in result["disclaimer"]


def test_cost_reduction_fasteners_and_cots(seeded, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    screws = find_cost_reduction(seeded, row(part_number="SHCS-M6X16", description="Screw SHCS M6x16", quantity=8))
    assert "fastener_count" in [s["kind"] for s in screws["suggestions"]]
    custom = find_cost_reduction(seeded, row(part_number="ORB-9", description="Retainer pin, ISO style", quantity=1))
    assert custom["suggestions"][0]["kind"] == "cots"


def test_cost_reduction_with_no_data(user):
    result = find_cost_reduction(user, row(part_number="NOPE"))
    assert result["suggestions"] == [] and result["baseline"]["unit_cost"] is None and not result["target_met"]


def test_claude_failure_is_ignored(history, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "x")

    def boom():
        raise RuntimeError("no network in tests")

    monkeypatch.setattr("bom_agent.team_requests._client", boom)
    result = find_cost_reduction(history, row(part_number="BR-100", description="Bracket mounting", material="7075-T6"))
    assert result["questions"] == [] and result["suggestions"]


def test_cost_reduction_endpoint(auth_client, api_client, other_user, history):
    project = Project.objects.create(name="P", owner=history)
    bom = Bom.objects.create(project=project)
    r = BomRow.objects.create(bom=bom, line_no=1, part_number="BR-100", description="Bracket mounting",
                              material="7075-T6", quantity=10)
    res = auth_client.get(f"/api/parts/cost-reduction/{r.id}/?target=0.1")
    assert res.status_code == 200 and res.json()["suggestions"][0]["kind"] == "material"
    assert auth_client.get(f"/api/parts/cost-reduction/{r.id}/?target=x").status_code == 400
    api_client.force_authenticate(other_user)
    assert api_client.get(f"/api/parts/cost-reduction/{r.id}/").status_code == 404
