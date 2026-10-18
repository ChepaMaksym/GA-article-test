"""CI-only comparison-wrapper fixtures, not evidence of scientific advantage."""
from copy import deepcopy
import os
import unittest
from unittest.mock import patch

from .. import knapsack_comparison as c


class ComparisonTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        c._ci_only()
        cls.problem = {"n": 3, "weights": [6, 5, 5], "profits": [10, 8, 8], "capacity": 10}
        cls.masks = ["100"] * 30
        cls.scores = [{"weight": 6, "profit": 10, "feasible": True} for _ in cls.masks]
        cls.result = c.run_comparison(cls.problem, cls.masks, cls.scores, 17, 0, 0, budget=61)

    def test_three_real_profiles_same_budget_and_initial_rng(self):
        result = self.result
        self.assertEqual(set(result["profiles"]), set(c.PROFILES))
        logs = [item["log"] for item in result["profiles"].values()]
        self.assertTrue(all(log["budget"] == 61 and len(log["candidates"]) == 61 for log in logs))
        self.assertTrue(all(log["initial_masks"] == self.masks for log in logs))
        self.assertTrue(all(log["rng_initial"] == logs[0]["rng_initial"] for log in logs))
        self.assertEqual(result["accounting"]["physical_new_search_evaluations"], 183)
        self.assertEqual(result["accounting"]["initial_score_validation_evaluations"], 90)
        self.assertEqual(result["accounting"]["independent_score_checks"], 273)

    def test_classical_keeps_original_fixed_label(self):
        classical = self.result["profiles"]["classical"]
        self.assertEqual(classical["requested_profile"], "classical")
        self.assertEqual(classical["log"]["method"], "fixed")
        self.assertEqual(classical["verification"]["verification_status"], "VERIFIED")

    def test_archive_first_generation_equality_not_forced_on_classical(self):
        pair = self.result["archive_first_generation_pairing"]
        self.assertEqual(pair["status"], "VERIFIED")
        self.assertEqual(pair["first_generation_calls"], 29)
        self.assertFalse(pair["classical_first_generation_equality_required"])
        left = self.result["profiles"]["unbalanced_gap"]["log"]
        right = deepcopy(self.result["profiles"]["balanced_gap"]["log"])
        right["candidates"][0]["profit"] += 1
        with self.assertRaises(ValueError):
            c.verify_first_generation(left, right)

    def test_observations_keep_record_mean_and_unused_archive_distinct(self):
        for method, row in self.result["descriptive"].items():
            self.assertEqual(row["new_search_evaluations"], 61)
            self.assertEqual(row["parent_uses_counted_even_for_same_mask"], 122)
            self.assertGreaterEqual(row["best_feasible_profit"], row["final_population_feasible_mean"])
            self.assertEqual(row["full_generations"], 2)
            self.assertEqual(row["terminal_prefix_children"], 3)
            self.assertGreaterEqual(row["final_population_normalized_hamming"], 0)
            self.assertLessEqual(row["final_population_normalized_hamming"], 1)
            if method == "classical":
                self.assertIsNone(row["final_archive_size"])
            else:
                self.assertGreaterEqual(row["final_archive_size"], 1)

    def test_bad_profiles_or_oracle_or_all_invalid_initials_refused(self):
        for method in ("BNTGA_FULL", "adaptive_mutation", "adaptive_population"):
            with self.subTest(method=method), self.assertRaises(ValueError):
                c.run_profile(self.problem, self.masks, self.scores, method, 17, 0, 0, 1)
        with self.assertRaises(ValueError):
            c.run_comparison({**self.problem, "optimum": 16}, self.masks, self.scores, 17, 0, 0, 1)
        with self.assertRaises(ValueError):
            c.run_comparison(self.problem, ["111"] * 30,
                [{"weight": 16, "profit": 26, "feasible": False}] * 30, 17, 0, 0, 1)

    def test_no_execution_outside_ci(self):
        with patch.dict(os.environ, {"GITHUB_ACTIONS": "false"}), self.assertRaises(ValueError):
            c.run_comparison(self.problem, self.masks, self.scores, 17, 0, 0, 1)

    def test_explicit_teaching_scope_and_not_new_KPLIB_evidence(self):
        report = c.teaching_knapsack_comparison()
        self.assertIn("not_KPLIB", report["scope"])
        self.assertEqual(report["new_queries_per_profile"], 61)
        self.assertEqual(report["independent_global_witness"], {"mask": "011", "weight": 10, "profit": 16})
