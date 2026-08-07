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

    def test_coherently_forged_payload_manifest_is_rejected(self):
        source_hashes = COMPARATOR._current_source_hashes()
        clean = {"untracked": [], "different_from_head": []}
        forged_sha = "e" * 64
        forged_manifest = {
            "instance_count": 31,
            "member_count": 1_143,
            "payload_bytes": 1,
            "sha256": forged_sha,
        }
        profile = {
            "protocol_id": COMPARATOR.PROTOCOL_ID,
            "paper_level_status": COMPARATOR.PAPER_LEVEL_STATUS,
            "profile_status": "PASS_PROFILE",
            "git_sha": "a" * 40,
            "source_sha256": source_hashes,
            "git_source_state": clean,
            "provenance_window": {
                "git_sha_end": "a" * 40,
                "source_sha256_end": source_hashes,
                "git_source_state_end": clean,
            },
            "archive": {
                "provided": True,
                "required": True,
                "expected_sha256": COMPARATOR.ARCHIVE_SHA256,
                "expected_bytes": COMPARATOR.ARCHIVE_BYTES,
                "bytes": COMPARATOR.ARCHIVE_BYTES,
                "sha256": COMPARATOR.ARCHIVE_SHA256,
                "sha256_end": COMPARATOR.ARCHIVE_SHA256,
                "instance_count": 31,
                "temporary_uncompressed_tar_bytes": (
                    COMPARATOR.UNCOMPRESSED_TAR_BYTES
                ),
                "temporary_uncompressed_tar_sha256": (
                    COMPARATOR.UNCOMPRESSED_TAR_SHA256
                ),
                "temporary_uncompressed_tar_sha256_end": (
                    COMPARATOR.UNCOMPRESSED_TAR_SHA256
                ),
                "authenticated_tar_snapshot_bytes": (
                    COMPARATOR.UNCOMPRESSED_TAR_BYTES
                ),
                "authenticated_tar_snapshot_sha256_start": (
                    COMPARATOR.UNCOMPRESSED_TAR_SHA256
                ),
                "authenticated_tar_snapshot_sha256_end": (
                    COMPARATOR.UNCOMPRESSED_TAR_SHA256
                ),
                "payload_manifest": forged_manifest,
                "payload_manifest_end": forged_manifest,
                "payload_manifest_sha256_start": forged_sha,
                "payload_manifest_sha256_end": forged_sha,
            },
        }
        with self.assertRaisesRegex(ValueError, "payload-manifest"):
            COMPARATOR._validate_profile(profile)

    def test_empty_scientific_objects_are_rejected(self):
        formula = {
            "case_id": "deleter-small-seed2602000",
            "seed": 2602000,
            "turns": 80,
            "invariant_pass": True,
            "deletion_pass": True,
            "contract_invariants": {f"i{index}": True for index in range(10)},
            "canonical_result": {},
        }
        with self.assertRaisesRegex(ValueError, "recomputation"):
            COMPARATOR._validate_formula_cases([formula])

        archive = {"instance": "C2000.9", "canonical_result": {}}
        with self.assertRaisesRegex(ValueError, "canonical instance"):
            COMPARATOR._recompute_archive_aggregate([archive])


if __name__ == "__main__":
    unittest.main()
