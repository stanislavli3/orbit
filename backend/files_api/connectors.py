"""
Pluggable connectors that index files *in place* (nothing is copied to S3).

A connector lists files in a configured location and can read their bytes.
``index_source`` parses each supported file with the shared extractor and
upserts an ``UploadedFile`` row (source != "upload") that links back to the
original location and records owner / last editor where the source exposes it.

Add a connector: subclass ``Connector``, implement ``status``/``list_files``/
``read_bytes``, and register it in ``CONNECTORS``.
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote

from django.conf import settings
from django.db import transaction
from django.utils.dateparse import parse_datetime

from .extractor import extract_metadata
from .models import ConnectedSource, ExtractionResult, UploadedFile

INDEXABLE_EXTENSIONS = {"step", "stp", "pdf", "m", "mat", "iges", "igs"}
MAX_INDEX_BYTES = int(os.getenv("CONNECTOR_MAX_FILE_BYTES", 50_000_000))
MAX_FILES_PER_RUN = 500


class ConnectorError(Exception):
    pass


@dataclass
class ConnectorFile:
    external_id: str
    name: str
    size: int
    url: str
    owner: str = ""
    last_editor: str = ""
    modified_at: datetime | None = None


class Connector:
    kind = ""

    def __init__(self, source: ConnectedSource):
        self.source = source

    @classmethod
    def status(cls) -> dict:
        """{"configured": bool, "detail": str} — whether this connector can run here."""
        return {"configured": True, "detail": ""}

    @classmethod
    def validate_config(cls, config: dict) -> dict:
        return config

    def list_files(self) -> list[ConnectorFile]:
        raise NotImplementedError

    def read_bytes(self, f: ConnectorFile) -> bytes:
        raise NotImplementedError


# ── Local folder ───────────────────────────────────────────────────────────


def _allowed_local_roots() -> list[Path]:
    raw = os.getenv("CONNECTOR_LOCAL_ROOTS", "")
    roots = [Path(p).expanduser().resolve() for p in raw.split(os.pathsep) if p.strip()]
    # The repo's samples/ folder is always allowed so the demo works out of the box.
    roots.append((Path(settings.BASE_DIR).parent / "samples").resolve())
    return roots


class LocalFolderConnector(Connector):
    """A folder of STEP/PDF/MATLAB exports on the Orbit server (or a mounted share)."""

    kind = "local_folder"

    @classmethod
    def status(cls) -> dict:
        roots = ", ".join(str(r) for r in _allowed_local_roots())
        return {"configured": True, "detail": f"Allowed roots: {roots}"}

    @classmethod
    def validate_config(cls, config: dict) -> dict:
        raw = (config or {}).get("path", "").strip()
        if not raw:
            raise ConnectorError("A folder path is required.")
        path = Path(raw).expanduser().resolve()
        if not any(path == r or r in path.parents for r in _allowed_local_roots()):
            raise ConnectorError(
                "Folder is outside the allowed roots. Set CONNECTOR_LOCAL_ROOTS on the server."
            )
        if not path.is_dir():
            raise ConnectorError(f"Folder not found: {path}")
        return {"path": str(path)}

    def list_files(self) -> list[ConnectorFile]:
        root = Path(self.source.config["path"])
        if not root.is_dir():
            raise ConnectorError(f"Folder not found: {root}")
        files = []
        for p in sorted(root.rglob("*")):
            if not p.is_file() or p.suffix.lower().lstrip(".") not in INDEXABLE_EXTENSIONS:
                continue
            st = p.stat()
            owner = ""
            try:
                import pwd

                owner = pwd.getpwuid(st.st_uid).pw_name
            except (ImportError, KeyError):
                pass
            files.append(ConnectorFile(
                external_id=str(p),
                name=p.name,
                size=st.st_size,
                url="file://" + quote(str(p)),
                owner=owner,
                # Filesystems don't record who last edited; the owner is the best signal.
                last_editor="",
                modified_at=datetime.fromtimestamp(st.st_mtime, tz=timezone.utc),
            ))
        return files

    def read_bytes(self, f: ConnectorFile) -> bytes:
        return Path(f.external_id).read_bytes()


# ── Google Drive ───────────────────────────────────────────────────────────

DRIVE_SCOPE = "https://www.googleapis.com/auth/drive.readonly"
DRIVE_API = "https://www.googleapis.com/drive/v3/files"
DRIVE_FIELDS = (
    "nextPageToken,files(id,name,size,mimeType,modifiedTime,webViewLink,"
    "owners(displayName,emailAddress),lastModifyingUser(displayName,emailAddress))"
)


def _drive_credentials_info() -> dict | None:
    raw = os.getenv("GOOGLE_DRIVE_SERVICE_ACCOUNT_JSON", "").strip()
    if not raw:
        return None
    if not raw.startswith("{"):
        raw = Path(raw).expanduser().read_text()
    return json.loads(raw)


def _person(p: dict | None) -> str:
    if not p:
        return ""
    return p.get("displayName") or p.get("emailAddress") or ""


class GoogleDriveConnector(Connector):
    """Read-only (drive.readonly) Drive folder via a service account the folder is shared with."""

    kind = "google_drive"

    @classmethod
    def status(cls) -> dict:
        try:
            info = _drive_credentials_info()
        except (OSError, ValueError) as exc:
            return {"configured": False, "detail": f"Invalid GOOGLE_DRIVE_SERVICE_ACCOUNT_JSON: {exc}"}
        if not info:
            return {
                "configured": False,
                "detail": "Google Drive is not configured. Set GOOGLE_DRIVE_SERVICE_ACCOUNT_JSON "
                "and share the folder with the service account.",
            }
        return {"configured": True, "detail": f"Service account: {info.get('client_email', '?')}"}

    @classmethod
    def validate_config(cls, config: dict) -> dict:
        folder = (config or {}).get("folder_id", "").strip()
        # Accept a pasted folder URL: https://drive.google.com/drive/folders/<id>
        if "/folders/" in folder:
            folder = folder.split("/folders/", 1)[1].split("?")[0].split("/")[0]
        if not folder:
            raise ConnectorError("A Google Drive folder ID or URL is required.")
        return {"folder_id": folder}

    def _token(self) -> str:
        from google.auth.transport.urllib3 import Request
        from google.oauth2 import service_account
        import urllib3

        info = _drive_credentials_info()
        if not info:
            raise ConnectorError("Google Drive is not configured.")
        creds = service_account.Credentials.from_service_account_info(info, scopes=[DRIVE_SCOPE])
        creds.refresh(Request(urllib3.PoolManager()))
        return creds.token

    def _get(self, url: str, fields: dict | None = None) -> bytes:
        """Single seam for HTTP so tests can mock all Drive traffic."""
        import urllib3

        if not hasattr(self, "_cached_token"):
            self._cached_token = self._token()
        resp = urllib3.PoolManager().request(
            "GET", url, fields=fields,
            headers={"Authorization": f"Bearer {self._cached_token}"},
        )
        if resp.status >= 400:
            raise ConnectorError(f"Google Drive API error {resp.status}: {resp.data[:200]!r}")
        return resp.data

    def list_files(self) -> list[ConnectorFile]:
        folder = self.source.config["folder_id"]
        files: list[ConnectorFile] = []
        token = None
        while True:
            params = {
                "q": f"'{folder}' in parents and trashed = false",
                "fields": DRIVE_FIELDS,
                "pageSize": "200",
                "supportsAllDrives": "true",
                "includeItemsFromAllDrives": "true",
            }
            if token:
                params["pageToken"] = token
            data = json.loads(self._get(DRIVE_API, params))
            for item in data.get("files", []):
                name = item.get("name", "")
                if name.rsplit(".", 1)[-1].lower() not in INDEXABLE_EXTENSIONS:
                    continue
                files.append(ConnectorFile(
                    external_id=item["id"],
                    name=name,
                    size=int(item.get("size") or 0),
                    url=item.get("webViewLink") or f"https://drive.google.com/file/d/{item['id']}/view",
                    owner=_person((item.get("owners") or [None])[0]),
                    last_editor=_person(item.get("lastModifyingUser")),
                    modified_at=parse_datetime(item["modifiedTime"]) if item.get("modifiedTime") else None,
                ))
            token = data.get("nextPageToken")
            if not token:
                return files

    def read_bytes(self, f: ConnectorFile) -> bytes:
        return self._get(f"{DRIVE_API}/{f.external_id}", {"alt": "media", "supportsAllDrives": "true"})


CONNECTORS: dict[str, type[Connector]] = {
    LocalFolderConnector.kind: LocalFolderConnector,
    GoogleDriveConnector.kind: GoogleDriveConnector,
}


def get_connector(source: ConnectedSource) -> Connector:
    return CONNECTORS[source.kind](source)


# ── Indexing ───────────────────────────────────────────────────────────────


def _index_one(source: ConnectedSource, connector: Connector, f: ConnectorFile) -> UploadedFile:
    ext = f.name.rsplit(".", 1)[-1].lower() if "." in f.name else ""
    key = hashlib.sha1(f.external_id.encode()).hexdigest()
    if f.size > MAX_INDEX_BYTES:
        result = {"error": f"File too large to index ({f.size} bytes).", "confidence": 0.0,
                  "warnings": [f"File too large to index ({f.size} bytes)."]}
    else:
        try:
            result = extract_metadata(f.name, connector.read_bytes(f))
        except (OSError, ConnectorError) as exc:
            result = {"error": f"Could not read file: {exc}", "confidence": 0.0,
                      "warnings": [f"Could not read file: {exc}"]}
    failed = bool(result.get("error"))
    description = result["error"] if failed else (result.get("file_description") or "")
    with transaction.atomic():
        record, _ = UploadedFile.objects.update_or_create(
            connected_source=source,
            external_id=f.external_id,
            defaults=dict(
                project=source.project,
                uploaded_by=source.created_by,
                original_name=f.name,
                file_type=ext,
                s3_key=f"connector/{source.id}/{key}",
                file_size=f.size,
                status="failed" if failed else "processed",
                category="vault",
                source=source.kind,
                description=description[:2000],
                external_url=f.url,
                owner_name=f.owner,
                last_editor_name=f.last_editor,
                source_modified_at=f.modified_at,
            ),
        )
        ExtractionResult.objects.update_or_create(file=record, defaults={"result_json": result})
    _embed(record, result)
    return record


def _embed(record: UploadedFile, result: dict) -> None:
    """Best-effort embedding so connected files show up in assistant search."""
    from .embeddings import generate_embedding
    from .models import FileEmbedding

    try:
        vec = generate_embedding(f"{record.original_name}\n{record.description}\n{json.dumps(result)}")
    except Exception:
        return
    if vec:
        FileEmbedding.objects.update_or_create(file=record, defaults={"embedding_json": vec})


def index_source(source: ConnectedSource) -> dict:
    """List + index every supported file; remove rows for files that disappeared."""
    connector = get_connector(source)
    if not connector.status()["configured"]:
        raise ConnectorError(connector.status()["detail"])
    try:
        listed = connector.list_files()[:MAX_FILES_PER_RUN]
    except ConnectorError as exc:
        source.last_error = str(exc)
        source.save(update_fields=["last_error"])
        raise
    indexed = failed = 0
    seen = []
    for f in listed:
        rec = _index_one(source, connector, f)
        seen.append(f.external_id)
        failed += rec.status == "failed"
        indexed += rec.status == "processed"
    gone = UploadedFile.objects.filter(connected_source=source).exclude(external_id__in=seen)
    removed = gone.count()
    gone.delete()
    source.last_indexed_at = datetime.now(timezone.utc)
    source.last_error = ""
    source.file_count = len(seen)
    source.save(update_fields=["last_indexed_at", "last_error", "file_count"])
    return {"indexed": indexed, "failed": failed, "removed": removed, "total": len(seen)}


def index_single_file(record: UploadedFile) -> None:
    """Re-index one connected file (used by the per-file Extract button)."""
    source = record.connected_source
    connector = get_connector(source)
    for f in connector.list_files():
        if f.external_id == record.external_id:
            _index_one(source, connector, f)
            return
    UploadedFile.objects.filter(pk=record.pk).update(
        status="failed", description="File no longer exists at its source."
    )
