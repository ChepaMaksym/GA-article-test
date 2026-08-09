from __future__ import annotations

import math
import unittest

from eu2615 import GarboFuzzySystem, ZeroAreaError, load_fixtures


class FuzzyTransitionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.system = GarboFuzzySystem()
        cls.fixture = load_fixtures()
        cls.tolerance = cls.fixture["absolute_tolerance"]

    def assertClose(self, actual, expected):
        self.assertTrue(
            math.isfinite(actual),
            msg=f"nonfinite actual value for expected {expected}",
        )
        self.assertLessEqual(
            abs(actual - expected),
            self.tolerance,
            msg=f"{actual!r} != {expected!r}",
        )

    def assertTransition(self, actual, expected):
        self.assertEqual(actual.branch, expected["branch"])
        self.assertClose(actual.cxpb, expected["cxpb"])
        self.assertClose(actual.mutpb, expected["mutpb"])
        self.assertEqual(len(actual.mutop), 3)
        for observed, target in zip(actual.mutop, expected["mutop"]):
            self.assertClose(observed, target)

    def test_numpy_arange_endpoint_semantics(self):
        for name, expected in self.fixture["universe_endpoints"].items():
            with self.subTest(universe=name):
                actual = self.system.universe(name)
                self.assertEqual(len(actual), expected["length"])
                self.assertEqual(actual[0], expected["first"])
                self.assertEqual(actual[-1], expected["last"])
        self.assertGreater(0.699, self.system.universe("fv")[-1])
        self.assertLess(self.system.universe("pi")[-1], 0.4)

    def test_every_frozen_transition_case(self):
        for case in self.fixture["transition_cases"]:
            with self.subTest(case=case["id"]):
                actual = self.system.transition_from_statistics(
                    case["fv"], case["ft"], case["mlc"], case["ssc"]
                )
                self.assertTransition(actual, case["expected"])

    def test_population_statistics_and_transition(self):
        case = self.fixture["population_case"]
        statistics, transition = self.system.transition_from_population(
            case["fitness"],
            case["previous_mean_fitness"],
            case["chromosomes"],
        )
        for name, expected in case["expected_statistics"].items():
            self.assertClose(getattr(statistics, name), expected)
        self.assertClose(statistics.mean_fitness, 0.6)
        self.assertTransition(transition, case["expected_transition"])

    def test_all_feature_rank_rules(self):
        for case in self.fixture["feature_rank_cases"]:
            with self.subTest(case=case["id"]):
                actual = self.system.feature_rank_delta(
                    case["usage"], case["benefit"]
                )
                self.assertClose(actual, case["expected_delta"])

    def test_mutation_uses_intfv_not_intft(self):
        int_fv = self.system.memberships("fv", 0.015)
        int_ft = self.system.memberships("ft", 0.015)
        self.assertClose(int_fv["low"], 0.5)
        self.assertClose(int_fv["med"], 0.0)
        self.assertClose(int_ft["low"], 0.0)
        self.assertClose(int_ft["med"], 1.0)
        actual = self.system.mutation_probability(0.015, 20.0)
        self.assertClose(actual, 0.2)
        self.assertGreater(abs(actual - 0.15), 0.04)

    def test_similarity_threshold_is_strict_and_precedes_fuzzy_rules(self):
        at_threshold = self.system.transition_from_statistics(0.05, 0.015, 20, 0.75)
        above_threshold = self.system.transition_from_statistics(
            0.699, 0.699, 200.0, 0.7500000001
        )
        self.assertEqual(at_threshold.branch, "fuzzy")
        self.assertEqual(above_threshold.branch, "similarity_override")
        self.assertEqual(above_threshold.mutop, (0.9, 0.1, 0.0))

    def test_mutop_is_source_complement_without_extra_normalization(self):
        for case in self.fixture["transition_cases"]:
            expected = case["expected"]
            if expected["branch"] != "fuzzy":
                continue
            with self.subTest(case=case["id"]):
                actual = self.system.mutation_operator_probabilities(
                    case["ssc"], case["mlc"]
                )
                self.assertClose(actual[2], 1.0 - (actual[0] + actual[1]))
                self.assertClose(sum(actual), 1.0)

    def test_decimal_0699_fails_zero_area_on_fuzzy_branch(self):
        with self.assertRaises(ZeroAreaError):
            self.system.transition_from_statistics(0.699, 0.05, 20.0, 0.75)

    def test_mlc_200_fails_zero_area_on_fuzzy_branch(self):
        with self.assertRaises(ZeroAreaError):
            self.system.transition_from_statistics(0.05, 0.05, 200.0, 0.75)

    def test_nonfinite_statistics_fail_closed(self):
        for value in (float("nan"), float("inf"), float("-inf")):
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.system.transition_from_statistics(value, 0.05, 20.0, 0.3)

    def test_population_zero_max_fitness_fails_closed(self):
        with self.assertRaises(ValueError):
            self.system.transition_from_population(
                [0.0, 0.0], 0.0, [[1], [2]]
            )

    def test_population_without_pair_fails_closed(self):
        with self.assertRaises(ValueError):
            self.system.transition_from_population([0.5], 0.4, [[1]])

    def test_population_empty_union_fails_closed(self):
        with self.assertRaises(ValueError):
            self.system.transition_from_population(
                [0.5, 0.4], 0.45, [[], []]
            )

    def test_duplicate_gene_input_fails_closed(self):
        with self.assertRaises(ValueError):
            self.system.transition_from_population(
                [0.5, 0.4], 0.45, [[1, 1], [2]]
            )


if __name__ == "__main__":
    unittest.main()
