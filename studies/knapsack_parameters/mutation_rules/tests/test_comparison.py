"""CI-only educational fixtures, not KPLIB scientific results."""
from __future__ import annotations

from copy import deepcopy
import json
import os
import unittest
from unittest.mock import patch

from studies.adaptive_parameters.mutation_only import engine
from studies.knapsack_parameters.mutation_rules import comparison
from studies.knapsack_parameters.mutation_rules.verifier import verify_sd_view


class BoundedComparisonTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if (os.environ.get("GITHUB_ACTIONS") != "true" or
                os.environ.get("GITHUB_REPOSITORY") != "ChepaMaksym/GA-article-test" or
                os.environ.get("GITHUB_REF") !=
                "refs/heads/research/masters-ga-diversity-crossover"):
            raise RuntimeError("Mutation comparison tests execute only in the registered CI branch")
        cls.problem = {"n": 100, "weights": [1] * 100,
                       "profits": [1] * 100, "capacity": 50}
        cls.masks = ["0" * 100] * 30
        cls.scores = [{"weight": 0, "profit": 0, "feasible": True} for _ in range(30)]
        cls.log = engine.run_search(cls.problem, cls.masks, cls.scores, "fixed",
                                    engine.make_rngs(17, 0, 0), 61)
        cls.view = comparison.derive_sd_view(cls.log)

    def test_derived_view_preserves_source_and_zero_extra_search(self):
        before = json.dumps(self.log, sort_keys=True, ensure_ascii=False, allow_nan=False)
        view = comparison.derive_sd_view(self.log)
        self.assertEqual(json.dumps(self.log, sort_keys=True, ensure_ascii=False, allow_nan=False), before)
        self.assertEqual(self.log["method"], "fixed")
        self.assertEqual(view["requested_profile"], "paper_sd_mutation")
        self.assertEqual(view["backend_profile"], "fixed")
        self.assertEqual(view["status"], "BOUNDED_EQUIVALENCE")
        self.assertEqual(view["accounting"]["additional_physical_search_evaluations"], 0)
        self.assertEqual(view["accounting"]["logical_profile_search_evaluations"], 61)
        self.assertEqual(view["accounting"]["new_independent_search_runs"], 0)
        self.assertEqual(view["construction_verification"]["source_operator_replay_score_checks"], 91)

    def test_independent_high_precision_proof_covers_full_registered_budget(self):
        report = verify_sd_view(self.log, self.view)
        self.assertEqual(report["verification_status"], "VERIFIED")
        self.assertEqual(report["decimal_precision"], 80)
        self.assertEqual(report["independent_source_score_checks"], 91)
        self.assertGreater(float(report["threshold_r1"]), 5000)
        self.assertLess(float(report["threshold_r1"]), 5300)
        self.assertEqual(report["final_radius"], 1)

    def test_every_transition_stays_at_fixed_one_percent(self):
        for row in self.view["controller_trace"]:
            self.assertEqual(row["r_before"], 1)
            self.assertEqual(row["r_after"], 1)
            self.assertEqual(row["p_m"], 0.01)
            self.assertEqual(row["p_m_next"], 0.01)
            self.assertGreater(row["threshold"], 5000)

    def test_last_partial_prefix_is_not_a_controller_update(self):
        rows = self.view["controller_trace"]
        self.assertEqual(len(rows), 3)
        self.assertTrue(rows[0]["complete"])
        self.assertTrue(rows[1]["complete"])
        self.assertFalse(rows[2]["complete"])
        self.assertEqual(rows[2]["children"], 3)
        self.assertEqual(rows[2]["event"], "PARTIAL_NO_UPDATE")
        self.assertEqual(rows[2]["u_before"], rows[2]["u_after"])
        self.assertEqual(rows[2]["r_before"], rows[2]["r_after"])

    def test_reject_outside_domain_before_source_replay(self):
        for budget in (0, True, 5001, 61.0):
            wrong = deepcopy(self.log)
            wrong["budget"] = budget
            with self.subTest(budget=budget), patch.object(comparison.historical, "verify_log") as replay:
                with self.assertRaises(ValueError):
                    comparison.derive_sd_view(wrong)
                replay.assert_not_called()
        wrong = deepcopy(self.log)
        wrong["problem"]["n"] = 99
        with self.assertRaises(ValueError):
            comparison.derive_sd_view(wrong)

    def test_reject_adaptive_source_or_oracle_input(self):
        wrong = deepcopy(self.log)
        wrong["method"] = "adaptive_mutation"
        with self.assertRaises(ValueError):
            comparison.derive_sd_view(wrong)
        for extra in ("optimum", "certificate", "optimal_mask"):
            problem = {**self.problem, extra: 123}
            with self.subTest(extra=extra), self.assertRaises(ValueError):
                comparison.run_comparison(problem, self.masks, self.scores, 17, 0, 0, budget=1)

    def test_independent_verifier_does_not_trust_production_threshold(self):
        with patch.object(comparison.controller, "threshold", return_value=6000.0):
            corrupt = comparison.derive_sd_view(self.log)
        with self.assertRaises(ValueError):
            verify_sd_view(self.log, corrupt)

    def test_reject_tampered_transitions_and_missing_rows(self):
        changes = (("u_after", 777), ("p_m_next", 0.02),
                   ("r_before", 2), ("threshold", 6000.0),
                   ("strict_success", "true"), ("event", "STAGNATION_INCREASE"))
        for field, value in changes:
            wrong = deepcopy(self.view)
            wrong["controller_trace"][0][field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                verify_sd_view(self.log, wrong)
        wrong = deepcopy(self.view)
        wrong["controller_trace"].pop()
        with self.assertRaises(ValueError):
            verify_sd_view(self.log, wrong)
        wrong = deepcopy(self.view)
        wrong["controller_trace"][-1]["u_after"] += 3
        with self.assertRaises(ValueError):
            verify_sd_view(self.log, wrong)

    def test_reject_source_hash_shape_and_accounting_tampering(self):
        wrong = deepcopy(self.view)
        wrong["source_journal_sha256"] = "0" * 64
        with self.assertRaises(ValueError):
            verify_sd_view(self.log, wrong)
        for field, value in (("additional_physical_search_evaluations", 61),
                             ("logical_profile_search_evaluations", 60),
                             ("new_independent_search_runs", 1)):
            wrong = deepcopy(self.view)
            wrong["accounting"][field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                verify_sd_view(self.log, wrong)
        wrong = deepcopy(self.view)
        wrong["proof"]["radius_inactive"] = 1
        with self.assertRaises(ValueError):
            verify_sd_view(self.log, wrong)
        wrong = deepcopy(self.view)
        wrong["extra"] = "unregistered"
        with self.assertRaises(ValueError):
            verify_sd_view(self.log, wrong)

    def test_source_operator_replay_is_required_even_with_correct_hash(self):
        wrong_log = deepcopy(self.log)
        wrong_log["candidates"][0]["profit"] += 1
        wrong_view = deepcopy(self.view)
        wrong_view["source_journal_sha256"] = comparison.source_journal_sha256(wrong_log)
        with self.assertRaises(ValueError):
            verify_sd_view(wrong_log, wrong_view)

    def test_three_profiles_have_only_two_physical_search_paths(self):
        result = comparison.run_comparison(self.problem, self.masks, self.scores,
                                           19, 0, 0, budget=61)
        self.assertEqual(set(result["profiles"]), set(comparison.PROFILES))
        self.assertEqual(result["profiles"]["fixed"]["log"]["method"], "fixed")
        self.assertEqual(result["profiles"]["own_adaptive_mutation"]["log"]["method"],
                         "adaptive_mutation")
        self.assertEqual(result["paired_first_generation"]["status"], "VERIFIED")
        counts = result["accounting"]
        self.assertEqual(counts["physical_search_runs"], 2)
        self.assertEqual(counts["physical_search_evaluations"], 122)
        self.assertEqual(counts["logical_profiles"], 3)
        self.assertEqual(counts["logical_profile_search_evaluations"], 183)
        self.assertEqual(counts["derived_additional_physical_search_evaluations"], 0)
        self.assertEqual(counts["operator_replay_score_checks"], 364)
        self.assertEqual(counts["initial_score_validation_evaluations"], 60)
        self.assertEqual(counts["independent_sd_controller_events"], 3)

    def test_ci_guard_fails_before_any_search(self):
        with patch.dict(os.environ, {"GITHUB_ACTIONS": "false"}), \
                patch.object(comparison.old_search, "run_profile") as search:
            with self.assertRaises(ValueError):
                comparison.run_comparison(self.problem, self.masks, self.scores, 17, 0, 0, 1)
            with self.assertRaises(ValueError):
                comparison.derive_sd_view(self.log)
            with self.assertRaises(ValueError):
                verify_sd_view(self.log, self.view)
            search.assert_not_called()


if __name__ == "__main__":
    unittest.main()
