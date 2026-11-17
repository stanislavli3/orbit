"""SCRUM-25: "Ask Orbit" from the BOM or part view, with that BOM/part as context.

Context = the BOM (or one BOM row) the user is looking at + the top hits from
``unified_search`` for the question. Every snippet is numbered so Claude can
cite ``[n]``. Without ANTHROPIC_API_KEY (or if Claude errors) we return a
retrieval-only answer listing the top cited snippets instead of failing.
"""

import os

import anthropic
from django.shortcuts import get_object_or_404

from core.usage import tracked_create

from bom_agent.models import Bom, BomRow
from part_history.models import Part
from .search import unified_search

MODEL = "claude-sonnet-4-6"


def _row_text(r: BomRow) -> str:
    parts = [r.part_number or "(no part number)", r.description, r.material, r.process, r.spec,
             f"qty {r.quantity}", f"rev {r.revision}" if r.revision else ""]
    return ", ".join(p for p in parts if p)


def build_context(user, question: str, bom_id=None, row_id=None) -> tuple[str, list[dict]]:
    """Return (focus description, numbered sources). Raises Http404 for others' BOMs."""
    sources: list[dict] = []
    focus = ""
    if row_id:
        row = get_object_or_404(BomRow.objects.select_related("bom"), pk=row_id, bom__project__owner=user)
        focus = f"BOM row {row.bom.reference} line {row.line_no}"
        sources.append({"title": focus, "snippet": _row_text(row),
                        "citation": f"{row.bom.reference} line {row.line_no}", "link": f"/boms/{row.bom_id}"})
        if row.part_number:
            part = Part.objects.filter(workspace_owner=user, part_number__iexact=row.part_number).first()
            if part:
                for c in part.costs.all()[:3]:
                    sources.append({"title": f"Past cost of {part.part_number}",
                                    "snippet": f"${c.unit_cost:.2f} {c.currency}"
                                    + (f" on {c.program}" if c.program else "")
                                    + (f" ({c.model_year})" if c.model_year else ""),
                                    "citation": c.source, "link": f"/estimate?part={part.id}"})
    elif bom_id:
        bom = get_object_or_404(Bom, pk=bom_id, project__owner=user)
        focus = f"{bom.reference} ({bom.source_name or 'uploaded file'})"
        for r in bom.rows.all()[:40]:
            sources.append({"title": f"{bom.reference} line {r.line_no}", "snippet": _row_text(r),
                            "citation": f"{bom.reference} line {r.line_no}", "link": f"/boms/{bom.id}"})

    seen = {s["citation"] for s in sources}
    hits = [h for g in unified_search(user, question, limit=3)["groups"].values() for h in g]
    hits.sort(key=lambda h: h["score"], reverse=True)
    for h in hits[:6]:
        if h["citation"] not in seen:
            seen.add(h["citation"])
            sources.append({k: h[k] for k in ("title", "snippet", "citation", "link")})
    for i, s in enumerate(sources, 1):
        s["n"] = i
    return focus, sources


def retrieval_only_answer(focus: str, sources: list[dict]) -> str:
    lines = ["**Retrieval-only answer** (AI is not configured) — the most relevant cited snippets"
             + (f" for {focus}" if focus else "") + ":", ""]
    if not sources:
        lines.append("Nothing relevant found in your files, BOMs or cost history.")
    for s in sources[:6]:
        lines.append(f"- [{s['n']}] **{s['title']}**: {s['snippet']} _(source: {s['citation']})_")
    return "\n".join(lines)


def ask(user, question: str, bom_id=None, row_id=None) -> dict:
    focus, sources = build_context(user, question, bom_id, row_id)
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if api_key:
        context = "\n".join(f"[{s['n']}] {s['title']}: {s['snippet']} (source: {s['citation']})" for s in sources)
        system = (
            "You are Orbit, an engineering cost assistant. The user is looking at "
            f"{focus or 'their workspace'}. Answer briefly in Markdown using ONLY the numbered sources below; "
            "cite them inline like [1]. If the sources don't answer it, say so.\n\nSources:\n" + context
        )
        try:
            msg = tracked_create(
                anthropic.Anthropic(api_key=api_key), path="query", operation="ask_orbit", user=user,
                target=focus, model=MODEL, max_tokens=800, system=system,
                messages=[{"role": "user", "content": question}],
            )
            return {"answer": msg.content[0].text.strip(), "mode": "ai", "focus": focus, "sources": sources}
        except Exception:
            pass
    return {"answer": retrieval_only_answer(focus, sources), "mode": "retrieval_only",
            "focus": focus, "sources": sources}
