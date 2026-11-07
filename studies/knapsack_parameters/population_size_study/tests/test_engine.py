"""CI-only regression and boundary checks for the configured shared GA loop."""
from __future__ import annotations

from copy import deepcopy
from fractions import Fraction
import gzip
import hashlib
import json
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

PACKAGE = Path(__file__).resolve().parents[2] / "presentation_package"
sys.path.insert(0, str(PACKAGE))

from program.ga_core import create_random_generators, parameter_controller, run_ga
from program.ga_core.controllers import (default_parameters,
    update_configured_fixed_parameters, update_parameters, validate_initial_parameters)
from program.ga_core.engine import run_search
from program.ga_core.operators import evaluate


def problem(item_count=8):
    """Use a fully feasible teaching problem, not a benchmark result."""
    return {"n": item_count, "weights": [1] * item_count,
            "profits": list(range(1, item_count + 1)), "capacity": item_count}


def parameters(item_count, population_size):
    return {"p_m": 1 / item_count, "p_c": .9, "target_mu": population_size,
            "tournament_size": 2, "elite_count": 1}


def known_population(instance, population_size):
    masks = ["0" * instance["n"]] * population_size
    return {"masks": masks, "scores": [evaluate(instance, mask) for mask in masks]}


def without_timing(log):
    result = deepcopy(log)
    result.pop("timing_ns", None)
    return result


