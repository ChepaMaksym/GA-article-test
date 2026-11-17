"""CI-only negative checks for technical completeness and mixed receipts."""
from copy import deepcopy
import os
import unittest

from .common import guard_technical, registered_cases
from .summarize import consolidate


class SummaryChecks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if os.environ.get("GITHUB_ACTIONS") != "true":
            raise RuntimeError("Checks run only in the authorized CI stage")
        guard_technical()

    @staticmethod
    def rows():
        return [{**case, "schema": "population13-technical-case-v1", "status": "VERIFIED",
                 "total_evaluations": 100000, "initial_evaluations": case["mu"],
                 "new_evaluations": 100000 - case["mu"], "pc_percentage": 90,
                 "mutation_basis_points": 100, "tournament_size": 2, "elite_count": 1,
                 "case_seconds_before_receipt": 10.0, "artifact_bytes_before_receipt": 1000,
                 "workflow_commit": "a" * 40, "source_manifest_sha256": "b" * 64,
                 "workflow_run_id": "12345", "reference_journal_sha256": "c" * 64,
                 "compatibility_scope": "complete_journal_except_timing_ns"}
                for case in registered_cases()]

    def test_missing_cases_never_create_main_resource_forecast(self):
        result = consolidate(self.rows()[:-1])
        self.assertEqual(result["status"], "TECHNICAL_INCOMPLETE")
        self.assertIsNone(result["main_resource_forecast"])
        self.assertFalse(result["main_stage_authorized"])

    def test_duplicate_identity_and_mixed_versions_are_rejected(self):
        rows = self.rows()
        with self.assertRaises(ValueError):
            consolidate(rows + [rows[0]])
        for field, value in (("workflow_commit", "d" * 40), ("source_manifest_sha256", "e" * 64),
                             ("workflow_run_id", "other")):
            changed = deepcopy(rows)
            changed[0][field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                consolidate(changed)

    def test_forecast_is_bounded_projection_not_main_permission(self):
        result = consolidate(self.rows())
        self.assertEqual(result["verified_cases"], 6)
        self.assertEqual(result["technical_search_evaluations"], 600000)
        self.assertFalse(result["main_stage_authorized"])
        self.assertEqual(result["main_runs_started"], 0)
        self.assertGreaterEqual(result["main_resource_forecast"]["proposed_runner_minutes"], 10)
        for value in (0, -1, float("inf"), float("nan"), True):
            damaged = self.rows()
            damaged[0]["case_seconds_before_receipt"] = value
            with self.subTest(value=value), self.assertRaises(ValueError):
                consolidate(damaged)
