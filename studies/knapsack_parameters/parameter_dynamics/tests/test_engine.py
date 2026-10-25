"""CI-only instructional fixtures; no KPLIB experiments or parameter tuning."""
from __future__ import annotations

import copy
from fractions import Fraction
import inspect
import itertools
import os
import unittest
from unittest.mock import patch

import numpy as np

from studies.knapsack_parameters.parameter_dynamics import engine
from studies.knapsack_parameters.two_signal_mutation import engine as historical


def problem(n=10, capacity=None):
    return {"n": n, "weights": [1] * n, "profits": list(range(1, n + 1)),
            "capacity": n if capacity is None else capacity}


def journal(profile=31, *, p=None, masks=None, budget=61, seed=7):
    p = problem() if p is None else p
    masks = ["0" * p["n"]] * 30 if masks is None else masks
    scores = [engine.evaluate(p, mask) for mask in masks]
    return engine.run_search(p, masks, scores, profile, engine.make_rngs(seed, 0, 0), budget=budget)


def instructional(predicate, **kwargs):
    # A fixed bounded search for educational events, never scientific seeds.
    for seed in range(128):
        log = journal(seed=seed, **kwargs)
        if predicate(log):
            return log
    raise AssertionError("No instructional fixture found in the fixed seed range 0..127")


def semantic(log):
    value = copy.deepcopy(log)
    value.pop("timing_ns")
    return value


