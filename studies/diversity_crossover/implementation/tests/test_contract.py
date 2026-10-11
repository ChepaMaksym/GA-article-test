"""Negative authority, budget and artifact-integrity fixtures; CI only."""
import copy
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile

from .. import contract, ci_support


class ContractTests(unittest.TestCase):
    def test_ci_branch_guard(self):
        contract.ci_only()
        with patch.dict(os.environ, {"GITHUB_REF": "refs/heads/main"}):
            with self.assertRaises(ValueError):
                contract.ci_only()

    def test_file_inventory_checksum_and_extra(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            (root / "input.txt").write_text("fixture", encoding="utf-8")
            contract.write_file_manifest(root)
            contract.verify_file_manifest(root)
            (root / "extra.txt").write_text("extra", encoding="utf-8")
            with self.assertRaises(ValueError):
                contract.verify_file_manifest(root)
            (root / "extra.txt").unlink()
            (root / "input.txt").write_text("changed", encoding="utf-8")
            with self.assertRaises(ValueError):
                contract.verify_file_manifest(root)

    def test_receipt_rejects_failed_or_mixed_source(self):
        receipt = {"protocol_id": contract.PROTOCOL_ID, "tests_passed": True,
                   "tests_run": 10, "source_manifest": {"fixture": 1},
                   "tests_run_id": 1, "tests_artifact_id": 2,
                   "tests_sha": "a" * 40, "tests_zip_sha256": "b" * 64}
        with patch.object(contract, "read_json", return_value=receipt), \
             patch.object(contract, "source_manifest", return_value={"fixture": 1}), \
             patch.object(contract, "validate_artifact_receipt", return_value={}):
            contract.validate_tests_receipt()
            receipt["tests_passed"] = False
            with self.assertRaises(ValueError):
                contract.validate_tests_receipt()
            receipt["tests_passed"] = True
            receipt["source_manifest"] = {"fixture": 2}
            with self.assertRaises(ValueError):
                contract.validate_tests_receipt()

    def test_expired_or_wrong_artifact(self):
        run = {"head_sha": "a" * 40, "head_branch": contract.BRANCH,
               "status": "completed", "conclusion": "success"}
        artifact = {"expired": False, "digest": "sha256:" + "b" * 64,
                    "workflow_run": {"id": 1, "head_sha": "a" * 40}}
        with patch.object(contract, "api", side_effect=lambda path: run if "runs" in path else artifact):
            contract.validate_artifact_receipt(1, 2, "a" * 40, "b" * 64)
            artifact["expired"] = True
            with self.assertRaises(ValueError):
                contract.validate_artifact_receipt(1, 2, "a" * 40, "b" * 64)

    def test_budget_rounding_and_reservation(self):
        cutoff = "2026-10-01T00:00:00Z"
        job = {"id": 5, "name": "fixture", "conclusion": "success",
               "started_at": "2026-10-01T00:00:00Z", "completed_at": "2026-10-01T00:01:01Z"}
        previous = {"id": 1, "status": "completed", "run_attempt": 1, "created_at": cutoff,
                    "updated_at": cutoff}
        def fake_api(path):
            if path.startswith("/commits/"):
                return {"commit": {"committer": {"date": cutoff}}}
            if path.startswith("/actions/runs?"):
                return {"workflow_runs": [previous]}
            return {"jobs": [job]}
        with patch.object(contract, "authenticate"), patch.object(contract, "api", side_effect=fake_api), \
             patch.dict(os.environ, {"GITHUB_RUN_ID": "2", "GITHUB_RUN_ATTEMPT": "1"}):
            result = contract.budget_preflight("pilot")
            self.assertEqual(result["used_runner_minutes"], 2)
            job["completed_at"] = "2026-10-01T00:23:00Z"
            with self.assertRaises(ValueError):
                contract.budget_preflight("pilot")
            job["completed_at"] = None
            with self.assertRaises(ValueError):
                contract.budget_preflight("tests")

    def test_unsafe_zip_member(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            with zipfile.ZipFile(root / "bad.zip", "w") as z:
                z.writestr("../outside.txt", "fixture")
            with self.assertRaises(ValueError):
                ci_support.extract_zip(root / "bad.zip", root / "members")
