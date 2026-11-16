"""Galvanic material-pair flags (SCRUM-77). Plain functions, no Django.

Two dissimilar metals in contact (with moisture present) form a cell: the
more anodic one corrodes. We flag touching parts whose anodic indices differ
by more than a threshold and suggest a mitigation.

The anodic index table is a REFERENCE APPROXIMATION of the commonly published
galvanic series (e.g. MIL-STD-889 style tables, in volts relative to gold).
Values vary with alloy, temper, surface finish and electrolyte; confirm with
a materials engineer before acting on a flag.
"""

import math
import re
from itertools import combinations

REFERENCE_NOTE = (
    "Anodic index values are a reference approximation of the published galvanic series "
    "(V vs gold). Confirm with a materials engineer."
)

# Threshold on the anodic-index difference (V) above which a pair is flagged.
THRESHOLDS = {"general": 0.25, "harsh": 0.15}

# (regex on upper-cased material/description, label, anodic index V). First match wins,
# so more specific patterns come first.
ANODIC_INDEX = [
    (r"\bGOLD\b", "Gold", 0.00),
    (r"\bSILVER\b", "Silver", 0.15),
    (r"\bTITANIUM\b|\bTI-6AL-4V\b", "Titanium", 0.15),
    (r"\bNICKEL\b|\bMONEL\b|\bINCONEL\b", "Nickel alloy", 0.30),
    (r"\bCOPPER\b", "Copper", 0.35),
    (r"\bBRASS\b|\bBRONZE\b", "Brass / bronze", 0.40),
    (r"\b(?:SS|STAINLESS(?:\s+STEEL)?)[\s-]*(?:303|304L?|316L?)\b|\bSTAINLESS\b|\b(?:303|304L?|316L?)\s*SS\b",
     "Stainless steel 300 series (passive)", 0.50),
    (r"\b17-4\b|\b4[01]0\s*SS\b|\bSS[\s-]*4[01]0\b", "Stainless steel 400 / 17-4", 0.60),
    (r"\bGALVANI[SZ]ED\b|\bZINC\b|\bZN\b", "Zinc / galvanized", 1.20),
    (r"\bMAGNESIUM\b|\bAZ31\b|\bAZ91\b", "Magnesium", 1.75),
    (r"\b(?:AL(?:UMINUM|UMINIUM)?[\s-]*)?2024\b", "Aluminium 2000 series", 0.75),
    (r"\bCAST\b.*\bAL(?:UMINUM|UMINIUM)?\b|\bA356\b|\bA380\b", "Cast aluminium", 0.95),
    (r"\b(?:AL(?:UMINUM|UMINIUM)?[\s-]*)?(?:6061|6063|7075|5052)\b|\bALUMINUM\b|\bALUMINIUM\b",
     "Aluminium (wrought, non-2000)", 0.90),
    (r"\b(?:STEEL|AISI|SAE)[\s-]*(?:1018|1020|1045|4140|4340|A36)\b|\b(?:1018|1045|4140|4340)\b"
     r"|\bCARBON STEEL\b|\bSTEEL\b|\bIRON\b", "Carbon steel / iron", 0.85),
]

_FASTENER = re.compile(r"\b(SCREW|BOLT|NUT|WASHER|RIVET|SHCS|STUD|FASTENER)\b|\bM\d+(?:\.\d+)?\s*X\s*\d")


def classify(material: str) -> dict | None:
    """The galvanic class of a material callout, or None if it isn't a recognised metal."""
    text = (material or "").upper()
    for pattern, label, index in ANODIC_INDEX:
        if re.search(pattern, text):
            return {"label": label, "anodic_index": index}
    return None


def _is_fastener(row: dict) -> bool:
    return bool(_FASTENER.search(f"{row.get('description', '')} {row.get('part_number', '')}".upper()))