class ParameterDynamicsEngineTests(unittest.TestCase):
    def test_default_parameters_are_independent_and_registered(self):
        first = engine.default_parameters()
        self.assertEqual(first, {"p_m": .01, "p_c": .9, "target_mu": 30,
                                 "tournament_size": 2, "elite_count": 1})
        first["target_mu"] = 50
        self.assertEqual(engine.default_parameters()["target_mu"], 30)

    def test_novelty_formula_by_exhaustive_small_crossovers(self):
        for n in range(2, 6):
            for distance in range(n + 1):
                a, b = "0" * n, "1" * distance + "0" * (n - distance)
                outcomes = ["".join(a[i] if bit else b[i] for i, bit in enumerate(choices))
                            for choices in itertools.product((False, True), repeat=n)]
                self.assertEqual(engine.novelty_probability(distance),
                                 Fraction(sum(child not in (a, b) for child in outcomes), 2 ** n))
        for distance in (-1, True, .5):
            with self.assertRaises(ValueError):
                engine.novelty_probability(distance)

    def test_exact_mean_is_not_function_of_average_distance(self):
        stats = engine.novelty_statistics([0, 4])
        self.assertEqual(Fraction(stats["novelty_mean_numerator"], stats["novelty_mean_denominator"]), Fraction(7, 16))
        self.assertNotEqual(Fraction(7, 16), engine.novelty_probability(2))
        with self.assertRaises(ValueError):
            engine.novelty_statistics([])

    def test_all_thirty_two_flags_update_only_enabled_fields(self):
        initial = engine.default_parameters()
        success = {"p_m": .01, "p_c": .5, "target_mu": 15, "tournament_size": 3, "elite_count": 2}
        stagnant = {"p_m": .02, "p_c": .5, "target_mu": 60, "tournament_size": 2, "elite_count": 1}
        for profile in range(32):
            for improved, before_count, expected in ((True, 0, success), (False, 116, stagnant)):
                result = engine.update_parameters(initial, before_count, improved, 29, Fraction(1, 2), profile)
                for bit, name in enumerate(engine.PARAMETER_NAMES):
                    self.assertEqual(result["parameters"][name], expected[name] if profile & (1 << bit) else initial[name])
                    self.assertEqual(result["parameter_events"][bit]["enabled"], bool(profile & (1 << bit)))
        self.assertEqual(initial, engine.default_parameters())

    def test_failure_counter_threshold_resets_even_with_all_flags_off(self):
        params = engine.default_parameters()
        count = 0
        for generation in range(1, 6):
            result = engine.update_parameters(params, count, False, 29, Fraction(0), 0)
            self.assertEqual(result["parameters"], params)
            count = result["failed_queries_after"]
            self.assertEqual(count, 29 * generation if generation < 5 else 0)
        self.assertEqual(result["event"], "STAGNATION")
        self.assertEqual(result["stagnation_overshoot"], 0)

    def test_variable_generation_failure_overshoot_is_recorded(self):
        params = engine.default_parameters()
        params["target_mu"] = 60
        result = engine.update_parameters(params, 100, False, 59, Fraction(0), 4)
        self.assertEqual(result["failed_queries_accumulated"], 159)
        self.assertEqual(result["stagnation_overshoot"], 14)
        self.assertEqual(result["failed_queries_after"], 0)
        self.assertEqual(result["parameters"]["target_mu"], 100)

    def test_success_has_priority_and_uses_no_failed_queries_from_successful_generation(self):
        result = engine.update_parameters(engine.default_parameters(), 144, True, 29, Fraction(0), 31)
        self.assertEqual(result["event"], "SUCCESS")
        self.assertEqual(result["failed_queries_accumulated"], 0)
        self.assertEqual(result["failed_queries_after"], 0)
        self.assertEqual(result["stagnation_overshoot"], 0)

    def test_simultaneous_update_uses_old_vector_not_modified_elite_count(self):
        result = engine.update_parameters(engine.default_parameters(), 0, True, 29, Fraction(1, 2), 31)
        self.assertEqual(result["parameters"], {"p_m": .01, "p_c": .5, "target_mu": 15,
                                               "tournament_size": 3, "elite_count": 2})
        self.assertEqual([event["field"] for event in result["parameter_events"]], list(engine.PARAMETER_NAMES))

    def test_population_halving_rounds_up_and_has_registered_minimum(self):
        params = engine.default_parameters()
        params["target_mu"] = 31
        self.assertEqual(engine.update_parameters(params, 0, True, 30, Fraction(0), 4)["parameters"]["target_mu"], 16)
        params["target_mu"] = 15
        self.assertEqual(engine.update_parameters(params, 0, True, 14, Fraction(0), 4)["parameters"]["target_mu"], 10)

    def test_crossover_uses_one_float_conversion_of_exact_affine_expression(self):
        for novelty in (Fraction(0), Fraction(1, 3), Fraction(7, 16), Fraction(1)):
            result = engine.update_parameters(engine.default_parameters(), 0, False, 29, novelty, 2)
            self.assertEqual(result["parameters"]["p_c"], float(Fraction(1, 10) + Fraction(4, 5) * novelty))
            self.assertEqual(result["event"], "NO_CHANGE")
        self.assertEqual(engine.update_parameters(engine.default_parameters(), 0, False, 29, Fraction(0), 2)
                         ["parameters"]["p_c"], .1)

    def test_boundary_events_do_not_claim_actual_parameter_changes(self):
        params = {"p_m": .08, "p_c": .9, "target_mu": 100, "tournament_size": 5, "elite_count": 5}
        success = engine.update_parameters(params, 0, True, 95, Fraction(1), 31)
        events = {event["field"]: event for event in success["parameter_events"]}
        self.assertEqual(events["tournament_size"]["direction"], "unchanged")
        self.assertTrue(events["tournament_size"]["at_boundary"])
        self.assertEqual(events["elite_count"]["direction"], "unchanged")
        stagnant = engine.update_parameters(params, 144, False, 95, Fraction(1), 31)
        events = {event["field"]: event for event in stagnant["parameter_events"]}
        self.assertEqual(events["p_m"]["direction"], "unchanged")
        self.assertEqual(events["target_mu"]["direction"], "unchanged")
        self.assertEqual(stagnant["failed_queries_after"], 0)

    def test_invalid_controller_inputs_and_disabled_field_drift_are_rejected(self):
        initial = engine.default_parameters()
        cases = ((initial, 145, False, 29, Fraction(0), 31), (initial, True, False, 29, Fraction(0), 31),
                 (initial, 0, 1, 29, Fraction(0), 31), (initial, 0, False, 28, Fraction(0), 31),
                 (initial, 0, False, 29, .5, 31), (initial, 0, False, 29, Fraction(-1), 31),
                 (initial, 0, False, 29, Fraction(2), 31), (initial, 0, False, 29, Fraction(0), True),
                 (initial, 0, False, 29, Fraction(0), 32), (initial, 0, False, 29, Fraction(0), -1))
        for args in cases:
            with self.subTest(args=args), self.assertRaises(ValueError):
                engine.update_parameters(*args)
        for name, value in (("p_m", float("nan")), ("p_c", True), ("target_mu", 9),
                            ("tournament_size", 6), ("elite_count", 0)):
            invalid = dict(initial)
            invalid[name] = value
            with self.assertRaises(ValueError):
                engine.update_parameters(invalid, 0, True, 29, Fraction(0), 31)
        drift = dict(initial, p_m=.02)
        with self.assertRaises(ValueError):
            engine.update_parameters(drift, 0, True, 29, Fraction(0), 0)

    def test_all_profiles_have_identical_first_generation_candidates_populations_and_rngs(self):
        baseline = journal(0, budget=29)
        for profile in range(1, 32):
            other = journal(profile, budget=29)
            self.assertEqual(other["candidates"], baseline["candidates"])
            for field in ("parameters_before", "population_before", "population_after", "elite_indices",
                          "elite_references", "actual_parent_mu", "rng_before", "rng_after", "parent_distances"):
                self.assertEqual(other["generations"][0][field], baseline["generations"][0][field])

    def test_fixed_profile_preserves_full_historical_candidates_rng_and_populations_n100(self):
        p = problem(100, 50)
        masks = ["0" * 100] + [format(index, "0100b") for index in range(1, 30)]
        scores = [engine.evaluate(p, mask) for mask in masks]
        new = engine.run_search(p, masks, scores, 0, engine.make_rngs(19, 2, 1), budget=5000)
        old = historical.run_search(p, masks, scores, "fixed", historical.make_rngs(19, 2, 1), budget=5000)
        self.assertEqual(new["candidates"], old["candidates"])
        self.assertEqual(new["rng_initial"], old["rng_initial"])
        self.assertEqual(new["rng_final"], old["rng_final"])
        for first, second in zip(new["generations"], old["generations"]):
            for field in ("population_before", "population_after", "rng_before", "rng_after"):
                self.assertEqual(first[field], second[field])
            self.assertEqual(first["elite_indices"], [second["elite_index"]])

    def test_target_population_changes_only_after_next_generation_finishes(self):
        log = journal(4, p=problem(2), masks=["11"] * 30, budget=204)
        fifth, sixth = log["generations"][4:6]
        self.assertEqual(fifth["end_call"], 145)
        self.assertEqual(fifth["parameters_after"]["target_mu"], 60)
        self.assertEqual(len(fifth["population_after"]), 30)
        self.assertEqual(sixth["actual_parent_mu"], 30)
        self.assertEqual(sixth["requested_offspring"], 59)
        self.assertEqual(len(sixth["population_after"]), 60)

    def test_growing_terminal_prefix_does_not_replace_population_or_update_controller(self):
        log = journal(4, p=problem(2), masks=["11"] * 30, budget=146)
        final = log["generations"][-1]
        self.assertFalse(final["complete"])
        self.assertEqual(final["parameters_before"]["target_mu"], 60)
        self.assertEqual(final["actual_parent_mu"], 30)
        self.assertEqual(final["requested_offspring"], 59)
        self.assertEqual(final["population_after"], final["population_before"])
        self.assertEqual(final["parameters_after"], final["parameters_before"])
        self.assertEqual(final["failed_queries_after"], final["failed_queries_before"])
        self.assertIsNone(final["success"])
        self.assertIsNone(final["stagnation_overshoot"])
        self.assertEqual(final["parameter_events"], [])

    def test_failed_query_count_uses_variable_offspring_not_generation_count(self):
        log = journal(4, p=problem(2), masks=["11"] * 30, budget=322)
        generation = log["generations"][-1]
        self.assertTrue(generation["complete"])
        self.assertEqual(generation["end_call"], 322)
        self.assertEqual(generation["failed_queries_accumulated"], 177)
        self.assertEqual(generation["stagnation_overshoot"], 32)
        self.assertEqual(generation["parameters_after"]["target_mu"], 100)
        self.assertEqual(len(generation["population_after"]), 60)

    def test_joint_success_uses_more_elites_larger_tournaments_and_smaller_next_population(self):
        log = instructional(lambda item: item["generations"][0]["success"], profile=31, budget=42)
        first, second = log["generations"][:2]
        self.assertEqual(first["parameters_after"], {"p_m": .01, "p_c": .1, "target_mu": 15,
                                                    "tournament_size": 3, "elite_count": 2})
        self.assertEqual(second["actual_parent_mu"], 30)
        self.assertEqual(second["requested_offspring"], 13)
        self.assertTrue(second["complete"])
        self.assertEqual(len(second["population_after"]), 15)
        self.assertEqual(len(set(second["elite_indices"])), 2)
        for child in log["candidates"][29:]:
            self.assertEqual([len(entries) for entries in child["tournaments"]], [3, 3])

    def test_sequential_elites_are_distinct_best_occurrences(self):
        log = instructional(lambda item: item["generations"][0]["success"], profile=16, budget=57)
        masks = list(log["initial_masks"]) + [child["mask"] for child in log["candidates"]]
        scores = [engine.evaluate(log["problem"], mask) for mask in masks]
        second = log["generations"][1]
        before = second["population_before"]
        available = list(range(len(before)))
        self.assertEqual(len(second["elite_indices"]), 2)
        for position, reference in zip(second["elite_indices"], second["elite_references"]):
            self.assertIn(position, available)
            self.assertEqual(reference, before[position])
            selected = (scores[reference]["feasible"], scores[reference]["profit"])
            self.assertEqual(selected, max((scores[before[index]]["feasible"], scores[before[index]]["profit"])
                                           for index in available))
            available.remove(position)
        self.assertEqual(second["population_after"][:2], second["elite_references"])

    def test_tournament_repeated_occurrences_are_retained(self):
        log = journal(31, budget=400)
        # Repeated positions in a tournament remain literal occurrences.
        self.assertTrue(any(len(set(entries)) < len(entries) for child in log["candidates"]
                            for entries in child["tournaments"]))
        for generation in log["generations"]:
            for child in log["candidates"][generation["start_call"] - 1:generation["end_call"]]:
                for winner, entries in zip(child["parent_indices"], child["tournaments"]):
                    self.assertIn(winner, entries)

    def test_signal_uses_all_pairs_even_when_crossover_is_not_applied(self):
        log = instructional(lambda item: any(not child["crossover"] for child in item["candidates"]), profile=2, budget=58)
        for generation in log["generations"]:
            children = log["candidates"][generation["start_call"] - 1:generation["end_call"]]
            self.assertEqual(generation["parent_distances"], [child["parent_distance"] for child in children])
            mean = sum((engine.novelty_probability(child["parent_distance"]) for child in children), Fraction(0)) / len(children)
            self.assertEqual(mean, Fraction(generation["novelty_mean_numerator"], generation["novelty_mean_denominator"]))

    def test_worse_and_infeasible_children_enter_completed_population(self):
        log = instructional(lambda item: any(not child["feasible"] for child in item["candidates"]),
                            profile=0, p=problem(2, 0), budget=29)
        event = log["generations"][0]
        self.assertEqual(event["population_after"], event["elite_references"] + list(range(30, 59)))
        self.assertEqual(log["summary"]["best_profit"], 0)

    def test_zero_record_is_not_absence_of_record_and_not_false_success(self):
        log = journal(31, p=problem(2, 0), budget=145)
        self.assertEqual(log["summary"]["best_profit"], 0)
        self.assertEqual(log["summary"]["best_call"], 0)
        self.assertTrue(all(not row["success"] for row in log["generations"] if row["complete"]))
        self.assertEqual(log["generations"][-1]["controller_event"], "STAGNATION")

    def test_first_feasible_candidate_can_create_record_from_none(self):
        log = instructional(lambda item: item["summary"]["best_profit"] == 0,
                            profile=0, p=problem(2, 0), masks=["11"] * 30, budget=400)
        self.assertIsNone(log["generations"][0]["record_before"])
        self.assertGreater(log["summary"]["best_call"], 0)

    def test_final_query_record_survives_partial_generation(self):
        log = instructional(lambda item: item["summary"]["best_call"] == 1, profile=31, budget=1)
        self.assertGreater(log["summary"]["best_profit"], 0)
        self.assertEqual(log["summary"]["final_population"], list(range(30)))
        self.assertEqual(log["summary"]["final_parameters"], engine.default_parameters())

    def test_full_budget_baseline_and_joint_profile_have_exact_accounting(self):
        for profile in (0, 31):
            log = journal(profile, p=problem(2), masks=["11"] * 30, budget=5000)
            self.assertEqual(len(log["candidates"]), 5000)
            self.assertEqual(log["summary"]["new_calls"], 5000)
            self.assertEqual(log["summary"]["physical_evaluations"], 5000)
            self.assertEqual(log["summary"]["known_score_validation_evaluations"], 30)
            self.assertEqual(log["summary"]["duplicate_calls"], sum(child["duplicate"] for child in log["candidates"]))
            if profile == 0:
                self.assertEqual(log["summary"]["full_generations"], 172)
                self.assertEqual(log["summary"]["partial_children"], 12)

    def test_six_isolated_rngs_and_signal_do_not_consume_random_numbers(self):
        rngs = engine.make_rngs(7, 2, 1)
        for channel, name in enumerate(engine.CHANNELS):
            self.assertEqual(rngs[name].bit_generator.state, np.random.PCG64(np.random.SeedSequence([7, 2, 1, channel])).state)
        states = {name: copy.deepcopy(rng.bit_generator.state) for name, rng in rngs.items()}
        engine.novelty_statistics([0, 1, 2, 100])
        engine.update_parameters(engine.default_parameters(), 0, True, 29, Fraction(1, 2), 31)
        self.assertEqual(states, {name: rng.bit_generator.state for name, rng in rngs.items()})
        p = problem()
        masks = ["0" * 10] * 30
        scores = [engine.evaluate(p, mask) for mask in masks]
        rngs["ties"] = rngs["selection"]
        with self.assertRaises(ValueError):
            engine.run_search(p, masks, scores, 0, rngs, 1)

    def test_determinism_input_preservation_and_disjoint_observational_times(self):
        p, masks = problem(), ["0" * 10] * 30
        saved = copy.deepcopy((p, masks))
        first, second = journal(p=p, masks=masks, budget=400), journal(p=p, masks=masks, budget=400)
        self.assertEqual(semantic(first), semantic(second))
        self.assertEqual((p, masks), saved)
        self.assertEqual(set(first["timing_ns"]), set(engine.TIMING_COMPONENTS) | {"total"})
        self.assertTrue(all(type(value) is int and value >= 0 for value in first["timing_ns"].values()))
        self.assertGreaterEqual(first["timing_ns"]["total"], sum(first["timing_ns"][key] for key in engine.TIMING_COMPONENTS))

    def test_interface_rejects_oracles_bad_scores_invalid_profiles_and_local_search(self):
        self.assertEqual(tuple(inspect.signature(engine.run_search).parameters),
                         ("problem", "initial_masks", "initial_scores", "profile", "rngs", "budget"))
        p = problem()
        p["optimum"] = 123
        with self.assertRaises(ValueError):
            journal(p=p)
        p = problem()
        masks = ["0" * 10] * 30
        scores = [engine.evaluate(p, mask) for mask in masks]
        scores[0]["profit"] = 1
        with self.assertRaises(ValueError):
            engine.run_search(p, masks, scores, 0, engine.make_rngs(7, 0, 0), 1)
        for profile in (True, -1, 32, "p00"):
            with self.assertRaises(ValueError):
                journal(profile=profile, budget=1)
        with patch.dict(os.environ, {"GITHUB_ACTIONS": "false"}):
            with self.assertRaises(ValueError):
                journal(budget=1)


if __name__ == "__main__":
    unittest.main()
