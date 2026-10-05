"""Small descriptive report fixtures; never evaluate a real tree or dataset."""
from __future__ import annotations

import copy
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from chc_qx_alignment_study.aggregate import describe, validate_metrics  # noqa: E402
from local_optima_study.contract import per_class_metrics  # noqa: E402


def fabricated_metrics():
    matrix = [[40000, 10000], [10000, 39762]]
    classes = per_class_metrics(matrix)
    block = {"confusion_matrix": matrix, "classes": classes,
             "balanced_accuracy": (classes["0"]["recall"] + classes["1"]["recall"]) / 2,
             "accuracy": (matrix[0][0] + matrix[1][1]) / 99762}
    return {"weighted": copy.deepcopy(block), "unweighted": copy.deepcopy(block)}


class DescriptiveAnalysisTests(unittest.TestCase):
    def test_class_metrics_come_from_one_model_matrix(self):
        validate_metrics(fabricated_metrics())

    def test_inconsistent_class_and_quality_metrics_rejected(self):
        metrics = fabricated_metrics()
        metrics["weighted"]["classes"]["1"]["recall"] += .01
        with self.assertRaises(ValueError):
            validate_metrics(metrics)
        metrics = fabricated_metrics()
        metrics["weighted"]["balanced_accuracy"] += .01
        with self.assertRaises(ValueError):
            validate_metrics(metrics)

    def test_wrong_holdout_counts_rejected(self):
        metrics = fabricated_metrics()
        metrics["unweighted"]["confusion_matrix"][0][0] += 1
        with self.assertRaises(ValueError):
            validate_metrics(metrics)

    def test_missing_preparation_retained_without_inventing_quality(self):
        summary = describe([{"seed": seed, "arms": {}} for seed in range(44001, 44031)])
        self.assertEqual(summary["cases_accounted"], 30)
        for row in summary["arms"].values():
            self.assertEqual(row["registered_cases"], 30)
            self.assertEqual(row["diagnostic_cases"], 0)
            self.assertEqual(row["not_evaluable_cases"], 30)
            self.assertIsNone(row["median_test_wba"])
        self.assertFalse(summary["hypothesis_tests"])
        self.assertFalse(any(summary["claims"].values()))


if __name__ == "__main__":
    unittest.main()
