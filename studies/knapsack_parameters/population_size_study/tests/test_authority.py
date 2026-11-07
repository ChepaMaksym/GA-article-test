"""CI-only fixtures for fresh grants, cumulative attempts and bounded permits."""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from studies.knapsack_parameters.population_size_study import authority as a


def grant():
    return {"protocol_id": a.PROTOCOL, "explicit_user_numeric_approval": True,
            "execution_authorized": True, "runner_minutes_ceiling": 160,
            "compressed_bytes_ceiling": 4 * 1024**3, "historical_budgets_reassigned": False,
            "approved_phases": list(a.PHASES), "tuning_authorized": False, "main_authorized": False,
            "approval_record": {"approved_at_utc": "2026-01-01T00:00:00Z", "user_message": "Fixture approval",
                                "runner_minutes_ceiling": 160, "compressed_bytes_ceiling": 4 * 1024**3}}


def run(identifier, attempts, status="completed"):
    return {"id": identifier, "run_attempt": attempts, "path": a.WORKFLOW,
            "head_branch": a.BRANCH, "status": status}


def job(identifier, seconds, conclusion="success"):
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    from datetime import timedelta
    return {"id": identifier, "name": "fixture", "status": "completed", "conclusion": conclusion,
            "started_at": start.isoformat(), "completed_at": (start + timedelta(seconds=seconds)).isoformat()}


def artifact(identifier, run_id, size, expired=False):
    return {"id": identifier, "name": "fixture", "size_in_bytes": size,
            "expired": expired, "workflow_run": {"id": run_id}}


