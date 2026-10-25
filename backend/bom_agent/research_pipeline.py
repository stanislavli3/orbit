"""
BOM Research Pipeline (#59 / #60).

Runs per BOM line item using Claude Sonnet with tool use.
Uses Claude Haiku for per-item summarisation.

Stages per line item
  1. Material identification  — explicit tool, updates BomLineItem.material_spec
  2. Supplier search          — AVL-first, non-AVL flagged ⚠️, 2–5 quotes
  3. Cost analysis            — unit price, tooling, landed cost, outlier flag
  4. Risk assessment          — single-source, lead time, compliance gap, geo concentration
  5. Haiku summary            — structured JSON summary written to results_json

Entry point:  run_bom_research(run_id: int) — call in a background thread.
Log format:   {"ts": "HH:MM:SS", "type": "<type>", "message": "<text>"}
"""

import os
import json
import time
import traceback
from datetime import datetime, timezone

import anthropic


# ── Lazy client ───────────────────────────────────────────────────────────────

_CLIENT: anthropic.Anthropic | None = None


def _client() -> anthropic.Anthropic:
    global _CLIENT
    if _CLIENT is None:
        _CLIENT = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY", ""))
    return _CLIENT


# ── Log helper ────────────────────────────────────────────────────────────────

def _log(run, log_type: str, message: str, **extra) -> None:
    """Append a timestamped entry immediately — one DB write per call."""
    from .models import BomResearchRun

    ts = datetime.now(timezone.utc).strftime("%H:%M:%S")
    entry = {"ts": ts, "type": log_type, "message": message}
    entry.update({key: value for key, value in extra.items() if value not in (None, "")})
    new_log = run.research_log + [entry]
    BomResearchRun.objects.filter(pk=run.pk).update(research_log=new_log)
    run.research_log = new_log


def _set_status(run, new_status: str) -> None:
    from .models import BomResearchRun

    run.status = new_status
    BomResearchRun.objects.filter(pk=run.pk).update(status=new_status)


def _update_results(run, item_key: str, patch: dict) -> None:
    """Merge patch into run.results_json[item_key] and persist."""
    from .models import BomResearchRun

    fresh = BomResearchRun.objects.values_list("results_json", flat=True).get(pk=run.pk) or {}
    section = fresh.get(item_key, {})
    section.update(patch)
    fresh[item_key] = section
    BomResearchRun.objects.filter(pk=run.pk).update(results_json=fresh)
    run.results_json = fresh


# ── Rate-limit + context-size helpers ─────────────────────────────────────────

def _is_rate_limit_error(exc: Exception) -> bool:
    """Detect a 429 rate-limit response in a provider-agnostic way."""
    if exc.__class__.__name__ == "RateLimitError":
        return True
    s = str(exc).lower()
    return "rate_limit_error" in s or "rate limit" in s or " 429" in s


def _call_claude_with_backoff(run, item, *, messages, system, tools, max_tokens=4096, max_retries=2):
    """
    messages.create wrapper with one 30 s backoff on HTTP 429 rate-limit errors.
    Re-raises any other exception, and re-raises 429 after max_retries exhausted.
    """
    for attempt in range(max_retries):
        try:
            return _client().messages.create(
                model="claude-sonnet-4-6",
                max_tokens=max_tokens,
                system=system,
                tools=tools,
                messages=messages,
            )
        except Exception as exc:
            if _is_rate_limit_error(exc) and attempt + 1 < max_retries:
                wait_s = 30
                _log(
                    run, "warn",
                    f"  ⏸ Rate limit hit on {item.part_name} — waiting {wait_s}s before retry (attempt {attempt + 1}/{max_retries})",
                    item_id=item.id,
                    part_name=item.part_name,
                )
                time.sleep(wait_s)
                continue
            raise


