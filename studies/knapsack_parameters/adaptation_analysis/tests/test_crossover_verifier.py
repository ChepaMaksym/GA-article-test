"""Prospective CI fixtures for independent crossover replay; not run locally.

These tiny examples are software checks, not KPLIB experiments or evidence
that the user-approved crossover heuristic improves solution quality.
"""
from copy import deepcopy
from fractions import Fraction
import inspect
import math
import os
import unittest
from unittest.mock import patch

from studies.adaptive_parameters.mutation_only import engine as historical_engine
from studies.knapsack_parameters.adaptation_analysis import crossover
from studies.knapsack_parameters.adaptation_analysis import crossover_verifier as v


def _score(problem, mask):
    selected = [index for index, bit in enumerate(mask) if bit == "1"]
    weight = sum(problem["weights"][index] for index in selected)
    profit = sum(problem["profits"][index] for index in selected)
    return {"weight": weight, "profit": profit, "feasible": weight <= problem["capacity"]}


def _fixture(method="adaptive_crossover", budget=61, seed=27001):
    problem = {"n": 4, "weights": [1, 1, 1, 1], "profits": [1, 2, 3, 4], "capacity": 2}
    masks = ["0000", "1000", "0100", "0010", "0001", "1100"] * 5
    scores = [_score(problem, mask) for mask in masks]
    return crossover.run_search(problem, masks, scores, method,
                                historical_engine.make_rngs(seed, 0, 0), budget=budget)


class CrossoverVerifierTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if os.environ.get("GITHUB_ACTIONS") != "true":
            raise RuntimeError("Registered software checks are CI-only")

    def test_both_profiles_independently_reconstructed(self):
        for method in ("fixed_crossover", "adaptive_crossover"):
            with self.subTest(method=method):
                log = _fixture(method)
                receipt = v.verify_log(log)
                self.assertEqual(receipt["verification_status"], "VERIFIED")
                self.assertEqual(receipt["new_calls"], 61)
                self.assertEqual(receipt["independent_score_checks"], 91)
                self.assertEqual(receipt["completed_generations"], 2)
                self.assertEqual(receipt["partial_generations"], 1)
                self.assertEqual(receipt["summary"], log["summary"])

    def test_fraction_reference_is_mean_of_novelties_not_novelty_of_mean(self):
        self.assertEqual(v._reference_mean([0], 4), Fraction(0))
        self.assertEqual(v._reference_mean([1], 4), Fraction(0))
        self.assertEqual(v._reference_mean([2], 4), Fraction(1, 2))
        self.assertEqual(v._reference_mean([3], 4), Fraction(3, 4))
        self.assertEqual(v._reference_mean([0, 2], 4), Fraction(1, 4))
        self.assertIsNone(v._reference_mean([], 4))
        self.assertLess(v._reference_mean([100], 100), Fraction(1))
        for distances in ([True], [-1], [5], [2.0]):
            with self.assertRaises(ValueError):
                v._reference_mean(distances, 4)

    def test_first_generation_identical_before_feedback(self):
        fixed, adaptive = [_fixture(method) for method in ("fixed_crossover", "adaptive_crossover")]
        self.assertEqual(fixed["rng_initial"], adaptive["rng_initial"])
        self.assertEqual(fixed["candidates"][:29], adaptive["candidates"][:29])
        self.assertEqual(fixed["generations"][0]["rng_after"],
                         adaptive["generations"][0]["rng_after"])
        self.assertEqual(fixed["generations"][0]["p_c"], 0.9)
        self.assertEqual(adaptive["generations"][0]["p_c"], 0.9)

    def test_new_fixed_kernel_matches_untouched_classical_kernel(self):
        new = _fixture("fixed_crossover")
        old = historical_engine.run_search(new["problem"], new["initial_masks"],
            new["initial_scores"], "fixed", historical_engine.make_rngs(27001, 0, 0), budget=61)
        stripped = [{key: value for key, value in row.items() if key != "parent_distance"}
                    for row in new["candidates"]]
        self.assertEqual(stripped, old["candidates"])
        self.assertEqual(new["rng_final"], old["rng_final"])
        self.assertEqual({key: value for key, value in new["summary"].items()
                          if key != "final_crossover_probability"}, old["summary"])
        self.assertEqual(v.verify_log(new)["final_p_c"], 0.9)

    def test_cloned_parents_produce_lower_crossover_after_full_generation(self):
        problem = {"n": 4, "weights": [1] * 4, "profits": [1] * 4, "capacity": 4}
        masks = ["0000"] * 30
        log = crossover.run_search(problem, masks, [_score(problem, mask) for mask in masks],
            "adaptive_crossover", historical_engine.make_rngs(27002, 0, 0), budget=29)
        v.verify_log(log)
        generation = log["generations"][0]
        self.assertEqual(generation["parent_distances"], [0] * 29)
        self.assertEqual(generation["mean_novelty"], 0.0)
        self.assertEqual(generation["p_c_next"], 0.1)
        self.assertEqual(generation["controller_event"], "DIVERSITY_FEEDBACK")

    def test_partial_generation_records_signal_without_committing_controller(self):
        log = _fixture(budget=12)
        v.verify_log(log)
        event = log["generations"][0]
        self.assertFalse(event["complete"])
        self.assertEqual(len(event["parent_distances"]), 12)
        self.assertEqual(event["population_before"], event["population_after"])
        self.assertEqual(event["p_c"], event["p_c_next"])
        self.assertEqual(event["controller_event"], "PARTIAL_NO_UPDATE")

    def test_5000_query_negative_control_and_last_prefix_accounting(self):
        problem = {"n": 2, "weights": [1, 1], "profits": [1, 1], "capacity": 0}
        masks = ["00"] * 30
        log = crossover.run_search(problem, masks, [_score(problem, mask) for mask in masks],
            "adaptive_crossover", historical_engine.make_rngs(27003, 0, 0), budget=5000)
        receipt = v.verify_log(log)
        self.assertEqual(receipt["new_calls"], 5000)
        self.assertEqual(receipt["independent_score_checks"], 5030)
        self.assertEqual(log["summary"]["full_generations"], 172)
        self.assertEqual(log["summary"]["partial_children"], 12)
        self.assertEqual(log["summary"]["best_profit"], 0)
        self.assertEqual(log["summary"]["best_call"], 0)
        self.assertGreater(log["summary"]["duplicate_calls"], 0)
        self.assertGreater(log["summary"]["infeasible_calls"], 0)

    def test_distance_array_and_candidate_distance_corruptions_rejected(self):
        pristine = _fixture()
        for location in ("candidate", "generation", "boolean"):
            bad = deepcopy(pristine)
            if location == "generation":
                bad["generations"][0]["parent_distances"][0] = 5
            elif location == "boolean":
                bad["candidates"][0]["parent_distance"] = True
            else:
                bad["candidates"][0]["parent_distance"] += 1
            with self.subTest(location=location), self.assertRaises(ValueError):
                v.verify_log(bad)

    def test_signal_and_applied_or_next_parameter_corruptions_rejected(self):
        pristine = _fixture()
        for field in ("mean_novelty", "p_c", "p_c_next", "p_m"):
            bad = deepcopy(pristine)
            bad["generations"][0][field] += 0.123
            with self.subTest(field=field), self.assertRaises(ValueError):
                v.verify_log(bad)
        bad = deepcopy(pristine)
        bad["generations"][0]["mean_novelty"] = math.nan
        with self.assertRaises(ValueError):
            v.verify_log(bad)

    def test_failed_candidate_still_independently_scored(self):
        log = _fixture(budget=100)
        failures = [row for row in log["candidates"]
                    if not row["feasible"] or row["record_call"] != row["call"]]
        self.assertTrue(failures)
        row = failures[0]
        log["candidates"][row["call"] - 1]["weight"] += 1
        with self.assertRaises(ValueError):
            v.verify_log(log)

    def test_uncrossed_pairs_are_not_omitted_from_signal(self):
        log = _fixture(budget=100)
        uncrossed = [row for row in log["candidates"] if not row["crossover"]]
        self.assertTrue(uncrossed)
        child = uncrossed[0]
        event = log["generations"][child["generation"] - 1]
        event["parent_distances"].pop(child["call"] - event["start_call"])
        with self.assertRaises(ValueError):
            v.verify_log(log)

    def test_mutation_bits_branch_rng_and_population_corruptions_rejected(self):
        pristine = _fixture()
        mutations = [
            lambda log: log["candidates"][0].update({"mutation_bits": [99]}),
            lambda log: log["candidates"][0].update({"crossover": not log["candidates"][0]["crossover"]}),
            lambda log: log["generations"][0]["population_after"].__setitem__(0, 999),
            lambda log: log["rng_final"]["branch"]["state"].update({"state": 0}),
        ]
        for index, corrupt in enumerate(mutations):
            bad = deepcopy(pristine)
            corrupt(bad)
            with self.subTest(corruption=index), self.assertRaises(ValueError):
                v.verify_log(bad)

    def test_prefix_controller_or_population_commit_is_rejected(self):
        pristine = _fixture(budget=12)
        for field, value in (("p_c_next", 0.5), ("population_after", list(range(30, 60))),
                             ("controller_event", "DIVERSITY_FEEDBACK")):
            bad = deepcopy(pristine)
            bad["generations"][0][field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                v.verify_log(bad)

    def test_carry_fixed_and_partial_parameters_cannot_drift_even_one_ulp(self):
        fixed = _fixture("fixed_crossover")
        fixed["generations"][0]["p_c_next"] = math.nextafter(0.9, 0.0)
        partial = _fixture(budget=12)
        partial["generations"][0]["p_c_next"] = math.nextafter(0.9, 0.0)
        carried = _fixture()
        carried["generations"][1]["p_c"] = math.nextafter(
            carried["generations"][1]["p_c"], 0.0)
        for index, log in enumerate((fixed, partial, carried)):
            with self.subTest(corruption=index), self.assertRaises(ValueError):
                v.verify_log(log)

    def test_missing_records_extra_fields_and_oracle_metadata_rejected(self):
        pristine = _fixture()
        mutations = [
            lambda log: log["candidates"].pop(),
            lambda log: log["generations"].pop(),
            lambda log: log.update({"optimum": 7}),
            lambda log: log["problem"].update({"optimal_mask": "0011"}),
            lambda log: log["candidates"][0].update({"fitness_oracle": 7}),
            lambda log: log["summary"].update({"final_mutation_probability": 0.08}),
            lambda log: log["candidates"][0].update({"call": True}),
        ]
        for index, corrupt in enumerate(mutations):
            bad = deepcopy(pristine)
            corrupt(bad)
            with self.subTest(corruption=index), self.assertRaises(ValueError):
                v.verify_log(bad)

    def test_no_feasible_start_and_wrong_method_or_schema_rejected(self):
        pristine = _fixture()
        for field, value in (("method", "adaptive_mutation"), ("method", "lambda_own"),
                             ("schema", "ga-adaptive-mutation-only-log-v1")):
            bad = deepcopy(pristine)
            bad[field] = value
            with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                v.verify_log(bad)
        bad = deepcopy(pristine)
        bad["initial_masks"] = ["1111"] * 30
        bad["initial_scores"] = [_score(bad["problem"], mask) for mask in bad["initial_masks"]]
        with self.assertRaises(ValueError):
            v.verify_log(bad)

    def test_verifier_does_not_call_production_controller_or_engine(self):
        log = _fixture()
        with patch.object(crossover, "update_crossover", side_effect=AssertionError("production controller used")), \
             patch.object(crossover, "run_search", side_effect=AssertionError("production GA used")), \
             patch.object(historical_engine, "_evaluate", side_effect=AssertionError("production evaluator used")):
            self.assertEqual(v.verify_log(log)["verification_status"], "VERIFIED")
        source = inspect.getsource(v)
        self.assertNotIn("from .crossover import", source)
        self.assertNotIn("mutation_only.engine import", source)
        self.assertIn("Fraction", source)

    def test_ci_identity_is_required(self):
        log = _fixture()
        for key, value in (("GITHUB_ACTIONS", "false"), ("GITHUB_REPOSITORY", "other/repo"),
                           ("GITHUB_REF", "refs/heads/main")):
            with patch.dict(os.environ, {key: value}), self.assertRaises(ValueError):
                v.verify_log(log)


if __name__ == "__main__":
    unittest.main()
