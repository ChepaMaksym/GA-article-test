from __future__ import annotations

import dataclasses
import json
import math
import unittest

from eu2616.contract import candidate_root
from eu2616.transition import (
    GUARD_DOUBLE_STEP,
    GUARD_UPPER,
    ControlState,
    initial_state,
    java_float,
    round_best_fitness,
    transition_generation,
)


class FrozenFixtureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        path = candidate_root() / "fixtures" / "transition_cases.json"
        cls.fixture = json.loads(path.read_text(encoding="utf-8"))

    def test_every_frozen_case(self) -> None:
        tolerance = self.fixture["tolerance"]
        for case in self.fixture["cases"]:
            with self.subTest(case=case["name"]):
                state = ControlState(**case["state"])
                next_state, event = transition_generation(
                    state,
                    generation=case["generation"],
                    current_best_fitness=case["current_best_fitness"],
                    current_average_fitness=case["current_average_fitness"],
                    max_generations=case["max_generations"],
                )
                observed = {**dataclasses.asdict(next_state), **dataclasses.asdict(event)}
                for key, expected in case["expected"].items():
                    if isinstance(expected, float):
                        source_expected = (
                            java_float(expected)
                            if key in {"best_average_fitness", "best_fitness"}
                            else expected
                        )
                        self.assertAlmostEqual(observed[key], source_expected, delta=tolerance)
                    else:
                        self.assertEqual(observed[key], expected)
                self.assertAlmostEqual(
                    next_state.crossover_probability + next_state.mutation_probability,
                    1.0,
                    delta=tolerance,
                )

    def test_fixture_names_are_unique(self) -> None:
        names = [case["name"] for case in self.fixture["cases"]]
        self.assertEqual(len(names), len(set(names)))

    def test_fixture_has_both_off_lattice_directions(self) -> None:
        names = {case["name"] for case in self.fixture["cases"]}
        self.assertIn("off_lattice_improvement_is_not_clamped", names)
        self.assertIn("off_lattice_non_improvement_is_not_clamped", names)


