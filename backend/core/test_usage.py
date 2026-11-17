"""#23 — token and cost accounting on every Claude call. No network."""

from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from core.models import LlmUsage
from core.usage import cost_usd, tracked_create, usage_fields


def fake_response(model="claude-sonnet-4-6", inp=1000, out=200, write=0, read=0, searches=0, text="ok"):
    usage = SimpleNamespace(
        input_tokens=inp, output_tokens=out, cache_creation_input_tokens=write, cache_read_input_tokens=read,
        server_tool_use=SimpleNamespace(web_search_requests=searches) if searches else None,
    )
    return SimpleNamespace(model=model, usage=usage, content=[SimpleNamespace(type="text", text=text)],
                           stop_reason="end_turn")


def test_cost_matches_list_prices():
    # Sonnet 4.6: 1M in at $3 + 1M out at $15
    assert cost_usd("claude-sonnet-4-6", 1_000_000, 1_000_000) == Decimal("18.000000")
    # Haiku 4.5 with a dated snapshot suffix; cache write/read priced separately
    assert cost_usd("claude-haiku-4-5-20251001", 2000, 300, 1000, 1000) == Decimal("0.004850")
    # web search is $10 per 1,000
    assert cost_usd("claude-sonnet-4-6", 0, 0, web_searches=3) == Decimal("0.030000")
    assert cost_usd("some-unpriced-model", 10, 10) is None


def test_usage_fields_reads_sdk_and_dict_shapes():
    assert usage_fields(fake_response(searches=2))["web_search_requests"] == 2
    assert usage_fields({"usage": {"input_tokens": 5, "output_tokens": 7}})["output_tokens"] == 7
    assert usage_fields(SimpleNamespace())["input_tokens"] == 0


@pytest.mark.django_db
def test_tracked_create_records_tokens_cost_and_latency(user):
    client = MagicMock()
    client.messages.create.return_value = fake_response(inp=3100, out=420)
    response = tracked_create(client, path="query", operation="ask_orbit", user=user, target="BOM-00001",
                              model="claude-sonnet-4-6", max_tokens=10, messages=[])
    assert response.content[0].text == "ok"
    client.messages.create.assert_called_once_with(model="claude-sonnet-4-6", max_tokens=10, messages=[])
    row = LlmUsage.objects.get()
    assert (row.path, row.operation, row.input_tokens, row.output_tokens) == ("query", "ask_orbit", 3100, 420)
    assert row.cost_usd == Decimal("0.015600")  # 3100*3/1e6 + 420*15/1e6
    assert row.latency_ms is not None and row.user == user and row.target == "BOM-00001"


@pytest.mark.django_db
def test_api_error_is_recorded_and_reraised():
    client = MagicMock()
    client.messages.create.side_effect = TimeoutError("slow")
    with pytest.raises(TimeoutError):
        tracked_create(client, path="agent", operation="research_step", model="claude-sonnet-4-6")
    row = LlmUsage.objects.get()
    assert (row.error, row.input_tokens, row.cost_usd) == ("TimeoutError", 0, Decimal("0"))


@pytest.mark.django_db
def test_accounting_failure_never_breaks_the_call():
    client = MagicMock()
    client.messages.create.return_value = fake_response()
    with patch("core.models.LlmUsage.objects.create", side_effect=RuntimeError("db down")):
        assert tracked_create(client, path="query", operation="x", model="claude-sonnet-4-6").content


@pytest.mark.django_db
def test_ask_orbit_logs_a_query_row(user, monkeypatch):
    from assistant.ask import ask

    monkeypatch.setenv("ANTHROPIC_API_KEY", "test")
    with patch("assistant.ask.anthropic.Anthropic") as anthropic_cls:
        anthropic_cls.return_value.messages.create.return_value = fake_response(text="Answer [1]")
        result = ask(user, "what bracket material?")
    assert result["mode"] == "ai"
    row = LlmUsage.objects.get()
    assert (row.path, row.operation, row.user) == ("query", "ask_orbit", user)


@pytest.mark.django_db
def test_extraction_description_logs_an_extraction_row(monkeypatch):
    from files_api.ai_description import generate_file_description

    monkeypatch.setenv("ANTHROPIC_API_KEY", "test")
    with patch("files_api.ai_description.anthropic.Anthropic") as anthropic_cls:
        anthropic_cls.return_value.messages.create.return_value = fake_response(
            model="claude-haiku-4-5-20251001", inp=2130, out=305, text="A bracket.")
        assert generate_file_description("bracket.step", "step", {"schema": "AP214"}) == "A bracket."
    row = LlmUsage.objects.get()
    assert (row.path, row.operation, row.target) == ("extraction", "file_description", "bracket.step")
    assert row.cost_usd == Decimal("0.003655")
