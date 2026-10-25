"""CI-only software fixtures for independent replay, not research outcomes."""
from __future__ import annotations

from copy import deepcopy
from fractions import Fraction
import inspect
import itertools
import math
import os
import unittest
from unittest.mock import patch

from studies.knapsack_parameters.two_signal_mutation import engine
from studies.knapsack_parameters.two_signal_mutation import verifier as v


def _score(problem, mask):
    selected = [index for index, bit in enumerate(mask) if bit == "1"]
    weight = sum(problem["weights"][index] for index in selected)
    profit = sum(problem["profits"][index] for index in selected)
    return {"weight": weight, "profit": profit, "feasible": weight <= problem["capacity"]}


def _fixture(method="two_signal", budget=61, seed=37001, *, problem=None, masks=None):
    problem = ({"n": 4, "weights": [1, 1, 1, 1], "profits": [1, 2, 3, 4], "capacity": 2}
               if problem is None else problem)
    masks = (["0000", "1000", "0100", "0010", "0001", "1100"] * 5
             if masks is None else masks)
    return engine.run_search(problem, masks, [_score(problem, mask) for mask in masks],
                             method, engine.make_rngs(seed, 0, 0), budget=budget)


class TwoSignalVerifierTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if os.environ.get("GITHUB_ACTIONS") != "true":
            raise RuntimeError("Registered software checks are CI-only")

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

    def test_all_three_profiles_independently_reconstructed(self):
        for method in ("fixed", "adaptive_mutation", "two_signal"):
            with self.subTest(method=method):
                receipt = self.assertVerified(_fixture(method))
                self.assertEqual(receipt["completed_generations"], 2)
                self.assertEqual(receipt["partial_generations"], 1)
                self.assertEqual(len(receipt["derived_metrics"]["candidate_metrics"]), 61)

    def test_exact_signal_is_mean_of_probabilities_not_probability_of_mean(self):
        for distance, expected in ((0, Fraction(0)), (1, Fraction(0)),
                                   (2, Fraction(1, 2)), (3, Fraction(3, 4)),
                                   (4, Fraction(7, 8))):
            self.assertEqual(v._reference_mean([distance], 100), expected)
        self.assertEqual(v._reference_mean([0, 2], 100), Fraction(1, 4))
        self.assertEqual(v._reference_mean([0, 3], 100), Fraction(3, 8))
        self.assertLess(v._reference_mean([100], 100), Fraction(1))
        for distances in ([], [True], [-1], [101], [2.0]):
            with self.subTest(distances=distances), self.assertRaises(ValueError):
                v._reference_mean(distances, 100)

    def test_rational_novelty_matches_enumerated_small_crossovers(self):
        for distance in range(5):
            first, second = "0000", "1" * distance + "0" * (4 - distance)
            novel = total = 0
            for choices in itertools.product((False, True), repeat=distance):
                mask = list(first)
                for index, take_second in enumerate(choices):
                    if take_second:
                        mask[index] = second[index]
                mask = "".join(mask)
                total += 1
                novel += int(mask != first and mask != second)
            self.assertEqual(v._reference_mean([distance], 4), Fraction(novel, total))

    def test_exact_threshold_includes_equality_and_rejects_one_rational_step_above(self):
        self.assertEqual(v._feedback(100, 0.01, 4, False, "two_signal", Fraction(1, 2)),
                         (0.02, 0, "STAGNATION_DOUBLE"))
        just_above = Fraction(1, 2) + Fraction(1, 2 ** 100)
        self.assertEqual(v._feedback(100, 0.01, 4, False, "two_signal", just_above),
                         (0.01, 0, "GATE_DENIED"))
        # Float rounding erases the distinction; the gate must not use it.
        self.assertEqual(float(just_above), 0.5)

    def test_success_precedes_gate_and_fifth_failure_resets_counter(self):
        self.assertEqual(v._feedback(100, 0.08, 4, True, "two_signal", Fraction(1)),
                         (0.04, 0, "SUCCESS_HALVE"))
        self.assertEqual(v._feedback(100, 0.01, 4, True, "two_signal", Fraction(1)),
                         (0.01, 0, "SUCCESS_HALVE"))
        self.assertEqual(v._feedback(100, 0.08, 4, False, "two_signal", Fraction(0)),
                         (0.08, 0, "STAGNATION_DOUBLE"))
        self.assertEqual(v._feedback(100, 0.01, 3, False, "two_signal", Fraction(1)),
                         (0.01, 4, "NO_CHANGE"))
        self.assertEqual(v._feedback(100, 0.01, 4, False, "adaptive_mutation", Fraction(1)),
                         (0.02, 0, "STAGNATION_DOUBLE"))

    def test_first_generation_and_rng_state_identical_for_all_profiles(self):
        logs = [_fixture(method) for method in ("fixed", "adaptive_mutation", "two_signal")]
        for log in logs[1:]:
            self.assertEqual(log["rng_initial"], logs[0]["rng_initial"])
            self.assertEqual(log["candidates"][:29], logs[0]["candidates"][:29])
            self.assertEqual(log["generations"][0]["rng_after"],
                             logs[0]["generations"][0]["rng_after"])
        for log in logs:
            self.assertVerified(log)

    def test_population_metrics_use_counts_and_committed_population(self):
        problem = {"n": 4, "weights": [1] * 4, "profits": [1] * 4, "capacity": 4}
        masks = ["0000"] * 15 + ["1111"] * 15
        receipt = self.assertVerified(_fixture(problem=problem, masks=masks, budget=12))
        trace = receipt["derived_metrics"]["population_trace"]
        expected = 4 * 15 * 15 / math.comb(30, 2)
        self.assertEqual(trace[0]["q"], 0)
        self.assertEqual(trace[0]["unique_masks"], 2)
        self.assertEqual(trace[0]["unique_fraction"], 2 / 30)
        self.assertEqual(trace[0]["mean_pairwise_hamming"], expected)
        self.assertEqual(trace[0]["feasible_fraction"], 1)
        self.assertEqual(trace[0]["mean_feasible_profit"], 2)
        self.assertTrue(trace[0]["record_in_population"])
        self.assertEqual(trace[-1]["q"], 12)
        self.assertFalse(trace[-1]["complete"])
        for name in ("unique_masks", "unique_fraction", "mean_pairwise_hamming",
                     "feasible_fraction", "mean_feasible_profit"):
            self.assertEqual(trace[0][name], trace[-1][name])

    def test_no_feasible_population_mean_is_undefined_not_zero(self):
        problem = {"n": 4, "weights": [1] * 4, "profits": [1] * 4, "capacity": 0}
        point = v._population_point(0, True, list(range(30)), ["1111"] * 30,
                                    [_score(problem, "1111")] * 30, None, 4)
        self.assertEqual(point["feasible_fraction"], 0)
        self.assertIsNone(point["mean_feasible_profit"])
        self.assertFalse(point["record_in_population"])

    def test_prefix_has_signal_but_no_gate_controller_or_population_update(self):
        log = _fixture(budget=12)
        receipt = self.assertVerified(log)
        generation = log["generations"][0]
        self.assertEqual(len(generation["parent_distances"]), 12)
        self.assertIsNone(generation["gate_allows_increase"])
        self.assertEqual(generation["population_before"], generation["population_after"])
        self.assertEqual(generation["p_m"], generation["p_m_next"])
        self.assertEqual(generation["stagnation_before"], generation["stagnation_after"])
        self.assertEqual(generation["controller_event"], "PARTIAL_NO_UPDATE")
        self.assertFalse(receipt["derived_metrics"]["generation_trace"][0]["complete"])

    def test_registered_5000_call_accounting_keeps_twelve_query_prefix(self):
        problem = {"n": 2, "weights": [1, 1], "profits": [1, 1], "capacity": 0}
        receipt = self.assertVerified(_fixture(problem=problem, masks=["00"] * 30, budget=5000))
        self.assertEqual(receipt["new_calls"], 5000)
        self.assertEqual(receipt["completed_generations"], 172)
        self.assertEqual(receipt["summary"]["partial_children"], 12)
        self.assertEqual(receipt["summary"]["best_profit"], 0)
        self.assertEqual(receipt["record_call"], 0)
        self.assertEqual(receipt["derived_metrics"]["generation_trace"][-1]["start_q"], 4989)

    def test_first_feasible_final_prefix_record_changes_record_not_population(self):
        problem = {"n": 2, "weights": [1, 1], "profits": [1, 1], "capacity": 0}
        log = None
        # These are bounded instructional fixtures, not selectors for research
        # tasks, seeds, or favourable experimental trajectories.
        for seed in range(128):
            candidate = _fixture(problem=problem, masks=["11"] * 30, budget=1, seed=seed)
            if candidate["summary"]["best_profit"] == 0:
                log = candidate
                break
        self.assertIsNotNone(log)
        receipt = self.assertVerified(log)
        self.assertEqual(receipt["record_call"], 1)
        self.assertEqual(receipt["final_population_refs"], list(range(30)))
        self.assertEqual(receipt["derived_metrics"]["record_events"],
                         [{"q": 0, "profit": None}, {"q": 1, "profit": 0}])
        self.assertFalse(receipt["derived_metrics"]["population_trace"][-1]["record_in_population"])

    def test_equal_record_does_not_refresh_call_and_worse_children_are_committed(self):
        problem = {"n": 2, "weights": [1, 1], "profits": [1, 1], "capacity": 2}
        log = _fixture(problem=problem, masks=["11"] * 30, budget=58)
        receipt = self.assertVerified(log)
        self.assertEqual(receipt["record_call"], 0)
        self.assertEqual(receipt["derived_metrics"]["record_events"], [{"q": 0, "profit": 2}])
        for event in log["generations"]:
            children = list(range(30 + event["start_call"] - 1, 30 + event["end_call"]))
            self.assertEqual(event["population_after"][1:], children)
            self.assertEqual(len(event["population_after"]), 30)

    def test_operator_metrics_reconstructed_for_all_pairs_but_condition_on_crossing(self):
        log = _fixture(budget=100)
        receipt = self.assertVerified(log)
        derived = receipt["derived_metrics"]
        self.assertEqual(sum(row["total"] for row in derived["operator_bins"]), 100)
        self.assertEqual(sum(row["crossed"] for row in derived["operator_bins"]),
                         sum(child["crossover"] for child in log["candidates"]))
        for child, row in zip(log["candidates"], derived["candidate_metrics"], strict=True):
            expected = _score(log["problem"], child["pre_mask"])
            self.assertEqual(row["pre_weight"], expected["weight"])
            self.assertEqual(row["pre_profit"], expected["profit"])
            self.assertEqual(row["pre_feasible"], expected["feasible"])
            self.assertEqual(row["q"], child["call"])
            self.assertEqual(row["parent_distance"], child["parent_distance"])
            self.assertEqual(row["crossed"], child["crossover"])
            if not child["crossover"]:
                self.assertFalse(row["pre_novel"])
                self.assertFalse(row["pre_better_both"])
        self.assertEqual(sum(row["strict_record"] for row in derived["candidate_metrics"]),
                         len(derived["record_events"]) - 1)

    def test_verifier_is_independent_of_production_evaluator_controller_and_replay(self):
        log = _fixture()
        with patch.object(engine, "evaluate", side_effect=AssertionError("production score used")), \
             patch.object(engine, "update_mutation", side_effect=AssertionError("production control used")), \
             patch.object(engine, "run_search", side_effect=AssertionError("production replay used")):
            self.assertVerified(log)
        source = inspect.getsource(v)
        self.assertNotIn("from .engine import", source)
        self.assertNotIn("import engine", source)
        self.assertNotIn("mutation_only.engine", source)
        self.assertIn("Fraction", source)
        self.assertEqual(tuple(inspect.signature(v.verify_log).parameters), ("log",))

    def test_exact_signal_and_gate_corruptions_rejected_without_tolerance(self):
        pristine = _fixture()
        for field, transform in (
            ("novelty_sum_numerator", lambda value: value + 1),
            ("novelty_sum_denominator", lambda value: 0),
            ("novelty_mean_numerator", lambda value: True),
            ("novelty_mean_denominator", lambda value: value + 1),
            ("gate_allows_increase", lambda value: not value),
        ):
            bad = deepcopy(pristine)
            bad["generations"][0][field] = transform(bad["generations"][0][field])
            with self.subTest(field=field), self.assertRaises(ValueError):
                v.verify_log(bad)
        bad = deepcopy(pristine)
        event = bad["generations"][0]
        event["novelty_mean_numerator"] *= 2
        event["novelty_mean_denominator"] *= 2
        with self.assertRaises(ValueError):
            v.verify_log(bad)

    def test_uncrossed_parent_pairs_cannot_be_omitted_from_signal(self):
        pristine = _fixture(budget=100)
        uncrossed = [child for child in pristine["candidates"] if not child["crossover"]]
        self.assertTrue(uncrossed)
        child = uncrossed[0]
        bad = deepcopy(pristine)
        event = bad["generations"][child["generation"] - 1]
        event["parent_distances"].pop(child["call"] - event["start_call"])
        with self.assertRaises(ValueError):
            v.verify_log(bad)

    def test_timing_is_observational_exact_nonnegative_and_disjoint(self):
        log = _fixture()
        receipt = self.assertVerified(log)
        self.assertEqual(receipt["timing_status"], "OBSERVATIONAL_VALIDATED_NOT_RECONSTRUCTED")
        self.assertEqual(receipt["timing_ns"], log["timing_ns"])
        for value in (-1, True, 1.0, math.nan):
            bad = deepcopy(log)
            bad["timing_ns"]["signal"] = value
            with self.subTest(value=value), self.assertRaises(ValueError):
                v.verify_log(bad)
        bad = deepcopy(log)
        bad["timing_ns"]["total"] = 0
        bad["timing_ns"]["evaluation"] = 1
        with self.assertRaises(ValueError):
            v.verify_log(bad)

    def test_operator_population_rng_record_and_counter_corruptions_rejected(self):
        pristine = _fixture()
        corruptions = {
            "profit": lambda log: log["candidates"][0].__setitem__("profit", -1),
            "feasible_bool": lambda log: log["candidates"][0].__setitem__("feasible", 1),
            "parent": lambda log: log["candidates"][0]["parent_indices"].__setitem__(0, 30),
            "parent_distance": lambda log: log["candidates"][0].__setitem__("parent_distance", True),
            "tournament": lambda log: log["candidates"][0]["tournaments"][0].__setitem__(0, -1),
            "crossover": lambda log: log["candidates"][0].__setitem__("crossover", "yes"),
            "premask": lambda log: log["candidates"][0].__setitem__("pre_mask", "invalid"),
            "mutation": lambda log: log["candidates"][0].__setitem__("mutation_bits", [100]),
            "duplicates": lambda log: log["candidates"][0].__setitem__("duplicate", None),
            "record": lambda log: log["candidates"][0].__setitem__("record_call", 9999),
            "generation_number": lambda log: log["generations"][0].__setitem__("generation", True),
            "p": lambda log: log["generations"][0].__setitem__("p_m", math.nextafter(0.25, 1)),
            "counter": lambda log: log["generations"][0].__setitem__("stagnation_after", 5),
            "feedback": lambda log: log["generations"][0].__setitem__("controller_event", "UNKNOWN"),
            "population": lambda log: log["generations"][0]["population_after"].pop(),
            "rng": lambda log: log["rng_final"]["branch"]["state"].__setitem__("state", 0),
            "prefix_commit": lambda log: log["generations"][-1].__setitem__("complete", True),
            "summary": lambda log: log["summary"].__setitem__("physical_evaluations", 0),
        }
        for name, mutate in corruptions.items():
            bad = deepcopy(pristine)
            mutate(bad)
            with self.subTest(corruption=name), self.assertRaises(ValueError):
                v.verify_log(bad)

    def test_missing_extra_mixed_or_oracle_fields_are_rejected(self):
        pristine = _fixture()
        corruptions = [
            lambda log: log["candidates"].pop(),
            lambda log: log["generations"].pop(),
            lambda log: log.update({"schema": "historical-other-schema"}),
            lambda log: log.update({"method": "lambda_own"}),
            lambda log: log.update({"optimum": 123}),
            lambda log: log["problem"].update({"optimal_mask": "1111"}),
            lambda log: log["candidates"][0].update({"pre_score": 123}),
            lambda log: log["timing_ns"].update({"fabricated": 0}),
        ]
        for index, mutate in enumerate(corruptions):
            bad = deepcopy(pristine)
            mutate(bad)
            with self.subTest(corruption=index), self.assertRaises(ValueError):
                v.verify_log(bad)

    def test_ci_and_branch_identity_are_required(self):
        log = _fixture()
        for key, value in (("GITHUB_ACTIONS", "false"),
                           ("GITHUB_REPOSITORY", "someone/other"),
                           ("GITHUB_REF", "refs/heads/main")):
            with patch.dict(os.environ, {key: value}), self.assertRaises(ValueError):
                v.verify_log(log)


if __name__ == "__main__":
    unittest.main()
