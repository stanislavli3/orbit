"""SCRUM-31 (explicit COTS status) and SCRUM-32 (RFQ spec sheets)."""

from importlib import import_module

import pytest
from django.apps import apps as django_apps

from bom_agent.models import Bom, BomLineItem, BomResearchRun, BomRow, RfqDraft, SupplierQuote
from bom_agent.research_pipeline import _handle_record_supplier_quote
from projects.models import Project


@pytest.fixture
def project(db, user):
    return Project.objects.create(name="P", owner=user)


@pytest.fixture
def item(project, user):
    run = BomResearchRun.objects.create(project=project, created_by=user)
    return BomLineItem.objects.create(run=run, part_name="Bracket")


def make_quote(item, **kw):
    defaults = dict(supplier_name="Acme", unit_price="1.00", moq=1, lead_time_days=5)
    return SupplierQuote.objects.create(line_item=item, **{**defaults, **kw})


# ── SCRUM-31 ─────────────────────────────────────────────────────────────────

def test_backfill_uses_tooling_cost_and_marks_quotes_inferred(item):
    commodity = make_quote(item, tooling_cost=0, is_cots=False)
    machined = make_quote(item, tooling_cost=250, is_cots=True)
    migration = import_module("bom_agent.migrations.0012_supplierquote_is_cots_and_rfq_draft")
    migration.backfill_cots(django_apps, None)

    commodity.refresh_from_db()
    machined.refresh_from_db()
    assert (commodity.is_cots, commodity.is_cots_source) == (True, "backfill")
    assert (machined.is_cots, machined.is_cots_source) == (False, "backfill")


def test_agent_sets_cots_explicitly_even_with_tooling_cost(item):
    inputs = dict(supplier_name="Fastenal", unit_price=0.1, moq=100, lead_time_days=3,
                  tooling_cost=50, landed_cost_usd=0.12, is_avl=True, is_cots=True, country="USA")
    _handle_record_supplier_quote(item, item.run, inputs)
    quote = item.quotes.get()
    assert (quote.is_cots, quote.is_cots_source) == (True, "agent")


def test_human_override_via_patch(auth_client, item):
    quote = make_quote(item, tooling_cost=0, is_cots=True)
    response = auth_client.patch(f"/api/bom/quotes/{quote.pk}/", {"is_cots": False}, format="json")
    assert response.status_code == 200
    assert response.json()["is_cots"] is False and response.json()["is_cots_source"] == "human"
    # The source can't be forged by the client.
    auth_client.patch(f"/api/bom/quotes/{quote.pk}/", {"is_cots_source": "agent"}, format="json")
    quote.refresh_from_db()
    assert quote.is_cots_source == "human"


def test_other_users_cannot_override_quotes(api_client, other_user, item):
    quote = make_quote(item)
    api_client.force_authenticate(other_user)
    assert api_client.patch(f"/api/bom/quotes/{quote.pk}/", {"is_cots": True}, format="json").status_code == 404


# ── SCRUM-32 ─────────────────────────────────────────────────────────────────

@pytest.fixture
def row(project):
    bom = Bom.objects.create(project=project, status="approved")
    return BomRow.objects.create(bom=bom, line_no=1, part_number="ORB-1042",
                                 description="Mounting bracket", material="6061-T6",
                                 process="machined", quantity=4)


def test_draft_rfq_copies_row_and_flags_missing_fields(auth_client, row):
    response = auth_client.post(f"/api/bom/structured/{row.bom_id}/rows/{row.pk}/rfq/")
    assert response.status_code == 201
    data = response.json()
    assert data["status"] == "draft"
    assert (data["part_number"], data["material"], data["quantity"]) == ("ORB-1042", "6061-T6", 4)
    assert data["part_context"] == "Mounting bracket"
    # Never invented: blank size, tolerance and due date become explicit assumptions.
    assert data["tolerance"] == "" and data["due_date"] is None
    assumptions = " ".join(data["assumptions"])
    for label in ("Blank / stock size", "Tolerance", "Quote due date"):
        assert label in assumptions
    assert "Material" not in assumptions
    assert all("assumption — confirm" in a for a in data["assumptions"])


def test_rfq_is_editable_and_exports_printable_html(auth_client, row):
    rfq_id = auth_client.post(f"/api/bom/structured/{row.bom_id}/rows/{row.pk}/rfq/").json()["id"]
    response = auth_client.patch(f"/api/bom/rfqs/{rfq_id}/", {
        "tolerance": "±0.05 mm", "blank_size": "50 x 30 x 10 mm", "due_date": "2026-12-01",
    }, format="json")
    assert response.status_code == 200
    assert response.json()["assumptions"] == []

    html = auth_client.get(f"/api/bom/rfqs/{rfq_id}/export/")
    assert html.status_code == 200 and html["Content-Type"].startswith("text/html")
    body = html.content.decode()
    assert "±0.05 mm" in body and "6061-T6" in body and "2026" in body
    assert "Assumption — confirm" not in body


def test_export_marks_missing_fields(auth_client, row):
    rfq = RfqDraft.objects.create(bom_row=row, created_by=row.bom.project.owner, part_number="X")
    body = auth_client.get(f"/api/bom/rfqs/{rfq.pk}/export/").content.decode()
    assert "Assumption — confirm" in body and "Tolerance: not stated" in body


def test_other_users_cannot_draft_or_read_rfqs(api_client, other_user, row, user):
    rfq = RfqDraft.objects.create(bom_row=row, created_by=user)
    api_client.force_authenticate(other_user)
    assert api_client.post(f"/api/bom/structured/{row.bom_id}/rows/{row.pk}/rfq/").status_code == 404
    assert api_client.get(f"/api/bom/rfqs/{rfq.pk}/").status_code == 404
