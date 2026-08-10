#!/usr/bin/env python3
"""Formula and ordering tests for the EU26-18 clean-room kernel."""

from __future__ import annotations

import math
from pathlib import Path
import sys
import unittest


VERIFICATION_ROOT = Path(__file__).resolve().parents[1] / "verification"
sys.path.insert(0, str(VERIFICATION_ROOT))

from reference_sa_plm import (  # noqa: E402
    REFERENCE_PROFILE,
    algorithm_3_novelty_step,
    mutate_vector,
    paper_mutation_probability,
    polynomial_mutation_coordinate,
    update_distribution_index,
)


class AlgorithmFourTests(unittest.TestCase):
    def test_mean_one_perturbation_and_both_parent_updates(self) -> None:
        eta, parents = update_distribution_index([10.0, 20.0], 0.25)
        self.assertEqual(eta, 15.25)
        self.assertEqual(parents, (15.25, 15.25))

    def test_declared_repair_profile_clamps_both_sides(self) -> None:
        self.assertEqual(update_distribution_index([1.0, 1.0], -2.0)[0], 1.0)
        self.assertEqual(
            update_distribution_index([100.0, 100.0], 2.0)[0], 100.0
        )

    def test_invalid_algorithm_four_inputs_fail_closed(self) -> None:
        invalid_calls = [
            lambda: update_distribution_index([], 0.0),
            lambda: update_distribution_index([float("nan")], 0.0),
            lambda: update_distribution_index([10.0], float("inf")),
            lambda: update_distribution_index([0.0], 0.0),
            lambda: update_distribution_index([10.0], 0.0, 5.0, 5.0),
        ]
        for invalid_call in invalid_calls:
            with self.subTest(call=invalid_call):
                with self.assertRaises(ValueError):
                    invalid_call()


class AlgorithmTwoTests(unittest.TestCase):
    def test_left_and_right_formula_golden_values(self) -> None:
        left = polynomial_mutation_coordinate(0.5, 0.0, 1.0, 20.0, 0.25)
        right = polynomial_mutation_coordinate(0.5, 0.0, 1.0, 20.0, 0.75)
        self.assertEqual(left.hex(), "0x1.dec0a803d530ap-2")
        self.assertEqual(right.hex(), "0x1.109fabfe1567bp-1")
        self.assertEqual(left + right, 1.0)

    def test_paper_scale_oracles_under_declared_x_c_equals_x_profile(self) -> None:
        self.assertAlmostEqual(
            polynomial_mutation_coordinate(3.0, 0.0, 10.0, 20.0, 0.25),
            2.675575055329454,
            places=14,
        )
        self.assertEqual(
            polynomial_mutation_coordinate(3.0, 0.0, 10.0, 20.0, 0.5), 3.0
        )
        self.assertAlmostEqual(
            polynomial_mutation_coordinate(3.0, 0.0, 10.0, 20.0, 0.75),
            3.324682214756264,
            places=14,
        )

    def test_branch_boundary_and_variable_bounds(self) -> None:
        for eta in (1.0, 100.0):
            self.assertEqual(
                polynomial_mutation_coordinate(0.5, 0.0, 1.0, eta, 0.5), 0.5
            )
            self.assertEqual(
                polynomial_mutation_coordinate(0.0, 0.0, 1.0, eta, 0.0), 0.0
            )
            self.assertEqual(
                polynomial_mutation_coordinate(1.0, 0.0, 1.0, eta, 1.0), 1.0
            )
        just_right = math.nextafter(0.5, 1.0)
        nextafter_result = polynomial_mutation_coordinate(
            0.5, 0.0, 1.0, 20.0, just_right
        )
        # The right branch is selected, but its sub-ULP displacement may round
        # back to the midpoint. A resolvable right-side input must move right.
        self.assertGreaterEqual(nextafter_result, 0.5)
        self.assertGreater(
            polynomial_mutation_coordinate(0.5, 0.0, 1.0, 20.0, 0.500001),
            0.5,
        )

    def test_lower_eta_is_stronger_for_one_fixed_random_draw(self) -> None:
        weak_index = polynomial_mutation_coordinate(0.25, 0.0, 1.0, 1.0, 0.25)
        strong_index = polynomial_mutation_coordinate(
            0.25, 0.0, 1.0, 100.0, 0.25
        )
        self.assertGreater(abs(weak_index - 0.25), abs(strong_index - 0.25))

    def test_mutation_gate_is_strictly_less_than_pm(self) -> None:
        values = (0.5, 0.5, 0.5)
        result = mutate_vector(
            values,
            (0.0, 0.0, 0.0),
            (1.0, 1.0, 1.0),
            20.0,
            0.25,
            (0.24, 0.25, 0.26),
            (0.25, 0.25, 0.25),
        )
        self.assertNotEqual(result[0], values[0])
        self.assertEqual(result[1:], values[1:])

    def test_paper_probability_uses_decision_dimension_not_eta_gene(self) -> None:
        self.assertEqual(paper_mutation_probability(4), 0.25)
        self.assertNotEqual(paper_mutation_probability(4), 1.0 / 5.0)
        with self.assertRaises(ValueError):
            paper_mutation_probability(0)
        with self.assertRaises(TypeError):
            paper_mutation_probability(True)


class AlgorithmThreeOrderingTests(unittest.TestCase):
    def test_update_precedes_external_crossover_and_child_mutation(self) -> None:
        result = algorithm_3_novelty_step(
            parent_etas=(10.0, 20.0),
            gaussian_perturbation=0.25,
            crossover_children=((0.5, 0.25), (0.5, 0.75)),
            lower_bounds=(0.0, 0.0),
            upper_bounds=(1.0, 1.0),
            mutation_probability=1.0,
            gate_uniforms=((0.0, 0.0), (0.0, 0.0)),
            mutation_uniforms=((0.25, 0.75), (0.75, 0.25)),
        )
        self.assertEqual(
            result.events,
            (
                "algorithm3.line6.select_parents_external",
                "algorithm3.line7.update_distribution_index",
                "algorithm3.line8.sbx_crossover_external",
                "algorithm3.line9.mutate_child1",
                "algorithm3.line10.mutate_child2",
                "algorithm3.line11.append_offspring_pair",
            ),
        )
        self.assertEqual(result.parent_eta_after, (15.25, 15.25))
        self.assertEqual(result.child_eta, (15.25, 15.25))

    def test_every_ambiguous_choice_is_named(self) -> None:
        self.assertEqual(
            set(REFERENCE_PROFILE),
            {
                "profile_id",
                "repair_semantics",
                "algorithm_2_current_value",
                "parent_update_semantics",
                "strategy_inheritance",
                "crossover_scope",
                "rng_scope",
            },
        )
        self.assertIn("assumption", REFERENCE_PROFILE["repair_semantics"])
        self.assertIn("undefined_x_c", REFERENCE_PROFILE["algorithm_2_current_value"])
        self.assertIn("external", REFERENCE_PROFILE["crossover_scope"])


if __name__ == "__main__":
    unittest.main()
