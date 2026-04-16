import hashlib
import re
from collections import Counter
from typing import List

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
    return _hashed_tfidf_embedding(text)


def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    denom = np.linalg.norm(a) * np.linalg.norm(b)
    if denom == 0:
        return 0.0
    return float(np.dot(a, b) / denom)
