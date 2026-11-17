"""Answer generation for the answer-quality (#27) and head-to-head (#28) harnesses.

orbit_answer      Orbit's shipped Ask Orbit path (``assistant.ask.ask``): unified search
                  context + Claude, or a retrieval-only answer when no API key is set.
assistant_answer  The "general-purpose assistant" arm: the same corpus files handed to a
                  Claude model directly (PDFs as document blocks, text files inline), with
                  no Orbit retrieval, parsing or cost history structure. Needs ANTHROPIC_API_KEY.
                  For a non-Anthropic assistant (e.g. ChatGPT with file upload) collect the
                  answers by hand and pass them as a CSV instead (see head_to_head.py).
"""

import base64
import os
import re
import time
from pathlib import Path

from .env import REPO

ASSISTANT_SYSTEM = (
    "You are a helpful general-purpose assistant. The user has uploaded the files below from their "
    "engineering team's shared drive. Answer their question."
)


def orbit_answer(user, question: str) -> dict:
    from assistant.ask import ask

    t0 = time.perf_counter()
    result = ask(user, question)
    return {
        "answer": result["answer"], "mode": result["mode"], "sources": result["sources"],
        "latency_ms": round((time.perf_counter() - t0) * 1000, 1),
    }


def corpus_content_blocks(manifest: list[dict]) -> list[dict]:
    """Every corpus file as a Messages API content block, the way a chat upload would carry it."""
    blocks = []
    for m in manifest:
        path = REPO / m["path"]
        data = path.read_bytes()
        if m["file_type"] == "pdf":
            blocks.append({"type": "document", "title": path.name, "source": {
                "type": "base64", "media_type": "application/pdf", "data": base64.b64encode(data).decode()}})
        elif m["file_type"] == "mat":
            blocks.append({"type": "text", "text": f"[{path.name}: binary MATLAB MAT-file, {len(data)} bytes; "
                                                   "a chat assistant cannot open it]"})
        else:
            blocks.append({"type": "text", "text": f"=== {path.name} ===\n{data.decode('utf-8', errors='ignore')}"})
    return blocks


def assistant_answer(manifest: list[dict], question: str, model: str) -> dict:
    import anthropic

    from core.usage import tracked_create

    t0 = time.perf_counter()
    msg = tracked_create(
        anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"]), path="query",
        operation="eval_general_assistant", target="h2h", model=model, max_tokens=800, system=ASSISTANT_SYSTEM,
        messages=[{"role": "user", "content": corpus_content_blocks(manifest) + [{"type": "text", "text": question}]}],
    )
    text = "".join(getattr(b, "text", "") for b in msg.content).strip()
    return {"answer": text, "mode": "ai", "sources": [], "latency_ms": round((time.perf_counter() - t0) * 1000, 1)}


_MARKERS = [  # (pattern, replacement)
    (re.compile(r"^\*\*Retrieval-only answer\*\*.*?:\s*", re.S), ""),
    (re.compile(r"\bOrbit\b", re.I), "the system"),
]


def blind_text(answer: str) -> str:
    """Strip labels that would tell a scorer which system wrote an answer."""
    text = answer
    for pattern, repl in _MARKERS:
        text = pattern.sub(repl, text)
    text = re.sub(r"\*\*|__|`", "", text)  # markdown emphasis differs by system
    return text.strip()
