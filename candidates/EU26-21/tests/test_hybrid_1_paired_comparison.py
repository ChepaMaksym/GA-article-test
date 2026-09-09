#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from hybrid_1.core import GenerationTrace, RunResult  # noqa: E402
from hybrid_1.paired_comparison import hybrid_nfe_to_targets  # noqa: E402
from hybrid_1.run_old_hybrid_comparison import (  # noqa: E402
    _bca_quantiles,
    evaluate_rows,
)


class HybridOnePairedComparisonTests(unittest.TestCase):
    def test_hybrid_target_nfe_uses_accepted_parent_trajectory(self) -> None:
        result = RunResult(
            seed=1,
            dimension=4,
            workers=1,
            evaluations=56,
            generations=3,
            reset_events=0,
            best_mask=(1, 1, 1, 0),
            best_fitness=(0.946, -0.75),
            solved=False,
            trace=(
                GenerationTrace(
                    generation=1,
                    evaluations=52,
                    lambda_before=1.0,
                    lambda_after=1.0,
                    offspring_count=1,
                    mutation_probability=0.25,
                    crossover_probability=1.0,
                    mutation_strength=1,
                    best_mutant_primary=0.945,
                    best_mutant_secondary=-0.50,
                    parent_primary_before=0.940,
                    parent_secondary_before=-0.50,
                    candidate_primary=0.945,
                    candidate_secondary=-0.50,
                    strict_success=True,
                    accepted=True,
                    reset_event=False,
                    parent_ones_after=2,
                ),
                GenerationTrace(
                    generation=2,
                    evaluations=54,
                    lambda_before=1.0,
                    lambda_after=1.0,
                    offspring_count=1,
                    mutation_probability=0.25,
                    crossover_probability=1.0,
                    mutation_strength=1,
                    best_mutant_primary=0.946,
                    best_mutant_secondary=-0.75,
                    parent_primary_before=0.945,
                    parent_secondary_before=-0.50,
                    candidate_primary=0.946,
                    candidate_secondary=-0.75,
                    strict_success=True,
                    accepted=True,
                    reset_event=False,
                    parent_ones_after=3,
                ),
                GenerationTrace(
                    generation=3,
                    evaluations=56,
                    lambda_before=1.0,
                    lambda_after=1.1066819197003215,
                    offspring_count=1,
                    mutation_probability=0.25,
                    crossover_probability=1.0,
                    mutation_strength=0,
                    best_mutant_primary=0.946,
                    best_mutant_secondary=-0.75,
                    parent_primary_before=0.946,
                    parent_secondary_before=-0.75,
                    candidate_primary=0.946,
                    candidate_secondary=-0.75,
                    strict_success=False,
                    accepted=True,
                    reset_event=False,
                    parent_ones_after=3,
                ),
            ),
        )
        observed = hybrid_nfe_to_targets(
            result,
            targets=(0.945, 0.946, 0.947),
            initial_evaluations=50,
        )
        self.assertEqual(observed["0.945000"], 52)
        self.assertEqual(observed["0.946000"], 54)
        self.assertIsNone(observed["0.947000"])

    def test_bca_constant_vector_is_exact(self) -> None:
        observed = _bca_quantiles(
            [-0.0005] * 30,
            alphas=(0.025, 0.05, 0.975),
            seed=1,
            resamples=5_000,
        )
        self.assertEqual(observed["0.025000"], -0.0005)
        self.assertEqual(observed["0.050000"], -0.0005)
        self.assertEqual(observed["0.975000"], -0.0005)

    @staticmethod
    def _row(seed: int, hybrid_difference: float = -0.0005) -> dict:
        old_accuracy = 0.9500
        hybrid_accuracy = old_accuracy + hybrid_difference
        targets = {
            "0.945000": 900,
            "0.946000": 1_000,
            "0.947000": 1_100,
        }
        hybrid_targets = {
            "0.945000": 400,
            "0.946000": 500,
            "0.947000": 550,
        }
        digest = f"{seed:064x}"[-64:]
        return {
            "seed": seed,
            "active_sample_size": 14_964,
            "active_indices_sha256": digest,
            "baseline_validation_accuracy": 0.92,
            "baseline_test_accuracy": 0.92,
            "initial_population": 50,
            "initial_masks_sha256": digest,
            "old": {
                "seed": seed,
                "search_seed": seed + 1_000_003,
                "active_sample_size": 14_964,
                "active_indices_sha256": digest,
                "selected_features": list(range(10)),
                "validation_accuracy": 0.951,
                "test_accuracy": old_accuracy,
                "active_nfe": 1_200,
                "full_validation_nfe": 100,
                "optimizer_nfe": 1_300,
                "chunks": 5,
                "final_distance": 4,
                "active_nfe_to_target": targets,
                "best_active_fitness": 0.952,
            },
            "hybrid_h1": {
                "seed": seed,
                "search_seed": seed + 1_000_003,
                "budget": 400,
                "workers": 4,
                "reset": True,
                "selected_features": list(range(6)),
                "selected_feature_count": 6,
                "validation_accuracy": 0.949,
                "test_accuracy": hybrid_accuracy,
                "evaluations": 400,
                "generations": 20,
                "reset_events": 0,
                "nfe_to_target": {
                    "0.945000": 200,
                    "0.946000": 300,
                    "0.947000": None,
                },
                "best_mask": [1] * 6 + [0] * 35,
            },
            "hybrid_h3": {
                "seed": seed,
                "search_seed": seed + 1_000_003,
                "budget": 2_500,
                "workers": 4,
                "reset": True,
                "selected_features": list(range(6)),
                "selected_feature_count": 6,
                "validation_accuracy": 0.951,
                "test_accuracy": hybrid_accuracy,
                "evaluations": 2_500,
                "generations": 100,
                "reset_events": 2,
                "nfe_to_target": hybrid_targets,
                "best_mask": [1] * 6 + [0] * 35,
            },
        }

    def test_synthetic_30_seed_campaign_passes_confidence_h1_and_h3(self) -> None:
        rows = [self._row(seed) for seed in range(1, 31)]
        report = evaluate_rows(
            rows,
            h1_margin=0.001,
            primary_target=0.946,
            targets=(0.945, 0.946, 0.947),
            h3_budget=2_500,
            resamples=5_000,
        )
        self.assertEqual(report["claim_status"], "PASS_PROTOCOL_RESULTS_AVAILABLE")
        self.assertEqual(report["h1"]["decision"], "PASS_CONFIDENCE_BOUND")
        self.assertEqual(report["h2"]["decision"], "PASS")
        self.assertEqual(report["h3"]["primary_decision"], "PASS_CONFIDENCE_BOUND")

    def test_noninferiority_failure_is_reported_not_hidden(self) -> None:
        rows = [self._row(seed, hybrid_difference=-0.002) for seed in range(1, 31)]
        report = evaluate_rows(
            rows,
            h1_margin=0.001,
            primary_target=0.946,
            targets=(0.945, 0.946, 0.947),
            h3_budget=2_500,
            resamples=5_000,
        )
        self.assertEqual(
            report["h1"]["decision"],
            "FAIL_NONINFERIORITY_OR_BASELINE_GAIN",
        )


if __name__ == "__main__":
    unittest.main()
