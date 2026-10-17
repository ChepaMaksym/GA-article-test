"""Independent mathematical fixtures for the admitted mutation-rule adapter.

Run only in GitHub Actions. These are controller fixtures, not scientific
KPLIB experiments, and do not support claims about optimization performance.
"""
from __future__ import annotations

from copy import deepcopy
from decimal import Decimal, localcontext
import inspect
import math
import os
import unittest
from unittest.mock import patch

from .. import controller


def reference_threshold(n, r, R=None):
    """80-digit formula, without the production logarithmic implementation."""
    with localcontext() as context:
        context.prec = 80
        dimension = Decimal(n)
        strength = Decimal(str(r))
        confidence = Decimal(n ** 3) if R is None else Decimal(str(R))
        failure_wait = ((dimension / strength) ** strength
                        * (dimension / (dimension - strength))
                        ** (dimension - strength))
        # ln(e*n*R) = 1 + ln(n) + ln(R); retaining this 1 is essential.
        return +(failure_wait * (Decimal(1) + dimension.ln() + confidence.ln()))


class MutationRuleControllerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if os.environ.get("GITHUB_ACTIONS") != "true":
            raise RuntimeError("This test suite is CI-only")

    def assertThresholdClose(self, actual, expected):
        self.assertTrue(math.isfinite(actual))
        expected_float = float(expected)
        self.assertTrue(math.isclose(actual, expected_float,
                                     rel_tol=1e-12, abs_tol=1e-12),
                        (actual, expected_float))

    def test_formula_matches_independent_decimal80_reference(self):
        for n, r, R in ((2, 1, 1), (4, 1, 2), (10, 1, 1000),
                        (10, 2, 1000), (10, 5, 1000),
                        (100, 1, 1000000), (100, 2, 1000000),
                        (100, 50, 1000000)):
            with self.subTest(n=n, r=r, R=R):
                self.assertThresholdClose(controller.threshold(n, r, R),
                                          reference_threshold(n, r, R))

    def test_default_R_is_n_cubed(self):
        for n in (2, 4, 10, 100):
            with self.subTest(n=n):
                self.assertThresholdClose(controller.threshold(n, 1),
                                          controller.threshold(n, 1, n ** 3))
                self.assertThresholdClose(controller.threshold(n, 1),
                                          reference_threshold(n, 1))

    def test_registered_budget_cannot_reach_first_threshold(self):
        expected = reference_threshold(100, 1, 1000000)
        self.assertGreater(expected, Decimal(5000))
        self.assertThresholdClose(controller.threshold(100, 1), expected)
        self.assertGreater(controller.threshold(100, 1), 5000)

    def test_formula_does_not_drop_e_inside_logarithm(self):
        with localcontext() as context:
            context.prec = 80
            n, R = Decimal(100), Decimal(1000000)
            factor = n * (n / (n - 1)) ** 99
            incorrect = factor * (n.ln() + R.ln())
        actual = controller.threshold(100, 1)
        self.assertFalse(math.isclose(actual, float(incorrect),
                                      rel_tol=1e-3, abs_tol=1e-12))
        self.assertGreater(actual, float(incorrect))

    def test_exact_binomial_failure_factor_is_not_exponential_shortcut(self):
        # The exact (n/(n-r))**(n-r) factor is not replaced by exp(r).
        actual = controller.threshold(10, 5, 1000)
        shortcut = (10 / 5) ** 5 * math.exp(5) * math.log(math.e * 10 * 1000)
        self.assertFalse(math.isclose(actual, shortcut, rel_tol=1e-3))

    def test_initial_state_and_probability(self):
        state = controller.initial_state(100)
        self.assertEqual(state, {"r": 1.0, "u": 0})
        event = controller.transition(100, state, 29, False)
        self.assertEqual(event["before"], state)
        self.assertEqual(event["p_before"], .01)
        self.assertEqual(event["p_after"], .01)
        self.assertEqual(event["event"], "NO_CHANGE")

    def test_counts_failed_evaluations_not_generations(self):
        state = controller.initial_state(100)
        for generation in range(1, 6):
            event = controller.transition(100, state, 29, False)
            state = event["after"]
            self.assertEqual(state, {"r": 1.0, "u": 29 * generation})
        self.assertEqual(state["u"], 145)

    def test_all_registered_complete_blocks_remain_at_one_percent(self):
        state = controller.initial_state(100)
        for _ in range(172):
            event = controller.transition(100, state, 29, False)
            self.assertEqual((event["p_before"], event["p_after"]), (.01, .01))
            self.assertEqual(event["event"], "NO_CHANGE")
            state = event["after"]
        self.assertEqual(state["u"], 4988)
        prefix = controller.transition(100, state, 12, False, complete=False)
        self.assertEqual(prefix["after"], state)
        self.assertEqual(prefix["event"], "PARTIAL_NO_UPDATE")

    def test_strict_success_resets_strength_and_count(self):
        event = controller.transition(100, {"r": 3.0, "u": 100}, 29, True)
        self.assertEqual(event["after"], {"r": 1.0, "u": 0})
        self.assertEqual(event["p_before"], .03)
        self.assertEqual(event["p_after"], .01)
        self.assertEqual(event["event"], "STRICT_SUCCESS_RESET")

    def test_success_has_priority_over_exceeded_threshold(self):
        with patch.object(controller, "threshold", return_value=100.0):
            event = controller.transition(100, {"r": 2.0, "u": 100}, 29, True)
        self.assertEqual(event["after"], {"r": 1.0, "u": 0})
        self.assertEqual(event["event"], "STRICT_SUCCESS_RESET")

    def test_threshold_equality_does_not_increase_strength(self):
        with patch.object(controller, "threshold", return_value=100.0):
            event = controller.transition(100, {"r": 1.0, "u": 99}, 1, False)
        self.assertEqual(event["after"], {"r": 1.0, "u": 100})
        self.assertEqual(event["event"], "NO_CHANGE")

    def test_first_evaluation_strictly_above_threshold_increases_strength(self):
        with patch.object(controller, "threshold", return_value=100.0):
            event = controller.transition(100, {"r": 1.0, "u": 100}, 1, False)
        self.assertEqual(event["after"], {"r": 2.0, "u": 0})
        self.assertEqual(event["event"], "STAGNATION_INCREASE")
        self.assertEqual(event["p_after"], .02)

    def test_small_teaching_case_crosses_real_threshold(self):
        expected = reference_threshold(4, 1, 2)
        below = int(expected)
        self.assertLess(Decimal(below), expected)
        self.assertGreater(Decimal(below + 1), expected)
        event = controller.transition(4, controller.initial_state(4), below,
                                      False, R=2)
        self.assertEqual(event["after"], {"r": 1.0, "u": below})
        following = controller.transition(4, event["after"], 1, False, R=2)
        self.assertEqual(following["after"], {"r": 2.0, "u": 0})
        self.assertEqual(following["event"], "STAGNATION_INCREASE")

    def test_upper_bound_is_n_over_two(self):
        with patch.object(controller, "threshold", return_value=1.0):
            event = controller.transition(100, {"r": 50.0, "u": 1}, 1, False)
        self.assertEqual(event["after"], {"r": 50.0, "u": 0})
        self.assertEqual(event["p_after"], .5)
        self.assertEqual(event["event"], "STAGNATION_CAPPED")

    def test_odd_dimension_cap_does_not_round_above_n_over_two(self):
        with patch.object(controller, "threshold", return_value=1.0):
            event = controller.transition(5, {"r": 2.0, "u": 1}, 1, False)
        self.assertEqual(event["after"], {"r": 2.5, "u": 0})
        self.assertEqual(event["p_after"], .5)

    def test_partial_generation_never_updates_even_with_success(self):
        for success in (False, True):
            with self.subTest(success=success):
                state = {"r": 3.0, "u": 100}
                event = controller.transition(100, state, 12, success,
                                              complete=False)
                self.assertEqual(event["before"], event["after"])
                self.assertEqual(event["p_before"], event["p_after"])
                self.assertEqual(event["event"], "PARTIAL_NO_UPDATE")

    def test_return_record_exposes_all_transition_evidence(self):
        event = controller.transition(100, controller.initial_state(100), 29, False)
        self.assertEqual(set(event), {"before", "after", "p_before", "p_after",
                                      "threshold", "event", "complete",
                                      "completed_evaluations", "strict_success"})
        self.assertEqual(event["completed_evaluations"], 29)
        self.assertIs(event["complete"], True)
        self.assertIs(event["strict_success"], False)

    def test_function_does_not_mutate_or_alias_input_state(self):
        state = {"r": 1.0, "u": 7}
        original = deepcopy(state)
        event = controller.transition(100, state, 29, False)
        self.assertEqual(state, original)
        event["before"]["u"] = 999
        event["after"]["u"] = 888
        self.assertEqual(state, original)

    def test_inputs_cannot_include_oracle_metadata(self):
        signature = inspect.signature(controller.transition)
        self.assertEqual(set(signature.parameters),
                         {"n", "state", "completed_evaluations", "strict_success",
                          "complete", "R"})
        for key in ("optimum", "optimal_mask", "certificate", "population"):
            with self.subTest(key=key), self.assertRaises(ValueError):
                controller.transition(100, {"r": 1.0, "u": 0, key: 0}, 29, False)

    def test_invalid_dimensions_are_rejected(self):
        for n in (True, False, 0, 1, -1, 100.0, float("nan"), "100", None):
            with self.subTest(n=n), self.assertRaises(ValueError):
                controller.initial_state(n)
            with self.subTest(n=n), self.assertRaises(ValueError):
                controller.threshold(n, 1)

    def test_invalid_strengths_and_confidence_are_rejected(self):
        for strength in (True, False, 0, .5, -1, 50.1,
                         float("nan"), float("inf"), "1", None):
            with self.subTest(strength=strength), self.assertRaises(ValueError):
                controller.threshold(100, strength)
        for confidence in (True, False, 0, .5, -1,
                           float("nan"), float("inf"), "1000000"):
            with self.subTest(R=confidence), self.assertRaises(ValueError):
                controller.threshold(100, 1, confidence)

    def test_invalid_state_counters_and_shapes_are_rejected(self):
        states = [{"r": 1, "u": value}
                  for value in (True, False, -1, 1.0, float("nan"), "1", None)]
        states += [{}, {"r": 1}, {"u": 0}, None, [1, 0]]
        for state in states:
            with self.subTest(state=state), self.assertRaises(ValueError):
                controller.transition(100, state, 29, False)

    def test_partial_boundary_does_not_bypass_input_validation(self):
        for strength in (True, 0, 51, float("nan"), float("inf")):
            with self.subTest(strength=strength), self.assertRaises(ValueError):
                controller.transition(100, {"r": strength, "u": 0}, 12, False,
                                      complete=False)
        for n in (True, 1, 100.0):
            with self.subTest(n=n), self.assertRaises(ValueError):
                controller.transition(n, {"r": 1.0, "u": 0}, 12, False,
                                      complete=False)

    def test_invalid_query_counts_and_boolean_signals_are_rejected(self):
        for calls in (True, False, 0, -1, 29.0, float("nan"), "29", None):
            with self.subTest(calls=calls), self.assertRaises(ValueError):
                controller.transition(100, controller.initial_state(100), calls, False)
        for signal in (0, 1, "false", None, float("nan")):
            with self.subTest(success=signal), self.assertRaises(ValueError):
                controller.transition(100, controller.initial_state(100), 29, signal)
            with self.subTest(complete=signal), self.assertRaises(ValueError):
                controller.transition(100, controller.initial_state(100), 29, False,
                                      complete=signal)

    def test_nonfinite_threshold_overflow_is_rejected_not_silent_infinity(self):
        with self.assertRaises(ValueError):
            controller.threshold(10000, 5000)
