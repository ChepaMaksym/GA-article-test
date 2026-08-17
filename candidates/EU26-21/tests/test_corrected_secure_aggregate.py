#!/usr/bin/env python3
from __future__ import annotations

import copy
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from corrected_applied.secure_aggregate import (  # noqa: E402
    EXPECTED_ENVIRONMENT_PROFILE,
    EXPECTED_PACKAGES,
    validate_secure_row,
)


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
        "no_information_rate": 0.90,
        "confusion_matrix": [[90.0, 10.0], [5.0, 5.0]],
        "negative_support": 100.0,
        "positive_support": 10.0,
    }


def result(mask: list[int], *, reset=None, budget=None, workers=None) -> dict:
    selected = [index for index, bit in enumerate(mask) if bit]
    raw_indices = [index if index < 24 else index + 1 for index in selected]
    payload = {
        "selected_mask": list(mask),
        "official_test_metrics": {
            "selected_feature_count": len(selected),
            "selected_predictive_indices": selected,
            "selected_raw_indices": raw_indices,
            "selected_feature_names": [f"feature_{index}" for index in selected],
            "weighted": metric_block(0.70),
            "unweighted": metric_block(0.70),
        },
    }
    if reset is not None:
        payload.update(
            {
                "seed": 1,
                "search_seed": 1_000_004,
                "reset": reset,
                "budget": budget,
                "workers": workers,
                "evaluations": budget,
                "reset_events": 2 if reset and budget == 2500 else 0,
            }
        )
    return payload


def valid_row() -> dict:
    digest = "a" * 64
    baseline_mask = [1] * 40
    old_mask = [1] * 6 + [0] * 34
    h1_mask = [1] * 5 + [0] * 35
    old = result(old_mask)
    old.update(
        {
            "seed": 1,
            "search_seed": 1_000_004,
            "active_nfe": 200,
            "full_validation_nfe": 100,
            "optimizer_nfe": 300,
        }
    )
    protocol = {
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
        "environment_profile": EXPECTED_ENVIRONMENT_PROFILE,
        "python_version": "3.11.15",
        "package_versions": dict(EXPECTED_PACKAGES),
    }
    return {
        "schema": "eu26-21-corrected-applied-row-v1",
        "seed": 1,
        "protocol": protocol,
        "initial_population": 50,
        "initial_masks_sha256": digest,
        "baseline": result(baseline_mask),
        "old": old,
        "hybrid_h1": result(h1_mask, reset=True, budget=400, workers=4),
        "hybrid_reset": result(h1_mask, reset=True, budget=2500, workers=1),
        "hybrid_no_reset": result(h1_mask, reset=False, budget=2500, workers=1),
    }


class SecureAggregateTests(unittest.TestCase):
    def test_valid_secure_row_passes(self) -> None:
        validate_secure_row(valid_row(), 1)

    def test_instance_weight_raw_index_is_rejected(self) -> None:
        row = valid_row()
        row["hybrid_h1"]["official_test_metrics"]["selected_raw_indices"][0] = 24
        with self.assertRaisesRegex(ValueError, "instance-weight index 24"):
            validate_secure_row(row, 1)

    def test_package_version_mismatch_is_rejected(self) -> None:
        row = valid_row()
        row["protocol"]["package_versions"]["numpy"] = "0.0.0"
        with self.assertRaisesRegex(ValueError, "package-version ledger"):
            validate_secure_row(row, 1)

    def test_mask_and_selected_indices_must_agree(self) -> None:
        row = valid_row()
        row["hybrid_reset"]["official_test_metrics"]["selected_predictive_indices"] = [39]
        with self.assertRaisesRegex(ValueError, "indices disagree with mask"):
            validate_secure_row(row, 1)

    def test_no_reset_run_cannot_record_reset_event(self) -> None:
        row = valid_row()
        row["hybrid_no_reset"]["reset_events"] = 1
        with self.assertRaisesRegex(ValueError, "no-reset run recorded"):
            validate_secure_row(row, 1)


if __name__ == "__main__":
    unittest.main()
