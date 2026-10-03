#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from hybrid_1.paired_comparison_v2 import SequentialTargetObjective  # noqa: E402
from hybrid_1.run_old_hybrid_comparison_v2 import evaluate  # noqa: E402


class SymmetricFirstHitTests(unittest.TestCase):
    def test_sequential_tracker_records_first_evaluated_mask(self) -> None:
        scores = {
            (1, 0): (0.944, -0.5),
            (0, 1): (0.946, -0.5),
            (1, 1): (0.947, -1.0),
        }
        tracker = SequentialTargetObjective(
            lambda mask: scores[tuple(mask)],
            targets=(0.945, 0.946, 0.947),
        )
        tracker((1, 0))
        tracker((0, 1))
        tracker((1, 1))
        self.assertEqual(tracker.calls, 3)
        self.assertEqual(tracker.first_hit["0.945000"], 2)
        self.assertEqual(tracker.first_hit["0.946000"], 2)
        self.assertEqual(tracker.first_hit["0.947000"], 3)

    @staticmethod
    def _row(seed: int, *, accuracy_difference: float, nfe_reduction: float) -> dict:
        old_accuracy = 0.9500
        hybrid_accuracy = old_accuracy + accuracy_difference
        old_nfe = {"0.945000": 1000, "0.946000": 1200, "0.947000": 1500}
        hybrid_nfe = {
            key: int(round(value * (1.0 - nfe_reduction)))
            for key, value in old_nfe.items()
        }
        digest = f"{seed:064x}"[-64:]
        return {
            "schema": "eu26-21-old-hybrid-paired-row-v2",
            "seed": seed,
            "active_sample_size": 14964,
            "active_indices_sha256": digest,
            "baseline_validation_accuracy": 0.92,
            "baseline_test_accuracy": 0.92,
            "initial_population": 50,
            "initial_masks_sha256": digest,
            "old": {
                "seed": seed,
                "search_seed": seed + 1_000_003,
                "active_sample_size": 14964,
                "active_indices_sha256": digest,
                "selected_features": list(range(10)),
                "validation_accuracy": 0.951,
                "test_accuracy": old_accuracy,
                "active_nfe": 1500,
                "full_validation_nfe": 100,
                "optimizer_nfe": 1600,
                "chunks": 5,
                "final_distance": 4,
                "active_nfe_to_target": old_nfe,
                "best_active_fitness": 0.952,
            },
            "hybrid_h1": {
                "seed": seed,
                "search_seed": seed + 1_000_003,
                "budget": 400,
                "workers": 4,
                "reset": True,
                "exact_first_hit": False,
                "selected_features": list(range(6)),
                "selected_feature_count": 6,
                "validation_accuracy": 0.949,
                "test_accuracy": hybrid_accuracy,
                "evaluations": 400,
                "generations": 20,
                "reset_events": 0,
                "nfe_to_target": {
                    "0.945000": None,
                    "0.946000": None,
                    "0.947000": None,
                },
                "best_evaluated_primary": None,
                "best_mask": [1] * 6 + [0] * 35,
            },
            "hybrid_h3": {
                "seed": seed,
                "search_seed": seed + 1_000_003,
                "budget": 2500,
                "workers": 1,
                "reset": True,
                "exact_first_hit": True,
                "selected_features": list(range(6)),
                "selected_feature_count": 6,
                "validation_accuracy": 0.951,
                "test_accuracy": hybrid_accuracy,
                "evaluations": 2500,
                "generations": 100,
                "reset_events": 2,
                "nfe_to_target": hybrid_nfe,
                "best_evaluated_primary": 0.952,
                "best_mask": [1] * 6 + [0] * 35,
            },
        }

    def test_confidence_bound_h1_and_h3_pass_when_all_pairs_clear_margin(self) -> None:
        rows = [
            self._row(seed, accuracy_difference=-0.0005, nfe_reduction=0.30)
            for seed in range(1, 31)
        ]
        report = evaluate(rows, (0.945, 0.946, 0.947))
        self.assertEqual(report["claim_status"], "PASS_PROTOCOL_RESULTS_AVAILABLE")
        self.assertEqual(report["h1"]["decision"], "PASS_CONFIDENCE_BOUND")
        self.assertEqual(report["h2"]["decision"], "PASS")
        self.assertEqual(report["h3"]["primary_decision"], "PASS_CONFIDENCE_BOUND")

    def test_two_sided_lower_bound_failure_is_not_hidden(self) -> None:
        rows = [
            self._row(seed, accuracy_difference=-0.0015, nfe_reduction=0.10)
            for seed in range(1, 31)
        ]
        report = evaluate(rows, (0.945, 0.946, 0.947))
        self.assertEqual(
            report["h1"]["decision"],
            "FAIL_NONINFERIORITY_OR_BASELINE_GAIN",
        )
        self.assertEqual(
            report["h3"]["primary_decision"],
            "FAIL_OR_INSUFFICIENT_TARGET_COVERAGE",
        )


if __name__ == "__main__":
    unittest.main()