@unittest.skipUnless(os.environ.get("GITHUB_ACTIONS") == "true", "Authority fixtures run only in GitHub Actions")
class AuthorityTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.directory = Path(self.temporary.name)

    def test_fresh_numeric_approval_is_required(self):
        for field in ("explicit_user_numeric_approval", "execution_authorized"):
            invalid = grant()
            invalid[field] = False
            with self.assertRaisesRegex(ValueError, "SEPARATE_NUMERIC"):
                a.validate_grant(invalid, "tests")

    def test_approval_record_is_required(self):
        for missing in (None, {}, {"user_message": " "}):
            invalid = grant()
            invalid["approval_record"] = missing
            with self.assertRaises(ValueError):
                a.validate_grant(invalid, "tests")

    def test_recorded_numeric_ceilings_must_match(self):
        invalid = grant()
        invalid["runner_minutes_ceiling"] = 170
        with self.assertRaisesRegex(ValueError, "ceilings differ"):
            a.validate_grant(invalid, "tests")

    def test_historical_budgets_cannot_be_reassigned(self):
        invalid = grant()
        invalid["historical_budgets_reassigned"] = True
        with self.assertRaises(ValueError):
            a.validate_grant(invalid, "tests")

    def test_future_approval_is_rejected(self):
        invalid = grant()
        invalid["approval_record"]["approved_at_utc"] = "2099-01-01T00:00:00Z"
        with self.assertRaisesRegex(ValueError, "future"):
            a.validate_grant(invalid, "tests", now=datetime(2026, 1, 2, tzinfo=timezone.utc))

    def test_approval_timezone_is_required(self):
        invalid = grant()
        invalid["approval_record"]["approved_at_utc"] = "2026-01-01T00:00:00"
        with self.assertRaisesRegex(ValueError, "timezone"):
            a.validate_grant(invalid, "tests")

    def test_expired_grant_is_rejected(self):
        invalid = grant()
        invalid["valid_until_utc"] = "2026-01-02T00:00:00Z"
        with self.assertRaisesRegex(ValueError, "expired"):
            a.validate_grant(invalid, "tests", now=datetime(2026, 1, 3, tzinfo=timezone.utc))

    def test_scientific_execution_phases_are_absent(self):
        for phase in ("tune", "tuning", "main", "holdout", "all", ""):
            with self.assertRaisesRegex(ValueError, "UNREGISTERED"):
                a.validate_grant(grant(), phase)

    def test_push_requires_exactly_one_matching_marker(self):
        a.validate_requested_phase("tests", "push", "Run [population-size:tests]")
        for message in ("No phase", "[population-size:main]", "[population-size:pilot]",
                        "[population-size:tests] [population-size:pilot]", "[population-size:tests"):
            with self.assertRaises(ValueError):
                a.validate_requested_phase("tests", "push", message)

    def test_dispatch_allows_only_registered_phases(self):
        a.validate_requested_phase("tests", "workflow_dispatch")
        with self.assertRaises(ValueError):
            a.validate_requested_phase("main", "workflow_dispatch")
        with self.assertRaises(ValueError):
            a.validate_requested_phase("tests", "pull_request")

    def test_tuning_or_main_cannot_be_folded_into_technical_grant(self):
        for field in ("tuning_authorized", "main_authorized"):
            invalid = grant()
            invalid[field] = True
            with self.assertRaises(ValueError):
                a.validate_grant(invalid, "tests")

    def test_reservations_match_full_job_timeouts_and_rounding_margin(self):
        self.assertEqual(a.RESERVATIONS["tests"], 1 + 8 + 2)
        self.assertEqual(a.RESERVATIONS["prepare-pilot"], 1 + 20 + 2)
        self.assertEqual(a.RESERVATIONS["pilot"], 1 + 9 * 8 + 6 + 11)
        self.assertLessEqual(9 * a.MAX_WORKER_COMPRESSED_BYTES + 16 * 1024**2, a.BYTE_RESERVATIONS["pilot"])

    def test_insufficient_time_blocks_phase(self):
        usage = {"used_runner_minutes": 71, "used_compressed_bytes": 0}
        with self.assertRaisesRegex(ValueError, "RUNNER_MINUTES"):
            a.check_allowance("pilot", usage, grant())

    def test_insufficient_artifact_capacity_blocks_phase(self):
        usage = {"used_runner_minutes": 0, "used_compressed_bytes": 1024**3 + 1}
        with self.assertRaisesRegex(ValueError, "ARTIFACT_CAPACITY"):
            a.check_allowance("pilot", usage, grant())

    def test_exact_remaining_capacity_is_allowed(self):
        usage = {"used_runner_minutes": 70, "used_compressed_bytes": 1024**3}
        a.check_allowance("pilot", usage, grant())

    def test_unknown_usage_is_rejected(self):
        for invalid in ({}, {"used_runner_minutes": None, "used_compressed_bytes": 0},
                        {"used_runner_minutes": 0, "used_compressed_bytes": -1}):
            with self.assertRaisesRegex(ValueError, "UNKNOWN_CUMULATIVE"):
                a.check_allowance("tests", invalid, grant())

    def test_pagination_includes_the_second_page(self):
        first = [{"id": value} for value in range(100)]
        with patch.object(a, "api", side_effect=[{"jobs": first, "total_count": 101},
                                                {"jobs": [{"id": 100}], "total_count": 101}]) as api:
            values = list(a.pages("/actions/runs/1/jobs", "jobs"))
        self.assertEqual(len(values), 101)
        self.assertIn("page=2", api.call_args_list[1].args[0])

    def test_unknown_paginated_response_fails_closed(self):
        with patch.object(a, "api", return_value={"jobs": None}):
            with self.assertRaises(ValueError):
                list(a.pages("/actions/runs/1/jobs", "jobs"))

    def test_truncated_or_changed_pagination_fails_closed(self):
        with patch.object(a, "api", return_value={"jobs": [], "total_count": 1}):
            with self.assertRaisesRegex(ValueError, "INCOMPLETE_PAGINATED"):
                list(a.pages("/actions/runs/1/jobs", "jobs"))
        first = [{"id": value} for value in range(100)]
        with patch.object(a, "api", side_effect=[{"jobs": first, "total_count": 101},
                                                {"jobs": [{"id": 100}], "total_count": 102}]):
            with self.assertRaisesRegex(ValueError, "changed during"):
                list(a.pages("/actions/runs/1/jobs", "jobs"))

    def test_all_attempts_failures_cancellations_and_artifacts_are_counted(self):
        calls = []
        def rows(endpoint, key):
            calls.append((endpoint, key))
            if key == "workflow_runs":
                return iter([run(10, 2), run(20, 2, "in_progress")])
            mapping = {
                "/actions/runs/10/attempts/1/jobs": [job(101, 61, "failure")],
                "/actions/runs/10/attempts/2/jobs": [job(102, 1, "cancelled")],
                "/actions/runs/20/attempts/1/jobs": [job(103, 120)],
                "/actions/runs/10/artifacts": [artifact(1, 10, 10), artifact(2, 10, 20, True)],
                "/actions/runs/20/artifacts": [artifact(3, 20, 30)],
            }
            return iter(mapping[endpoint])
        with patch.object(a, "MODULE", self.directory), patch.object(a, "pages", side_effect=rows):
            usage = a.resource_usage(20, 2)
        self.assertEqual(usage["used_runner_minutes"], 5)
        self.assertEqual(usage["used_compressed_bytes"], 60)
        self.assertFalse(any("/20/attempts/2/jobs" in endpoint for endpoint, _ in calls))

    def test_active_previous_workflow_blocks_accounting(self):
        with patch.object(a, "MODULE", self.directory), patch.object(a, "pages", return_value=iter([run(10, 1, "queued")])):
            with self.assertRaisesRegex(ValueError, "ACTIVE_OR_UNKNOWN"):
                a.resource_usage(20, 1)

    def test_unknown_allocated_job_duration_blocks_accounting(self):
        invalid = job(1, 1)
        invalid["completed_at"] = None
        with self.assertRaises(ValueError):
            a._duration_minutes(invalid)

    def test_job_rounding_is_per_allocated_job(self):
        self.assertEqual(a._duration_minutes(job(1, 1)), 1)
        self.assertEqual(a._duration_minutes(job(2, 61)), 2)

    def test_unsafe_evidence_paths_are_rejected(self):
        for value in ("../escape", "/absolute", "C:/absolute", "nested\\file", ""):
            with self.assertRaises(ValueError):
                a.safe_child(self.directory, value)

    def test_manifest_detects_missing_extra_or_changed_evidence(self):
        artifact_dir = self.directory / "artifact"
        artifact_dir.mkdir()
        (artifact_dir / "receipt.json").write_text("{}", encoding="utf-8")
        a.write_manifest(artifact_dir)
        a.verify_manifest(artifact_dir)
        (artifact_dir / "receipt.json").write_text('{"altered":true}', encoding="utf-8")
        with self.assertRaises(ValueError):
            a.verify_manifest(artifact_dir)

    def test_manifest_inventory_rejects_missing_and_extra_files(self):
        for label in ("missing", "extra"):
            with self.subTest(label=label):
                artifact_dir = self.directory / label
                artifact_dir.mkdir()
                (artifact_dir / "receipt.json").write_text("{}", encoding="utf-8")
                a.write_manifest(artifact_dir)
                if label == "missing":
                    (artifact_dir / "receipt.json").unlink()
                else:
                    (artifact_dir / "unlisted.json").write_text("{}", encoding="utf-8")
                with self.assertRaises((ValueError, FileNotFoundError)):
                    a.verify_manifest(artifact_dir)

    def test_nested_manifest_is_part_of_parent_inventory(self):
        artifact_dir = self.directory / "nested"
        (artifact_dir / "mathematics").mkdir(parents=True)
        (artifact_dir / "mathematics" / "curves.csv").write_text("n,mu\n100,2\n", encoding="utf-8")
        a.write_manifest(artifact_dir / "mathematics")
        a.write_manifest(artifact_dir)
        manifest = a.verify_manifest(artifact_dir)
        self.assertIn("mathematics/file_manifest.json", [row["path"] for row in manifest["files"]])

    def test_internal_symlink_is_not_accepted_as_evidence(self):
        target = self.directory / "original.json"
        target.write_text("{}", encoding="utf-8")
        link = self.directory / "linked.json"
        link.symlink_to(target)
        with self.assertRaisesRegex(ValueError, "Linked"):
            a.safe_child(self.directory, "linked.json")

    def test_missing_retained_artifact_blocks_resource_accounting(self):
        a.write_json(self.directory / "frozen_tests.json", {"artifact_id": 99})
        with patch.object(a, "MODULE", self.directory), patch.object(a, "pages", return_value=iter([])):
            with self.assertRaisesRegex(ValueError, "MISSING_PREVIOUSLY_RECORDED"):
                a.resource_usage(20, 1)

    def test_permit_rejects_foreign_attempt_or_changed_authorization(self):
        provenance = {"protocol_id": a.PROTOCOL, "implementation_sha": "a" * 40,
                      "source_manifest": {"sha256": "b" * 64}, "run_id": 20, "run_attempt": 1,
                      "actor": "fixture", "environment": {}}
        authorization = grant()
        auth_id = {"sha256": "c" * 64, "bytes": 1}
        permit = {**provenance, "phase": "tests", "grant": authorization,
                  "resource_authorization_identity": auth_id, "frozen_receipt_identities": {},
                  "reserved_runner_minutes": a.RESERVATIONS["tests"],
                  "reserved_compressed_bytes": a.BYTE_RESERVATIONS["tests"],
                  "usage": {"used_runner_minutes": 0, "used_compressed_bytes": 0}}
        with patch.dict(os.environ, {"GITHUB_EVENT_NAME": "workflow_dispatch", "COMMIT_MESSAGE": ""}), \
             patch.object(a, "authenticate", return_value=provenance), patch.object(a, "grant_for", return_value=authorization), \
             patch.object(a, "identity", return_value=auth_id), patch.object(a, "_frozen_receipt_identities", return_value={}):
            a.check_permit(permit, "tests")
            invalid = deepcopy(permit)
            invalid["run_attempt"] = 2
            with self.assertRaisesRegex(ValueError, "foreign"):
                a.check_permit(invalid, "tests")
            invalid = deepcopy(permit)
            invalid["resource_authorization_identity"]["sha256"] = "d" * 64
            with self.assertRaisesRegex(ValueError, "Changed"):
                a.check_permit(invalid, "tests")

    def test_api_rejects_unapproved_endpoints_before_network(self):
        for endpoint in ("https://example.test", "/user", "/actions/../secrets"):
            with self.assertRaises(ValueError):
                a.api(endpoint)

    def test_ci_repository_and_branch_are_required(self):
        with patch.dict(os.environ, {"GITHUB_ACTIONS": "true", "GITHUB_REPOSITORY": "foreign/repo", "GITHUB_REF": "refs/heads/main"}):
            with self.assertRaisesRegex(ValueError, "repository"):
                a.require_ci()


if __name__ == "__main__":
    unittest.main()
