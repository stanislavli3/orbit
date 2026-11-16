"""
Design change review (SCRUM-23, SCRUM-55). Plain functions, no Django.

- ``diff_rows``: what changed between two versions of a BOM (added / removed /
  changed parts, field by field), keyed by part number.
- ``find_conflicts``: across several BOMs of one project, components whose
  part number, revision, material or tolerance callout disagree between files.
- ``neighbours``: parts near a changed part in a STEP assembly, by placement
  distance when the file has positions, else by assembly structure.

Rows are dicts with the BomRow fields plus ``bom`` (a citation dict naming the
BOM and file they came from). Every flag cites the rows it is based on.
"""

import math
import re
from collections import defaultdict

from .bom_extraction import _args, _ref, _statements, _str

COMPARED_FIELDS = ("description", "material", "process", "quantity", "spec", "revision")


def part_key(part_number: str) -> str:
    """Part numbers that differ only in case, spaces or punctuation are the same part."""
    return re.sub(r"[^A-Z0-9]", "", (part_number or "").upper())


def _norm(value) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip().upper()


def cite(row: dict) -> dict:
    """Where a row came from: BOM, file and line."""
    return {**row["bom"], "row_id": row.get("id"), "line_no": row.get("line_no"), "part_number": row["part_number"]}


# ── SCRUM-23: change summary ─────────────────────────────────────────────────

def diff_rows(old: list[dict], new: list[dict]) -> dict:
    old_by = {part_key(r["part_number"]): r for r in old if part_key(r["part_number"])}
    new_by = {part_key(r["part_number"]): r for r in new if part_key(r["part_number"])}
    added = [{"part_number": r["part_number"], "row": cite(r)} for k, r in new_by.items() if k not in old_by]
    removed = [{"part_number": r["part_number"], "row": cite(r)} for k, r in old_by.items() if k not in new_by]
    changed = []
    for k, before in old_by.items():
        after = new_by.get(k)
        if not after:
            continue
        fields = [
            {"field": f, "before": before.get(f), "after": after.get(f)}
            for f in COMPARED_FIELDS
            if _norm(before.get(f)) != _norm(after.get(f))
        ]
        if fields:
            changed.append({
                "part_number": after["part_number"],
                "fields": fields,
                "rows": [cite(before), cite(after)],
            })
    unchanged = sum(1 for k in old_by if k in new_by) - len(changed)
    parts = [f"{len(added)} added", f"{len(removed)} removed", f"{len(changed)} changed", f"{unchanged} unchanged"]
    return {"summary": ", ".join(parts), "added": added, "removed": removed, "changed": changed}


# ── SCRUM-23: cross-file conflicts ───────────────────────────────────────────

_CONFLICT_FIELDS = (
    ("revision", "revision", "Revision conflict"),
    ("material", "material", "Contradictory material callout"),
    ("spec", "tolerance", "Contradictory tolerance / spec callout"),
)


def find_conflicts(rows: list[dict]) -> list[dict]:
    """Flags for the same component described differently in different files.

    Only values that are present are compared: a file that is silent on a
    material doesn't contradict one that names it.
    """
    flags = []
    by_part = defaultdict(list)
    for r in rows:
        if part_key(r["part_number"]):
            by_part[part_key(r["part_number"])].append(r)

    for group in by_part.values():
        if len({r["bom"]["bom_id"] for r in group}) < 2:
            continue
        spellings = {r["part_number"].strip() for r in group}
        if len(spellings) > 1:
            flags.append(_flag("part_number", "Part-number mismatch", group,
                               f"Written as {', '.join(sorted(spellings))} in different files"))
        for field, kind, title in _CONFLICT_FIELDS:
            with_value = [r for r in group if _norm(r.get(field))]
            values = {_norm(r[field]) for r in with_value}
            if len(values) > 1:
                shown = sorted({str(r[field]).strip() for r in with_value})
                flags.append(_flag(kind, title, with_value,
                                   f"{group[0]['part_number']}: {' vs '.join(shown)}"))

    # Same component (same description) under different part numbers.
    by_desc = defaultdict(list)
    for r in rows:
        if len(_norm(r.get("description"))) >= 4:
            by_desc[_norm(r["description"])].append(r)
    for group in by_desc.values():
        keys = {part_key(r["part_number"]) for r in group}
        if len(keys) > 1 and len({r["bom"]["bom_id"] for r in group}) > 1:
            numbers = sorted({r["part_number"] or "(none)" for r in group})
            flags.append(_flag("part_number", "Part-number mismatch", group,
                               f"'{group[0]['description']}' has part numbers {', '.join(numbers)}"))
    return flags


def _flag(kind, title, rows, detail):
    return {"kind": kind, "title": title, "detail": detail, "citations": [cite(r) for r in rows]}