def pair_flag(row_a: dict, row_b: dict, environment: str = "general") -> dict | None:
    """A flag for two touching parts, or None when the pair is fine or unknown.

    Rows are dicts with at least part_number, description and material.
    """
    a = classify(row_a.get("material") or row_a.get("description"))
    b = classify(row_b.get("material") or row_b.get("description"))
    if not a or not b:
        return None
    diff = round(abs(a["anodic_index"] - b["anodic_index"]), 2)
    threshold = THRESHOLDS.get(environment, THRESHOLDS["general"])
    if diff <= threshold:
        return None

    anode_row, anode = (row_a, a) if a["anodic_index"] > b["anodic_index"] else (row_b, b)
    cathode_row, cathode = (row_b, b) if anode_row is row_a else (row_a, a)
    # A small anode (e.g. a fastener) against a large cathode corrodes fastest.
    small_anode = _is_fastener(anode_row) and not _is_fastener(cathode_row)
    severity = "high" if diff >= 0.5 or small_anode else "medium"

    fastener = next((r for r in (row_a, row_b) if _is_fastener(r)), None)
    mitigations = [
        "Isolate the contact: non-conductive washer, sleeve or gasket (e.g. nylon, G10)",
        f"Coat or plate the anodic part ({anode['label']}): anodize, zinc-nickel or sealant at the joint",
    ]
    if fastener:
        other = row_b if fastener is row_a else row_a
        mitigations.append(
            f"Change the fastener material to match or sit close to {other.get('material') or 'the mating part'}"
        )
    else:
        mitigations.append("Choose mating materials closer together in the galvanic series")

    return {
        "kind": "galvanic",
        "severity": severity,
        "environment": environment,
        "parts": [row_a.get("part_number", ""), row_b.get("part_number", "")],
        "materials": [row_a.get("material", ""), row_b.get("material", "")],
        "anodic_index": [a["anodic_index"], b["anodic_index"]],
        "difference_v": diff,
        "threshold_v": threshold,
        "corrodes": anode_row.get("part_number", ""),
        "title": f"Galvanic pair: {anode['label']} vs {cathode['label']}",
        "detail": (
            f"{anode_row.get('part_number')} ({anode['label']}, {anode['anodic_index']:.2f} V) touches "
            f"{cathode_row.get('part_number')} ({cathode['label']}, {cathode['anodic_index']:.2f} V): "
            f"difference {diff:.2f} V > {threshold:.2f} V allowed for a {environment} environment. "
            f"{anode_row.get('part_number')} is the anode and will corrode"
            + (" (small anode, large cathode)." if small_anode else ".")
        ),
        "mitigations": mitigations,
    }


def contact_pairs(rows: list[dict], occurrences: list[dict] | None = None, radius: float = 50) -> tuple[str, list]:
    """Pairs of row indices treated as touching, and the method used.

    With STEP placements: parts placed within ``radius`` of each other. With
    assembly structure only: parts under the same parent. Without an assembly:
    a flat BOM is treated as one subassembly, so every pair is checked.
    """
    from .design_change import part_key

    index = {}
    for i, r in enumerate(rows):
        index.setdefault(part_key(r.get("part_number")), i)
    occs = [o for o in (occurrences or []) if part_key(o["part_number"]) in index]
    pairs = set()
    if occs:
        positioned = [o for o in occs if o["position"]]
        if len(positioned) >= 2:
            method = "placement_distance"
            for x, y in combinations(positioned, 2):
                if math.dist(x["position"], y["position"]) <= radius:
                    pairs.add((x["part_number"], y["part_number"]))
        else:
            method = "assembly_structure"
            for x, y in combinations(occs, 2):
                if x["parent"] == y["parent"]:
                    pairs.add((x["part_number"], y["part_number"]))
        out = set()
        for pa, pb in pairs:
            ia, ib = index[part_key(pa)], index[part_key(pb)]
            if ia != ib:
                out.add((min(ia, ib), max(ia, ib)))
        return method, sorted(out)
    return "same_bom", list(combinations(range(len(rows)), 2))


def galvanic_flags(rows: list[dict], occurrences=None, environment: str = "general", radius: float = 50) -> dict:
    method, pairs = contact_pairs(rows, occurrences, radius)
    flags = [f for i, j in pairs if (f := pair_flag(rows[i], rows[j], environment))]
    flags.sort(key=lambda f: (f["severity"] != "high", -f["difference_v"]))
    return {
        "method": method,
        "environment": environment,
        "threshold_v": THRESHOLDS.get(environment, THRESHOLDS["general"]),
        "flags": flags,
        "note": REFERENCE_NOTE,
        "table": [{"material": label, "anodic_index": idx} for _, label, idx in ANODIC_INDEX],
    }
