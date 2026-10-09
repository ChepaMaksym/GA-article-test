"""Offline authority and rounded-time fixtures; run exclusively through CI."""

import os
from unittest import TestCase
from unittest.mock import patch

from studies.knapsack_parameters.lambda_study import contract


class BudgetAuthority(TestCase):
    def setUp(self):
        self.environ = {"GITHUB_RUN_ID": "42", "GITHUB_RUN_ATTEMPT": "1", "GITHUB_SHA": "a" * 40}
        self.run = {"id": 41, "run_attempt": 1, "name": "audit", "head_sha": "b" * 40,
                    "status": "completed", "created_at": "2026-10-09T08:01:00Z", "path": "paper.yml"}
        self.jobs = [{"conclusion": "success", "started_at": "2026-10-09T08:01:00Z",
                      "completed_at": "2026-10-09T08:02:01Z"}]

    def api(self, endpoint):
        if endpoint.startswith("/commits/"):
            return {"commit": {"committer": {"date": "2026-10-09T08:00:00Z"}}}
        if endpoint.startswith("/actions/runs?"):
            return {"workflow_runs": [self.run]}
        if "/jobs?" in endpoint:
            return {"jobs": self.jobs}
        raise AssertionError(endpoint)

    def check(self, phase="pilot"):
        with patch.dict(os.environ, self.environ), patch.object(contract, "_github_json", self.api):
            return contract.budget_preflight(phase)

    def test_ceil_each_runner_and_reserve_all_current_jobs(self):
        result = self.check()
        self.assertEqual(result["previous_rounded_runner_minutes"], 2)
        self.assertEqual(result["reserved_current_minutes"], 44)
        self.assertEqual(result["cumulative_ceiling_minutes"], 60)

    def test_failed_job_still_costs_budget(self):
        self.jobs[0]["conclusion"] = "failure"
        self.assertEqual(self.check()["previous_rounded_runner_minutes"], 2)

    def test_previous_active_run_blocks_new_spending(self):
        self.run["status"] = "in_progress"
        with self.assertRaisesRegex(ValueError, "still active"):
            self.check()

    def test_current_legacy_phase_is_reserved_not_a_false_blocker(self):
        self.run.update(status="in_progress", head_sha="a" * 40,
                        path=".github/workflows/knapsack-feasibility.yml")
        self.assertEqual(self.check()["previous_rounded_runner_minutes"], 0)

    def test_current_run_previous_attempts_are_not_free(self):
        self.environ["GITHUB_RUN_ATTEMPT"] = "3"
        self.run.update(id=42, status="in_progress", run_attempt=3)
        self.assertEqual(self.check()["previous_rounded_runner_minutes"], 4)

    def test_old_legacy_retry_attempts_are_counted(self):
        self.run.update(status="in_progress", head_sha="a" * 40, run_attempt=3,
                        path=".github/workflows/knapsack-parameters.yml")
        self.assertEqual(self.check()["previous_rounded_runner_minutes"], 4)

    def test_large_cost_blocks_without_authorizing_full_reproduction(self):
        self.jobs[0]["completed_at"] = "2026-10-09T08:20:00Z"
        with self.assertRaisesRegex(ValueError, "budget exhausted"):
            self.check()
        for phase in ("run", "full", "calibration", "main", "knapsack"):
            with self.subTest(phase=phase), self.assertRaisesRegex(ValueError, "unapproved"):
                self.check(phase)

    def test_skipped_jobs_have_no_charge(self):
        self.jobs[0] = {"conclusion": "skipped", "started_at": None, "completed_at": None}
        self.assertEqual(self.check()["previous_rounded_runner_minutes"], 0)

    def test_missing_job_time_fails_closed(self):
        self.jobs[0]["completed_at"] = None
        with self.assertRaisesRegex(ValueError, "runner time"):
            self.check()

    def test_mixed_historical_execution_markers_are_refused(self):
        for message in ("paper [knapsack:prepare]", "paper [knapsack-ga:run]"):
            with self.subTest(message=message), patch.dict(os.environ, {"COMMIT_MESSAGE": message}):
                with self.assertRaisesRegex(ValueError, "mixed historical"):
                    self.check()

    def test_rerun_of_older_run_is_not_free_after_registration(self):
        self.run.update(created_at="2026-10-08T08:00:00Z", updated_at="2026-10-09T09:00:00Z")
        self.assertEqual(self.check()["previous_rounded_runner_minutes"], 2)

    def test_old_attempt_jobs_before_registration_are_not_recharged(self):
        self.run.update(created_at="2026-10-08T08:00:00Z", updated_at="2026-10-09T09:00:00Z")
        self.jobs.insert(0, {"conclusion": "success", "started_at": "2026-10-08T08:00:00Z",
                            "completed_at": "2026-10-08T09:00:00Z"})
        self.assertEqual(self.check()["previous_rounded_runner_minutes"], 2)
