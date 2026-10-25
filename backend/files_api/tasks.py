"""
Celery tasks for uploaded-file processing.

Enqueue with ``transaction.on_commit`` so the worker never reads a row that
isn't committed yet. ``recover_orphaned_jobs`` runs when a worker starts.
"""

import json

from celery import shared_task

from .ai_description import generate_engineering_profile, generate_file_description
from .embeddings import generate_embedding
from .extractor import extract_step_header
from .models import ExtractionResult, FileEmbedding, UploadedFile
from .s3_service import download_file_from_s3


@shared_task
def describe_file(file_id: int) -> None:
    """Generate an AI description on upload only. Status stays 'uploaded'."""
    file = UploadedFile.objects.filter(id=file_id).first()
    if file is None:
        return  # deleted while queued
    try:
        file_bytes = download_file_from_s3(file.s3_key)
        result = extract_step_header(file_bytes)
        description = generate_file_description(file.original_name, file.file_type, result)
        if description:
            UploadedFile.objects.filter(id=file_id).update(description=description)
    except Exception:
        pass  # Non-fatal: description stays empty, file is still usable


@shared_task
def extract_file(file_id: int) -> None:
    """Full extraction: STEP parse + profile + embedding. Triggered on demand."""
    file = UploadedFile.objects.filter(id=file_id).first()
    if file is None:
        return  # deleted while queued
    try:
        UploadedFile.objects.filter(id=file_id).update(status="processing")
        file_bytes = download_file_from_s3(file.s3_key)
        result = extract_step_header(file_bytes)
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
    except Exception:
        UploadedFile.objects.filter(id=file_id).update(status="failed")
        raise


def recover_orphaned_jobs() -> None:
    """Re-queue extractions a dead worker left in 'processing'."""
    for file_id in UploadedFile.objects.filter(status="processing").values_list("pk", flat=True):
        extract_file.delay(file_id)
