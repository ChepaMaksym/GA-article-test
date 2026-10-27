"""Prospective CI fixtures; these definitions do not authorize any execution.

Only synthetic small inputs and the unchanged historical engine are used.
There are no KPLIB inputs, optimum queries or experiment seed selectors here.
"""
from __future__ import annotations

import copy
import inspect
import os
import unittest
from unittest.mock import patch

import numpy as np

from studies.knapsack_parameters.mutation_refinement import engine
from studies.knapsack_parameters.parameter_dynamics import engine as historical


def problem(n=10, capacity=None):
    return {"n": n, "weights": [1] * n, "profits": list(range(1, n + 1)),
            "capacity": n if capacity is None else capacity}


def journal(method="gentle", *, p=None, masks=None, budget=61, seed=7):
    p = problem() if p is None else p
    masks = ["0" * p["n"]] * 30 if masks is None else masks
    scores = [engine.evaluate(p, mask) for mask in masks]
    return engine.run_search(p, masks, scores, method, engine.make_rngs(seed, 0, 0), budget)


def semantic(log):
    value = copy.deepcopy(log)
    value.pop("timing_ns")
    return value


def historical_projection(log, profile):
    value = semantic(log)
    value["schema"] = historical.SCHEMA
    value.pop("method")
    value["profile"] = profile
    return value


def instructional(predicate, **kwargs):
    # Fixed, bounded educational fixtures; never scientific case selection.
    for seed in range(32):
        log = journal(seed=seed, **kwargs)
        if predicate(log):
            return log
    raise AssertionError("No instructional fixture in fixed seed range 0..31")


