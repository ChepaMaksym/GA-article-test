#!/usr/bin/env python3
"""Fixed-tape tests against the exact pinned CHC-QX author source."""
from __future__ import annotations

import argparse
import copy
import os
from pathlib import Path
import random
import sys
import unittest
from types import SimpleNamespace

import numpy as np


class UpstreamSourceTests(unittest.TestCase):
    upstream: Path
    Evolution: object
    creator: object
    base: object

    @classmethod
    def setUpClass(cls) -> None:
        if not hasattr(cls, "upstream"):
            configured = os.environ.get("EU26_21_UPSTREAM")
            if configured:
                cls.upstream = Path(configured).resolve()
            else:
                raise unittest.SkipTest(
                    "pinned upstream path is required; set EU26_21_UPSTREAM "
                    "or execute this file with the upstream argument"
                )
        code_dir = cls.upstream / "code"
        if not (code_dir / "Evolution.py").is_file():
            raise RuntimeError(f"missing pinned Evolution.py under {code_dir}")
        sys.path.insert(0, str(code_dir))
        from deap import base, creator
        from Evolution import Evolution

        cls.Evolution = Evolution
        cls.creator = creator
        cls.base = base

    def setUp(self) -> None:
        random.seed(12345)
        np.random.seed(12345)

    def test_hamming_distance(self) -> None:
        self.assertEqual(
            self.Evolution.hammingDistance(
                [0, 1, 1, 0, 1, 0],
                [1, 1, 0, 0, 1, 1],
            ),
            3,
        )
        self.assertEqual(
            self.Evolution.hammingDistance([1, 0, 1], [1, 0, 1]),
            0,
        )

    def test_common_bridge_hux_matches_actual_pinned_operator_and_rng_state(self) -> None:
        sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
        from common_bridge.search import _pinned_source_hux

        for dimension in (2, 8, 40):
            for seed in range(12):
                first = tuple((index + seed) % 2 for index in range(dimension))
                second = tuple(1-bit for bit in first)
                random.seed(seed)
                source = self.Evolution.HUX(
                    self.creator.Individual(first), self.creator.Individual(second), fixed=True,
                )
                source_state = random.getstate()
                local = random.Random(seed)
                actual = _pinned_source_hux(first, second, local)
                self.assertEqual(actual, tuple(tuple(child) for child in source))
                self.assertEqual(local.getstate(), source_state)

    def test_fixed_hux_swaps_half_the_differing_loci_per_child(self) -> None:
        parent_a = self.creator.Individual([0, 0, 0, 0, 1, 1, 1, 1])
        parent_b = self.creator.Individual([1, 1, 1, 1, 0, 0, 0, 0])
        original_a = list(parent_a)
        original_b = list(parent_b)

        child_a, child_b = self.Evolution.HUX(parent_a, parent_b, fixed=True)

        self.assertEqual(len(child_a), 8)
        self.assertEqual(len(child_b), 8)
        self.assertEqual(
            self.Evolution.hammingDistance(child_a, original_a),
            4,
        )
        self.assertEqual(
            self.Evolution.hammingDistance(child_b, original_b),
            4,
        )
        self.assertTrue(set(child_a) <= {0, 1})
        self.assertTrue(set(child_b) <= {0, 1})

    def test_source_population_is_binary_and_has_requested_shape(self) -> None:
        population = self.Evolution.create_population(
            population_size=17,
            ind_size=41,
            fixed_p=(0.5, 0.5),
        )
        self.assertEqual(len(population), 17)
        self.assertTrue(all(len(individual) == 41 for individual in population))
        self.assertTrue(
            all(
                set(int(value) for value in individual) <= {0, 1}
                for individual in population
            )
        )

    def _run_identical_population(self, generations: int):
        toolbox = self.base.Toolbox()
        counters = {"mate": 0, "mutate": 0, "evaluate": 0}

        def clone(individual):
            return copy.deepcopy(individual)

        def mate(first, second):
            counters["mate"] += 1
            return self.Evolution.HUX(first, second, fixed=True)

        def mutate(individual):
            counters["mutate"] += 1
            individual[0] = 1 - int(individual[0])
            return (individual,)

        def evaluate(individual):
            counters["evaluate"] += 1
            return (float(sum(individual)),)

        toolbox.register("clone", clone)
        toolbox.register("mate", mate)
        toolbox.register("mutate", mutate)
        toolbox.register("evaluate", evaluate)

        population = [self.creator.Individual([0] * 8) for _ in range(4)]
        dataset = SimpleNamespace(features=list(range(8)))
        log, final_population, final_d = self.Evolution.CHC(
            dataset,
            toolbox,
            d=2,
            population=population,
            max_generations=generations,
            max_no_change=np.inf,
            timeout=np.inf,
            optimization_task="feature_selection",
            verbose=0,
        )
        return log, final_population, final_d, counters

    def test_distance_decrements_when_identical_population_cannot_recombine(self) -> None:
        _, _, after_one, counters_one = self._run_identical_population(1)
        _, _, after_two, counters_two = self._run_identical_population(2)

        self.assertEqual(after_one, 1)
        self.assertEqual(after_two, 0)
        self.assertEqual(counters_one["mate"], 0)
        self.assertEqual(counters_two["mate"], 0)
        self.assertEqual(counters_one["mutate"], 0)
        self.assertEqual(counters_two["mutate"], 0)

    def test_zero_distance_triggers_cataclysmic_restart_and_resets_d(self) -> None:
        log, population, final_d, counters = self._run_identical_population(3)

        self.assertEqual(final_d, 2)
        self.assertEqual(counters["mate"], 0)
        self.assertEqual(counters["mutate"], 4)
        self.assertEqual(len(population), 4)
        self.assertTrue(any(sum(individual) > 0 for individual in population))
        self.assertGreaterEqual(counters["evaluate"], 8)
        self.assertFalse(log.empty)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("upstream", type=Path)
    args, remaining = parser.parse_known_args()
    UpstreamSourceTests.upstream = args.upstream.resolve()
    unittest.main(argv=[sys.argv[0], *remaining])


if __name__ == "__main__":
    main()
