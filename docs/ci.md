# Orbit — CI

## CI (GitHub Actions)

Workflow: [`.github/workflows/ci.yml`](../.github/workflows/ci.yml)

**Triggers:** every push (any branch) and every pull request.

**Job: `Backend tests`** — Python 3.12, `pip install -r backend/requirements-dev.txt`, then `pytest -q` from `backend/`. This runs every suite (`accounts`, `bom_agent`, `core`, `files_api`, `projects`, ...), found via `backend/pytest.ini`. Tests use SQLite and need no external services or secrets.

Run the same thing locally:

```bash
cd backend && pip install -r requirements-dev.txt && pytest -q
```

## Blocking merges (branch protection)

CI only *reports* failures; GitHub blocks the merge once the check is required. One-time setup (repo admin):

1. GitHub → **Settings → Branches → Add branch ruleset** (or classic branch protection rule) for `main`.
2. Enable **Require status checks to pass before merging** and add **`Backend tests`**
   (the check only appears in the picker after the workflow has run once).
3. Enable **Require branches to be up to date before merging** (recommended).

## Known gaps

- `ruff check` / `ruff format --check` currently fail on existing code, so lint is **not** part of CI yet. Fix the backlog, then add a lint step.
- Frontend (`apps/web`) has no CI job yet.

## CD (deploy)

Not configured yet.
