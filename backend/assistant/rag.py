import json
import os
from typing import List

import numpy as np
from django.contrib.auth.models import User

from files_api.embeddings import generate_embedding, cosine_similarity
from files_api.models import UploadedFile, ExtractionResult, FileEmbedding


def _serialize_extraction(file: UploadedFile) -> dict:
    try:
        result: ExtractionResult = file.result  # type: ignore[attr-defined]
        return result.result_json or {}
    except ExtractionResult.DoesNotExist:
        return {}
    except Exception:
        return {}


def find_relevant_files(
    query: str, user: User, project_id: int | None, top_k: int = 5
) -> list[UploadedFile]:
    """
    Compute cosine similarity between the query embedding and stored file embeddings
    for the user (optionally limited to a project) and return the top-K files.
    """
    query_vec = np.array(generate_embedding(query), dtype=float)
    if query_vec.size == 0 or not np.any(query_vec):
        return []

    embeddings = (
        FileEmbedding.objects.select_related("file", "file__project")
        .filter(file__project__owner=user)
        .order_by("-updated_at")
    )
    if project_id:
        embeddings = embeddings.filter(file__project_id=project_id)

    scored: list[tuple[float, UploadedFile]] = []
    for embedding in embeddings:
        vec = np.array(embedding.embedding_json, dtype=float)
        score = cosine_similarity(query_vec, vec)
        if score > 0:
            scored.append((score, embedding.file))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [file for _, file in scored[:top_k]]


def build_context_prompt(files: List[UploadedFile]) -> str:
    """
    Format retrieved files into a text block that can be injected into a system prompt.
    """
    if not files:
        return "No related files were found; answer using general engineering knowledge."

    blocks = []
    for file in files:
        extraction = _serialize_extraction(file)
        extraction_snippet = json.dumps(extraction, ensure_ascii=False)[:1500]
        description = file.description or "No description available."

        blocks.append(
            f"File: {file.original_name}\n"
            f"Description: {description}\n"
            f"Metadata: {extraction_snippet}"
        )

    return "\n\n".join(blocks)


def build_system_prompt(context_block: str) -> str:
    api_key_present = bool(os.getenv("ANTHROPIC_API_KEY"))
    api_note = (
        ""
        if api_key_present
        else "Anthropic API key is missing — respond with a helpful disclaimer."
    )
    return (
        "You are Orbit's engineering file assistant. Answer concisely, grounding every claim in the provided file metadata. "
        "If the context lacks the answer, say so and suggest what to upload. "
        f"{api_note}\n\nContext:\n{context_block}"
    )
