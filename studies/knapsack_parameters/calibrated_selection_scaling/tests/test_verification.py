"""Independent replay fails closed on malformed or mixed scientific journals."""
from copy import deepcopy
import os
import unittest
from unittest.mock import patch

from studies.knapsack_parameters.calibrated_selection_scaling.verification import verify_log
from studies.knapsack_parameters.calibrated_selection_scaling.tests.helpers import require_ci, run_small


class CalibratedVerificationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        require_ci()

    def assert_corruption_rejected(self, original, mutations):
        for label, mutate in mutations:
            with self.subTest(corruption=label):
                altered = deepcopy(original)
                mutate(altered)
                with self.assertRaises(ValueError):
                    verify_log(altered)

    def test_receipt_keeps_shared_independent_analysis_interface(self):
        log = run_small(profile="adaptive", budget=20)
        receipt = verify_log(log)
        self.assertEqual(receipt["verification_status"], "VERIFIED")
        self.assertEqual(receipt["new_calls"], 20)
        self.assertEqual(receipt["independent_score_checks"], 50)
        self.assertEqual(receipt["initial_score_checks"], 10)
        self.assertEqual(receipt["final_score_checks"], 20)
        self.assertEqual(receipt["premutation_score_checks"], 20)
        self.assertEqual(receipt["completed_generations"], 2)
        self.assertEqual(receipt["partial_generations"], 1)
        self.assertEqual(receipt["summary"], log["summary"])
        self.assertEqual(receipt["final_population_refs"], log["summary"]["final_population"])
        self.assertEqual(receipt["final_parameters"], log["summary"]["final_parameters"])
        metrics = receipt["derived_metrics"]
        self.assertEqual(set(metrics), {"record_events", "population_trace", "generation_trace",
                                       "operator_bins", "candidate_metrics"})
        self.assertEqual(len(metrics["generation_trace"]), 3)
        self.assertEqual(len(metrics["population_trace"]), 4)
        self.assertEqual(len(metrics["candidate_metrics"]), 20)
        self.assertEqual(sum(bucket["total"] for bucket in metrics["operator_bins"]), 20)

    def test_mask_score_operator_and_selection_corruption_is_rejected(self):
        original = run_small()
        self.assert_corruption_rejected(original, [
            ("mask", lambda log: log["candidates"][0].__setitem__("mask", "x" * 6)),
            ("score", lambda log: log["candidates"][0].__setitem__("profit", -1)),
            ("initial score", lambda log: log["initial_scores"][0].__setitem__("profit", 99)),
            ("mutation", lambda log: log["candidates"][0].__setitem__("mutation_bits", [99])),
            ("crossover", lambda log: log["candidates"][0].__setitem__("crossover", not log["candidates"][0]["crossover"])),
            ("parent", lambda log: log["candidates"][0].__setitem__("parent_indices", [99, 99])),
            ("tournament", lambda log: log["candidates"][0].__setitem__("tournaments", [[0], [0]])),
            ("record", lambda log: log["candidates"][0].__setitem__("record_call", 999)),
            ("duplicate", lambda log: log["candidates"][0].__setitem__("duplicate", not log["candidates"][0]["duplicate"])),
        ])

    def test_every_rng_boundary_and_channel_identity_is_checked(self):
        original = run_small()
        self.assert_corruption_rejected(original, [
            ("initial state", lambda log: log["rng_initial"]["selection"]["state"].__setitem__("state", 0)),
            ("final state", lambda log: log["rng_final"]["mutation"]["state"].__setitem__("state", 0)),
            ("generation before", lambda log: log["generations"][0]["rng_before"]["ties"]["state"].__setitem__("state", 0)),
            ("generation after", lambda log: log["generations"][0]["rng_after"]["branch"]["state"].__setitem__("state", 0)),
            ("missing channel", lambda log: log["rng_initial"].pop("initialization")),
            ("wrong bit generator", lambda log: log["rng_initial"]["ties"].__setitem__("bit_generator", "MT19937")),
        ])

    def test_missing_duplicate_reordered_and_extra_queries_are_rejected(self):
        original = run_small()
        self.assert_corruption_rejected(original, [
            ("missing query", lambda log: log["candidates"].pop()),
            ("extra query", lambda log: log["candidates"].append(deepcopy(log["candidates"][-1]))),
            ("duplicate query", lambda log: log["candidates"].__setitem__(1, deepcopy(log["candidates"][0]))),
            ("query numbering", lambda log: log["candidates"][0].__setitem__("call", 2)),
            ("missing generation", lambda log: log["generations"].pop()),
            ("duplicate generation", lambda log: log["generations"].append(deepcopy(log["generations"][-1]))),
            ("generation coverage", lambda log: log["generations"][0].__setitem__("end_call", 8)),
        ])

    def test_mixed_schema_contract_profile_and_schedule_fail_closed(self):
        original = run_small()
        self.assert_corruption_rejected(original, [
            ("old schema", lambda log: log.__setitem__("schema", "ga-knapsack-fixed-mutation-grid-log-v1")),
            ("mixed contract", lambda log: log.__setitem__("configuration_contract", "fixed-mutation-grid-v1")),
            ("integer profile", lambda log: log.__setitem__("profile", 0)),
            ("unsupported profile", lambda log: log.__setitem__("profile", "k4")),
            ("initial k mismatch", lambda log: log.__setitem__("profile", "k3")),
            ("nonempty schedule", lambda log: log.__setitem__("schedule", [2])),
            ("empty schedule", lambda log: log.__setitem__("schedule", [])),
            ("missing schedule", lambda log: log.pop("schedule")),
            ("extra top-level", lambda log: log.update(optimum=100)),
        ])

    def test_initial_and_disabled_parameters_are_independently_checked(self):
        original = run_small(profile="adaptive", n=500)
        self.assert_corruption_rejected(original, [
            ("wrong pm", lambda log: log["initial_parameters"].__setitem__("p_m", .01)),
            ("wrong pc", lambda log: log["initial_parameters"].__setitem__("p_c", 1.1)),
            ("boolean probability", lambda log: log["initial_parameters"].__setitem__("p_c", True)),
            ("initial k", lambda log: log["initial_parameters"].__setitem__("tournament_size", 3)),
            ("size mismatch", lambda log: log.__setitem__("initial_population_size", 11)),
            ("disabled parameter before", lambda log: log["generations"][0]["parameters_before"].__setitem__("p_c", .5)),
            ("disabled parameter after", lambda log: log["generations"][0]["parameters_after"].__setitem__("target_mu", 20)),
            ("wrong monitoring bound", lambda log: log["generations"][0]["parameter_events"][0].__setitem__("at_boundary", True)),
        ])

    def test_controller_population_partial_and_summary_corruption_is_rejected(self):
        original = run_small(profile="adaptive")
        self.assert_corruption_rejected(original, [
            ("wrong update", lambda log: log["generations"][0]["parameters_after"].__setitem__("tournament_size", 99)),
            ("wrong enabled flag", lambda log: log["generations"][0]["parameter_events"][3].__setitem__("enabled", False)),
            ("wrong success", lambda log: log["generations"][0].__setitem__("success", not log["generations"][0]["success"])),
            ("wrong failure count", lambda log: log["generations"][0].__setitem__("failed_queries_after", 99)),
            ("wrong population", lambda log: log["generations"][0].__setitem__("population_after", [0] * 10)),
            ("partial update", lambda log: log["generations"][-1].__setitem__("controller_event", "SUCCESS")),
            ("partial population", lambda log: log["generations"][-1].__setitem__("population_after", [0] * 10)),
            ("summary", lambda log: log["summary"].__setitem__("new_calls", 999)),
            ("negative timing", lambda log: log["timing_ns"].__setitem__("evaluation", -1)),
        ])

    def test_replay_guard_does_not_accept_local_execution(self):
        log = run_small()
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(ValueError, "GitHub Actions required"):
                verify_log(log)


if __name__ == "__main__":
    require_ci()
    unittest.main()
