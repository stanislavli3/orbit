"""Computer-use agent stub: export a file from a legacy app into Orbit's watched folder.

SCRUM-51 proof-of-concept *shape* (see docs/computer-use-poc.md). The real model call
(e.g. Anthropic's computer-use tool) and the real screen driver (e.g. pyautogui / xdotool on
a locked-down VM) are injected, so ``--dry-run`` runs end-to-end with fakes and calls nothing
external.
"""

from __future__ import annotations

import argparse
import csv
import shutil
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Protocol

ALLOWED_ACTIONS = {"click", "type", "key", "wait", "done", "abort"}


@dataclass
class ExportTask:
    name: str
    instructions: str
    expected_file: str  # where the legacy app saves the export
    required_headers: list[str]
    max_steps: int = 40
    max_seconds: int = 300


TASKS = {
    "wirs_cost_export": ExportTask(
        name="wirs_cost_export",
        instructions=(
            "You are operating the WIRS desktop client, already signed in. Open Reports > "
            "Cost history, set the date range to last quarter, click Export > CSV and save as "
            "wirs_costs.csv. Only export. Never edit, delete or submit records. If anything "
            "unexpected appears, return abort."
        ),
        expected_file="wirs_costs.csv",
        required_headers=["part_number", "unit_cost"],
    )
}


@dataclass
class Action:
    kind: str
    x: int | None = None
    y: int | None = None
    text: str = ""


class Screen(Protocol):
    def screenshot(self) -> bytes: ...
    def perform(self, action: Action) -> None: ...


Model = Callable[[ExportTask, bytes, list[Action]], Action]


@dataclass
class RunResult:
    ok: bool
    steps: list[Action] = field(default_factory=list)
    output: Path | None = None
    error: str = ""


def run_agent(task: ExportTask, model: Model, screen: Screen, export_dir: Path, watched_folder: Path) -> RunResult:
    """Screenshot -> model -> action loop, then validate and hand the file to Orbit."""
    history: list[Action] = []
    started = time.monotonic()
    for _ in range(task.max_steps):
        if time.monotonic() - started > task.max_seconds:
            return RunResult(False, history, error="timed out")
        action = model(task, screen.screenshot(), history)
        if action.kind not in ALLOWED_ACTIONS:
            return RunResult(False, history, error=f"disallowed action {action.kind!r}")
        history.append(action)
        if action.kind == "abort":
            return RunResult(False, history, error=action.text or "model aborted")
        if action.kind == "done":
            break
        screen.perform(action)
    else:
        return RunResult(False, history, error="step limit reached")

    exported = export_dir / task.expected_file
    problem = validate_export(exported, task.required_headers)
    if problem:
        return RunResult(False, history, error=problem)
    watched_folder.mkdir(parents=True, exist_ok=True)
    dest = watched_folder / f"{time.strftime('%Y%m%d-%H%M%S')}_{task.expected_file}"
    shutil.move(str(exported), dest)
    return RunResult(True, history, output=dest)


def validate_export(path: Path, required_headers: list[str]) -> str:
    if not path.exists():
        return f"export file {path.name} not found"
    with path.open(newline="", encoding="utf-8-sig") as f:
        header = next(csv.reader(f), [])
        rows = sum(1 for _ in csv.reader(f))
    missing = [h for h in required_headers if h not in header]
    if missing:
        return f"missing columns: {', '.join(missing)}"
    if rows == 0:
        return "export has no data rows"
    return ""


# ── Dry-run fakes (no external calls) ──────────────────────────────────────────

class FakeScreen:
    """Pretends to be the legacy app: the 'Save' click writes a small CSV."""

    def __init__(self, export_dir: Path, filename: str):
        self.export_dir, self.filename = export_dir, filename

    def screenshot(self) -> bytes:
        return b"fake-png"

    def perform(self, action: Action) -> None:
        if action.kind == "click" and action.text == "Save":
            (self.export_dir / self.filename).write_text("part_number,unit_cost\nORB-1042,4.10\n")


def scripted_model(script: list[Action]) -> Model:
    def model(task: ExportTask, screenshot: bytes, history: list[Action]) -> Action:
        return script[len(history)] if len(history) < len(script) else Action("done")
    return model


DRY_RUN_SCRIPT = [
    Action("click", 40, 12, "Reports"),
    Action("click", 60, 80, "Cost history"),
    Action("click", 300, 20, "Export > CSV"),
    Action("type", text="wirs_costs.csv"),
    Action("click", 420, 300, "Save"),
    Action("done"),
]


def anthropic_model(task: ExportTask, screenshot: bytes, history: list[Action]) -> Action:  # pragma: no cover
    """Real implementation goes here: send the screenshot + task to a computer-use model and
    map its tool_use (click/type/key) to an Action. Intentionally not implemented in the PoC."""
    raise NotImplementedError("Wire up the computer-use model on the export VM.")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--task", default="wirs_cost_export", choices=sorted(TASKS))
    p.add_argument("--watched-folder", type=Path, required=True)
    p.add_argument("--dry-run", action="store_true", help="Use a scripted fake model and screen")
    args = p.parse_args(argv)
    task = TASKS[args.task]
    if not args.dry_run:
        print("Only --dry-run is implemented in this proof of concept.")
        return 2
    with tempfile.TemporaryDirectory() as tmp:
        export_dir = Path(tmp)
        result = run_agent(task, scripted_model(DRY_RUN_SCRIPT), FakeScreen(export_dir, task.expected_file),
                           export_dir, args.watched_folder)
    print(f"{'OK' if result.ok else 'FAILED'} after {len(result.steps)} steps: {result.output or result.error}")
    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
