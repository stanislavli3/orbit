"""
Generate a plain-English description of an uploaded engineering file using Claude.
Called once, synchronously, inside the background extraction thread.
Returns an empty string on any error so the caller never crashes.
"""

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
