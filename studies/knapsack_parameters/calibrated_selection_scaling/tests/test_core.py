"""Contract, operator and controller regression cases, executable only in CI."""
from copy import deepcopy
import math
import unittest

import numpy as np

from studies.knapsack_parameters.mutation_grid_100.program import ga_core as historical
from studies.knapsack_parameters.calibrated_selection_scaling.program import ga_core as current
from studies.knapsack_parameters.calibrated_selection_scaling.verification import verify_log
from studies.knapsack_parameters.calibrated_selection_scaling.tests.helpers import (
    CHANNELS, CONTRACT, configured, fixture, require_ci, run_small, scientific_trace, score,
)


class CalibratedCoreTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        require_ci()

    def test_explicit_calibrated_dimensions_and_profiles_replay(self):
        for n, pc in ((500, .9), (100, 1.)):
            for profile in ("k2", "k3", "adaptive"):
                with self.subTest(n=n, pc=pc, profile=profile):
                    log = run_small(n=n, pc=pc, profile=profile, mu=15, budget=30)
                    receipt = verify_log(log)
                    self.assertEqual(receipt["verification_status"], "VERIFIED")
                    self.assertEqual(log["initial_parameters"]["p_m"], .002 if n == 500 else .01)
                    self.assertEqual(log["configuration_contract"], CONTRACT)
                    self.assertIsNone(log["schedule"])
                    for event in log["generations"]:
                        for name in ("p_m", "p_c", "target_mu", "elite_count"):
                            self.assertEqual(event["parameters_before"][name], log["initial_parameters"][name])
                            self.assertEqual(event["parameters_after"][name], log["initial_parameters"][name])

    def test_six_streams_are_independent_reproducible_pcg64(self):
        first = current.create_random_generators(17, 4, 0)
        second = current.create_random_generators(17, 4, 0)
        self.assertEqual(tuple(first), CHANNELS)
        self.assertEqual(len({id(generator) for generator in first.values()}), 6)
        initial_states = []
        for index, channel in enumerate(CHANNELS):
            expected = np.random.PCG64(np.random.SeedSequence([17, 4, 0, index])).state
            self.assertEqual(first[channel].bit_generator.state, expected)
            self.assertEqual(second[channel].bit_generator.state, expected)
            initial_states.append(expected["state"]["state"])
        self.assertEqual(len(set(initial_states)), 6)
        first["selection"].random(3)
        for channel in CHANNELS:
            self.assertEqual(first[channel].bit_generator.state == second[channel].bit_generator.state,
                             channel != "selection")

    def test_complete_trace_repeats_with_identical_rng_input(self):
        first = run_small(profile="adaptive", budget=50)
        second = run_small(profile="adaptive", budget=50)
        self.assertEqual(scientific_trace(first), scientific_trace(second))
        self.assertEqual(first["initial_parameters"], second["initial_parameters"])
        verify_log(first)
        verify_log(second)

    def test_calibrated_route_matches_historical_tournament_at_shared_configuration(self):
        problem, initial = fixture(mu=30, n=100)
        for profile in ("k2", "k3", "adaptive"):
            with self.subTest(profile=profile):
                old = historical.run_ga(problem, initial, historical.tournament_controller(profile),
                                        historical.create_random_generators(17, 4, 0), 151)
                new = run_small(mu=30, profile=profile, problem=problem, initial=initial, budget=151)
                self.assertEqual(scientific_trace(new), scientific_trace(old))
                verify_log(new)

    def test_all_historical_entry_routes_keep_their_exact_log(self):
        problem, initial = fixture(mu=30, n=100)
        for profile in (0, 1, 31, "k2", "k3", "adaptive"):
            with self.subTest(profile=profile):
                original_controller = (historical.parameter_controller(profile) if type(profile) is int
                                       else historical.tournament_controller(profile))
                copied_controller = (current.parameter_controller(profile) if type(profile) is int
                                     else current.tournament_controller(profile))
                old = historical.run_ga(problem, initial, original_controller,
                                        historical.create_random_generators(17, 4, 0), 60)
                new = current.run_ga(problem, initial, copied_controller,
                                     current.create_random_generators(17, 4, 0), 60)
                old.pop("timing_ns")
                new.pop("timing_ns")
                self.assertEqual(new, old)
        for contract, mutation, crossover in ((None, .01, .9), ("population-crossover-v1", .01, 1.),
                                               ("fixed-mutation-grid-v1", .02, 1.)):
            parameters = configured(mu=30, n=100, pc=crossover)
            parameters["p_m"] = mutation
            old = historical.run_ga(problem, initial, historical.parameter_controller(0),
                                    historical.create_random_generators(17, 4, 0), 31,
                                    initial_parameters=parameters, configuration_contract=contract)
            new = current.run_ga(problem, initial, current.parameter_controller(0),
                                 current.create_random_generators(17, 4, 0), 31,
                                 initial_parameters=parameters, configuration_contract=contract)
            old.pop("timing_ns")
            new.pop("timing_ns")
            self.assertEqual(new, old)

    def test_first_generation_k2_and_adaptive_are_identical(self):
        fixed = run_small(profile="k2", budget=20)
        adaptive = run_small(profile="adaptive", budget=20)
        self.assertEqual(fixed["candidates"][:9], adaptive["candidates"][:9])
        before = deepcopy(fixed["generations"][0])
        after = deepcopy(adaptive["generations"][0])
        for event in (before, after):
            event.pop("parameters_after")
            event.pop("parameter_events")
        self.assertEqual(before, after)

    def test_n500_and_pc_one_draw_consumption_is_exact(self):
        for n, pc in ((500, .9), (100, 1.), (6, 0.)):
            with self.subTest(n=n, pc=pc):
                log = run_small(n=n, pc=pc, budget=20)
                expected = current.create_random_generators(17, 4, 0)
                for _ in range(20):
                    for _entry in range(4):
                        expected["selection"].integers(10)
                    crossed = bool(expected["branch"].random() < pc)
                    if crossed:
                        expected["crossover"].random(n)
                    expected["mutation"].random(n)
                for channel in ("initialization", "selection", "branch", "crossover", "mutation"):
                    self.assertEqual(log["rng_final"][channel], expected[channel].bit_generator.state)
                verify_log(log)

    def test_inclusive_population_and_crossover_admission_edges(self):
        for mu in (2, 25000):
            for pc in (0, 1):
                with self.subTest(mu=mu, pc=pc):
                    log = run_small(mu=mu, n=2, pc=pc, budget=1)
                    self.assertEqual(log["initial_population_size"], mu)
                    verify_log(log)

    def test_invalid_population_and_discrete_parameters_are_rejected(self):
        cases = {"target_mu": (1, 25001, True, 10., "10"),
                 "tournament_size": (1, 3, 4, 5, True, 2.),
                 "elite_count": (0, 2, True, 1.)}
        for field, values in cases.items():
            for value in values:
                with self.subTest(field=field, value=value):
                    parameters = configured()
                    parameters[field] = value
                    with self.assertRaises(ValueError):
                        run_small(parameters=parameters)

    def test_invalid_mutation_and_crossover_are_rejected(self):
        for field, values in {"p_m": (0, .01, 1, math.nan, math.inf, -math.inf, True, "0.1", None),
                              "p_c": (-.1, 1.1, math.nan, math.inf, -math.inf, True, False, "0.9", None)}.items():
            for value in values:
                with self.subTest(field=field, value=value):
                    parameters = configured()
                    parameters[field] = value
                    with self.assertRaises(ValueError):
                        run_small(parameters=parameters)

    def test_calibrated_profile_and_initial_selection_must_agree(self):
        for profile in (0, 8, "k4", "k5", "replay"):
            with self.subTest(profile=profile):
                with self.assertRaises(ValueError):
                    run_small(profile=profile, schedule=[2] if profile == "replay" else None)
        for profile, initial_k in (("k2", 3), ("k3", 2), ("adaptive", 3)):
            parameters = configured(profile=profile)
            parameters["tournament_size"] = initial_k
            with self.assertRaises(ValueError):
                run_small(profile=profile, parameters=parameters)

    def test_explicit_population_parameters_and_contract_are_required(self):
        problem, initial = fixture()
        with self.assertRaises(ValueError):
            current.run_ga(problem, initial, current.tournament_controller("k2"),
                           current.create_random_generators(17, 4, 0), 1,
                           configuration_contract=CONTRACT)
        for alteration in (lambda value: value.pop("elite_count"),
                           lambda value: value.update(extra=1)):
            parameters = configured()
            alteration(parameters)
            with self.assertRaises(ValueError):
                run_small(parameters=parameters)
        for contract in ("", "calibrated-selection-v2", True, 1):
            with self.assertRaises(ValueError):
                run_small(contract=contract)
        with self.assertRaises(ValueError):
            run_small(parameters=configured(mu=11))

    def test_caller_parameters_and_population_are_not_mutated_or_aliased(self):
        parameters = configured()
        problem, initial = fixture()
        expected = deepcopy((parameters, problem, initial))
        log = run_small(parameters=parameters, problem=problem, initial=initial, profile="adaptive")
        self.assertEqual((parameters, problem, initial), expected)
        parameters["p_c"] = 0
        problem["weights"][0] = 999
        initial["masks"][0] = "111111"
        self.assertEqual(log["initial_parameters"], expected[0])
        self.assertEqual(log["problem"], expected[1])
        self.assertEqual(log["initial_masks"], expected[2]["masks"])
        verify_log(log)

    def test_final_partial_preserves_population_parameters_and_failure_count(self):
        log = run_small(profile="adaptive", budget=20)
        event = log["generations"][-1]
        self.assertFalse(event["complete"])
        self.assertEqual(event["controller_event"], "PARTIAL_NO_UPDATE")
        self.assertIsNone(event["success"])
        self.assertIsNone(event["stagnation_overshoot"])
        self.assertEqual(event["parameter_events"], [])
        self.assertEqual(event["parameters_before"], event["parameters_after"])
        self.assertEqual(event["population_before"], event["population_after"])
        self.assertEqual(event["failed_queries_before"], event["failed_queries_after"])
        self.assertEqual(log["summary"]["partial_children"], 2)
        self.assertEqual(len(log["candidates"]), 20)
        verify_log(log)

    def test_n500_stagnation_threshold_and_partial_tail_are_replayed(self):
        problem, initial = fixture(mu=20, n=500, identical=True, capacity=0)
        log = run_small(mu=20, profile="adaptive", problem=problem, initial=initial, budget=153)
        complete = [event for event in log["generations"] if event["complete"]]
        self.assertEqual(len(complete), 8)
        self.assertEqual([event["failed_queries_after"] for event in complete],
                         [19, 38, 57, 76, 95, 114, 133, 0])
        self.assertEqual(complete[-1]["controller_event"], "STAGNATION")
        self.assertEqual(complete[-1]["failed_queries_accumulated"], 152)
        self.assertEqual(complete[-1]["stagnation_overshoot"], 7)
        self.assertEqual(log["generations"][-1]["controller_event"], "PARTIAL_NO_UPDATE")
        self.assertEqual(log["summary"]["final_failed_queries"], 0)
        self.assertEqual(log["summary"]["partial_children"], 1)
        verify_log(log)

    def test_partial_record_is_retained_without_committing_offspring(self):
        problem, initial = fixture(mu=10, n=2, identical=True, capacity=3)
        generators = current.create_random_generators(17, 4, 0)
        # Choose a prospective PCG64 starting state whose first mask mutates.
        # The exact starting state is journaled and replayed; no search result
        # or reference optimum selects the fixture.
        for _ in range(100):
            preview = deepcopy(generators["mutation"])
            if any(preview.random(2) < .5):
                break
            generators["mutation"].random(2)
        else:
            self.fail("Unable to form deterministic partial-record fixture")
        log = current.run_ga(problem, initial, current.tournament_controller("adaptive"),
                             generators, 1, initial_parameters=configured(n=2),
                             configuration_contract=CONTRACT)
        event = log["generations"][0]
        self.assertFalse(event["complete"])
        self.assertEqual(log["summary"]["best_call"], 1)
        self.assertGreater(log["summary"]["best_profit"], 0)
        self.assertEqual(log["summary"]["final_population"], list(range(10)))
        self.assertEqual(log["summary"]["final_parameters"], configured(n=2))
        self.assertEqual(event["controller_event"], "PARTIAL_NO_UPDATE")
        receipt = verify_log(log)
        self.assertFalse(receipt["derived_metrics"]["population_trace"][-1]["record_in_population"])

    def test_duplicate_ties_infeasibility_and_single_elite_are_preserved(self):
        problem = {"n": 2, "weights": [1, 1], "profits": [1, 1], "capacity": 0}
        initial = {"masks": ["00"] * 10, "scores": [score(problem, "00")] * 10}
        log = run_small(problem=problem, initial=initial, budget=180, profile="adaptive")
        self.assertEqual(log["summary"]["best_profit"], 0)
        self.assertGreater(log["summary"]["duplicate_calls"], 0)
        self.assertGreater(log["summary"]["infeasible_calls"], 0)
        self.assertTrue(any(len(set(entries)) < len(entries)
                            for child in log["candidates"] for entries in child["tournaments"]))
        for event in log["generations"]:
            self.assertEqual(len(event["elite_references"]), 1)
            self.assertEqual(event["population_after"][0], event["elite_references"][0])
        verify_log(log)

    def test_single_elite_survives_with_worse_offspring_admitted(self):
        problem = {"n": 100, "weights": [1] * 100, "profits": [1] * 100, "capacity": 100}
        initial = {"masks": ["1" * 100] * 10, "scores": [score(problem, "1" * 100)] * 10}
        log = run_small(problem=problem, initial=initial, budget=90, pc=0)
        self.assertTrue(any(child["profit"] < 100 for child in log["candidates"]))
        masks = initial["masks"] + [child["mask"] for child in log["candidates"]]
        for event in log["generations"]:
            self.assertEqual(len(event["population_after"]), 10)
            self.assertEqual(masks[event["elite_references"][0]], "1" * 100)
            self.assertEqual(event["population_after"][1:],
                             list(range(10 + event["start_call"] - 1, 10 + event["end_call"])))
        verify_log(log)

    def test_optimum_or_extra_problem_metadata_is_rejected(self):
        problem, initial = fixture()
        problem["optimum"] = 100
        with self.assertRaises(ValueError):
            run_small(problem=problem, initial=initial)


if __name__ == "__main__":
    require_ci()
    unittest.main()
