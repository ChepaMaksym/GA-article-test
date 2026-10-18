import copy
import unittest
from unittest.mock import patch

from studies.adaptive_parameters.mutation_only import engine
from studies.knapsack_parameters.adaptation_analysis import comparison as c


class ComparisonTests(unittest.TestCase):
    def fixture(self):
        problem = {"n": 4, "weights": [6, 5, 5, 1], "profits": [10, 8, 8, 1], "capacity": 10}
        masks = ["1000"] * 30
        scores = [{"weight": 6, "profit": 10, "feasible": True} for _ in masks]
        return problem, masks, scores

    def test_five_profiles_one_classical_control(self):
        result = c.run_comparison(*self.fixture(), 23, 0, 0, 61)
        self.assertEqual(set(result["profiles"]), set(c.ACTIVE_PROFILES))
        self.assertEqual(result["accounting"]["new_search_evaluations"], 305)
        self.assertEqual(result["accounting"]["classical_control_runs"], 1)
        for value in result["pairing"].values():
            self.assertEqual(value["status"], "VERIFIED")
        for method, result in result["profiles"].items():
            self.assertEqual(c.verify_profile_log(method, result["log"])["verification_status"], "VERIFIED")

    def test_lambda_refuses_before_any_search_or_rng(self):
        with patch.object(engine, "make_rngs", side_effect=AssertionError("RNG must not be created")):
            for method in c.DEFERRED_PROFILES:
                with self.assertRaisesRegex(ValueError, "BLOCKED_LAMBDA_REPLICATION"):
                    c.run_profile(*self.fixture(), method, 1, 0, 0, 5)
        self.assertIsNone(c.lambda_status()["search_runs"])
        self.assertFalse(c.lambda_status()["implemented"])

    def test_wrong_method_and_oracle_refused(self):
        with self.assertRaises(ValueError):
            c.run_profile(*self.fixture(), "combined", 1, 0, 0, 5)
        problem, masks, scores = self.fixture()
        problem["optimum"] = 16
        with self.assertRaises(ValueError):
            c.run_profile(problem, masks, scores, "classical", 1, 0, 0, 5)

    def test_profile_identity_not_substituted(self):
        result = c.run_profile(*self.fixture(), "classical", 23, 0, 0, 5)
        self.assertEqual(result["log"]["method"], "fixed")
        with self.assertRaises(ValueError):
            c.verify_profile_log("adaptive_mutation", result["log"])

    def test_first_generation_tampering(self):
        fixed = c.run_profile(*self.fixture(), "classical", 23, 0, 0, 5)["log"]
        adaptive = c.run_profile(*self.fixture(), "adaptive_crossover", 23, 0, 0, 5)["log"]
        self.assertEqual(c.verify_crossover_first_generation(fixed, adaptive)["status"], "VERIFIED")
        corrupt = copy.deepcopy(adaptive)
        corrupt["candidates"][0]["profit"] += 1
        with self.assertRaises(ValueError):
            c.verify_crossover_first_generation(fixed, corrupt)

    def test_no_local_execution(self):
        with patch.dict("os.environ", {"GITHUB_ACTIONS": "false"}):
            with self.assertRaises(ValueError):
                c.run_comparison(*self.fixture(), 1, 0, 0, 5)
