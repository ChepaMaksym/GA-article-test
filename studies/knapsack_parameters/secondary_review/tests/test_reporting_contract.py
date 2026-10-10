"""Small contract/report fixtures; execute only in the registered CI workflow."""
from copy import deepcopy
import os
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path

from studies.knapsack_parameters.secondary_review import contract
from studies.knapsack_parameters.secondary_review.reporting import number, population_points, report_status
from studies.knapsack_parameters.secondary_review import reporting


def fixture():
    identity = {key: "fixed" for key in ("protocol_id", "protocol_sha256", "implementation_commit_sha",
        "implementation_fingerprint", "source_implementation_commit_sha", "source_summaries_sha256", "registry_sha256")}
    identity.update(protocol_id=contract.PROTOCOL_ID, run_id=123, run_attempt=1,
                    source_run_id=contract.SOURCE_RUN, new_search_runs=0, new_exact_solver_runs=0)
    analysis = {**identity, "status": "COMPLETE_COMPACT_ANALYSIS", "exploratory": True,
                "counts": {"runs": 35640}, "loo": [None] * 10, "correlations": [None] * 4,
                "configuration_summaries": [None] * 54}
    trace = {"protocol_id": contract.PROTOCOL_ID, "provenance": identity.copy(),
        "expected_case_count": 6, "verified_case_count": 0, "cases": [],
        "source": {"artifact_id": 11557059267, "run_id": contract.SOURCE_RUN,
                   "implementation_commit_sha": contract.SOURCE_SHA},
        "status": "PARTIAL_TRACE_AUDIT", "fault": {"replacement_selected": False}, "retained_traces": None}
    tests = {"schema_version": "ga-knapsack-secondary-tests-v1", "provenance": identity.copy(),
             "outcome": "success", "passed": True, "test_count": 10}
    return analysis, trace, tests, identity


class ReportingTests(unittest.TestCase):
    def test_unavailable_trace_does_not_become_complete(self):
        self.assertEqual(report_status(*fixture()), "PARTIAL_TRACE_AUDIT")

    def test_mixed_implementation_or_failed_tests_rejected(self):
        for field in ("implementation_commit_sha", "run_id", "run_attempt", "source_run_id"):
            values = fixture()
            values[0][field] = "other"
            with self.subTest(field=field), self.assertRaises(ValueError):
                report_status(*values)
        values = fixture()
        values[2]["passed"] = False
        with self.assertRaises(ValueError):
            report_status(*values)

    def test_substitute_source_rejected(self):
        values = fixture()
        values[1]["source"]["artifact_id"] = 999
        with self.assertRaises(ValueError):
            report_status(*values)

    def test_duplicate_or_missing_full_case_rejected(self):
        values = fixture()
        trace = values[1]
        trace.update(status="COMPLETE_TRACE_AUDIT", verified_case_count=6, retained_traces={"path": "a"})
        trace["cases"] = [{"verified": True, "identity": {"start_profile": start,
            "configuration_id": config, "instance_id": "UC-s000", "repeat_seed": 51001}}
            for start in ("random", "local") for config in ("m0p5-c0p9-n30", "m1-c0p9-n30", "m3-c0p9-n30")]
        self.assertEqual(report_status(*values), "COMPLETE_SECONDARY_REVIEW")
        trace["cases"][0] = deepcopy(trace["cases"][1])
        with self.assertRaises(ValueError):
            report_status(*values)

    def test_constant_rho_not_rendered_as_zero(self):
        self.assertEqual(number(None), "не визначено")
        self.assertEqual(number(0), "0,0000")

    def test_partial_generation_not_extended_as_population(self):
        rows = [{"generation": 0, "complete": True}, {"generation": 1, "complete": True},
                {"generation": 2, "complete": False}]
        self.assertEqual(population_points(rows), rows[:2])

    def test_output_rejects_checkout_and_existing_files(self):
        with self.assertRaises(ValueError):
            contract.output_directory(contract.ROOT)
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary)
            (path / "prior.json").write_text("{}")
            with self.assertRaises(ValueError):
                contract.output_directory(path)

    def test_failure_handler_never_remanifests_existing_evidence(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary)
            retained = path / "file_manifest.json"
            retained.write_bytes(b"original proof")
            with patch.dict(os.environ, {"GITHUB_ACTIONS": "true"}), \
                    patch.object(reporting, "aggregate", side_effect=ValueError("identity rejected")), \
                    self.assertRaises(ValueError):
                reporting.main(["--expected-sha", "other", "--output", str(path)])
            self.assertEqual(retained.read_bytes(), b"original proof")
            self.assertEqual({entry.name for entry in path.iterdir()}, {"file_manifest.json"})


class BudgetTests(unittest.TestCase):
    def response(self, endpoint, *, costly=False, running=False):
        if endpoint.startswith("/commits/"):
            return {"commit": {"committer": {"date": "2026-10-09T00:00:00Z"}}}
        if endpoint.startswith("/actions/runs?"):
            return {"workflow_runs": [{"id": 1, "updated_at": "2026-10-09T01:00:00Z",
                "created_at": "2026-10-09T01:00:00Z", "head_sha": "old", "path": "review.yml",
                "name": "prior", "status": "in_progress" if running else "completed", "run_attempt": 1}]}
        return {"jobs": [{"conclusion": "failure", "started_at": "2026-10-09T01:00:00Z",
            "completed_at": "2026-10-09T01:21:01Z" if costly else "2026-10-09T01:00:01Z"},
            {"conclusion": "skipped", "started_at": None, "completed_at": None}]}

    def test_failed_attempt_counted_and_skipped_not_counted(self):
        with patch.dict(os.environ, {"GITHUB_RUN_ID": "9", "GITHUB_RUN_ATTEMPT": "1", "GITHUB_SHA": "new"}), \
                patch.object(contract, "_api", side_effect=self.response):
            result = contract.budget_preflight("analyze")
        self.assertEqual(result["previous_rounded_runner_minutes"], 1)
        self.assertEqual(result["reserved_current_minutes"], 40)

    def test_over_budget_does_not_execute(self):
        with patch.dict(os.environ, {"GITHUB_RUN_ID": "9", "GITHUB_RUN_ATTEMPT": "1", "GITHUB_SHA": "new"}), \
                patch.object(contract, "_api", side_effect=lambda endpoint: self.response(endpoint, costly=True)), \
                self.assertRaisesRegex(ValueError, "budget exhausted"):
            contract.budget_preflight("analyze")

    def test_active_prior_run_blocks_and_mixed_markers_block(self):
        with patch.dict(os.environ, {"GITHUB_RUN_ID": "9", "GITHUB_RUN_ATTEMPT": "1", "GITHUB_SHA": "new"}), \
                patch.object(contract, "_api", side_effect=lambda endpoint: self.response(endpoint, running=True)), \
                self.assertRaisesRegex(ValueError, "still active"):
            contract.budget_preflight("analyze")
        with patch.dict(os.environ, {"COMMIT_MESSAGE": "[knapsack-ga:main]"}), self.assertRaisesRegex(ValueError, "mixed"):
            contract.budget_preflight("analyze")


if __name__ == "__main__":
    unittest.main()
