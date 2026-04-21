"""
Generate a plain-English description and structured Engineering Profile for uploaded
engineering files using Claude. Called synchronously inside the background extraction thread.
"""

import json
import os
import anthropic


_MODEL = "claude-haiku-4-5-20251001"  # fast + cheap for description generation


def generate_file_description(
    file_name: str,
    file_type: str,
    extraction: dict,
) -> str:
    """
    Ask Claude to write a concise description of the file.

    Parameters
    ----------
    file_name   : original filename, e.g. "bracket_v3.step"
    file_type   : extension without dot, e.g. "step"
    extraction  : result dict from extract_step_header()
    """
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        return ""

    schema = extraction.get("schema") or ""
    file_description = extraction.get("file_description") or ""
    units_hint = extraction.get("units_hint") or ""
    confidence = extraction.get("confidence", 0)

    known_facts = []
    if file_description:
        known_facts.append(f'- FILE_DESCRIPTION from header: "{file_description}"')
    if schema:
        known_facts.append(f"- STEP schema: {schema}")
    if units_hint:
        known_facts.append(f"- Units: {units_hint}")
    if confidence:
        known_facts.append(f"- Extraction confidence: {int(confidence * 100)}%")

    facts_block = (
        "\n".join(known_facts) if known_facts else "No header data could be parsed."
    )

    prompt = f"""You are an expert mechanical engineer reviewing a CAD file upload.

File name: {file_name}
File type: {file_type.upper()}

Automatically extracted metadata:
{facts_block}

Write a concise, factual description (2-4 sentences) of what this file likely contains and its key characteristics. Mention the schema, units, and any part information available. If metadata is sparse, describe what is typical for this file type and schema. Do not speculate beyond what the metadata supports. Do not use markdown."""

    try:
        client = anthropic.Anthropic(api_key=api_key)
        message = client.messages.create(
            model=_MODEL,
            max_tokens=256,
            messages=[{"role": "user", "content": prompt}],
        )
        return message.content[0].text.strip()
    except Exception:
        return ""


def generate_engineering_profile(
    file_name: str,
    file_type: str,
    extraction: dict,
) -> dict:
    """
    Ask Claude to produce a structured Engineering Profile from extraction metadata.
    Returns a dict with profile fields, or {} on error.
    """
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        return {}

    context_parts = [f"Filename: {file_name}", f"File type: {file_type.upper()}"]

    if extraction.get("file_description"):
        context_parts.append(f"STEP description: {extraction['file_description']}")
    if extraction.get("schema"):
        context_parts.append(f"STEP schema: {extraction['schema']}")
    if extraction.get("units_hint"):
        context_parts.append(f"Units: {extraction['units_hint']}")

    products = extraction.get("products") or {}
    if products.get("product_names"):
        context_parts.append(f"Product names: {', '.join(products['product_names'][:5])}")
    if products.get("revisions"):
        context_parts.append(f"Revisions: {', '.join(products['revisions'])}")

    geometry = extraction.get("geometry") or {}
    geo_items = [
        f"{k}: {geometry[k]}"
        for k in ("solid_bodies", "faces", "edges", "vertices")
        if geometry.get(k) is not None
    ]
    if geo_items:
        context_parts.append(f"Geometry: {', '.join(geo_items)}")

    bb = (extraction.get("spatial") or {}).get("bounding_box_estimate")
    if bb:
        context_parts.append(f"Bounding box: X={bb.get('x')}, Y={bb.get('y')}, Z={bb.get('z')}")

    materials = (extraction.get("appearance") or {}).get("materials") or []
    if materials:
        context_parts.append(f"Materials mentioned: {', '.join(materials)}")

    context = "\n".join(context_parts)

    prompt = f"""You are an expert mechanical engineer. Analyze this CAD file metadata and produce a structured Engineering Profile as JSON.

{context}

Return ONLY valid JSON (no markdown) with exactly this structure:
{{
  "part_number": "extracted or inferred part number, or null",
  "name": "descriptive part name",
  "material": {{
    "value": "material name or null",
    "confidence": 0.0
  }},
  "category": "part category (e.g. Shaft, Bracket, Housing, Plate, Assembly)",
  "dimensions": "concise dimension string using engineering notation (e.g. Ø32 × 200 mm), or null",
  "revision": "revision letter/number or null",
  "volume": {{
    "value": "volume with units or null",
    "confidence": 0.0
  }},
  "provenance": {{
    "sources": ["list of data sources used"],
    "warnings": ["list of data quality warnings, or empty list"]
  }}
}}

Rules:
- part_number: look for codes like GB-2045, PN-123, P/N patterns in filename or description; null if absent
- name: use product_names if available, else infer cleanly from filename (strip extension, underscores)
- material: infer from description/materials list; low confidence (0.3-0.5) if guessed, null value if truly unknown
- category: classify the part type from geometry and name context
- dimensions: use bounding box to construct a concise string; null if no spatial data
- revision: look for revision letters in filename (v2, rev_b, _B) or products revisions list
- volume: estimate from bounding box if available; confidence 0.5-0.7 for estimates
- provenance.sources: list actual data sources used (e.g. "filename", "STEP header", "geometry parser")
- provenance.warnings: note data quality issues (missing units, low confidence, sparse metadata)"""

    try:
        client = anthropic.Anthropic(api_key=api_key)
        message = client.messages.create(
            model=_MODEL,
            max_tokens=512,
            messages=[{"role": "user", "content": prompt}],
        )
        text = message.content[0].text.strip()
        if text.startswith("```"):
            parts = text.split("```")
            text = parts[1]
            if text.startswith("json"):
                text = text[4:]
        return json.loads(text.strip())
    except Exception:
        return {}
