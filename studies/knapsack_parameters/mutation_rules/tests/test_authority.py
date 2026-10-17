"""CI-only bounded authority and transport fixtures."""
from __future__ import annotations

import copy
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
            raise RuntimeError("CI-only test suite")

    def test_frozen_registration_and_environment(self):
        receipt = a.authenticate(runtime=True)
        self.assertEqual(receipt["registration_sha"], a.REGISTRATION_SHA)
        self.assertFalse(a.read_json(a.MODULE / "registration.json")["scientific_execution_authorized"])

    def test_exact_marker_only(self):
        self.assertEqual(a.phase("Run fixtures [mutation-rules:tests]"), "tests")
        for message in ("none", "[mutation-rules:pilot]", "[mutation-rules:main]",
                        "[mutation-rules:tests] [another]", "[mutation-rules:tests] [mutation-rules:tests]"):
            with self.subTest(message=message), self.assertRaises(ValueError):
                a.phase(message)

    def test_six_minutes_are_shared_not_reissued(self):
        self.assertEqual(set(a.SHARED_WORKFLOWS),
                         {"knapsack-mutation-population.yml", "knapsack-mutation-rules.yml"})
        for used in (0, 1, 2, 3):
            a.check_allowance({"used_runner_minutes": used})
        for used in (4, 6, -1, None, True):
            with self.subTest(used=used), self.assertRaises(ValueError):
                a.check_allowance({"used_runner_minutes": used})

    def test_every_prior_attempt_and_job_is_counted(self):
        runs = {
            "knapsack-mutation-population.yml": [{"id": 10, "status": "completed", "run_attempt": 2}],
            "knapsack-mutation-rules.yml": [{"id": 20, "status": "in_progress", "run_attempt": 1}],
        }
        def fake_pages(path, field):
            if field == "workflow_runs":
                return next(value for key, value in runs.items() if key in path)
            attempt = 1 if "/attempts/1/" in path else 2
            return [{"id": attempt, "conclusion": "failure", "started_at": "2026-10-17T00:00:00Z",
                     "completed_at": "2026-10-17T00:01:01Z"},
                    {"id": 100 + attempt, "conclusion": "skipped"}]
        with patch.dict(os.environ, {"GITHUB_RUN_ID": "20", "GITHUB_RUN_ATTEMPT": "1"}), \
                patch.object(a, "pages", side_effect=fake_pages):
            self.assertEqual(a.runner_usage()["used_runner_minutes"], 4)
        runs["knapsack-mutation-population.yml"][0]["status"] = "in_progress"
        with patch.dict(os.environ, {"GITHUB_RUN_ID": "20", "GITHUB_RUN_ATTEMPT": "1"}), \
                patch.object(a, "pages", side_effect=fake_pages), self.assertRaises(ValueError):
            a.runner_usage()

    def test_unknown_job_duration_blocks_allowance(self):
        def fake_pages(path, field):
            if field == "workflow_runs":
                return [{"id": 10, "status": "completed", "run_attempt": 1}] if "population.yml" in path else []
            return [{"id": 1, "conclusion": "failure", "started_at": None, "completed_at": None}]
        with patch.object(a, "pages", side_effect=fake_pages), self.assertRaises(ValueError):
            a.runner_usage()

    def test_transport_checks_missing_corrupt_unlisted_and_duplicate_members(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            a.write_json(root / "a.json", {"ok": True})
            a.write_manifest(root)
            manifest = a.verify_manifest(root)
            a.write_json(root / "extra.json", {})
            with self.assertRaises(ValueError):
                a.verify_manifest(root)
            (root / "extra.json").unlink()
            broken = copy.deepcopy(manifest)
            broken["files"].append(copy.deepcopy(broken["files"][0]))
            a.write_json(root / "file_manifest.json", broken)
            with self.assertRaises(ValueError):
                a.verify_manifest(root)
            a.write_json(root / "file_manifest.json", manifest)
            a.write_json(root / "a.json", {"ok": False})
            with self.assertRaises(ValueError):
                a.verify_manifest(root)

    def test_old_authorization_is_not_called_or_weakened(self):
        source = (a.MODULE / "authority.py").read_text(encoding="utf-8")
        self.assertNotIn("mutation_population.contract", source)
        gate = a.read_json(a.MODULE / "source_gate.json")
        self.assertEqual(gate["admitted_new_published_controllers"], 1)
        self.assertTrue(gate["own_heuristic_is_not_a_paper_controller"])
        self.assertEqual(gate["sources"][1]["authors"], "Alexander Woodcock; Li Zhang")
