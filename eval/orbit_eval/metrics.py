"""Pure-Python metrics: field P/R/F1, ranking metrics, calibration, inter-rater agreement.

No Django and no third-party imports so they are easy to unit-test and audit.
"""

import math
from collections import Counter


# ── Field-level extraction (#25) ─────────────────────────────────────────────

def prf(tp: int, fp: int, fn: int) -> dict:
    """Precision / recall / F1. Undefined ratios are None, never silently 0 or 1."""
    p = tp / (tp + fp) if tp + fp else None
    r = tp / (tp + fn) if tp + fn else None
    if p is None or r is None:
        f1 = None
    else:
        f1 = 2 * p * r / (p + r) if p + r else 0.0
    return {"tp": tp, "fp": fp, "fn": fn, "precision": p, "recall": r, "f1": f1}


def score_field(gold: str, pred: str) -> tuple[int, int, int]:
    """(tp, fp, fn) for one already-normalized value. Blank = no value.

    A wrong non-blank prediction is both a false positive and a false negative.
    Both blank is a correct abstention and counts nowhere.
    """
    gold, pred = (gold or "").strip(), (pred or "").strip()
    if gold and pred:
        return (1, 0, 0) if gold == pred else (0, 1, 1)
    if pred:
        return 0, 1, 0
    if gold:
        return 0, 0, 1
    return 0, 0, 0


# ── Calibration (#25, T4) ────────────────────────────────────────────────────

def calibration(confidences: list[float], correct: list[bool], n_bins: int = 5) -> dict:
    """Expected calibration error with equal-width bins, plus the per-bin table for a reliability diagram."""
    assert len(confidences) == len(correct)
    n = len(confidences)
    bins = []
    ece = 0.0
    for b in range(n_bins):
        lo, hi = b / n_bins, (b + 1) / n_bins
        idx = [i for i, c in enumerate(confidences) if (lo <= c < hi) or (b == n_bins - 1 and c == 1.0)]
        if not idx:
            bins.append({"bin": f"[{lo:.1f},{hi:.1f}{']' if b == n_bins - 1 else ')'}", "n": 0,
                         "mean_confidence": None, "accuracy": None})
            continue
        conf = sum(confidences[i] for i in idx) / len(idx)
        acc = sum(1 for i in idx if correct[i]) / len(idx)
        ece += len(idx) / n * abs(acc - conf)
        bins.append({"bin": f"[{lo:.1f},{hi:.1f}{']' if b == n_bins - 1 else ')'}", "n": len(idx),
                     "mean_confidence": round(conf, 3), "accuracy": round(acc, 3)})
    return {"n": n, "ece": round(ece, 4) if n else None, "bins": bins}


def abstention_thresholds(confidences: list[float], correct: list[bool]) -> list[dict]:
    """For each distinct confidence t: accuracy and coverage of the rows with confidence >= t."""
    out = []
    for t in sorted(set(confidences)):
        kept = [c for conf, c in zip(confidences, correct) if conf >= t]
        out.append({"threshold": t, "kept": len(kept), "coverage": round(len(kept) / len(correct), 3),
                    "accuracy": round(sum(kept) / len(kept), 3) if kept else None})
    return out


# ── Ranking (#27, T1) ────────────────────────────────────────────────────────

def recall_at_k(ranked: list[str], relevant: set[str], k: int) -> float:
    if not relevant:
        return float("nan")
    return len(set(ranked[:k]) & relevant) / len(relevant)


def hit_at_k(ranked: list[str], relevant: set[str], k: int) -> float:
    return 1.0 if set(ranked[:k]) & relevant else 0.0


def reciprocal_rank(ranked: list[str], relevant: set[str]) -> float:
    for i, doc in enumerate(ranked, start=1):
        if doc in relevant:
            return 1.0 / i
    return 0.0


def ndcg_at_k(ranked: list[str], relevant: set[str], k: int) -> float:
    """Binary-relevance nDCG@k."""
    dcg = sum(1.0 / math.log2(i + 1) for i, doc in enumerate(ranked[:k], start=1) if doc in relevant)
    ideal = sum(1.0 / math.log2(i + 1) for i in range(1, min(len(relevant), k) + 1))
    return dcg / ideal if ideal else float("nan")


def ranking_summary(runs: list[tuple[list[str], set[str]]], ks=(1, 5, 10)) -> dict:
    """Mean metrics over (ranked doc ids, relevant doc ids) pairs."""
    n = len(runs)
    out = {"n_questions": n}
    if not n:
        return out
    for k in ks:
        out[f"recall@{k}"] = round(sum(recall_at_k(r, rel, k) for r, rel in runs) / n, 4)
        out[f"hit@{k}"] = round(sum(hit_at_k(r, rel, k) for r, rel in runs) / n, 4)
    out["mrr"] = round(sum(reciprocal_rank(r, rel) for r, rel in runs) / n, 4)
    out["ndcg@10"] = round(sum(ndcg_at_k(r, rel, 10) for r, rel in runs) / n, 4)
    return out


# ── Agreement (#25, #27, #28 human labels) ───────────────────────────────────

def cohens_kappa(a: list[str], b: list[str]) -> dict:
    """Cohen's kappa for two labellers over the same items (blank pairs skipped)."""
    pairs = [(x.strip(), y.strip()) for x, y in zip(a, b) if x.strip() and y.strip()]
    n = len(pairs)
    if not n:
        return {"n": 0, "kappa": None, "observed_agreement": None}
    po = sum(1 for x, y in pairs if x == y) / n
    ca, cb = Counter(x for x, _ in pairs), Counter(y for _, y in pairs)
    pe = sum(ca[c] * cb[c] for c in set(ca) | set(cb)) / (n * n)
    kappa = (po - pe) / (1 - pe) if pe < 1 else 1.0
    return {"n": n, "kappa": round(kappa, 4), "observed_agreement": round(po, 4)}
