"""One labelled low / likely / high should-cost range per BOM line (SCRUM-73)
and price-surprise flags against it (SCRUM-74).

Combines the two existing estimates instead of re-deriving them:
  * history  — similar parts' inflation-adjusted costs (estimator.estimate_row)
  * model    — material + process + volume (should_cost.should_cost_row)
When both exist the range spans both, and "likely" is their average weighted
towards history when the historical match is strong. Every number keeps the
data behind it: similar parts with their sources, and the rates used.
"""

from decimal import ROUND_HALF_UP, Decimal

from django.conf import settings

_CENTS = Decimal("0.01")
# Flag an entered price this far below the low end (or above the high end).
DEFAULT_MARGIN = 0.30
HISTORY_WEIGHT = {"high": Decimal("0.8"), "medium": Decimal("0.6"), "low": Decimal("0.4")}


def default_margin() -> float:
    return float(getattr(settings, "PRICE_FLAG_MARGIN", DEFAULT_MARGIN))


def _money(v: Decimal) -> str:
    return str(v.quantize(_CENTS, ROUND_HALF_UP))


def cost_range(estimate: dict, should_cost: dict) -> dict:
    """``estimate`` is an estimate_row() result, ``should_cost`` a should_cost_row() result."""
    m_low, m_exp, m_high = (Decimal(should_cost[k]) for k in ("low", "expected", "high"))
    similar = [
        {
            "part_number": m["part_number"],
            "description": m["description"],
            "similarity": m["similarity"],
            "unit_cost": m["adjusted_unit_cost"],
            "source": m["cost"]["source"] or "historical cost import",
            "model_year": m["cost"]["model_year"],
            "program": m["cost"]["program"],
            "is_sample": m["cost"]["is_sample"],
        }
        for m in estimate.get("matches", [])
    ]
    rates = list(should_cost["basis"])
    est = estimate.get("estimate")
    if not est:
        low, likely, high = m_low, m_exp, m_high
        method = "Material + process model only (no similar historical parts)"
        basis = "model"
    else:
        hist = Decimal(est["unit_cost"])
        used = [Decimal(s["unit_cost"]) for s in similar if s["part_number"] in est["based_on"]] or [hist]
        w = HISTORY_WEIGHT.get(estimate.get("confidence"), Decimal("0.5"))
        likely = hist * w + m_exp * (1 - w)
        low = min(m_low, min(used), likely)
        high = max(m_high, max(used), likely)
        method = (f"Likely = {w:.0%} history (${_money(hist)} from {', '.join(est['based_on'])})"
                  f" + {1 - w:.0%} model (${_money(m_exp)}); range spans both")
        basis = "history + model"
    return {
        "low": _money(low),
        "likely": _money(likely),
        "high": _money(high),
        "currency": "USD",
        "basis": basis,
        "method": method,
        "history_unit_cost": est["unit_cost"] if est else None,
        "model_unit_cost": should_cost["expected"],
        "similar_parts": similar,
        "rates": rates,
        "uses_sample_data": bool(estimate.get("uses_sample_data")) or should_cost.get("is_assumed", False),
    }


def price_flag(row, rng: dict, margin: float | None = None) -> dict | None:
    """Compare a line's entered price with its range; None when no price was entered."""
    price = getattr(row, "entered_price", None)
    if price is None:
        return None
    margin = DEFAULT_MARGIN if margin is None else margin
    price = Decimal(price)
    low, high = Decimal(rng["low"]), Decimal(rng["high"])
    note = (getattr(row, "entered_price_note", "") or "").strip()
    priced_from = f"priced from {note}" if note else "entered price"
    span = f"${rng['low']}–${rng['high']}"
    flag = {"entered_price": _money(price), "note": note, "margin": margin, "level": "ok",
            "pct_from_range": 0.0, "message": f"${_money(price)} is within or near the should-cost range {span}."}
    if price < low * Decimal(str(1 - margin)):
        pct = float((low - price) / low) if low else 0.0
        flag.update(level="far_below", pct_from_range=round(-pct, 3), message=(
            f"${_money(price)} ({priced_from}) is {pct:.0%} below the low end of should-cost; "
            f"production cost likely {span}."))
    elif price > high * Decimal(str(1 + margin)):
        pct = float((price - high) / high) if high else 0.0
        flag.update(level="far_above", pct_from_range=round(pct, 3), message=(
            f"${_money(price)} ({priced_from}) is {pct:.0%} above the high end of should-cost {span}; "
            "check for prototype premiums or quote padding."))
    return flag


def flag_summary(rows: list[dict], margin: float) -> dict:
    flags = [r["price_flag"] for r in rows if r.get("price_flag")]
    return {
        "margin": margin,
        "priced": len(flags),
        "far_below": sum(f["level"] == "far_below" for f in flags),
        "far_above": sum(f["level"] == "far_above" for f in flags),
    }
