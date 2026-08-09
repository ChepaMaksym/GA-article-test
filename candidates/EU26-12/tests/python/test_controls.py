from __future__ import annotations

import unittest
from decimal import Decimal
from fractions import Fraction

from eu2612.contract import load_contract
from eu2612.controls import (
    ControlError,
    evaluation_schedule,
    fixture_report,
    fraction_decimal,
    lpsr_population,
    replacement_sources,
    round_ties_even,
    transform_cr,
    transform_f,
    update_success_memory,
)


class MemoryControlTests(unittest.TestCase):
    def test_frozen_memory_update_is_arithmetic(self) -> None:
        result = update_success_memory([10, 8, 5], [9, 6, 4.5], [0.2, 0.4, 0.8], [0.1, 0.5, 0.9])
        self.assertEqual(result.F, Fraction(2, 5))
        self.assertEqual(result.CR, Fraction(31, 70))
        self.assertEqual(result.weights, (Fraction(2, 7), Fraction(4, 7), Fraction(1, 7)))

    def test_non_improving_members_are_excluded(self) -> None:
        result = update_success_memory([10, 8], [9, 8], [0.25, 0.75], [0.2, 0.8])
        self.assertEqual(result.successful_indices, (0,))
        self.assertEqual(result.F, Fraction(1, 4))

    def test_no_strict_improvement_fails(self) -> None:
        with self.assertRaises(ControlError):
            update_success_memory([1], [1], [0.5], [0.5])

    def test_mismatched_shapes_fail(self) -> None:
        with self.assertRaises(ControlError):
            update_success_memory([1], [0], [0.5, 0.6], [0.5])

    def test_out_of_range_f_fails(self) -> None:
        with self.assertRaises(ControlError):
            update_success_memory([1], [0], [0], [0.5])

    def test_boolean_control_fails(self) -> None:
        with self.assertRaises(ControlError):
            update_success_memory([1], [0], [True], [0.5])


class TransformControlTests(unittest.TestCase):
    def test_cr_transform_clips_both_sides(self) -> None:
        self.assertEqual(transform_cr(0.5, [-10, 0, 10]), (Fraction(0), Fraction(1, 2), Fraction(1)))

    def test_cr_memory_outside_domain_fails(self) -> None:
        with self.assertRaises(ControlError):
            transform_cr(1.1, [0])

    def test_empty_cr_draws_fail(self) -> None:
        with self.assertRaises(ControlError):
            transform_cr(0.5, [])

    def test_f_redraw_and_cap(self) -> None:
        self.assertEqual(transform_f(0.5, [[-6, -4], [8], [0]]), (Fraction(1, 10), Fraction(1), Fraction(1, 2)))

    def test_f_sequence_without_positive_draw_fails(self) -> None:
        with self.assertRaises(ControlError):
            transform_f(0.5, [[-10, -6]])

    def test_empty_f_sequence_fails(self) -> None:
        with self.assertRaises(ControlError):
            transform_f(0.5, [[]])


class PopulationControlTests(unittest.TestCase):
    def test_explicit_ties_even(self) -> None:
        self.assertEqual(round_ties_even(Decimal("2.5")), 2)
        self.assertEqual(round_ties_even(Decimal("3.5")), 4)

    def test_lpsr_end_fixture(self) -> None:
        self.assertEqual(
            lpsr_population(initial_population=360, minimum_population=3, budget=50000, used_budget=49642),
            6,
        )

    def test_lpsr_clamps_at_small_terminal_overshoot(self) -> None:
        self.assertEqual(
            lpsr_population(initial_population=360, minimum_population=3, budget=50000, used_budget=50002),
            3,
        )

    def test_lpsr_invalid_bounds_fail(self) -> None:
        with self.assertRaises(ControlError):
            lpsr_population(initial_population=2, minimum_population=3, budget=10, used_budget=0)

    def test_schedule_explains_overshoot(self) -> None:
        result = evaluation_schedule(initial_population=360, minimum_population=3, budget=50000)
        self.assertEqual((result.generations, result.used_budget), (582, 49642))
        self.assertEqual((result.logged_evaluations, result.terminal_population), (50002, 6))

    def test_tie_selects_offspring_without_improvement(self) -> None:
        sources, improved = replacement_sources([1], [1])
        self.assertEqual(sources, ("offspring",))
        self.assertEqual(improved, (False,))

    def test_replacement_fixture(self) -> None:
        sources, improved = replacement_sources([1, 2, 3], [1, 1.5, 4])
        self.assertEqual(sources, ("offspring", "offspring", "parent"))
        self.assertEqual(improved, (False, True, False))

    def test_replacement_shape_mismatch_fails(self) -> None:
        with self.assertRaises(ControlError):
            replacement_sources([1], [1, 2])


class FixtureReportTests(unittest.TestCase):
    def test_complete_fixture_report_matches_contract(self) -> None:
        report = fixture_report(load_contract())
        self.assertEqual(report["memory_CR"], "0.44285714285714285714285714285714285714285714285714")
        self.assertEqual(report["schedule"]["logged_evaluations"], 50002)

    def test_fraction_rendering_terminating(self) -> None:
        self.assertEqual(fraction_decimal(Fraction(1, 10)), "0.1")

    def test_fraction_rendering_repeating_requires_places(self) -> None:
        with self.assertRaises(ControlError):
            fraction_decimal(Fraction(1, 3))

    def test_fraction_rendering_rounds_ties_even(self) -> None:
        self.assertEqual(fraction_decimal(Fraction(1, 8), places=2), "0.12")
        self.assertEqual(fraction_decimal(Fraction(3, 8), places=2), "0.38")


if __name__ == "__main__":
    unittest.main()
