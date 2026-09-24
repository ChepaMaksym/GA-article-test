#!/usr/bin/env python3
from __future__ import annotations

import copy
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from hybrid_1.audit_validation import (  # noqa: E402
    corrected_capped,
    evaluate_strict,
    validate_row_strict,
)


TARGETS = (0.945, 0.946, 0.947)


def valid_row(
    seed: int,
    *,
    accuracy_difference: float = -0.0005,
    nfe_reduction: float = 0.30,
) -> dict:
    old_accuracy = 0.9500
    hybrid_accuracy = old_accuracy + accuracy_difference
    old_nfe = {"0.945000": 1000, "0.946000": 1200, "0.947000": 1500}
    hybrid_nfe = {
        key: int(round(value * (1.0 - nfe_reduction)))
        for key, value in old_nfe.items()
    }
    digest = f"{seed:064x}"[-64:]
    selected = list(range(6))
    mask = [1] * 6 + [0] * 35
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
            "selected_features": selected,
            "selected_feature_count": len(selected),
            "validation_accuracy": 0.949,
            "test_accuracy": hybrid_accuracy,
            "evaluations": 400,
            "generations": 20,
            "reset_events": 0,
            "nfe_to_target": {key: None for key in old_nfe},
            "best_evaluated_primary": None,
            "best_mask": mask,
        },
        "hybrid_h3": {
            "seed": seed,
            "search_seed": seed + 1_000_003,
            "budget": 2500,
            "workers": 1,
            "reset": True,
            "exact_first_hit": True,
            "selected_features": selected,
            "selected_feature_count": len(selected),
            "validation_accuracy": 0.951,
            "test_accuracy": hybrid_accuracy,
            "evaluations": 2500,
            "generations": 100,
            "reset_events": 2,
            "nfe_to_target": hybrid_nfe,
            "best_evaluated_primary": 0.952,
            "best_mask": mask,
        },
    }


class StrictAuditValidationTests(unittest.TestCase):
    def test_valid_thirty_seed_report_passes_strict_revalidation(self) -> None:
        rows = [valid_row(seed) for seed in range(1, 31)]
        report = evaluate_strict(rows, TARGETS)
        self.assertEqual(report["audit_status"], "PASS_STRICT_REVALIDATION")
        self.assertTrue(all(report["audit_gates"].values()))
        self.assertEqual(report["h1"]["decision"], "PASS_CONFIDENCE_BOUND")
        self.assertEqual(report["h2"]["decision"], "PASS")
        self.assertEqual(report["h3"]["primary_decision"], "PASS_CONFIDENCE_BOUND")

    def test_initial_population_target_hit_is_valid(self) -> None:
        self.assertEqual(corrected_capped(1, 2500), (1, True))
        self.assertEqual(corrected_capped(49, 2500), (49, True))
        self.assertEqual(corrected_capped(50, 2500), (50, True))

    def test_nonpositive_and_noninteger_target_nfe_fails_closed(self) -> None:
        with self.assertRaises(ValueError):
            corrected_capped(0, 2500)
        with self.assertRaises(ValueError):
            corrected_capped(-1, 2500)
        with self.assertRaises(TypeError):
            corrected_capped(True, 2500)
        with self.assertRaises(TypeError):
            corrected_capped(1.5, 2500)  # type: ignore[arg-type]

    def test_nonhex_digest_is_rejected(self) -> None:
        row = valid_row(1)
        bad_digest = "z" * 64
        row["active_indices_sha256"] = bad_digest
        row["old"]["active_indices_sha256"] = bad_digest
        with self.assertRaisesRegex(ValueError, "not hexadecimal"):
            validate_row_strict(row, 1, TARGETS)

    def test_reset_configuration_is_verified(self) -> None:
        row = valid_row(1)
        row["hybrid_h3"]["reset"] = False
        with self.assertRaisesRegex(ValueError, "reset=True"):
            validate_row_strict(row, 1, TARGETS)

    def test_feature_indices_must_match_mask(self) -> None:
        row = valid_row(1)
        row["hybrid_h1"]["best_mask"][6] = 1
        with self.assertRaisesRegex(ValueError, "disagree with best mask"):
            validate_row_strict(row, 1, TARGETS)

    def test_target_nfe_must_be_monotone(self) -> None:
        row = valid_row(1)
        row["hybrid_h3"]["nfe_to_target"] = {
            "0.945000": 100,
            "0.946000": 90,
            "0.947000": 120,
        }
        with self.assertRaisesRegex(ValueError, "not monotone"):
            validate_row_strict(row, 1, TARGETS)

    def test_target_hit_must_be_supported_by_best_fitness(self) -> None:
        row = valid_row(1)
        row["hybrid_h3"]["best_evaluated_primary"] = 0.946
        with self.assertRaisesRegex(ValueError, "exceeds recorded best"):
            validate_row_strict(row, 1, TARGETS)

    def test_scientific_failure_is_not_misreported_as_protocol_failure(self) -> None:
        rows = [
            valid_row(seed, accuracy_difference=-0.002, nfe_reduction=0.10)
            for seed in range(1, 31)
        ]
        report = evaluate_strict(rows, TARGETS)
        self.assertEqual(report["claim_status"], "PASS_PROTOCOL_RESULTS_AVAILABLE")
        self.assertEqual(
            report["h1"]["decision"],
            "FAIL_NONINFERIORITY_OR_BASELINE_GAIN",
        )
        self.assertEqual(report["h2"]["decision"], "BLOCKED_BY_H1")
        self.assertEqual(report["h2"]["unconditional_decision"], "PASS")
        self.assertEqual(
            report["h3"]["primary_decision"],
            "FAIL_OR_INSUFFICIENT_TARGET_COVERAGE",
        )

    def test_row_mutation_does_not_leak_between_cases(self) -> None:
        original = valid_row(1)
        mutated = copy.deepcopy(original)
        mutated["hybrid_h1"]["selected_features"].append(40)
        with self.assertRaises(ValueError):
            validate_row_strict(mutated, 1, TARGETS)
        validate_row_strict(original, 1, TARGETS)


if __name__ == "__main__":
    unittest.main()
