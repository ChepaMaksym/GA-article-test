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
)
from hybrid_1.core import run_reset_lambda_ga  # noqa: E402


def signature(result):
    return {
        "evaluations": result.evaluations,
        "generations": result.generations,
        "reset_events": result.reset_events,
        "best_mask": result.best_mask,
        "best_fitness": result.best_fitness,
        "solved": result.solved,
        "trace": tuple(
            (
                row.generation,
                row.evaluations,
                row.lambda_before,
                row.lambda_after,
                row.mutation_strength,
                row.strict_success,
                row.accepted,
                row.reset_event,
            )
            for row in result.trace
        ),
    }


class HybridOneWorkerTests(unittest.TestCase):
    def test_evaluation_workers_1_2_4_are_exactly_invariant(self) -> None:
        objective = JumpObjective(3)
        initial = jump_local_optimum(20, 3)
        results = []
        for workers in (1, 2, 4):
            results.append(
                run_reset_lambda_ga(
                    objective,
                    dimension=20,
                    seed=11,
                    max_evaluations=3000,
                    workers=workers,
                    reset=True,
                    initial_mask=initial,
                    target_primary=23.0,
                )
            )
        self.assertEqual(signature(results[0]), signature(results[1]))
        self.assertEqual(signature(results[0]), signature(results[2]))

    def test_campaign_process_workers_1_2_4_are_invariant(self) -> None:
        common = dict(
            n=20,
            k=3,
            seeds=range(1, 9),
            budget=2500,
            evaluation_workers=1,
        )
        sequential = run_jump_campaign(campaign_workers=1, **common)
        two = run_jump_campaign(campaign_workers=2, **common)
        four = run_jump_campaign(campaign_workers=4, **common)
        self.assertEqual(sequential, two)
        self.assertEqual(sequential, four)


if __name__ == "__main__":
    unittest.main()
