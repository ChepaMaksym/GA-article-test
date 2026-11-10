"""CI-only synthetic checks for the fixed-grid wrapper and operator contract."""
from copy import deepcopy
import unittest

from .common import guard_stage
from .search import CROSSOVER_PERCENTAGES, POPULATIONS, make_log
from .pilot import comparable_log
from studies.knapsack_parameters.population_validation_100.preparation import make_bank, score
from studies.knapsack_parameters.crossover_population.program.ga_core import create_random_generators
from studies.knapsack_parameters.crossover_population.program.ga_core.operators import create_offspring
from studies.knapsack_parameters.crossover_population.verification import verify_log


class FixedGridSearch(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        guard_stage("technical")

    def setUp(self):
        self.problem = {"n": 100, "weights": [1] * 100,
                        "profits": [1 + i % 11 for i in range(100)], "capacity": 50}
        self.seed, self.task_index = 159999, 0
        self.bank = make_bank(self.problem, self.task_index, self.seed, 159998)

    def test_all_sixteen_configurations_replay_exact_budget_and_partial_generation(self):
        for mu in POPULATIONS:
            for pc in CROSSOVER_PERCENTAGES:
                with self.subTest(mu=mu, crossover=pc):
                    total = mu + 2 * (mu - 1) + 3
                    log = make_log(self.problem, self.bank, mu, pc, self.seed, self.task_index, total)
                    verified = verify_log(log)
                    self.assertEqual(verified["verification_status"], "VERIFIED")
                    self.assertEqual(log["summary"]["new_calls"], total - mu)
                    self.assertEqual(log["summary"]["known_score_validation_evaluations"], mu)
                    self.assertEqual(log["summary"]["full_generations"], 2)
                    self.assertEqual(log["summary"]["partial_children"], 3)
                    self.assertEqual(len(log["candidates"]), total - mu)
                    self.assertEqual(log["initial_masks"], self.bank["masks"][:mu])
                    self.assertEqual(log["initial_scores"], self.bank["scores"][:mu])
                    self.assertEqual(log["rng_initial"], self.bank["rng_states"])
                    last = log["generations"][-1]
                    self.assertFalse(last["complete"])
                    self.assertEqual(last["controller_event"], "PARTIAL_NO_UPDATE")
                    self.assertEqual(last["population_before"], last["population_after"])
                    self.assertEqual(last["parameters_before"], last["parameters_after"])
                    self.assertEqual(last["parameters_after"]["p_c"], pc / 100)
                    self.assertEqual(last["parameters_after"]["p_m"], .01)

    def test_ninety_percent_matches_historical_wrapper_without_timing(self):
        from studies.knapsack_parameters.population_validation_100.pilot import make_log as historical
        for mu in (10, 20):
            with self.subTest(mu=mu):
                total = mu + 2 * (mu - 1) + 1
                actual = make_log(self.problem, self.bank, mu, 90, self.seed, self.task_index, total)
                reference = historical(self.problem, self.bank, mu, self.seed, self.task_index, total)
                self.assertEqual(comparable_log(actual), comparable_log(reference))

    def test_determinism_and_inputs_remain_unchanged(self):
        problem, bank = deepcopy(self.problem), deepcopy(self.bank)
        first = make_log(self.problem, self.bank, 15, 80, self.seed, self.task_index, 47)
        second = make_log(self.problem, self.bank, 15, 80, self.seed, self.task_index, 47)
        self.assertEqual(comparable_log(first), comparable_log(second))
        self.assertEqual(self.problem, problem)
        self.assertEqual(self.bank, bank)

    def test_hundred_percent_still_consumes_one_crossover_decision_draw(self):
        import numpy as np
        generators = create_random_generators(self.seed, self.task_index, 0)
        expected_branch = np.random.Generator(np.random.PCG64())
        expected_branch.bit_generator.state = deepcopy(generators["branch"].bit_generator.state)
        expected_branch.random()
        applied, before_mutation, positions, offspring = create_offspring(
            "0" * 100, "1" * 100, 100, {"p_c": 1.0, "p_m": .01}, generators)
        self.assertTrue(applied)
        self.assertEqual(generators["branch"].bit_generator.state, expected_branch.bit_generator.state)
        self.assertEqual(len(before_mutation), len(offspring))
        self.assertEqual({i for i, (a, b) in enumerate(zip(before_mutation, offspring)) if a != b}, set(positions))

    def test_wrong_configuration_bank_identity_and_optimum_are_rejected(self):
        for mu, pc in ((9, 90), (30, 90), (15, 69), (15, 101), (True, 90), (15, 90.0)):
            with self.subTest(mu=mu, crossover=pc):
                with self.assertRaises(ValueError):
                    make_log(self.problem, self.bank, mu, pc, self.seed, self.task_index, 50)
        with self.assertRaises(ValueError):
            make_log(self.problem, self.bank, 15, 90, self.seed + 1, self.task_index, 50)
        with self.assertRaises(ValueError):
            make_log({**self.problem, "optimum": 1000}, self.bank, 15, 90, self.seed, self.task_index, 50)
        changed = deepcopy(self.bank)
        changed["rng_states"]["mutation"]["state"]["state"] += 1
        with self.assertRaises(ValueError):
            make_log(self.problem, changed, 15, 90, self.seed, self.task_index, 50)

    def test_duplicates_ties_and_elite_do_not_reduce_evaluation_count(self):
        bank = deepcopy(self.bank)
        bank["masks"] = ["0" * 100 for _ in range(30)]
        bank["scores"] = [score(self.problem, mask) for mask in bank["masks"]]
        log = make_log(self.problem, bank, 15, 100, self.seed, self.task_index, 44)
        checked = verify_log(log)
        self.assertEqual(checked["verification_status"], "VERIFIED")
        self.assertEqual(len(log["initial_masks"]), 15)
        self.assertEqual(len(log["candidates"]), 29)
        self.assertEqual(log["summary"]["full_generations"], 2)
        self.assertEqual(log["summary"]["partial_children"], 1)
        for generation in log["generations"]:
            self.assertEqual(len(generation["elite_references"]), 1)
            self.assertEqual(generation["requested_offspring"], 14)


if __name__ == "__main__":
    unittest.main()
