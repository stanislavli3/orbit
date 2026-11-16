"""Side by side: a current part (BOM line or Part) next to a prior-program part (SCRUM-53)."""

from .models import Part

ATTRIBUTES = [
    ("part_number", "Part number"),
    ("description", "Description"),
    ("material", "Material"),
    ("process", "Process"),
    ("dimensions", "Dimensions"),
    ("mass", "Mass"),
    ("unit_cost", "Latest unit cost"),
    ("program", "Program / year"),
]


def part_side(part: Part) -> dict:
    cost = part.costs.select_related("supplier").first()
    values = {f: getattr(part, f) for f in ("part_number", "description", "material", "process", "dimensions", "mass")}
    values["unit_cost"] = f"${cost.unit_cost:.2f}" if cost else ""
    values["program"] = " ".join(str(x) for x in (cost.program, cost.model_year) if x) if cost else ""
    return {
        "kind": "part",
        "id": part.id,
        "link": f"/api/parts/{part.id}/",
        "values": values,
        "sources": {"unit_cost": cost.source, "program": cost.source} if cost else {},
    }


def row_side(row) -> dict:
    values = {f: getattr(row, f) for f in ("part_number", "description", "material", "process")}
    values.update(dimensions=row.spec, mass="", unit_cost="", program=row.bom.project.name)
    sources = {k: v for k, v in (row.sources or {}).items() if k in values}
    sources.setdefault("program", row.bom.reference)
    return {
        "kind": "bom_row",
        "id": row.id,
        "link": f"/boms/{row.bom_id}",
        "values": values,
        "sources": sources,
    }


def compare(left: dict, right: dict) -> dict:
    return {
        "left": left,
        "right": right,
        "rows": [
            {
                "key": key,
                "label": label,
                "left": left["values"][key] or "",
                "right": right["values"][key] or "",
                "same": bool(left["values"][key])
                and str(left["values"][key]).strip().lower() == str(right["values"][key]).strip().lower(),
            }
            for key, label in ATTRIBUTES
        ],
    }
