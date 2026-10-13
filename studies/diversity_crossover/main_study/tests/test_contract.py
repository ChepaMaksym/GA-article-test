from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from .. import contract


class MainContractTests(unittest.TestCase):
    def test_registered_counts_and_cap(self):
        self.assertEqual(contract.AUTHORITY["counts"]["total_runs"], 6304)
        self.assertEqual(contract.AUTHORITY["resources"]["approved_runner_minutes"], 1200)
        self.assertFalse(contract.AUTHORITY["authorization"]["merge"])
        self.assertFalse(contract.AUTHORITY["adaptive_controller_scope"]["own_rule_authorized"])

    def test_markers(self):
        self.assertEqual(contract.parse_phase("a [diversity-main:tests]"), "tests")
        for text in ("none", "[diversity-main:oops]", "[diversity-main:main] [diversity-main:tests]",
                     "[diversity-main:main] [diversity:pilot]"):
            with self.assertRaises(ValueError):
                contract.parse_phase(text)

    def test_manifest_rejects_missing_or_corrupt(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "a.json"
            p.write_bytes(b"{}")
            contract.write_file_manifest(d)
            self.assertEqual(len(contract.verify_file_manifest(d)["files"]), 1)
            p.write_bytes(b"[]")
            with self.assertRaises(ValueError):
                contract.verify_file_manifest(d)

    def test_manifest_rejects_extra(self):
        with tempfile.TemporaryDirectory() as d:
            contract.write_file_manifest(d)
            (Path(d) / "extra").write_bytes(b"x")
            with self.assertRaises(ValueError):
                contract.verify_file_manifest(d)

    def test_manifest_rejects_unsafe_member(self):
        with tempfile.TemporaryDirectory() as d:
            contract.write_json(Path(d) / "file_manifest.json", {"schema_version": 1,
                "protocol_id": contract.PROTOCOL_ID, "excludes_self": True,
                "files": [{"path": "../outside", "sha256": "0"*64, "bytes": 0}]})
            with self.assertRaises(ValueError):
                contract.verify_file_manifest(d)

    def test_canonical_nan_forbidden(self):
        with self.assertRaises(ValueError):
            contract.canonical_bytes({"x": float("nan")})

    def test_retry_source_budget_reserves_active_matrix_and_services(self):
        usage = {"used_runner_minutes": 1000, "unfinished_current_jobs": [
            {"name": "main (Flat-b0)"}, {"name": "main (global-b0)"}]}
        with patch.object(contract, "ci_only"), patch.object(contract, "runner_usage", return_value=usage):
            result = contract.job_budget_preflight("Flat-b0")
            self.assertEqual(result["reserved_runner_minutes"], 38)
            usage["used_runner_minutes"] = 1190
            with self.assertRaises(ValueError):
                contract.job_budget_preflight("Flat-b0")

    def test_retry_service_budget_fails_before_computation(self):
        usage = {"used_runner_minutes": 1180, "unfinished_current_jobs": [{"name": "aggregate"}]}
        with patch.object(contract, "ci_only"), patch.object(contract, "runner_usage", return_value=usage):
            self.assertEqual(contract.nonsearch_budget_preflight("aggregate")["reserved_runner_minutes"], 20)
            usage["used_runner_minutes"] = 1181
            with self.assertRaises(ValueError):
                contract.nonsearch_budget_preflight("aggregate")


if __name__ == "__main__":
    contract.ci_only()
    unittest.main()