def _compact_response_content(content):
    """
    Return response.content as a list of plain dicts, with web_search_tool_result
    blocks aggressively trimmed:
      - encrypted_content dropped (largest token hog)
      - top 3 results only
      - title + url truncated
    Server-side search has already executed; keeping the full payload in
    message history only inflates future-turn input tokens.
    """
    out = []
    for block in content:
        # Convert SDK objects → dicts
        if hasattr(block, "model_dump"):
            b = block.model_dump()
        elif isinstance(block, dict):
            b = block
        else:
            try:
                b = dict(block.__dict__)
            except Exception:
                out.append(block)
                continue

        if b.get("type") == "web_search_tool_result":
            raw = b.get("content") or []
            if isinstance(raw, list):
                trimmed = []
                for r in raw[:3]:
                    if not isinstance(r, dict):
                        continue
                    trimmed.append({
                        "type": r.get("type", "web_search_result"),
                        "title": (r.get("title") or "")[:80],
                        "url": (r.get("url") or "")[:120],
                    })
                b["content"] = trimmed
        out.append(b)
    return out


def _finalize_on_api_error(item, run, exc):
    """
    On unrecoverable API error: preserve partial results.
    If ≥ 1 quote was already recorded, mark the item `sourced` with a warning.
    Otherwise mark `needs_input` as before.
    """
    from .models import BomLineItem
    item.refresh_from_db()
    quote_count = item.quotes.count()
    if quote_count > 0:
        _log(
            run, "warn",
            f"  Partial — {item.part_name} kept with {quote_count} quote(s) after API error: {exc}",
            item_id=item.id,
            part_name=item.part_name,
        )
        BomLineItem.objects.filter(pk=item.pk).update(status="sourced")
    else:
        _log(run, "error", f"  API error for {item.part_name}: {exc}")
        BomLineItem.objects.filter(pk=item.pk).update(status="needs_input")


# ── Tool definitions (Sonnet) ─────────────────────────────────────────────────

# web_search is an Anthropic-hosted tool — no external API key needed.
# Claude calls it; Anthropic's servers execute the search and inject results.
_TOOLS = [
    {"type": "web_search_20250305", "name": "web_search"},
    {
        "name": "record_material_spec",
        "description": (
            "Record the confirmed material specification for this part. "
            "Call ONCE after identifying the material from metadata or Library context."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "material": {
                    "type": "string",
                    "description": "Full material grade, e.g. '6061-T6 Aluminum' or '316L Stainless Steel'",
                },
                "standard": {
                    "type": "string",
                    "description": "Applicable standard (ASTM, ISO, MIL-SPEC) if known, else empty string",
                },
                "found_in_library": {
                    "type": "boolean",
                    "description": "True if spec was found in a Library document",
                },
                "source": {
                    "type": "string",
                    "description": "Where the material was identified (e.g. 'STEP metadata', 'Library: materials.xlsx', 'inferred from part name')",
                },
            },
            "required": ["material", "standard", "found_in_library", "source"],
        },
    },
    {
        "name": "record_supplier_quote",
        "description": (
            "Record one supplier quote. "
            "Call once per supplier — aim for 2–5 quotes. "
            "Prefer AVL suppliers; flag non-AVL with is_avl=false."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "supplier_name": {"type": "string"},
                "unit_price": {"type": "number", "description": "Unit price in USD at the requested production volume"},
                "moq": {"type": "integer", "description": "Minimum order quantity"},
                "lead_time_days": {"type": "integer"},
                "tooling_cost": {
                    "type": "number",
                    "description": "One-time tooling / NRE cost in USD; 0 for COTS / fasteners",
                },
                "landed_cost_usd": {
                    "type": "number",
                    "description": "Estimated per-unit landed cost including shipping (unit_price + shipping_estimate/qty)",
                },
                "source_url": {"type": "string", "description": "Supplier website URL, empty if unknown"},
                "notes": {"type": "string", "description": "Any relevant notes"},
                "is_avl": {"type": "boolean"},
                "country": {"type": "string", "description": "Supplier country, e.g. 'USA', 'China', 'Germany'"},
            },
            "required": [
                "supplier_name",
                "unit_price",
                "moq",
                "lead_time_days",
                "tooling_cost",
                "landed_cost_usd",
                "is_avl",
                "country",
            ],
        },
    },
    {
        "name": "flag_insufficient_data",
        "description": (
            "Call this when you genuinely cannot research this part after 2+ searches — "
            "for example the part name is not identifiable (e.g. a CAD schema string like "
            "'STEP AP203'), quantity/material are missing, or no supplier data exists. "
            "This marks the line item as needs_input and surfaces your reason to the user. "
            "Prefer recording estimated quotes over calling this — only use this when you "
            "truly cannot proceed."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "reason": {
                    "type": "string",
                    "description": "Concrete reason, referencing what you saw. e.g. 'Part name STEP AP203 is a CAD schema version, not a part identifier. Web search returned only CAD-format documentation, no supplier pricing.'",
                },
                "what_would_help": {
                    "type": "string",
                    "description": "Specific input the user could provide to unblock. e.g. 'An actual part name, a drawing, or a supplier hint'.",
                },
            },
            "required": ["reason", "what_would_help"],
        },
    },
    {
        "name": "record_risk_flags",
        "description": "Record risk assessment after all supplier quotes have been submitted. Call ONCE per part.",
        "input_schema": {
            "type": "object",
            "properties": {
                "single_source_risk": {
                    "type": "boolean",
                    "description": "True if fewer than 2 AVL suppliers exist for this part",
                },
                "long_lead_time_risk": {
                    "type": "boolean",
                    "description": "True if the shortest lead time exceeds 90 days",
                },
                "compliance_gap": {
                    "type": "boolean",
                    "description": "True if required compliance certification is absent from Library",
                },
                "geographic_concentration": {
                    "type": "boolean",
                    "description": "True if all identified suppliers are in a single country/region",
                },
                "cost_outlier": {
                    "type": "boolean",
                    "description": "True if any quote deviates more than 2× from the median unit price",
                },
                "summary": {
                    "type": "string",
                    "description": "1–2 sentence plain-English risk summary",
                },
            },
            "required": [
                "single_source_risk",
                "long_lead_time_risk",
                "compliance_gap",
                "geographic_concentration",
                "cost_outlier",
                "summary",
            ],
        },
    },
]


