import hashlib
import math
import os
import re
from collections import Counter
from typing import List

import anthropic
import numpy as np

DIM = 1024


def _hashed_tfidf_embedding(text: str) -> List[float]:
    tokens = re.findall(r"\b\w+\b", text.lower())
    counts = Counter(tokens)
    if not counts:
        return [0.0] * DIM

    vec = np.zeros(DIM, dtype=float)
    total = sum(counts.values())
    for token, count in counts.items():
        digest = hashlib.md5(token.encode()).hexdigest()
        idx = int(digest, 16) % DIM
        tf = count / total
        vec[idx] += tf

    norm = np.linalg.norm(vec)
    if norm == 0:
        return vec.tolist()
    return (vec / norm).tolist()


def generate_embedding(text: str) -> List[float]:
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if api_key and text.strip():
        try:
            client = anthropic.Anthropic(api_key=api_key)
            response = client.embeddings.create(model="voyage-3", input=[text])
            embedding = response.data[0].embedding  # type: ignore[attr-defined]
            if embedding:
                return embedding
        except Exception:
            pass
    return _hashed_tfidf_embedding(text)


def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    denom = np.linalg.norm(a) * np.linalg.norm(b)
    if denom == 0:
        return 0.0
    return float(np.dot(a, b) / denom)
