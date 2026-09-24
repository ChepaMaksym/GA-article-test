#!/usr/bin/env python3
from __future__ import annotations

import copy
import importlib.util
from pathlib import Path
import unittest

MODULE_PATH = Path(__file__).resolve().parents[1] / "old" / "run_source_campaign.py"
SPEC = importlib.util.spec_from_file_location("eu26_21_source_campaign", MODULE_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("cannot load source campaign")
CAMPAIGN = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CAMPAIGN)

TARGET_VALUES = [94.84, 94.88, 94.91, 94.93, 94.94, 94.94, 94.95, 94.96, 95.00, 95.04]


def result(seed: int, test_percent: float | None = None) -> dict:
    percent = TARGET_VALUES[seed - 1] if test_percent is None else test_percent
    selected = [12, 16, 17, 19, 40]
    return {
        "schema": "eu26-21-census-source-v1",
        "profile": "author_source_seeded",
        "seed": seed,
        "upstream_commit": "6ac5a7ec77f8a7c096ab4d019254fcc897988fd6",
        "dataset_rows": 199_523,
        "raw_features": 41,
        "target_labels": [0, 1],
        "target_counts": [187_141, 12_382],
        "split_sizes": [119_713, 39_905, 39_905],
        "baseline_validation_accuracy": 0.9287,
        "baseline_test_accuracy": 0.9287,
        "meta_model_sample_size": 14_964,
        "controlled_individuals": 10,
        "evolution_control_frequency": 10,
        "outer_no_change_limit": 2,
        "population_size": 50,
        "chc_chunk_count": 8,
        "chc_chunk_final_d": [8, 7, 7, 6, 6, 5, 5, 4],
        "chc_chunk_improvement_rows": [3, 1, 2, 0, 1, 0, 0, 0],
        "improvement_rows": 4,
        "validation_fitness": percent / 100.0 - 0.0005,
        "test_accuracy": percent / 100.0,
        "selected_feature_count": len(selected),
        "selected_features": selected,
        "feature_mask": [1 if index in selected else 0 for index in range(41)],
        "elapsed_seconds": 50.0 + seed,
        "source_sha256": "a" * 64,
        "dataset_source_sha256": "b" * 64,
        "notebook_sha256": "c" * 64,
        "data_sha256": "d" * 64,
        "python_hash_seed": "0",
    }


class SourceCampaignTests(unittest.TestCase):
    def setUp(self) -> None:
        self.results = [result(seed) for seed in range(1, 11)]
        self.repeat = copy.deepcopy(self.results[0])
        self.repeat["elapsed_seconds"] = 999.0

    def test_aligned_endpoint_passes(self) -> None:
        report = CAMPAIGN.evaluate(self.results, self.repeat)
        self.assertEqual(report["claim_status"], "PASS_SOURCE_NUMERIC_ALIGNMENT")
        self.assertTrue(all(gate["pass"] for gate in report["gates"].values()))

    def test_median_mismatch_blocks(self) -> None:
        results = [result(seed, 95.50) for seed in range(1, 11)]
        repeat = copy.deepcopy(results[0])
        report = CAMPAIGN.evaluate(results, repeat)
        self.assertEqual(report["claim_status"], "BLOCKED_SOURCE_NUMERIC_MISMATCH")
        self.assertFalse(report["gates"]["S3_chcqx_median_alignment"]["pass"])

    def test_high_dispersion_blocks(self) -> None:
        values = [94.2, 94.4, 94.6, 94.8, 94.9, 95.0, 95.1, 95.2, 95.4, 95.6]
        results = [result(seed, values[seed - 1]) for seed in range(1, 11)]
        repeat = copy.deepcopy(results[0])
        report = CAMPAIGN.evaluate(results, repeat)
        self.assertEqual(report["claim_status"], "BLOCKED_SOURCE_NUMERIC_MISMATCH")
        self.assertFalse(report["gates"]["S4_run_dispersion"]["pass"])

    def test_repeat_mismatch_is_provenance_blocker(self) -> None:
        repeat = copy.deepcopy(self.repeat)
        repeat["selected_features"] = [10, 12, 16, 17]
        repeat["selected_feature_count"] = 4
        repeat["feature_mask"] = [
            1 if index in repeat["selected_features"] else 0 for index in range(41)
        ]
        report = CAMPAIGN.evaluate(self.results, repeat)
        self.assertEqual(
            report["claim_status"],
            "BLOCKED_SOURCE_IMPLEMENTATION_OR_PROVENANCE",
        )
        self.assertFalse(
            report["gates"]["S1_deterministic_source_replay"]["pass"]
        )

    def test_identity_mismatch_is_provenance_blocker(self) -> None:
        results = copy.deepcopy(self.results)
        results[3]["data_sha256"] = "e" * 64
        report = CAMPAIGN.evaluate(results, self.repeat)
        self.assertEqual(
            report["claim_status"],
            "BLOCKED_SOURCE_IMPLEMENTATION_OR_PROVENANCE",
        )
        self.assertFalse(report["gates"]["S0_provenance_structure"]["pass"])

    def test_invalid_subset_fails_closed(self) -> None:
        invalid = copy.deepcopy(self.results[0])
        invalid["selected_features"] = []
        invalid["selected_feature_count"] = 0
        invalid["feature_mask"] = [0] * 41
        with self.assertRaises(ValueError):
            CAMPAIGN.validate_result(invalid, 1)

    def test_wrong_seed_order_fails_closed(self) -> None:
        results = copy.deepcopy(self.results)
        results[0], results[1] = results[1], results[0]
        with self.assertRaises(ValueError):
            CAMPAIGN.evaluate(results, self.repeat)


if __name__ == "__main__":
    unittest.main()
