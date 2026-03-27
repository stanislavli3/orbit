"""
Lightweight STEP file header parser.
No external dependencies — pure Python regex on the first 8 KB of the file.
Extracts FILE_DESCRIPTION, FILE_NAME, FILE_SCHEMA from the STEP header section.
"""

import re
from datetime import datetime, timezone


def _parse_step_string(raw: str) -> str:
    """Strip outer quotes and unescape STEP string literals."""
    raw = raw.strip()
    if raw.startswith("'") and raw.endswith("'"):
        raw = raw[1:-1]
    return raw.replace("\\n", "\n").replace("\\'", "'").strip()


def _first_list_item(raw: str) -> str:
    """Extract first item from a STEP list like ('item1','item2')."""
    m = re.search(r"'([^']*)'", raw)
    return m.group(1).strip() if m else ""


def _infer_units(schema: str) -> str | None:
    """Guess units from schema name heuristics."""
    s = schema.upper()
    if "MILS" in s or "MM" in s or "MILLIMETER" in s:
        return "mm"
    if "INCH" in s or "IN_" in s:
        return "in"
    if "CM" in s or "CENTIMETER" in s:
        return "cm"
    return None


def extract_step_header(file_bytes: bytes) -> dict:
    """
    Parse a STEP file's HEADER section and return a structured extraction result.

    Returns a dict with:
      schema, file_description, units_hint, confidence, warnings, extracted_at
    """
    warnings: list[str] = []
    text = file_bytes[:8000].decode("utf-8", errors="ignore")

    # Must start with the STEP magic
    if "ISO-10303-21" not in text:
        return {
            "schema": None,
            "file_description": None,
            "units_hint": None,
            "confidence": 0.0,
            "warnings": ["File does not appear to be a valid STEP (ISO-10303-21) file."],
            "extracted_at": datetime.now(timezone.utc).isoformat(),
        }

    # FILE_SCHEMA(('SCHEMA_NAME'));
    schema: str | None = None
    m = re.search(r"FILE_SCHEMA\s*\(\s*(\([^)]*\))\s*\)", text, re.IGNORECASE)
    if m:
        schema = _first_list_item(m.group(1)) or None

    # FILE_DESCRIPTION(('description text'),'2;1');
    file_description: str | None = None
    m = re.search(r"FILE_DESCRIPTION\s*\(\s*(\([^)]*\))", text, re.IGNORECASE)
    if m:
        desc = _first_list_item(m.group(1))
        file_description = desc if desc else None

    # Infer units from schema name
    units_hint: str | None = _infer_units(schema) if schema else None

    # Confidence: high if we got schema, medium if only description
    if schema and file_description:
        confidence = 0.9
    elif schema:
        confidence = 0.75
    elif file_description:
        confidence = 0.5
        warnings.append("Could not determine schema from FILE_SCHEMA record.")
    else:
        confidence = 0.3
        warnings.append("Could not parse FILE_SCHEMA or FILE_DESCRIPTION records.")

    if units_hint is None:
        warnings.append(
            "Could not infer units from schema name. "
            "Geometry extraction (OCC) required for definitive unit detection."
        )

    return {
        "schema": schema,
        "file_description": file_description,
        "units_hint": units_hint,
        "confidence": confidence,
        "warnings": warnings,
        "extracted_at": datetime.now(timezone.utc).isoformat(),
    }
