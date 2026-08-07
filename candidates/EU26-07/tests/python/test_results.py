from __future__ import annotations

import hashlib
import json
import unittest
from pathlib import Path


CANDIDATE = Path(__file__).resolve().parents[2]
REPORT = CANDIDATE / "results" / "formal-full-replay.json"
REPORT_SHA256 = "93e49149f97e9c96c6b38d43395ed0933737f1f9549c7c176eb28aafe9c7e945"
ROWS_SHA256 = "6e5b6b6da38d0c2d846b3379150532667447a0ff38fb64aae3148149db41d176"


class FormalReplayResultTests(unittest.TestCase):
    def test_retained_report_is_the_atomic_formal_output(self):
        payload = REPORT.read_bytes()
        self.assertEqual(hashlib.sha256(payload).hexdigest(), REPORT_SHA256)
        report = json.loads(payload)
        self.assertEqual(report["claim_status"], "PASS_TARGET_ARTIFACT_REPLAY")
        self.assertEqual(
            report["paper_level_status"], "BLOCKED_PAPER_SOURCE_DIVERGENCES"
        )
        self.assertEqual(report["requested_runs"], 500)
        self.assertEqual(report["replay"]["rows_examined"], 500)
        self.assertEqual(report["replay"]["source_rows_compared"], 500)
        self.assertEqual(report["replay"]["cleanroom_rows_compared"], 500)
        self.assertIsNone(report["replay"]["first_failure"])
        for field in (
            "expected_prefix_sha256",
            "source_rows_sha256",
            "cleanroom_rows_sha256",
        ):
            self.assertEqual(report["replay"][field], ROWS_SHA256)
        self.assertEqual(report["published"]["canonical_rows_sha256"], ROWS_SHA256)
        self.assertEqual(report["post_run_authentication"]["status"], "PASS")

    def test_h0_through_h6_pass_but_h7_and_pass_full_are_not_invented(self):
        report = json.loads(REPORT.read_text(encoding="utf-8"))
        for gate in (
            "H0_source_freeze",
            "H1_eligibility",
            "H2_paper_formula",
            "H3_profile_isolation",
            "H4_published_data_integrity",
            "H5_source_native_replay",
            "H6_cleanroom_replay",
        ):
            self.assertTrue(report["gates"][gate].startswith("PASS"))
        self.assertEqual(report["gates"]["H7_cross_language"], "NOT_RUN_BY_THIS_SCRIPT")
        self.assertNotEqual(report["claim_status"], "PASS_FULL")


if __name__ == "__main__":
    unittest.main()