# ── Tool handlers ─────────────────────────────────────────────────────────────

def _handle_record_material_spec(item, run, inputs: dict) -> str:
    from .models import BomLineItem

    material = inputs.get("material", "").strip()
    standard = inputs.get("standard", "").strip()
    found_in_library = inputs.get("found_in_library", False)
    source = inputs.get("source", "")

    if material:
        full_spec = f"{material} {standard}".strip() if standard else material
        BomLineItem.objects.filter(pk=item.pk).update(material_spec=full_spec)
        item.material_spec = full_spec

    lib_tag = " [from Library]" if found_in_library else ""
    _log(
        run,
        "material",
        f"  Material confirmed: {material} ({source}){lib_tag}",
        item_id=item.id,
        part_name=item.part_name,
        source=source,
    )
    _update_results(run, f"item_{item.id}", {
        "material": material,
        "material_standard": standard,
        "material_source": source,
        "material_from_library": found_in_library,
    })
    return "Material spec recorded."


def _handle_record_supplier_quote(item, run, inputs: dict) -> str:
    from .models import SupplierQuote

    is_avl = inputs.get("is_avl", False)
    notes = inputs.get("notes", "").strip()
    country = inputs.get("country", "")
    landed = inputs.get("landed_cost_usd")

    if not is_avl:
        notes = f"⚠️ Non-AVL supplier. {notes}".strip()

    SupplierQuote.objects.create(
        line_item=item,
        supplier_name=inputs["supplier_name"],
        unit_price=inputs["unit_price"],
        moq=inputs["moq"],
        lead_time_days=inputs["lead_time_days"],
        tooling_cost=inputs.get("tooling_cost", 0),
        landed_cost_usd=landed,
        source_url=inputs.get("source_url", ""),
        notes=f"{notes} [Country: {country}]".strip() if country else notes,
        is_avl=is_avl,
    )

    avl_tag = "" if is_avl else " [Non-AVL ⚠️]"
    landed_str = f", landed ${landed:.2f}" if landed is not None else ""
    _log(
        run, "quote",
        f"  Quoted: {inputs['supplier_name']}{avl_tag} — "
        f"${inputs['unit_price']}/unit{landed_str}, "
        f"MOQ {inputs['moq']}, {inputs['lead_time_days']}d lead, {country}",
        item_id=item.id,
        part_name=item.part_name,
        supplier_name=inputs["supplier_name"],
        source_url=inputs.get("source_url", ""),
    )
    return "Quote recorded."


