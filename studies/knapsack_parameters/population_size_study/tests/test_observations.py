"""CI-only checks of total-evaluation checkpoints and population observations."""
from __future__ import annotations

from copy import deepcopy
import os
import unittest
from unittest.mock import patch

from studies.knapsack_parameters.population_size_study.observations import extract, population_metrics


def score(mask):
    profit = sum(index + 1 for index, bit in enumerate(mask) if bit == "1")
    return {"weight": mask.count("1"), "profit": profit, "feasible": True}


def fixture():
    """A readable observation fixture, independent of the producer loop."""
    initial = ["0000", "1000", "0100", "0000"]
    settings = {"p_m": .25, "p_c": .9, "target_mu": 4, "tournament_size": 2, "elite_count": 1}
    candidates = [{"mask": mask, **score(mask)} for mask in ("0010", "0001", "1100", "0110", "1111")]
    population = [1, 4, 5, 6]
    return {
        "schema": "ga-knapsack-configured-fixed-log-v1", "problem": {"n": 4},
        "initial_population_size": 4, "initial_masks": initial,
        "initial_scores": [score(mask) for mask in initial], "initial_parameters": settings,
        "budget": 5, "candidates": candidates,
        "generations": [
            {"generation": 1, "start_call": 1, "end_call": 3, "complete": True,
             "population_after": population, "parameters_after": deepcopy(settings),
             "failed_queries_after": 0, "requested_offspring": 3, "actual_parent_mu": 4},
            {"generation": 2, "start_call": 4, "end_call": 5, "complete": False,
             "population_after": population, "parameters_after": deepcopy(settings),
             "failed_queries_after": 0, "requested_offspring": 3, "actual_parent_mu": 4}],
        "summary": {"partial_children": 2}}


@unittest.skipUnless(os.environ.get("GITHUB_ACTIONS") == "true", "Scientific checks run only in GitHub Actions")
class ObservationTests(unittest.TestCase):
    def test_initialization_prefix_has_a_record_but_no_completed_population(self):
        result = extract(fixture(), 9, 10, checkpoints=(0, 1, 2, 3, 4))
        zero, first, second, third, initial = result["checkpoints"]
        self.assertIsNone(zero["record_profit"])
        self.assertIsNone(zero["completed_population"])
        self.assertEqual(first["record_profit"], 0)
        self.assertEqual(second["record_profit"], 1)
        self.assertEqual(third["record_profit"], 2)
        self.assertEqual(third["phase"], "initializing")
        self.assertEqual(third["partial_initial_references"], [0, 1, 2])
        self.assertEqual(initial["completed_population"], [0, 1, 2, 3])
        self.assertEqual(initial["population_total_q"], 4)
        self.assertEqual(initial["offspring_evaluations"], 0)

    def test_partial_generation_keeps_prior_population_and_new_record(self):
        result = extract(fixture(), 9, 10, checkpoints=(5, 7, 8, 9))
        first, complete, partial, last = result["checkpoints"]
        self.assertEqual(first["completed_population"], [0, 1, 2, 3])
        self.assertEqual(first["partial_offspring_references"], [4])
        self.assertEqual(complete["completed_population"], [1, 4, 5, 6])
        self.assertEqual(complete["partial_offspring_count"], 0)
        self.assertEqual(partial["partial_offspring_references"], [7])
        self.assertEqual(last["partial_offspring_references"], [7, 8])
        self.assertEqual(last["record_profit"], 10)
        self.assertEqual(last["record_total_q"], 9)
        self.assertEqual(last["population_total_q"], 7)
        self.assertEqual(last["completed_population"], complete["completed_population"])
        self.assertEqual(result["completed_generations"], 1)
        self.assertEqual(result["terminal_partial_offspring"], 2)
        self.assertEqual([row["q"] for row in result["population_trace"]], [4, 7])

    def test_target_on_last_total_evaluation_is_retained(self):
        result = extract(fixture(), 9, 10, checkpoints=(9,))
        self.assertEqual(result["final_gap_percent"], 0)
        for threshold in ("93", "95", "99"):
            self.assertEqual(result["targets"][threshold],
                             {"first_total_evaluation": 9, "attained": True, "restricted_evaluations": 9})
        self.assertEqual(result["initial_evaluations"] + result["new_evaluations"], 9)
        self.assertEqual(result["search_evaluations_performed"], 0)

    def test_initial_target_and_exact_boundary_are_counted(self):
        log = fixture()
        log["initial_masks"][0] = "1111"
        log["initial_scores"][0] = score("1111")
        result = extract(log, 9, 10, checkpoints=(1, 9))
        self.assertTrue(all(value["first_total_evaluation"] == 1 for value in result["targets"].values()))
        result = extract(fixture(), 9, 20, checkpoints=(9,))
        self.assertTrue(all(value == {"first_total_evaluation": None, "attained": False,
                                     "restricted_evaluations": 9} for value in result["targets"].values()))

    def test_pairwise_hamming_formula_matches_explicit_pairs(self):
        masks = ["0000", "1010", "1010", "1111"]
        scores = [score(mask) for mask in masks]
        scores[3]["feasible"] = False
        references = [0, 1, 2, 3]
        result = population_metrics(references, masks, scores, 4)
        explicit = sum(sum(a != b for a, b in zip(masks[i], masks[j], strict=True))
                       for i in range(len(masks)) for j in range(i + 1, len(masks)))
        self.assertEqual(result["pairwise_hamming_sum"], explicit)
        self.assertEqual(result["mean_pairwise_hamming"], explicit / 6)
        self.assertEqual(result["unique_fraction"], .75)
        self.assertEqual(result["feasible_fraction"], .75)
        self.assertEqual(result["mean_feasible_profit"], 8 / 3)
        identical = population_metrics([1, 1], masks, scores, 4)
        self.assertEqual(identical["mean_pairwise_hamming"], 0)
        self.assertEqual(identical["unique_fraction"], .5)

    def test_no_feasible_population_returns_missing_mean(self):
        masks = ["10", "01"]
        scores = [{"profit": 1, "feasible": False}, {"profit": 2, "feasible": False}]
        result = population_metrics([0, 1], masks, scores, 2)
        self.assertEqual(result["feasible_fraction"], 0)
        self.assertIsNone(result["mean_feasible_profit"])

    def test_input_is_not_mutated_and_invalid_totals_are_rejected(self):
        log = fixture()
        saved = deepcopy(log)
        extract(log, 9, 10, checkpoints=(9,))
        self.assertEqual(log, saved)
        for checkpoints in ((10,), (-1,), (1, 1), (True,)):
            with self.subTest(checkpoints=checkpoints), self.assertRaises(ValueError):
                extract(log, 9, 10, checkpoints=checkpoints)
        for total, optimum in ((8, 10), (9, 0), (9, 9)):
            with self.subTest(total=total, optimum=optimum), self.assertRaises(ValueError):
                extract(log, total, optimum, checkpoints=(1,))

    def test_observations_refuse_execution_outside_ci(self):
        with patch.dict(os.environ, {"GITHUB_ACTIONS": "false"}):
            with self.assertRaises(ValueError):
                extract(fixture(), 9, 10, checkpoints=(9,))
            with self.assertRaises(ValueError):
                population_metrics([0, 1], ["00", "11"], [score("00"), score("11")], 2)


if __name__ == "__main__":
    unittest.main()
