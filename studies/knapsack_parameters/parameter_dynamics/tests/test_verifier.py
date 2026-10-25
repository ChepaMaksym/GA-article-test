"""Educational CI fixtures for independent dynamic-parameter replay."""
from __future__ import annotations

from copy import deepcopy
from fractions import Fraction
import inspect
import itertools
import math
import os
import unittest
from unittest.mock import patch

from studies.knapsack_parameters.parameter_dynamics import engine
from studies.knapsack_parameters.parameter_dynamics import verifier as v


def _score(problem, mask):
    selected = [position for position, bit in enumerate(mask) if bit == "1"]
    weight = sum(problem["weights"][position] for position in selected)
    profit = sum(problem["profits"][position] for position in selected)
    return {"weight": weight, "profit": profit, "feasible": weight <= problem["capacity"]}


def _fixture(profile=31, budget=211, seed=37001, *, problem=None, masks=None):
    problem = ({"n": 4, "weights": [1] * 4, "profits": [1, 2, 3, 4], "capacity": 2}
               if problem is None else problem)
    masks = (["0000", "1000", "0100", "0010", "0001", "1100"] * 5 if masks is None else masks)
    return engine.run_search(problem, masks, [_score(problem, mask) for mask in masks],
                             profile, engine.make_rngs(seed, 0, 0), budget=budget)


def _flat(profile=31, budget=211, seed=37001):
    return _fixture(profile, budget, seed, problem={"n": 4, "weights": [1] * 4,
                    "profits": [1] * 4, "capacity": 0}, masks=["0000"] * 30)


def _successful(profile=31, budget=100):
    problem = {"n": 100, "weights": [1] * 100, "profits": list(range(1, 101)), "capacity": 100}
    # A fixed bounded educational seed bank, not a scientific case selector.
    for seed in range(128):
        log = _fixture(profile, budget, seed, problem=problem, masks=["0" * 100] * 30)
        if log["generations"][0]["record_after"] > 0:
            return log
    raise AssertionError("No successful instructional fixture in seeds0..127")


class DynamicVerifierTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if os.environ.get("GITHUB_ACTIONS") != "true":
            raise RuntimeError("Registered software checks are CI-only")

    def assertVerified(self, log):
        result = v.verify_log(log)
        self.assertEqual(result["verification_status"], "VERIFIED")
        self.assertEqual(result["new_calls"], log["budget"])
        self.assertEqual(result["independent_score_checks"], 30 + 2 * log["budget"])
        self.assertEqual(result["initial_score_checks"], 30)
        self.assertEqual(result["final_score_checks"], log["budget"])
        self.assertEqual(result["premutation_score_checks"], log["budget"])
        self.assertEqual(result["summary"], log["summary"])
        return result

    def test_all_thirty_two_profiles_independently_reconstructed(self):
        for profile in range(32):
            with self.subTest(profile=profile):
                receipt = self.assertVerified(_fixture(profile))
                self.assertEqual(len(receipt["derived_metrics"]["candidate_metrics"]), 211)

    def test_first_generation_and_rng_identical_for_all_profiles(self):
        logs = [_fixture(profile, budget=29) for profile in range(32)]
        for profile, log in enumerate(logs):
            with self.subTest(profile=profile):
                self.assertEqual(log["candidates"], logs[0]["candidates"])
                self.assertEqual(log["rng_initial"], logs[0]["rng_initial"])
                self.assertEqual(log["rng_final"], logs[0]["rng_final"])
                self.assertEqual(log["generations"][0]["population_after"], logs[0]["generations"][0]["population_after"])
                self.assertVerified(log)

    def test_study_probabilities_are_absolute_in_small_fixtures(self):
        log = _fixture(0, budget=1)
        self.assertEqual(log["generations"][0]["parameters_before"]["p_m"], 0.01)
        self.assertNotEqual(log["generations"][0]["parameters_before"]["p_m"], 1 / log["problem"]["n"])
        self.assertVerified(log)

    def test_independent_exact_novelty_matches_enumerated_crossovers(self):
        for distance in range(7):
            first, second = "0" * 6, "1" * distance + "0" * (6 - distance)
            novel = 0
            for choices in itertools.product((False, True), repeat=distance):
                mask = list(first)
                for position, take_second in enumerate(choices):
                    if take_second:
                        mask[position] = second[position]
                novel += int("".join(mask) not in (first, second))
            self.assertEqual(v._reference_mean([distance], 6), Fraction(novel, 2 ** distance))
        self.assertEqual(v._reference_mean([0, 4], 100), Fraction(7, 16))
        self.assertNotEqual(v._reference_mean([0, 4], 100), v._reference_mean([2], 100))
        self.assertLess(v._reference_mean([100], 100), Fraction(1))
        for distances in ([], [True], [-1], [101], [1.0]):
            with self.subTest(distances=distances), self.assertRaises(ValueError):
                v._reference_mean(distances, 100)

    def test_success_updates_simultaneously_and_resets_failed_queries(self):
        old = {"p_m": 0.08, "p_c": 0.5, "target_mu": 99, "tournament_size": 4, "elite_count": 4}
        result = v._reference_update(old, 140, True, 95, 31, Fraction(1, 4))
        self.assertEqual(result["parameters_after"],
                         {"p_m": 0.04, "p_c": 0.3, "target_mu": 50, "tournament_size": 5, "elite_count": 5})
        self.assertEqual(result["controller_event"], "SUCCESS")
        self.assertEqual(result["failed_queries_accumulated"], 0)
        self.assertEqual(result["failed_queries_after"], 0)
        self.assertEqual(result["stagnation_overshoot"], 0)
        self.assertEqual(old["target_mu"], 99)
        self.assertEqual([item["field"] for item in result["parameter_events"]], list(v.PARAMETER_NAMES))

    def test_query_threshold_overshoot_and_boundary_events_are_distinct_from_changes(self):
        old = {"p_m": 0.08, "p_c": 0.9, "target_mu": 60, "tournament_size": 2, "elite_count": 1}
        result = v._reference_update(old, 140, False, 59, 31, Fraction(1))
        self.assertEqual(result["controller_event"], "STAGNATION")
        self.assertEqual(result["failed_queries_accumulated"], 199)
        self.assertEqual(result["failed_queries_after"], 0)
        self.assertEqual(result["stagnation_overshoot"], 54)
        self.assertEqual(result["parameters_after"], {**old, "target_mu": 100})
        events = {item["field"]: item for item in result["parameter_events"]}
        self.assertTrue(events["p_m"]["at_boundary"])
        self.assertEqual(events["p_m"]["direction"], "unchanged")
        self.assertEqual(events["target_mu"]["direction"], "increase")

    def test_disabled_fields_remain_initial_but_counter_still_resets(self):
        result = v._reference_update(deepcopy(v.INITIAL), 116, False, 29, 0, Fraction(0))
        self.assertEqual(result["controller_event"], "STAGNATION")
        self.assertEqual(result["parameters_after"], v.INITIAL)
        self.assertEqual(result["failed_queries_after"], 0)
        self.assertTrue(all(not item["enabled"] and item["direction"] == "unchanged"
                            for item in result["parameter_events"]))
        self.assertTrue(result["parameter_events"][0]["at_boundary"])

    def test_crossover_updates_on_every_completed_generation_not_only_control_events(self):
        result = v._reference_update(deepcopy(v.INITIAL), 0, False, 29, 2, Fraction(0))
        self.assertEqual(result["controller_event"], "NO_CHANGE")
        self.assertEqual(result["parameters_after"]["p_c"], 0.1)
        self.assertEqual(result["failed_queries_after"], 29)
        self.assertEqual(result["parameters_after"]["p_m"], 0.01)
        result = v._reference_update(deepcopy(v.INITIAL), 0, False, 29, 2, Fraction(1, 2))
        self.assertEqual(result["parameters_after"]["p_c"], 0.5)

    def test_target_population_growth_is_not_immediate_and_prefix_is_not_committed(self):
        log = _flat(profile=4, budget=150)
        receipt = self.assertVerified(log)
        fifth, prefix = log["generations"][4:6]
        self.assertEqual(fifth["end_call"], 145)
        self.assertEqual(fifth["parameters_after"]["target_mu"], 60)
        self.assertEqual(len(fifth["population_after"]), 30)
        self.assertEqual(prefix["actual_parent_mu"], 30)
        self.assertEqual(prefix["requested_offspring"], 59)
        self.assertEqual(prefix["end_call"] - prefix["start_call"] + 1, 5)
        self.assertFalse(prefix["complete"])
        self.assertEqual(prefix["population_after"], fifth["population_after"])
        self.assertEqual(prefix["parameters_before"], prefix["parameters_after"])
        self.assertEqual(prefix["failed_queries_before"], prefix["failed_queries_after"])
        self.assertEqual(prefix["parameter_events"], [])
        self.assertIsNone(prefix["success"])
        self.assertIsNone(prefix["stagnation_overshoot"])
        self.assertEqual(receipt["derived_metrics"]["population_trace"][-1]["population_size"], 30)

    def test_dynamic_shrink_and_multiple_elites_are_replayed_from_parent_population(self):
        log = _successful(profile=28, budget=42)
        receipt = self.assertVerified(log)
        first, second = log["generations"]
        self.assertTrue(first["success"])
        self.assertEqual(first["parameters_after"]["target_mu"], 15)
        self.assertEqual(first["parameters_after"]["elite_count"], 2)
        self.assertEqual(first["parameters_after"]["tournament_size"], 3)
        self.assertEqual(second["actual_parent_mu"], 30)
        self.assertEqual(second["requested_offspring"], 13)
        self.assertTrue(second["complete"])
        self.assertEqual(len(second["elite_indices"]), 2)
        self.assertEqual(len(set(second["elite_indices"])), 2)
        self.assertEqual(len(second["population_after"]), 15)
        self.assertEqual(receipt["derived_metrics"]["population_trace"][-1]["population_size"], 15)
        self.assertEqual(receipt["summary"]["partial_children"], 0)

    def test_population_metrics_use_actual_size_not_initial_thirty(self):
        problem = {"n": 4, "weights": [1] * 4, "profits": [1] * 4, "capacity": 4}
        masks = ["0000"] * 5 + ["1111"] * 5
        point = v._population_point(10, True, list(range(10)), masks,
                                    [_score(problem, mask) for mask in masks], "1111", 4)
        self.assertEqual(point["population_size"], 10)
        self.assertEqual(point["unique_masks"], 2)
        self.assertEqual(point["unique_fraction"], 0.2)
        self.assertEqual(point["mean_pairwise_hamming"], 4 * 5 * 5 / math.comb(10, 2))
        self.assertEqual(point["mean_feasible_profit"], 2)
        self.assertTrue(point["record_in_population"])
        no_feasible = v._population_point(10, False, list(range(10)), ["1111"] * 10,
                                         [{"weight": 4, "profit": 4, "feasible": False}] * 10, None, 4)
        self.assertIsNone(no_feasible["mean_feasible_profit"])
        self.assertEqual(no_feasible["feasible_fraction"], 0)

    def test_fixed_profile_keeps_172_generations_and_twelve_query_prefix(self):
        receipt = self.assertVerified(_flat(profile=0, budget=5000))
        self.assertEqual(receipt["completed_generations"], 172)
        self.assertEqual(receipt["summary"]["partial_children"], 12)
        self.assertEqual(receipt["record_call"], 0)
        self.assertEqual(receipt["summary"]["best_profit"], 0)
        self.assertEqual(receipt["summary"]["final_parameters"], v.INITIAL)
        self.assertEqual(receipt["derived_metrics"]["generation_trace"][-1]["start_q"], 4989)

    def test_last_query_can_improve_record_without_population_update(self):
        log = _successful(profile=31, budget=1)
        receipt = self.assertVerified(log)
        self.assertEqual(receipt["record_call"], 1)
        self.assertGreater(receipt["record_profit"], 0)
        self.assertEqual(receipt["final_population_refs"], list(range(30)))
        self.assertFalse(receipt["derived_metrics"]["population_trace"][-1]["record_in_population"])
        self.assertEqual(receipt["final_parameters"], v.INITIAL)

    def test_equal_record_does_not_refresh_and_worse_offspring_are_committed(self):
        log = _flat(profile=0, budget=58)
        receipt = self.assertVerified(log)
        self.assertEqual(receipt["record_call"], 0)
        self.assertEqual(receipt["derived_metrics"]["record_events"], [{"q": 0, "profit": 0}])
        for generation in log["generations"]:
            references = list(range(30 + generation["start_call"] - 1, 30 + generation["end_call"]))
            self.assertEqual(generation["population_after"][1:], references)

    def test_operator_diagnostics_are_independent_postsearch_work(self):
        log = _fixture(budget=100)
        receipt = self.assertVerified(log)
        derived = receipt["derived_metrics"]
        self.assertEqual(sum(item["total"] for item in derived["operator_bins"]), 100)
        self.assertEqual(sum(item["crossed"] for item in derived["operator_bins"]),
                         sum(item["crossover"] for item in log["candidates"]))
        for child, row in zip(log["candidates"], derived["candidate_metrics"], strict=True):
            score = _score(log["problem"], child["pre_mask"])
            self.assertEqual((row["pre_weight"], row["pre_profit"], row["pre_feasible"]),
                             (score["weight"], score["profit"], score["feasible"]))
            if not row["crossed"]:
                self.assertFalse(row["pre_novel"])
                self.assertFalse(row["pre_better_both"])

    def test_verifier_does_not_use_production_evaluation_or_control(self):
        log = _fixture()
        with patch.object(engine, "evaluate", side_effect=AssertionError("production score used")), \
                patch.object(engine, "update_parameters", side_effect=AssertionError("production control used")), \
                patch.object(engine, "run_search", side_effect=AssertionError("production replay used")):
            self.assertVerified(log)
        source = inspect.getsource(v)
        self.assertNotIn("from .engine import", source)
        self.assertNotIn("import engine", source)
        self.assertNotIn("two_signal_mutation", source)
        self.assertEqual(tuple(inspect.signature(v.verify_log).parameters), ("log",))

    def test_exact_rational_and_all_selected_pairs_are_required(self):
        pristine = _fixture(budget=100)
        for field, transform in (
                ("novelty_sum_numerator", lambda value: value + 1),
                ("novelty_sum_denominator", lambda value: 0),
                ("novelty_mean_numerator", lambda value: True),
                ("novelty_mean_denominator", lambda value: value + 1)):
            bad = deepcopy(pristine)
            bad["generations"][0][field] = transform(bad["generations"][0][field])
            with self.subTest(field=field), self.assertRaises(ValueError):
                v.verify_log(bad)
        bad = deepcopy(pristine)
        bad["generations"][0]["novelty_mean_numerator"] *= 2
        bad["generations"][0]["novelty_mean_denominator"] *= 2
        with self.assertRaises(ValueError):
            v.verify_log(bad)
        bad = deepcopy(pristine)
        bad["generations"][0]["parent_distances"].pop()
        with self.assertRaises(ValueError):
            v.verify_log(bad)

    def test_parameter_population_counter_and_rng_corruption_is_rejected(self):
        pristine = _fixture(budget=211)
        mutations = {
            "target": lambda log: log["generations"][0]["parameters_after"].__setitem__("target_mu", 100),
            "mu_type": lambda log: log["generations"][0]["parameters_before"].__setitem__("target_mu", 30.0),
            "elite_repeat": lambda log: log["generations"][0].__setitem__("elite_indices", [0, 0]),
            "elite_reference": lambda log: log["generations"][0]["elite_references"].__setitem__(0, 999),
            "parent_mu": lambda log: log["generations"][0].__setitem__("actual_parent_mu", 31),
            "quota": lambda log: log["generations"][0].__setitem__("requested_offspring", 30),
            "counter": lambda log: log["generations"][0].__setitem__("failed_queries_after", 145),
            "overshoot": lambda log: log["generations"][0].__setitem__("stagnation_overshoot", 1),
            "event": lambda log: log["generations"][0].__setitem__("controller_event", "UNKNOWN"),
            "success": lambda log: log["generations"][0].__setitem__("success", 1),
            "parameter_event": lambda log: log["generations"][0]["parameter_events"][0].__setitem__("enabled", None),
            "population": lambda log: log["generations"][0]["population_after"].pop(),
            "profit": lambda log: log["candidates"][0].__setitem__("profit", -1),
            "feasible": lambda log: log["candidates"][0].__setitem__("feasible", 1),
            "tournament": lambda log: log["candidates"][0]["tournaments"][0].append(0),
            "parent": lambda log: log["candidates"][0]["parent_indices"].__setitem__(0, -1),
            "distance": lambda log: log["candidates"][0].__setitem__("parent_distance", True),
            "mutation": lambda log: log["candidates"][0].__setitem__("mutation_bits", [100]),
            "premask": lambda log: log["candidates"][0].__setitem__("pre_mask", "bad"),
            "record": lambda log: log["candidates"][0].__setitem__("record_call", 9999),
            "duplicate": lambda log: log["candidates"][0].__setitem__("duplicate", None),
            "rng": lambda log: log["rng_final"]["branch"]["state"].__setitem__("state", 0),
            "summary": lambda log: log["summary"].__setitem__("physical_evaluations", 0),
        }
        for label, mutate in mutations.items():
            bad = deepcopy(pristine)
            mutate(bad)
            with self.subTest(corruption=label), self.assertRaises(ValueError):
                v.verify_log(bad)

    def test_partial_block_cannot_change_parameters_counter_or_population(self):
        pristine = _flat(profile=4, budget=150)
        mutations = (
            lambda event: event.__setitem__("complete", True),
            lambda event: event.__setitem__("parameters_after", v.INITIAL),
            lambda event: event.__setitem__("failed_queries_after", 5),
            lambda event: event["population_after"].append(179),
            lambda event: event.__setitem__("success", False),
            lambda event: event.__setitem__("stagnation_overshoot", 0),
            lambda event: event.__setitem__("parameter_events", [{}]),
        )
        for mutate in mutations:
            bad = deepcopy(pristine)
            mutate(bad["generations"][-1])
            with self.assertRaises(ValueError):
                v.verify_log(bad)

    def test_missing_extra_oracle_and_foreign_schema_fields_rejected(self):
        pristine = _fixture()
        mutations = (
            lambda log: log["candidates"].pop(),
            lambda log: log["generations"].pop(),
            lambda log: log["generations"].append(deepcopy(log["generations"][-1])),
            lambda log: log.update({"schema": "foreign"}),
            lambda log: log.update({"profile": True}),
            lambda log: log.update({"profile": 32}),
            lambda log: log.update({"optimum": 123}),
            lambda log: log["problem"].update({"optimal_mask": "1111"}),
            lambda log: log["candidates"][0].update({"pre_score": 123}),
            lambda log: log["timing_ns"].update({"invented": 0}),
        )
        for mutate in mutations:
            bad = deepcopy(pristine)
            mutate(bad)
            with self.assertRaises(ValueError):
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

    def test_ci_repository_and_branch_are_mandatory(self):
        log = _fixture()
        for key, value in (("GITHUB_ACTIONS", "false"), ("GITHUB_REPOSITORY", "other/repository"),
                           ("GITHUB_REF", "refs/heads/main")):
            with patch.dict(os.environ, {key: value}), self.assertRaises(ValueError):
                v.verify_log(log)


if __name__ == "__main__":
    unittest.main()
