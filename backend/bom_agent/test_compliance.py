"""SCRUM-37/38 — standards corpus and per-BOM-line compliance check."""

import pytest

from bom_agent.compliance import check_row, load_corpus, parse_corpus
from bom_agent.models import Bom, BomRow
from projects.models import Project


def ids(result):
    return {f["rule"]["id"] for f in result["findings"] if f["rule"]}


def test_corpus_loads_and_is_labelled():
    corpus = load_corpus()
    assert "verify against the official standard" in corpus.label
    assert len(corpus.rules) >= 8
    for rule in corpus.rules:
        assert rule.citation and rule.explanation and rule.applies_to


def test_corpus_rejects_bad_rules():
    base = {"id": "X", "title": "t", "citation": "c", "outcome": "pass", "severity": "info", "explanation": "e"}
    with pytest.raises(ValueError):
        parse_corpus({"label": "l", "version": "1", "rules": [{**base, "applies_to": {"colour": ["red"]}}]})
    with pytest.raises(ValueError):
        parse_corpus({"label": "l", "version": "1", "rules": [{**base, "applies_to": {"material": ["x"]}, "outcome": "ok"}]})


def test_known_alloy_with_temper_passes_with_citation():
    result = check_row({"part_number": "ORB-1042", "description": "Bracket", "material": "6061-T6", "process": "machined"})
    assert result["status"] == "pass"
    finding = result["findings"][0]
    assert finding["rule"]["id"] == "MAT-AL-6061" and "ASTM B209" in finding["rule"]["citation"]


def test_alloy_without_temper_needs_info():
    result = check_row({"description": "Plate", "material": "6061"})
    assert result["status"] == "needs_info"
    assert "Temper" in result["findings"][0]["message"]


def test_missing_material_is_flagged_needs_info():
    result = check_row({"part_number": "P-1", "description": "Cover"})
    assert result["status"] == "needs_info"
    assert result["findings"][0]["rule"] is None and "No material" in result["findings"][0]["message"]


@pytest.mark.parametrize("spec,rule", [
    ("Zinc plate, yellow chromate", "ROHS-CR6"),
    ("Cadmium plated per QQ-P-416", "ROHS-CD"),
    ("Hexavalent chrome passivate", "ROHS-CR6"),
])
def test_restricted_finishes_warn(spec, rule):
    result = check_row({"description": "Shaft", "material": "1018 steel", "spec": spec})
    assert result["status"] == "warning"
    assert rule in ids(result)


def test_shcs_needs_fastener_standard_until_cited():
    row = {"part_number": "SHCS-M6X16", "description": "Socket head cap screw", "material": "steel 12.9"}
    assert "FAST-SHCS" in ids(check_row(row))
    assert check_row(row)["status"] == "needs_info"
    assert check_row({**row, "spec": "ISO 4762"})["status"] == "pass"


def test_aerospace_keyword_warns_about_certification():
    result = check_row({"description": "Flight control bracket", "material": "7075-T73", "spec": "AMS 4045"})
    assert "CERT-AERO" in ids(result) and result["status"] == "warning"


def test_unknown_material_needs_manual_check():
    result = check_row({"description": "Gasket", "material": "EPDM"})
    assert result["status"] == "needs_info" and result["findings"][0]["rule"] is None


# ── Endpoints ────────────────────────────────────────────────────────────────

@pytest.fixture
def bom(db, user):
    project = Project.objects.create(owner=user, name="Demo")
    bom = Bom.objects.create(project=project, source_name="bracket.step", status="needs_review")
    BomRow.objects.create(bom=bom, line_no=1, part_number="ORB-1042", material="6061-T6")
    BomRow.objects.create(bom=bom, line_no=2, part_number="ORB-1043", material="")
    BomRow.objects.create(bom=bom, line_no=3, part_number="PIN-1", material="1018", spec="cadmium plated")
    return bom


def test_compliance_endpoint(auth_client, bom):
    data = auth_client.get(f"/api/bom/structured/{bom.pk}/compliance/").json()
    assert data["reference"] == bom.reference
    assert "verify against the official standard" in data["corpus"]["label"]
    assert [line["status"] for line in data["lines"]] == ["pass", "needs_info", "warning"]
    assert data["summary"] == {"pass": 1, "warning": 1, "needs_info": 1}
    cited = [f for f in data["lines"][2]["findings"] if f["rule"]]
    assert any(f["rule"]["id"] == "ROHS-CD" for f in cited)


def test_compliance_endpoint_is_owner_only(api_client, other_user, bom):
    api_client.force_authenticate(other_user)
    assert api_client.get(f"/api/bom/structured/{bom.pk}/compliance/").status_code == 404


def test_standards_corpus_endpoint(auth_client):
    data = auth_client.get("/api/bom/standards/").json()
    assert "verify against the official standard" in data["label"]
    assert {r["id"] for r in data["rules"]} >= {"FAST-SHCS", "ROHS-CR6", "CERT-AUTO"}
