"""SCRUM-30 should-cost range and SCRUM-36 estimate-stages Excel export."""

import io
from decimal import Decimal
from types import SimpleNamespace

import pytest
from openpyxl import load_workbook

from part_history.should_cost import should_cost_row
from part_history.stages_export import quote_status
from part_history.test_quick_estimate import _post, project, seeded  # noqa: F401  (fixtures)


def row(**kw):
    return SimpleNamespace(**{"part_number": "", "description": "", "material": "", "process": "", "quantity": 100, **kw})


def test_range_is_ordered_and_cites_its_basis():
    sc = should_cost_row(row(material="AL 6061-T6", process="machined"))
    low, exp, high = (Decimal(sc[k]) for k in ("low", "expected", "high"))
    assert low < exp < high
    # 0.30 kg x 1.6 x $4.50 = 2.16 material; $12 run; $150 setup over 100/assy x 500 assemblies
    assert exp == Decimal("14.16")
    assert sc["volume"] == 100 * sc["build_volume"]
    assert sc["material"] == "aluminum" and sc["process"] == "machined"
    assert any(b.startswith("Material: Aluminum") for b in sc["basis"])
    assert any(b.startswith("Process: CNC machining") for b in sc["basis"])
    assert any("SAMPLE / ASSUMED" in b for b in sc["basis"])
    assert sc["spread"] == pytest.approx(0.20)


def test_setup_is_spread_over_production_volume_not_bom_quantity(settings):
    """BOM quantity is per assembly; 4 per assembly must not mean a 4-part batch."""
    settings.SHOULD_COST_BUILD_VOLUME = 500
    sc = should_cost_row(row(material="6061-T6", process="machined", quantity=4))
    assert sc["volume"] == 2000
    assert Decimal(sc["expected"]) < Decimal("15")  # not $12 run + $150/4 setup
    assert "low volume" not in sc["basis"][2]


def test_range_widens_for_unknown_and_low_volume_parts(settings):
    settings.SHOULD_COST_BUILD_VOLUME = 10  # a prototype run
    known = should_cost_row(row(material="6061-T6", process="machined"))
    odd = should_cost_row(row(material="unobtainium", process="", quantity=2))
    assert odd["spread"] > known["spread"]
    assert odd["spread"] == pytest.approx(0.70)
    assert odd["confidence"] == "low"
    assert "low volume" in odd["basis"][2] and "material not recognised" in odd["basis"][2]


def test_infers_process_when_missing():
    assert should_cost_row(row(description="SHCS M6x16", material="steel 4140"))["process"] == "purchased"


def test_quote_status():
    assert quote_status(1, 2, 3) == "Beats"
    assert quote_status(2.5, 2, 3) == "Meets"
    assert quote_status(4, 2, 3) == "Exceeds"


def test_quick_report_includes_should_cost(auth_client, seeded, project):  # noqa: F811
    report = _post(auth_client, project).json()
    for r in report["rows"]:
        assert set(r["should_cost"]) >= {"low", "expected", "high", "basis"}


def test_stages_export_xlsx(auth_client, seeded, project):  # noqa: F811
    bom_id = _post(auth_client, project).json()["bom"]["id"]
    res = auth_client.get(f"/api/parts/estimate/bom/{bom_id}/stages.xlsx")
    assert res.status_code == 200
    assert res["Content-Type"].startswith("application/vnd.openxmlformats")
    wb = load_workbook(io.BytesIO(res.content))
    sheet = wb["Estimate Stages"]
    headers = [c.value for c in sheet[1]]
    assert headers.index("Quote unit price") == headers.index("Should-cost high") + 3
    rows = [dict(zip(headers, (c.value for c in r))) for r in sheet.iter_rows(min_row=2)]
    bracket = [r for r in rows if r["Part number"] == "ORB-1042" and r["Supplier"]]
    assert bracket and all(r["Quote vs should-cost"] in {"Beats", "Meets", "Exceeds"} for r in bracket)
    assert bracket[0]["Historical estimate"] is not None
    assert any(r["Quote vs should-cost"] == "No quote yet" for r in rows)
    assert len(sheet.conditional_formatting) >= 1


def test_stages_export_scoped_to_owner(api_client, other_user, auth_client, seeded, project):  # noqa: F811
    bom_id = _post(auth_client, project).json()["bom"]["id"]
    api_client.force_authenticate(other_user)
    assert api_client.get(f"/api/parts/estimate/bom/{bom_id}/stages.xlsx").status_code == 404
