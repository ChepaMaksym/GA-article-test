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
    "eu26_20_source_campaign_v2", OLD_DIR / "run_colon_campaign_v2.py"
)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("cannot load source campaign v2")
CAMPAIGN = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CAMPAIGN)


def row(seed: int, accuracy: float = 0.94, subset: int = 6) -> dict:
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
        "subset_length": subset,
        "features": list(range(seed * 20, seed * 20 + subset)),
        "precision": accuracy,
        "recall": accuracy,
        "fscore": accuracy,
        "mcc": 0.8,
        "nfe": 788 + seed,
        "iterations": 30,
        "adaptive_events": 3,
        "final_pc": 0.0,
        "final_pm": 1.0,
        "first_target_iteration": 10,
        "first_target_nfe": 250,
        "source_sha256": "a" * 64,
        "dataset_sha256": "b" * 64,
        "features_sha256": "c" * 64,
    }


class SourceCampaignV2Tests(unittest.TestCase):
    def test_exact_target_passes(self) -> None:
        rows = [row(seed) for seed in range(1, 11)]
        report = CAMPAIGN.evaluate_successes(rows, copy.deepcopy(rows[0]))
        self.assertEqual(report["claim_status"], "PASS_SOURCE_NUMERIC_ALIGNMENT")

    def test_accuracy_mismatch_blocks(self) -> None:
        rows = [row(seed, accuracy=0.99) for seed in range(1, 11)]
        report = CAMPAIGN.evaluate_successes(rows, copy.deepcopy(rows[0]))
        self.assertEqual(report["claim_status"], "BLOCKED_SOURCE_NUMERIC_MISMATCH")

    def test_repeat_mismatch_blocks_provenance(self) -> None:
        rows = [row(seed) for seed in range(1, 11)]
        repeated = copy.deepcopy(rows[0])
        repeated["nfe"] += 1
        report = CAMPAIGN.evaluate_successes(rows, repeated)
        self.assertEqual(
            report["claim_status"], "BLOCKED_SOURCE_IMPLEMENTATION_OR_PROVENANCE"
        )


if __name__ == "__main__":
    unittest.main()
