"""CI-only fixtures for bounded authority, exact evidence, and transport failures."""
from __future__ import annotations

import hashlib
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile

from studies.knapsack_parameters.stagnation_diagnosis import contract as c
from studies.knapsack_parameters.stagnation_diagnosis.execution import regression_suite


class ExecutionAuthorityTests(unittest.TestCase):
    def test_registered_phase_exact_and_unique(self):
        for phase in c.RESERVATIONS:
            self.assertEqual(c.phase("Registered [knapsack-stagnation:" + phase + "]"), phase)
        for message in ("", "[knapsack-stagnation:main]", "[knapsack-stagnation:unknown]",
                        "[knapsack-stagnation:probe] [knapsack-stagnation:tests]",
                        "[knapsack-stagnation:probe] [knapsack-final:probe]",
                        "[knapsack-stagnation:probe] [knapsack-stagnation:probe]"):
            with self.subTest(message=message), self.assertRaises(ValueError):
                c.phase(message)

    def test_cumulative_ceiling_does_not_inherit_other_grants(self):
        self.assertEqual(c.RESERVATIONS, {"tests": 12, "prepare": 9, "probe": 31})
        c.check_allowance({"used_runner_minutes": 29}, "probe")
        for usage in ({"used_runner_minutes": 30}, {}, {"used_runner_minutes": None},
                      {"used_runner_minutes": -1}, {"used_runner_minutes": True}):
            with self.subTest(usage=usage), self.assertRaises(ValueError):
                c.check_allowance(usage, "probe")
        with self.assertRaises(ValueError):
            c.check_allowance({"used_runner_minutes": 0}, "main")

    def test_each_job_rounds_up_and_unknown_duration_blocks(self):
        base = {"status": "completed", "conclusion": "success", "started_at": "2026-10-20T12:00:00Z"}
        for ending, expected in (("12:00:01", 1), ("12:01:00", 1), ("12:01:01", 2)):
            self.assertEqual(c.job_minutes({**base, "completed_at": "2026-10-20T" + ending + "Z"}), expected)
        for job in (base, {**base, "status": "in_progress"},
                    {**base, "completed_at": "2026-10-20T11:59:59Z"}):
            with self.assertRaises(ValueError):
                c.job_minutes(job)

    def test_prior_attempts_count_and_current_gate_is_inside_reservation(self):
        old = {"id": 10, "status": "completed", "run_attempt": 2}
        current = {"id": 20, "status": "in_progress", "run_attempt": 1}
        def jobs(path, key):
            if key == "workflow_runs":
                return [old, current]
            if "/20/" in path:
                return [{"id": 200, "name": "gate", "status": "in_progress"}]
            attempt = 1 if "/attempts/1/" in path else 2
            return [{"id": 100 + attempt, "status": "completed", "conclusion": "failure",
                     "started_at": "2026-10-20T12:00:00Z", "completed_at": "2026-10-20T12:01:01Z"}]
        with patch.dict("os.environ", {"GITHUB_RUN_ID": "20", "GITHUB_RUN_ATTEMPT": "1"}), \
                patch.object(c, "pages", side_effect=jobs):
            usage = c.runner_usage()
        self.assertEqual(usage["used_runner_minutes"], 4)
        self.assertEqual(len(usage["jobs"]), 2)

    def test_local_or_foreign_execution_rejected(self):
        with patch.dict("os.environ", {}, clear=True), self.assertRaisesRegex(ValueError, "CI repository"):
            c.authenticate()
        with patch.dict("os.environ", {"GITHUB_ACTIONS": "true", "GITHUB_REPOSITORY": c.REPOSITORY,
                                       "GITHUB_REF": "refs/heads/main"}, clear=True), self.assertRaises(ValueError):
            c.authenticate()

    def test_safe_paths_and_full_inventory(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            c.write_json(root / "one.json", {"a": 1})
            c.write_manifest(root)
            c.verify_manifest(root)
            for name in ("", "..", ".", "../outside", "/absolute", "C:stream", "a\\b"):
                with self.subTest(name=name), self.assertRaises(ValueError):
                    c.safe_path(root, name)
            c.write_json(root / "unexpected.json", {})
            with self.assertRaises(ValueError):
                c.verify_manifest(root)

    def test_regression_selection_is_explicit_and_not_silent_skip(self):
        _, selected = regression_suite()
        self.assertEqual(selected["discovered"] - selected["selected"], 1)
        self.assertEqual(len(selected["excluded"]), 1)
        self.assertTrue(any("test_engine" in name for name in selected["selected_ids"]))
        self.assertTrue(any("test_solvers" in name for name in selected["selected_ids"]))

    def test_zip_checksum_and_traversal_fail_closed(self):
        for unsafe in ("../outside.json", "C:outside.json", "a\\outside.json"):
            data = io.BytesIO()
            with zipfile.ZipFile(data, "w") as archive:
                archive.writestr(unsafe, b"fixture")
            raw = data.getvalue()
            metadata = {"id": 1, "expired": False, "size_in_bytes": len(raw),
                        "digest": "sha256:" + hashlib.sha256(raw).hexdigest()}
            with tempfile.TemporaryDirectory() as temporary, \
                    patch.dict("os.environ", {"GITHUB_TOKEN": "FICTITIOUS_FIXTURE_TOKEN"}), \
                    patch("urllib.request.build_opener") as opener:
                opener.return_value.open.return_value = io.BytesIO(raw)
                with self.assertRaises(ValueError):
                    c._download_zip(metadata, Path(temporary) / "destination")
                self.assertFalse((Path(temporary) / "outside.json").exists())

    def test_expired_artifact_and_wrong_digest_are_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            for metadata in ({"expired": True}, {"id": 1, "expired": False, "size_in_bytes": 1,
                                                  "digest": "sha256:not-a-valid-checksum"}):
                with self.assertRaises(ValueError):
                    c._download_zip(metadata, Path(temporary) / "destination")


if __name__ == "__main__":
    unittest.main()
