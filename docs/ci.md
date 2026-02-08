# Orbit — CI/CD

## CI (GitHub Actions)

Workflow: [`.github/workflows/ci.yml`](../.github/workflows/ci.yml)

**Triggers:** Push and pull requests to `main`.

**Jobs:**

| Job       | When it runs | What it does |
|-----------|--------------|--------------|
| `validate`| Always       | Checks repo structure (AGENTS.md, README, apps/, packages/) |
| `TypeScript` | When `apps/web/package.json` exists | Node 20, `npm ci`, lint, typecheck, test, build (scripts run if present) |
| `Python`  | When `apps/api` or `apps/worker` has `requirements.txt` or `pyproject.toml` | Python 3.10, pip install, ruff, pyright, pytest (tools run if present) |

- Jobs **skip** when the relevant manifests are missing, so CI stays green before apps are scaffolded.
- Python lint/typecheck/test use `ruff`, `pyright`, `pytest` when available; add them to your app’s dev dependencies when you add code.

## CD (deploy)

Not configured yet. To add CD (e.g. deploy API + web on push to `main` or on tag):

1. Add a workflow under `.github/workflows/` (e.g. `deploy.yml`).
2. Use secrets for deploy credentials; never commit them.
3. Document deploy steps and rollback in this file or in `docs/`.
