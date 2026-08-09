from __future__ import annotations

import json
from pathlib import Path
import sys
import unittest

import numpy as np


CANDIDATE_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(CANDIDATE_ROOT / "environments" / "python"))

from eu2617 import RateState, SAGA1Config, adjust_rates, calc_gdm, run_trajectory  # noqa: E402


class FormulaTests(unittest.TestCase):
    def test_shared_cross_language_fixture(self) -> None:
        fixture = json.loads(
            (CANDIDATE_ROOT / "fixtures" / "transition_cases.json").read_text(
                encoding="utf-8"
            )
        )
        config = SAGA1Config(**fixture["config"])
        for case in fixture["cases"]:
            with self.subTest(case=case["name"]):
                result = adjust_rates(
                    case["fitness"], RateState(**case["state"]), config
                )
                expected = case["expected"]
                self.assertAlmostEqual(
                    result.gdm, expected["gdm"], delta=fixture["tolerance"]
                )
                self.assertAlmostEqual(
                    result.current.mutation_rate,
                    expected["mutation_rate"],
                    delta=fixture["tolerance"],
                )
                self.assertAlmostEqual(
                    result.current.crossover_rate,
                    expected["crossover_rate"],
                    delta=fixture["tolerance"],
                )
                self.assertEqual(result.branch, expected["branch"])

    def test_exact_threshold_equalities_do_not_change_rates(self) -> None:
        config = SAGA1Config()
        at_min = np.zeros(200)
        at_min[0] = 1.0
        at_max = np.zeros(20)
        at_max[:3] = 1.0
        for fitness, expected in ((at_min, config.v_min), (at_max, config.v_max)):
            with self.subTest(expected=expected):
                result = adjust_rates(fitness)
                self.assertEqual(result.gdm, expected)
                self.assertEqual(result.current, RateState())
                self.assertEqual(result.branch, "no_change")

    def test_repeated_updates_reach_and_retain_all_bounds(self) -> None:
        high = run_trajectory([[1.0, 1.0]] * 100)
        self.assertEqual(high[-1].current.mutation_rate, 0.25)
        self.assertEqual(high[-1].current.crossover_rate, 0.5)
        low = run_trajectory(
            [[-0.999, 1.0]] * 200,
            state=high[-1].current,
        )
        self.assertEqual(low[-1].current.mutation_rate, 0.001)
        self.assertEqual(low[-1].current.crossover_rate, 1.0)

    def test_invalid_fitness_fails_closed(self) -> None:
        invalid = (
            [],
            [[1.0, 2.0]],
            [np.nan, 1.0],
            [np.inf, 1.0],
            [0.0, 0.0],
            [-1.0, 0.0],
        )
        for value in invalid:
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    calc_gdm(value)

    def test_invalid_config_and_state_fail_closed(self) -> None:
        invalid_configs = (
            SAGA1Config(v_min=0.15),
            SAGA1Config(v_min=-0.1),
            SAGA1Config(mutation_rate_min=0.3, mutation_rate_max=0.2),
            SAGA1Config(crossover_rate_max=1.1),
            SAGA1Config(mutation_rate_multiplier=1.0),
            SAGA1Config(crossover_rate_multiplier=np.nan),
        )
        for config in invalid_configs:
            with self.subTest(config=config):
                with self.assertRaises(ValueError):
                    adjust_rates([1.0, 1.0], config=config)
        for state in (
            RateState(0.0, 0.75),
            RateState(0.025, 0.4),
            RateState(np.nan, 0.75),
        ):
            with self.subTest(state=state):
                with self.assertRaises(ValueError):
                    adjust_rates([1.0, 1.0], state=state)


if __name__ == "__main__":
    unittest.main()
