import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch

from .. import contract as c


class MainAuthorityTests(unittest.TestCase):
    def usage(self, minutes=0, payload=0, zipped=0, workers=0):
        return {"used_runner_minutes": minutes, "previous_payload_upper_bound_bytes": payload,
                "previous_artifact_zip_bytes": zipped, "previous_main_workers": workers}

    def test_only_exact_single_new_phase_markers(self):
        for name in ("tests", "main"):
            self.assertEqual(c.phase(f"[knapsack-stagnation-main:{name}]"), name)
        for value in ("", "[knapsack-stagnation:probe]", "[knapsack-stagnation-main:prepare]",
                      "[knapsack-stagnation-main:main] [knapsack-stagnation-main:tests]",
                      "[knapsack-stagnation-main:main] [skip ci]"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                c.phase(value)

    def test_independent_ceiling_and_all_reservations(self):
        self.assertEqual(c.RESERVATIONS, {"tests": 12, "main": 160})
        c.check_allowance(self.usage(minutes=40), "main")
        c.check_allowance(self.usage(minutes=188), "tests")
        for usage in (self.usage(minutes=41), self.usage(minutes=-1), self.usage(minutes=True),
                      self.usage(workers=1), self.usage(payload=c.BYTE_CEILING), {}):
            with self.subTest(usage=usage), self.assertRaises(ValueError):
                c.check_allowance(usage, "main")

    def test_uncompressed_payload_is_not_mistaken_for_small_zip(self):
        with self.assertRaises(ValueError):
            c.check_allowance(self.usage(payload=c.BYTE_CEILING - c.MAIN_PAYLOAD_RESERVATION + 1, zipped=1), "main")
        c.check_allowance(self.usage(payload=c.BYTE_CEILING - c.MAIN_PAYLOAD_RESERVATION, zipped=1), "main")

    def test_cumulative_attempts_and_expired_storage_still_count(self):
        old = {"id": 10, "status": "completed", "run_attempt": 2}
        current = {"id": 20, "status": "in_progress", "run_attempt": 1}
        def pages(path, key):
            if key == "workflow_runs":
                return [old, current]
            if key == "artifacts":
                if "/10/" in path:
                    return [{"id": 1000, "name": "knapsack-stagnation-main-tests-10-1", "size_in_bytes": 1, "expired": True}]
                return []
            if "/20/" in path:
                return [{"id": 200, "name": "gate", "status": "in_progress"}]
            attempt = 1 if "/attempts/1/" in path else 2
            return [{"id": 100 + attempt, "name": "tests", "status": "completed", "conclusion": "failure",
                     "started_at": "2026-10-20T12:00:00Z", "completed_at": "2026-10-20T12:01:01Z"}]
        with patch.dict("os.environ", {"GITHUB_RUN_ID": "20", "GITHUB_RUN_ATTEMPT": "1"}), patch.object(c, "pages", side_effect=pages):
            result = c.resource_usage()
        self.assertEqual(result["used_runner_minutes"], 4)
        self.assertEqual(result["previous_artifact_zip_bytes"], 1)
        self.assertEqual(result["previous_payload_upper_bound_bytes"], c.TESTS_CAP)

    def test_local_authorization_rejected_and_historical_source_still_frozen(self):
        with patch.dict("os.environ", {}, clear=True), self.assertRaises(ValueError):
            c.authenticate()
        self.assertEqual(c.old.fingerprint(), c.TECHNICAL_FINGERPRINT)
        self.assertEqual(c.identity(c.old.MODULE / "evidence/prepare-run-39418724226-1/bank_registry.json")["sha256"], c.BANK_SHA)

    def test_registered_payload_caps_fit_one_full_matrix(self):
        self.assertLess(c.MAIN_PAYLOAD_RESERVATION + c.TESTS_CAP + 1024 ** 2, c.BYTE_CEILING)
        protocol = c.read_json(c.MODULE / "protocol.json")
        self.assertEqual(protocol["authorization"]["worker_evidence_payload_bytes_ceiling"], c.WORKER_CAP)
        self.assertEqual(protocol["scientific_design"]["runs"], 900)

    def test_mixed_sha_or_grant_permit_rejected(self):
        provenance = {name: "fixture-" + name for name in c.PROVENANCE_KEYS}
        permit = {**provenance, **self.usage(), "phase": "tests", "reserved_runner_minutes": 12,
                  "runner_minutes_ceiling": 200, "evidence_payload_bytes_ceiling": c.BYTE_CEILING,
                  "main_search_authorized": False}
        with tempfile.TemporaryDirectory() as temporary, patch.object(c, "authenticate", return_value=provenance), \
                patch.dict("os.environ", {"COMMIT_MESSAGE": "[knapsack-stagnation-main:tests]"}):
            directory = Path(temporary)
            c.write_json(directory / "permit.json", permit)
            c.write_manifest(directory)
            self.assertEqual(c.check_permit(directory, "tests"), provenance)
            for key, wrong in (("implementation_commit_sha", "other"), ("runner_minutes_ceiling", 201),
                               ("evidence_payload_bytes_ceiling", 9 * 1024 ** 3), ("main_search_authorized", True)):
                c.write_json(directory / "permit.json", {**permit, key: wrong})
                c.write_manifest(directory)
                with self.subTest(key=key), self.assertRaises(ValueError):
                    c.check_permit(directory, "tests")


if __name__ == "__main__":
    unittest.main()