@unittest.skipUnless(os.environ.get("GITHUB_ACTIONS") == "true", "CI-only definitions require a separately approved run")
class MutationRefinementEngineTests(unittest.TestCase):
    def test_five_methods_and_all_other_parameters_frozen(self):
        self.assertEqual(engine.METHODS, ("fixed_0.005", "fixed_0.01", "fixed_0.02", "legacy", "gentle"))
        for method, probability in (("fixed_0.005", .005), ("fixed_0.01", .01),
                                    ("fixed_0.02", .02), ("legacy", .01), ("gentle", .01)):
            params = engine.default_parameters(method)
            self.assertEqual(params, {"p_m": probability, "p_c": .9, "target_mu": 30,
                                      "tournament_size": 2, "elite_count": 1})
            params["p_c"] = .8
            with self.assertRaises(ValueError):
                engine.update_parameters(params, 0, False, 29, method)
        mutable = engine.default_parameters()
        mutable["target_mu"] = 31
        self.assertEqual(engine.default_parameters()["target_mu"], 30)

    def test_success_divisor_stagnation_multiplier_and_exact_float_clipping(self):
        for method, lower, upper, factor in (("legacy", .01, .08, 2), ("gentle", .005, .02, 1.25)):
            params = engine.default_parameters(method)
            expected = .01
            for _ in range(10):
                expected = min(upper, expected * factor)
                result = engine.update_parameters(params, 116, False, 29, method)
                params = result["parameters"]
                self.assertEqual(params["p_m"], expected)
                self.assertEqual(result["event"], "STAGNATION")
                self.assertEqual(result["failed_queries_after"], 0)
            self.assertEqual(params["p_m"], upper)
            for _ in range(20):
                expected = max(lower, expected / factor)
                result = engine.update_parameters(params, 116, True, 29, method)
                params = result["parameters"]
                self.assertEqual(params["p_m"], expected)
                self.assertEqual(result["event"], "SUCCESS")
                self.assertEqual(result["failed_queries_after"], 0)
            self.assertEqual(params["p_m"], lower)

    def test_boundary_events_are_logged_even_when_probability_cannot_change(self):
        for method in ("legacy", "gentle"):
            lower, upper = engine.mutation_bounds(method)
            for probability, improved, event in ((lower, True, "SUCCESS"), (upper, False, "STAGNATION")):
                params = dict(engine.default_parameters(method), p_m=probability)
                result = engine.update_parameters(params, 116, improved, 29, method)
                mutation = result["parameter_events"][0]
                self.assertEqual(result["event"], event)
                self.assertEqual(mutation["before"], mutation["after"])
                self.assertEqual(mutation["direction"], "unchanged")
                self.assertTrue(mutation["enabled"])
                self.assertTrue(mutation["at_boundary"])
        for method in engine.FIXED_PROBABILITIES:
            params = engine.default_parameters(method)
            for success in (False, True):
                result = engine.update_parameters(params, 116, success, 29, method)
                self.assertEqual(result["parameters"], params)
                self.assertTrue(result["parameter_events"][0]["at_boundary"])
                self.assertTrue(all(not item["enabled"] for item in result["parameter_events"]))

    def test_threshold_is_failed_queries_of_whole_generations_and_resets(self):
        for method in engine.METHODS:
            params, count = engine.default_parameters(method), 0
            for generation in range(1, 6):
                result = engine.update_parameters(params, count, False, 29, method)
                count = result["failed_queries_after"]
                self.assertEqual(result["failed_queries_accumulated"], 29 * generation)
                self.assertEqual(count, 29 * generation if generation < 5 else 0)
                self.assertEqual(result["event"], "NO_CHANGE" if generation < 5 else "STAGNATION")
                self.assertEqual(result["stagnation_overshoot"], 0)
                params = result["parameters"]
            self.assertEqual(engine.update_parameters(params, 0, False, 29, method)["failed_queries_after"], 29)

    def test_exact_threshold_and_success_priority_with_no_tolerance(self):
        params = engine.default_parameters("gentle")
        just_below = engine.update_parameters(params, 115, False, 29, "gentle")
        self.assertEqual((just_below["event"], just_below["failed_queries_after"]), ("NO_CHANGE", 144))
        threshold = engine.update_parameters(params, 116, False, 29, "gentle")
        self.assertEqual((threshold["event"], threshold["failed_queries_after"]), ("STAGNATION", 0))
        self.assertEqual(threshold["parameters"]["p_m"], .01 * 1.25)
        priority = engine.update_parameters(params, 144, True, 29, "gentle")
        self.assertEqual(priority["event"], "SUCCESS")
        self.assertEqual(priority["failed_queries_accumulated"], 0)
        self.assertEqual(priority["failed_queries_after"], 0)
        self.assertEqual(priority["stagnation_overshoot"], 0)
        self.assertEqual(priority["parameters"]["p_m"], .01 / 1.25)

    def test_invalid_controller_states_and_unregistered_construction_rejected(self):
        params = engine.default_parameters("gentle")
        for count, success, calls in ((145, False, 29), (-1, False, 29), (True, False, 29),
                                       (0, 1, 29), (0, False, 28), (0, False, 30), (0, False, True)):
            with self.subTest(count=count, success=success, calls=calls), self.assertRaises(ValueError):
                engine.update_parameters(params, count, success, calls, "gentle")
        for name, value in (("p_m", float("nan")), ("p_m", True), ("p_m", .004999999999999999),
                            ("p_m", .020000000000000004), ("p_c", True), ("target_mu", 31),
                            ("tournament_size", 3), ("elite_count", 2)):
            with self.subTest(name=name, value=value), self.assertRaises(ValueError):
                engine.update_parameters(dict(params, **{name: value}), 0, True, 29, "gentle")
        with self.assertRaises(ValueError):
            engine.update_parameters(dict(engine.default_parameters(), p_m=.02), 0, False, 29, "fixed_0.01")
        for method in (True, None, 1, "fixed", "adaptive_mutation", "gentle_tuned"):
            with self.assertRaises(ValueError):
                engine.default_parameters(method)

    def test_first_generation_same_source_for_all_and_identical_one_percent_starts(self):
        logs = {method: journal(method, budget=29) for method in engine.METHODS}
        fixed = logs["fixed_0.01"]
        for other in logs.values():
            self.assertEqual(other["rng_initial"], fixed["rng_initial"])
            self.assertEqual(other["generations"][0]["rng_after"], fixed["generations"][0]["rng_after"])
            for first, second in zip(other["candidates"], fixed["candidates"]):
                for field in ("tournaments", "parent_indices", "parent_distance", "crossover", "pre_mask"):
                    self.assertEqual(first[field], second[field])
        for method in ("legacy", "gentle"):
            self.assertEqual(logs[method]["candidates"], fixed["candidates"])
            for field in ("parameters_before", "population_before", "population_after", "elite_indices",
                          "elite_references", "actual_parent_mu", "parent_distances", "rng_before", "rng_after"):
                self.assertEqual(logs[method]["generations"][0][field], fixed["generations"][0][field])

    def test_fixed_one_percent_and_legacy_exact_historical_candidates_decisions_rng(self):
        p = problem(100, 50)
        masks = ["0" * 100] + [format(index, "0100b") for index in range(1, 30)]
        scores = [engine.evaluate(p, mask) for mask in masks]
        for method, profile in (("fixed_0.01", 0), ("legacy", 1)):
            with self.subTest(method=method):
                new = engine.run_search(p, masks, scores, method, engine.make_rngs(19, 2, 1))
                old = historical.run_search(p, masks, scores, profile, historical.make_rngs(19, 2, 1))
                self.assertEqual(historical_projection(new, profile), semantic(old))

    def test_six_stream_identity_is_method_independent_and_channels_cannot_alias(self):
        rngs = engine.make_rngs(7, 2, 1)
        for channel, name in enumerate(engine.CHANNELS):
            expected = np.random.PCG64(np.random.SeedSequence([7, 2, 1, channel])).state
            self.assertEqual(rngs[name].bit_generator.state, expected)
        states = {name: copy.deepcopy(rng.bit_generator.state) for name, rng in rngs.items()}
        engine.novelty_statistics([0, 1, 2, 100])
        for method in engine.METHODS:
            engine.update_parameters(engine.default_parameters(method), 116, False, 29, method)
        self.assertEqual(states, {name: rng.bit_generator.state for name, rng in rngs.items()})
        p = problem()
        masks = ["0" * 10] * 30
        scores = [engine.evaluate(p, mask) for mask in masks]
        rngs["ties"] = rngs["selection"]
        with self.assertRaises(ValueError):
            engine.run_search(p, masks, scores, "gentle", rngs, 1)
        rngs = engine.make_rngs(7, 2, 1)
        rngs["ties"] = np.random.Generator(np.random.MT19937(1))
        with self.assertRaises(ValueError):
            engine.run_search(p, masks, scores, "gentle", rngs, 1)

    def test_record_success_changes_mutation_only_in_next_generation(self):
        log = instructional(lambda item: item["generations"][0]["success"], budget=58)
        first, second = log["generations"]
        self.assertEqual(first["parameters_before"]["p_m"], .01)
        self.assertEqual(first["parameters_after"]["p_m"], .01 / 1.25)
        self.assertEqual(second["parameters_before"], first["parameters_after"])
        for generation in log["generations"]:
            self.assertEqual(generation["population_after"], generation["elite_references"] +
                             list(range(30 + generation["start_call"] - 1, 30 + generation["end_call"])))
            self.assertEqual(len(generation["population_after"]), 30)

    def test_zero_record_is_present_and_stagnation_waits_five_complete_generations(self):
        log = journal(p=problem(2, 0), budget=146)
        self.assertEqual(log["summary"]["best_profit"], 0)
        self.assertEqual(log["summary"]["best_call"], 0)
        self.assertEqual([row["controller_event"] for row in log["generations"]],
                         ["NO_CHANGE"] * 4 + ["STAGNATION", "PARTIAL_NO_UPDATE"])
        self.assertTrue(all(row["success"] is False for row in log["generations"][:5]))
        fifth, sixth = log["generations"][4:]
        self.assertEqual(fifth["failed_queries_accumulated"], 145)
        self.assertEqual(fifth["failed_queries_after"], 0)
        self.assertEqual(sixth["parameters_before"]["p_m"], .01 * 1.25)

    def test_partial_generation_retains_only_record_and_no_population_or_controller_commit(self):
        for method in engine.METHODS:
            log = journal(method, budget=61)
            row = log["generations"][-1]
            self.assertFalse(row["complete"])
            self.assertIsNone(row["success"])
            self.assertIsNone(row["stagnation_overshoot"])
            self.assertEqual(row["controller_event"], "PARTIAL_NO_UPDATE")
            self.assertEqual(row["parameter_events"], [])
            self.assertEqual(row["population_before"], row["population_after"])
            self.assertEqual(row["parameters_before"], row["parameters_after"])
            self.assertEqual(row["failed_queries_before"], row["failed_queries_after"])
            self.assertEqual(len(row["parent_distances"]), 3)
        final_record = instructional(lambda item: item["summary"]["best_call"] == 1, p=problem(100), budget=1)
        self.assertGreater(final_record["summary"]["best_profit"], 0)
        self.assertEqual(final_record["summary"]["final_population"], list(range(30)))
        self.assertEqual(final_record["summary"]["final_parameters"], engine.default_parameters("gentle"))

    def test_absent_initial_record_can_be_created_by_first_feasible_query(self):
        log = instructional(lambda item: item["summary"]["best_profit"] == 0,
                            p=problem(2, 0), masks=["11"] * 30, budget=406)
        self.assertIsNone(log["generations"][0]["record_before"])
        self.assertGreater(log["summary"]["best_call"], 0)
        self.assertTrue(any(row["controller_event"] == "SUCCESS" for row in log["generations"]))

    def test_all_children_enter_completed_population_even_if_infeasible_or_worse(self):
        log = journal(p=problem(2, 0), masks=["11"] * 30, budget=29)
        row = log["generations"][0]
        self.assertEqual(row["population_after"], row["elite_references"] + list(range(30, 59)))
        self.assertTrue(any(not child["feasible"] for child in log["candidates"]))
        worse = instructional(lambda item: any(child["profit"] < 55 for child in item["candidates"]),
                              p=problem(), masks=["1" * 10] * 30, budget=29)
        self.assertEqual(worse["summary"]["best_profit"], 55)
        self.assertEqual(len(worse["generations"][0]["population_after"]), 30)

    def test_duplicate_queries_are_uncached_and_full_budget_has_twelve_terminal_children(self):
        log = journal(p=problem(2), masks=["11"] * 30)
        self.assertGreater(log["summary"]["duplicate_calls"], 0)
        self.assertEqual(log["summary"]["duplicate_calls"], sum(child["duplicate"] for child in log["candidates"]))
        full = journal(p=problem(2), masks=["11"] * 30, budget=5000)
        self.assertEqual(len(full["candidates"]), 5000)
        for field in ("new_calls", "physical_evaluations"):
            self.assertEqual(full["summary"][field], 5000)
        self.assertEqual(full["summary"]["known_score_validation_evaluations"], 30)
        self.assertEqual(full["summary"]["full_generations"], 172)
        self.assertEqual(full["summary"]["partial_children"], 12)
        self.assertEqual(full["generations"][-1]["start_call"], 4989)
        self.assertEqual(full["generations"][-1]["population_before"], full["generations"][-1]["population_after"])

    def test_tournament_repeated_occurrences_and_literal_operator_trace(self):
        log = journal(budget=400)
        self.assertTrue(any(len(set(entries)) < len(entries) for child in log["candidates"]
                            for entries in child["tournaments"]))
        for child in log["candidates"]:
            for winner, entries in zip(child["parent_indices"], child["tournaments"]):
                self.assertEqual(len(entries), 2)
                self.assertIn(winner, entries)
            bits = list(child["pre_mask"])
            for index in child["mutation_bits"]:
                bits[index] = "0" if bits[index] == "1" else "1"
            self.assertEqual("".join(bits), child["mask"])
        for row in log["generations"]:
            children = log["candidates"][row["start_call"] - 1:row["end_call"]]
            self.assertEqual(row["parent_distances"], [child["parent_distance"] for child in children])

    def test_feasibility_precedes_profit_and_infeasible_order_is_capacity_excess(self):
        self.assertGreater(engine._key({"weight": 0, "profit": 0, "feasible": True}, 5),
                           engine._key({"weight": 6, "profit": 999, "feasible": False}, 5))
        self.assertGreater(engine._key({"weight": 6, "profit": 1, "feasible": False}, 5),
                           engine._key({"weight": 7, "profit": 999, "feasible": False}, 5))
        self.assertEqual(engine._key({"weight": 6, "profit": 1, "feasible": False}, 5),
                         engine._key({"weight": 6, "profit": 999, "feasible": False}, 5))

    def test_known_inputs_preserved_and_only_timing_is_observational(self):
        p, masks = problem(), ["0" * 10] * 30
        original = copy.deepcopy((p, masks))
        first, second = journal(p=p, masks=masks), journal(p=p, masks=masks)
        self.assertEqual((p, masks), original)
        self.assertEqual(semantic(first), semantic(second))
        self.assertEqual(set(first["timing_ns"]), set(engine.TIMING_COMPONENTS) | {"total"})
        self.assertTrue(all(type(value) is int and value >= 0 for value in first["timing_ns"].values()))
        self.assertGreaterEqual(first["timing_ns"]["total"],
                                sum(first["timing_ns"][name] for name in engine.TIMING_COMPONENTS))

    def test_search_signature_exposes_no_oracle_and_extra_metadata_is_rejected(self):
        self.assertEqual(tuple(inspect.signature(engine.run_search).parameters),
                         ("problem", "initial_masks", "initial_scores", "method", "rngs", "budget"))
        clean, masks = problem(), ["0" * 10] * 30
        scores = [engine.evaluate(clean, mask) for mask in masks]
        for field in ("optimum", "OPT", "witness", "certificate", "oracle", "neighbors"):
            p = dict(problem(), **{field: 999})
            with self.subTest(field=field), self.assertRaises(ValueError):
                engine.run_search(p, masks, scores, "gentle", engine.make_rngs(7, 0, 0), 1)
        for method in (True, None, 0, "fixed", "gentle_tuned"):
            with self.subTest(method=method), self.assertRaises(ValueError):
                engine.run_search(clean, masks, scores, method, engine.make_rngs(7, 0, 0), 1)
        p, masks = problem(), ["0" * 10] * 30
        scores = [engine.evaluate(p, mask) for mask in masks]
        scores[0]["profit"] = 1
        with self.assertRaises(ValueError):
            engine.run_search(p, masks, scores, "gentle", engine.make_rngs(7, 0, 0), 1)
        for budget in (True, 0, -1, 5001, 1.5):
            with self.subTest(budget=budget), self.assertRaises(ValueError):
                journal(budget=budget)

    def test_evaluation_and_search_reject_local_execution_before_any_evaluation(self):
        p, masks = problem(), ["0" * 10] * 30
        scores = [{"weight": 0, "profit": 0, "feasible": True} for _ in masks]
        with patch.dict(os.environ, {"GITHUB_ACTIONS": "false"}):
            with self.assertRaises(ValueError):
                engine.evaluate(p, masks[0])
            with patch.object(engine, "_evaluate", side_effect=AssertionError("Local evaluation forbidden")):
                with self.assertRaises(ValueError):
                    engine.run_search(p, masks, scores, "gentle", engine.make_rngs(7, 0, 0), 1)


if __name__ == "__main__":
    unittest.main()
