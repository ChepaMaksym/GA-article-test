from __future__ import annotations

import json
import math
from pathlib import Path
import sys
import unittest


CANDIDATE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(CANDIDATE / "environments" / "python"))

from banditverify.rewards import evaluate_reward, printed_eq2_literal  # noqa: E402


class RewardTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.oracle = json.loads(
            (CANDIDATE / "fixtures" / "formula_oracles.json").read_text()
        )["reward_sign"]

    def test_three_frozen_semantics_and_sign_conflict(self) -> None:
        actual = {
            key: evaluate_reward(key, self.oracle["parent"], self.oracle["child"])
            for key in ("P1", "P2", "P3")
        }
        for key, expected in self.oracle["expected"].items():
            self.assertAlmostEqual(actual[key], expected, delta=1e-15)
        self.assertGreater(actual["P2"], 0.0)
        self.assertLess(actual["P3"], 0.0)
        self.assertEqual(actual["P2"], -actual["P3"])

    def test_p1_is_primary_function_min_semantics_without_log(self) -> None:
        self.assertEqual(evaluate_reward("P1", [-10.0], [-20.0]), 10.0)
        with self.assertRaisesRegex(ValueError, "greater than -1"):
            evaluate_reward("P2", [-10.0], [-20.0])
        with self.assertRaisesRegex(ValueError, "greater than -1"):
            evaluate_reward("P3", [-10.0], [-20.0])

    def test_printed_eq2_is_singular_for_function_min_vector(self) -> None:
        with self.assertRaisesRegex(ZeroDivisionError, "m=0"):
            printed_eq2_literal([9.0], [3.0])

    def test_printed_eq2_divisor_differs_from_intended_mean(self) -> None:
        parent = [9.0, 4.0]
        child = [3.0, 1.0]
        literal = printed_eq2_literal(parent, child)
        intended = evaluate_reward("P2", parent, child)
        self.assertAlmostEqual(literal, intended * 2.0)

    def test_vector_means(self) -> None:
        self.assertEqual(evaluate_reward("P1", [5, 9], [1, 3]), 5.0)

    def test_invalid_reward_inputs_fail_closed(self) -> None:
        cases = (
            ("P1", [], []),
            ("P1", [1], [1, 2]),
            ("P1", [math.inf], [0]),
            ("P1", [True], [0]),
            ("P4", [1], [0]),
        )
        for semantics, parent, child in cases:
            with self.subTest(semantics=semantics), self.assertRaises(
                (TypeError, ValueError)
            ):
                evaluate_reward(semantics, parent, child)


if __name__ == "__main__":
    unittest.main()
