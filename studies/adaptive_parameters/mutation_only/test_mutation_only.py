"""CI-only instructional fixtures, not scientific seeds or effect estimates."""
from __future__ import annotations

import copy
import inspect
import itertools
import math
import os
import unittest
from unittest.mock import patch

import numpy as np

from studies.adaptive_parameters.mutation_only import engine, verifier


def problem(n=10, capacity=None):
    return {"n": n, "weights": [1] * n, "profits": list(range(1, n + 1)),
            "capacity": n if capacity is None else capacity}


def journal(*, p=None, masks=None, method="adaptive_mutation", budget=61, seed=7):
    p = problem() if p is None else p
    masks = ["0" * p["n"]] * 30 if masks is None else masks
    scores = [engine.evaluate(p, mask) for mask in masks]
    return engine.run_search(p, masks, scores, method, engine.make_rngs(seed, 0, 0), budget=budget)


def find_fixture(predicate, **kwargs):
    """Bounded deterministic selection of a tiny teaching fixture in CI only."""
    for seed in range(128):
        result = journal(seed=seed, **kwargs)
        if predicate(result):
            return result
    raise AssertionError("No teaching fixture in the fixed 0..127 seed range")


class MutationOnlyTests(unittest.TestCase):
    def assertVerified(self, log):
        result = verifier.verify_log(log)
        self.assertEqual(result["verification_status"], "VERIFIED")
        self.assertEqual(result["independent_score_checks"], 30 + log["budget"])
        self.assertEqual(result["summary"], log["summary"])
        return result

    def test_five_failures_and_success_reset(self):
        p, s = 0.01, 0
        for expected_s in range(1, 5):
            p, s, event = engine.update_mutation(100, p, s, False)
            self.assertEqual((p, s, event), (0.01, expected_s, "NO_CHANGE"))
        p, s, event = engine.update_mutation(100, p, s, False)
        self.assertEqual((p, s, event), (0.02, 0, "STAGNATION_DOUBLE"))
        self.assertEqual(engine.update_mutation(100, p, 3, True), (0.01, 0, "SUCCESS_HALVE"))
        self.assertEqual(engine.update_mutation(100, 0.01, 4, True), (0.01, 0, "SUCCESS_HALVE"))

    def test_repeated_cycles_and_upper_bound_event(self):
        p, s = 0.01, 0
        for expected_p in (0.02, 0.04, 0.08, 0.08):
            for _ in range(5):
                p, s, event = engine.update_mutation(100, p, s, False)
            self.assertEqual((p, s, event), (expected_p, 0, "STAGNATION_DOUBLE"))
        self.assertEqual(engine.update_mutation(100, p, 4, True), (0.04, 0, "SUCCESS_HALVE"))

    def test_small_n_clipping_is_not_assumed_power_of_two(self):
        self.assertEqual(engine.update_mutation(10, 0.4, 4, False), (0.5, 0, "STAGNATION_DOUBLE"))
        self.assertEqual(engine.update_mutation(10, 0.5, 2, True), (0.25, 0, "SUCCESS_HALVE"))
        self.assertEqual(engine.update_mutation(2, 0.5, 4, False), (0.5, 0, "STAGNATION_DOUBLE"))

    def test_fixed_controller_and_invalid_states(self):
        self.assertEqual(engine.update_mutation(100, 0.08, 4, False, "fixed"), (0.01, 0, "FIXED"))
        for args in ((1, 1, 0, False), (100, float("nan"), 0, False),
                     (100, 0.001, 0, False), (100, 0.09, 0, False),
                     (100, True, 0, False), (100, 0.01, 5, False),
                     (100, 0.01, True, False), (100, 0.01, 0, 1)):
            with self.subTest(args=args), self.assertRaises(ValueError):
                engine.update_mutation(*args)
        with self.assertRaises(ValueError):
            engine.update_mutation(100, 0.01, 0, False, "unknown")

    def test_streams_match_registered_seed_sequence(self):
        rngs = engine.make_rngs(7, 2, 1)
        self.assertEqual(len({id(rng) for rng in rngs.values()}), 6)
        for channel, name in enumerate(engine.CHANNELS):
            expected = np.random.PCG64(np.random.SeedSequence([7, 2, 1, channel])).state
            self.assertEqual(rngs[name].bit_generator.state, expected)

    def test_empty_set_is_feasible_and_zero_is_a_real_record(self):
        p = problem(2, 0)
        self.assertEqual(engine.evaluate(p, "00"), {"weight": 0, "profit": 0, "feasible": True})
        log = journal(p=p, budget=29)
        self.assertEqual(log["generations"][0]["record_before"], 0)
        self.assertEqual(log["generations"][0]["record_after"], 0)
        self.assertEqual(log["generations"][0]["controller_event"], "NO_CHANGE")
        self.assertEqual(log["summary"]["best_call"], 0)
        self.assertVerified(log)

    def test_first_feasible_record_triggers_success(self):
        p = problem(2, 0)
        log = find_fixture(lambda item: item["summary"]["best_profit"] == 0,
                           p=p, masks=["11"] * 30, budget=29)
        generation = log["generations"][0]
        self.assertIsNone(generation["record_before"])
        self.assertEqual(generation["record_after"], 0)
        self.assertEqual(generation["controller_event"], "SUCCESS_HALVE")
        self.assertGreater(log["summary"]["best_call"], 0)
        self.assertVerified(log)

    def test_infeasible_changes_are_not_controller_success(self):
        p = problem(100, 0)
        log = find_fixture(lambda item: item["summary"]["best_profit"] is None,
                           p=p, masks=["1" * 100] * 30, budget=29)
        generation = log["generations"][0]
        self.assertIsNone(log["summary"]["best_mask"])
        self.assertIsNone(log["summary"]["best_call"])
        self.assertEqual(generation["controller_event"], "NO_CHANGE")
        self.assertEqual(generation["stagnation_after"], 1)
        self.assertVerified(log)

    def test_same_first_generation_with_isolated_method_rngs(self):
        fixed = journal(method="fixed", budget=58)
        adaptive = journal(method="adaptive_mutation", budget=58)
        self.assertEqual(fixed["rng_initial"], adaptive["rng_initial"])
        self.assertEqual(fixed["candidates"][:29], adaptive["candidates"][:29])
        for field in ("population_before", "population_after", "elite_index", "p_m",
                      "rng_before", "rng_after", "record_before", "record_after"):
            self.assertEqual(fixed["generations"][0][field], adaptive["generations"][0][field])
        self.assertVerified(fixed)
        self.assertVerified(adaptive)

    def test_determinism_and_journal_does_not_alias_inputs(self):
        p = problem()
        masks = ["0" * 10] * 30
        original = copy.deepcopy((p, masks))
        first = journal(p=p, masks=masks)
        second = journal(p=p, masks=masks)
        self.assertEqual(first, second)
        self.assertEqual((p, masks), original)
        first["generations"][0]["population_before"][0] = 999
        self.assertNotEqual(first["generations"][1]["population_before"][0], 999)
        self.assertVerified(second)

    def test_duplicates_are_evaluated_and_counted(self):
        log = find_fixture(lambda item: item["summary"]["duplicate_calls"] > 0,
                           p=problem(2), budget=29)
        self.assertEqual(log["summary"]["new_calls"], 29)
        self.assertEqual(log["summary"]["physical_evaluations"], 29)
        self.assertEqual(log["summary"]["duplicate_calls"],
                         sum(child["duplicate"] for child in log["candidates"]))
        self.assertVerified(log)

    def test_elite_preserved_and_worse_children_not_rejected(self):
        p = problem()
        initial = ["1" * 10] * 30
        log = find_fixture(lambda item: any(c["profit"] < 55 for c in item["candidates"]),
                           p=p, masks=initial, budget=29)
        event = log["generations"][0]
        expected_refs = [event["elite_index"]] + list(range(30, 59))
        self.assertEqual(event["population_after"], expected_refs)
        self.assertEqual(len(event["population_after"]), 30)
        self.assertEqual(log["summary"]["best_profit"], 55)
        self.assertVerified(log)

    def test_partial_generation_has_no_replacement_or_update(self):
        log = journal(budget=61)
        event = log["generations"][-1]
        self.assertFalse(event["complete"])
        self.assertEqual(event["end_call"] - event["start_call"] + 1, 3)
        self.assertEqual(event["population_after"], event["population_before"])
        self.assertEqual(event["p_m_next"], event["p_m"])
        self.assertEqual(event["stagnation_after"], event["stagnation_before"])
        self.assertEqual(event["controller_event"], "PARTIAL_NO_UPDATE")
        self.assertVerified(log)

    def test_improvement_on_final_call_is_recorded_without_partial_update(self):
        log = find_fixture(lambda item: item["summary"]["best_call"] == 1,
                           p=problem(2), budget=1)
        self.assertGreater(log["summary"]["best_profit"], 0)
        self.assertEqual(log["summary"]["final_population"], list(range(30)))
        self.assertEqual(log["generations"][0]["controller_event"], "PARTIAL_NO_UPDATE")
        self.assertVerified(log)

    def test_full_registered_budget_on_one_instructional_problem(self):
        log = journal(p=problem(2), masks=["11"] * 30, budget=5000, seed=11)
        result = self.assertVerified(log)
        self.assertEqual(result["completed_generations"], 172)
        self.assertEqual(log["summary"]["partial_children"], 12)
        self.assertEqual(log["summary"]["best_call"], 0)
        self.assertEqual(len(log["summary"]["final_population"]), 30)
        self.assertEqual(log["generations"][-1]["start_call"], 4989)

    def test_tournaments_and_population_refs_stay_in_previous_generation(self):
        log = journal(budget=60)
        for generation in log["generations"]:
            refs = generation["population_before"]
            self.assertEqual(len(refs), 30)
            keys = []
            for ref in refs:
                score = log["initial_scores"][ref] if ref < 30 else log["candidates"][ref - 30]
                keys.append((1, score["profit"]) if score["feasible"]
                            else (0, log["problem"]["capacity"] - score["weight"]))
            for child in log["candidates"][generation["start_call"] - 1:generation["end_call"]]:
                for pair, parent in zip(child["tournaments"], child["parent_indices"], strict=True):
                    self.assertEqual(len(pair), 2)
                    self.assertTrue(all(0 <= i < 30 for i in pair))
                    self.assertIn(parent, pair)
                    self.assertEqual(keys[parent], max(keys[i] for i in pair))
        self.assertVerified(log)

    def test_infeasible_ties_ignore_profit_and_less_excess_wins(self):
        initial = ["10", "01"] * 15
        for weights in ([1, 1], [2, 1]):
            with self.subTest(weights=weights):
                p = {"n": 2, "weights": weights, "profits": [100, 1], "capacity": 0}
                log = journal(p=p, masks=initial, budget=29)
                mixed_tournaments = 0
                for child in log["candidates"]:
                    for pair, parent in zip(child["tournaments"], child["parent_indices"], strict=True):
                        if initial[pair[0]] != initial[pair[1]]:
                            mixed_tournaments += 1
                            if weights[0] > weights[1]:
                                self.assertEqual(initial[parent], "01")
                self.assertGreater(mixed_tournaments, 0)
                # In the equal-weight case, independent replay must consume a
                # random tie draw, not silently prefer the 100-profit parent.
                self.assertVerified(log)

    def test_input_validation_and_no_oracle_parameter(self):
        self.assertEqual(tuple(inspect.signature(engine.run_search).parameters),
                         ("problem", "initial_masks", "initial_scores", "method", "rngs", "budget"))
        p = problem()
        p["optimum"] = 999
        with self.assertRaises(ValueError):
            journal(p=p)
        p = problem()
        bad_scores = [engine.evaluate(p, "0" * 10) for _ in range(30)]
        bad_scores[0]["profit"] = 1
        with self.assertRaises(ValueError):
            engine.run_search(p, ["0" * 10] * 30, bad_scores, "fixed", engine.make_rngs(7, 0, 0), 1)

    def test_guards_refuse_local_search_and_wrong_verifier_identity(self):
        with patch.dict(os.environ, {"GITHUB_ACTIONS": "false"}):
            with self.assertRaises(ValueError):
                journal(budget=1)
            with self.assertRaises(ValueError):
                verifier.verify_log({})
        log = journal(budget=1)
        for field, value in (("GITHUB_REPOSITORY", "someone/other"),
                             ("GITHUB_REF", "refs/heads/main")):
            with patch.dict(os.environ, {field: value}), self.assertRaises(ValueError):
                verifier.verify_log(log)

    def test_independent_verifier_never_calls_engine_evaluator_or_controller(self):
        log = journal()
        with patch.object(engine, "evaluate", side_effect=AssertionError("production evaluate used")), \
                patch.object(engine, "update_mutation", side_effect=AssertionError("production update used")), \
                patch.object(engine, "run_search", side_effect=AssertionError("production replay used")):
            self.assertVerified(log)

    def test_corrupted_operator_score_controller_rng_and_accounting_rejected(self):
        original = journal()
        changes = {
            "profit": lambda x: x["candidates"][0].__setitem__("profit", x["candidates"][0]["profit"] + 1),
            "feasible_type": lambda x: x["candidates"][0].__setitem__("feasible", 1),
            "pre_mask": lambda x: x["candidates"][0].__setitem__("pre_mask", "1" * 10),
            "mutation_bits": lambda x: x["candidates"][0].__setitem__("mutation_bits", [-1]),
            "parent": lambda x: x["candidates"][0]["parent_indices"].__setitem__(0, 30),
            "tournament": lambda x: x["candidates"][0]["tournaments"][0].__setitem__(0, -1),
            "branch": lambda x: x["candidates"][0].__setitem__("crossover", not x["candidates"][0]["crossover"]),
            "duplicate": lambda x: x["candidates"][0].__setitem__("duplicate", not x["candidates"][0]["duplicate"]),
            "record": lambda x: x["candidates"][0].__setitem__("record_call", 999),
            "controller": lambda x: x["generations"][0].__setitem__("controller_event", "FIXED"),
            "probability": lambda x: x["generations"][0].__setitem__("p_m_next", 0.5),
            "counter": lambda x: x["generations"][0].__setitem__("stagnation_after", 5),
            "population": lambda x: x["generations"][0]["population_after"].pop(),
            "before_record": lambda x: x["generations"][0].__setitem__("record_before", None),
            "partial": lambda x: x["generations"][-1].__setitem__("complete", True),
            "rng": lambda x: x["rng_final"]["mutation"]["state"].__setitem__(
                "state", x["rng_final"]["mutation"]["state"]["state"] ^ 1),
            "generation_rng": lambda x: x["generations"][0]["rng_before"]["ties"]["state"].__setitem__(
                "state", x["generations"][0]["rng_before"]["ties"]["state"]["state"] ^ 1),
            "missing_child": lambda x: x["candidates"].pop(),
            "missing_generation": lambda x: x["generations"].pop(),
            "summary": lambda x: x["summary"].__setitem__("physical_evaluations", 0),
            "oracle": lambda x: x["problem"].__setitem__("optimum", 55),
        }
        for label, change in changes.items():
            with self.subTest(label=label):
                corrupted = copy.deepcopy(original)
                change(corrupted)
                with self.assertRaises(ValueError):
                    verifier.verify_log(corrupted)

    def test_instructional_target_probability_and_mutation_mass(self):
        n, p, r = 4, 0.5, 2
        self.assertEqual(p ** r * (1 - p) ** (n - r), 1 / 16)
        self.assertEqual(sum(math.comb(n, k) * p ** k * (1 - p) ** (n - k)
                             for k in range(n + 1)), 1)
        self.assertEqual(sum(k * math.comb(n, k) * p ** k * (1 - p) ** (n - k)
                             for k in range(n + 1)), n * p)

    def test_instructional_same_distance_different_crossover_usefulness(self):
        p = {"n": 4, "weights": [2, 2, 1, 1], "profits": [2, 2, 2, 2], "capacity": 2}
        probabilities = []
        for first, second in (("1000", "0100"), ("0010", "0001")):
            different = [i for i in range(4) if first[i] != second[i]]
            self.assertEqual(len(different), 2)
            useful = novel = 0
            for choices in itertools.product((False, True), repeat=2):
                child = list(first)
                for index, use_first in zip(different, choices, strict=True):
                    child[index] = first[index] if use_first else second[index]
                mask = "".join(child)
                score = engine.evaluate(p, mask)
                useful += int(score["feasible"] and score["profit"] > 2)
                novel += int(mask != first and mask != second)
            self.assertEqual(novel / 4, 1 - 2 ** (1 - len(different)))
            probabilities.append(useful / 4)
        self.assertEqual(probabilities, [0, 0.25])


if __name__ == "__main__":
    unittest.main()
