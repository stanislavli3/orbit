"""Load the evaluation corpus into a throw-away workspace through Orbit's own code paths.

Files go through ``files_api.tasks.extract_file`` (metadata parse, AI description
and engineering profile when ANTHROPIC_API_KEY is set, embedding) with the S3
download patched to read local bytes, and STEP/PDF files through
``bom_agent.tasks.build_bom``. The two CSVs go through the real cost-history and
supplier-spend importers. Nothing is reimplemented, so what is measured is what ships.
"""

import csv
import uuid
from pathlib import Path
from unittest.mock import patch

from .env import EVAL, REPO

UPLOAD_TYPES = {"step", "stp", "pdf", "m", "mat"}


def manifest() -> list[dict]:
    return list(csv.DictReader(open(EVAL / "corpus" / "manifest.csv")))


def make_user(prefix="eval"):
    """A fresh user = a fresh, isolated workspace (harnesses may share one database)."""
    from django.contrib.auth.models import User

    username = f"{prefix}-{uuid.uuid4().hex[:8]}"
    return User.objects.create(username=username, email=f"{username}@example.invalid")


def ingest_corpus(user, *, build_boms=True) -> dict:
    """Return {doc_id: {"file_id", "bom_id", "name", "file_type"}} plus CSV import reports."""
    from bom_agent.tasks import build_bom
    from files_api.models import UploadedFile
    from files_api.tasks import extract_file
    from part_history.importer import import_costs
    from part_history.spend_import import import_spend
    from projects.models import Project

    project = Project.objects.create(name="Evaluation corpus (synthetic)", owner=user)
    run = uuid.uuid4().hex[:8]
    docs = {}
    for m in manifest():
        path = REPO / m["path"]
        data = path.read_bytes()
        info = {"name": path.name, "file_type": m["file_type"], "path": m["path"], "file_id": None, "bom_id": None}
        if m["file_type"] in UPLOAD_TYPES:
            f = UploadedFile.objects.create(
                project=project, uploaded_by=user, original_name=path.name, file_type=m["file_type"],
                s3_key=f"eval/{run}/{m['doc_id']}/{path.name}", file_size=len(data),
            )
            with patch("files_api.tasks.download_file_from_s3", return_value=data):
                extract_file(f.pk)
            info["file_id"] = f.pk
            if build_boms and m["bom_role"] in ("bom", "negative"):
                f.refresh_from_db()
                info["bom_id"] = build_bom(f, data).pk
        elif m["doc_id"] == "D06":
            info["import"] = import_costs(user, data, path.name, is_sample=True)
        elif m["doc_id"] == "D07":
            info["import"] = import_spend(user, data, path.name)
        docs[m["doc_id"]] = info
    return docs


def doc_lookup(docs: dict):
    """Map a search hit back to a corpus doc id (None when the hit has no source file)."""
    by_file = {v["file_id"]: k for k, v in docs.items() if v["file_id"]}
    by_bom = {v["bom_id"]: k for k, v in docs.items() if v["bom_id"]}
    by_name = {v["name"]: k for k, v in docs.items()}

    def lookup(hit: dict) -> str | None:
        from bom_agent.models import BomRow

        if hit.get("type") == "file":
            return by_file.get(hit["id"])
        if hit.get("type") == "bom_row":
            row = BomRow.objects.filter(pk=hit["id"]).values("bom_id").first()
            return by_bom.get(row["bom_id"]) if row else None
        citation = hit.get("citation") or ""
        for name, doc_id in by_name.items():
            if name in citation:
                return doc_id
        return None

    return lookup
