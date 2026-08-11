#!/usr/bin/env python3
"""Fail-closed tests for the independent paper-profile campaign."""
from __future__ import annotations

import copy
import importlib.util
from pathlib import Path
import sys
import unittest

OLD_DIR = Path(__file__).resolve().parents[1] / "old"
sys.path.insert(0, str(OLD_DIR))
SPEC = importlib.util.spec_from_file_location(
    "eu26_20_paper_campaign", OLD_DIR / "run_paper_campaign.py"
)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("cannot load paper campaign")
CAMPAIGN = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CAMPAIGN)


def result(seed: int, accuracy: float = 0.94, subset_length: int = 6) -> dict:
    features = list(range(seed * 10, seed * 10 + subset_length))
    return {
        "schema": "eu26-20-colon-paper-old-v1",
        "profile": "paper_cleanroom_feature_geometry",
        "seed": seed,
        "upstream_commit": "d24e61e78ac197ad75342e8f4be5d63d17bd9e7a",
        "offspring_rounding": "paper_ceil",
        "geometry": "feature_vectors_euclidean",
        "kmeans_n_init": 10,
        "dataset_rows": 62,
        "raw_features": 2000,
        "class_labels": [1, 2],
        "class_counts": [22, 40],
        "search_space_size": 128,
        "baseline_accuracy": 0.69,
        "best_accuracy": accuracy,
        "subset_length": subset_length,
        "features": features,
        "accuracy": accuracy,
        "precision": accuracy,
        "recall": accuracy,
        "fscore": accuracy,
        "mcc": 0.85,
        "nfe": 788 + seed,
        "iterations": 30 + seed,
        "adaptive_events": 3,
        "final_pc": 0.3,
        "final_pm": 0.8,
        "stagnation": 5,
        "first_target_iteration": 10,
        "first_target_nfe": 260,
        "source_sha256": "a" * 64,
        "dataset_sha256": "b" * 64,
        "features_sha256": "c" * 64,
        "trace": [],
    }


class PaperCampaignTests(unittest.TestCase):
    def setUp(self) -> None:
        self.rows = [result(seed) for seed in range(1, 11)]
        self.repeat = copy.deepcopy(self.rows[0])

    def test_exact_target_passes(self) -> None:
        report = CAMPAIGN.evaluate(self.rows, self.repeat)
        self.assertEqual(report["claim_status"], "PASS_PAPER_PROFILE_NUMERIC")
        self.assertTrue(all(gate["pass"] for gate in report["gates"].values()))

    def test_numeric_mismatch_blocks(self) -> None:
        rows = [result(seed, accuracy=0.99) for seed in range(1, 11)]
        report = CAMPAIGN.evaluate(rows, copy.deepcopy(rows[0]))
        self.assertEqual(
            report["claim_status"], "BLOCKED_PAPER_NUMERIC_MISMATCH"
        )
        self.assertFalse(report["gates"]["P3_final_accuracy_alignment"]["pass"])

    def test_repeat_mismatch_is_implementation_blocker(self) -> None:
        repeat = copy.deepcopy(self.repeat)
        repeat["nfe"] += 1
        report = CAMPAIGN.evaluate(self.rows, repeat)
        self.assertEqual(
            report["claim_status"], "BLOCKED_PAPER_IMPLEMENTATION_OR_PROVENANCE"
        )
        self.assertFalse(report["gates"]["P1_deterministic_replay"]["pass"])

    def test_identity_mismatch_is_implementation_blocker(self) -> None:
        rows = copy.deepcopy(self.rows)
        rows[2]["geometry"] = "numeric_feature_identifiers"
        with self.assertRaises(ValueError):
            CAMPAIGN.evaluate(rows, self.repeat)


if __name__ == "__main__":
    unittest.main()
