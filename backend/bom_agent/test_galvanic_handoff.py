"""SCRUM-77 (galvanic material pairs) and SCRUM-69 (buyer handoff view)."""

from unittest.mock import patch

import pytest

from bom_agent.galvanic import classify, contact_pairs, galvanic_flags, pair_flag
from bom_agent.handoff import explain_row, open_questions
from bom_agent.models import Bom, BomRow
from projects.models import Project


def r(pn, material, description=""):
    return {"part_number": pn, "material": material, "description": description}


# ── SCRUM-77 ─────────────────────────────────────────────────────────────────

def test_classify_known_metals_and_ignores_plastics():
    assert classify("6061-T6")["anodic_index"] == 0.90
    assert classify("SS 304")["anodic_index"] == 0.50
    assert classify("ABS") is None


def test_aluminium_vs_stainless_fastener_is_flagged():
    flag = pair_flag(r("ORB-1042", "6061-T6", "Bracket"), r("SCR-1", "SS 304", "Screw M5 x 12"))
    assert flag and flag["difference_v"] == 0.40
    assert flag["corrodes"] == "ORB-1042"
    assert flag["severity"] == "medium"
    assert any("fastener material" in m for m in flag["mitigations"])


def test_aluminium_vs_aluminium_is_ok():
    assert pair_flag(r("A", "6061-T6"), r("B", "7075-T6")) is None


def test_harsh_environment_uses_tighter_threshold():
    # Carbon steel 0.85 vs stainless 17-4 0.60: 0.25 is fine in general, flagged when harsh.
    a, b = r("A", "4140"), r("B", "17-4")
    assert pair_flag(a, b, "general") is None
    assert pair_flag(a, b, "harsh")["threshold_v"] == 0.15


def test_small_anode_fastener_is_high_severity():
    flag = pair_flag(r("P", "SS 316", "Plate"), r("S", "Zinc plated steel", "Bolt M8"))
    assert flag["severity"] == "high" and flag["corrodes"] == "S"


def test_contact_pairs_use_placement_or_parent():
    rows = [r("A", "6061"), r("B", "SS 304"), r("C", "SS 304")]
    occs = [{"part_number": "A", "parent": "X", "position": (0, 0, 0)},
            {"part_number": "B", "parent": "X", "position": (10, 0, 0)},
            {"part_number": "C", "parent": "X", "position": (500, 0, 0)}]
    assert contact_pairs(rows, occs, radius=50) == ("placement_distance", [(0, 1)])
    for o in occs:
        o["position"] = None
    occs[2]["parent"] = "Y"
    assert contact_pairs(rows, occs) == ("assembly_structure", [(0, 1)])
    assert contact_pairs(rows)[0] == "same_bom"
    assert len(galvanic_flags(rows)["flags"]) == 2


# ── SCRUM-69 ─────────────────────────────────────────────────────────────────

def test_explanation_is_deterministic_and_plain():
    text = explain_row({"part_number": "ORB-1042", "description": "Bracket, Mounting", "material": "6061-T6",
                        "process": "machined", "quantity": 2, "spec": "±0.05"})
    assert text.startswith("ORB-1042 is a bracket, mounting.")
    assert "CNC" in text and "2 needed per build" in text and "±0.05" in text


def test_open_questions_list_missing_fields():
    qs = open_questions({"part_number": "X", "description": "Plate", "material": "", "process": "machined",
                         "spec": "", "revision": "", "flags": ["Material inferred from description"]})
    assert any("Material is not stated" in q for q in qs)
    assert any("tolerance" in q for q in qs)
    assert any("Extraction flag" in q for q in qs)


@pytest.fixture
def bom(db, user):
    project = Project.objects.create(name="Handoff", owner=user)
    bom = Bom.objects.create(project=project, source_name="bracket.pdf", status="approved")
    BomRow.objects.create(bom=bom, line_no=1, part_number="ORB-1042", description="Bracket", material="6061-T6",
                          process="machined", quantity=2, spec="±0.05", revision="A")
    BomRow.objects.create(bom=bom, line_no=2, part_number="SCR-5", description="Screw M5 x 12", material="SS 304",
                          process="purchased", quantity=4)
    return bom


def test_handoff_endpoint(auth_client, bom, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    res = auth_client.get(f"/api/bom/structured/{bom.pk}/handoff/")
    assert res.status_code == 200
    body = res.json()
    assert [l["part_number"] for l in body["lines"]] == ["ORB-1042", "SCR-5"]
    line = body["lines"][0]
    assert line["explanation_source"] == "rules"
    assert float(line["cost"]["low"]) <= float(line["cost"]["high"])
    assert body["galvanic"]["flags"][0]["parts"] == ["ORB-1042", "SCR-5"]
    assert any("Material pair" in q for q in line["open_questions"])
    assert float(body["total"]["low"]) > 0


def test_handoff_uses_claude_when_available(auth_client, bom, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test")
    rows = list(bom.rows.order_by("line_no"))

    class Msg:
        content = [type("T", (), {"text": f'{{"{rows[0].pk}": "A machined aluminium bracket."}}'})]

    with patch("bom_agent.team_requests._client") as client:
        client.return_value.messages.create.return_value = Msg
        body = auth_client.get(f"/api/bom/structured/{bom.pk}/handoff/").json()
    assert body["lines"][0]["explanation"] == "A machined aluminium bracket."
    assert body["lines"][1]["explanation_source"] == "rules"


def test_handoff_is_owner_only(api_client, other_user, bom):
    api_client.force_authenticate(other_user)
    assert api_client.get(f"/api/bom/structured/{bom.pk}/handoff/").status_code == 404
