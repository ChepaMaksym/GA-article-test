#!/usr/bin/env python3
"""CI-only contracts for the prospective EU26-21 common bridge."""
from __future__ import annotations

import copy
import json
from pathlib import Path
import random
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from common_bridge import aggregate, fetch_source_artifacts, run_seed, search  # noqa: E402
from common_bridge.search import (  # noqa: E402
    BudgetLedger,
    run_harmonized_chc,
    run_lambda_no_reset,
)


def _initial_masks(count: int = 50, dimension: int = 40) -> list[tuple[int, ...]]:
    masks: list[tuple[int, ...]] = []
    for index in range(count):
        code = index + 1
        masks.append(
            tuple(
                ((code >> (bit % 6)) ^ (bit // 6)) & 1
                for bit in range(dimension)
            )
        )
    return masks


def _toy_objective(mask: tuple[int, ...]) -> tuple[float, float]:
    count = sum(mask)
    return count / len(mask), -count / len(mask)


class BudgetLedgerTests(unittest.TestCase):
    def test_duplicate_calls_consume_budget_and_exact_tie_keeps_earlier(self) -> None:
        scores = iter(
            [
                (0.80, -0.50),
                (0.80, -0.50),
                (0.80, -0.25),
                (0.80, -0.25),
            ]
        )
        invoked: list[tuple[int, ...]] = []

        def objective(mask: tuple[int, ...]) -> tuple[float, float]:
            invoked.append(mask)
            return next(scores)

        ledger = BudgetLedger(objective, budget=4, dimension=2)
        duplicate = (1, 0)
        for _ in range(4):
            ledger.evaluate(duplicate)

        self.assertEqual(ledger.calls, 4)
        self.assertEqual(invoked, [duplicate] * 4)
        self.assertEqual(ledger.terminal_call, 3)
        self.assertEqual(ledger.terminal_fitness, (0.80, -0.25))
        self.assertEqual(ledger.normalized_auc(), 0.80)
        with self.assertRaisesRegex(RuntimeError, "budget exhausted"):
            ledger.evaluate(duplicate)

    def test_best_so_far_auc_and_mask_guards(self) -> None:
        scores = iter([0.2, 0.1, 0.4, 0.3])
        ledger = BudgetLedger(lambda _mask: next(scores), budget=4, dimension=2)
        ledger.evaluate_many([(0, 0), (0, 1), (1, 0), (1, 1)])
        self.assertEqual(
            [row.best_so_far_weighted_balanced_accuracy for row in ledger.records],
            [0.2, 0.2, 0.4, 0.4],
        )
        self.assertAlmostEqual(ledger.normalized_auc(), 0.3)
        self.assertEqual(ledger.terminal_call, 3)

        guarded = BudgetLedger(_toy_objective, budget=2, dimension=2)
        with self.assertRaises(ValueError):
            guarded.evaluate((0, 1, 0))
        with self.assertRaises(ValueError):
            guarded.evaluate((0, 2))
        self.assertEqual(guarded.calls, 0)


class SearchMechanismTests(unittest.TestCase):
    def test_hux_matches_pinned_source_rng_tape(self) -> None:
        first = (0, 0, 0, 0, 1, 1, 1, 1)
        second = (1, 1, 1, 1, 0, 0, 0, 0)

        def reference(
            left_mask: tuple[int, ...],
            right_mask: tuple[int, ...],
            rng: random.Random,
        ) -> tuple[tuple[int, ...], tuple[int, ...]]:
            left = list(left_mask)
            right = list(right_mask)
            differing = [i for i, pair in enumerate(zip(left, right)) if pair[0] != pair[1]]
            rng.randrange(1, len(differing))
            first_positions = rng.sample(differing, len(differing) // 2)
            old_left = list(left)
            for position in first_positions:
                left[position] = right[position]
            rng.randrange(1, len(differing))
            second_positions = rng.sample(differing, len(differing) // 2)
            for position in second_positions:
                right[position] = old_left[position]
            return tuple(left), tuple(right)

        expected = reference(first, second, random.Random(90210))
        observed = search._pinned_source_hux(  # noqa: SLF001
            first,
            second,
            random.Random(90210),
        )
        self.assertEqual(observed, expected)
        self.assertEqual(sum(a != b for a, b in zip(first, observed[0])), 4)
        self.assertEqual(sum(a != b for a, b in zip(second, observed[1])), 4)

    def test_chc_partial_prefix_rolls_back_population_and_distance_update(self) -> None:
        initial = [
            (0, 0, 0, 1),
            (0, 0, 1, 0),
            (0, 1, 0, 0),
            (1, 0, 0, 0),
        ]

        def flip_first(
            mask: tuple[int, ...],
            _probability: float,
            _rng: random.Random,
        ) -> tuple[int, ...]:
            return (1 - mask[0], *mask[1:])

        result = run_harmonized_chc(
            _toy_objective,
            initial,
            seed=77,
            budget=6,
            initial_distance=0,
            cataclysmic_mutation=flip_first,
        )
        self.assertEqual(result.objective_calls, 6)
        self.assertEqual(result.termination_phase, "partial_chc_offspring_prefix")
        self.assertTrue(result.terminal_state["partial_population_update_skipped"])
        self.assertEqual(result.terminal_state["final_distance"], 0)
        self.assertEqual(result.terminal_state["population_size"], 4)
        self.assertEqual(result.generation_trace[-1]["evaluated_fresh_offspring"], 2)

    def test_both_arms_are_exact_paired_deterministic_and_reset_free(self) -> None:
        initial = _initial_masks()
        chc = run_harmonized_chc(_toy_objective, initial, seed=104104, budget=400)
        lam = run_lambda_no_reset(_toy_objective, initial, seed=104104, budget=400)

        self.assertEqual(chc.objective_calls, 400)
        self.assertEqual(lam.objective_calls, 400)
        self.assertFalse(chc.reset)
        self.assertFalse(lam.reset)
        self.assertEqual(chc.reset_events, 0)
        self.assertEqual(lam.reset_events, 0)
        self.assertEqual(
            [record.to_dict() for record in chc.evaluations[:50]],
            [record.to_dict() for record in lam.evaluations[:50]],
        )
        self.assertTrue(
            all(
                1.0 <= row["lambda_before"] <= 40.0
                and 1.0 <= row["lambda_after"] <= 40.0
                and (row["calls_after"] - row["calls_before"]) % 2 == 0
                for row in lam.generation_trace
            )
        )

        chc_again = run_harmonized_chc(
            _toy_objective,
            initial,
            seed=104104,
            budget=400,
        )
        lam_again = run_lambda_no_reset(
            _toy_objective,
            initial,
            seed=104104,
            budget=400,
        )
        self.assertEqual(chc.evaluations, chc_again.evaluations)
        self.assertEqual(chc.generation_trace, chc_again.generation_trace)
        self.assertEqual(lam.evaluations, lam_again.evaluations)
        self.assertEqual(lam.generation_trace, lam_again.generation_trace)

    def test_trace_contains_no_test_outcome_keys(self) -> None:
        result = run_lambda_no_reset(
            _toy_objective,
            _initial_masks(count=4, dimension=4),
            seed=22,
            budget=8,
            lambda_max=4.0,
        )
        trace = result.to_trace_dict(
            seed=41001,
            provenance={"config_sha256": "a" * 64, "implementation_sha": "b" * 40},
            pairing={"initial_masks_sha256": "c" * 64},
        )

        def keys(value: object) -> list[str]:
            collected: list[str] = []
            if isinstance(value, dict):
                for key, child in value.items():
                    collected.append(str(key))
                    collected.extend(keys(child))
            elif isinstance(value, list):
                for child in value:
                    collected.extend(keys(child))
            return collected

        self.assertFalse(any("test" in key.lower() for key in keys(trace)))
        self.assertEqual(trace["config_sha256"], "a" * 64)


class EvidenceContractTests(unittest.TestCase):
    def test_pairing_formulas_and_initial_mask_binding_are_fail_closed(self) -> None:
        seed = 41001
        pairing = {
            "seed": seed,
            "split_seed": 2_026_081_700 + seed,
            "active_sample_seed": 2_026_081_800 + seed,
            "search_seed": seed + 1_000_003,
            "initial_mask_seed": seed + 1_000_102,
            "initial_mask_count": 50,
            "dimension": 40,
            "split_sha256": "a" * 64,
            "active_indices_sha256": "b" * 64,
            "evaluator_sha256": "c" * 64,
            "initial_masks_sha256": "d" * 64,
            "first_50_evaluations_sha256": "e" * 64,
        }
        normalized = aggregate._validate_pairing(  # noqa: SLF001
            pairing,
            "pairing",
            seed=seed,
        )
        self.assertEqual(normalized["search_seed"], seed + 1_000_003)
        changed = dict(pairing)
        changed["split_seed"] += 1
        with self.assertRaises(aggregate.EvidenceError):
            aggregate._validate_pairing(changed, "pairing", seed=seed)  # noqa: SLF001

    def test_empty_mask_uses_frozen_shortcut_fitness(self) -> None:
        mask = [0] * 40
        row = {
            "call": 1,
            "mask": mask,
            "mask_sha256": aggregate.canonical_sha256(mask),
            "validation_weighted_balanced_accuracy": 0.0,
            "negative_selected_feature_fraction": -1.0,
            "selected_feature_count": 0,
            "best_so_far_weighted_balanced_accuracy": 0.0,
            "terminal_best_update": True,
        }
        normalized = aggregate._validate_evaluation(  # noqa: SLF001
            row,
            seed=41001,
            arm="chc_harmonized",
            expected_call=1,
        )
        self.assertEqual(normalized["negative_selected_feature_fraction"], -1.0)
        invalid = dict(row)
        invalid["validation_weighted_balanced_accuracy"] = 0.1
        with self.assertRaises(aggregate.EvidenceError):
            aggregate._validate_evaluation(  # noqa: SLF001
                invalid,
                seed=41001,
                arm="chc_harmonized",
                expected_call=1,
            )

    def test_negative_scientific_result_remains_protocol_valid(self) -> None:
        rows = []
        for _ in range(30):
            rows.append(
                {
                    "arms": {
                        "chc_harmonized": {
                            "auc": 0.50,
                            "post_initial_auc": 0.50,
                            "terminal": {
                                "test_weighted_balanced_accuracy": 0.80,
                                "selected_feature_count": 20,
                            },
                        },
                        "lambda_no_reset": {
                            "auc": 0.60,
                            "post_initial_auc": 0.62,
                            "terminal": {
                                "test_weighted_balanced_accuracy": 0.798,
                                "selected_feature_count": 15,
                            },
                        },
                    }
                }
            )
        report = aggregate.analyze_rows(rows)
        self.assertEqual(
            report["quality_noninferiority"]["decision"],
            "FAIL_NONINFERIORITY",
        )
        self.assertEqual(
            report["auc_superiority"]["decision"],
            "BLOCKED_BY_QUALITY_NONINFERIORITY",
        )
        self.assertEqual(
            report["auc_calls_51_400_descriptive"]["decision"],
            "DESCRIPTIVE_ONLY",
        )
        self.assertEqual(report["quality_noninferiority"]["resamples"], 50_000)

    def test_canonical_hash_and_artifact_ledger_validation(self) -> None:
        self.assertEqual(
            aggregate.canonical_sha256({"b": 2, "a": 1}),
            aggregate.canonical_sha256({"a": 1, "b": 2}),
        )
        with self.assertRaises(aggregate.EvidenceError):
            aggregate.canonical_sha256({"invalid": float("nan")})

        run_id = 321
        attempt = 1
        ledger = {
            "schema": fetch_source_artifacts.EXPECTED_SCHEMA,
            "repository": "ChepaMaksym/GA-article-test",
            "source_run_id": run_id,
            "source_run_attempt": attempt,
            "source_head_sha": "a" * 40,
            "source_ref": "refs/tags/eu26-21-common-bridge-evidence-v1",
            "source_workflow_sha": "a" * 40,
            "source_workflow_path": (
                ".github/workflows/eu26-21-common-bridge-30-paired.yml"
            ),
            "artifacts": [
                {
                    "seed": seed,
                    "id": seed,
                    "name": (
                        f"eu26-21-common-bridge-seed-{seed}-{run_id}-{attempt}"
                    ),
                    "digest": "sha256:" + format(seed, "064x"),
                }
                for seed in range(41001, 41031)
            ],
        }
        validated = fetch_source_artifacts.validate_expected_artifact_ledger(
            ledger,
            repository="ChepaMaksym/GA-article-test",
            source_run_id=run_id,
        )
        self.assertEqual(len(validated["artifacts"]), 30)
        duplicate = copy.deepcopy(ledger)
        duplicate["artifacts"][1]["id"] = duplicate["artifacts"][0]["id"]
        with self.assertRaises(fetch_source_artifacts.ArtifactError):
            fetch_source_artifacts.validate_expected_artifact_ledger(
                duplicate,
                repository="ChepaMaksym/GA-article-test",
                source_run_id=run_id,
            )

    def test_runtime_config_rejects_declarative_drift(self) -> None:
        config_path = ROOT / "common_bridge" / "config.json"
        protocol_path = ROOT / "common_bridge" / "protocol.json"
        config = json.loads(config_path.read_text(encoding="utf-8"))
        protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
        run_seed._validate_config(config, protocol)  # noqa: SLF001
        changed = copy.deepcopy(config)
        changed["rng"]["initial_mask_stream"] = "global_numpy_rng"
        with self.assertRaises(ValueError):
            run_seed._validate_config(changed, protocol)  # noqa: SLF001


if __name__ == "__main__":
    unittest.main()