def _handle_flag_insufficient_data(item, run, inputs: dict) -> str:
    from .models import BomLineItem

    reason = (inputs.get("reason") or "").strip() or "No reason provided."
    hint = (inputs.get("what_would_help") or "").strip()

    BomLineItem.objects.filter(pk=item.pk).update(status="needs_input")
    item.status = "needs_input"

    msg = f"  ⚠️ Cannot research {item.part_name} — {reason}"
    if hint:
        msg += f" | Would help: {hint}"
    _log(
        run, "warn", msg,
        item_id=item.id,
        part_name=item.part_name,
        reason=reason,
        what_would_help=hint,
    )
    _update_results(run, f"item_{item.id}", {
        "needs_input_reason": reason,
        "needs_input_hint": hint,
        "flagged_insufficient": True,
    })
    return f"Line item marked needs_input: {reason}"


def _handle_record_risk_flags(item, run, inputs: dict) -> str:
    flags = []
    if inputs.get("single_source_risk"):
        flags.append("single-source")
    if inputs.get("long_lead_time_risk"):
        flags.append("long-lead-time")
    if inputs.get("compliance_gap"):
        flags.append("compliance-gap")
    if inputs.get("geographic_concentration"):
        flags.append("geographic-concentration")
    if inputs.get("cost_outlier"):
        flags.append("cost-outlier")

    summary = inputs.get("summary", "")
    log_type = "risk" if flags else "info"
    flag_str = ", ".join(flags) if flags else "none"
    _log(
        run,
        log_type,
        f"  Risk flags: {flag_str}. {summary}",
        item_id=item.id,
        part_name=item.part_name,
    )

    _update_results(run, f"item_{item.id}", {
        "risk_flags": flags,
        "risk_summary": summary,
    })
    return "Risk flags recorded."


# ── Haiku summarisation (#5) ──────────────────────────────────────────────────

def _summarise_item(item, run) -> None:
    """
    Use Claude Haiku to produce a concise structured summary for one item
    and store it in results_json[item_<id>].summary.
    """
    quotes = list(item.quotes.all())
    if not quotes:
        return

    quote_lines = "\n".join(
        f"- {q.supplier_name}: ${q.unit_price}/unit, MOQ {q.moq}, {q.lead_time_days}d, tooling ${q.tooling_cost}"
        for q in quotes
    )
    results_section = (run.results_json or {}).get(f"item_{item.id}", {})
    risk_flags = results_section.get("risk_flags", [])
    material = results_section.get("material") or item.material_spec or "unknown"

    prompt = f"""Summarise this BOM line item research in ≤120 words for an engineer.

Part: {item.part_name}
Material: {material}
Quantity: {item.quantity}

Supplier quotes:
{quote_lines}

Risk flags: {', '.join(risk_flags) if risk_flags else 'none'}

Write a concise summary covering: recommended material, best supplier pick (with reason), \
key cost drivers, and top risk. Plain prose, no bullet lists, no headers."""

    try:
        response = _client().messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=200,
            messages=[{"role": "user", "content": prompt}],
        )
        summary_text = response.content[0].text.strip()
        _update_results(run, f"item_{item.id}", {"summary": summary_text})
        _log(run, "summary", f"  Summary generated for {item.part_name}")
    except Exception as exc:
        _log(run, "warn", f"  Haiku summary failed for {item.part_name}: {exc}")


# ── Per-item research (Sonnet) ────────────────────────────────────────────────

