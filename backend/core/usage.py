"""Token and cost accounting for every Claude call (assignment #23).

Every ``messages.create`` in the backend goes through :func:`tracked_create`,
which times the call, reads ``response.usage`` and writes one ``LlmUsage`` row
plus a structured ``llm_usage {json}`` log line. Accounting must never break
the product: any failure inside the bookkeeping is swallowed and logged.

``path`` groups calls the way the COGS model (#31) needs them:

* ``extraction`` — file description + engineering profile on upload
* ``query``      — Ask Orbit and the project chat assistant
* ``agent``      — BOM sourcing research (Sonnet steps, Haiku summary, web research,
                   team request emails / reply parsing)
* ``enrichment`` — optional rewrites (buyer handoff text, cost-reduction questions)

Prices are USD per million tokens, from Anthropic's pricing page
(platform.claude.com/docs/en/about-claude/pricing), retrieved 2026-11-17, and
match the Sep 6 cost model register (V1–V3). Re-verify before quoting them.
"""

import json
import logging
import time
from decimal import Decimal

logger = logging.getLogger("orbit.usage")

PATHS = ("extraction", "query", "agent", "enrichment")

# model prefix -> (input, output, 5-min cache write, cache read), USD per MTok
PRICES = {
    "claude-sonnet-4-6": (Decimal("3"), Decimal("15"), Decimal("3.75"), Decimal("0.30")),
    "claude-haiku-4-5": (Decimal("1"), Decimal("5"), Decimal("1.25"), Decimal("0.10")),
}
WEB_SEARCH_USD = Decimal("0.01")  # $10 per 1,000 searches
PRICE_SOURCE = "platform.claude.com/docs/en/about-claude/pricing, retrieved 2026-11-17"

_MILLION = Decimal(1_000_000)


def price_for(model: str):
    for prefix, price in PRICES.items():
        if (model or "").startswith(prefix):
            return price
    return None


def cost_usd(model: str, input_tokens=0, output_tokens=0, cache_write=0, cache_read=0, web_searches=0) -> Decimal | None:
    """Dollar cost of one call, or None for a model with no price on file."""
    price = price_for(model)
    if price is None:
        return None
    p_in, p_out, p_write, p_read = price
    tokens = (
        Decimal(input_tokens or 0) * p_in
        + Decimal(output_tokens or 0) * p_out
        + Decimal(cache_write or 0) * p_write
        + Decimal(cache_read or 0) * p_read
    ) / _MILLION
    return (tokens + Decimal(web_searches or 0) * WEB_SEARCH_USD).quantize(Decimal("0.000001"))


def _get(obj, name, default=0):
    if obj is None:
        return default
    if isinstance(obj, dict):
        return obj.get(name, default)
    return getattr(obj, name, default)


def usage_fields(response) -> dict:
    """Pull token counts out of an SDK response (or a dict shaped like one)."""
    usage = _get(response, "usage", None)
    server = _get(usage, "server_tool_use", None)
    return {
        "input_tokens": int(_get(usage, "input_tokens", 0) or 0),
        "output_tokens": int(_get(usage, "output_tokens", 0) or 0),
        "cache_creation_input_tokens": int(_get(usage, "cache_creation_input_tokens", 0) or 0),
        "cache_read_input_tokens": int(_get(usage, "cache_read_input_tokens", 0) or 0),
        "web_search_requests": int(_get(server, "web_search_requests", 0) or 0),
    }


def record_usage(response, *, path: str, operation: str, model: str, latency_ms: int | None = None,
                 user=None, target: str = "", error: str = ""):
    """Write one LlmUsage row and a structured log line. Never raises."""
    try:
        from .models import LlmUsage

        fields = usage_fields(response) if response is not None else {
            "input_tokens": 0, "output_tokens": 0, "cache_creation_input_tokens": 0,
            "cache_read_input_tokens": 0, "web_search_requests": 0,
        }
        model = str(_get(response, "model", "") or model or "")
        cost = cost_usd(
            model, fields["input_tokens"], fields["output_tokens"], fields["cache_creation_input_tokens"],
            fields["cache_read_input_tokens"], fields["web_search_requests"],
        )
        user_id = getattr(user, "pk", None) if user is not None and getattr(user, "is_authenticated", True) else None
        row = LlmUsage.objects.create(
            path=path, operation=operation[:60], model=model[:80], latency_ms=latency_ms,
            cost_usd=cost, user_id=user_id, target=str(target)[:120], error=error[:200], **fields,
        )
        logger.info("llm_usage %s", json.dumps({
            "path": path, "operation": operation, "model": model, **fields,
            "cost_usd": str(cost) if cost is not None else None, "latency_ms": latency_ms,
            "target": str(target)[:120], "error": error[:200],
        }))
        return row
    except Exception:  # accounting must never break the product
        logger.exception("llm_usage accounting failed for %s/%s", path, operation)
        return None


def tracked_create(client, *, path: str, operation: str, user=None, target: str = "", **kwargs):
    """``client.messages.create(**kwargs)`` with timing and usage accounting.

    API errors are recorded (zero tokens, error class) and re-raised unchanged so
    callers keep their existing fallbacks.
    """
    start = time.monotonic()
    try:
        response = client.messages.create(**kwargs)
    except Exception as exc:
        record_usage(None, path=path, operation=operation, model=kwargs.get("model", ""),
                     latency_ms=int((time.monotonic() - start) * 1000), user=user, target=target,
                     error=exc.__class__.__name__)
        raise
    record_usage(response, path=path, operation=operation, model=kwargs.get("model", ""),
                 latency_ms=int((time.monotonic() - start) * 1000), user=user, target=target)
    return response
