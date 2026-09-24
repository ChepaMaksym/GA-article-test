#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import sys
import unittest

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from hybrid_1.benchmarks import OneMaxObjective  # noqa: E402
from hybrid_1.core import (  # noqa: E402
    controls,
    evaluate_many,
    make_crossovers,
    make_mutants,
    next_lambda,
    run_reset_lambda_ga,
)


class ExtendedCoreSemanticTests(unittest.TestCase):
    def test_target_met_by_initial_population_stops_before_offspring(self) -> None:
        result = run_reset_lambda_ga(
            OneMaxObjective(),
            dimension=4,
            seed=3,
            max_evaluations=100,
            initial_masks=[(0, 0, 0, 1), (1, 1, 1, 1)],
            target_primary=4.0,
        )
        self.assertTrue(result.solved)
        self.assertEqual(result.evaluations, 2)
        self.assertEqual(result.generations, 0)
        self.assertEqual(result.trace, ())
        self.assertEqual(result.best_mask, (1, 1, 1, 1))

    def test_neutral_generation_is_accepted_but_lambda_grows(self) -> None:
        result = run_reset_lambda_ga(
            lambda mask: (1.0, 0.0),
            dimension=4,
            seed=9,
            max_evaluations=3,
            initial_mask=(1, 0, 0, 0),
        )
        self.assertEqual(len(result.trace), 1)
        row = result.trace[0]
        self.assertTrue(row.accepted)
        self.assertFalse(row.strict_success)
        self.assertGreater(row.lambda_after, row.lambda_before)

    def test_objective_call_count_matches_logical_nfe(self) -> None:
        calls = []

        def objective(mask):
            calls.append(mask)
            return float(sum(mask)), 0.0

        result = run_reset_lambda_ga(
            objective,
            dimension=8,
            seed=11,
            max_evaluations=57,
            initial_masks=[(1, 0, 0, 0, 0, 0, 0, 0)] * 3,
        )
        self.assertEqual(len(calls), result.evaluations)
        self.assertLessEqual(result.evaluations, 57)

    def test_zero_mutation_strength_produces_parent_copies(self) -> None:
        parent = (1, 0, 1, 0)
        mutants = make_mutants(
            parent,
            count=7,
            strength=0,
            rng=np.random.default_rng(5),
        )
        self.assertEqual(mutants, [parent] * 7)

    def test_crossover_probability_endpoints(self) -> None:
        parent = (0, 0, 1, 1)
        mutant = (1, 1, 0, 0)
        no_mutant_bits = make_crossovers(
            parent,
            mutant,
            count=4,
            probability=0.0,
            rng=np.random.default_rng(1),
        )
        all_mutant_bits = make_crossovers(
            parent,
            mutant,
            count=4,
            probability=1.0,
            rng=np.random.default_rng(1),
        )
        self.assertEqual(no_mutant_bits, [parent] * 4)
        self.assertEqual(all_mutant_bits, [mutant] * 4)

    def test_reset_occurs_at_cap_not_on_transition_to_cap(self) -> None:
        at_cap, reset_event = next_lambda(
            19.0,
            strict_success=False,
            update_factor=16.0,
            dimension=20,
            reset=True,
        )
        self.assertEqual(at_cap, 20.0)
        self.assertFalse(reset_event)
        after_cap_failure, reset_event = next_lambda(
            at_cap,
            strict_success=False,
            update_factor=16.0,
            dimension=20,
            reset=True,
        )
        self.assertEqual(after_cap_failure, 1.0)
        self.assertTrue(reset_event)

    def test_parallel_evaluation_preserves_input_order(self) -> None:
        masks = [
            (0, 0, 0),
            (1, 0, 0),
            (0, 1, 0),
            (1, 1, 1),
        ]

        def objective(mask):
            return float(mask[0] * 4 + mask[1] * 2 + mask[2]), 0.0

        sequential = evaluate_many(objective, masks, workers=1)
        parallel = evaluate_many(objective, masks, workers=4)
        self.assertEqual(parallel, sequential)
        self.assertEqual([value[0] for value in parallel], [0.0, 4.0, 2.0, 7.0])

    def test_parallel_objective_exception_is_not_hidden(self) -> None:
        def objective(mask):
            if mask == (1, 1):
                raise RuntimeError("intentional objective failure")
            return float(sum(mask)), 0.0

        with self.assertRaisesRegex(RuntimeError, "intentional objective failure"):
            evaluate_many(objective, [(0, 0), (1, 1), (1, 0)], workers=3)

    def test_invalid_controls_fail_closed(self) -> None:
        with self.assertRaises(TypeError):
            controls(True, 20)
        with self.assertRaises(ValueError):
            controls(float("nan"), 20)
        with self.assertRaises(ValueError):
            controls(1.0, 1)
        with self.assertRaises(ValueError):
            controls(21.0, 20)


if __name__ == "__main__":
    unittest.main()
