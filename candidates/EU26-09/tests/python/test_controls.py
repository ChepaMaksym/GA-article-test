from __future__ import annotations

import math
import unittest

from eu2609.controls import (
    ControlError,
    control_state,
    round_ties_to_even_positive,
    transition_lambda,
)


class RoundingTests(unittest.TestCase):
    def test_below_half_rounds_down(self) -> None:
        self.assertEqual(round_ties_to_even_positive(1.49), 1)

    def test_odd_half_rounds_up(self) -> None:
        self.assertEqual(round_ties_to_even_positive(1.5), 2)

    def test_even_half_rounds_down(self) -> None:
        self.assertEqual(round_ties_to_even_positive(2.5), 2)

    def test_next_odd_half_rounds_up(self) -> None:
        self.assertEqual(round_ties_to_even_positive(3.5), 4)

    def test_cap_half_rounds_to_even(self) -> None:
        self.assertEqual(round_ties_to_even_positive(99.5), 100)

    def test_rejects_nonpositive_nonfinite_and_boolean(self) -> None:
        for value in (0.0, -1.0, math.nan, math.inf, True):
            with self.subTest(value=value), self.assertRaises(ControlError):
                round_ties_to_even_positive(value)


class MappingTests(unittest.TestCase):
    def test_initial_mapping(self) -> None:
        state = control_state(1.0, dimension=100)
        self.assertEqual(state.mutation_probability, 0.01)
        self.assertEqual(state.crossover_probability, 1.0)
        self.assertEqual(state.source_offspring_count, 1)
        self.assertEqual(state.evaluation_increment, 2)

    def test_mapping_at_two(self) -> None:
        state = control_state(2.0, dimension=100)
        self.assertEqual(state.mutation_probability, 0.02)
        self.assertEqual(state.crossover_probability, 0.5)
        self.assertEqual(state.source_offspring_count, 2)

    def test_paper_source_conflict_at_half_integer(self) -> None:
        state = control_state(2.5, dimension=100)
        self.assertEqual(state.source_offspring_count, 2)
        self.assertEqual(state.paper_offspring_count, 3)

    def test_subunit_crossover_rate_is_direct(self) -> None:
        state = control_state(10.0, dimension=100, crossover_rate=0.25)
        self.assertEqual(state.crossover_probability, 0.25)

    def test_mapping_at_cap(self) -> None:
        state = control_state(100.0, dimension=100)
        self.assertEqual(state.mutation_probability, 1.0)
        self.assertEqual(state.crossover_probability, 0.01)
        self.assertEqual(state.source_offspring_count, 100)
        self.assertEqual(state.evaluation_increment, 200)

    def test_evaluation_increment_is_even(self) -> None:
        for value in (1.0, 1.5, 2.5, 17.2, 99.5):
            with self.subTest(value=value):
                self.assertEqual(control_state(value, dimension=100).evaluation_increment % 2, 0)

    def test_rejects_bad_dimension(self) -> None:
        for dimension in (0, 1, True, 2.5):
            with self.subTest(dimension=dimension), self.assertRaises(ControlError):
                control_state(1.0, dimension=dimension)  # type: ignore[arg-type]

    def test_rejects_lambda_above_cap(self) -> None:
        with self.assertRaises(ControlError):
            control_state(100.01, dimension=100)

    def test_rejects_bad_crossover_rate(self) -> None:
        for value in (0.0, -1.0, math.nan, math.inf, False):
            with self.subTest(value=value), self.assertRaises(ControlError):
                control_state(1.0, dimension=100, crossover_rate=value)


class TransitionTests(unittest.TestCase):
    def test_success_at_floor_stays_at_one(self) -> None:
        self.assertEqual(
            transition_lambda(1.0, success=True, update_factor=1.5, lambda_max=100.0),
            1.0,
        )

    def test_success_divides_by_factor(self) -> None:
        self.assertEqual(
            transition_lambda(15.0, success=True, update_factor=1.5, lambda_max=100.0),
            10.0,
        )

    def test_failure_multiplies_by_fourth_root(self) -> None:
        observed = transition_lambda(
            1.0, success=False, update_factor=1.5, lambda_max=100.0
        )
        self.assertAlmostEqual(observed, math.pow(1.5, 0.25), places=15)

    def test_failure_at_exact_cap_resets(self) -> None:
        self.assertEqual(
            transition_lambda(100.0, success=False, update_factor=1.5, lambda_max=100.0),
            1.0,
        )

    def test_failure_near_cap_clamps_without_reset(self) -> None:
        self.assertEqual(
            transition_lambda(99.0, success=False, update_factor=1.5, lambda_max=100.0),
            100.0,
        )

    def test_rejects_factor_not_greater_than_one(self) -> None:
        for factor in (0.5, 1.0):
            with self.subTest(factor=factor), self.assertRaises(ControlError):
                transition_lambda(1.0, success=True, update_factor=factor, lambda_max=100.0)

    def test_rejects_nonboolean_success(self) -> None:
        with self.assertRaises(ControlError):
            transition_lambda(1.0, success=1, update_factor=1.5, lambda_max=100.0)  # type: ignore[arg-type]

    def test_rejects_value_above_cap(self) -> None:
        with self.assertRaises(ControlError):
            transition_lambda(101.0, success=False, update_factor=1.5, lambda_max=100.0)


if __name__ == "__main__":
    unittest.main()
