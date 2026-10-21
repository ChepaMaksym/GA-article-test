import ast
import copy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from .. import contract as c


class SecondaryAuthorityTests(unittest.TestCase):
    def usage(self, minutes=0, payload=0, zipped=0, workers=0):
        return {"used_runner_minutes": minutes, "previous_payload_upper_bound_bytes": payload,
                "previous_artifact_zip_bytes": zipped, "previous_workers": workers}

    def test_single_exact_phase_without_search_markers(self):
        for phase in ("tests", "analyze"):
            self.assertEqual(c.phase(f"[knapsack-stagnation-mechanisms:{phase}]"), phase)
        for marker in ("", "[knapsack-stagnation-main:main]", "[knapsack-stagnation-mechanisms:search]",
                       "[knapsack-stagnation-mechanisms:analyze] [skip ci]",
                       "[knapsack-stagnation-mechanisms:tests] [knapsack-stagnation-mechanisms:analyze]"):
            with self.subTest(marker=marker), self.assertRaises(ValueError):
                c.phase(marker)

    def test_separate_grant_cannot_be_inherited_or_expand_search(self):
        grant = {"protocol_id": c.PROTOCOL_ID, "authorized": True, "runner_minutes_ceiling": 90,
                 "output_payload_bytes_ceiling": 1024 ** 3, "user_answer": "Explicit new approval",
                 "new_search_authorized": False}
        c.validate_grant(grant)
        for key, value in (("protocol_id", c.source.PROTOCOL_ID), ("authorized", False),
                           ("runner_minutes_ceiling", 200), ("output_payload_bytes_ceiling", 8 * 1024 ** 3),
                           ("user_answer", ""), ("new_search_authorized", True)):
            bad = {**grant, key: value}
            with self.subTest(key=key), self.assertRaises(ValueError):
                c.validate_grant(bad)

    def test_unknown_or_insufficient_resources_block(self):
        c.check_allowance(self.usage(minutes=20), "analyze")
        c.check_allowance(self.usage(minutes=78), "tests")
        for usage in ({}, self.usage(minutes=21), self.usage(minutes=True), self.usage(minutes=-1),
                      self.usage(workers=1), self.usage(payload=c.BYTE_CEILING),
                      self.usage(zipped=c.BYTE_CEILING + 1)):
            with self.subTest(usage=usage), self.assertRaises(ValueError):
                c.check_allowance(usage, "analyze")

    def test_cumulative_payload_not_zip_compression_controls_storage(self):
        reserve = c.CAPS["permit"] + 10 * c.CAPS["worker"] + c.CAPS["summary"]
        c.check_allowance(self.usage(payload=c.BYTE_CEILING - reserve, zipped=1), "analyze")
        with self.assertRaises(ValueError):
            c.check_allowance(self.usage(payload=c.BYTE_CEILING - reserve + 1, zipped=1), "analyze")

    def test_original_summary_and_fingerprints_are_frozen(self):
        summary = c.source_summary()
        self.assertEqual(summary["provenance"]["run_id"], 39465647096)
        self.assertEqual(len(summary["transport_ledger"]["artifacts"]), 30)
        with patch.object(c.source, "fingerprint", return_value="0" * 64), self.assertRaises(ValueError):
            c.source_summary()

    def test_unregistered_or_modified_source_zip_blocks_before_download(self):
        ledger = c.source_summary()["transport_ledger"]["artifacts"][0]
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(c.old, "_download_zip") as download:
                with self.assertRaises(ValueError):
                    c.download_source({**ledger, "zip_sha256": "0" * 64}, directory)
                download.assert_not_called()
                metadata = {"workflow_run": {"id": 39465647096,
                            "head_sha": "7fbb0e56fc07a357b201874e339646d197dd5834"},
                            "name": ledger["name"], "digest": "sha256:" + "0" * 64,
                            "size_in_bytes": ledger["zip_bytes"]}
                with patch.object(c, "api", return_value=metadata), self.assertRaises(ValueError):
                    c.download_source(ledger, directory)
                download.assert_not_called()

    def test_no_new_search_or_exact_solver_call_in_production_module(self):
        forbidden = {"run_search", "execute_case", "execute_batch", "solve_exact", "solve_dp", "generate_bank"}
        for source in c.MODULE.glob("*.py"):
            tree = ast.parse(source.read_text(encoding="utf-8"))
            called = {node.func.id if isinstance(node.func, ast.Name) else node.func.attr
                      for node in ast.walk(tree) if isinstance(node, ast.Call)
                      and isinstance(node.func, (ast.Name, ast.Attribute))}
            self.assertFalse(called & forbidden, f"Unauthorized new search in {source.name}")

    def test_scientific_pre_registration_precedes_implementation_and_remains_exploratory(self):
        protocol = c.read_json(c.MODULE / "protocol.json")
        self.assertEqual(protocol["protocol_id"], c.PROTOCOL_ID)
        self.assertEqual(protocol["source"]["runs"], 900)
        self.assertEqual(protocol["analysis"]["spearman"]["constant"], "UNDEFINED")
        self.assertFalse(protocol["analysis"]["bootstrap"])
        self.assertIn("exploratory", protocol["scope"])

    def test_unsafe_output_paths_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            for value in ("../escape", "/absolute", "a\\b", "C:/escape", ""):
                with self.subTest(value=value), self.assertRaises(ValueError):
                    c.safe_path(directory, value)


if __name__ == "__main__":
    unittest.main()
