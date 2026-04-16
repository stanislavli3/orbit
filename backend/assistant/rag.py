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
        scored.append((score, embedding.file))

    scored.sort(key=lambda x: x[0], reverse=True)
    results = [file for _, file in scored[:top_k]]

    # If TF-IDF found no overlap, fall back to returning the most recent files
    if not results or all(s == 0 for s, _ in scored[:top_k]):
        return [file for _, file in scored[:top_k]] if scored else []

    return results


def build_context_prompt(files: List[UploadedFile]) -> str:
    """
    Format retrieved files into a text block that can be injected into a system prompt.
    """
    if not files:
        return (
            "No related files were found; answer using general engineering knowledge."
        )

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


def find_library_docs(
    user: User,
    doc_types: list[str] | None = None,
    query: str = "",
    top_k: int = 10,
):
    """
    Return LibraryDocument queryset for the workspace, optionally filtered by doc_type (#59).
    Falls back to embedding-ranked results if a query is given.
    """
    from bom_agent.models import LibraryDocument  # local import to avoid circular

    qs = LibraryDocument.objects.filter(workspace_owner=user)
    if doc_types:
        qs = qs.filter(doc_type__in=doc_types)

    if not query:
        return list(qs[:top_k])

    # Embedding-based ranking within the filtered set
    query_vec = np.array(generate_embedding(query), dtype=float)
    results = []
    for doc in qs:
        try:
            emb_vec = np.array(doc.embedding.embedding_json, dtype=float)
            score = cosine_similarity(query_vec, emb_vec)
        except Exception:
            score = 0.0
        results.append((score, doc))

    results.sort(key=lambda x: x[0], reverse=True)
    return [doc for _, doc in results[:top_k]]


def build_system_prompt(context_block: str) -> str:
    api_key_present = bool(os.getenv("ANTHROPIC_API_KEY"))
    api_note = (
        ""
        if api_key_present
        else "Anthropic API key is missing — respond with a helpful disclaimer."
    )
    return (
        "You are Orbit's engineering file assistant. "
        "Always respond with rich, well-structured Markdown: use headers (##/###), "
        "bold labels, bullet lists, and tables where appropriate. "
        "Ground every claim in the provided file metadata — never invent values. "
        "When presenting extracted data, organise it into clear sections: "
        "Overview, Products / Assembly, Geometry, Units & Spatial, Appearance, and Limitations. "
        "Omit sections that have no data. "
        "If the context lacks an answer, say so clearly and suggest what to upload next. "
        f"{api_note}\n\nContext:\n{context_block}"
    )
