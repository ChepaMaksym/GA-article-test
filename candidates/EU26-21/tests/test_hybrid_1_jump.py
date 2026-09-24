#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from hybrid_1.benchmarks import (  # noqa: E402
    JumpObjective,
    jump_local_optimum,
    run_jump_campaign,
    run_onemax_pair,
    summarize_jump,
)


class HybridOneJumpTests(unittest.TestCase):
    def test_jump_landscape_critical_points(self) -> None:
        objective = JumpObjective(3)
        local = jump_local_optimum(20, 3)
        optimum = tuple([1] * 20)
        valley = tuple([1] * 18 + [0] * 2)
        self.assertEqual(objective(local)[0], 20.0)
        self.assertEqual(objective(optimum)[0], 23.0)
        self.assertEqual(objective(valley)[0], 2.0)

    def test_reset_has_preregistered_meaningful_jump_gain(self) -> None:
        rows = run_jump_campaign(
            n=20,
            k=3,
            seeds=range(101, 121),
            budget=10000,
            campaign_workers=4,
            evaluation_workers=1,
        )
        summary = summarize_jump(rows)
        self.assertGreater(int(summary["total_reset_events"]), 0)
        self.assertGreaterEqual(
            float(summary["success_rate_difference"]),
            0.20,
        )
        self.assertGreaterEqual(float(summary["success_ratio"]), 1.50)

    def test_reset_does_not_regress_onemax(self) -> None:
        for seed in range(1, 21):
            reset, no_reset = run_onemax_pair(
                n=64,
                seed=seed,
                budget=5000,
                workers=1,
            )
            self.assertTrue(reset.solved)
            self.assertTrue(no_reset.solved)
            self.assertEqual(reset.evaluations, no_reset.evaluations)
            self.assertEqual(reset.best_mask, no_reset.best_mask)
            self.assertEqual(reset.best_fitness, no_reset.best_fitness)


if __name__ == "__main__":
    unittest.main()
