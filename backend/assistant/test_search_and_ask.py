"""SCRUM-24 unified search and SCRUM-25 Ask Orbit in context. Claude is always mocked."""

from types import SimpleNamespace
from unittest import mock

import pytest
from django.core.management import call_command

from bom_agent.models import Bom, BomRow
from files_api.embeddings import generate_embedding
from files_api.models import FileEmbedding, UploadedFile
from projects.models import Project


@pytest.fixture
def data(user):
    call_command("seed_part_history", user.username)
    project = Project.objects.create(name="Rover", owner=user)
    f = UploadedFile.objects.create(project=project, uploaded_by=user, original_name="bracket_drawing.pdf",
                                    description="Aluminum mounting bracket drawing", file_type="pdf",
                                    s3_key="k1", file_size=1)
    FileEmbedding.objects.create(file=f, embedding_json=generate_embedding("aluminum mounting bracket drawing"))
    bom = Bom.objects.create(project=project, source_file=f, source_name="bracket_drawing.pdf", status="needs_review")
    row = BomRow.objects.create(bom=bom, line_no=1, part_number="ORB-1042", description="Mounting bracket",
                                material="6061-T6 aluminum", process="CNC machining", quantity=4)
    return SimpleNamespace(project=project, file=f, bom=bom, row=row)


def test_search_groups_ranks_and_cites(auth_client, data):
    res = auth_client.get("/api/assistant/search/", {"q": "bracket"})
    assert res.status_code == 200
    g = res.json()["groups"]
    assert set(g) == {"files", "bom_rows", "parts", "quotes", "suppliers"}
    assert g["files"][0]["link"] == f"/project/{data.project.id}/file/{data.file.id}/result"
    assert g["bom_rows"][0]["citation"].startswith(f"{data.bom.reference} line 1")
    assert g["bom_rows"][0]["link"] == f"/boms/{data.bom.id}"
    for hits in g.values():
        assert [h["score"] for h in hits] == sorted([h["score"] for h in hits], reverse=True)
        assert all(h["citation"] and h["link"] for h in hits)


def test_search_finds_cost_history_by_part_number(auth_client, data):
    g = auth_client.get("/api/assistant/search/", {"q": "ORB-1042"}).json()["groups"]
    assert g["parts"] and g["parts"][0]["title"].startswith("ORB-1042")
    assert g["quotes"]


def test_search_is_scoped_to_user(api_client, other_user, data):
    api_client.force_authenticate(other_user)
    assert api_client.get("/api/assistant/search/", {"q": "bracket"}).json()["total"] == 0


def test_empty_query(auth_client, data):
    assert auth_client.get("/api/assistant/search/", {"q": " "}).json()["total"] == 0


def test_ask_without_key_returns_retrieval_only(auth_client, data, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    res = auth_client.post("/api/assistant/ask/", {"question": "What did this cost before?", "row_id": data.row.id},
                           format="json")
    body = res.json()
    assert res.status_code == 200 and body["mode"] == "retrieval_only"
    assert "Retrieval-only" in body["answer"] and "[1]" in body["answer"]
    assert body["sources"][0]["citation"] == f"{data.bom.reference} line 1"
    assert any("Past cost of ORB-1042" == s["title"] for s in body["sources"])


def test_ask_with_bom_context_calls_claude(auth_client, data, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test")
    fake = mock.MagicMock()
    fake.messages.create.return_value = SimpleNamespace(content=[SimpleNamespace(text="Use 6061 [1].")])
    with mock.patch("assistant.ask.anthropic.Anthropic", return_value=fake):
        body = auth_client.post("/api/assistant/ask/", {"question": "Which material?", "bom_id": data.bom.id},
                                format="json").json()
    assert body == {**body, "answer": "Use 6061 [1].", "mode": "ai"}
    system = fake.messages.create.call_args.kwargs["system"]
    assert data.bom.reference in system and "[1]" in system


def test_ask_claude_error_falls_back(auth_client, data, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test")
    with mock.patch("assistant.ask.anthropic.Anthropic", side_effect=RuntimeError("down")):
        body = auth_client.post("/api/assistant/ask/", {"question": "cost?", "bom_id": data.bom.id},
                                format="json").json()
    assert body["mode"] == "retrieval_only"


def test_ask_validation_and_ownership(api_client, auth_client, other_user, data):
    assert auth_client.post("/api/assistant/ask/", {"question": ""}, format="json").status_code == 400
    api_client.force_authenticate(other_user)
    assert api_client.post("/api/assistant/ask/", {"question": "x", "bom_id": data.bom.id},
                           format="json").status_code == 404
