"""Small software fixtures, never new KPLIB experiment observations."""
from copy import deepcopy
from fractions import Fraction
import os
import unittest

from studies.knapsack_parameters.final_study import endpoints as e


class EndpointTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if os.environ.get("GITHUB_ACTIONS") != "true":
            raise RuntimeError("Checks execute only in CI")

    def test_gap_uses_exact_optimum_and_profit(self):
        self.assertEqual(e.gap_percent(46537, 46510), Fraction(2700, 46537))
        for opt, value in ((0, 0), (5, 6), (5, -1), (5, 1.0)):
            with self.assertRaises(ValueError):
                e.gap_percent(opt, value)

    def test_family_weighting_not_pooled_candidates(self):
        rows = [{"task": "UC-s010", "seed": 1, "value": 0},
                {"task": "UC-s010", "seed": 2, "value": 2},
                {"task": "WC-s010", "seed": 1, "value": 3},
                {"task": "UC-s011", "seed": 1, "value": 10}]
        result = e.family_means(rows)
        self.assertEqual(result, {"s010": Fraction(2), "s011": Fraction(10)})
        self.assertEqual(sum(result.values()) / len(result), 6)
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            e.family_means(rows + [rows[0]])

    def test_final_prefix_record_equal_to_separate_stopped_search(self):
        from studies.adaptive_parameters.mutation_only.engine import run_search, make_rngs, evaluate
        problem = {"n": 3, "capacity": 10, "weights": [6, 5, 5], "profits": [10, 8, 8]}
        masks = ["100"] * 30
        scores = [evaluate(problem, mask) for mask in masks]
        long = run_search(problem, masks, scores, "fixed", make_rngs(19, 0, 0), 70)
        short = run_search(problem, masks, scores, "fixed", make_rngs(19, 0, 0), 57)
        self.assertEqual(e.prefix_record(long, 57), e.prefix_record(short, 57))
        self.assertEqual(long["candidates"][:57], short["candidates"])
        self.assertFalse(short["generations"][-1]["complete"])
        self.assertEqual(e.prefix_record(long, 57)["total_logical_evaluations"], 87)

    def test_last_query_improvement_and_first_tie_retained(self):
        log = {"budget": 2, "problem": {"n": 3, "capacity": 10,
               "weights": [6, 5, 5], "profits": [10, 8, 8]},
               "initial_masks": ["100"], "initial_scores": [{"weight": 6, "profit": 10, "feasible": True}],
               "candidates": [{"call": 1, "mask": "100", "weight": 6, "profit": 10, "feasible": True},
                              {"call": 2, "mask": "011", "weight": 10, "profit": 16, "feasible": True}]}
        self.assertEqual(e.prefix_record(log, 1)["best_new_query"], 0)
        self.assertEqual(e.prefix_record(log, 2)["best_new_query"], 2)
        self.assertEqual(e.prefix_record(log, 2)["best_profit"], 16)
        corrupt = deepcopy(log)
        corrupt["candidates"][-1]["profit"] = 17
        with self.assertRaisesRegex(ValueError, "Corrupted"):
            e.prefix_record(corrupt, 2)

    def test_statistics_cannot_be_released_by_probe(self):
        with self.assertRaisesRegex(ValueError, "BLOCKED_MAIN_RESOURCE_APPROVAL"):
            e.four_gap_intervals([[0, 0, 0, 0]] * 10)

    def test_degenerate_fixture_is_descriptive_not_positive_evidence(self):
        result = e.four_gap_intervals([[0, 0, 0, 0]] * 10, software_fixture=True)
        self.assertEqual(len(result["intervals"]), 4)
        self.assertTrue(all(row["status"] == "DESCRIPTIVE_ONLY" and
                            row["positive_effect_supported"] is False for row in result["intervals"]))
        self.assertEqual([row["rng_entropy"] for row in result["intervals"]], [[91031, k] for k in range(4)])

    def test_family_bootstrap_nondegenerate_fixture_against_independent_scalar_reference(self):
        # Independent scalar arithmetic, jackknife, linear quantile, and NormalDist
        # validate a nondegenerate column of the unchanged vectorized implementation.
        import math
        import numpy as np
        from statistics import NormalDist, fmean
        values = [1, 2, 2, 4, 5, 8]
        rows = [[value, 0, 0, 0] for value in values]
        result = e.four_gap_intervals(rows, software_fixture=True)["intervals"][0]
        rng = np.random.Generator(np.random.PCG64(np.random.SeedSequence([result["derived_seed"]])))
        draws = rng.integers(0, len(values), size=(50000, len(values)))
        samples = [fmean(values[int(index)] for index in draw) for draw in draws]
        observed = fmean(values)
        jack = [fmean(values[:k] + values[k+1:]) for k in range(len(values))]
        delta = [fmean(jack) - value for value in jack]
        acceleration = sum(x**3 for x in delta) / (6 * sum(x*x for x in delta)**1.5)
        bias = (sum(value < observed for value in samples) + 0.5*sum(value == observed for value in samples)) / len(samples)
        normal = NormalDist()
        z0 = normal.inv_cdf(bias)
        samples.sort()
        expected = []
        for tail in (0.00625, 0.99375):
            z = normal.inv_cdf(tail)
            p = normal.cdf(z0 + (z0+z)/(1-acceleration*(z0+z)))
            position = (len(samples)-1)*p
            lo, hi = math.floor(position), math.ceil(position)
            expected.append(samples[lo] + (position-lo)*(samples[hi]-samples[lo]))
        self.assertEqual(result["status"], "INFERENTIAL_BCA")
        self.assertAlmostEqual(result["lower"], expected[0], places=12)
        self.assertAlmostEqual(result["upper"], expected[1], places=12)