class TransitionSemanticsTests(unittest.TestCase):
    def test_initial_state_matches_source(self) -> None:
        self.assertEqual(initial_state(), ControlState(0.5, 0.5, 0.0, -1.0, 0))

    def test_guard_thresholds_are_java_float_expressions(self) -> None:
        self.assertEqual(GUARD_DOUBLE_STEP, java_float(java_float(0.02) * 2.0))
        self.assertEqual(GUARD_UPPER, java_float(1.0 - GUARD_DOUBLE_STEP))
        self.assertLess(GUARD_UPPER, 0.96)
        self.assertLess(GUARD_DOUBLE_STEP, 0.04)

    def test_repeated_improvements_stop_at_publication_lattice_endpoint(self) -> None:
        state = initial_state()
        for generation in range(1, 31):
            state, _ = transition_generation(
                state,
                generation=generation,
                current_best_fitness=0.5 + generation / 10_000,
                current_average_fitness=generation / 100,
                max_generations=200,
            )
        self.assertAlmostEqual(state.crossover_probability, 0.96, delta=1e-12)
        self.assertAlmostEqual(state.mutation_probability, 0.04, delta=1e-12)
        self.assertAlmostEqual(state.best_average_fitness, java_float(0.30), delta=1e-12)

    def test_repeated_non_improvements_stop_at_opposite_lattice_endpoint(self) -> None:
        state = ControlState(0.5, 0.5, java_float(1.0), java_float(-1.0), 0)
        for generation in range(1, 31):
            state, _ = transition_generation(
                state,
                generation=generation,
                current_best_fitness=-1.0,
                current_average_fitness=0.5,
                max_generations=200,
            )
        self.assertAlmostEqual(state.crossover_probability, 0.04, delta=1e-12)
        self.assertAlmostEqual(state.mutation_probability, 0.96, delta=1e-12)

    def test_improvement_guard_is_not_a_clamp(self) -> None:
        state = ControlState(0.95, 0.05, 0.2, 0.5, 1)
        state, event = transition_generation(
            state,
            generation=2,
            current_best_fitness=0.5,
            current_average_fitness=0.3,
            max_generations=200,
        )
        self.assertAlmostEqual(state.crossover_probability, 0.97, delta=1e-12)
        self.assertAlmostEqual(state.mutation_probability, 0.03, delta=1e-12)
        self.assertTrue(event.probabilities_changed)

    def test_best_average_updates_even_when_guard_blocks(self) -> None:
        state = ControlState(0.96, 0.04, 0.2, 0.5, 1)
        state, event = transition_generation(
            state,
            generation=2,
            current_best_fitness=0.5,
            current_average_fitness=0.3,
            max_generations=200,
        )
        self.assertEqual(state.best_average_fitness, java_float(0.3))
        self.assertFalse(event.probabilities_changed)

    def test_equality_is_non_improvement(self) -> None:
        state = ControlState(0.5, 0.5, java_float(0.2), 0.5, 1)
        _, event = transition_generation(
            state,
            generation=2,
            current_best_fitness=0.5,
            current_average_fitness=0.2,
            max_generations=200,
        )
        self.assertEqual(event.average_branch, "non_improvement")

    def test_maximum_generation_check_occurs_after_rate_change(self) -> None:
        state, event = transition_generation(
            initial_state(),
            generation=1,
            current_best_fitness=0.1,
            current_average_fitness=0.1,
            max_generations=1,
        )
        self.assertAlmostEqual(state.crossover_probability, 0.52, delta=1e-12)
        self.assertTrue(event.should_stop)
        self.assertEqual(event.stop_reason, "max_generations")

    def test_rounded_improvement_resets_stop_clock_before_check(self) -> None:
        state = ControlState(0.5, 0.5, 0.3, 0.5, 1)
        state, event = transition_generation(
            state,
            generation=11,
            current_best_fitness=0.50006,
            current_average_fitness=0.31,
            max_generations=200,
        )
        self.assertEqual(state.last_best_generation, 11)
        self.assertFalse(event.should_stop)

    def test_stagnation_requires_positive_best(self) -> None:
        state = ControlState(0.5, 0.5, 0.3, -0.1, 0)
        _, event = transition_generation(
            state,
            generation=100,
            current_best_fitness=-0.1,
            current_average_fitness=0.2,
            max_generations=200,
        )
        self.assertFalse(event.should_stop)

    def test_max_generation_precedes_stagnation_reason(self) -> None:
        state = ControlState(0.5, 0.5, 0.3, 0.5, 0)
        _, event = transition_generation(
            state,
            generation=10,
            current_best_fitness=0.5,
            current_average_fitness=0.2,
            max_generations=10,
        )
        self.assertEqual(event.stop_reason, "max_generations")


class FloatRoundingAndValidationTests(unittest.TestCase):
    def test_rounds_down_to_four_decimals(self) -> None:
        self.assertAlmostEqual(round_best_fitness(0.12344), 0.1234, delta=1e-7)

    def test_rounds_half_up_after_java_float_cast(self) -> None:
        self.assertAlmostEqual(round_best_fitness(0.12345), 0.1235, delta=1e-7)

    def test_negative_rounding_matches_java_math_round(self) -> None:
        self.assertAlmostEqual(round_best_fitness(-0.12345), -0.1234, delta=1e-7)

    def test_rejects_probability_sum_mismatch(self) -> None:
        with self.assertRaises(ValueError):
            ControlState(0.5, 0.4, 0.0, -1.0, 0).validate()

    def test_rejects_probability_out_of_range(self) -> None:
        with self.assertRaises(ValueError):
            ControlState(1.01, -0.01, 0.0, -1.0, 0).validate()

    def test_rejects_nan_fitness(self) -> None:
        with self.assertRaises(ValueError):
            round_best_fitness(math.nan)

    def test_rejects_boolean_generation(self) -> None:
        with self.assertRaises(ValueError):
            transition_generation(
                initial_state(),
                generation=True,
                current_best_fitness=0.1,
                current_average_fitness=0.1,
                max_generations=200,
            )

    def test_rejects_nonpositive_maximum(self) -> None:
        with self.assertRaises(ValueError):
            transition_generation(
                initial_state(),
                generation=1,
                current_best_fitness=0.1,
                current_average_fitness=0.1,
                max_generations=0,
            )


if __name__ == "__main__":
    unittest.main()
