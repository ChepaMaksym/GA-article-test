from __future__ import annotations

import json
from pathlib import Path
import sys
import unittest

import numpy as np

CANDIDATE_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(CANDIDATE_ROOT / "environments" / "python"))

from gesmr import (  # noqa: E402
    GESMRConfig,
    gesmr_step,
    get_benchmark,
    initial_mutation_rates,
    run_gesmr,
)


class CountingObjective:
    def __init__(self) -> None:
        self.calls = 0
        self.rows = 0

    def __call__(self, population: np.ndarray) -> np.ndarray:
        self.calls += 1
        self.rows += population.shape[0]
        return np.sum(population * population, axis=1)


class CoreTests(unittest.TestCase):
    def test_cross_environment_fixed_tape_fixture(self) -> None:
        fixture_path = CANDIDATE_ROOT / "fixtures" / "cross_env_step.json"
        fixture = json.loads(fixture_path.read_text(encoding="utf-8"))
        config = GESMRConfig(**fixture["config"])
        result = gesmr_step(
            fixture["population"],
            fixture["sigmas"],
            get_benchmark(fixture["objective"]),
            config,
            tape=fixture["tape"],
        )
        tolerance = fixture["tolerance"]
        expected = fixture["expected"]
        np.testing.assert_allclose(
            result.next_population,
            expected["next_population"],
            atol=tolerance,
            rtol=0.0,
        )
        np.testing.assert_allclose(
            result.next_fitness,
            expected["next_fitness"],
            atol=tolerance,
            rtol=0.0,
        )
        np.testing.assert_allclose(
            result.group_delta,
            expected["group_delta"],
            atol=tolerance,
            rtol=0.0,
        )
        np.testing.assert_allclose(
            result.next_sigmas,
            expected["next_sigmas"],
            atol=tolerance,
            rtol=0.0,
        )

    def test_elitism_and_positive_mutation_rates(self) -> None:
        config = GESMRConfig(non_elite_size=20, n_groups=4)
        result = run_gesmr(
            get_benchmark("sphere"),
            dimension=12,
            initial_std=1.0,
            seed=7,
            generations=12,
            config=config,
        )
        differences = np.diff(result.best_fitness_history)
        self.assertTrue(np.all(differences <= 1e-12))
        self.assertTrue(np.all(np.isfinite(result.sigma_history)))
        self.assertTrue(np.all(result.sigma_history > 0.0))
        self.assertTrue(np.any(result.sigma_history[1:] != result.sigma_history[:-1]))

    def test_same_seed_is_bitwise_repeatable_in_python(self) -> None:
        config = GESMRConfig(non_elite_size=20, n_groups=4)
        first = run_gesmr(
            get_benchmark("ackley"), 12, 1.0, 19, 6, config
        )
        second = run_gesmr(
            get_benchmark("ackley"), 12, 1.0, 19, 6, config
        )
        self.assertTrue(np.array_equal(first.final_population, second.final_population))
        self.assertTrue(np.array_equal(first.final_fitness, second.final_fitness))
        self.assertTrue(np.array_equal(first.sigma_history, second.sigma_history))

    def test_run_uses_one_full_population_evaluation_per_state(self) -> None:
        config = GESMRConfig(non_elite_size=20, n_groups=4)
        objective = CountingObjective()
        generations = 5
        result = run_gesmr(objective, 12, 1.0, 0, generations, config)
        self.assertEqual(objective.calls, 1 + generations)
        self.assertEqual(
            objective.rows,
            (config.non_elite_size + 1) * (1 + generations),
        )
        self.assertEqual(result.objective_call_count, objective.calls)
        self.assertEqual(result.objective_row_evaluation_count, objective.rows)

    def test_reported_mr_curve_is_geometric_not_arithmetic_mean(self) -> None:
        config = GESMRConfig(non_elite_size=20, n_groups=4)
        result = run_gesmr(get_benchmark("sphere"), 12, 1.0, 0, 0, config)
        expected_geometric = np.exp(np.mean(np.log(result.sigma_history[0])))
        expected_arithmetic = np.mean(result.sigma_history[0])
        self.assertEqual(result.geometric_mean_sigma_history[0], expected_geometric)
        self.assertEqual(result.arithmetic_mean_sigma_history[0], expected_arithmetic)
        self.assertNotEqual(expected_geometric, expected_arithmetic)

    def test_default_101_row_transition_has_stable_original_index_tie_break(self) -> None:
        config = GESMRConfig()
        population = np.full((101, 12), 9.0)
        population[0] = np.array([1.0] + [0.0] * 11)
        population[1] = np.array([-1.0] + [0.0] * 11)
        tape = {
            "solution_parent_ranks": np.zeros(100, dtype=np.int64),
            "solution_noise": np.zeros((100, 12)),
            "mr_parent_ranks": np.zeros(9, dtype=np.int64),
            "mr_uniform": np.zeros(9),
        }
        result = gesmr_step(
            population,
            initial_mutation_rates(config),
            get_benchmark("sphere"),
            config,
            tape=tape,
        )
        np.testing.assert_array_equal(result.selected_parents[0], population[0])

    def test_initial_mutation_rate_population(self) -> None:
        sigmas = initial_mutation_rates()
        self.assertEqual(sigmas.shape, (10,))
        self.assertEqual(sigmas[0], 1e-3)
        self.assertEqual(sigmas[-1], 1e3)
        np.testing.assert_allclose(np.diff(np.log10(sigmas)), 2.0 / 3.0, atol=1e-14)

    def test_ambiguous_group_or_selection_arithmetic_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "divide"):
            GESMRConfig(non_elite_size=20, n_groups=3).validate()
        with self.assertRaisesRegex(ValueError, "must be an integer"):
            GESMRConfig(
                non_elite_size=20,
                n_groups=4,
                mr_selection_rate=0.3,
            ).validate()

    def test_random_tape_out_of_range_fails_closed(self) -> None:
        fixture = json.loads(
            (CANDIDATE_ROOT / "fixtures" / "cross_env_step.json").read_text(
                encoding="utf-8"
            )
        )
        fixture["tape"]["solution_parent_ranks"][0] = 2
        with self.assertRaisesRegex(ValueError, "outside"):
            gesmr_step(
                fixture["population"],
                fixture["sigmas"],
                get_benchmark("sphere"),
                GESMRConfig(**fixture["config"]),
                tape=fixture["tape"],
            )

    def test_fractional_random_tape_rank_fails_closed(self) -> None:
        fixture = json.loads(
            (CANDIDATE_ROOT / "fixtures" / "cross_env_step.json").read_text(
                encoding="utf-8"
            )
        )
        fixture["tape"]["solution_parent_ranks"][0] = 0.5
        with self.assertRaisesRegex(ValueError, "must be integers"):
            gesmr_step(
                fixture["population"],
                fixture["sigmas"],
                get_benchmark("sphere"),
                GESMRConfig(**fixture["config"]),
                tape=fixture["tape"],
            )


if __name__ == "__main__":
    unittest.main()
