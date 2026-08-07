from __future__ import annotations

import json
import math
from pathlib import Path
import sys
import unittest


CANDIDATE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(CANDIDATE / "environments" / "python"))

from banditverify.objectives import OBJECTIVES, evaluate_objective  # noqa: E402


class ObjectiveTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.fixture = json.loads(
            (CANDIDATE / "fixtures" / "formula_oracles.json").read_text()
        )
        cls.atol = cls.fixture["tolerance"]["absolute"]
        cls.rtol = cls.fixture["tolerance"]["relative"]

    def assertOracle(self, actual: float, expected: float) -> None:  # noqa: N802
        self.assertTrue(
            math.isclose(actual, expected, abs_tol=self.atol, rel_tol=self.rtol),
            (actual, expected),
        )

    def test_all_six_mixed_vector_oracles(self) -> None:
        anchor = self.fixture["objective_anchors"]["mixed5"]
        self.assertEqual(set(anchor["expected"]), set(OBJECTIVES))
        for name, expected in anchor["expected"].items():
            with self.subTest(name=name):
                self.assertOracle(evaluate_objective(name, anchor["vector"]), expected)

    def test_paper_global_minimum_anchors(self) -> None:
        zero = self.fixture["objective_anchors"]["zero5"]
        one = self.fixture["objective_anchors"]["one5"]
        for name, expected in zero["expected"].items():
            with self.subTest(name=name):
                self.assertOracle(evaluate_objective(name, zero["vector"]), expected)
        self.assertEqual(evaluate_objective("rosenbrock", one["vector"]), 0.0)

    def test_one_based_griewank_index_is_discriminating(self) -> None:
        x = [0.0, math.pi * math.sqrt(2.0)]
        expected = math.fsum(value * value for value in x) / 4000.0 + 2.0
        self.assertOracle(evaluate_objective("griewank", x), expected)

    def test_deterministic_properties_on_grid(self) -> None:
        for step in range(1, 25):
            x = [(index - 3) * step / 17.0 for index in range(7)]
            self.assertGreaterEqual(evaluate_objective("sphere", x), 0.0)
            self.assertGreaterEqual(evaluate_objective("rastrigin", x), -self.atol)
            self.assertEqual(
                evaluate_objective("sphere", x),
                evaluate_objective("sphere", [-value for value in x]),
            )

    def test_invalid_inputs_fail_closed(self) -> None:
        invalid = ([], [0.0, math.inf], [math.nan], [True, 0.0], "123")
        for value in invalid:
            with self.subTest(value=value), self.assertRaises((TypeError, ValueError)):
                evaluate_objective("sphere", value)
        with self.assertRaises(ValueError):
            evaluate_objective("rosenbrock", [1.0])
        with self.assertRaises(ValueError):
            evaluate_objective("not-a-function", [0.0, 1.0])


if __name__ == "__main__":
    unittest.main()
