import copy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from studies.knapsack_parameters.adaptation_analysis import authority as a


def grant():
    return {"protocol_id": a.PROTOCOL, "explicit_user_approval": True, "allowed_phases": ["tests"],
            "additional_runner_minutes": 6, "shared_ceiling_minutes": 12,
            "job_reservation_minutes": 3, "scientific_search_authorized": False,
            "lambda_search_authorized": False}


class AuthorityTests(unittest.TestCase):
    def test_only_tests_marker(self):
        self.assertEqual(a.phase("Checks [adaptation-analysis:tests]"), "tests")
        for message in ("", "[adaptation-analysis:pilot]", "[adaptation-analysis:main]",
                        "[adaptation-analysis:tests][anything]", "[adaptation-analysis:tests]\n[tests]"):
            with self.assertRaises(ValueError):
                a.phase(message)

    def test_missing_grant_is_not_implementation_authorization(self):
        with patch.object(Path, "is_file", return_value=False):
            with self.assertRaisesRegex(ValueError, "BLOCKED_RESOURCE_APPROVAL"):
                a.resource_grant()

    def test_only_explicit_tests_only_grant(self):
        with patch.object(Path, "is_file", return_value=True), patch.object(a, "read_json", return_value=grant()):
            self.assertEqual(a.resource_grant(), grant())
        for name, value in (("explicit_user_approval", False), ("allowed_phases", ["tests", "pilot"]),
                            ("additional_runner_minutes", 60), ("lambda_search_authorized", True),
                            ("scientific_search_authorized", True), ("additional_runner_minutes", 6.0),
                            ("job_reservation_minutes", 3.0)):
            altered = {**grant(), name: value}
            with patch.object(Path, "is_file", return_value=True), patch.object(a, "read_json", return_value=altered):
                with self.assertRaises(ValueError):
                    a.resource_grant()

    def test_allowance_includes_reservation(self):
        a.check_allowance({"used_runner_minutes": 9}, grant())
        for used in (10, -1, True, None):
            with self.assertRaises(ValueError):
                a.check_allowance({"used_runner_minutes": used}, grant())

    def test_all_attempts_and_allocated_failures_count(self):
        run = {"id": 41, "status": "completed", "run_attempt": 2}
        jobs = {1: [{"id": 51, "conclusion": "failure", "started_at": "2026-10-18T00:00:00Z",
                     "completed_at": "2026-10-18T00:01:05Z"}],
                2: [{"id": 52, "conclusion": "success", "started_at": "2026-10-18T00:02:00Z",
                     "completed_at": "2026-10-18T00:02:05Z"}, {"id": 53, "conclusion": "skipped"}]}

        def pages(path, key):
            if key == "workflow_runs":
                return [run] if "knapsack-mutation-population.yml" in path else []
            return jobs[1 if "/attempts/1/" in path else 2]

        with patch.dict("os.environ", {"GITHUB_RUN_ID": "99", "GITHUB_RUN_ATTEMPT": "1"}), \
                patch.object(a, "pages", side_effect=pages):
            usage = a.runner_usage()
        self.assertEqual(usage["used_runner_minutes"], 3)
        self.assertEqual(len(usage["prior_jobs"]), 2)

    def test_unknown_or_concurrent_cost_blocks(self):
        for run in ({"id": 41, "status": "in_progress", "run_attempt": 1},
                    {"id": 41, "status": "completed", "run_attempt": 1}):
            def pages(path, key):
                if key == "workflow_runs":
                    return [run] if "knapsack-mutation-population.yml" in path else []
                return [{"id": 51, "conclusion": "failure", "started_at": None, "completed_at": None}]
            with patch.dict("os.environ", {"GITHUB_RUN_ID": "99", "GITHUB_RUN_ATTEMPT": "1"}), \
                    patch.object(a, "pages", side_effect=pages):
                with self.assertRaises(ValueError):
                    a.runner_usage()

    def test_frozen_sources_and_runtime(self):
        result = a.authenticate(runtime=True)
        self.assertEqual(result["registration_sha"], a.REGISTRATION_SHA)
        self.assertEqual(result["environment"]["python"], "3.12.14")
        self.assertEqual(len(result["source_manifest"]["sha256"]), 64)

    def test_artifact_integrity_and_unsafe_paths(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            a.write_json(root / "proof.json", {"scope": "software fixture only"})
            a.write_manifest(root)
            self.assertEqual(a.verify_manifest(root)["protocol_id"], a.PROTOCOL)
            original = a.read_json(root / "file_manifest.json")
            (root / "proof.json").write_bytes(b"corrupt")
            with self.assertRaises(ValueError):
                a.verify_manifest(root)
            altered = copy.deepcopy(original)
            altered["files"][0]["path"] = "../outside.json"
            a.write_json(root / "file_manifest.json", altered)
            with self.assertRaises(ValueError):
                a.verify_manifest(root)

    def test_lambda_and_scientific_execution_are_not_granted(self):
        registration = a.read_json(a.MODULE / "registration.json")
        self.assertEqual(registration["authorization"]["new_runner_minutes"], 0)
        self.assertTrue(all(registration["authorization"][name] is False
                            for name in ("pilot", "main", "lambda_search", "scientific_figures")))
        self.assertNotEqual(registration["lambda_replication_status"], "PASS_FULL")
