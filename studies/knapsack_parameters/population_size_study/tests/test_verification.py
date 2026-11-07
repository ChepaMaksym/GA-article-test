"""CI fixtures for independent reconstruction of configured population journals."""
from __future__ import annotations

from copy import deepcopy
import os
import unittest

from studies.knapsack_parameters.presentation_package.program.ga_core import (
    create_random_generators,
    parameter_controller,
    run_ga,
)
from studies.knapsack_parameters.population_size_study.verification import verify_log


def fixture(n=8, population_size=5, offspring=11, capacity=None, repeated=False):
    """Create a small teaching log; never invoked outside a CI test method."""
    problem = {"n": n, "weights": [1 + i % 3 for i in range(n)],
               "profits": [2 + i % 5 for i in range(n)],
               "capacity": n if capacity is None else capacity}
    masks = ["0" * n if repeated else format(i % (1 << n), f"0{n}b")
             for i in range(population_size)]
    scores = []
    for mask in masks:
        weight = sum(problem["weights"][i] for i, bit in enumerate(mask) if bit == "1")
        profit = sum(problem["profits"][i] for i, bit in enumerate(mask) if bit == "1")
        scores.append({"weight": weight, "profit": profit, "feasible": weight <= problem["capacity"]})
    parameters = {"p_m": 1 / n, "p_c": 0.9, "target_mu": population_size,
                  "tournament_size": 2, "elite_count": 1}
    return run_ga(problem, {"masks": masks, "scores": scores}, parameter_controller(0),
                  create_random_generators(130000, 1, 0), budget=offspring,
                  initial_parameters=parameters)


@unittest.skipUnless(os.environ.get("GITHUB_ACTIONS") == "true", "Scientific fixtures run only in GitHub Actions")
class ConfiguredJournalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.log = fixture()

    def test_full_reconstruction_including_partial_prefix(self):
        result = verify_log(deepcopy(self.log))
        self.assertEqual(result["verification_status"], "VERIFIED")
        self.assertEqual(result["new_calls"], 11)
        self.assertEqual(result["initial_score_checks"], 5)
        self.assertEqual(result["completed_generations"], 2)
        self.assertEqual(result["partial_generations"], 1)
        self.assertEqual(result["summary"]["partial_children"], 3)
        self.assertEqual(result["independent_score_checks"], 5 + 2 * 11)

    def test_smallest_population_has_one_new_offspring_per_generation(self):
        result = verify_log(fixture(population_size=2, offspring=5))
        self.assertEqual(result["completed_generations"], 5)
        self.assertEqual(result["partial_generations"], 0)

    def test_global_empty_control_has_no_strict_record(self):
        result = verify_log(fixture(population_size=5, offspring=150, capacity=0, repeated=True))
        self.assertEqual(result["record_profit"], 0)
        self.assertEqual(result["record_call"], 0)
        self.assertEqual(result["summary"]["best_mask"], "0" * 8)
        self.assertTrue(any(item["controller_event"] == "STAGNATION"
                            for item in result["derived_metrics"]["generation_trace"]))

    def test_large_dimension_normalizes_mutation(self):
        result = verify_log(fixture(n=500, population_size=3, offspring=3))
        self.assertEqual(result["final_parameters"]["p_m"], 1 / 500)
        self.assertEqual(result["initial_score_checks"], 3)

    def test_largest_population_retains_partial_prefix_population(self):
        result = verify_log(fixture(n=2, population_size=25000, offspring=1, repeated=True))
        self.assertEqual(result["initial_score_checks"], 25000)
        self.assertEqual(result["completed_generations"], 0)
        self.assertEqual(result["partial_generations"], 1)
        self.assertEqual(result["final_population_refs"], list(range(25000)))

    def reject(self, mutate):
        invalid = deepcopy(self.log)
        mutate(invalid)
        with self.assertRaises(ValueError):
            verify_log(invalid)

    def test_corrupt_final_mask(self):
        self.reject(lambda log: log["candidates"][0].__setitem__("mask", "x" * 8))

    def test_corrupt_pre_mutation_mask(self):
        self.reject(lambda log: log["candidates"][0].__setitem__("pre_mask", "x" * 8))

    def test_corrupt_mutation_positions(self):
        self.reject(lambda log: log["candidates"][0].__setitem__("mutation_bits", [99]))

    def test_corrupt_parent_positions(self):
        self.reject(lambda log: log["candidates"][0].__setitem__("parent_indices", [0, 99]))

    def test_corrupt_evaluation_count(self):
        self.reject(lambda log: log.__setitem__("budget", log["budget"] + 1))

    def test_corrupt_known_initial_score(self):
        self.reject(lambda log: log["initial_scores"][0].__setitem__("profit", 99))

    def test_wrong_explicit_initial_size(self):
        self.reject(lambda log: log.__setitem__("initial_population_size", 30))

    def test_parameter_drift(self):
        self.reject(lambda log: log["generations"][0]["parameters_after"].__setitem__("target_mu", 6))

    def test_initial_configuration_extra_field(self):
        self.reject(lambda log: log["initial_parameters"].__setitem__("optimum", 999))

    def test_optimum_in_problem_rejected(self):
        self.reject(lambda log: log["problem"].__setitem__("optimum", 999))

    def test_rng_channel_missing(self):
        self.reject(lambda log: log["rng_initial"].pop("ties"))

    def test_rng_state_malformed(self):
        self.reject(lambda log: log["rng_initial"]["ties"].__setitem__("bit_generator", "MT19937"))

    def test_rng_final_state_changed(self):
        def mutate(log):
            log["rng_final"]["mutation"]["state"]["state"] += 1
        self.reject(mutate)

    def test_population_replacement_corrupted(self):
        self.reject(lambda log: log["generations"][0].__setitem__("population_after", [0] * 5))

    def test_partial_prefix_cannot_replace_population(self):
        self.reject(lambda log: log["generations"][-1].__setitem__("complete", True))

    def test_fixed_events_cannot_enable_adaptation(self):
        self.reject(lambda log: log["generations"][0]["parameter_events"][0].__setitem__("enabled", True))

    def test_candidate_duplicate_flag_reconstructed(self):
        def mutate(log):
            child = log["candidates"][0]
            child["duplicate"] = not child["duplicate"]
        self.reject(mutate)

    def test_non_json_timing_rejected(self):
        self.reject(lambda log: log["timing_ns"].__setitem__("total", float("nan")))

    def test_unknown_top_level_field_rejected(self):
        self.reject(lambda log: log.__setitem__("unregistered", True))


class VerificationEnvironmentTests(unittest.TestCase):
    def test_local_execution_is_not_permitted(self):
        # This is a guard assertion only; no search or reconstruction is performed.
        from unittest.mock import patch
        with patch.dict(os.environ, {"GITHUB_ACTIONS": "false"}):
            with self.assertRaisesRegex(ValueError, "GitHub Actions required"):
                verify_log({})


if __name__ == "__main__":
    unittest.main()
