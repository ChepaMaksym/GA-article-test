"""Prospective software-check definitions; no execution budget is granted.

Fixtures are instructional data, never cohort inputs or scientific outcomes.
These checks may be run only after separate technical authorization in CI.
"""
from __future__ import annotations

from copy import deepcopy
from fractions import Fraction
import inspect
import itertools
import math
import os
import unittest
from unittest.mock import patch

from studies.knapsack_parameters.mutation_refinement import engine
from studies.knapsack_parameters.mutation_refinement import verifier as v


METHODS = ("fixed_0.005", "fixed_0.01", "fixed_0.02", "legacy", "gentle")


def _score(problem, mask):
    positions = [index for index, bit in enumerate(mask) if bit == "1"]
    weight = sum(problem["weights"][index] for index in positions)
    profit = sum(problem["profits"][index] for index in positions)
    return {"weight": weight, "profit": profit, "feasible": weight <= problem["capacity"]}


def _fixture(method="gentle", budget=61, seed=37001, *, problem=None, masks=None):
    problem = ({"n": 4, "weights": [1] * 4, "profits": [1, 2, 3, 4], "capacity": 2}
               if problem is None else problem)
    masks = (["0000", "1000", "0100", "0010", "0001", "1100"] * 5
             if masks is None else masks)
    return engine.run_search(problem, masks, [_score(problem, mask) for mask in masks],
                             method, engine.make_rngs(seed, 0, 0), budget=budget)


def _flat(method="gentle", budget=150):
    return _fixture(method, budget, problem={"n": 2, "weights": [1, 1],
                    "profits": [1, 1], "capacity": 0}, masks=["00"] * 30)


def _successful_prefix(method="gentle", *, initial_feasible=True):
    problem = {"n": 100, "weights": [1] * 100,
               "profits": list(range(1, 101)), "capacity": 100 if initial_feasible else 99}
    initial_mask = ("0" if initial_feasible else "1") * 100
    # A bounded instructional fixture selector, never a search over study
    # tasks, scientific seeds, methods, or favourable experimental outcomes.
    for seed in range(128):
        log = _fixture(method, 1, seed, problem=problem, masks=[initial_mask] * 30)
        if log["summary"]["best_call"] == 1:
            return log
    raise AssertionError("No one-query educational record in seeds 0 through 127")


def _parameters(p_m=0.01):
    return {"p_m": p_m, "p_c": 0.9, "target_mu": 30,
            "tournament_size": 2, "elite_count": 1}


class MutationRefinementVerifierTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if os.environ.get("GITHUB_ACTIONS") != "true":
            raise RuntimeError("Prospective software checks require separately authorized CI")

    def assertVerified(self, log):
        receipt = v.verify_log(log)
        self.assertEqual(receipt["verification_status"], "VERIFIED")
        self.assertEqual(receipt["new_calls"], log["budget"])
        self.assertEqual(receipt["independent_score_checks"], 30 + 2 * log["budget"])
        self.assertEqual(receipt["initial_score_checks"], 30)
        self.assertEqual(receipt["final_score_checks"], log["budget"])
        self.assertEqual(receipt["premutation_score_checks"], log["budget"])
        self.assertEqual(receipt["summary"], log["summary"])
        return receipt

    def test_all_five_registered_methods_are_independently_reconstructed(self):
        for method in METHODS:
            with self.subTest(method=method):
                receipt = self.assertVerified(_fixture(method))
                self.assertEqual(receipt["completed_generations"], 2)
                self.assertEqual(receipt["partial_generations"], 1)
                self.assertEqual(len(receipt["derived_metrics"]["candidate_metrics"]), 61)
                self.assertEqual(len(receipt["final_population_refs"]), 30)

    def test_equal_initial_one_percent_methods_have_identical_first_generation(self):
        logs = [_fixture(method, 29) for method in ("fixed_0.01", "legacy", "gentle")]
        for log in logs:
            self.assertVerified(log)
            self.assertEqual(log["candidates"], logs[0]["candidates"])
            self.assertEqual(log["rng_initial"], logs[0]["rng_initial"])
            self.assertEqual(log["rng_final"], logs[0]["rng_final"])
            self.assertEqual(log["generations"][0]["population_after"],
                             logs[0]["generations"][0]["population_after"])

    def test_fixed_rates_use_common_uniforms_with_absolute_bit_probabilities(self):
        logs = [_fixture(method, 29) for method in METHODS[:3]]
        for log in logs:
            self.assertVerified(log)
            self.assertEqual(log["rng_initial"], logs[0]["rng_initial"])
            self.assertEqual(log["rng_final"], logs[0]["rng_final"])
            self.assertNotEqual(log["generations"][0]["parameters_before"]["p_m"],
                                1 / log["problem"]["n"])
        for low, middle, high in zip(*(log["candidates"] for log in logs), strict=True):
            self.assertEqual(low["pre_mask"], middle["pre_mask"])
            self.assertEqual(middle["pre_mask"], high["pre_mask"])
            self.assertLessEqual(set(low["mutation_bits"]), set(middle["mutation_bits"]))
            self.assertLessEqual(set(middle["mutation_bits"]), set(high["mutation_bits"]))

    def test_controller_uses_registered_method_factors_and_bounds(self):
        cases = (
            ("legacy", 0.04, True, 0.02),
            ("legacy", 0.04, False, 0.08),
            ("gentle", 0.01, True, 0.01 / 1.25),
            ("gentle", 0.01, False, 0.0125),
            ("gentle", 0.01953125, False, 0.02),
            ("gentle", 0.00512, True, 0.005),
        )
        for method, old_p, success, expected_p in cases:
            old = _parameters(old_p)
            result = v._reference_update(old, 116, success, 29, method)
            with self.subTest(method=method, p=old_p, success=success):
                self.assertEqual(result["parameters_after"], _parameters(expected_p))
                self.assertEqual(result["controller_event"], "SUCCESS" if success else "STAGNATION")
                self.assertEqual(result["failed_queries_after"], 0)
                self.assertEqual(old, _parameters(old_p))
                events = result["parameter_events"]
                self.assertEqual([row["field"] for row in events], list(v.PARAMETER_NAMES))
                self.assertEqual([row["enabled"] for row in events], [True, False, False, False, False])

    def test_success_has_priority_and_threshold_uses_failed_queries(self):
        success = v._reference_update(_parameters(0.02), 144, True, 29, "gentle")
        self.assertEqual(success["controller_event"], "SUCCESS")
        self.assertEqual(success["parameters_after"]["p_m"], 0.02 / 1.25)
        self.assertEqual(success["failed_queries_accumulated"], 0)
        self.assertEqual(success["failed_queries_after"], 0)
        self.assertEqual(success["stagnation_overshoot"], 0)
        for before, accumulated, after, overshoot, event in (
            (115, 144, 144, 0, "NO_CHANGE"),
            (116, 145, 0, 0, "STAGNATION"),
            (117, 146, 0, 1, "STAGNATION"),
        ):
            result = v._reference_update(_parameters(), before, False, 29, "gentle")
            with self.subTest(failed_before=before):
                self.assertEqual(result["controller_event"], event)
                self.assertEqual(result["failed_queries_accumulated"], accumulated)
                self.assertEqual(result["failed_queries_after"], after)
                self.assertEqual(result["stagnation_overshoot"], overshoot)

    def test_boundary_events_are_retained_even_when_value_does_not_change(self):
        for method, value, success in (("legacy", 0.01, True), ("legacy", 0.08, False),
                                       ("gentle", 0.005, True), ("gentle", 0.02, False)):
            result = v._reference_update(_parameters(value), 116, success, 29, method)
            with self.subTest(method=method, value=value, success=success):
                self.assertEqual(result["parameters_after"]["p_m"], value)
                self.assertEqual(result["controller_event"], "SUCCESS" if success else "STAGNATION")
                self.assertEqual(result["failed_queries_after"], 0)
                self.assertEqual(result["parameter_events"][0],
                                 {"field": "p_m", "enabled": True, "before": value,
                                  "after": value, "direction": "unchanged", "at_boundary": True})

    def test_fixed_controls_log_events_and_reset_counter_without_changing_parameters(self):
        for method, rate in zip(METHODS[:3], (0.005, 0.01, 0.02), strict=True):
            for success in (False, True):
                result = v._reference_update(_parameters(rate), 116, success, 29, method)
                with self.subTest(method=method, success=success):
                    self.assertEqual(result["parameters_after"], _parameters(rate))
                    self.assertEqual(result["failed_queries_after"], 0)
                    self.assertEqual(result["controller_event"], "SUCCESS" if success else "STAGNATION")
                    self.assertTrue(all(not row["enabled"] and row["direction"] == "unchanged"
                                        for row in result["parameter_events"]))
                    self.assertTrue(result["parameter_events"][0]["at_boundary"])

    def test_stagnation_change_applies_from_next_generation_and_prefix_has_no_update(self):
        log = _flat("gentle", 157)
        receipt = self.assertVerified(log)
        fifth, prefix = log["generations"][4:6]
        self.assertEqual(fifth["end_call"], 145)
        self.assertEqual(fifth["parameters_before"]["p_m"], 0.01)
        self.assertEqual(fifth["parameters_after"]["p_m"], 0.0125)
        self.assertEqual(fifth["controller_event"], "STAGNATION")
        self.assertEqual(fifth["failed_queries_accumulated"], 145)
        self.assertEqual(prefix["parameters_before"]["p_m"], 0.0125)
        self.assertEqual(prefix["end_call"] - prefix["start_call"] + 1, 12)
        self.assertFalse(prefix["complete"])
        self.assertEqual(prefix["population_after"], fifth["population_after"])
        self.assertEqual(prefix["parameters_before"], prefix["parameters_after"])
        self.assertEqual(prefix["failed_queries_before"], prefix["failed_queries_after"])
        self.assertEqual(prefix["parameter_events"], [])
        self.assertEqual(prefix["controller_event"], "PARTIAL_NO_UPDATE")
        self.assertIsNone(prefix["success"])
        self.assertIsNone(prefix["stagnation_overshoot"])
        self.assertEqual(receipt["derived_metrics"]["population_trace"][-1]["population_size"], 30)

    def test_registered_budget_is_5000_new_queries_plus_separate_thirty_known_scores(self):
        receipt = self.assertVerified(_flat("legacy", 5000))
        self.assertEqual(receipt["new_calls"], 5000)
        self.assertEqual(receipt["completed_generations"], 172)
        self.assertEqual(receipt["summary"]["partial_children"], 12)
        self.assertEqual(receipt["summary"]["physical_evaluations"], 5000)
        self.assertEqual(receipt["summary"]["known_score_validation_evaluations"], 30)
        self.assertEqual(receipt["derived_metrics"]["generation_trace"][-1]["start_q"], 4989)
        self.assertEqual(receipt["record_call"], 0)
        self.assertEqual(receipt["summary"]["best_profit"], 0)

    def test_last_query_can_change_record_without_population_or_controller_change(self):
        log = _successful_prefix()
        receipt = self.assertVerified(log)
        self.assertEqual(receipt["record_call"], 1)
        self.assertGreater(receipt["record_profit"], 0)
        self.assertEqual(receipt["final_population_refs"], list(range(30)))
        self.assertEqual(receipt["final_parameters"], _parameters())
        self.assertEqual(receipt["final_failed_queries"], 0)
        self.assertFalse(receipt["derived_metrics"]["population_trace"][-1]["record_in_population"])
        self.assertIsNone(log["generations"][0]["success"])

    def test_equal_records_do_not_refresh_call_and_all_offspring_are_committed(self):
        log = _flat("fixed_0.01", 58)
        receipt = self.assertVerified(log)
        self.assertEqual(receipt["record_call"], 0)
        self.assertEqual(receipt["derived_metrics"]["record_events"], [{"q": 0, "profit": 0}])
        for generation in log["generations"]:
            offspring = list(range(30 + generation["start_call"] - 1, 30 + generation["end_call"]))
            self.assertEqual(generation["population_after"][1:], offspring)
            self.assertFalse(generation["success"])

    def test_first_feasible_prefix_record_starts_from_undefined_initial_record(self):
        log = _successful_prefix(initial_feasible=False)
        receipt = self.assertVerified(log)
        self.assertIsNone(log["generations"][0]["record_before"])
        self.assertEqual(receipt["record_call"], 1)
        self.assertEqual(receipt["derived_metrics"]["record_events"],
                         [{"q": 0, "profit": None}, {"q": 1, "profit": receipt["record_profit"]}])
        self.assertEqual(receipt["final_population_refs"], list(range(30)))
        self.assertFalse(receipt["derived_metrics"]["population_trace"][-1]["record_in_population"])
        self.assertIsNone(receipt["derived_metrics"]["population_trace"][-1]["mean_feasible_profit"])

    def test_ranking_and_tie_occurrences_are_independent_of_profit_when_infeasible(self):
        self.assertGreater(v._key({"weight": 0, "profit": 0, "feasible": True}, 1),
                           v._key({"weight": 2, "profit": 1000, "feasible": False}, 1))
        self.assertGreater(v._key({"weight": 2, "profit": 1, "feasible": False}, 1),
                           v._key({"weight": 3, "profit": 1000, "feasible": False}, 1))
        class TieGenerator:
            def __init__(self):
                self.bounds = []
            def integers(self, bound):
                self.bounds.append(bound)
                return bound - 1
        generator = TieGenerator()
        self.assertEqual(v._choose([4], generator), 4)
        self.assertEqual(generator.bounds, [])
        self.assertEqual(v._choose([2, 2, 7], generator), 7)
        self.assertEqual(generator.bounds, [3])

    def test_exact_observational_novelty_uses_all_pairs_without_affecting_control(self):
        for distance in range(5):
            first, second = "0000", "1" * distance + "0" * (4 - distance)
            novel = 0
            for choices in itertools.product((False, True), repeat=distance):
                mask = list(first)
                for index, take_second in enumerate(choices):
                    if take_second:
                        mask[index] = second[index]
                novel += int("".join(mask) not in (first, second))
            self.assertEqual(v._reference_mean([distance], 4), Fraction(novel, 2 ** distance))
        self.assertEqual(v._reference_mean([0, 4], 100), Fraction(7, 16))
        self.assertLess(v._reference_mean([100], 100), Fraction(1))
        for invalid in ([], [True], [-1], [101], [2.0]):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                v._reference_mean(invalid, 100)

    def test_population_metrics_use_only_the_committed_population(self):
        problem = {"n": 4, "weights": [1] * 4, "profits": [1] * 4, "capacity": 4}
        masks = ["0000"] * 15 + ["1111"] * 15
        receipt = self.assertVerified(_fixture(problem=problem, masks=masks, budget=12))
        first, last = receipt["derived_metrics"]["population_trace"]
        self.assertEqual(first["unique_masks"], 2)
        self.assertEqual(first["unique_fraction"], 2 / 30)
        self.assertEqual(first["mean_pairwise_hamming"], 4 * 15 * 15 / math.comb(30, 2))
        self.assertEqual(first["mean_feasible_profit"], 2)
        self.assertFalse(last["complete"])
        for name in ("population_size", "unique_masks", "unique_fraction", "mean_pairwise_hamming",
                     "feasible_fraction", "mean_feasible_profit"):
            self.assertEqual(last[name], first[name])
        no_feasible = v._population_point(0, True, list(range(30)), ["1111"] * 30,
                                         [{"weight": 4, "profit": 4, "feasible": False}] * 30, None, 4)
        self.assertIsNone(no_feasible["mean_feasible_profit"])
        self.assertFalse(no_feasible["record_in_population"])

    def test_operator_diagnostics_recompute_premutation_fitness_after_search(self):
        log = _fixture(budget=100)
        receipt = self.assertVerified(log)
        derived = receipt["derived_metrics"]
        self.assertEqual(sum(row["total"] for row in derived["operator_bins"]), 100)
        self.assertEqual(sum(row["crossed"] for row in derived["operator_bins"]),
                         sum(child["crossover"] for child in log["candidates"]))
        for child, metric in zip(log["candidates"], derived["candidate_metrics"], strict=True):
            score = _score(log["problem"], child["pre_mask"])
            self.assertEqual((metric["pre_weight"], metric["pre_profit"], metric["pre_feasible"]),
                             (score["weight"], score["profit"], score["feasible"]))
            if not child["crossover"]:
                self.assertFalse(metric["pre_novel"])
                self.assertFalse(metric["pre_better_both"])

    def test_verifier_uses_no_production_scoring_selection_controller_or_replay(self):
        log = _fixture()
        with patch.object(engine, "evaluate", side_effect=AssertionError("production score used")), \
                patch.object(engine, "_evaluate", side_effect=AssertionError("production private score used")), \
                patch.object(engine, "_pick", side_effect=AssertionError("production selection used")), \
                patch.object(engine, "update_parameters", side_effect=AssertionError("production control used")), \
                patch.object(engine, "run_search", side_effect=AssertionError("production replay used")):
            self.assertVerified(log)
        source = inspect.getsource(v)
        self.assertNotIn("from .engine import", source)
        self.assertNotIn("import engine", source)
        self.assertNotIn("parameter_dynamics", source)
        self.assertNotIn("two_signal_mutation", source)
        self.assertEqual(tuple(inspect.signature(v.verify_log).parameters), ("log",))

    def test_float_and_exact_rational_corruption_are_rejected_without_tolerance(self):
        pristine = _fixture()
        changes = (
            lambda event: event["parameters_after"].__setitem__(
                "p_m", math.nextafter(event["parameters_after"]["p_m"], 1)),
            lambda event: event.__setitem__("novelty_sum_numerator", event["novelty_sum_numerator"] + 1),
            lambda event: event.__setitem__("novelty_sum_denominator", 0),
            lambda event: event.__setitem__("novelty_mean_numerator", True),
            lambda event: event.__setitem__("novelty_mean_denominator", event["novelty_mean_denominator"] + 1),
            lambda event: event["parent_distances"].pop(),
        )
        for index, mutate in enumerate(changes):
            bad = deepcopy(pristine)
            mutate(bad["generations"][0])
            with self.subTest(corruption=index), self.assertRaises(ValueError):
                v.verify_log(bad)
        bad = deepcopy(pristine)
        event = bad["generations"][0]
        event["novelty_mean_numerator"] *= 2
        event["novelty_mean_denominator"] *= 2
        with self.assertRaises(ValueError):
            v.verify_log(bad)

    def test_candidate_population_record_controller_and_rng_corruptions_are_rejected(self):
        pristine = _fixture()
        corruptions = {
            "initial_score": lambda log: log["initial_scores"][0].__setitem__("profit", 999),
            "profit": lambda log: log["candidates"][0].__setitem__("profit", -1),
            "feasible_type": lambda log: log["candidates"][0].__setitem__("feasible", 1),
            "tournament": lambda log: log["candidates"][0]["tournaments"][0].append(0),
            "parent": lambda log: log["candidates"][0]["parent_indices"].__setitem__(0, -1),
            "distance": lambda log: log["candidates"][0].__setitem__("parent_distance", True),
            "crossover": lambda log: log["candidates"][0].__setitem__("crossover", "yes"),
            "mutation": lambda log: log["candidates"][0].__setitem__("mutation_bits", [100]),
            "premask": lambda log: log["candidates"][0].__setitem__("pre_mask", "bad"),
            "duplicate": lambda log: log["candidates"][0].__setitem__("duplicate", None),
            "record": lambda log: log["candidates"][0].__setitem__("record_call", 9999),
            "generation": lambda log: log["generations"][0].__setitem__("generation", True),
            "target": lambda log: log["generations"][0]["parameters_after"].__setitem__("target_mu", 60),
            "mu_type": lambda log: log["generations"][0]["parameters_before"].__setitem__("target_mu", 30.0),
            "elite_reference": lambda log: log["generations"][0]["elite_references"].__setitem__(0, 999),
            "parent_mu": lambda log: log["generations"][0].__setitem__("actual_parent_mu", 31),
            "quota": lambda log: log["generations"][0].__setitem__("requested_offspring", 30),
            "counter": lambda log: log["generations"][0].__setitem__("failed_queries_after", 145),
            "overshoot": lambda log: log["generations"][0].__setitem__("stagnation_overshoot", 1),
            "event": lambda log: log["generations"][0].__setitem__("controller_event", "UNKNOWN"),
            "success_type": lambda log: log["generations"][0].__setitem__("success", 1),
            "parameter_event": lambda log: log["generations"][0]["parameter_events"][0].__setitem__("enabled", None),
            "population": lambda log: log["generations"][0]["population_after"].pop(),
            "rng": lambda log: log["rng_final"]["branch"]["state"].__setitem__(
                "state", log["rng_final"]["branch"]["state"]["state"] ^ 1),
            "initialization_rng_consumed": lambda log: log["rng_final"]["initialization"]["state"].__setitem__(
                "state", log["rng_final"]["initialization"]["state"]["state"] ^ 1),
            "summary": lambda log: log["summary"].__setitem__("physical_evaluations", 0),
        }
        for name, mutate in corruptions.items():
            bad = deepcopy(pristine)
            mutate(bad)
            with self.subTest(corruption=name), self.assertRaises(ValueError):
                v.verify_log(bad)

    def test_partial_block_cannot_commit_population_counter_or_feedback(self):
        pristine = _flat("gentle", 157)
        corruptions = (
            lambda event: event.__setitem__("complete", True),
            lambda event: event["parameters_after"].__setitem__("p_m", 0.02),
            lambda event: event.__setitem__("failed_queries_after", 12),
            lambda event: event.__setitem__("failed_queries_accumulated", 12),
            lambda event: event["population_after"].append(186),
            lambda event: event.__setitem__("success", False),
            lambda event: event.__setitem__("stagnation_overshoot", 0),
            lambda event: event.__setitem__("parameter_events", [{}]),
            lambda event: event.__setitem__("controller_event", "NO_CHANGE"),
        )
        for index, mutate in enumerate(corruptions):
            bad = deepcopy(pristine)
            mutate(bad["generations"][-1])
            with self.subTest(corruption=index), self.assertRaises(ValueError):
                v.verify_log(bad)

    def test_all_six_rng_channels_require_lossless_pcg64_state_and_exact_progress(self):
        pristine = _fixture()
        corruptions = (
            lambda log: log["rng_initial"].pop("mutation"),
            lambda log: log["rng_initial"].update({"extra": deepcopy(log["rng_initial"]["ties"])}),
            lambda log: log["rng_initial"]["selection"].__setitem__("bit_generator", "MT19937"),
            lambda log: log["rng_initial"]["mutation"]["state"].__setitem__("state", "invalid"),
            lambda log: log["generations"][0]["rng_before"]["ties"]["state"].__setitem__(
                "state", log["generations"][0]["rng_before"]["ties"]["state"]["state"] ^ 1),
            lambda log: log["generations"][0]["rng_after"]["crossover"]["state"].__setitem__(
                "state", log["generations"][0]["rng_after"]["crossover"]["state"]["state"] ^ 1),
        )
        for index, mutate in enumerate(corruptions):
            bad = deepcopy(pristine)
            mutate(bad)
            with self.subTest(corruption=index), self.assertRaises(ValueError):
                v.verify_log(bad)

    def test_missing_extra_oracle_foreign_method_and_schema_fields_are_rejected(self):
        pristine = _fixture()
        corruptions = (
            lambda log: log["candidates"].pop(),
            lambda log: log["generations"].pop(),
            lambda log: log["generations"].append(deepcopy(log["generations"][-1])),
            lambda log: log.update({"schema": "foreign"}),
            lambda log: log.update({"method": True}),
            lambda log: log.update({"method": "fixed"}),
            lambda log: log.update({"method": "two_signal"}),
            lambda log: log.update({"profile": 1}),
            lambda log: log.update({"budget": 0}),
            lambda log: log.update({"budget": 5001}),
            lambda log: log.update({"optimum": 123}),
            lambda log: log["problem"].update({"optimal_mask": "1111"}),
            lambda log: log["candidates"][0].update({"pre_score": 123}),
            lambda log: log["timing_ns"].update({"invented": 0}),
        )
        for index, mutate in enumerate(corruptions):
            bad = deepcopy(pristine)
            mutate(bad)
            with self.subTest(corruption=index), self.assertRaises(ValueError):
                v.verify_log(bad)

    def test_timing_is_observational_nonnegative_and_disjoint(self):
        pristine = _fixture()
        receipt = self.assertVerified(pristine)
        self.assertEqual(receipt["timing_status"], "OBSERVATIONAL_VALIDATED_NOT_RECONSTRUCTED")
        self.assertEqual(receipt["timing_ns"], pristine["timing_ns"])
        for bad_value in (-1, True, 1.0, math.nan):
            bad = deepcopy(pristine)
            bad["timing_ns"]["signal"] = bad_value
            with self.subTest(value=bad_value), self.assertRaises(ValueError):
                v.verify_log(bad)
        bad = deepcopy(pristine)
        bad["timing_ns"]["total"] = 0
        bad["timing_ns"]["evaluation"] = 1
        with self.assertRaises(ValueError):
            v.verify_log(bad)

    def test_ci_repository_and_branch_identity_are_required(self):
        log = _fixture()
        for key, value in (("GITHUB_ACTIONS", "false"), ("GITHUB_REPOSITORY", "other/repository"),
                           ("GITHUB_REF", "refs/heads/main")):
            with patch.dict(os.environ, {key: value}), self.assertRaises(ValueError):
                v.verify_log(log)


if __name__ == "__main__":
    unittest.main()
