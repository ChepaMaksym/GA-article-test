"""CI-only tests of source, transfer and resource boundaries."""
from __future__ import annotations

import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from .. import authority as a


class AuthorityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if os.environ.get("GITHUB_ACTIONS") != "true":
            raise RuntimeError("CI-only checks")

    def test_frozen_contract_and_runtime(self):
        receipt = a.authenticate(runtime=True)
        self.assertEqual(receipt["registration_sha"], a.REGISTRATION_SHA)
        self.assertEqual(receipt["transfer_registration_sha"], a.TRANSFER_SHA)

    def test_transfer_approval_is_not_a_search_budget(self):
        old = a.read_json(a.MODULE / "registration.json")
        new = a.read_json(a.MODULE / "transfer_registration.json")
        self.assertFalse(old["knapsack_objective_transfer_authorized"])
        self.assertTrue(new["authorization"]["auxiliary_profit_weight_archive"])
        self.assertFalse(new["authorization"]["scientific_search_resource_approval"])
        self.assertFalse(new["scientific_search_authorized"])
        self.assertFalse(new["scientific_pilot_authorized"])

    def test_only_registered_test_marker(self):
        self.assertEqual(a.phase("Check [bntga-selection:tests]"), "tests")
        for value in ("none", "[bntga-selection:pilot]", "[bntga-selection:main]",
                      "[bntga-selection:tests] [other]", "[bntga-selection:tests] [bntga-selection:tests]"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                a.phase(value)

    def test_allowance_is_shared_not_reissued(self):
        self.assertEqual(len(a.WORKFLOWS), 3)
        self.assertIn("knapsack-mutation-rules.yml", a.WORKFLOWS)
        self.assertEqual(a.ALLOWANCE, 6)
        for used in (0, 2, 3):
            a.check_allowance({"used_runner_minutes": used})
        for used in (4, None, True, -1):
            with self.subTest(used=used), self.assertRaises(ValueError):
                a.check_allowance({"used_runner_minutes": used})

    def test_all_attempts_failures_and_rounding_count(self):
        def fake_pages(path, field):
            if field == "workflow_runs":
                return [{"id": 10, "status": "completed", "run_attempt": 2}] if "population.yml" in path else []
            attempt = 1 if "/attempts/1/" in path else 2
            return [{"id": attempt, "conclusion": "failure", "started_at": "2026-10-17T00:00:00Z",
                     "completed_at": "2026-10-17T00:00:01Z"},
                    {"id": 50 + attempt, "conclusion": "skipped"}]
        with patch.object(a, "pages", side_effect=fake_pages):
            result = a.runner_usage()
        self.assertEqual(result["used_runner_minutes"], 2)
        self.assertEqual(len(result["prior_jobs"]), 2)

    def test_unknown_duration_or_concurrent_usage_blocks(self):
        for status, job in (("in_progress", {}), ("completed", {"id": 1, "conclusion": "failure"})):
            def fake_pages(path, field):
                if field == "workflow_runs":
                    return [{"id": 10, "status": status, "run_attempt": 1}] if "population.yml" in path else []
                return [job]
            with self.subTest(status=status), patch.object(a, "pages", side_effect=fake_pages), self.assertRaises(ValueError):
                a.runner_usage()

    def test_artifact_guard(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            a.write_json(root / "sample.json", {"teaching": True})
            a.write_manifest(root)
            a.verify_manifest(root)
            a.write_json(root / "extra.json", {})
            with self.assertRaises(ValueError):
                a.verify_manifest(root)
            (root / "extra.json").unlink()
            a.write_json(root / "sample.json", {"teaching": False})
            with self.assertRaises(ValueError):
                a.verify_manifest(root)

    def test_source_scope_is_not_full_article_replication(self):
        gate = a.read_json(a.MODULE / "source_gate.json")
        self.assertFalse(gate["redistribute_author_code"])
        self.assertFalse(gate["numerical_article_replication"])
        self.assertFalse(gate["knapsack_search_admitted"])
        self.assertEqual(gate["author_commit"], "5a72aeae88c82772482e9df586a6fa428b33f301")
