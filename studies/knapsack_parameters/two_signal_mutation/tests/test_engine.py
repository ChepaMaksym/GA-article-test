"""CI-only instructional fixtures; no held-out data or scientific outcomes."""

from __future__ import annotations

import copy
from fractions import Fraction
import inspect
import itertools
import os
import unittest
from unittest.mock import patch

import numpy as np

from studies.adaptive_parameters.mutation_only import engine as historical
from studies.knapsack_parameters.two_signal_mutation import engine


def problem(n=10, capacity=None):
    return {"n": n, "weights": [1] * n, "profits": list(range(1, n + 1)),
            "capacity": n if capacity is None else capacity}


def journal(*, p=None, masks=None, method="two_signal", budget=61, seed=7, implementation=engine):
    p = problem() if p is None else p
    masks = ["0" * p["n"]] * 30 if masks is None else masks
    scores = [implementation.evaluate(p, mask) for mask in masks]
    return implementation.run_search(p, masks, scores, method,
                                     implementation.make_rngs(seed, 0, 0), budget=budget)


def semantic(log):
    result = copy.deepcopy(log)
    result.pop("timing_ns", None)
    return result


def historical_projection(log):
    result = semantic(log)
    result["schema"] = historical.SCHEMA
    for child in result["candidates"]:
        child.pop("parent_distance")
    for generation in result["generations"]:
        for field in ("parent_distances", "novelty_sum_numerator", "novelty_sum_denominator",
                      "novelty_mean_numerator", "novelty_mean_denominator", "gate_allows_increase"):
            generation.pop(field)
    return result


def fixture(predicate, **kwargs):
    # Bounded educational seeds, never selectors for scientific cases.
    for seed in range(128):
        result = journal(seed=seed, **kwargs)
        if predicate(result):
            return result
    raise AssertionError("No instructional fixture in the fixed seed range 0..127")


