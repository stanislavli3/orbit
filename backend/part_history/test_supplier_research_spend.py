"""SCRUM-70 unverified supplier research + SCRUM-72 supplier spend import."""

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from django.conf import settings
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command

from bom_agent.models import Bom, BomRow
from part_history.lead_time import lead_time_row
from part_history.models import HistoricalCost, ImportBatch, Quote, Supplier, SupplierResearch
from part_history.shortlist import shortlist_row
from projects.models import Project

SPEND = (Path(settings.BASE_DIR).parent / "samples" / "supplier_spend_sample.csv").read_bytes()


@pytest.fixture
def bom_row(user):
    project = Project.objects.create(name="P", owner=user)
    bom = Bom.objects.create(project=project)
    return BomRow.objects.create(bom=bom, line_no=1, part_number="ORB-1042", material="6061-T6")


def _upload(client, dry_run):
    f = SimpleUploadedFile("spend.csv", SPEND, content_type="text/csv")
    return client.post("/api/parts/spend-imports/", {"file": f, "dry_run": str(dry_run).lower()})


def test_spend_import_validates_then_imports(auth_client, user):
    dry = _upload(auth_client, True)
    assert dry.status_code == 200
    assert dry.json()["valid_rows"] == 5
    assert dry.json()["rejected"][0]["row"] == 7
    assert Quote.objects.count() == 0

    res = _upload(auth_client, False)
    assert res.status_code == 201
    assert res.json()["imported_rows"] == 5
    assert Supplier.objects.filter(is_approved=False).count() == 3  # never on the AVL
    q = Quote.objects.get(part__part_number="ORB-1042")
    assert q.source == "spend.csv spend import row 2 (PO-24017)"
    assert q.quantity == 500 and q.lead_time_days == 15
    assert HistoricalCost.objects.filter(source=q.source, model_year=2025).exists()
    assert Quote.objects.filter(part__part_number="Hex nut M6").exists()

    assert auth_client.get("/api/parts/spend-imports/").json()[0]["kind"] == "spend"
    assert auth_client.get("/api/parts/imports/").json() == []
    ImportBatch.objects.get().delete()
    assert not Quote.objects.exists() and not HistoricalCost.objects.exists()


def test_spend_feeds_shortlist_and_lead_time(auth_client, user):
    _upload(auth_client, False)
    Supplier.objects.filter(name="Keystone CNC").update(is_approved=True)
    row = SimpleNamespace(part_number="ORB-1042", material="")
    picks = shortlist_row(user, row)["suppliers"]
    assert picks[0]["supplier"] == "Keystone CNC"
    assert "spend import row 2" in picks[0]["evidence"][0]["source"]
    assert lead_time_row(user, row)["days"] == 15


def test_research_without_key_uses_history(auth_client, user, bom_row, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    call_command("seed_part_history", user.username)
    res = auth_client.post(f"/api/parts/supplier-research/{bom_row.id}/")
    assert res.status_code == 201
    body = res.json()
    assert body["status"] == "UNVERIFIED" and body["mode"] == "history"
    assert "ANTHROPIC_API_KEY" in body["note"]
    names = [r["supplier"] for r in body["results"]]
    assert names == ["SAMPLE Precision Works"]
    assert all(not r["verified"] for r in body["results"])
    assert not Supplier.objects.get(name="SAMPLE Precision Works").is_approved
    assert auth_client.get(f"/api/parts/supplier-research/{bom_row.id}/").json()["id"] == body["id"]


def test_research_with_key_mocks_claude(auth_client, user, bom_row, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test")
    Supplier.objects.create(workspace_owner=user, name="Approved Co", is_approved=True)
    text = ('Here: [{"supplier": "Web Machining LLC", "unit_price": 3.8, "lead_time_days": 20, '
            '"risk_notes": ["Overseas"], "sources": ["https://example.com/web-machining"]}, '
            '{"supplier": "Approved Co", "unit_price": 1, "sources": ["https://x.example"]}, '
            '{"supplier": "No Source Inc", "unit_price": 1, "sources": []}]')
    fake = MagicMock()
    fake.messages.create.return_value = SimpleNamespace(content=[SimpleNamespace(type="text", text=text)])
    count = Supplier.objects.count()
    with patch("bom_agent.research_pipeline._client", return_value=fake):
        body = auth_client.post(f"/api/parts/supplier-research/{bom_row.id}/").json()
    assert body["mode"] == "web"
    assert [r["supplier"] for r in body["results"]] == ["Web Machining LLC"]
    assert body["results"][0]["sources"] == ["https://example.com/web-machining"]
    assert body["results"][0]["unit_price"] == "3.80"
    assert Supplier.objects.count() == count  # never added to suppliers / AVL
    assert SupplierResearch.objects.count() == 1
