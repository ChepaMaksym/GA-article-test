"""Prospective CI-only software checks, not a knapsack scientific series.

The registration does not currently authorize running these checks.  Their
presence alone must not dispatch CI or be reported as successful execution.
"""

from copy import deepcopy
from fractions import Fraction
from itertools import product
import math
import os
import unittest
from unittest.mock import patch

from studies.adaptive_parameters.mutation_only import engine as historical
from studies.knapsack_parameters.adaptation_analysis import crossover


def _problem():
    return {"n": 4, "weights": [1, 2, 3, 4], "profits": [2, 4, 6, 8], "capacity": 4}


def _score(problem, mask):
    weight = sum(problem["weights"][i] for i, bit in enumerate(mask) if bit == "1")
    profit = sum(problem["profits"][i] for i, bit in enumerate(mask) if bit == "1")
    return {"weight": weight, "profit": profit, "feasible": weight <= problem["capacity"]}


def _bank(problem):
    masks = ["0000", "1000", "0100", "0010", "0001", "1100"] * 5
    return masks, [_score(problem, mask) for mask in masks]


def _log(method="adaptive_crossover", budget=61, seed=18001):
    problem = _problem()
    masks, scores = _bank(problem)
    return crossover.run_search(problem, masks, scores, method,
                                historical.make_rngs(seed, 0, 0), budget=budget)


class CrossoverTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if os.environ.get("GITHUB_ACTIONS") != "true":
            raise RuntimeError("Registered software checks run only in GitHub Actions")

    def test_novelty_formula_against_complete_small_crossover_enumeration(self):
        for n in range(2, 7):
            for d in range(n + 1):
                first, second = "0" * n, "1" * d + "0" * (n - d)
                novel = 0
                for choices in product((0, 1), repeat=n):
                    child = "".join(first[i] if choices[i] else second[i] for i in range(n))
                    novel += int(child not in (first, second))
                expected = Fraction(novel, 2 ** n)
                with self.subTest(n=n, d=d):
                    self.assertAlmostEqual(crossover.novelty_probability(d, n), float(expected),
                                           delta=1e-12)

    def test_identical_and_one_bit_different_parents_have_no_crossover_novelty(self):
        self.assertEqual(crossover.novelty_probability(0, 100), 0.0)
        self.assertEqual(crossover.novelty_probability(1, 100), 0.0)
        self.assertEqual(crossover.novelty_probability(2, 100), 0.5)

    def test_controller_uses_mean_of_pair_probabilities_not_mean_distance(self):
        probability, signal, event = crossover.update_crossover(4, 0.9, [0, 2])
        self.assertEqual(signal, 0.25)
        self.assertAlmostEqual(probability, 0.3, delta=1e-12)
        self.assertNotEqual(probability, 0.1 + 0.8 * crossover.novelty_probability(1, 4))
        self.assertEqual(event, "DIVERSITY_FEEDBACK")

    def test_complete_update_bounds_and_large_distance_float_limit(self):
        low, _, _ = crossover.update_crossover(100, 0.9, [0] * 29)
        high, _, _ = crossover.update_crossover(100, 0.1, [100] * 29)
        self.assertEqual(low, 0.1)
        self.assertEqual(high, 0.9)
        self.assertEqual(crossover.novelty_probability(1076, 1076), 1.0)

    def test_partial_and_empty_pair_helpers_hold_parameter(self):
        probability, signal, event = crossover.update_crossover(4, 0.7, [0, 2], complete=False)
        self.assertEqual((probability, signal, event), (0.7, 0.25, "PARTIAL_NO_UPDATE"))
        self.assertEqual(crossover.update_crossover(4, 0.7, []), (0.7, None, "NO_PAIRS"))
        self.assertEqual(crossover.update_crossover(4, 0.7, [], complete=False),
                         (0.7, None, "PARTIAL_NO_UPDATE"))

    def test_fixed_helper_does_not_use_signal_to_change_crossover(self):
        for distances in ([0] * 29, [2] * 29, [4] * 29):
            probability, signal, event = crossover.update_crossover(
                4, 0.9, distances, method="fixed_crossover"
            )
            self.assertEqual(probability, 0.9)
            self.assertIsNotNone(signal)
            self.assertEqual(event, "FIXED")

    def test_invalid_novelty_and_controller_states_rejected(self):
        for d, n in ((True, 4), (-1, 4), (5, 4), (0, True), (0, 1), (0.5, 4)):
            with self.subTest(d=d, n=n), self.assertRaises(ValueError):
                crossover.novelty_probability(d, n)
        for probability in (True, float("nan"), float("inf"), 0.0, 1.0):
            with self.subTest(probability=probability), self.assertRaises(ValueError):
                crossover.update_crossover(4, probability, [0])
        for kwargs in ({"complete": 1}, {"method": "unknown"}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                crossover.update_crossover(4, 0.9, [0], **kwargs)
        with self.assertRaises(ValueError):
            crossover.update_crossover(4, 0.9, [True])
        with self.assertRaises(ValueError):
            crossover.update_crossover(4, 0.9, "0,2")

    def test_first_generation_identical_between_own_profiles(self):
        fixed, adaptive = _log("fixed_crossover"), _log("adaptive_crossover")
        self.assertEqual(fixed["rng_initial"], adaptive["rng_initial"])
        self.assertEqual(fixed["candidates"][:29], adaptive["candidates"][:29])
        for field in ("population_before", "population_after", "rng_before", "rng_after",
                      "parent_distances", "mean_novelty", "p_c", "p_m"):
            self.assertEqual(fixed["generations"][0][field], adaptive["generations"][0][field])

    def test_fixed_crossover_matches_unchanged_historical_fixed_core(self):
        problem = _problem()
        masks, scores = _bank(problem)
        old = historical.run_search(problem, masks, scores, "fixed",
                                    historical.make_rngs(18001, 0, 0), budget=61)
        new = _log("fixed_crossover")
        stripped = [{key: value for key, value in row.items() if key != "parent_distance"}
                    for row in new["candidates"]]
        self.assertEqual(stripped, old["candidates"])
        self.assertEqual(new["rng_final"], old["rng_final"])
        for key, value in old["summary"].items():
            self.assertEqual(new["summary"][key], value)

    def test_every_selected_pair_including_non_crossover_branch_contributes(self):
        problem = _problem()
        masks, scores = _bank(problem)
        rngs = historical.make_rngs(18002, 0, 0)
        explicit_branch_state = None
        # A bounded search for a SOFTWARE input state exercises the no-crossover
        # branch.  It is neither a scientific seed selection nor an experiment.
        for _ in range(128):
            state = deepcopy(rngs["branch"].bit_generator.state)
            if rngs["branch"].random() >= 0.9:
                explicit_branch_state = state
                break
        self.assertIsNotNone(explicit_branch_state)
        rngs["branch"].bit_generator.state = explicit_branch_state
        log = crossover.run_search(problem, masks, scores, "adaptive_crossover", rngs, budget=29)
        generation = log["generations"][0]
        self.assertFalse(log["candidates"][0]["crossover"])
        self.assertEqual(generation["parent_distances"],
                         [row["parent_distance"] for row in log["candidates"]])
        self.assertEqual(len(generation["parent_distances"]), 29)
        exact = sum((Fraction(0) if d == 0 else 1 - Fraction(2) ** (1 - d)
                     for d in generation["parent_distances"]), Fraction()) / 29
        self.assertAlmostEqual(generation["mean_novelty"], float(exact), delta=1e-12)
        self.assertAlmostEqual(generation["p_c_next"], float(Fraction(1, 10) + Fraction(4, 5) * exact),
                               delta=1e-12)

    def test_terminal_prefix_records_signal_without_population_or_parameter_update(self):
        log = _log(budget=12)
        generation = log["generations"][0]
        self.assertFalse(generation["complete"])
        self.assertEqual(generation["population_before"], generation["population_after"])
        self.assertEqual(generation["p_c_next"], generation["p_c"])
        self.assertEqual(generation["controller_event"], "PARTIAL_NO_UPDATE")
        self.assertEqual(len(generation["parent_distances"]), 12)
        self.assertTrue(math.isfinite(generation["mean_novelty"]))
        self.assertEqual(log["summary"]["new_calls"], 12)
        self.assertEqual(log["summary"]["partial_children"], 12)

    def test_duplicates_and_infeasible_queries_are_not_skipped(self):
        problem = {"n": 2, "weights": [1, 1], "profits": [1, 1], "capacity": 0}
        masks = ["00"] * 30
        scores = [_score(problem, mask) for mask in masks]
        log = crossover.run_search(problem, masks, scores, "adaptive_crossover",
                                   historical.make_rngs(18003, 0, 0), budget=61)
        self.assertEqual(log["summary"]["new_calls"], 61)
        self.assertEqual(log["summary"]["physical_evaluations"], 61)
        self.assertEqual(log["summary"]["known_score_validation_evaluations"], 30)
        self.assertGreaterEqual(log["summary"]["duplicate_calls"], 57)
        self.assertGreater(log["summary"]["infeasible_calls"], 0)
        self.assertEqual(log["summary"]["best_profit"], 0)
        self.assertEqual(log["summary"]["final_mutation_probability"], 0.5)

    def test_core_is_deterministic_and_leaves_initialization_stream_unused(self):
        first, second = _log(), _log()
        self.assertEqual(first, second)
        self.assertEqual(first["rng_initial"]["initialization"],
                         first["rng_final"]["initialization"])
        self.assertEqual(first["summary"]["full_generations"], 2)
        self.assertEqual(first["summary"]["partial_children"], 3)
        self.assertTrue(all(row["p_m"] == 0.25 for row in first["generations"]))
        self.assertTrue(all(0.1 <= row["p_c"] <= 0.9 for row in first["generations"]))

    def test_known_inputs_are_not_mutated_or_retained_by_reference(self):
        problem = _problem()
        masks, scores = _bank(problem)
        before = deepcopy((problem, masks, scores))
        log = crossover.run_search(problem, masks, scores, "adaptive_crossover",
                                   historical.make_rngs(18004, 0, 0), budget=3)
        self.assertEqual((problem, masks, scores), before)
        masks[0] = "1111"
        scores[0]["profit"] = 999
        problem["profits"][0] = 999
        self.assertEqual(log["initial_masks"][0], "0000")
        self.assertEqual(log["initial_scores"][0]["profit"], 0)
        self.assertEqual(log["problem"]["profits"][0], 2)

    def test_no_oracle_fields_all_infeasible_starts_and_corrupt_known_scores_rejected(self):
        problem = _problem()
        masks, scores = _bank(problem)
        for field in ("optimum", "optimal_mask", "certificate"):
            with self.subTest(field=field), self.assertRaises(ValueError):
                crossover.run_search({**problem, field: 1}, masks, scores, "adaptive_crossover",
                                     historical.make_rngs(18005, 0, 0), budget=1)
        with self.assertRaises(ValueError):
            crossover.run_search(problem, ["1111"] * 30,
                                 [_score(problem, "1111") for _ in range(30)],
                                 "adaptive_crossover", historical.make_rngs(18005, 0, 0), budget=1)
        corrupted = deepcopy(scores)
        corrupted[0]["profit"] = True
        with self.assertRaises(ValueError):
            crossover.run_search(problem, masks, corrupted, "adaptive_crossover",
                                 historical.make_rngs(18005, 0, 0), budget=1)

    def test_rejects_rng_aliases_unknown_methods_invalid_budget_and_wrong_ci_scope(self):
        problem = _problem()
        masks, scores = _bank(problem)
        rngs = historical.make_rngs(18006, 0, 0)
        rngs["mutation"] = rngs["selection"]
        with self.assertRaises(ValueError):
            crossover.run_search(problem, masks, scores, "adaptive_crossover", rngs, budget=1)
        for method, budget in (("unknown", 1), ("adaptive_crossover", True),
                               ("adaptive_crossover", 0)):
            with self.subTest(method=method, budget=budget), self.assertRaises(ValueError):
                crossover.run_search(problem, masks, scores, method,
                                     historical.make_rngs(18006, 0, 0), budget=budget)
        with patch.dict(os.environ, {"GITHUB_REPOSITORY": "other/repository"}):
            with self.assertRaises(ValueError):
                crossover.run_search(problem, masks, scores, "adaptive_crossover",
                                     historical.make_rngs(18006, 0, 0), budget=1)

    def test_last_evaluated_candidate_can_improve_record_without_committing_state(self):
        problem = {"n": 4, "weights": [1] * 4, "profits": [1, 2, 3, 4], "capacity": 4}
        masks = ["0000"] * 30
        scores = [_score(problem, mask) for mask in masks]
        rngs = historical.make_rngs(18007, 0, 0)
        explicit_mutation_state = None
        for _ in range(64):
            state = deepcopy(rngs["mutation"].bit_generator.state)
            if any(rngs["mutation"].random(4) < 0.25):
                explicit_mutation_state = state
                break
        self.assertIsNotNone(explicit_mutation_state)
        rngs["mutation"].bit_generator.state = explicit_mutation_state
        log = crossover.run_search(problem, masks, scores, "adaptive_crossover", rngs, budget=1)
        self.assertGreater(log["summary"]["best_profit"], 0)
        self.assertEqual(log["summary"]["best_call"], 1)
        self.assertEqual(log["summary"]["final_population"], list(range(30)))
        self.assertEqual(log["summary"]["final_crossover_probability"], 0.9)
        self.assertEqual(log["generations"][0]["mean_novelty"], 0.0)


if __name__ == "__main__":
    unittest.main()
