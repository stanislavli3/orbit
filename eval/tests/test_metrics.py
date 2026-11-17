"""Unit tests for the evaluation metrics and scoring helpers (no Django, no network).

Run:  backend/.venv/bin/python -m pytest -q eval/tests -p no:django
"""

import csv
import math
import sys
from pathlib import Path

import pytest

EVAL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(EVAL))

from orbit_eval.metrics import (  # noqa: E402
    abstention_thresholds, calibration, cohens_kappa, ndcg_at_k, prf, ranking_summary, recall_at_k,
    reciprocal_rank, score_field,
)


def test_score_field_counts_wrong_values_as_fp_and_fn():
    assert score_field("4", "4") == (1, 0, 0)
    assert score_field("4", "1") == (0, 1, 1)
    assert score_field("", "B") == (0, 1, 0)
    assert score_field("C", "") == (0, 0, 1)
    assert score_field("", "") == (0, 0, 0)


def test_prf_handles_empty_denominators():
    assert prf(9, 1, 2)["precision"] == pytest.approx(0.9)
    assert prf(9, 1, 2)["recall"] == pytest.approx(9 / 11)
    assert prf(0, 0, 0)["f1"] is None
    assert prf(0, 3, 0)["f1"] is None and prf(0, 3, 0)["precision"] == 0


def test_ranking_metrics_on_a_hand_worked_example():
    ranked, rel = ["d3", "d1", "d7", "d2"], {"d1", "d2"}
    assert recall_at_k(ranked, rel, 1) == 0
    assert recall_at_k(ranked, rel, 5) == 1
    assert reciprocal_rank(ranked, rel) == 0.5
    # DCG = 1/log2(3) + 1/log2(5); IDCG = 1 + 1/log2(3)
    assert ndcg_at_k(ranked, rel, 10) == pytest.approx((1 / math.log2(3) + 1 / math.log2(5)) / (1 + 1 / math.log2(3)))
    s = ranking_summary([(ranked, rel), (["d9"], {"d1"})])
    assert s["n_questions"] == 2 and s["mrr"] == 0.25 and s["recall@5"] == 0.5


def test_calibration_perfect_and_overconfident():
    assert calibration([1.0, 1.0], [True, True])["ece"] == 0
    over = calibration([0.9] * 10, [True] * 5 + [False] * 5)
    assert over["ece"] == pytest.approx(0.4)
    assert abstention_thresholds([0.5, 0.9], [False, True])[-1] == {"threshold": 0.9, "kept": 1, "coverage": 0.5, "accuracy": 1.0}


def test_cohens_kappa_textbook_values():
    assert cohens_kappa(["a", "b", "a", "b"], ["a", "b", "a", "b"])["kappa"] == 1.0
    # po = 0.5, pe = 0.5 -> kappa 0
    assert cohens_kappa(["a", "a", "b", "b"], ["a", "b", "a", "b"])["kappa"] == 0.0
    assert cohens_kappa(["a", ""], ["a", "b"])["n"] == 1


def test_material_normalisation_is_lenient_only_on_prefixes():
    from extraction_eval import norm

    assert norm("material", "AL 7075-T6") == "7075-T6"
    assert norm("material", "AISI 4140") == "4140"
    assert norm("material", "Stainless steel 304") == "SS 304"
    assert norm("material", "-") == "-"
    assert norm("material", "CRS") == "CRS"
    assert norm("quantity", "2 EA") == ""


def test_head_to_head_score_unblinds_and_reports_delta(tmp_path):
    from head_to_head import SHEET_COLUMNS, score

    key = tmp_path / "key.csv"
    with open(key, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["item", "question_id", "A", "B"])
        w.writeheader()
        w.writerow({"item": 1, "question_id": "Q1", "A": "orbit", "B": "assistant"})
        w.writerow({"item": 2, "question_id": "Q2", "A": "assistant", "B": "orbit"})

    def sheet(path, rows):
        with open(path, "w", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(SHEET_COLUMNS)
            for r in rows:
                w.writerow(r)

    s1, s2 = tmp_path / "s1.csv", tmp_path / "s2.csv"
    sheet(s1, [[1, "q", "r", "a", "correct", "grounded", "b", "incorrect", "fabricated", "x", ""],
               [2, "q", "r", "a", "correct", "grounded", "b", "correct", "grounded", "x", ""]])
    sheet(s2, [[1, "q", "r", "a", "correct", "grounded", "b", "partial", "fabricated", "y", ""],
               [2, "q", "r", "a", "correct", "grounded", "b", "correct", "grounded", "y", ""]])

    class Args:
        pass

    args = Args()
    args.key, args.sheets = str(key), [str(s1), str(s2)]
    report = score(args)
    assert report["per_system"]["orbit"]["rate"] == 1.0
    assert report["per_system"]["assistant"]["rate"] == 0.5
    assert report["orbit_minus_assistant_pp"] == 50.0
    assert len(report["disagreements"]) == 1
