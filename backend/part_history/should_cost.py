"""A simple material + process + volume should-cost range (SCRUM-30).

A second, explainable estimate next to the historical one: material cost
(mass x $/kg x scrap) plus process cost (run cost per part + setup spread
over the batch). Every rate comes from the small reference tables below,
which are SAMPLE / ASSUMED values to be replaced with real ones. The range
widens when the material or process is unknown or the volume is low.
"""

from decimal import ROUND_HALF_UP, Decimal

from bom_agent.bom_extraction import find_material, infer_process

_CENTS = Decimal("0.01")
REFERENCE_NOTE = "SAMPLE / ASSUMED reference values — replace with your own rates"

# $/kg of raw stock by material family (ASSUMED, rough 2026 market levels).
MATERIAL_RATES = {
    "aluminum": {"usd_per_kg": Decimal("4.50"), "basis": "Aluminum bar/plate, assumed $4.50/kg"},
    "stainless": {"usd_per_kg": Decimal("6.00"), "basis": "Stainless bar, assumed $6.00/kg"},
    "steel": {"usd_per_kg": Decimal("1.80"), "basis": "Carbon/alloy steel bar, assumed $1.80/kg"},
    "plastic": {"usd_per_kg": Decimal("3.00"), "basis": "Engineering resin, assumed $3.00/kg"},
    "other metal": {"usd_per_kg": Decimal("15.00"), "basis": "Brass/copper/titanium blend, assumed $15/kg"},
}
UNKNOWN_MATERIAL = {"usd_per_kg": Decimal("5.00"), "basis": "Material unknown, assumed $5.00/kg"}

# Per process: assumed mass, scrap/buy-to-fly factor, run cost per part, one-off setup per batch (ASSUMED).
PROCESS_RATES = {
    "machined": {"mass_kg": Decimal("0.30"), "scrap": Decimal("1.6"), "run": Decimal("12.00"),
                 "setup": Decimal("150"), "basis": "CNC machining, assumed $12/part run + $150 setup"},
    "sheet metal": {"mass_kg": Decimal("0.40"), "scrap": Decimal("1.3"), "run": Decimal("4.00"),
                    "setup": Decimal("100"), "basis": "Laser cut + brake form, assumed $4/part run + $100 setup"},
    "casting": {"mass_kg": Decimal("0.80"), "scrap": Decimal("1.2"), "run": Decimal("6.00"),
                "setup": Decimal("400"), "basis": "Casting + finish machining, assumed $6/part run + $400 setup"},
    "injection molded": {"mass_kg": Decimal("0.05"), "scrap": Decimal("1.05"), "run": Decimal("0.60"),
                         "setup": Decimal("300"), "basis": "Injection molding (tool not included), assumed $0.60/part + $300 setup"},
    "purchased": {"mass_kg": Decimal("0.01"), "scrap": Decimal("1.0"), "run": Decimal("0.25"),
                  "setup": Decimal("0"), "basis": "Catalog/purchased part, assumed $0.25 handling"},
    "assembly": {"mass_kg": Decimal("0"), "scrap": Decimal("1.0"), "run": Decimal("8.00"),
                 "setup": Decimal("50"), "basis": "Assembly labor only, assumed $8/assy + $50 setup"},
}
UNKNOWN_PROCESS = {"mass_kg": Decimal("0.30"), "scrap": Decimal("1.4"), "run": Decimal("10.00"),
                   "setup": Decimal("150"), "basis": "Process unknown, assumed general fabrication $10/part + $150 setup"}

BASE_SPREAD = Decimal("0.20")  # +/-20% for a well-understood part
LOW_VOLUME = 50  # batches below this are treated as low volume


def _money(value: Decimal) -> str:
    return str(value.quantize(_CENTS, ROUND_HALF_UP))


def reference_table() -> dict:
    """The assumptions themselves, so the UI/export can show them."""
    return {
        "note": REFERENCE_NOTE,
        "materials": {k: {"usd_per_kg": str(v["usd_per_kg"]), "basis": v["basis"]} for k, v in MATERIAL_RATES.items()},
        "processes": {k: {**{f: str(v[f]) for f in ("mass_kg", "scrap", "run", "setup")}, "basis": v["basis"]}
                      for k, v in PROCESS_RATES.items()},
    }


def should_cost_row(row) -> dict:
    """Low / expected / high unit cost for one BOM line, with its basis."""
    quantity = max(int(getattr(row, "quantity", 1) or 1), 1)
    material_found = find_material(getattr(row, "material", "") or "")
    family = material_found[1] if material_found else None
    material = MATERIAL_RATES.get(family, UNKNOWN_MATERIAL)

    process_name = getattr(row, "process", "") or infer_process(
        getattr(row, "description", ""), getattr(row, "material", "")
    )
    process = PROCESS_RATES.get(process_name, UNKNOWN_PROCESS)

    material_cost = process["mass_kg"] * process["scrap"] * material["usd_per_kg"]
    setup_per_part = process["setup"] / quantity
    unit = material_cost + process["run"] + setup_per_part

    spread, widened = BASE_SPREAD, []
    if not family:
        spread += Decimal("0.15")
        widened.append("material not recognised")
    if process_name not in PROCESS_RATES:
        spread += Decimal("0.15")
        widened.append("process unknown")
    if quantity < LOW_VOLUME:
        spread += Decimal("0.20")
        widened.append(f"low volume ({quantity} < {LOW_VOLUME})")

    basis = [
        f"Material: {material['basis']} x {process['mass_kg']} kg assumed mass x {process['scrap']} scrap factor"
        f" = ${_money(material_cost)}",
        f"Process: {process['basis']}; setup spread over {quantity} = ${_money(setup_per_part)}/part",
        f"Range ±{spread:.0%}" + (f", widened for {', '.join(widened)}" if widened else ""),
        "⚠ " + REFERENCE_NOTE,
    ]
    confidence = "medium" if not widened else "low" if len(widened) > 1 else "medium-low"
    return {
        "low": _money(unit * (1 - spread)),
        "expected": _money(unit),
        "high": _money(unit * (1 + spread)),
        "currency": "USD",
        "spread": float(spread),
        "material": family or "unknown",
        "process": process_name or "unknown",
        "quantity": quantity,
        "basis": basis,
        "confidence": confidence,
        "is_assumed": True,
    }
