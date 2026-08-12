#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import sys
import unittest

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from hybrid_1.core import (  # noqa: E402
    controls,
    crossover_mask,
    make_mutants,
    mutate_exact,
    next_lambda,
    round_half_up,
    run_reset_lambda_ga,
    select_generation_candidate,
)
from hybrid_1.benchmarks import OneMaxObjective  # noqa: E402


class HybridOneCoreTests(unittest.TestCase):
    def test_controls_and_rounding(self) -> None:
        self.assertEqual(round_half_up(1.49), 1)
        self.assertEqual(round_half_up(1.50), 2)
        ctl = controls(5.0, 20)
        self.assertEqual(ctl.offspring_count, 5)
        self.assertAlmostEqual(ctl.mutation_probability, 0.25)
        self.assertAlmostEqual(ctl.crossover_probability, 0.20)
        endpoint = controls(20.0, 20)
        self.assertEqual(endpoint.offspring_count, 20)
        self.assertEqual(endpoint.mutation_probability, 1.0)
        self.assertAlmostEqual(endpoint.crossover_probability, 0.05)

    def test_lambda_success_growth_and_reset(self) -> None:
        shrink, reset = next_lambda(
            9.0,
            strict_success=True,
            update_factor=1.5,
            dimension=20,
            reset=True,
        )
        self.assertEqual((shrink, reset), (6.0, False))
        grow, reset = next_lambda(
            1.0,
            strict_success=False,
            update_factor=1.5,
            dimension=20,
            reset=True,
        )
        self.assertAlmostEqual(grow, 1.5 ** 0.25)
        self.assertFalse(reset)
        at_cap, reset = next_lambda(
            20.0,
            strict_success=False,
            update_factor=1.5,
            dimension=20,
            reset=True,
        )
        self.assertEqual((at_cap, reset), (1.0, True))
        no_reset, reset_event = next_lambda(
            20.0,
            strict_success=False,
            update_factor=1.5,
            dimension=20,
            reset=False,
        )
        self.assertEqual((no_reset, reset_event), (20.0, False))

    def test_exact_mutation_and_crossover(self) -> None:
        parent = (0, 0, 1, 1)
        mutant = mutate_exact(parent, [0, 3])
        self.assertEqual(mutant, (1, 0, 1, 0))
        child = crossover_mask(parent, mutant, [True, False, True, False])
        self.assertEqual(child, (1, 0, 1, 1))
        with self.assertRaises(ValueError):
            mutate_exact(parent, [1, 1])

    def test_one_mutation_strength_for_whole_generation(self) -> None:
        parent = tuple([0] * 20)
        mutants = make_mutants(
            parent,
            count=12,
            strength=5,
            rng=np.random.default_rng(77),
        )
        distances = [
            sum(first != second for first, second in zip(parent, child))
            for child in mutants
        ]
        self.assertEqual(distances, [5] * 12)

    def test_final_pool_uses_selected_mutant_and_excludes_parent(self) -> None:
        parent = (0, 0, 0, 0)
        selection = select_generation_candidate(
            parent=parent,
            parent_fitness=(0.0, 0.0),
            mutants=[(1, 0, 0, 0), (0, 1, 0, 0)],
            mutant_fitness=[(3.0, 0.0), (2.0, 0.0)],
            crossovers=[parent, (0, 0, 1, 0)],
            crossover_fitness=[(100.0, 0.0), (2.5, 0.0)],
            rng=np.random.default_rng(4),
        )
        self.assertEqual(selection.best_mutant, (1, 0, 0, 0))
        self.assertEqual(selection.candidate, (1, 0, 0, 0))
        self.assertEqual(selection.eligible_count, 2)

    def test_secondary_sparsity_is_a_strict_success(self) -> None:
        parent = (1, 1, 0, 0)
        selection = select_generation_candidate(
            parent=parent,
            parent_fitness=(0.90, -0.50),
            mutants=[(1, 0, 0, 0)],
            mutant_fitness=[(0.90, -0.25)],
            crossovers=[parent],
            crossover_fitness=[(0.90, -0.50)],
            rng=np.random.default_rng(1),
        )
        self.assertGreater(selection.candidate_fitness, (0.90, -0.50))

    def test_budget_never_overshoots_and_trace_is_consistent(self) -> None:
        result = run_reset_lambda_ga(
            OneMaxObjective(),
            dimension=32,
            seed=19,
            max_evaluations=257,
            workers=1,
            reset=True,
            target_primary=32.0,
        )
        self.assertLessEqual(result.evaluations, 257)
        previous = 0
        for row in result.trace:
            self.assertGreater(row.evaluations, previous)
            self.assertTrue(1.0 <= row.lambda_before <= 32.0)
            self.assertTrue(1.0 <= row.lambda_after <= 32.0)
            self.assertAlmostEqual(
                row.mutation_probability,
                row.lambda_before / 32.0,
            )
            self.assertAlmostEqual(
                row.crossover_probability,
                1.0 / row.lambda_before,
            )
            if row.reset_event:
                self.assertEqual(row.lambda_before, 32.0)
                self.assertEqual(row.lambda_after, 1.0)
                self.assertFalse(row.strict_success)
            previous = row.evaluations


if __name__ == "__main__":
    unittest.main()