class TwoSignalEngineTests(unittest.TestCase):
    def test_exact_crossover_novelty_exhaustive_small_pairs(self):
        for n in range(2, 7):
            first = "0" * n
            for distance in range(n + 1):
                second = "1" * distance + "0" * (n - distance)
                novel = 0
                for choices in itertools.product((False, True), repeat=n):
                    child = "".join(first[i] if choices[i] else second[i] for i in range(n))
                    novel += int(child not in (first, second))
                self.assertEqual(Fraction(novel, 2 ** n), engine.novelty_probability(distance))

    def test_exact_statistics_mean_of_probabilities_not_mean_distance(self):
        stats = engine.novelty_statistics([0, 4])
        self.assertEqual(Fraction(stats["novelty_sum_numerator"], stats["novelty_sum_denominator"]),
                         Fraction(7, 8))
        self.assertEqual(Fraction(stats["novelty_mean_numerator"], stats["novelty_mean_denominator"]),
                         Fraction(7, 16))
        self.assertNotEqual(Fraction(7, 16), engine.novelty_probability(2))
        self.assertEqual(engine.novelty_probability(100), Fraction((1 << 99) - 1, 1 << 99))

    def test_gate_at_exact_half_and_above_without_tolerance(self):
        self.assertEqual(engine.update_mutation(100, 0.01, 4, False, "two_signal", Fraction(1, 2)),
                         (0.02, 0, "STAGNATION_DOUBLE"))
        just_above = Fraction(1, 2) + Fraction(1, 1 << 100)
        self.assertEqual(engine.update_mutation(100, 0.01, 4, False, "two_signal", just_above),
                         (0.01, 0, "GATE_DENIED"))

    def test_denial_resets_counter_and_next_opportunity_waits_five_generations(self):
        p, s, event = engine.update_mutation(100, 0.02, 4, False, "two_signal", Fraction(3, 4))
        self.assertEqual((p, s, event), (0.02, 0, "GATE_DENIED"))
        for next_s in range(1, 5):
            p, s, event = engine.update_mutation(100, p, s, False, "two_signal", Fraction(0))
            self.assertEqual((p, s, event), (0.02, next_s, "NO_CHANGE"))
        self.assertEqual(engine.update_mutation(100, p, s, False, "two_signal", Fraction(0)),
                         (0.04, 0, "STAGNATION_DOUBLE"))

    def test_success_preempts_gate_and_records_lower_bound_event(self):
        for mean in (Fraction(0), Fraction(1)):
            self.assertEqual(engine.update_mutation(100, 0.08, 4, True, "two_signal", mean),
                             (0.04, 0, "SUCCESS_HALVE"))
            self.assertEqual(engine.update_mutation(100, 0.01, 4, True, "two_signal", mean),
                             (0.01, 0, "SUCCESS_HALVE"))

    def test_allowed_upper_bound_event_and_denied_upper_bound_event(self):
        self.assertEqual(engine.update_mutation(100, 0.08, 4, False, "two_signal", Fraction(0)),
                         (0.08, 0, "STAGNATION_DOUBLE"))
        self.assertEqual(engine.update_mutation(100, 0.08, 4, False, "two_signal", Fraction(1)),
                         (0.08, 0, "GATE_DENIED"))

    def test_legacy_controller_paths_unchanged(self):
        for method, p, s, success in itertools.product(
                ("fixed", "adaptive_mutation"), (0.01, 0.02, 0.04, 0.08), range(5), (False, True)):
            with self.subTest(method=method, p=p, s=s, success=success):
                self.assertEqual(engine.update_mutation(100, p, s, success, method, Fraction(1)),
                                 historical.update_mutation(100, p, s, success, method))

    def test_same_rule_when_gate_always_allows(self):
        p_one = p_two = 0.01
        s_one = s_two = 0
        for step in range(50):
            success = step in (11, 27, 31)
            one = engine.update_mutation(100, p_one, s_one, success, "adaptive_mutation")
            two = engine.update_mutation(100, p_two, s_two, success, "two_signal", Fraction(step % 3, 4))
            self.assertEqual(one, two)
            p_one, s_one = one[:2]
            p_two, s_two = two[:2]

    def test_invalid_controller_and_signal_inputs(self):
        for args in ((100, 0.01, 5, False), (100, float("nan"), 0, False),
                     (100, True, 0, False), (1, 1, 0, False), (100, 0.01, True, False),
                     (100, 0.01, 0, 1), (100, 0.01, 0, False, "unknown")):
            with self.subTest(args=args), self.assertRaises(ValueError):
                engine.update_mutation(*args)
        for mean in (None, 0.5, True, Fraction(-1), Fraction(2)):
            with self.subTest(mean=mean), self.assertRaises(ValueError):
                engine.update_mutation(100, 0.01, 0, False, "two_signal", mean)
        for distance in (-1, True, 0.5):
            with self.assertRaises(ValueError):
                engine.novelty_probability(distance)
        with self.assertRaises(ValueError):
            engine.novelty_statistics([])

    def test_six_streams_registered_and_never_aliased(self):
        rngs = engine.make_rngs(7, 2, 1)
        self.assertEqual(len({id(rng) for rng in rngs.values()}), 6)
        for channel, name in enumerate(engine.CHANNELS):
            expected = np.random.PCG64(np.random.SeedSequence([7, 2, 1, channel])).state
            self.assertEqual(rngs[name].bit_generator.state, expected)
        p = problem()
        masks = ["0" * 10] * 30
        scores = [engine.evaluate(p, mask) for mask in masks]
        rngs["ties"] = rngs["selection"]
        with self.assertRaises(ValueError):
            engine.run_search(p, masks, scores, "fixed", rngs, 1)

    def test_fixed_and_one_signal_exact_historical_semantics_rng_and_order(self):
        for method in ("fixed", "adaptive_mutation"):
            with self.subTest(method=method):
                arguments = {"p": problem(100, 0), "method": method, "budget": 320}
                new = journal(**arguments)
                old = journal(**arguments, implementation=historical)
                self.assertEqual(historical_projection(new), old)

    def test_identical_first_generation_all_three_profiles(self):
        logs = [journal(method=method, budget=58) for method in engine.METHODS]
        for other in logs[1:]:
            self.assertEqual(logs[0]["rng_initial"], other["rng_initial"])
            self.assertEqual(logs[0]["candidates"][:29], other["candidates"][:29])
            for field in ("population_before", "population_after", "elite_index", "p_m",
                          "rng_before", "rng_after", "record_before", "record_after",
                          "parent_distances", "novelty_mean_numerator", "novelty_mean_denominator"):
                self.assertEqual(logs[0]["generations"][0][field], other["generations"][0][field])

    def test_all_pairs_in_signal_including_nonactivated_crossover(self):
        initial = ["10", "01"] * 15
        log = fixture(lambda item: any(not child["crossover"] for child in item["candidates"]),
                      p={"n": 2, "weights": [1, 1], "profits": [1, 1], "capacity": 2},
                      masks=initial, budget=29)
        generation = log["generations"][0]
        self.assertEqual(len(generation["parent_distances"]), 29)
        self.assertEqual(generation["parent_distances"],
                         [child["parent_distance"] for child in log["candidates"]])
        expected = sum((engine.novelty_probability(child["parent_distance"])
                        for child in log["candidates"]), Fraction(0)) / 29
        self.assertEqual(Fraction(generation["novelty_mean_numerator"],
                                  generation["novelty_mean_denominator"]), expected)

    def test_determinism_excludes_observational_timing_and_inputs_unmodified(self):
        p = problem()
        masks = ["0" * 10] * 30
        original = copy.deepcopy((p, masks))
        first, second = journal(p=p, masks=masks), journal(p=p, masks=masks)
        self.assertEqual(semantic(first), semantic(second))
        self.assertEqual((p, masks), original)
        self.assertEqual(set(first["timing_ns"]), set(engine.TIMING_COMPONENTS) | {"total"})
        self.assertTrue(all(type(value) is int and value >= 0 for value in first["timing_ns"].values()))
        self.assertGreaterEqual(first["timing_ns"]["total"],
                                sum(first["timing_ns"][name] for name in engine.TIMING_COMPONENTS))

    def test_always_allowed_small_problem_matches_one_signal_including_events(self):
        # For n=2 all possible distances are <=2, so the exact gate always allows.
        one = journal(p=problem(2), masks=["11"] * 30, method="adaptive_mutation", budget=174)
        two = journal(p=problem(2), masks=["11"] * 30, method="two_signal", budget=174)
        one = semantic(one)
        two = semantic(two)
        one["method"] = two["method"]
        self.assertEqual(one, two)

    def test_zero_record_and_infeasible_children_are_not_success(self):
        log = journal(p=problem(2, 0), budget=145)
        self.assertEqual(log["summary"]["best_profit"], 0)
        self.assertEqual(log["summary"]["best_call"], 0)
        self.assertEqual(log["generations"][0]["controller_event"], "NO_CHANGE")
        self.assertEqual(log["generations"][-1]["controller_event"], "STAGNATION_DOUBLE")

    def test_no_feasible_parent_record_then_first_feasible_is_success(self):
        log = fixture(lambda item: item["summary"]["best_profit"] == 0,
                      p=problem(2, 0), masks=["11"] * 30, budget=29)
        event = log["generations"][0]
        self.assertIsNone(event["record_before"])
        self.assertEqual(event["record_after"], 0)
        self.assertEqual(event["controller_event"], "SUCCESS_HALVE")

    def test_elite_and_all_worse_children_enter_new_population(self):
        log = fixture(lambda item: any(child["profit"] < 55 for child in item["candidates"]),
                      p=problem(), masks=["1" * 10] * 30, budget=29)
        event = log["generations"][0]
        self.assertEqual(event["population_after"], [event["elite_index"]] + list(range(30, 59)))
        self.assertEqual(log["summary"]["best_profit"], 55)

    def test_duplicates_count_as_physical_search_calls(self):
        log = journal(p=problem(2), masks=["11"] * 30, budget=61)
        self.assertGreater(log["summary"]["duplicate_calls"], 0)
        self.assertEqual(log["summary"]["physical_evaluations"], 61)
        self.assertEqual(log["summary"]["known_score_validation_evaluations"], 30)
        self.assertEqual(log["summary"]["duplicate_calls"],
                         sum(child["duplicate"] for child in log["candidates"]))

    def test_partial_has_no_gate_replacement_or_controller_update(self):
        log = journal(budget=61)
        event = log["generations"][-1]
        self.assertFalse(event["complete"])
        self.assertIsNone(event["gate_allows_increase"])
        self.assertEqual(len(event["parent_distances"]), 3)
        self.assertEqual(event["controller_event"], "PARTIAL_NO_UPDATE")
        self.assertEqual(event["population_before"], event["population_after"])
        self.assertEqual(event["p_m"], event["p_m_next"])
        self.assertEqual(event["stagnation_before"], event["stagnation_after"])

    def test_record_on_final_partial_call_is_not_lost(self):
        log = fixture(lambda item: item["summary"]["best_call"] == 1,
                      p=problem(2), budget=1)
        self.assertGreater(log["summary"]["best_profit"], 0)
        self.assertEqual(log["summary"]["final_population"], list(range(30)))
        self.assertEqual(log["generations"][0]["controller_event"], "PARTIAL_NO_UPDATE")

    def test_full_registered_budget_accounting_instructional_problem(self):
        log = journal(p=problem(2), masks=["11"] * 30, budget=5000, seed=11)
        self.assertEqual(log["summary"]["new_calls"], 5000)
        self.assertEqual(log["summary"]["full_generations"], 172)
        self.assertEqual(log["summary"]["partial_children"], 12)
        self.assertEqual(log["generations"][-1]["start_call"], 4989)
        self.assertEqual(len(log["candidates"]), 5000)

    def test_signature_rejects_oracle_wrong_scores_and_local_execution(self):
        self.assertEqual(tuple(inspect.signature(engine.run_search).parameters),
                         ("problem", "initial_masks", "initial_scores", "method", "rngs", "budget"))
        p = problem()
        p["optimum"] = 999
        with self.assertRaises(ValueError):
            journal(p=p)
        p = problem()
        scores = [engine.evaluate(p, "0" * 10) for _ in range(30)]
        scores[0]["profit"] = 1
        with self.assertRaises(ValueError):
            engine.run_search(p, ["0" * 10] * 30, scores, "fixed", engine.make_rngs(7, 0, 0), 1)
        with patch.dict(os.environ, {"GITHUB_ACTIONS": "false"}):
            with self.assertRaises(ValueError):
                journal(budget=1)


if __name__ == "__main__":
    unittest.main()
