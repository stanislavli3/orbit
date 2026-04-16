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

def _log(run, log_type: str, message: str) -> None:
    """Append a timestamped entry immediately — one DB write per call."""
    from .models import BomResearchRun

    ts = datetime.now(timezone.utc).strftime("%H:%M:%S")
    entry = {"ts": ts, "type": log_type, "message": message}
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


# ── Tool definitions (Sonnet) ─────────────────────────────────────────────────

_TOOLS = [
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
    _log(run, "material", f"  Material confirmed: {material} ({source}){lib_tag}")
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
    )
    return "Quote recorded."


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
    _log(run, log_type, f"  Risk flags: {flag_str}. {summary}")

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
    compliance_types: list[str],
    material_doc_names: list[str],
) -> None:
    from .models import BomLineItem

    _log(
        run, "search",
        f"Researching: {item.part_name} "
        f"(qty {item.quantity}, material: {item.material_spec or 'TBD'})",
    )
    BomLineItem.objects.filter(pk=item.pk).update(status="researching")
    item.refresh_from_db()

    avl_ctx = (
        f"Approved Vendor List — these suppliers are pre-approved: {', '.join(avl_names)}"
        if avl_names
        else "No AVL loaded — all suppliers are treated as non-AVL."
    )
    compliance_ctx = (
        f"Compliance certifications found in Library: {', '.join(compliance_types)}"
        if compliance_types
        else "No compliance documents in Library — flag compliance_gap=true if certs are needed."
    )
    material_ctx = (
        f"Material specification documents in Library: {', '.join(material_doc_names)}"
        if material_doc_names
        else "No material spec documents in Library."
    )
    inputs_summary = json.dumps(run.inputs_json, ensure_ascii=False)[:600]

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

## Pipeline — call tools in this order
1. Call record_material_spec once — identify the correct material grade/standard.
   Check the Library material docs first. If found there, set found_in_library=true.
   Otherwise infer from the part name and engineering knowledge.

2. Call record_supplier_quote 2–5 times — one call per supplier candidate.
   - Check AVL suppliers first (is_avl=true if in the list above).
   - Non-AVL suppliers must have is_avl=false.
   - Adjust unit_price for the production volume specified above.
   - Estimate landed_cost_usd = unit_price + (flat shipping estimate / qty).
   - Machined / cast parts need a non-zero tooling_cost.

3. Call record_risk_flags once — after all quotes are in.
   - cost_outlier=true if any quote is more than 2× the median unit price.

Output only tool calls — no narrative text."""

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
            response = _client().messages.create(
                model="claude-sonnet-4-6",
                max_tokens=1024,
                system=system_prompt,
                tools=_TOOLS,
                messages=messages,
            )
        except Exception as exc:
            _log(run, "error", f"  API error for {item.part_name}: {exc}")
            BomLineItem.objects.filter(pk=item.pk).update(status="needs_input")
            return

        if response.stop_reason == "end_turn":
            break

        if response.stop_reason == "tool_use":
            tool_results = []
            for block in response.content:
                if block.type != "tool_use":
                    continue
                try:
                    if block.name == "record_material_spec":
                        result = _handle_record_material_spec(item, run, block.input)
                    elif block.name == "record_supplier_quote":
                        result = _handle_record_supplier_quote(item, run, block.input)
                    elif block.name == "record_risk_flags":
                        result = _handle_record_risk_flags(item, run, block.input)
                    else:
                        result = f"Unknown tool: {block.name}"
                except Exception as exc:
                    result = f"Tool error: {exc}"

                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": result,
                })

            messages.append({"role": "assistant", "content": response.content})
            messages.append({"role": "user", "content": tool_results})
        else:
            break

    # Haiku summarisation pass
    item.refresh_from_db()
    _summarise_item(item, run)

    BomLineItem.objects.filter(pk=item.pk).update(status="sourced")


# ── Main entry point ──────────────────────────────────────────────────────────

def run_bom_research(run_id: int) -> None:
    """
    Full BOM research pipeline. Must be called in a background thread.

    Status transitions:
      gathering_inputs / awaiting_team_input
        → researching  (pipeline start)
        → generating_report  (all items done)
        → completed  (summary written)
        → failed  (on unhandled exception)
    """
    import datetime as dt
    from .models import BomResearchRun
    from assistant.rag import find_library_docs

    try:
        run = BomResearchRun.objects.prefetch_related("line_items").get(pk=run_id)
    except BomResearchRun.DoesNotExist:
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
            _log(run, "library", f"📚 AVL loaded: {', '.join(avl_names)}")
        else:
            avl_names = []
            _log(run, "library", "No AVL in Library — all suppliers treated as non-AVL")

        if compliance_docs:
            compliance_types = [d.original_name for d in compliance_docs]
            _log(run, "library", f"📚 Compliance docs: {', '.join(compliance_types)}")
        else:
            compliance_types = []

        if material_docs:
            material_doc_names = [d.original_name for d in material_docs]
            _log(run, "library", f"📚 Material specs: {', '.join(material_doc_names)}")
        else:
            material_doc_names = []

        if scorecard_docs:
            _log(run, "library", f"📚 Supplier scorecards: {', '.join(d.original_name for d in scorecard_docs)}")

        if prev_bom_docs:
            _log(run, "library", f"📚 Previous BOMs: {', '.join(d.original_name for d in prev_bom_docs)}")

        # ── Stage 1–4: Per-item research ──────────────────────────────────────
        items = list(run.line_items.exclude(part_name="(no files processed yet)"))
        if not items:
            items = list(run.line_items.all())

        _log(run, "info", f"Researching {len(items)} line item(s)")

        for item in items:
            _research_item(item, run, avl_names, compliance_types, material_doc_names)

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

        BomResearchRun.objects.filter(pk=run.pk).update(
            status="completed",
            completed_at=dt.datetime.now(dt.timezone.utc),
        )
        _log(run, "info", "✅ BOM run completed")

    except Exception:
        err = traceback.format_exc()
        try:
            _log(run, "error", f"Pipeline failed: {err[:400]}")
            _set_status(run, "failed")
        except Exception:
            pass
