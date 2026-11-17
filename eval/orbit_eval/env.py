"""Boot Django against a throw-away SQLite database so evaluations never touch dev data."""

import os
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
BACKEND = REPO / "backend"
EVAL = REPO / "eval"
RESULTS = EVAL / "results"

_READY = False


def setup(db_path: str | None = None) -> None:
    """Point Django at a fresh SQLite file, migrate it, and turn on demo mode (no Gmail, no S3)."""
    global _READY
    if _READY:
        return
    sys.path.insert(0, str(BACKEND))
    os.environ.setdefault("SECRET_KEY", "orbit-eval-only")
    if not db_path:
        fd, db_path = tempfile.mkstemp(prefix="orbit_eval_", suffix=".sqlite3")
        os.close(fd)
    os.environ["DATABASE_URL"] = f"sqlite:///{db_path}"
    os.environ["DJANGO_SETTINGS_MODULE"] = "config.settings"
    os.environ["ORBIT_DEMO_MODE"] = "True"
    os.environ.setdefault("CELERY_TASK_ALWAYS_EAGER", "True")

    import django
    from django.core.management import call_command

    django.setup()
    call_command("migrate", verbosity=0)
    _READY = True


def rel(path) -> str:
    """Repo-relative path for reports (absolute paths leak the machine layout)."""
    try:
        return str(Path(path).resolve().relative_to(REPO))
    except ValueError:
        return str(path)


def has_api_key() -> bool:
    return bool(os.getenv("ANTHROPIC_API_KEY", "").strip())


def git_commit() -> str:
    try:
        import subprocess

        return subprocess.check_output(["git", "-C", str(REPO), "rev-parse", "--short", "HEAD"], text=True).strip()
    except Exception:
        return "unknown"
