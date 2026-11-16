"""SCRUM-51 — the computer-use PoC stub runs with fakes and never calls out."""

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location("legacy_export_agent", ROOT / "scripts" / "legacy_export_agent.py")
agent = importlib.util.module_from_spec(_spec)
sys.modules["legacy_export_agent"] = agent
_spec.loader.exec_module(agent)


def test_dry_run_moves_export_into_watched_folder(tmp_path):
    inbox = tmp_path / "inbox"
    assert agent.main(["--dry-run", "--watched-folder", str(inbox)]) == 0
    files = list(inbox.iterdir())
    assert len(files) == 1 and files[0].name.endswith("wirs_costs.csv")
    assert "ORB-1042" in files[0].read_text()


def test_step_limit_and_disallowed_actions(tmp_path):
    task = agent.ExportTask("t", "x", "out.csv", ["a"], max_steps=3)
    screen = agent.FakeScreen(tmp_path, "out.csv")
    looping = agent.scripted_model([agent.Action("wait")] * 10)
    assert agent.run_agent(task, looping, screen, tmp_path, tmp_path / "in").error == "step limit reached"
    bad = agent.scripted_model([agent.Action("delete_record")])
    assert "disallowed" in agent.run_agent(task, bad, screen, tmp_path, tmp_path / "in").error


def test_rejects_export_missing_columns(tmp_path):
    (tmp_path / "out.csv").write_text("foo\n1\n")
    task = agent.ExportTask("t", "x", "out.csv", ["part_number"])
    res = agent.run_agent(task, agent.scripted_model([]), agent.FakeScreen(tmp_path, "x"), tmp_path, tmp_path / "in")
    assert not res.ok and "missing columns" in res.error
