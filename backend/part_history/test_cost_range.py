"""SCRUM-73 unified low/likely/high range and SCRUM-74 price-surprise flags."""

from decimal import Decimal
from types import SimpleNamespace

from part_history.cost_range import cost_range, price_flag
from part_history.test_quick_estimate import _post, project, seeded  # noqa: F401  (fixtures)

SC = {"low": "8.00", "expected": "10.00", "high": "12.00", "basis": ["Material: x", "Process: y"], "is_assumed": True}


def _match(pn, cost, sim=0.8):
    return {"part_number": pn, "description": "d", "similarity": sim, "adjusted_unit_cost": cost,
            "cost": {"source": "ERP 2023", "model_year": 2023, "program": "P", "is_sample": False}}


def test_model_only_range_when_no_history():
    r = cost_range({"matches": [], "estimate": None}, SC)
    assert (r["low"], r["likely"], r["high"]) == ("8.00", "10.00", "12.00")
    assert r["basis"] == "model" and r["rates"] == SC["basis"]


def test_combined_range_spans_history_and_model_with_sources():
    est = {"matches": [_match("A-1", "20.00")], "confidence": "high",
           "estimate": {"unit_cost": "20.00", "based_on": ["A-1"]}}
    r = cost_range(est, SC)
    assert r["likely"] == "18.00"  # 80% x 20 + 20% x 10
    assert r["low"] == "8.00" and r["high"] == "20.00"
    assert r["similar_parts"][0]["source"] == "ERP 2023"
    assert r["basis"] == "history + model"


def test_price_flags():
    rng = {"low": "10.00", "high": "20.00"}
    row = lambda p, n="": SimpleNamespace(entered_price=p, entered_price_note=n)  # noqa: E731
    assert price_flag(row(None), rng) is None
    assert price_flag(row(Decimal("9")), rng, 0.3)["level"] == "ok"
    low = price_flag(row(Decimal("5"), "Amazon/off-the-shelf"), rng, 0.3)
    assert low["level"] == "far_below" and "50% below" in low["message"]
    assert "Amazon/off-the-shelf" in low["message"] and "likely $10.00–$20.00" in low["message"]
    assert price_flag(row(Decimal("30")), rng, 0.3)["level"] == "far_above"
    assert price_flag(row(Decimal("6")), rng, 0.5)["level"] == "ok"  # margin is configurable


def test_enter_price_and_flag_in_report(auth_client, seeded, project):  # noqa: F811
    report = _post(auth_client, project).json()
    bom_id, first = report["bom"]["id"], report["rows"][0]
    assert {"low", "likely", "high", "similar_parts", "rates"} <= set(first["cost_range"])
    assert report["price_flags"]["priced"] == 0
    res = auth_client.patch(f"/api/parts/rows/{first['row_id']}/price/",
                            {"entered_price": "0.01", "entered_price_note": "prototype, Amazon"}, format="json")
    assert res.status_code == 200
    again = auth_client.get(f"/api/parts/quick-estimate/{bom_id}/").json()
    assert again["rows"][0]["price_flag"]["level"] == "far_below"
    assert again["rows"][0]["row"]["entered_price"] == "0.01"
    assert again["price_flags"] == {"margin": 0.3, "priced": 1, "far_below": 1, "far_above": 0}
    assert auth_client.get(f"/api/parts/quick-estimate/{bom_id}/?margin=2").status_code == 400
    assert auth_client.patch(f"/api/parts/rows/{first['row_id']}/price/", {"entered_price": "abc"},
                             format="json").status_code == 400
    auth_client.patch(f"/api/parts/rows/{first['row_id']}/price/", {"entered_price": None}, format="json")
    assert auth_client.get(f"/api/parts/quick-estimate/{bom_id}/").json()["price_flags"]["priced"] == 0
