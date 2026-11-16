# Computer-use agent PoC: export from a legacy system (SCRUM-51)

## Problem

Some customer systems (e.g. **WIRS**, see [integrations.md](integrations.md)) have no API
and no scheduled export — only a desktop or web UI with an "Export to CSV/Excel" button.
A **computer-use model** (a model that sees screenshots and returns mouse/keyboard actions,
e.g. Anthropic's computer-use tool) can click through that export on a schedule and drop
the file where Orbit already picks files up.

## Shape of the solution

```
 scheduler (cron / Task Scheduler)
        |
        v
 scripts/legacy_export_agent.py --task wirs_cost_export
        |   loop: screenshot -> model -> action -> execute
        v
 legacy app (on a locked-down VM, read-only account)
        |   "File > Export > CSV" -> C:\exports\wirs_costs.csv
        v
 file is validated and moved into Orbit's watched folder
 (a `local_folder` WorkspaceSource, Settings -> Workspace sources)
        |
        v
 Orbit cost importer / BOM pipeline (existing code)
```

## Plan

1. **Pick one export** with the customer: e.g. "WIRS cost history for last quarter to CSV".
   Record a screen video of a human doing it; write it down as numbered steps.
2. **Environment**: an isolated VM (or container with a virtual display) that has only the
   legacy client installed and a **read-only service account**. No email, no browser to the
   internet, no other credentials. The agent never sees or types a password: the session is
   pre-logged-in by IT, or login is done by a separate secret-store step outside the model.
3. **Agent loop** (`scripts/legacy_export_agent.py`): take a screenshot, send it with the
   task instructions to the computer-use model, execute the returned action (click, type,
   key), repeat. Hard limits: max steps (e.g. 40), max wall time, allow-list of actions,
   and stop if the model asks for anything outside the task.
4. **Guardrails**: the task prompt only describes *export*; the agent is told never to edit,
   delete or submit records. Every step's screenshot + action is logged for audit. A human
   reviews the first N runs.
5. **Validate the output** before Orbit sees it: file exists, expected headers, row count
   within range. Then move it into the watched folder with a timestamped name.
6. **Measure**: success rate over 20 runs, average time, failure modes (pop-ups, slow
   loads, UI changes). Success bar for the PoC: >= 90% unattended success.
7. **Decide**: if the customer can later give a DB view or scheduled export, switch to that —
   computer use is the fallback, not the target architecture.

## Risks and open questions

- UI changes / unexpected dialogs break runs -> retries, screenshots on failure, alert.
- Security review: the VM, the service account, and what leaves the network (screenshots go
  to the model provider — **to confirm** this is acceptable for WIRS data; see
  [data-policy.md](data-policy.md)).
- Licensing: does the legacy system's licence allow automated use? **To confirm with customer.**

## What's in the repo

`scripts/legacy_export_agent.py` is a **stub that shows the shape**: task definition, the
agent loop with step limits, output validation and the hand-off into the watched folder. The
model call and the screen/mouse driver are injected, so it runs in `--dry-run` mode with a
scripted fake model and touches nothing external. Tests: `backend/core/test_legacy_export_agent.py`.

```
python scripts/legacy_export_agent.py --dry-run --watched-folder /tmp/orbit-inbox
```
