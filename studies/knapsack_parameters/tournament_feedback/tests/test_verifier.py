"""Independent CI fixtures for operators, replay and damaged evidence.

These tests use small artificial problems. They do not select scientific
seeds, alter the registered controller, or produce experimental results.
"""
from __future__ import annotations

import copy
from fractions import Fraction
import inspect
from itertools import product
import os
import unittest
from unittest.mock import patch

from studies.knapsack_parameters.tournament_feedback import engine, verifier
from studies.knapsack_parameters.tournament_feedback.tests.test_engine import journal, problem


class FixedIndex:
    def __init__(self, index):
        self.index = index
        self.calls = 0

    def integers(self, limit):
        if not 0 <= self.index < limit:
            raise AssertionError("Fixture index outside the random-choice domain")
        self.calls += 1
        return self.index


class TournamentFeedbackVerifierTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if os.environ.get("GITHUB_ACTIONS") != "true":
            raise RuntimeError("These instructional checks may execute only in GitHub Actions")

    def test_all_registered_profiles_have_independent_replay(self):
        for profile in engine.PROFILES:
            log = journal(profile, schedule=[2, 5, 3] if profile == "replay" else None)
            result = verifier.verify(log)
            self.assertEqual(result["verification_status"], "VERIFIED")
            self.assertEqual(result["independent_score_checks"], 30 + 2 * 61)
            self.assertEqual(result["final_score_checks"], 61)
            self.assertEqual(result["premutation_score_checks"], 61)
            self.assertEqual(result["completed_generations"], 2)
            self.assertEqual(result["partial_generations"], 1)

    def test_verifier_remains_independent_when_production_helpers_fail(self):
        log = journal()
        with patch.object(engine, "_evaluate", side_effect=AssertionError("Production evaluator used")), \
                patch.object(engine, "_pick", side_effect=AssertionError("Production selector used")), \
                patch.object(engine, "update_parameters", side_effect=AssertionError("Production policy used")), \
                patch.object(engine, "novelty_statistics", side_effect=AssertionError("Production metric used")):
            self.assertEqual(verifier.verify(log)["verification_status"], "VERIFIED")
        imports = inspect.getsource(verifier)
        self.assertNotIn("import engine", imports)
        self.assertNotIn("from .engine", imports)

    def test_single_winner_does_not_consume_tie_randomness(self):
        chooser = FixedIndex(0)
        self.assertEqual(engine._pick([17], chooser), 17)
        self.assertEqual(chooser.calls, 0)
        self.assertEqual(verifier._choose([17], chooser), 17)
        self.assertEqual(chooser.calls, 0)

    def test_repeated_winning_occurrences_are_preserved_in_tie_choice(self):
        # An individual sampled twice has two winning occurrences, not one.
        for function in (engine._pick, verifier._choose):
            selected = [function([0, 2, 2], FixedIndex(index)) for index in range(3)]
            self.assertEqual(selected, [0, 2, 2])

    def test_feasibility_order_and_equal_overweight(self):
        for function in (engine._key, verifier._key):
            self.assertGreater(function({"profit": 0, "weight": 0, "feasible": True}, 10),
                               function({"profit": 1000, "weight": 11, "feasible": False}, 10))
            self.assertGreater(function({"profit": 1, "weight": 11, "feasible": False}, 10),
                               function({"profit": 1000, "weight": 12, "feasible": False}, 10))
            self.assertEqual(function({"profit": 1, "weight": 11, "feasible": False}, 10),
                             function({"profit": 1000, "weight": 11, "feasible": False}, 10))

    def test_uniform_crossover_novelty_matches_complete_small_enumeration(self):
        for distance in range(9):
            first, second = "0" * distance, "1" * distance
            children = ["".join(bits) for bits in product("01", repeat=distance)]
            novel = sum(child != first and child != second for child in children)
            self.assertEqual(engine.novelty_probability(distance), Fraction(novel, len(children)))

    def test_best_group_presence_formula_uses_sampling_with_replacement(self):
        # One of three positions belongs to the best group. Repetitions are
        # legal, so the exact domain has 3**k ordered tournament samples.
        for size in range(2, 6):
            samples = list(product(range(3), repeat=size))
            count = sum(0 in entries for entries in samples)
            self.assertEqual(Fraction(count, len(samples)), 1 - Fraction(2, 3) ** size)

    def test_population_diversity_has_independent_known_denominators(self):
        masks = ["00", "01", "10", "11"]
        p = problem(2, capacity=1)
        scores = [verifier._score(p, mask) for mask in masks]
        metrics = verifier._population_point(29, True, [0, 1, 2, 3], masks, scores, "10", 2)
        self.assertEqual(metrics["unique_fraction"], 1)
        self.assertEqual(metrics["mean_pairwise_hamming"], 4 / 3)
        self.assertEqual(metrics["feasible_fraction"], 3 / 4)
        self.assertEqual(metrics["mean_feasible_profit"], 1)
        self.assertTrue(metrics["record_in_population"])
        clones = verifier._population_point(0, True, [0, 0, 0, 0], masks, scores, "10", 2)
        self.assertEqual(clones["unique_fraction"], 1 / 4)
        self.assertEqual(clones["mean_pairwise_hamming"], 0)
        self.assertFalse(clones["record_in_population"])

    def test_final_prefix_metrics_describe_last_committed_population(self):
        log = journal(budget=61)
        result = verifier.verify(log)
        points = result["derived_metrics"]["population_trace"]
        final, previous = points[-1], points[-2]
        self.assertFalse(final["complete"])
        self.assertEqual(final["q"], 61)
        for field in ("population_size", "unique_masks", "unique_fraction", "mean_pairwise_hamming",
                      "feasible_fraction", "mean_feasible_profit"):
            self.assertEqual(final[field], previous[field])

    def test_corrupted_operator_controller_population_and_rng_are_rejected(self):
        source = journal()
        mutations = [
            lambda value: value["candidates"][0].__setitem__("mask", "1" * value["problem"]["n"]),
            lambda value: value["candidates"][0].__setitem__("mutation_bits", [0, 0]),
            lambda value: value["candidates"][0].__setitem__("parent_distance", 999),
            lambda value: value["candidates"][0].__setitem__("profit", -1),
            lambda value: value["candidates"][0]["tournaments"][0].append(0),
            lambda value: value["generations"][0]["parameters_after"].__setitem__("p_m", .02),
            lambda value: value["generations"][0].__setitem__("controller_event", "STAGNATION"),
            lambda value: value["generations"][0]["population_after"].reverse(),
            lambda value: value["generations"][-1].__setitem__("complete", True),
            lambda value: value["rng_final"]["mutation"]["state"].__setitem__("state", 0),
            lambda value: value["summary"].__setitem__("new_calls", 60),
            lambda value: value["initial_scores"][0].__setitem__("feasible", False),
            lambda value: value["problem"].__setitem__("optimum", 55),
            lambda value: value.__setitem__("schema", "different-study"),
            lambda value: value["candidates"].pop(),
            lambda value: value["generations"].pop(),
            lambda value: value["timing_ns"].__setitem__("total", 0),
        ]
        for number, mutation in enumerate(mutations):
            with self.subTest(corruption=number):
                damaged = copy.deepcopy(source)
                mutation(damaged)
                with self.assertRaises(ValueError):
                    verifier.verify(damaged)

    def test_schedule_corruption_is_not_silently_ignored(self):
        source = journal("replay", schedule=[2, 5, 3])
        for schedule in ([2, 5], [2, 4, 3], [2, 5, 6], [2, True, 3], [3, 5, 3]):
            damaged = copy.deepcopy(source)
            damaged["schedule"] = schedule
            with self.assertRaises(ValueError):
                verifier.verify(damaged)

    def test_donor_extraction_carries_no_fitness_or_candidate_state(self):
        log = journal("adaptive", budget=61)
        extracted = engine.extract_schedule(log)
        self.assertIsInstance(extracted, list)
        self.assertEqual(len(extracted), 3)
        self.assertTrue(all(type(value) is int and 2 <= value <= 5 for value in extracted))
        with self.assertRaises(ValueError):
            engine.extract_schedule(journal("k2"))
        log["generations"].pop()
        with self.assertRaises(ValueError):
            engine.extract_schedule(log)


if __name__ == "__main__":
    unittest.main()
