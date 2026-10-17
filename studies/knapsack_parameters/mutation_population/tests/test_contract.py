"""Fail-closed authority, data and provenance fixtures; CI only."""
from __future__ import annotations

from copy import deepcopy
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from .. import contract as c
from .. import driver


class ContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if os.environ.get("GITHUB_ACTIONS") != "true":
            raise RuntimeError("This test suite is CI-only")

    def test_registered_protocol_unchanged(self):
        record = c.authenticate(runtime=True)
        self.assertEqual(record["protocol_id"], c.PROTOCOL)
        self.assertEqual(record["registration_sha"], c.REGISTRATION_SHA)

    def test_exact_protected_hashes(self):
        registration = c.read_json(c.MODULE / "registration.json")
        for path, digest in registration["protected_sha256"].items():
            self.assertEqual(c.identity(c.ROOT / path)["sha256"], digest)

    def test_one_registered_marker(self):
        self.assertEqual(c.phase("Check implementation [mutation-population:tests]"), "tests")

    def test_unknown_duplicate_and_mixed_markers_rejected(self):
        for message in ("no marker", "[mutation-population:main]", "[other:tests]",
                        "[mutation-population:tests] [mutation-population:pilot]",
                        "[mutation-population:tests] [unknown]",
                        "[mutation-population:tests] [mutation-population:tests]"):
            with self.subTest(message=message), self.assertRaises(ValueError):
                c.phase(message)

    def test_preparation_and_pilot_are_closed(self):
        self.assertEqual(c.execution_permission("tests"), 6)
        with patch.object(c, "read_json", return_value={"approved": False}):
            for selected in ("prepare", "pilot", "main"):
                with self.subTest(phase=selected), self.assertRaises(ValueError):
                    c.execution_permission(selected)

    def test_population_gate_not_a_fixed_fallback(self):
        gate = c.read_json(c.MODULE / "population_source_gate.json")
        self.assertFalse(gate["adaptive_population_implementation_allowed"])
        self.assertFalse(gate["adaptive_population_runs_allowed"])
        self.assertFalse(gate["mutation_comparison_blocked"])

    def test_pilot_and_main_condition_identity(self):
        pilot = driver.planned_conditions("pilot")
        main = driver.planned_conditions("main")
        self.assertEqual(len(pilot), 8)
        self.assertEqual(len(main), 1320)
        self.assertEqual(len(set(main)), 1320)
        self.assertEqual(sum(start == "cloned" for _, start, _ in main), 420)
        self.assertEqual(sum(start == "bank" for _, start, _ in main), 900)
        self.assertTrue(all(85001 <= seed <= 85030 for _, _, seed in main))
        self.assertTrue(all(seed == 86001 for _, _, seed in pilot))
        with self.assertRaises(ValueError):
            driver.planned_conditions("unregistered")

    def test_all_thirty_source_bytes_and_external_cases(self):
        registry = c.read_json(c.ROOT / driver.REGISTRY)
        for task in registry["case_order"]:
            problem, case, source = driver.source_task(task)
            self.assertEqual(set(problem), {"n", "weights", "profits", "capacity"})
            self.assertEqual(problem["n"], 100)
            self.assertEqual(case["instance_id"], task)
            self.assertEqual(len(source["sha256"]), 64)

    def test_small_initial_bank_is_paired_and_separate_from_search(self):
        # A toy fixture, not a prepared KPLIB start or scientific run.
        problem = {"n": 3, "weights": [6, 5, 5], "profits": [10, 8, 8], "capacity": 10}
        case = {"certificate": {"center": {"mask": "100"}}}
        first = driver.initial_bank(problem, case, 0, "bank", 86001, 86000)
        replay = driver.initial_bank(problem, case, 0, "bank", 86001, 86000)
        self.assertEqual(first, replay)
        self.assertEqual(first["initial_masks"][0], "000")
        self.assertEqual(len(first["initial_masks"]), 30)
        self.assertEqual(first["physical_preparation_evaluations"], len(set(first["initial_masks"])))
        cloned = driver.initial_bank(problem, case, 0, "cloned", 86001, 86000)
        self.assertEqual(cloned["initial_masks"], ["100"] * 30)
        self.assertEqual(cloned["physical_preparation_evaluations"], 1)

    def test_scoring_rejects_invalid_mask_and_keeps_empty_feasible(self):
        problem = {"n": 2, "weights": [2, 2], "profits": [3, 4], "capacity": 2}
        self.assertEqual(driver.independent_score(problem, "00"),
                         {"weight": 0, "profit": 0, "feasible": True})
        self.assertFalse(driver.independent_score(problem, "11")["feasible"])
        for mask in ("0", "010", "0x", None):
            with self.assertRaises(ValueError):
                driver.independent_score(problem, mask)

    def test_manifest_roundtrip_and_corruption(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            c.write_json(root / "fixture.json", {"value": 1})
            c.write_manifest(root)
            self.assertEqual(len(c.verify_manifest(root)["files"]), 1)
            c.write_json(root / "fixture.json", {"value": 2})
            with self.assertRaises(ValueError):
                c.verify_manifest(root)

    def test_manifest_unlisted_file_and_unsafe_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            c.write_json(root / "fixture.json", {"value": 1})
            c.write_manifest(root)
            original = c.read_json(root / "file_manifest.json")
            c.write_json(root / "extra.json", {})
            with self.assertRaises(ValueError):
                c.verify_manifest(root)
            (root / "extra.json").unlink()
            for name in ("../escape", "/absolute", "C:/absolute", "a\\b", "file_manifest.json"):
                malicious = deepcopy(original)
                malicious["files"][0]["path"] = name
                c.write_json(root / "file_manifest.json", malicious)
                with self.subTest(path=name), self.assertRaises(ValueError):
                    c.verify_manifest(root)

    def test_missing_green_receipt_is_not_inherited(self):
        with patch.object(c, "read_json", return_value={"tests_passed": False}):
            with self.assertRaises(ValueError):
                c.validated_tests()

    def test_preflight_enforces_cumulative_allowance(self):
        with tempfile.TemporaryDirectory() as tmp, \
             patch.object(c, "authenticate", return_value={"protocol_id": c.PROTOCOL}), \
             patch.object(c, "runner_usage", return_value={"used_runner_minutes": 4, "prior_jobs": []}), \
             patch.dict(os.environ, {"COMMIT_MESSAGE": "[mutation-population:tests]"}):
            with self.assertRaises(ValueError):
                c.preflight(tmp)

    def test_unknown_usage_is_not_assumed_zero(self):
        with tempfile.TemporaryDirectory() as tmp, \
             patch.object(c, "authenticate", return_value={}), \
             patch.object(c, "runner_usage", side_effect=ValueError("unknown usage")), \
             patch.dict(os.environ, {"COMMIT_MESSAGE": "[mutation-population:tests]"}):
            with self.assertRaisesRegex(ValueError, "unknown usage"):
                c.preflight(tmp)

    def test_each_previous_attempt_is_counted(self):
        runs = [{"id": 1, "run_attempt": 2, "status": "completed"},
                {"id": 2, "run_attempt": 1, "status": "in_progress"}]
        def fake_pages(path, field):
            if field == "workflow_runs":
                return runs
            attempt = 1 if "/attempts/1/" in path else 2
            return [{"id": 10 + attempt, "started_at": "2026-10-17T00:00:00Z",
                     "completed_at": "2026-10-17T00:00:01Z", "conclusion": "success"}]
        with patch.dict(os.environ, {"GITHUB_RUN_ID": "2", "GITHUB_RUN_ATTEMPT": "1"}), \
             patch.object(c, "pages", side_effect=fake_pages):
            usage = c.runner_usage()
        self.assertEqual(usage["used_runner_minutes"], 2)
        self.assertEqual(len(usage["prior_jobs"]), 2)


if __name__ == "__main__":
    unittest.main()