@unittest.skipUnless(os.environ.get("GITHUB_ACTIONS") == "true", "Scientific fixtures run only in GitHub Actions")
class ConfiguredEngineTests(unittest.TestCase):
    def run_configured(self, population_size=5, item_count=8, budget=6, seed=129999):
        instance = problem(item_count)
        initial = known_population(instance, population_size)
        return run_ga(instance, initial, parameter_controller(0),
                      create_random_generators(seed, 0, 0), budget,
                      initial_parameters=parameters(item_count, population_size))

    def test_smallest_population_completes_one_offspring_generations(self):
        log = self.run_configured(population_size=2, budget=3)
        self.assertEqual(log["schema"], "ga-knapsack-configured-fixed-log-v1")
        self.assertEqual(log["initial_population_size"], 2)
        self.assertEqual(log["summary"]["known_score_validation_evaluations"], 2)
        self.assertEqual(log["summary"]["new_calls"], 3)
        self.assertEqual(log["summary"]["full_generations"], 3)
        self.assertEqual(log["summary"]["partial_children"], 0)
        self.assertTrue(all(row["requested_offspring"] == 1 for row in log["generations"]))
        self.assertTrue(all(len(row["population_after"]) == 2 for row in log["generations"]))

    def test_partial_generation_counts_all_candidates_without_population_update(self):
        log = self.run_configured(population_size=5, budget=6)
        self.assertEqual(len(log["candidates"]), 6)
        self.assertEqual(log["summary"]["physical_evaluations"], 6)
        self.assertEqual(log["summary"]["full_generations"], 1)
        self.assertEqual(log["summary"]["partial_children"], 2)
        complete, partial = log["generations"]
        self.assertTrue(complete["complete"])
        self.assertFalse(partial["complete"])
        self.assertEqual(partial["requested_offspring"], 4)
        self.assertEqual(partial["controller_event"], "PARTIAL_NO_UPDATE")
        self.assertIsNone(partial["success"])
        self.assertEqual(partial["parameter_events"], [])
        self.assertEqual(partial["population_before"], partial["population_after"])
        self.assertEqual(log["summary"]["final_population"], complete["population_after"])
        self.assertEqual(partial["failed_queries_before"], partial["failed_queries_after"])

    def test_final_evaluated_candidate_can_improve_record_without_replacing_population(self):
        instance = problem(4)
        initial = known_population(instance, 4)
        scripted_masks = iter(["0000", "0000", "0000", "1111"])

        def scripted_offspring(first, second, count, settings, generators):
            # A controlled operator fixture isolates the terminal-prefix accounting.
            mask = next(scripted_masks)
            changed = [index for index, (old, new) in enumerate(zip(first, mask)) if old != new]
            return False, first, changed, mask

        with patch("program.ga_core.engine.create_offspring", side_effect=scripted_offspring):
            log = run_ga(instance, initial, parameter_controller(0),
                         create_random_generators(129999, 0, 0), 4,
                         initial_parameters=parameters(4, 4))
        self.assertEqual(log["summary"]["best_mask"], "1111")
        self.assertEqual(log["summary"]["best_profit"], 10)
        self.assertEqual(log["summary"]["best_call"], 4)
        all_masks = log["initial_masks"] + [row["mask"] for row in log["candidates"]]
        self.assertNotIn("1111", [all_masks[index] for index in log["summary"]["final_population"]])
        self.assertEqual(log["summary"]["duplicate_calls"], 3)

    def test_normalized_mutation_and_fixed_parameters_for_all_dimensions(self):
        for item_count in (100, 200, 500):
            with self.subTest(item_count=item_count):
                expected = parameters(item_count, 3)
                log = self.run_configured(population_size=3, item_count=item_count, budget=3)
                self.assertEqual(log["initial_parameters"], expected)
                self.assertEqual(log["summary"]["final_parameters"], expected)
                self.assertAlmostEqual(item_count * expected["p_m"], 1)
                for generation in log["generations"]:
                    self.assertEqual(generation["parameters_before"], expected)
                    self.assertEqual(generation["parameters_after"], expected)
                    self.assertEqual(generation["actual_parent_mu"], 3)

    def test_configured_run_is_deterministic_except_timing(self):
        self.assertEqual(without_timing(self.run_configured()),
                         without_timing(self.run_configured()))

    def test_inputs_and_random_initialization_stream_are_not_mutated(self):
        instance = problem()
        initial = known_population(instance, 5)
        configuration = parameters(8, 5)
        input_snapshot = deepcopy((instance, initial, configuration))
        generators = create_random_generators(129999, 0, 0)
        initialization_state = deepcopy(generators["initialization"].bit_generator.state)
        log = run_ga(instance, initial, parameter_controller(0), generators, 3,
                     initial_parameters=configuration)
        self.assertEqual((instance, initial, configuration), input_snapshot)
        self.assertEqual(generators["initialization"].bit_generator.state, initialization_state)
        configuration["target_mu"] = 6
        initial["scores"][0]["profit"] = 999
        self.assertEqual(log["initial_parameters"]["target_mu"], 5)
        self.assertEqual(log["initial_scores"][0]["profit"], 0)

    def test_explicit_configuration_matches_legacy_fixed_search_at_shared_values(self):
        instance = problem(100)
        initial = known_population(instance, 30)
        legacy = run_ga(instance, initial, parameter_controller(0),
                        create_random_generators(129999, 0, 0), 60)
        configured = run_ga(instance, initial, parameter_controller(0),
                            create_random_generators(129999, 0, 0), 60,
                            initial_parameters=parameters(100, 30))
        comparable = without_timing(configured)
        comparable["schema"] = legacy["schema"]
        comparable.pop("initial_parameters")
        comparable.pop("initial_population_size")
        self.assertEqual(comparable, without_timing(legacy))
        self.assertEqual(set(legacy), {"schema", "profile", "problem", "initial_masks",
            "initial_scores", "rng_initial", "budget", "candidates", "generations", "summary",
            "rng_final", "timing_ns"})

    def test_historical_fixed_run_still_matches_retained_full_reference(self):
        input_path = PACKAGE / "data" / "parameters" / "UC-s020.json"
        self.assertEqual(hashlib.sha256(input_path.read_bytes()).hexdigest(),
                         "4b5e6a508e0391c39d91f7cded566be15424da12b91dc4ba990d5f0ee2b0f9f1")
        with input_path.open(encoding="utf-8") as stream:
            case = json.load(stream)
        reference = PACKAGE / "tests" / "references" / "parameters" / "UC-s020-bank-97001-p00.json.gz"
        self.assertEqual(hashlib.sha256(reference.read_bytes()).hexdigest(),
                         "749c0328206c1f4bfddacfaaec2a29e4165e6737d7f83b6d8e5633bf07b800dd")
        with gzip.open(reference, "rt", encoding="utf-8") as stream:
            expected = json.load(stream)
        actual = run_ga(case["problem"], case["initial_population"], parameter_controller(0),
            create_random_generators(case["seed"], case["task_index"], case["start_index"]), 5000)
        self.assertEqual(without_timing(actual), without_timing(expected))

    def test_legacy_initial_count_is_not_silently_relaxed(self):
        instance = problem()
        with self.assertRaises(ValueError):
            run_ga(instance, known_population(instance, 5), parameter_controller(0),
                   create_random_generators(129999, 0, 0), 1)

    def test_new_initial_count_matches_explicit_population(self):
        instance = problem()
        with self.assertRaises(ValueError):
            run_ga(instance, known_population(instance, 5), parameter_controller(0),
                   create_random_generators(129999, 0, 0), 1,
                   initial_parameters=parameters(8, 6))

    def test_adaptive_profiles_and_schedules_cannot_use_fixed_configuration(self):
        instance = problem()
        initial = known_population(instance, 5)
        for profile in (1, 31, "k2", "adaptive", "replay"):
            with self.subTest(profile=profile), self.assertRaises(ValueError):
                run_search(instance, initial["masks"], initial["scores"], profile,
                           create_random_generators(129999, 0, 0), 1,
                           [2] if profile == "replay" else None,
                           initial_parameters=parameters(8, 5))
        with self.assertRaises(ValueError):
            run_search(instance, initial["masks"], initial["scores"], 0,
                       create_random_generators(129999, 0, 0), 1, [2],
                       initial_parameters=parameters(8, 5))

    def test_invalid_parameters_and_oracle_metadata_are_rejected(self):
        base = parameters(100, 5)
        bad_parameters = [None, {}, dict(base, optimum=10)]
        bad_parameters += [dict(base, **change) for change in (
            {"target_mu": 1}, {"target_mu": 25001}, {"target_mu": True},
            {"p_m": .02}, {"p_m": float("nan")}, {"p_m": True},
            {"p_c": 1.0}, {"p_c": float("inf")},
            {"tournament_size": 3}, {"elite_count": 2},
        )]
        for configuration in bad_parameters:
            with self.subTest(configuration=configuration), self.assertRaises(ValueError):
                validate_initial_parameters(configuration, 100)
        instance = dict(problem(), optimum=100)
        with self.assertRaises(ValueError):
            run_ga(instance, known_population(problem(), 5), parameter_controller(0),
                   create_random_generators(129999, 0, 0), 1,
                   initial_parameters=parameters(8, 5))

    def test_boundaries_do_not_require_executing_a_large_search(self):
        for population_size in (2, 25000):
            original = parameters(500, population_size)
            result = validate_initial_parameters(original, 500)
            self.assertEqual(result, original)
            self.assertIsNot(result, original)
            event = update_configured_fixed_parameters(original, 0, False,
                population_size - 1, Fraction(0), 500)
            self.assertTrue(next(item for item in event["parameter_events"]
                                 if item["field"] == "target_mu")["at_boundary"])

    def test_configured_controller_observes_stagnation_without_adapting(self):
        settings = parameters(200, 146)
        failed = update_configured_fixed_parameters(settings, 0, False, 145, Fraction(0), 200)
        self.assertEqual(failed["event"], "STAGNATION")
        self.assertEqual(failed["failed_queries_after"], 0)
        self.assertEqual(failed["parameters"], settings)
        self.assertEqual(failed["stagnation_overshoot"], 0)
        self.assertTrue(all(not item["enabled"] and item["before"] == item["after"]
                            for item in failed["parameter_events"]))
        success = update_configured_fixed_parameters(settings, 144, True, 145, Fraction(1), 200)
        self.assertEqual(success["event"], "SUCCESS")
        self.assertEqual(success["failed_queries_accumulated"], 0)
        self.assertEqual(success["parameters"], settings)

    def test_configured_observations_match_historical_fixed_events_when_compatible(self):
        settings = default_parameters(0)
        for before, success in ((0, False), (116, False), (144, True)):
            with self.subTest(before=before, success=success):
                expected = update_parameters(settings, before, success, 29, Fraction(1, 2), 0)
                actual = update_configured_fixed_parameters(settings, before, success, 29,
                                                            Fraction(1, 2), 100)
                self.assertEqual(actual, expected)


if __name__ == "__main__":
    unittest.main()
