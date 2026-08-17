#!/usr/bin/env python3
from __future__ import annotations

import copy
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from corrected_applied.aggregate import evaluate  # noqa: E402
from corrected_applied.data_protocol import (  # noqa: E402
    INSTANCE_WEIGHT_RAW_INDEX,
    PREDICTIVE_DIMENSION,
    PREDICTIVE_RAW_INDICES,
    PreparedCorrectedCensus,
    WeightedBalancedFeatureObjective,
    WeightedDatasetAdapter,
    _binary_target,
    _metric_block,
    prepare_corrected_census,
)


class CorrectedDataProtocolTests(unittest.TestCase):
    def test_instance_weight_is_not_a_predictor(self) -> None:
        self.assertEqual(PREDICTIVE_DIMENSION, 40)
        self.assertNotIn(INSTANCE_WEIGHT_RAW_INDEX, PREDICTIVE_RAW_INDICES)
        self.assertEqual(len(set(PREDICTIVE_RAW_INDICES)), 40)

    def test_binary_target_accepts_both_file_suffix_styles(self) -> None:
        series = pd.Series([" - 50000.", " 50000+.", "- 50000", "50000+"])
        np.testing.assert_array_equal(_binary_target(series), np.array([0, 1, 0, 1]))

    def test_weighted_metrics_change_when_population_weights_change(self) -> None:
        y_true = np.array([0, 0, 1, 1], dtype=int)
        predicted = np.array([0, 1, 0, 1], dtype=int)
        probability = np.array([0.1, 0.8, 0.2, 0.9], dtype=float)
        unweighted = _metric_block(y_true, predicted, probability, None)
        weighted = _metric_block(
            y_true,
            predicted,
            probability,
            np.array([1.0, 1.0, 10.0, 1.0]),
        )
        self.assertNotEqual(unweighted["accuracy"], weighted["accuracy"])
        self.assertGreater(weighted["positive_support"], unweighted["positive_support"])
        self.assertEqual(len(weighted["confusion_matrix"]), 2)

    def test_objective_penalizes_empty_mask_and_uses_40_bits(self) -> None:
        x = np.arange(240, dtype=float).reshape(6, 40)
        y = np.array([0, 0, 0, 1, 1, 1], dtype=int)
        weight = np.ones(6, dtype=float)
        objective = WeightedBalancedFeatureObjective(
            x_active=x,
            y_active=y,
            weight_active=weight,
            x_validation=x,
            y_validation=y,
            weight_validation=weight,
        )
        self.assertEqual(objective(tuple([0] * 40)), (0.0, -1.0))
        fitness = objective(tuple([1] + [0] * 39))
        self.assertTrue(0.0 <= fitness[0] <= 1.0)
        self.assertEqual(fitness[1], -1.0 / 40.0)

    def test_adapter_copy_has_independent_classifier_and_selection_state(self) -> None:
        prepared = PreparedCorrectedCensus(
            x_train=np.arange(320, dtype=float).reshape(8, 40),
            y_train=np.array([0, 0, 0, 0, 1, 1, 1, 1], dtype=int),
            weight_train=np.ones(8),
            x_validation=np.arange(160, dtype=float).reshape(4, 40),
            y_validation=np.array([0, 0, 1, 1], dtype=int),
            weight_validation=np.ones(4),
            x_test=np.arange(160, dtype=float).reshape(4, 40),
            y_test=np.array([0, 0, 1, 1], dtype=int),
            weight_test=np.ones(4),
            active_instances=np.arange(6),
            feature_names=tuple("f{0}".format(index) for index in range(40)),
            metadata={},
        )
        first = WeightedDatasetAdapter(prepared)
        second = copy.copy(first)
        second.set_features([0, 1])
        second.set_instances([0, 1, 4, 5])
        self.assertEqual(len(first.features), 40)
        self.assertEqual(second.features, [0, 1])
        self.assertIsNot(first.clf, second.clf)

    def test_prepare_protocol_excludes_weight_and_uses_official_test(self) -> None:
        rng = np.random.default_rng(7)

        def make_frame(rows: int) -> pd.DataFrame:
            data = np.empty((rows, 42), dtype=object)
            for column in range(42):
                if column in (0, 5, 16, 17, 18, 24, 30, 39):
                    data[:, column] = rng.integers(1, 100, size=rows)
                elif column == 41:
                    labels = np.array([" - 50000.", " 50000+."] * ((rows + 1) // 2), dtype=object)
                    data[:, column] = labels[:rows]
                else:
                    data[:, column] = np.where(rng.random(rows) > 0.5, "a", "b")
            data[:, 24] = rng.integers(100, 1000, size=rows)
            return pd.DataFrame(data)

        train = make_frame(100)
        test = make_frame(40)
        with tempfile.TemporaryDirectory() as directory:
            train_path = Path(directory) / "train.csv"
            test_path = Path(directory) / "test.csv"
            train_path.write_text("placeholder", encoding="utf-8")
            test_path.write_text("placeholder", encoding="utf-8")
            with patch(
                "corrected_applied.data_protocol._read_raw",
                side_effect=[train, test],
            ):
                prepared = prepare_corrected_census(
                    train_path,
                    test_path,
                    seed=1,
                    active_sample_size=20,
                )
        self.assertEqual(prepared.x_train.shape[1], 40)
        self.assertEqual(prepared.x_validation.shape[1], 40)
        self.assertEqual(prepared.x_test.shape[1], 40)
        self.assertEqual(prepared.active_instances.size, 20)
        self.assertTrue(prepared.metadata["official_test_used"])
        self.assertFalse(prepared.metadata["instance_weight_as_predictor"])
        self.assertTrue(prepared.metadata["instance_weight_as_sample_weight"])


class CorrectedAggregationTests(unittest.TestCase):
    @staticmethod
    def metric_block(value: float) -> dict:
        return {
            "accuracy": value,
            "balanced_accuracy": value,
            "precision_positive": value,
            "recall_positive": value,
            "f1_positive": value,
            "mcc": max(-1.0, min(1.0, 2.0 * value - 1.0)),
            "roc_auc": value,
            "average_precision": value,
            "no_information_rate": 0.9,
            "confusion_matrix": [[90.0, 10.0], [5.0, 5.0]],
            "negative_support": 100.0,
            "positive_support": 10.0,
        }

    @classmethod
    def result(cls, value: float, count: int, *, reset=None, budget=None, workers=None, events=0, evaluations=400) -> dict:
        payload = {
            "official_test_metrics": {
                "selected_feature_count": count,
                "weighted": cls.metric_block(value),
                "unweighted": cls.metric_block(value),
            }
        }
        if reset is not None:
            payload.update({
                "seed": 0,
                "search_seed": 0,
                "reset": reset,
                "budget": budget,
                "workers": workers,
                "evaluations": evaluations,
                "reset_events": events,
            })
        return payload

    @classmethod
    def row(cls, seed: int, old_value: float, hybrid_value: float, reset_value: float, no_reset_value: float) -> dict:
        digest = "a" * 64
        old = cls.result(old_value, 6)
        old.update({
            "seed": seed,
            "search_seed": seed + 1_000_003,
            "active_nfe": 200,
            "full_validation_nfe": 100,
            "optimizer_nfe": 300,
        })
        h1 = cls.result(hybrid_value, 5, reset=True, budget=400, workers=4, evaluations=400)
        reset = cls.result(reset_value, 4, reset=True, budget=2500, workers=1, events=2, evaluations=2499)
        no_reset = cls.result(no_reset_value, 4, reset=False, budget=2500, workers=1, events=0, evaluations=2499)
        for result in (h1, reset, no_reset):
            result["seed"] = seed
            result["search_seed"] = seed + 1_000_003
        return {
            "schema": "eu26-21-corrected-applied-row-v1",
            "seed": seed,
            "protocol": {
                "official_test_file_rows": 99_762,
                "train_file_rows": 199_523,
                "raw_columns": 42,
                "instance_weight_raw_index": 24,
                "predictive_dimension": 40,
                "active_sample_size": 14_964,
                "official_test_used": True,
                "instance_weight_as_predictor": False,
                "instance_weight_as_sample_weight": True,
                "objective": "weighted_balanced_accuracy_then_sparsity",
                "train_file_sha256": digest,
                "official_test_file_sha256": digest,
                "active_indices_sha256": digest,
            },
            "initial_masks_sha256": digest,
            "baseline": cls.result(0.50, 40),
            "old": old,
            "hybrid_h1": h1,
            "hybrid_reset": reset,
            "hybrid_no_reset": no_reset,
        }

    def test_scientific_h1_failure_is_reported_not_raised(self) -> None:
        rows = [self.row(seed, 0.70, 0.68, 0.69, 0.69) for seed in range(1, 31)]
        report = evaluate(rows)
        self.assertEqual(report["claim_status"], "PASS_PROTOCOL_RESULTS_AVAILABLE")
        self.assertEqual(report["h1_corrected"]["decision"], "FAIL_NONINFERIORITY")
        self.assertEqual(report["h2_corrected"]["decision"], "BLOCKED_BY_H1")
        self.assertEqual(report["h8_reset_ablation"]["decision"], "NO_CLEAR_EFFECT")

    def test_positive_h1_and_reset_effect_pass_without_tuning(self) -> None:
        rows = [self.row(seed, 0.70, 0.7005, 0.705, 0.700) for seed in range(1, 31)]
        report = evaluate(rows)
        self.assertEqual(report["h1_corrected"]["decision"], "PASS_CONFIDENCE_BOUND")
        self.assertEqual(report["h2_corrected"]["decision"], "PASS")
        self.assertEqual(report["h8_reset_ablation"]["decision"], "POSITIVE_CONFIDENCE")


if __name__ == "__main__":
    unittest.main()
