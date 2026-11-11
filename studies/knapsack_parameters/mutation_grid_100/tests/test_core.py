"""Small independent-replay checks. Run only in the registered CI stage."""
from copy import deepcopy
from fractions import Fraction
import math
import os
import unittest

from studies.knapsack_parameters.crossover_population.program import ga_core as historical
from studies.knapsack_parameters.mutation_grid_100.program import ga_core as current
from studies.knapsack_parameters.mutation_grid_100.program.ga_core.controllers import (
    update_configured_fixed_parameters,
)
from studies.knapsack_parameters.mutation_grid_100.program.ga_core.operators import evaluate
from studies.knapsack_parameters.mutation_grid_100.observations import extract
from studies.knapsack_parameters.mutation_grid_100.verification import verify_log

CONTRACT = "fixed-mutation-grid-v1"


def fixture(mu=10, n=6, identical=False):
    problem = {"n": n, "weights": list(range(1, n + 1)),
               "profits": list(range(2, n + 2)), "capacity": n + 1}
    masks = (["0" * n] * mu if identical else
             [format(index % (1 << n), f"0{n}b") for index in range(mu)])
    return problem, {"masks": masks, "scores": [evaluate(problem, mask) for mask in masks]}


def configured(mu=10, pm=.01, pc=1.):
    return {"p_m": pm, "p_c": pc, "target_mu": mu, "tournament_size": 2, "elite_count": 1}


def run_small(*, mu=10, n=6, pm=.01, pc=1., budget=20, seed=17, initial=None,
              problem=None, contract=CONTRACT):
    if problem is None:
        problem, initial = fixture(mu, n)
    return current.run_ga(problem, initial, current.parameter_controller(0),
                          current.create_random_generators(seed, 4, 0), budget,
                          initial_parameters=configured(mu, pm, pc),
                          configuration_contract=contract)


def without_observational_metadata(log):
    copied = deepcopy(log)
    copied.pop("timing_ns")
    copied.pop("configuration_contract", None)
    copied["schema"] = "comparison-only"
    return copied


class MutationCoreTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if os.environ.get("GITHUB_ACTIONS") != "true":
            raise RuntimeError("Scientific tests require GitHub Actions")

    def test_legacy_explicit_routes_remain_identical(self):
        for contract, pc in ((None, .9), ("population-crossover-v1", 1.)):
            for mu in (2, 10, 15, 20):
                with self.subTest(contract=contract, mu=mu):
                    problem, initial = fixture(mu)
                    original = historical.run_ga(
                        problem, initial, historical.parameter_controller(0),
                        historical.create_random_generators(17, 4, 0), 23,
                        initial_parameters=configured(mu, 1 / 6, pc),
                        configuration_contract=contract)
                    copied = run_small(mu=mu, pm=1 / 6, pc=pc, budget=23, contract=contract)
                    original.pop("timing_ns")
                    copied.pop("timing_ns")
                    self.assertEqual(copied, original)

    def test_new_contract_preserves_mutation_one_over_n_scientific_trace(self):
        for mu in (10, 15, 20):
            old = run_small(mu=mu, pm=1 / 6, contract="population-crossover-v1")
            new = run_small(mu=mu, pm=1 / 6)
            self.assertEqual(without_observational_metadata(old), without_observational_metadata(new))
            self.assertEqual(new["schema"], "ga-knapsack-fixed-mutation-grid-log-v1")
            self.assertEqual(verify_log(new)["verification_status"], "VERIFIED")

    def test_historical_adaptive_and_tournament_routes_remain_identical(self):
        problem, initial = fixture(30)
        for profile in (0, 1, 31, "k2", "adaptive"):
            old_controller = (historical.parameter_controller(profile) if type(profile) is int
                              else historical.tournament_controller(profile))
            new_controller = (current.parameter_controller(profile) if type(profile) is int
                              else current.tournament_controller(profile))
            old = historical.run_ga(problem, initial, old_controller,
                                    historical.create_random_generators(5, 2, 0), 33)
            new = current.run_ga(problem, initial, new_controller,
                                 current.create_random_generators(5, 2, 0), 33)
            old.pop("timing_ns")
            new.pop("timing_ns")
            self.assertEqual(new, old)

    def test_all_registered_rates_remain_fixed_and_replay(self):
        for mu in (10, 15, 20):
            for basis_points in (25, 50, 75, 100, 150, 200):
                with self.subTest(mu=mu, mutation_basis_points=basis_points):
                    log = run_small(mu=mu, n=100, pm=basis_points / 10000, budget=mu)
                    verify_log(log)
                    expected = log["initial_parameters"]
                    self.assertEqual(log["summary"]["final_parameters"], expected)
                    for event in log["generations"]:
                        self.assertEqual(event["parameters_before"], expected)
                        self.assertEqual(event["parameters_after"], expected)

    def test_mutation_edges_keep_full_random_consumption(self):
        for mutation in (0., 1.):
            log = run_small(pm=mutation, pc=1., budget=17)
            expected = current.create_random_generators(17, 4, 0)
            expected["mutation"].random(17 * 6)
            expected["branch"].random(17)
            expected["crossover"].random(17 * 6)
            for stream in ("mutation", "branch", "crossover"):
                self.assertEqual(log["rng_final"][stream], expected[stream].bit_generator.state)
            for candidate in log["candidates"]:
                if mutation == 0:
                    self.assertEqual(candidate["mutation_bits"], [])
                    self.assertEqual(candidate["mask"], candidate["pre_mask"])
                else:
                    self.assertEqual(candidate["mutation_bits"], list(range(6)))
                    self.assertEqual(candidate["mask"], "".join("1" if b == "0" else "0"
                                                               for b in candidate["pre_mask"]))
            verify_log(log)

    def test_invalid_probabilities_and_legacy_relaxation_are_rejected(self):
        for mutation in (-.01, 1.01, math.nan, math.inf, -math.inf, True, False, ".01", None):
            with self.subTest(mutation=mutation):
                with self.assertRaises(ValueError):
                    run_small(pm=mutation)
        for pc in (-.01, 1.01, math.nan, math.inf, True, None):
            with self.subTest(crossover=pc):
                with self.assertRaises(ValueError):
                    run_small(pc=pc)
        for contract in (None, "population-crossover-v1"):
            with self.assertRaises(ValueError):
                run_small(pm=.01, pc=.9, contract=contract)
        for contract in ("", "unknown", True, 1):
            with self.assertRaises(ValueError):
                run_small(contract=contract)

    def test_success_priority_and_fixed_mutation_boundary_event(self):
        for mutation in (.0025, .01, .02):
            params = configured(pm=mutation)
            for success in (True, False):
                update = update_configured_fixed_parameters(
                    params, 144, success, 9, Fraction(1, 2), 100,
                    configuration_contract=CONTRACT)
                self.assertEqual(update["parameters"], params)
                self.assertEqual(update["event"], "SUCCESS" if success else "STAGNATION")
                self.assertEqual(update["failed_queries_after"], 0)
                event = next(e for e in update["parameter_events"] if e["field"] == "p_m")
                self.assertTrue(event["at_boundary"])
                self.assertFalse(event["enabled"])

    def test_partial_generation_updates_record_only(self):
        log = run_small(mu=10, budget=20)
        last = log["generations"][-1]
        self.assertFalse(last["complete"])
        self.assertEqual(last["controller_event"], "PARTIAL_NO_UPDATE")
        self.assertEqual(last["population_before"], last["population_after"])
        self.assertEqual(last["failed_queries_before"], last["failed_queries_after"])
        self.assertEqual(log["summary"]["partial_children"], 2)
        self.assertEqual(log["summary"]["new_calls"], 20)
        scores = log["initial_scores"] + log["candidates"]
        self.assertEqual(log["summary"]["best_profit"], max(s["profit"] for s in scores if s["feasible"]))
        verify_log(log)

    def test_elite_retained_and_worse_individuals_admitted(self):
        problem = {"n": 4, "weights": [1] * 4, "profits": [1] * 4, "capacity": 4}
        initial = {"masks": ["1111"] * 10, "scores": [evaluate(problem, "1111")] * 10}
        log = run_small(problem=problem, initial=initial, pm=1., budget=9)
        self.assertEqual(log["candidates"][0]["profit"], 0)
        after = log["generations"][0]["population_after"]
        self.assertEqual(len(after), 10)
        scores = initial["scores"] + log["candidates"]
        self.assertEqual([scores[ref]["profit"] for ref in after], [4] + [0] * 9)
        verify_log(log)

    def test_duplicates_ties_and_infeasible_masks_are_replayed(self):
        problem = {"n": 2, "weights": [1, 1], "profits": [1, 1], "capacity": 0}
        initial = {"masks": ["00"] * 10, "scores": [evaluate(problem, "00")] * 10}
        log = run_small(problem=problem, initial=initial, pm=1., budget=36)
        report = verify_log(log)
        self.assertEqual(report["record_profit"], 0)
        self.assertGreater(log["summary"]["duplicate_calls"], 0)
        self.assertGreater(log["summary"]["infeasible_calls"], 0)

    def test_corrupt_mask_rng_probability_operator_and_population_fail_closed(self):
        original = run_small()
        mutations = [
            lambda value: value["candidates"][0].__setitem__("mask", "x" * 6),
            lambda value: value["rng_final"]["mutation"]["state"].__setitem__("state", 0),
            lambda value: value["initial_parameters"].__setitem__("p_m", .02),
            lambda value: value["candidates"][0].__setitem__("mutation_bits", [99]),
            lambda value: value["generations"][0].__setitem__("population_after", [0] * 10),
        ]
        for mutate in mutations:
            value = deepcopy(original)
            mutate(value)
            with self.assertRaises(ValueError):
                verify_log(value)

    def test_optimum_metadata_never_enters_search(self):
        problem, initial = fixture()
        problem["optimum"] = 10
        with self.assertRaises(ValueError):
            run_small(problem=problem, initial=initial)

    def test_total_evaluation_observations_cover_initial_and_partial_prefix(self):
        problem = {"n": 2, "weights": [1, 1], "profits": [1, 1], "capacity": 2}
        initial = {"masks": ["00"] * 10, "scores": [evaluate(problem, "00")] * 10}
        log = run_small(problem=problem, initial=initial, pm=0., budget=20)
        # Both items fit, so OPT=2 is immediate; zero mutation of identical empty
        # parents can never reach it. OPT is passed only to the observations.
        observations = extract(log, 30, 2, checkpoints=(0, 1, 9, 10, 19, 30))
        self.assertEqual(observations["new_evaluations"], 20)
        self.assertEqual(observations["initial_evaluations"], 10)
        self.assertEqual(observations["checkpoints"][2]["phase"], "initializing")
        self.assertEqual(observations["checkpoints"][-1]["partial_offspring_count"], 2)
        for target in observations["targets"].values():
            self.assertFalse(target["attained"])
            self.assertIsNone(target["first_total_evaluation"])
            self.assertEqual(target["restricted_evaluations"], 30)

    def test_exact_initial_threshold_and_last_evaluation_attainment(self):
        problem = {"n": 2, "weights": [1, 1], "profits": [93, 7], "capacity": 2}
        initial = {"masks": ["10", "00"],
                   "scores": [evaluate(problem, mask) for mask in ("10", "00")]}
        log = run_small(mu=2, problem=problem, initial=initial, pm=0., pc=0., budget=1)
        observed = extract(log, 3, 100, checkpoints=(1, 2, 3))
        self.assertEqual(observed["targets"]["93"]["first_total_evaluation"], 1)
        self.assertFalse(observed["targets"]["95"]["attained"])
        self.assertFalse(observed["targets"]["99"]["attained"])
        problem = {"n": 2, "weights": [1, 1], "profits": [1, 1], "capacity": 2}
        initial = {"masks": ["00", "00"], "scores": [evaluate(problem, "00")] * 2}
        log = run_small(mu=2, problem=problem, initial=initial, pm=1., budget=1)
        observed = extract(log, 3, 2, checkpoints=(1, 2, 3))
        for target in observed["targets"].values():
            self.assertTrue(target["attained"])
            self.assertEqual(target["first_total_evaluation"], 3)
            self.assertEqual(target["restricted_evaluations"], 3)
        self.assertLessEqual(observed["targets"]["93"]["first_total_evaluation"],
                             observed["targets"]["99"]["first_total_evaluation"])


if __name__ == "__main__":
    unittest.main()
