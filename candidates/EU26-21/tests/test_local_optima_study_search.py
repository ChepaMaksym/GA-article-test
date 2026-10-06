"""Mechanical fixtures for the prospective kernel; execution belongs to CI."""
from pathlib import Path
import sys
import unittest
from unittest.mock import Mock, patch

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from local_optima_study import search  # noqa: E402


def feature_fitness(mask):
    return (sum(mask) / len(mask), -sum(mask) / len(mask)) if any(mask) else (0.0, -1.0)


class RandomTape:
    def __init__(self, strength=0, crossover_mutant=True):
        self.strength = strength
        self.crossover_mutant = crossover_mutant
        self.selection_options = []
        self.mutation_draws = 0

    def binomial(self, _dimension, _probability):
        return self.strength

    def choice(self, values, size=None, replace=True):
        if size is not None:
            self.mutation_draws += 1
            if replace:
                raise AssertionError("mutation positions must be distinct")
            return np.arange(size)
        options = tuple(int(item) for item in values)
        self.selection_options.append(options)
        return options[0]

    def random(self, count):
        return np.zeros(count) if self.crossover_mutant else np.ones(count)


class SearchTests(unittest.TestCase):
    def test_comparison_warmup_same_order_calls_and_exact_limit(self):
        masks = [(1, 0, 0, 0), (0, 1, 0, 0)] * 25
        for mode in ("adaptive", "fixed1"):
            with self.subTest(mode=mode):
                objective = Mock(side_effect=feature_fitness)
                result = search.run_lambda_search(objective, seed=42001, mode=mode, initial_masks=masks)
                self.assertEqual(objective.call_count, 400)
                self.assertEqual(result["objective_calls"], 400)
                self.assertEqual(result["initial_population_calls"], 50)
                self.assertEqual([row["mask"] for row in result["evaluations"][:50]], [list(mask) for mask in masks])
                self.assertEqual([row["call"] for row in result["evaluations"]], list(range(1, 401)))
                self.assertEqual(result["terminal"]["fitness"], list(max(tuple(row["fitness"]) for row in result["evaluations"])))
                self.assertIsNone(result["initial"])
                self.assertIsNone(result["escape"])

    def test_known_parent_q0_retained_without_reevaluation_or_false_exit(self):
        objective = Mock(side_effect=lambda mask: (0.8, -0.5) if mask == (1, 1, 0, 0) else (0.2, -0.5))
        result = search.run_lambda_search(
            objective, seed=29, budget=20, initial_parent=(1, 1, 0, 0), initial_fitness=(0.8, -0.5),
        )
        self.assertEqual(objective.call_count, 20)
        self.assertEqual(result["initial_population_calls"], 0)
        self.assertEqual(result["initial"]["call"], 0)
        self.assertEqual(result["terminal"]["call"], 0)
        self.assertEqual(result["terminal"]["mask"], [1, 1, 0, 0])
        self.assertTrue(all(row["best_so_far_weighted_balanced_accuracy"] == 0.8 for row in result["evaluations"]))
        self.assertEqual(result["normalized_auc_best_so_far_validation_wba_1_400"], 0.8)
        self.assertIsNone(result["normalized_auc_best_so_far_validation_wba_51_400"])
        self.assertEqual(result["escape"], {"first_exit_call": None, "first_accepted_exit_call": None, "censored": True, "restricted_calls": 20})

    def test_exact_fitness_tie_keeps_q0_even_when_parent_changes(self):
        with patch.object(search.np.random, "default_rng", return_value=RandomTape(strength=2)):
            result = search.run_lambda_search(
                lambda _mask: (0.8, -0.5), seed=1, budget=2, mode="fixed1",
                initial_parent=(1, 0, 1, 0), initial_fitness=(0.8, -0.5),
            )
        self.assertTrue(result["generation_trace"][0]["parent_changed"])
        self.assertEqual(result["terminal"]["call"], 0)
        self.assertIsNone(result["escape"]["first_exit_call"])

    def test_query_exit_and_acceptance_have_different_call_indices(self):
        with patch.object(search.np.random, "default_rng", return_value=RandomTape(strength=2)):
            objective = Mock(side_effect=feature_fitness)
            result = search.run_lambda_search(
                objective, seed=1, budget=4, mode="fixed1", initial_parent=(0, 0, 0, 1),
                initial_fitness=feature_fitness((0, 0, 0, 1)),
            )
        self.assertEqual(result["escape"]["first_exit_call"], 1)
        self.assertEqual(result["escape"]["first_accepted_exit_call"], 2)
        self.assertEqual(result["escape"]["restricted_calls"], 1)
        self.assertEqual(objective.call_count, 4)
        self.assertEqual(result["generation_trace"][0]["mutation_strength"], 2)
        self.assertEqual(result["generation_trace"][0]["lambda_before"], 1.0)

    def test_fewer_features_equal_wba_is_control_success_not_escape(self):
        with patch.object(search.np.random, "default_rng", return_value=RandomTape(strength=1)):
            result = search.run_lambda_search(
                lambda mask: (0.8, -sum(mask) / 4), seed=1, budget=2,
                lambda_initial=2.0, initial_parent=(1, 1, 0, 0), initial_fitness=(0.8, -0.5),
            )
        generation = result["generation_trace"][0]
        self.assertTrue(generation["strict_success"])
        self.assertAlmostEqual(generation["lambda_after"], 2 / 1.5)
        self.assertIsNone(result["escape"]["first_exit_call"])
        self.assertIsNone(result["escape"]["first_accepted_exit_call"])
        self.assertEqual(result["terminal"]["selected_feature_count"], 1)

    def test_duplicates_consume_calls_and_fixed_lambda_does_not_update(self):
        with patch.object(search.np.random, "default_rng", return_value=RandomTape(strength=0)):
            objective = Mock(return_value=(0.5, -0.25))
            result = search.run_lambda_search(
                objective, seed=1, budget=8, mode="fixed1",
                initial_parent=(0, 0, 0, 1), initial_fitness=(0.5, -0.25),
            )
        self.assertEqual(objective.call_count, 8)
        self.assertEqual(len(result["generation_trace"]), 4)
        self.assertTrue(all(row["mask"] == [0, 0, 0, 1] for row in result["evaluations"]))
        self.assertTrue(all(row["lambda_after"] == row["lambda_before"] == 1 for row in result["generation_trace"]))
        self.assertFalse(result["reset"])
        self.assertEqual(result["reset_events"], 0)

    def test_adaptive_failure_cap_does_not_reset(self):
        result = search.run_lambda_search(
            lambda _mask: (0.5, 0), seed=1, budget=8,
            initial_parent=(1, 0, 0, 0), initial_fitness=(0.5, 0), lambda_initial=4,
        )
        row = result["generation_trace"][0]
        self.assertEqual(row["mutation_probability"], 1)
        self.assertEqual(row["mutation_strength"], 4)
        self.assertEqual(row["lambda_before"], row["lambda_after"])
        self.assertFalse(row["reset_event"])

    def test_tail_count_truncation_keeps_real_lambda_probabilities(self):
        result = search.run_lambda_search(
            lambda _mask: 0, seed=1, budget=2,
            initial_parent=(0, 0, 0, 1), initial_fitness=0, lambda_initial=2.5,
        )
        row = result["generation_trace"][0]
        self.assertEqual(row["planned_offspring_count_per_phase"], 3)
        self.assertEqual(row["evaluated_offspring_count_per_phase"], 1)
        self.assertTrue(row["tail_truncated"])
        self.assertEqual(row["mutation_probability"], 0.625)
        self.assertEqual(row["crossover_probability"], 0.4)
        self.assertEqual([item["phase"] for item in result["evaluations"]], ["mutation", "crossover"])

    def test_same_chosen_mutant_used_for_both_roles_and_duplicates_remain(self):
        tape = RandomTape(strength=1, crossover_mutant=False)
        with (
            patch.object(search.np.random, "default_rng", return_value=tape),
            patch.object(search, "make_crossovers", wraps=search.make_crossovers) as crossover,
            patch.object(search, "select_from_chosen_mutant", wraps=search.select_from_chosen_mutant) as selection,
        ):
            result = search.run_lambda_search(
                feature_fitness, seed=1, budget=4, lambda_initial=2,
                initial_parent=(0, 0, 0, 1), initial_fitness=(0.25, -0.25),
            )
        self.assertEqual(selection.call_args.kwargs["selected_mutant_index"], 0)
        self.assertEqual(list(crossover.call_args.args[1]), result["generation_trace"][0]["selected_mutant_mask"])
        self.assertEqual(tape.selection_options, [(0, 1), (0,)])
        self.assertEqual(result["generation_trace"][0]["eligible_count"], 1)

    def test_nonparent_duplicates_keep_distinct_final_pool_entries(self):
        tape = RandomTape(strength=1, crossover_mutant=True)
        with patch.object(search.np.random, "default_rng", return_value=tape):
            result = search.run_lambda_search(
                feature_fitness, seed=1, budget=4, lambda_initial=2,
                initial_parent=(0, 0, 0, 1), initial_fitness=(0.25, -0.25),
            )
        self.assertEqual(result["generation_trace"][0]["eligible_count"], 3)
        self.assertEqual(tape.selection_options, [(0, 1), (0, 1, 2)])
        self.assertEqual(result["objective_calls"], 4)

    def test_deterministic_isolated_rng_with_identical_first_generation(self):
        arguments = dict(seed=42001, budget=100, initial_parent=(1, 0, 0, 0), initial_fitness=(0.25, -0.25))
        first = search.run_lambda_search(feature_fitness, **arguments)
        np.random.seed(7)
        np.random.random(5)
        second = search.run_lambda_search(feature_fitness, **arguments)
        fixed = search.run_lambda_search(feature_fitness, mode="fixed1", **arguments)
        self.assertEqual(first, second)
        self.assertEqual(first["evaluations"][:2], fixed["evaluations"][:2])
        for row in first["generation_trace"]:
            self.assertTrue(1 <= row["lambda_before"] <= 4)
            self.assertTrue(1 <= row["lambda_after"] <= 4)

    def test_empty_mask_special_fitness_is_preserved(self):
        result = search.run_lambda_search(feature_fitness, seed=1, budget=4, initial_masks=[(0, 0), (1, 0)])
        self.assertEqual(result["evaluations"][0]["fitness"], [0.0, -1.0])

    def test_invalid_static_inputs_do_not_call_objective_or_rng(self):
        invalid = [
            {"mode": "fixed2"}, {"mode": "fixed1", "lambda_initial": 2},
            {"seed": True}, {"seed": -1}, {"budget": 3}, {"budget": True},
            {"initial_parent": (1, 0.5)}, {"initial_parent": (True, 0)},
            {"initial_parent": (1,)}, {"initial_fitness": (0.5, float("nan"))},
            {"initial_fitness": True}, {"lambda_initial": float("nan")},
            {"update_factor": 1}, {"update_factor": True},
            {"initial_masks": [(1, 0)]},
        ]
        for changes in invalid:
            with self.subTest(changes=changes):
                objective = Mock(return_value=0)
                args = dict(seed=1, budget=2, initial_parent=(1, 0), initial_fitness=(0.5, -0.5))
                args.update(changes)
                with patch.object(search.np.random, "default_rng") as rng:
                    with self.assertRaises((TypeError, ValueError)):
                        search.run_lambda_search(objective, **args)
                    rng.assert_not_called()
                objective.assert_not_called()

    def test_nonfinite_objective_result_fails_instead_of_becoming_a_terminal_result(self):
        objective = Mock(return_value=(float("nan"), 0))
        with self.assertRaises(ValueError):
            search.run_lambda_search(objective, seed=1, budget=2, initial_parent=(1, 0), initial_fitness=(0.5, -0.5))
        self.assertEqual(objective.call_count, 1)

    def test_known_parent_duplicate_must_reproduce_q0(self):
        with patch.object(search.np.random, "default_rng", return_value=RandomTape(strength=0)):
            objective = Mock(return_value=(0.4, -0.5))
            with self.assertRaisesRegex(ValueError, "did not reproduce"):
                search.run_lambda_search(
                    objective, seed=1, budget=2, initial_parent=(1, 0), initial_fitness=(0.5, -0.5),
                )
        self.assertEqual(objective.call_count, 1)


if __name__ == "__main__":
    unittest.main()
