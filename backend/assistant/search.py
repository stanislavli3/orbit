"""SCRUM-24: one search across uploaded files, structured BOMs and cost history.

Demo-grade: everything is scored in Python with the same hashed TF-IDF
embedding the assistant already uses (``files_api.embeddings``), plus a small
bonus when the query appears verbatim (part numbers, supplier names). Every
hit carries a human-readable ``citation`` and an in-app ``link``.
"""

import numpy as np

from bom_agent.models import BomRow
from files_api.embeddings import cosine_similarity, generate_embedding
from files_api.models import FileEmbedding
from part_history.models import Part, Quote, Supplier

MIN_SCORE = 0.05
GROUPS = ["files", "bom_rows", "parts", "quotes", "suppliers"]


def _score(query: str, query_vec: np.ndarray, text: str) -> float:
    if not text.strip():
        return 0.0
    score = cosine_similarity(query_vec, np.array(generate_embedding(text), dtype=float))
    if query.lower() in text.lower():
        score += 0.5
    return round(score, 4)


def _rank(hits: list[dict], limit: int) -> list[dict]:
    hits = [h for h in hits if h["score"] >= MIN_SCORE]
    hits.sort(key=lambda h: h["score"], reverse=True)
    return hits[:limit]


def _search_files(user, query, qvec, project_id, limit):
    embeddings = FileEmbedding.objects.select_related("file", "file__project").filter(
        file__project__owner=user
    )
    if project_id:
        embeddings = embeddings.filter(file__project_id=project_id)
    hits = []
    for emb in embeddings:
        f = emb.file
        score = cosine_similarity(qvec, np.array(emb.embedding_json, dtype=float))
        if query.lower() in f"{f.original_name} {f.description}".lower():
            score += 0.5
        hits.append({
            "type": "file",
            "id": f.id,
            "title": f.original_name,
            "snippet": (f.description or "")[:240],
            "citation": f"{f.original_name} (project: {f.project.name})",
            "link": f"/project/{f.project_id}/file/{f.id}/result",
            "score": round(score, 4),
        })
    return _rank(hits, limit)


def _search_bom_rows(user, query, qvec, project_id, limit):
    rows = BomRow.objects.select_related("bom").filter(bom__project__owner=user)
    if project_id:
        rows = rows.filter(bom__project_id=project_id)
    hits = []
    for r in rows[:2000]:
        text = " ".join([r.part_number, r.description, r.material, r.process, r.spec])
        ref = r.bom.reference
        hits.append({
            "type": "bom_row",
            "id": r.id,
            "title": f"{r.part_number or '(no part number)'} — {r.description}".strip(" —"),
            "snippet": ", ".join(x for x in [r.material, r.process, r.spec, f"qty {r.quantity}"] if x),
            "citation": f"{ref} line {r.line_no} ({r.bom.source_name or 'uploaded file'})",
            "link": f"/boms/{r.bom_id}",
            "score": _score(query, qvec, text),
        })
    return _rank(hits, limit)


def _search_parts(user, query, qvec, limit):
    hits = []
    for p in Part.objects.filter(workspace_owner=user).prefetch_related("costs")[:2000]:
        text = " ".join([p.part_number, p.description, p.material, p.process])
        cost = next(iter(p.costs.all()), None)
        snippet = ", ".join(x for x in [p.material, p.process] if x)
        if cost:
            snippet += f"{'; ' if snippet else ''}last cost ${cost.unit_cost:.2f}"
            if cost.program:
                snippet += f" on {cost.program}"
        hits.append({
            "type": "part",
            "id": p.id,
            "title": f"{p.part_number} — {p.description}".strip(" —"),
            "snippet": snippet,
            "citation": cost.source if cost else "Part history",
            "link": f"/estimate?part={p.id}",
            "score": _score(query, qvec, text),
        })
    return _rank(hits, limit)


def _search_quotes(user, query, qvec, limit):
    hits = []
    for q in Quote.objects.filter(workspace_owner=user).select_related("supplier", "part")[:2000]:
        pn = q.part.part_number if q.part else ""
        text = " ".join([q.supplier.name, pn, q.material, q.tolerance, q.certifications, q.program])
        hits.append({
            "type": "quote",
            "id": q.id,
            "title": f"{q.supplier.name} quote{' for ' + pn if pn else ''}",
            "snippet": f"${q.unit_price:.2f} {q.currency}, quoted {q.quoted_at}"
            + (f", {q.material}" if q.material else ""),
            "citation": q.source,
            "link": f"/estimate?part={q.part_id}" if q.part_id else "/estimate",
            "score": _score(query, qvec, text),
        })
    return _rank(hits, limit)


def _search_suppliers(user, query, qvec, limit):
    hits = []
    for s in Supplier.objects.filter(workspace_owner=user)[:2000]:
        text = f"{s.name} {s.certifications}"
        hits.append({
            "type": "supplier",
            "id": s.id,
            "title": s.name,
            "snippet": s.certifications,
            "citation": s.approval_note or "Supplier list",
            "link": "/estimate",
            "score": _score(query, qvec, text),
        })
    return _rank(hits, limit)


def unified_search(user, query: str, project_id: int | None = None, limit: int = 5) -> dict:
    """Return ``{"query", "groups": {type: [hits]}, "total"}``; groups are ranked by score."""
    query = query.strip()
    empty = {g: [] for g in GROUPS}
    qvec = np.array(generate_embedding(query), dtype=float)
    if not query or not np.any(qvec):
        return {"query": query, "groups": empty, "total": 0}
    groups = {
        "files": _search_files(user, query, qvec, project_id, limit),
        "bom_rows": _search_bom_rows(user, query, qvec, project_id, limit),
        "parts": _search_parts(user, query, qvec, limit),
        "quotes": _search_quotes(user, query, qvec, limit),
        "suppliers": _search_suppliers(user, query, qvec, limit),
    }
    return {"query": query, "groups": groups, "total": sum(len(v) for v in groups.values())}