def _research_item(
    item,
    run,
    avl_names: list[str],
    avl_content: str,
    compliance_types: list[str],
    material_doc_names: list[str],
    material_doc_content: str,
) -> None:
    from .models import BomLineItem

    _log(
        run, "search",
        f"Researching: {item.part_name} "
        f"(qty {item.quantity}, material: {item.material_spec or 'TBD'})",
        item_id=item.id,
        part_name=item.part_name,
    )
    BomLineItem.objects.filter(pk=item.pk).update(status="researching")
    item.refresh_from_db()

    if avl_content:
        avl_ctx = (
            f"Approved Vendor List — pre-approved suppliers (is_avl=true for these):\n"
            f"{avl_content[:3000]}"
        )
    elif avl_names:
        avl_ctx = f"Approved Vendor List — pre-approved suppliers: {', '.join(avl_names)}"
    else:
        avl_ctx = "No AVL loaded — all suppliers are treated as non-AVL."

    compliance_ctx = (
        f"Compliance certifications found in Library: {', '.join(compliance_types)}"
        if compliance_types
        else "No compliance documents in Library — flag compliance_gap=true if certs are needed."
    )

    if material_doc_content:
        material_ctx = (
            f"Material specification from Library:\n{material_doc_content[:2000]}"
        )
    elif material_doc_names:
        material_ctx = f"Material specification documents in Library: {', '.join(material_doc_names)}"
    else:
        material_ctx = "No material spec documents in Library."

    inputs_summary = json.dumps(run.inputs_json, ensure_ascii=False)[:600]

    _log(run, "info", f"🔎 Researching {item.part_name}…", item_id=item.id, part_name=item.part_name)

    system_prompt = f"""You are an expert BOM research agent for mechanical engineering manufacturing.

## Part
Name: {item.part_name}
Part number: {item.part_number or "unknown"}
Current material: {item.material_spec or "unknown — you must identify it"}
Quantity per production run: {item.quantity}

## BOM run context (user-supplied answers)
{inputs_summary}

## Library context
{avl_ctx}

{compliance_ctx}

{material_ctx}

## Pipeline
Call tools in this order:

1. record_material_spec — once. Identify the material grade/standard from Library content,
   user-supplied context, or engineering inference.

2. web_search — at least TWO distinct-angle searches before concluding. Examples of
   different angles for the same part:
     - Material-first: "6061-T6 aluminum CNC machined bracket supplier quote"
     - Part-class-first: "[part type] manufacturer catalog USA pricing"
     - AVL-first (when an AVL is provided above): "[AVL supplier name] [part type] [material]"
   Prefer AVL suppliers when an AVL exists. Broaden to contract manufacturers /
   distributors if the first search yields no concrete pricing.

3. record_supplier_quote — 2–5 times. Each call records one supplier candidate.
   - AVL suppliers: is_avl=true. Others: is_avl=false.
   - Adjust unit_price for the production volume above.
   - landed_cost_usd ≈ unit_price + (shipping / qty).
   - Machined / cast parts must have non-zero tooling_cost.
   - If searches returned relevant distributors/manufacturers but no explicit
     price: you may record an estimated quote. Mark that clearly in notes
     ("Estimated: industry benchmark for 6061-T6 bracket in this size class, no
     exact quote published"). Estimates are better than 0 quotes.

4. record_risk_flags — once, after quotes are in.
   - cost_outlier=true if any quote deviates >2× from the median.

## Non-negotiable contract
Before calling end_turn you MUST have done one of the following:
  (a) Recorded AT LEAST 2 record_supplier_quote calls AND one record_risk_flags call, OR
  (b) Called flag_insufficient_data(reason, what_would_help) to explicitly surface
      why this part cannot be researched (e.g. "Part name 'STEP AP203' is a CAD
      schema version, not a part identifier — need an actual part name or
      drawing").

Never end your turn with 0 quotes and no flag_insufficient_data call. If the
searches come back empty or the part name is nonsense, use flag_insufficient_data.

Brief narrative reasoning in text blocks is welcome between tool calls — it
helps us debug and improve the pipeline.
"""

    messages: list[dict] = [
        {"role": "user", "content": f"Research this part: {item.part_name}"}
    ]

    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        _log(run, "warn", f"  Skipping {item.part_name} — ANTHROPIC_API_KEY not set")
        BomLineItem.objects.filter(pk=item.pk).update(status="needs_input")
        return

    for _turn in range(15):
        try:
            response = _call_claude_with_backoff(
                run, item,
                messages=messages,
                system=system_prompt,
                tools=_TOOLS,
            )
        except Exception as exc:
            _finalize_on_api_error(item, run, exc)
            return

        if response.stop_reason == "end_turn":
            break

        if response.stop_reason == "tool_use":
            tool_results = []
            for block in response.content:
                if block.type == "server_tool_use":
                    # Anthropic-hosted tools (e.g. web_search) execute server-side and
                    # their results come back in the same response as `web_search_tool_result`
                    # blocks. The client must NOT fabricate a tool_result for these —
                    # doing so causes "unexpected tool_use_id" 400s on the next turn.
                    if getattr(block, "name", "") == "web_search":
                        raw_input = getattr(block, "input", {}) or {}
                        query = raw_input.get("query", "") or raw_input.get("q", "") if isinstance(raw_input, dict) else ""
                        _log(
                            run,
                            "search",
                            f"  Search query: {query}" if query else "  Search query executed",
                            item_id=item.id,
                            part_name=item.part_name,
                            query=query,
                        )
                    continue

                if block.type == "web_search_tool_result":
                    # Fx: surface top web-search findings so the user can see what the
                    # agent actually saw (vs. silent 'search returned nothing' mystery).
                    raw = getattr(block, "content", None)
                    results_iter = raw if isinstance(raw, list) else []
                    top = []
                    for r in results_iter[:3]:
                        title = getattr(r, "title", None) if not isinstance(r, dict) else r.get("title")
                        url = getattr(r, "url", None) if not isinstance(r, dict) else r.get("url")
                        title = (title or "").strip()
                        url = (url or "").strip()
                        if title or url:
                            top.append(f"{title[:70]}{' — ' if title and url else ''}{url}")
                    if top:
                        _log(
                            run, "search",
                            "  Top results:\n    • " + "\n    • ".join(top),
                            item_id=item.id,
                            part_name=item.part_name,
                        )
                    continue

                if block.type != "tool_use":
                    # Skips any remaining server blocks and text reasoning blocks.
                    continue

                try:
                    if block.name == "record_material_spec":
                        result = _handle_record_material_spec(item, run, block.input)
                    elif block.name == "record_supplier_quote":
                        result = _handle_record_supplier_quote(item, run, block.input)
                    elif block.name == "record_risk_flags":
                        result = _handle_record_risk_flags(item, run, block.input)
                    elif block.name == "flag_insufficient_data":
                        result = _handle_flag_insufficient_data(item, run, block.input)
                    else:
                        result = f"Unknown tool: {block.name}"
                except Exception as exc:
                    result = f"Tool error: {exc}"

                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": result,
                })

            messages.append({"role": "assistant", "content": _compact_response_content(response.content)})
            if not tool_results:
                # Only server-side tools in this turn — let the model continue on
                # its own findings instead of appending an empty user message
                # (the API rejects user messages with empty content).
                continue
            messages.append({"role": "user", "content": tool_results})
        else:
            break

    # Ex: quality gate. If the model ended its turn with 0 quotes AND did not
    # call flag_insufficient_data, give it one targeted retry pointing at the
    # violation. This catches silent 'I give up' failures.
    item.refresh_from_db()
    if item.quotes.count() == 0 and item.status != "needs_input":
        _log(
            run, "warn",
            f"  ↻ Retry: {item.part_name} ended with 0 quotes and no flag — prompting for quotes or an explicit flag.",
            item_id=item.id,
            part_name=item.part_name,
        )
        retry_message = (
            "You ended your previous turn without recording any record_supplier_quote "
            "calls AND without calling flag_insufficient_data. This violates the "
            "non-negotiable contract from the system prompt.\n\n"
            "Do one of the following now:\n"
            "  (a) Record AT LEAST 2 record_supplier_quote calls, then record_risk_flags. "
            "Estimates are acceptable — mark them clearly in `notes` (e.g. "
            "\"Estimated from industry benchmarks, no public price available\").\n"
            "  (b) Call flag_insufficient_data with a concrete reason explaining exactly "
            "what blocked you (e.g. 'Part name is a CAD schema string, not a part').\n\n"
            "Choose one. Do not end your turn again with 0 quotes and no flag."
        )
        messages.append({"role": "user", "content": retry_message})
        for _retry_turn in range(5):
            try:
                response = _call_claude_with_backoff(
                    run, item,
                    messages=messages,
                    system=system_prompt,
                    tools=_TOOLS,
                )
            except Exception as exc:
                _log(run, "warn", f"  Retry API error for {item.part_name}: {exc}")
                break

            if response.stop_reason == "end_turn":
                break
            if response.stop_reason != "tool_use":
                break

            tool_results = []
            for block in response.content:
                if block.type == "server_tool_use":
                    continue
                if block.type == "web_search_tool_result":
                    continue
                if block.type != "tool_use":
                    continue
                try:
                    if block.name == "record_material_spec":
                        result = _handle_record_material_spec(item, run, block.input)
                    elif block.name == "record_supplier_quote":
                        result = _handle_record_supplier_quote(item, run, block.input)
                    elif block.name == "record_risk_flags":
                        result = _handle_record_risk_flags(item, run, block.input)
                    elif block.name == "flag_insufficient_data":
                        result = _handle_flag_insufficient_data(item, run, block.input)
                    else:
                        result = f"Unknown tool: {block.name}"
                except Exception as exc:
                    result = f"Tool error: {exc}"
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": result,
                })
            messages.append({"role": "assistant", "content": _compact_response_content(response.content)})
            if not tool_results:
                continue
            messages.append({"role": "user", "content": tool_results})

    # Haiku summarisation + final status
    item.refresh_from_db()
    quote_count = item.quotes.count()
    _log(
        run, "info",
        f"   ↳ finished {item.part_name} ({quote_count} quote{'s' if quote_count != 1 else ''})",
        item_id=item.id,
        part_name=item.part_name,
    )
    _summarise_item(item, run)

    # Correct status: only `sourced` if quotes landed. Otherwise `needs_input`
    # (preserving an earlier flag_insufficient_data reason if set).
    if quote_count > 0:
        BomLineItem.objects.filter(pk=item.pk).update(status="sourced")
    else:
        if item.status != "needs_input":
            _log(
                run, "warn",
                f"  ⚠️ {item.part_name}: 0 quotes after retry and no flag_insufficient_data — defaulting to needs_input.",
                item_id=item.id,
                part_name=item.part_name,
            )
        BomLineItem.objects.filter(pk=item.pk).update(status="needs_input")


