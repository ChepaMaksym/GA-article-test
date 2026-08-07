from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path


CANDIDATE = Path(__file__).resolve().parents[2]
COMPARATOR_PATH = CANDIDATE / "tests" / "hardware" / "compare_portability_reports.py"
SPEC = importlib.util.spec_from_file_location("eu2602_hardware_comparator", COMPARATOR_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("cannot load EU26-02 hardware comparator")
COMPARATOR = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(COMPARATOR)


class HardwareComparatorFailClosedTests(unittest.TestCase):
    def test_empty_self_asserted_profile_cannot_pass(self):
        forged = {
            "protocol_id": COMPARATOR.PROTOCOL_ID,
            "paper_level_status": COMPARATOR.PAPER_LEVEL_STATUS,
            "profile_status": "PASS_PROFILE",
            "git_sha": "a" * 40,
            "source_sha256": {},
            "provenance_window": {"git_sha_end": "a" * 40},
            "git_source_state": {"untracked": [], "different_from_head": []},
        }
        with self.assertRaises(ValueError):
            COMPARATOR._validate_profile(forged)

    def test_profile_role_requires_exact_worker_shape_and_context(self):
        local_four = {
            "requested_workers": 4,
            "requested_logical_cpus": 4,
            "hardware": {"execution_context": {"github_actions": False}},
        }
        self.assertEqual(COMPARATOR._profile_role(local_four), "work_4core")
        mismatched = dict(local_four, requested_workers=8)
        self.assertIsNone(COMPARATOR._profile_role(mismatched))
        fake_github = {
            "requested_workers": 4,
            "requested_logical_cpus": 4,
            "hardware": {"execution_context": {"github_actions": True}},
        }
        self.assertIsNone(COMPARATOR._profile_role(fake_github))


if __name__ == "__main__":
    unittest.main()
