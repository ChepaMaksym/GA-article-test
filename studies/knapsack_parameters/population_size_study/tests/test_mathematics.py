"""Exhaustive teaching fixtures and exact evaluation accounting, for CI only."""
from fractions import Fraction
from itertools import product
import os
import unittest

from studies.knapsack_parameters.population_size_study.mathematics import (
    exact_representation_probability, generation_accounting, minimum_representation_population,
    population_domain, representation_probability)


@unittest.skipUnless(os.environ.get("GITHUB_ACTIONS") == "true", "Mathematical fixtures run only in GitHub Actions")
class PopulationMathematicsTests(unittest.TestCase):
    def test_small_banks_exhaustively(self):
        for n in (1, 2, 3):
            for mu in (2, 3, 4):
                hits = count = 0
                for flat in product((0, 1), repeat=n * (mu - 1)):
                    count += 1
                    hits += int(all(any(flat[row*n+column] for row in range(mu-1)) for column in range(n)))
                self.assertEqual(exact_representation_probability(n, mu), Fraction(hits, count))

    def test_stable_curve_matches_fraction(self):
        for n in (2, 100, 200, 500):
            for mu in (2, 5, 10, 20):
                self.assertAlmostEqual(representation_probability(n, mu), float(exact_representation_probability(n, mu)), places=14)

    def test_confidence_minimum_is_exact(self):
        for n in (1, 100, 200, 500):
            for confidence in (Fraction(1, 2), Fraction(95, 100), Fraction(99, 100)):
                mu = minimum_representation_population(n, confidence)
                self.assertGreaterEqual(exact_representation_probability(n, mu), confidence)
                if mu > 2:
                    self.assertLess(exact_representation_probability(n, mu-1), confidence)

    def test_complete_generation_domain(self):
        lower, upper = population_domain(50000)
        self.assertEqual((lower, upper), (2, 25000))
        self.assertEqual(generation_accounting(lower)["complete_generations"], 49998)
        large = generation_accounting(upper)
        self.assertEqual((large["complete_generations"], large["partial_offspring"]), (1, 1))
        self.assertEqual(generation_accounting(upper+1)["complete_generations"], 0)

    def test_confidence_close_to_one_does_not_round_to_certainty(self):
        confidence = 1 - Fraction(1, 10**30)
        mu = minimum_representation_population(100, confidence)
        self.assertGreaterEqual(exact_representation_probability(100, mu), confidence)
        self.assertLess(exact_representation_probability(100, mu-1), confidence)

    def test_budget_conservation(self):
        for total in (3, 50, 5000, 50000):
            for mu in {2, population_domain(total)[1]}:
                row = generation_accounting(mu, total)
                self.assertEqual(mu + row["complete_generations"] * (mu-1) + row["partial_offspring"], total)

    def test_invalid_arguments(self):
        for value in (True, 0, -1, 2.5):
            with self.assertRaises(ValueError):
                population_domain(value)
        for value in (0, 1, -1):
            with self.assertRaises(ValueError):
                minimum_representation_population(100, value)
