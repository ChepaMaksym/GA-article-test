#!/usr/bin/env python3
"""Tests for the independent printed-paper OLD profile."""
from __future__ import annotations

import importlib.util
from pathlib import Path
import random
import sys
import unittest

import numpy as np

MODULE_PATH = Path(__file__).resolve().parents[1] / "old" / "paper_profile.py"
SPEC = importlib.util.spec_from_file_location("eu26_20_paper_profile", MODULE_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("cannot load paper profile")
PROFILE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = PROFILE
SPEC.loader.exec_module(PROFILE)


class PaperProfileTests(unittest.TestCase):
    def test_paper_ceil_offspring_counts(self) -> None:
        self.assertEqual(PROFILE.paper_offspring_counts(10, 0.9, 0.4), (10, 4))
        self.assertEqual(PROFILE.paper_offspring_counts(10, 0.6, 0.6), (6, 6))
        self.assertEqual(PROFILE.paper_offspring_counts(10, 0.3, 0.8), (4, 8))
        self.assertEqual(PROFILE.paper_offspring_counts(10, 0.0, 1.0), (0, 10))

    def test_geometry_uses_feature_vectors_not_numeric_identifiers(self) -> None:
        x = np.array([[0, 100, 0], [1, 100, 1], [2, 100, 2]], dtype=float)
        geometry = PROFILE.FeatureGeometry(x, [0, 1, 2])
        self.assertEqual(geometry.solution_distance([0], [2]), 0.0)
        self.assertGreater(geometry.solution_distance([0], [1]), 100.0)

    def test_variable_crossover_preserves_unique_pool_members(self) -> None:
        first, second = PROFILE.variable_single_point_crossover(
            [1, 2, 3, 4], [3, 4, 5, 6], random.Random(7)
        )
        self.assertEqual(len(first), len(set(first)))
        self.assertEqual(len(second), len(set(second)))
        self.assertTrue(set(first) <= {1, 2, 3, 4, 5, 6})
        self.assertTrue(set(second) <= {1, 2, 3, 4, 5, 6})

    def test_replacement_mutation_changes_exactly_one_feature(self) -> None:
        original = (1, 2, 3)
        mutated = PROFILE.replacement_mutation(original, range(1, 9), random.Random(1))
        self.assertEqual(len(mutated), len(original))
        self.assertEqual(len(mutated), len(set(mutated)))
        self.assertEqual(len(set(original) ^ set(mutated)), 2)

    def test_adaptation_reaches_mutation_only_after_fifteen_failures(self) -> None:
        config = PROFILE.PaperConfig()
        pc, pm, stagnation, clock = 0.9, 0.4, 0, 0
        observed = []
        for failure in range(1, 21):
            pc, pm, stagnation, clock, adapted = PROFILE.update_rates(
                pc, pm, stagnation, clock, False, config
            )
            if adapted:
                observed.append((failure, pc, pm))
        self.assertEqual(
            observed,
            [(5, 0.6, 0.6), (10, 0.3, 0.8), (15, 0.0, 1.0), (20, 0.0, 1.0)],
        )
        self.assertEqual(stagnation, 20)

    def test_improvement_resets_rates_and_counters(self) -> None:
        config = PROFILE.PaperConfig()
        state = (0.3, 0.8, 14, 4)
        self.assertEqual(
            PROFILE.update_rates(*state, True, config),
            (0.9, 0.4, 0, 0, False),
        )

    def test_fitness_is_deterministic_and_nfe_is_not_cached(self) -> None:
        rng = np.random.default_rng(4)
        x = rng.normal(size=(20, 6))
        y = np.array([1] * 10 + [2] * 10)
        x[:10, 0] += 3
        x[10:, 0] -= 3
        evaluator = PROFILE.FitnessEvaluator(x, y)
        first = evaluator.evaluate([0, 1])
        second = evaluator.evaluate([0, 1])
        self.assertEqual(first, second)
        self.assertEqual(evaluator.nfe, 2)

    def test_two_iteration_full_run_is_exactly_repeatable(self) -> None:
        rng = np.random.default_rng(123)
        x = rng.normal(size=(40, 100))
        y = np.array([1] * 20 + [2] * 20)
        x[:20, :3] += 2
        x[20:, :3] -= 2
        config = PROFILE.PaperConfig(
            max_iterations=2,
            repository_attempt_limit=10_000,
        )
        first = PROFILE.run_paper_profile(x, y, range(100), 1, config)
        second = PROFILE.run_paper_profile(x, y, range(100), 1, config)
        self.assertEqual(first, second)
        self.assertEqual(first["iterations"], 2)
        # Initial Pop + Pope = 20; each .9/.4 iteration evaluates 10+4+10+2=26.
        self.assertEqual(first["nfe"], 72)
        self.assertEqual(first["offspring_rounding"], "paper_ceil")
        self.assertEqual(first["geometry"], "feature_vectors_euclidean")


if __name__ == "__main__":
    unittest.main()
