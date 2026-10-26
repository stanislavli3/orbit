"""SCRUM-28 — part, price, supplier and quote history across programs."""

from decimal import Decimal
from pathlib import Path

import pytest
from django.conf import settings

from bom_agent.models import BomLineItem, BomResearchRun
from bom_agent.research_pipeline import _handle_record_supplier_quote
from bom_agent.tasks import build_bom
from files_api.models import UploadedFile
from part_history.history import suppliers_who_quoted
from part_history.models import HistoricalCost, Part, Quote, Supplier
from projects.models import Project

SAMPLE_STEP = (Path(settings.BASE_DIR).parent / "samples" / "bracket_assembly.step").read_bytes()


@pytest.fixture
def project(db, user):
    return Project.objects.create(name="Program A", owner=user)


def _research_quote(project, user, *, part_number="ORB-1042", supplier="Acme Machining", price="4.10", is_avl=True):
    run = BomResearchRun.objects.create(project=project, created_by=user)
    item = BomLineItem.objects.create(
        run=run, part_name="Bracket, Mounting", part_number=part_number, material_spec="6061-T6"
    )
    _handle_record_supplier_quote(
        item, run,
        {"supplier_name": supplier, "unit_price": Decimal(price), "moq": 100, "lead_time_days": 12, "is_avl": is_avl},
    )
    return run


def test_research_quote_is_kept_in_history(project, user):
    run = _research_quote(project, user)

    quote = Quote.objects.get()
    assert quote.supplier.name == "Acme Machining"
    assert quote.supplier.is_approved is True
    assert quote.part.part_number == "ORB-1042"
    assert (quote.material, quote.unit_price, quote.lead_time_days) == ("6061-T6", Decimal("4.1000"), 12)
    assert (quote.program, quote.source) == ("Program A", f"BOM research run #{run.pk}")


def test_history_accumulates_across_runs_and_programs(project, user):
    _research_quote(project, user, price="4.10")
    other_program = Project.objects.create(name="Program B", owner=user)
    _research_quote(other_program, user, price="3.95")

    assert Supplier.objects.count() == 1 and Part.objects.count() == 1
    [entry] = suppliers_who_quoted(user, part_number="orb-1042")
    assert [(q["unit_price"], q["source"].startswith("BOM research run #")) for q in entry["quotes"]] == [
        ("3.9500", True), ("4.1000", True),  # newest first
    ]


def test_history_failure_does_not_stop_research(project, user, monkeypatch):
    def boom(_):
        raise RuntimeError("db down")

    monkeypatch.setattr("part_history.history.record_research_quote", boom)
    run = _research_quote(project, user)
    assert run.line_items.get().quotes.count() == 1
    run.refresh_from_db()
    assert any("price history" in e["message"] for e in run.research_log)


def test_who_quoted_filters_material_tolerance_and_certification(user):
    acme = Supplier.objects.create(workspace_owner=user, name="Acme", certifications="ISO 9001, AS9100")
    bolt = Supplier.objects.create(workspace_owner=user, name="BoltCo")
    common = {"workspace_owner": user, "unit_price": 5, "source": "test"}
    Quote.objects.create(supplier=acme, material="6061-T6", tolerance="±0.05 mm", **common)
    Quote.objects.create(supplier=bolt, material="6061-T6", tolerance="±0.2 mm", **common)
    Quote.objects.create(supplier=bolt, material="SS 304", certifications="AS9100", **common)

    names = lambda **kw: [e["supplier"] for e in suppliers_who_quoted(user, **kw)]  # noqa: E731
    assert names(material="6061") == ["Acme", "BoltCo"]
    assert names(material="6061", tolerance="0.05") == ["Acme"]
    assert names(certification="as9100") == ["Acme", "BoltCo"]  # supplier-level or quote-level
    assert names(material="6061", certification="AS9100") == ["Acme"]


def test_approving_a_bom_adds_its_parts_without_overwriting(auth_client, project, user):
    Part.objects.create(workspace_owner=user, part_number="ORB-1042", description="Bracket v1 (from 2022 program)")
    file = UploadedFile.objects.create(
        project=project, uploaded_by=user, original_name="a.step", file_type="step", s3_key="k", file_size=1
    )
    bom = build_bom(file, SAMPLE_STEP)

    assert auth_client.post(f"/api/bom/structured/{bom.pk}/approve/").status_code == 200
    assert set(Part.objects.values_list("part_number", flat=True)) == {"ORB-1042", "ORB-1043", "SHCS-M6X16", "Part1"}
    bracket = Part.objects.get(part_number="ORB-1042")
    assert bracket.description == "Bracket v1 (from 2022 program)"
    assert bracket.material == "6061-T6"  # blank before, filled in


# ── API ──────────────────────────────────────────────────────────────────────

@pytest.fixture
def bracket(user):
    part = Part.objects.create(workspace_owner=user, part_number="ORB-1042", description="Bracket, Mounting")
    HistoricalCost.objects.create(workspace_owner=user, part=part, unit_cost=4, program="P21", model_year=2021, source="a.csv row 2")
    HistoricalCost.objects.create(workspace_owner=user, part=part, unit_cost=5, program="P23", model_year=2023, source="a.csv row 3")
    return part


def test_part_list_shows_latest_cost(auth_client, bracket):
    [row] = auth_client.get("/api/parts/?q=bracket").json()
    assert row["latest_cost"]["model_year"] == 2023
    assert row["latest_cost"]["source"] == "a.csv row 3"
    assert auth_client.get("/api/parts/?q=nothing").json() == []


def test_part_detail(auth_client, bracket):
    data = auth_client.get(f"/api/parts/{bracket.pk}/").json()
    assert [c["model_year"] for c in data["costs"]] == [2023, 2021]
    assert data["quotes"] == []


def test_who_quoted_api(auth_client, project, user):
    _research_quote(project, user)
    data = auth_client.get("/api/parts/suppliers/who-quoted/?material=6061").json()
    assert data[0]["supplier"] == "Acme Machining"
    assert data[0]["quotes"][0]["part_number"] == "ORB-1042"


def test_history_is_private_to_its_workspace(api_client, other_user, bracket):
    api_client.force_authenticate(other_user)
    assert api_client.get("/api/parts/").json() == []
    assert api_client.get(f"/api/parts/{bracket.pk}/").status_code == 404