# ── SCRUM-55: affected neighbours ────────────────────────────────────────────

def _entities(data: bytes) -> dict[int, tuple[str, str]]:
    """id -> (entity name, raw argument text). Complex entities get name ''."""
    out = {}
    for statement in _statements(data.decode("utf-8", errors="ignore")):
        m = re.match(r"#(\d+)\s*=\s*([A-Z0-9_]*)\s*\((.*)\)\s*$", statement, re.S | re.I)
        if m:
            out[int(m.group(1))] = (m.group(2).upper(), m.group(3))
    return out


def assembly_occurrences(data: bytes) -> list[dict]:
    """One dict per placed part occurrence: part_number, parent, position (x, y, z) or None.

    Positions come from CONTEXT_DEPENDENT_SHAPE_REPRESENTATION → ITEM_DEFINED_TRANSFORMATION
    → AXIS2_PLACEMENT_3D → CARTESIAN_POINT, relative to the parent assembly.
    """
    ents = _entities(data)

    def args(i, name):
        e = ents.get(i)
        return _args(e[1]) if e and e[0] == name else None

    product_pn = {i: _str(_args(raw)[0]) for i, (n, raw) in ents.items() if n == "PRODUCT"}
    formation = {i: product_pn.get(_ref(a[2])) for i, (n, raw) in ents.items()
                 if n == "PRODUCT_DEFINITION_FORMATION" and len(a := _args(raw)) > 2}
    pd_pn = {i: formation.get(_ref(a[2])) for i, (n, raw) in ents.items()
             if n == "PRODUCT_DEFINITION" and len(a := _args(raw)) > 2}

    def point_of(placement_id):
        a = args(placement_id, "AXIS2_PLACEMENT_3D")
        p = args(_ref(a[1]), "CARTESIAN_POINT") if a and len(a) > 1 else None
        if not p or len(p) < 2:
            return None
        try:
            coords = [float(c) for c in p[1].strip("()").split(",")]
        except ValueError:
            return None
        return tuple((coords + [0.0, 0.0])[:3])

    # NAUO id -> position, via its PRODUCT_DEFINITION_SHAPE and CDSR.
    position = {}
    for i, (n, raw) in ents.items():
        if n != "CONTEXT_DEPENDENT_SHAPE_REPRESENTATION":
            continue
        a = _args(raw)
        pds = args(_ref(a[1]), "PRODUCT_DEFINITION_SHAPE") if len(a) > 1 else None
        nauo = _ref(pds[2]) if pds and len(pds) > 2 else None
        relation = ents.get(_ref(a[0]))
        if not nauo or not relation:
            continue
        for ref in re.findall(r"#(\d+)", relation[1]):
            idt = args(int(ref), "ITEM_DEFINED_TRANSFORMATION")
            if idt and len(idt) > 3 and (pt := point_of(_ref(idt[3]))):
                position[nauo] = pt

    occurrences = []
    for i, (n, raw) in ents.items():
        if n != "NEXT_ASSEMBLY_USAGE_OCCURRENCE":
            continue
        a = _args(raw)
        if len(a) > 4 and pd_pn.get(_ref(a[4])):
            occurrences.append({
                "id": i,
                "part_number": pd_pn[_ref(a[4])],
                "parent": pd_pn.get(_ref(a[3])) or "",
                "position": position.get(i),
            })
    return occurrences


def neighbours(data: bytes, part_number: str, radius: float) -> dict:
    """Parts to recheck when ``part_number`` changes, and the method used to find them."""
    occs = assembly_occurrences(data)
    key = part_key(part_number)
    mine = [o for o in occs if part_key(o["part_number"]) == key]
    if not mine:
        return {"method": "not_in_assembly", "radius": radius, "parts": []}
    others = [o for o in occs if part_key(o["part_number"]) != key]

    if all(o["position"] for o in mine) and any(o["position"] for o in others):
        nearest = {}
        for o in others:
            if not o["position"]:
                continue
            d = min(math.dist(m["position"], o["position"]) for m in mine)
            if d <= radius and d < nearest.get(o["part_number"], math.inf):
                nearest[o["part_number"]] = d
        parts = [{"part_number": pn, "distance": round(d, 2), "reason": f"within {radius:g} of the changed part"}
                 for pn, d in sorted(nearest.items(), key=lambda x: x[1])]
        return {"method": "placement_distance", "radius": radius, "parts": parts}

    parents = {m["parent"] for m in mine}
    siblings = sorted({o["part_number"] for o in others if o["parent"] in parents})
    parts = [{"part_number": pn, "distance": None, "reason": "same parent subassembly"} for pn in siblings]
    return {"method": "assembly_structure", "radius": radius, "parts": parts}
