#!/usr/bin/env python3
from __future__ import annotations

import copy
import importlib.util
from pathlib import Path
import sys
import unittest

OLD_DIR = Path(__file__).resolve().parents[1] / "old"
sys.path.insert(0, str(OLD_DIR))
SPEC = importlib.util.spec_from_file_location(
    "eu26_20_sensitivity_campaign", OLD_DIR / "run_sensitivity_campaign.py"
)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("cannot load sensitivity campaign")
CAMPAIGN = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CAMPAIGN)


def row(seed: int, accuracy: float = 0.94, subset: int = 6) -> dict:
    return {
        "schema": "eu26-20-colon-sensitivity-v1",
        "profile": "old_sensitivity_only",
        "variant": "source_rounding",
        "seed": seed,
        "primary_gate_eligible": False,
        "upstream_commit": "d24e61e78ac197ad75342e8f4be5d63d17bd9e7a",
        "dataset_rows": 62,
        "raw_features": 2000,
        "class_labels": [1, 2],
        "class_counts": [22, 40],
        "search_space_size": 128,
        "baseline_accuracy": 0.69,
        "numpy_rng_mode": "pcg64",
        "offspring_rounding": "source_round_ties_to_even",
        "stop_after": 20,
        "geometry": "feature_vectors_euclidean",
        "best_accuracy": accuracy,
        "subset_length": subset,
        "features": list(range(seed * 20, seed * 20 + subset)),
        "accuracy": accuracy,
        "precision": accuracy,
        "recall": accuracy,
        "fscore": accuracy,
        "mcc": 0.8,
        "nfe": 788 + seed,
        "iterations": 30,
        "adaptive_events": 3,
        "final_pc": 0.0,
        "final_pm": 1.0,
        "stagnation": 20,
        "first_target_iteration": 10,
        "first_target_nfe": 250,
        "source_sha256": "a" * 64,
        "dataset_sha256": "b" * 64,
        "features_sha256": "c" * 64,
        "trace": [],
    }


class SensitivityCampaignTests(unittest.TestCase):
    def test_aligned_variant_remains_sensitivity_only(self) -> None:
        rows = [row(seed) for seed in range(1, 11)]
        report = CAMPAIGN.evaluate(rows, copy.deepcopy(rows[0]), "source_rounding")
        self.assertEqual(report["claim_status"], "ALIGNED_SENSITIVITY_ONLY")
        self.assertNotIn("PASS_OLD_REPRODUCTION", report["claim_status"])

    def test_subset_mismatch_is_reported(self) -> None:
        rows = [row(seed, subset=10) for seed in range(1, 11)]
        report = CAMPAIGN.evaluate(rows, copy.deepcopy(rows[0]), "source_rounding")
        self.assertEqual(report["claim_status"], "SENSITIVITY_MISMATCH")
        self.assertFalse(report["gates"]["S4_subset_alignment"]["pass"])

    def test_determinism_mismatch_blocks_interpretation(self) -> None:
        rows = [row(seed) for seed in range(1, 11)]
        repeat = copy.deepcopy(rows[0])
        repeat["nfe"] += 1
        report = CAMPAIGN.evaluate(rows, repeat, "source_rounding")
        self.assertEqual(
            report["claim_status"],
            "BLOCKED_SENSITIVITY_IMPLEMENTATION_OR_PROVENANCE",
        )

    def test_primary_eligibility_mutation_fails_closed(self) -> None:
        rows = [row(seed) for seed in range(1, 11)]
        rows[2]["primary_gate_eligible"] = True
        with self.assertRaises(ValueError):
            CAMPAIGN.evaluate(rows, copy.deepcopy(rows[0]), "source_rounding")


if __name__ == "__main__":
    unittest.main()
