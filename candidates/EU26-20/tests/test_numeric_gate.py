#!/usr/bin/env python3
"""Unit tests for the preregistered EU26-20 numerical gate."""
from __future__ import annotations

import copy
import importlib.util
from pathlib import Path
import unittest

MODULE_PATH = Path(__file__).resolve().parents[1] / "old" / "run_colon_campaign.py"
SPEC = importlib.util.spec_from_file_location("eu26_20_campaign", MODULE_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("cannot load campaign module")
CAMPAIGN = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CAMPAIGN)


def result(seed: int, accuracy: float = 0.94, subset_length: int = 6) -> dict:
    features = list(range(seed * 10, seed * 10 + subset_length))
    return {
        "schema": "eu26-20-colon-old-v1",
        "profile": "author_source_compatibility",
        "seed": seed,
        "upstream_commit": "d24e61e78ac197ad75342e8f4be5d63d17bd9e7a",
        "offspring_rounding": "python_round_ties_to_even",
        "dataset_rows": 62,
        "raw_features": 2000,
        "class_labels": [1, 2],
        "class_counts": [22, 40],
        "search_space_size": 128,
        "baseline_accuracy": 0.69,
        "best_accuracy": accuracy,
        "subset_length": subset_length,
        "features": features,
        "precision": accuracy,
        "recall": accuracy,
        "fscore": accuracy,
        "mcc": 0.85,
        "nfe": 788 + seed,
        "iterations": 40 + seed,
        "adaptive_events": 3,
        "final_pc": 0.3,
        "final_pm": 0.8,
        "first_target_iteration": 10,
        "first_target_nfe": 260,
        "source_sha256": "a" * 64,
        "dataset_sha256": "b" * 64,
        "features_sha256": "c" * 64,
    }


class NumericGateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.rows = [result(seed) for seed in range(1, 11)]
        self.repeat = copy.deepcopy(self.rows[0])

    def test_exact_paper_endpoint_passes(self) -> None:
        report = CAMPAIGN.evaluate_campaign(self.rows, self.repeat)
        self.assertEqual(report["claim_status"], "PASS_OLD_REPRODUCTION")
        self.assertTrue(all(gate["pass"] for gate in report["gates"].values()))

    def test_systematically_too_high_endpoint_does_not_masquerade_as_reproduction(self) -> None:
        rows = [result(seed, accuracy=0.99) for seed in range(1, 11)]
        repeat = copy.deepcopy(rows[0])
        report = CAMPAIGN.evaluate_campaign(rows, repeat)
        self.assertEqual(report["claim_status"], "BLOCKED_NUMERIC_MISMATCH")
        self.assertFalse(report["gates"]["G3_final_accuracy_alignment"]["pass"])

    def test_subset_mismatch_blocks_reproduction(self) -> None:
        rows = [result(seed, subset_length=10) for seed in range(1, 11)]
        repeat = copy.deepcopy(rows[0])
        report = CAMPAIGN.evaluate_campaign(rows, repeat)
        self.assertEqual(report["claim_status"], "BLOCKED_NUMERIC_MISMATCH")
        self.assertFalse(report["gates"]["G4_subset_length_alignment"]["pass"])

    def test_repeat_mismatch_is_implementation_blocker(self) -> None:
        repeat = copy.deepcopy(self.repeat)
        repeat["features"] = [999, 1000, 1001, 1002, 1003, 1004]
        report = CAMPAIGN.evaluate_campaign(self.rows, repeat)
        self.assertEqual(report["claim_status"], "BLOCKED_IMPLEMENTATION_OR_PROVENANCE")
        self.assertFalse(report["gates"]["G1_deterministic_replay"]["pass"])

    def test_identity_mismatch_is_implementation_blocker(self) -> None:
        rows = copy.deepcopy(self.rows)
        rows[1]["dataset_sha256"] = "d" * 64
        report = CAMPAIGN.evaluate_campaign(rows, self.repeat)
        self.assertEqual(report["claim_status"], "BLOCKED_IMPLEMENTATION_OR_PROVENANCE")
        self.assertFalse(report["gates"]["G0_provenance_structure"]["pass"])

    def test_wrong_seed_order_fails_closed(self) -> None:
        rows = copy.deepcopy(self.rows)
        rows[0], rows[1] = rows[1], rows[0]
        with self.assertRaises(ValueError):
            CAMPAIGN.evaluate_campaign(rows, self.repeat)


if __name__ == "__main__":
    unittest.main()
