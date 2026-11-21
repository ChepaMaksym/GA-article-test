"""CI-only resource-ledger boundaries; no search or external network."""
from copy import deepcopy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import os

from .common import guard_main
from . import evidence


class ResourceEvidenceChecks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.protocol, cls.authorization = guard_main()

    def test_rounding_is_per_job_and_skipped_jobs_cost_zero(self):
        jobs = [{"id": 1, "status": "completed", "conclusion": "success",
                 "started_at": "2026-11-18T08:00:00Z", "completed_at": "2026-11-18T08:00:01Z"},
                {"id": 2, "status": "completed", "conclusion": "failure",
                 "started_at": "2026-11-18T08:00:01Z", "completed_at": "2026-11-18T08:01:02Z"},
                {"id": 3, "status": "completed", "conclusion": "skipped",
                 "started_at": None, "completed_at": None}]
        self.assertEqual(evidence.rounded_job_minutes(jobs, require_completed=True), 3)
        with self.assertRaises(ValueError):
            evidence.rounded_job_minutes(jobs + [jobs[0]], require_completed=True)

    def test_live_prior_jobs_and_negative_elapsed_time_are_rejected(self):
        job = {"id": 1, "status": "in_progress", "started_at": "2026-11-18T08:00:00Z",
               "completed_at": None}
        with self.assertRaises(ValueError):
            evidence.rounded_job_minutes([job], require_completed=True)
        self.assertEqual(evidence.rounded_job_minutes([job], require_completed=False), 0)
        job.update(status="completed", completed_at="2026-11-18T07:59:59Z")
        with self.assertRaises(ValueError):
            evidence.rounded_job_minutes([job], require_completed=True)

    def test_upload_cap_counts_nested_payload_bytes(self):
        protocol = deepcopy(self.protocol)
        protocol["limits"]["index_artifact_bytes"] = 7
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "case").mkdir()
            (root / "case" / "record.json").write_bytes(b"12345678")
            with patch.object(evidence, "guard_main", return_value=(protocol, self.authorization)):
                with self.assertRaises(ValueError):
                    evidence.check_upload("index", root, "synthetic-grant")
            self.assertEqual(evidence.directory_bytes(root), 8)

    def test_artifact_symlink_cannot_escape_its_evidence_root(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "inside"
            root.mkdir()
            outside = Path(directory) / "outside.bin"
            outside.write_bytes(b"retained")
            (root / "alias.bin").symlink_to(outside)
            with self.assertRaises(ValueError):
                evidence.directory_bytes(root)

    def test_plan_accounts_for_previously_uploaded_artifacts(self):
        authorization = deepcopy(self.authorization)
        planned = {"workflow_run_id": os.environ["GITHUB_RUN_ID"],
                   "source_manifest_sha256": authorization["source_manifest_sha256"],
                   "active_shards": [{"shard_id": f"{i:03d}"} for i in range(30)]}
        admission = {"workflow_run_id": os.environ["GITHUB_RUN_ID"],
                     "remaining_runner_minutes": 150,
                     "uploaded_artifact_bytes": authorization["artifact_bytes"] - 1}
        with patch.object(evidence, "guard_main", return_value=(self.protocol, authorization)), \
                patch.object(evidence, "read_json", side_effect=[planned, admission]):
            with self.assertRaises(ValueError):
                evidence.plan_budget("plan", "receipt", "synthetic-grant")

    def test_remaining_allowance_must_match_the_prior_run_ledger(self):
        authorization = deepcopy(self.authorization)
        authorization.update(runner_minutes=150, remaining_runner_minutes=140)
        with tempfile.TemporaryDirectory() as directory, \
                patch.object(evidence, "guard_main", return_value=(self.protocol, authorization)), \
                patch.object(evidence, "resource_state", return_value={"rounded_completed_job_minutes": 11,
                            "uploaded_artifact_bytes": 0, "runs": []}):
            output = Path(directory) / "must-not-exist.json"
            with self.assertRaises(ValueError):
                evidence.admit(output, "synthetic-grant")
            self.assertFalse(output.exists())

    def test_unapproved_stage_is_rejected_before_resource_network_io(self):
        with patch.object(evidence, "guard_main", side_effect=ValueError("not approved")), \
                patch.object(evidence, "resource_state") as request:
            with self.assertRaises(ValueError):
                evidence.admit("unused", "unapproved-grant")
            request.assert_not_called()


if __name__ == "__main__":
    unittest.main()
