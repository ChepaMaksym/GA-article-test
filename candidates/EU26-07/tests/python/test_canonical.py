from __future__ import annotations

import json
import math
import unittest
from pathlib import Path

from eu2607.canonical import (
    ARTIFACT_GENERIC,
    PAPER_ALGORITHM3,
    Profile,
    controls,
    crossover_from_mutant_positions,
    fixed_tape_generation,
    jump_fitness,
    mutate_exact_positions,
    next_lambda,
    rounded_offspring,
)


CANDIDATE = Path(__file__).resolve().parents[2]
FIXTURE = CANDIDATE / "fixtures" / "fixed_tape_cases.json"


class CanonicalPolicyTests(unittest.TestCase):
    def test_jump_definition_local_optimum_valley_and_global_target(self):
        self.assertEqual(jump_fitness((1 << 16) - 1, 20, 4), (20, False))
        self.assertEqual(jump_fitness((1 << 17) - 1, 20, 4), (3, False))
        self.assertEqual(jump_fitness((1 << 20) - 1, 20, 4), (24, True))

    def test_dimension_and_domain_fail_closed(self):
        with self.assertRaises(ValueError):
            jump_fitness(0, 10, 4)
        with self.assertRaises(ValueError):
            jump_fitness(1 << 20, 20, 4)
        with self.assertRaises(TypeError):
            jump_fitness(True, 20, 4)

    def test_profile_rounding_is_explicit(self):
        self.assertEqual(rounded_offspring(2.5, PAPER_ALGORITHM3), 3)
        self.assertEqual(rounded_offspring(2.5, ARTIFACT_GENERIC), 2)
        self.assertEqual(rounded_offspring(3.5, PAPER_ALGORITHM3), 4)
        self.assertEqual(rounded_offspring(3.5, ARTIFACT_GENERIC), 4)

    def test_controls_use_real_lambda_and_coefficient_one(self):
        value = controls(2.5, 20, PAPER_ALGORITHM3)
        self.assertEqual(value.offspring_count, 3)
        self.assertEqual(value.mutation_probability, 0.125)
        self.assertEqual(value.crossover_probability, 0.4)
        with self.assertRaisesRegex(ValueError, "coefficient 1"):
            controls(2.5, 20, PAPER_ALGORITHM3, crossover_coefficient=0.5)
        for illegal in (True, "2.5"):
            with self.subTest(illegal=illegal), self.assertRaises(TypeError):
                controls(illegal, 20, PAPER_ALGORITHM3)

    def test_profiles_cannot_be_semantically_mislabeled(self):
        forged = Profile(
            name="paper_algorithm3",
            rounding="python_ties_to_even",
            final_pool="all_mutants_plus_crossover_children",
            jump_shortcuts=True,
        )
        with self.assertRaisesRegex(ValueError, "registered profile"):
            rounded_offspring(2.5, forged)

    def test_shared_exact_mutation_and_biased_crossover_witness(self):
        fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))["operator_case"]
        mutant = mutate_exact_positions(
            fixture["parent"],
            fixture["n"],
            fixture["mutation_positions_zero_based_lsb"],
        )
        self.assertEqual(mutant, fixture["expected_mutant"])
        child = crossover_from_mutant_positions(
            fixture["parent"],
            mutant,
            fixture["n"],
            fixture["crossover_take_mutant_positions_zero_based_lsb"],
        )
        self.assertEqual(child, fixture["expected_crossover"])
        self.assertEqual(mutate_exact_positions(7, 20, []), 7)
        self.assertEqual(crossover_from_mutant_positions(7, 8, 20, []), 7)

    def test_operator_masks_fail_closed(self):
        with self.assertRaisesRegex(ValueError, "distinct"):
            mutate_exact_positions(0, 20, [1, 1])
        with self.assertRaisesRegex(ValueError, "outside"):
            mutate_exact_positions(0, 20, [20])
        with self.assertRaises(TypeError):
            crossover_from_mutant_positions(0, 1, 20, [True])

    def test_fixed_tape_rejects_bool_string_and_fractional_children(self):
        for illegal in (True, "5", 5.9):
            with self.subTest(illegal=illegal), self.assertRaises((TypeError, ValueError)):
                fixed_tape_generation(
                    parent=0,
                    n=20,
                    k=4,
                    lambda_real=1,
                    update_factor=1.5,
                    profile=PAPER_ALGORITHM3,
                    mutation_children=[illegal],
                    crossover_children=[0],
                )

    def test_strict_success_shrinks_and_neutral_failure_grows(self):
        self.assertEqual(
            next_lambda(
                3.0,
                strict_success=True,
                update_factor=1.5,
                lambda_max=20,
            ),
            2.0,
        )
        expected = 3.0 * 1.5 ** 0.25
        self.assertEqual(
            next_lambda(
                3.0,
                strict_success=False,
                update_factor=1.5,
                lambda_max=20,
            ),
            expected,
        )

    def test_reset_occurs_one_failure_after_clamping_to_cap(self):
        at_cap = next_lambda(
            19.0,
            strict_success=False,
            update_factor=1.5,
            lambda_max=20,
        )
        self.assertEqual(at_cap, 20.0)
        self.assertEqual(
            next_lambda(
                at_cap,
                strict_success=False,
                update_factor=1.5,
                lambda_max=20,
            ),
            1.0,
        )
        with self.assertRaisesRegex(TypeError, "reset"):
            next_lambda(
                20.0,
                strict_success=False,
                update_factor=1.5,
                lambda_max=20,
                reset=1,
            )

    def test_shared_fixed_tape_profile_witnesses(self):
        cases = json.loads(FIXTURE.read_text(encoding="utf-8"))["cases"]
        self.assertEqual(len(cases), 2)
        observed = {}
        for case in cases:
            expected = case.pop("expected")
            name = case.pop("name")
            with self.subTest(case=name):
                result = fixed_tape_generation(**case)
                for field, value in expected.items():
                    self.assertEqual(getattr(result, field), value)
                self.assertTrue(math.isclose(result.lambda_after, 2 / 1.5))
                observed[name] = result.selected_candidate
        self.assertNotEqual(
            observed["paper_selected_mutant_pool"],
            observed["artifact_all_mutants_pool"],
        )

    def test_empty_final_pool_is_neutral_and_grows(self):
        result = fixed_tape_generation(
            parent=1023,
            n=20,
            k=4,
            lambda_real=1.0,
            update_factor=1.5,
            profile=PAPER_ALGORITHM3,
            mutation_children=[1023],
            crossover_children=[1023],
        )
        self.assertEqual(result.parent_after, 1023)
        self.assertFalse(result.strict_success)
        self.assertEqual(result.final_pool, ())
        self.assertEqual(result.logical_evaluations, 2)
        self.assertEqual(result.lambda_after, 1.5 ** 0.25)


if __name__ == "__main__":
    unittest.main()
