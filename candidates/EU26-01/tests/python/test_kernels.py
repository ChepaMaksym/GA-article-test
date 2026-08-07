from __future__ import annotations

from fractions import Fraction
import itertools
import json
from pathlib import Path
import unittest

from tworateverify.kernels import (
    FormulaValidationError,
    adapt_two_rate,
    generation_from_tape,
    hypervolume_2d,
    mutate_bits,
    mutation_probabilities,
    oneminmax,
    pareto_insert,
    validate_fixture,
    zero_truncated_binomial_count,
)


CANDIDATE = Path(__file__).resolve().parents[2]
FIXTURE = CANDIDATE / "fixtures" / "tworate_fixed_tape.json"


def brute_hv(points: list[tuple[int, int]], reference: tuple[int, int]) -> int:
    maximum_x = max(point[0] for point in points)
    maximum_y = max(point[1] for point in points)
    return sum(
        1
        for x in range(reference[0] + 1, maximum_x + 1)
        for y in range(reference[1] + 1, maximum_y + 1)
        if any(point[0] >= x and point[1] >= y for point in points)
    )


class ObjectiveAndHypervolumeTests(unittest.TestCase):
    def test_oneminmax_exhaustive_small_dimension(self):
        for bits in itertools.product((0, 1), repeat=6):
            with self.subTest(bits=bits):
                point = oneminmax(bits)
                self.assertEqual(point[0], sum(bits))
                self.assertEqual(sum(point), 6)

    def test_oneminmax_rejects_invalid_bits(self):
        for value in ([], "", "0102", [0, True], [0, 2], None):
            with self.subTest(value=value):
                with self.assertRaises(FormulaValidationError):
                    oneminmax(value)

    def test_hypervolume_hand_values_and_permutations(self):
        points = [(49, 51), (50, 50), (51, 49)]
        self.assertEqual(hypervolume_2d([(50, 50)]), 2601)
        self.assertEqual(hypervolume_2d(points), 2701)
        for permutation in itertools.permutations(points):
            self.assertEqual(hypervolume_2d(permutation), 2701)

    def test_hypervolume_matches_brute_union(self):
        reference = (-1, -1)
        universe = [(x, y) for x in range(4) for y in range(4)]
        for size in range(1, 5):
            for points in itertools.combinations(universe, size):
                with self.subTest(points=points):
                    self.assertEqual(
                        hypervolume_2d(points, reference),
                        brute_hv(list(points), reference),
                    )

    def test_hypervolume_rejects_bad_reference_and_nonfinite(self):
        for points, reference in (([(0, 0)], (1, 1)), ([(0, float("nan"))], (-1, -1))):
            with self.subTest(points=points, reference=reference):
                with self.assertRaises(FormulaValidationError):
                    hypervolume_2d(points, reference)


class TransitionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))

    def test_frozen_fixture(self):
        result = validate_fixture(self.fixture)
        self.assertEqual(len(result["adaptation_cases"]), 5)
        self.assertEqual(len(result["generation_cases"]), 1)
        self.assertEqual(len(result["invalid_generation_cases"]), 4)

    def test_generation_is_repeatable(self):
        case = self.fixture["generation_cases"][0]
        self.assertEqual(generation_from_tape(case), generation_from_tape(case))

    def test_five_five_rate_assignment(self):
        rates = mutation_probabilities(1, 100, 10)
        self.assertEqual(rates[:5], [Fraction(1, 200)] * 5)
        self.assertEqual(rates[5:], [Fraction(1, 50)] * 5)

    def test_first_maximum_and_q_boundary(self):
        result = adapt_two_rate(
            [(50, 50)],
            [(49, 51)] + [(50, 50)] * 4 + [(51, 49)] + [(50, 50)] * 4,
            2,
            Fraction(3, 4),
            n=100,
        )
        self.assertEqual(result["winner_index"], 0)
        self.assertEqual(result["decision"], "halve")
        self.assertEqual(result["r_after"], 1)

    def test_duplicate_replacement_does_not_enlarge_population(self):
        self.assertEqual(pareto_insert([(50, 50)], (50, 50)), [(50, 50)])

    def test_zero_truncation_and_flip_validation(self):
        self.assertEqual(zero_truncated_binomial_count([0, 0, 3], 10), 3)
        self.assertEqual(mutate_bits("1100", [0, 3]), (0, 1, 0, 1))
        invalid_operations = (
            lambda: zero_truncated_binomial_count([0], 10),
            lambda: zero_truncated_binomial_count([1, 0], 10),
            lambda: mutate_bits("1100", [0, 0]),
            lambda: mutate_bits("1100", [4]),
        )
        for operation in invalid_operations:
            with self.assertRaises(FormulaValidationError):
                operation()

    def test_invalid_q_and_strength_fail_closed(self):
        children = [(50, 50)] * 10
        for r, q in ((0, 0), (26, 0), (1, -1), (1, "NaN"), (1, float("inf"))):
            with self.subTest(r=r, q=q):
                with self.assertRaises(FormulaValidationError):
                    adapt_two_rate([(50, 50)], children, r, q, n=100)


if __name__ == "__main__":
    unittest.main()
