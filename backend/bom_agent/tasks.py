"""
Celery tasks for BOM research and Library ingestion.

Views enqueue through the ``enqueue_*`` helpers, which defer the send until the
surrounding transaction commits so the worker never reads a row that isn't
there yet. ``recover_orphaned_jobs`` runs when a worker starts and re-queues
anything the database still shows as in flight.
"""

import csv
import io
import os
import uuid

from celery import shared_task
from django.db import transaction

from files_api.embeddings import generate_embedding
from files_api.s3_service import get_s3_client
from .models import BomResearchRun, LibraryDocument, LibraryEmbedding

# Statuses in which a research job is queued or running.
RESEARCH_IN_FLIGHT = ("researching", "generating_report")
INGEST_IN_FLIGHT = ("pending", "processing")

_EXTRACT_ROW_LIMIT = 300
_EXTRACT_CHAR_LIMIT = 8_000


# ── BOM research ─────────────────────────────────────────────────────────────

def enqueue_bom_research(run) -> None:
    """
    Queue research for ``run``. Each enqueue issues a fresh job token; the
    pipeline stops as soon as it sees a newer one, so a re-delivered or
    superseded message never researches the same run twice.
    """
    token = uuid.uuid4().hex
    BomResearchRun.objects.filter(pk=run.pk).update(job_token=token)
    run.job_token = token
    transaction.on_commit(lambda: research_bom_run.delay(run.pk, token))


@shared_task
def research_bom_run(run_id: int, job_token: str) -> None:
    from .research_pipeline import run_bom_research

    # A late re-delivery of a finished or superseded job is a no-op.
    if not BomResearchRun.objects.filter(
        pk=run_id, job_token=job_token, status__in=RESEARCH_IN_FLIGHT
    ).exists():
        return
    run_bom_research(run_id, job_token=job_token)


# ── Library ingestion (#60) ──────────────────────────────────────────────────

def _extract_csv(file_bytes: bytes) -> str:
    text = file_bytes.decode("utf-8", errors="ignore")
    reader = csv.reader(io.StringIO(text))
    rows = []
    for i, row in enumerate(reader):
        if i >= _EXTRACT_ROW_LIMIT:
            break
        line = ", ".join(c.strip() for c in row if c.strip())
        if line:
            rows.append(line)
    return "\n".join(rows)[:_EXTRACT_CHAR_LIMIT]


def _extract_xlsx(file_bytes: bytes) -> str:
    try:
        import openpyxl
        wb = openpyxl.load_workbook(io.BytesIO(file_bytes), read_only=True, data_only=True)
        lines = []
        for sheet in wb.worksheets:
            for row in sheet.iter_rows(values_only=True):
                cells = [str(c).strip() for c in row if c is not None and str(c).strip()]
                if cells:
                    lines.append(", ".join(cells))
            if len(lines) >= _EXTRACT_ROW_LIMIT:
                break
        wb.close()
        return "\n".join(lines[:_EXTRACT_ROW_LIMIT])[:_EXTRACT_CHAR_LIMIT]
    except Exception:
        return ""


def _extract_pdf(file_bytes: bytes) -> str:
    try:
        import pypdf
        reader = pypdf.PdfReader(io.BytesIO(file_bytes))
        pages = []
        for page in reader.pages[:20]:
            pages.append(page.extract_text() or "")
        return "\n".join(pages)[:_EXTRACT_CHAR_LIMIT]
    except Exception:
        return ""


def _extract_text(file_bytes: bytes, file_type: str) -> str:
    """Extract plain text from a library document based on its file type."""
    if file_type == "csv":
        return _extract_csv(file_bytes)
    if file_type == "xlsx":
        return _extract_xlsx(file_bytes)
    if file_type == "pdf":
        return _extract_pdf(file_bytes)
    # docx: return empty — no python-docx dependency; filename still used for context
    return ""


def enqueue_library_ingest(doc) -> None:
    LibraryDocument.objects.filter(pk=doc.pk).update(ingest_status="pending")
    doc.ingest_status = "pending"
    transaction.on_commit(lambda: ingest_library_document.delay(doc.pk))


@shared_task
def ingest_library_document(doc_id: int) -> None:
    """Download a doc from S3, extract its text, embed it, and store both."""
    try:
        doc = LibraryDocument.objects.get(id=doc_id)
    except LibraryDocument.DoesNotExist:
        return  # deleted while queued

    LibraryDocument.objects.filter(pk=doc.pk).update(ingest_status="processing")
    try:
        s3 = get_s3_client()
        bucket = os.getenv("AWS_STORAGE_BUCKET_NAME", "")
        buf = io.BytesIO()
        s3.download_fileobj(bucket, doc.s3_key, buf)
        extracted = _extract_text(buf.getvalue(), doc.file_type)

        # Persist extracted text so the BOM agent can include it in context
        if extracted:
            LibraryDocument.objects.filter(pk=doc.pk).update(extracted_text=extracted)
            doc.extracted_text = extracted

        # Embed extracted content; fall back to name+type if extraction produced nothing
        embed_source = extracted if extracted else f"{doc.original_name} {doc.doc_type}"
        vector = generate_embedding(embed_source)

        LibraryEmbedding.objects.update_or_create(
            document=doc,
            defaults={"embedding_json": vector, "doc_type": doc.doc_type},
        )
        LibraryDocument.objects.filter(pk=doc.pk).update(ingest_status="ready")
    except Exception:
        LibraryDocument.objects.filter(pk=doc.pk).update(ingest_status="failed")
        raise


# ── Worker-start recovery ────────────────────────────────────────────────────

def recover_orphaned_jobs() -> None:
    """Re-queue research runs and library ingests a dead worker left in flight."""
    from .research_pipeline import _log

    for run in BomResearchRun.objects.filter(status__in=RESEARCH_IN_FLIGHT):
        _log(run, "warn", "Worker started — re-queued this unfinished run")
        enqueue_bom_research(run)

    for doc_id in LibraryDocument.objects.filter(
        ingest_status__in=INGEST_IN_FLIGHT
    ).values_list("pk", flat=True):
        ingest_library_document.delay(doc_id)