# ── Main entry point ──────────────────────────────────────────────────────────

def _superseded(run, job_token: str | None) -> bool:
    """True once a newer job for this run has been queued (see tasks.enqueue_bom_research)."""
    from .models import BomResearchRun

    if job_token is None:
        return False
    current = BomResearchRun.objects.values_list("job_token", flat=True).get(pk=run.pk)
    return current != job_token


def run_bom_research(run_id: int, job_token: str | None = None) -> None:
    """
    Full BOM research pipeline. Runs in a Celery worker (bom_agent.tasks).

    Resumable: items already `sourced` are skipped, and any other item's
    partial quotes are cleared before it is re-researched, so running this
    again after a crash or a team reply never duplicates quotes.

    Status transitions:
      gathering_inputs / awaiting_team_input
        → researching  (pipeline start)
        → generating_report  (all items done)
        → completed  (summary written)
        → failed  (on unhandled exception)
    """
    import django.db
    django.db.close_old_connections()

    run = None
    try:
        import datetime as dt
        from .models import BomResearchRun
        from assistant.rag import find_library_docs
        from .excel_export import upload_bom_workbook

        try:
            run = BomResearchRun.objects.prefetch_related("line_items").get(pk=run_id)
        except BomResearchRun.DoesNotExist:
            return

    except Exception:
        err = traceback.format_exc()
        if run is not None:
            try:
                _log(run, "error", f"Pipeline startup failed: {err[:400]}")
                _set_status(run, "failed")
            except Exception:
                pass
        return

    try:
        _set_status(run, "researching")
        _log(run, "info", "BOM research started")

        user = run.created_by

        # ── Stage 0: Load Library docs ────────────────────────────────────────
        avl_docs = find_library_docs(user, doc_types=["avl"])
        compliance_docs = find_library_docs(user, doc_types=["compliance"])
        material_docs = find_library_docs(user, doc_types=["material-spec", "preferred-materials"])
        scorecard_docs = find_library_docs(user, doc_types=["scorecard"])
        prev_bom_docs = find_library_docs(user, doc_types=["previous-bom"])

        all_lib_docs = [*avl_docs, *compliance_docs, *material_docs, *scorecard_docs, *prev_bom_docs]
        if all_lib_docs:
            run.library_documents.add(*all_lib_docs)

        if avl_docs:
            avl_names = [d.original_name for d in avl_docs]
            avl_content = "\n\n".join(d.extracted_text for d in avl_docs if d.extracted_text)
            supplier_count = avl_content.count("\n") if avl_content else 0
            _log(run, "library", f"📚 AVL loaded: {', '.join(avl_names)} — ~{supplier_count} rows")
        else:
            avl_names = []
            avl_content = ""
            _log(run, "library", "No AVL in Library — all suppliers treated as non-AVL")

        if compliance_docs:
            compliance_types = [d.original_name for d in compliance_docs]
            _log(run, "library", f"📚 Compliance docs: {', '.join(compliance_types)}")
        else:
            compliance_types = []

        if material_docs:
            material_doc_names = [d.original_name for d in material_docs]
            material_doc_content = "\n\n".join(d.extracted_text for d in material_docs if d.extracted_text)
            _log(run, "library", f"📚 Material specs: {', '.join(material_doc_names)}")
        else:
            material_doc_names = []
            material_doc_content = ""

        if scorecard_docs:
            _log(run, "library", f"📚 Supplier scorecards: {', '.join(d.original_name for d in scorecard_docs)}")

        if prev_bom_docs:
            _log(run, "library", f"📚 Previous BOMs: {', '.join(d.original_name for d in prev_bom_docs)}")

        # ── Stage 1–4: Per-item research ──────────────────────────────────────
        items = list(run.line_items.exclude(part_name="(no files processed yet)"))
        if not items:
            items = list(run.line_items.all())

        already_sourced = [i for i in items if i.status == "sourced"]
        items = [i for i in items if i.status != "sourced"]
        if already_sourced:
            _log(run, "info", f"Resuming — {len(already_sourced)} item(s) already sourced, skipping")
        _log(run, "info", f"Researching {len(items)} line item(s)")

        for item in items:
            if _superseded(run, job_token):
                return
            item.quotes.all().delete()  # partial quotes from an interrupted attempt
            _research_item(
                item, run,
                avl_names, avl_content,
                compliance_types,
                material_doc_names, material_doc_content,
            )

        if _superseded(run, job_token):
            return

        # ── Generating report ─────────────────────────────────────────────────
        _set_status(run, "generating_report")
        _log(run, "info", "Generating run summary…")

        items_refreshed = list(run.line_items.prefetch_related("quotes").all())
        total_quotes = sum(i.quotes.count() for i in items_refreshed)
        needs_input = sum(1 for i in items_refreshed if i.status == "needs_input")
        sourced = sum(1 for i in items_refreshed if i.status == "sourced")

        # Aggregate cost summary
        all_prices = [
            float(q.unit_price)
            for i in items_refreshed
            for q in i.quotes.all()
        ]
        if all_prices:
            avg_unit = sum(all_prices) / len(all_prices)
            _log(run, "info", f"Average unit price across all quotes: ${avg_unit:.2f}")

        _log(
            run, "info",
            f"Research complete — {sourced} items sourced, {needs_input} need manual input, "
            f"{total_quotes} supplier quotes captured",
        )

        run.refresh_from_db()
        run.completed_at = dt.datetime.now(dt.timezone.utc)
        excel_key = ""
        try:
            excel_key = upload_bom_workbook(run)
        except Exception as exc:
            # Running without S3 (e.g. `make dev-local`) or a transient upload
            # failure shouldn't fail the whole run — the results are already
            # persisted via BomLineItem / SupplierQuote rows.
            _log(run, "warn", f"Excel upload skipped — {type(exc).__name__}: {str(exc)[:200]}")

        BomResearchRun.objects.filter(pk=run.pk).update(
            excel_s3_key=excel_key,
            status="completed",
            completed_at=run.completed_at,
        )
        run.excel_s3_key = excel_key

        if excel_key:
            _log(run, "info", "Excel workbook generated and uploaded", source_url=excel_key)
        _log(run, "info", "✅ BOM run completed")

    except Exception:
        err = traceback.format_exc()
        try:
            _log(run, "error", f"Pipeline failed: {err[:400]}")
            _set_status(run, "failed")
        except Exception:
            pass
