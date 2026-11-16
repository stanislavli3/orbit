"""
Celery tasks for uploaded-file processing.

Enqueue with ``transaction.on_commit`` so the worker never reads a row that
isn't committed yet. ``recover_orphaned_jobs`` runs when a worker starts.
"""

import json

from core.jobs import monitored_task

from .ai_description import generate_engineering_profile, generate_file_description
from .embeddings import generate_embedding
from .extractor import extract_metadata
from .models import ExtractionResult, FileEmbedding, UploadedFile
from .s3_service import download_file_from_s3


# A failed description is non-fatal (the file stays usable), so it is recorded in
# the admin but doesn't page anyone.
@monitored_task("file_description", notify=False)
def describe_file(file_id: int) -> None:
    """Generate an AI description on upload only. Status stays 'uploaded'."""
    file = UploadedFile.objects.filter(id=file_id).first()
    if file is None:
        return  # deleted while queued
    file_bytes = download_file_from_s3(file.s3_key)
    result = extract_metadata(file.original_name, file_bytes)
    if result.get("error"):
        UploadedFile.objects.filter(id=file_id).update(description=result["error"])
        return
    description = generate_file_description(file.original_name, file.file_type, result)
    if description:
        UploadedFile.objects.filter(id=file_id).update(description=description)


def _mark_extraction_failed(args, exc) -> None:
    UploadedFile.objects.filter(id=args[0]).update(status="failed")


@monitored_task("file_extraction", on_dead=_mark_extraction_failed)
def extract_file(file_id: int) -> None:
    """Full extraction: STEP parse + profile + embedding. Triggered on demand."""
    file = UploadedFile.objects.filter(id=file_id).first()
    if file is None:
        return  # deleted while queued
    UploadedFile.objects.filter(id=file_id).update(status="processing")
    if file.source != "upload":
        from .connectors import index_single_file

        index_single_file(file)
        return
    file_bytes = download_file_from_s3(file.s3_key)
    result = extract_metadata(file.original_name, file_bytes)
    if result.get("error"):
        # Malformed file: fail loudly with the parser's reason, don't index junk.
        ExtractionResult.objects.update_or_create(
            file_id=file_id, defaults={"result_json": result}
        )
        UploadedFile.objects.filter(id=file_id).update(
            status="failed", description=result["error"]
        )
        return
    description = generate_file_description(file.original_name, file.file_type, result)
    profile = generate_engineering_profile(file.original_name, file.file_type, result)
    result["profile"] = profile
    ExtractionResult.objects.update_or_create(
        file_id=file_id, defaults={"result_json": result}
    )
    UploadedFile.objects.filter(id=file_id).update(
        status="processed", description=description
    )
    embedding_payload = f"{file.original_name}\n{description}\n{json.dumps(result)}"
    embedding_vector = generate_embedding(embedding_payload)
    if embedding_vector:
        FileEmbedding.objects.update_or_create(
            file_id=file_id, defaults={"embedding_json": embedding_vector}
        )


def recover_orphaned_jobs() -> None:
    """Re-queue extractions a dead worker left in 'processing'."""
    for file_id in UploadedFile.objects.filter(status="processing", source="upload").values_list("pk", flat=True):
        extract_file.delay(file_id)
