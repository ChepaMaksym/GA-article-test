"""Pipeline fixtures. Execute these only in GitHub Actions."""

import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile

import numpy as np

from studies.knapsack_parameters.feasibility.data_audit import Instance
from studies.knapsack_parameters.ga_study.banks import create_bank, validate_bank
from studies.knapsack_parameters.ga_study.contract import (authenticate, canonical_bytes,
    read_json, safe_member, verify_file_manifest, write_file_manifest, write_json)
from studies.knapsack_parameters.ga_study.transport import (expected_jobs, extract_bundle,
                                                           verify_artifact_identity)


class BankFixtures(unittest.TestCase):
    def setUp(self):
        self.instance = Instance(3, 10, (10, 8, 8), (6, 5, 5), "fixture.kp", "UC", "s000", 0)

    def test_bank_shape_empty_first_and_exact_scores(self):
        arrays, metadata = create_bank(self.instance, 51001)
        self.assertTrue(validate_bank(self.instance, arrays, metadata, 51001))
        self.assertEqual(arrays["masks"].shape, (50, 3))
        self.assertEqual(arrays["masks"][0].tolist(), [0, 0, 0])
        self.assertTrue(arrays["feasible"][0])
        self.assertEqual(metadata["physical_evaluations"], 50)
        self.assertNotEqual(metadata["rng_before"], metadata["rng_after"])

    def test_deterministic_bank_and_rng_states(self):
        first, metadata1 = create_bank(self.instance, 51001)
        second, metadata2 = create_bank(self.instance, 51001)
        for name in first:
            np.testing.assert_array_equal(first[name], second[name])
        self.assertEqual(metadata1, metadata2)

    def test_bank_matches_independent_registered_entropy_and_draw_order(self):
        arrays, metadata = create_bank(self.instance, 51001)
        reference = np.random.Generator(np.random.PCG64(np.random.SeedSequence([0, 0, 51001, 0])))
        before = reference.bit_generator.state
        expected = (reference.random((49, 3)) < 0.5).astype(np.uint8)
        np.testing.assert_array_equal(arrays["masks"][1:], expected)
        self.assertEqual(metadata["rng_before"], before)
        self.assertEqual(metadata["rng_after"], reference.bit_generator.state)

    def test_bank_duplicates_not_removed(self):
        arrays, metadata = create_bank(self.instance, 51002)
        self.assertEqual(len(arrays["masks"]), 50)
        self.assertLess(len({row.tobytes() for row in arrays["masks"]}), 50)
        self.assertTrue(validate_bank(self.instance, arrays, metadata, 51002))

    def test_independent_score_verifier_rejects_modified_score(self):
        arrays, metadata = create_bank(self.instance, 51001)
        arrays["profit"][0] = 1
        with self.assertRaisesRegex(ValueError, "score mismatch"):
            validate_bank(self.instance, arrays, metadata, 51001)

    def test_rng_state_checksum_rejected(self):
        arrays, metadata = create_bank(self.instance, 51001)
        metadata["rng_after_sha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "RNG state"):
            validate_bank(self.instance, arrays, metadata, 51001)

    def test_wrong_seed_is_not_substituted(self):
        arrays, metadata = create_bank(self.instance, 51001)
        with self.assertRaisesRegex(ValueError, "identity"):
            validate_bank(self.instance, arrays, metadata, 51002)


class EvidenceFixtures(unittest.TestCase):
    def test_exact_file_inventory_and_corruption(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            write_json(root / "payload.json", {"counter": 2 ** 100})
            write_file_manifest(root)
            self.assertEqual(len(verify_file_manifest(root)["files"]), 1)
            write_json(root / "payload.json", {"counter": 2 ** 100 + 1})
            with self.assertRaisesRegex(ValueError, "hash/length"):
                verify_file_manifest(root)

    def test_unexpected_member_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            write_json(root / "one.json", {"x": 1})
            write_file_manifest(root)
            write_json(root / "two.json", {"x": 2})
            with self.assertRaisesRegex(ValueError, "unexpected"):
                verify_file_manifest(root)

    def test_path_traversal_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            for path in ("../outside.json", "/absolute", "x\\y", "C:secret", ""):
                with self.subTest(path=path), self.assertRaises(ValueError):
                    safe_member(temporary, path)

    def test_duplicate_file_manifest_entries_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            write_json(root / "one.json", {"x": 1})
            manifest = write_file_manifest(root)
            manifest["files"].append(manifest["files"][0].copy())
            write_json(root / "file_manifest.json", manifest)
            with self.assertRaisesRegex(ValueError, "duplicate"):
                verify_file_manifest(root)

    def test_zip_slip_rejected(self):
        raw = io.BytesIO()
        with zipfile.ZipFile(raw, "w") as archive:
            archive.writestr("../outside", b"no")
        with tempfile.TemporaryDirectory() as temporary, self.assertRaisesRegex(ValueError, "unsafe ZIP"):
            extract_bundle(raw.getvalue(), Path(temporary) / "bundle")

    def test_canonical_json_exact_integer_states(self):
        value = {"state": 2 ** 127, "small": 1}
        self.assertEqual(json.loads(canonical_bytes(value)), value)
        self.assertNotIn(b"\n", canonical_bytes(value))

    def test_ci_guard_rejects_local_execution(self):
        with patch.dict("os.environ", {"GITHUB_ACTIONS": "false"}), self.assertRaisesRegex(ValueError, "only in GitHub Actions"):
            authenticate("1" * 40, scientific=False)


class TransportFixtures(unittest.TestCase):
    def test_ninety_unique_main_jobs(self):
        instances = [Instance(100, 1, (1,) * 100, (1,) * 100, "fixture", label, f"s{index:03d}", index)
                     for label in ("UC", "WC", "SC") for index in range(10)]
        jobs = expected_jobs(instances, "run")
        self.assertEqual(len(jobs), 90)
        self.assertEqual(len({row["job_key"] for row in jobs}), 90)
        self.assertEqual(jobs[0]["job_key"], "UC-s000-51001-51010")
        self.assertEqual(jobs[-1]["seed_last"], 51030)

    def test_pilot_jobs_fixed_not_outcome_selected(self):
        jobs = expected_jobs([], "pilot")
        self.assertEqual([row["instance_id"] for row in jobs], ["UC-s000", "WC-s001", "SC-s005"])
        self.assertTrue(all(row["seed_first"] == row["seed_last"] == 52001 for row in jobs))

    def test_mixed_sha_and_expired_artifacts_rejected(self):
        metadata = {"id": 7, "expired": False, "digest": "sha256:" + "a" * 64,
                    "workflow_run": {"id": 8, "head_sha": "b" * 40,
                                     "head_branch": "research/masters-ga-knapsack-parameters"}}
        verify_artifact_identity(metadata, artifact_id=7, source_run_id=8, source_sha="b" * 40, zip_sha256="a" * 64)
        with self.assertRaisesRegex(ValueError, "identity"):
            verify_artifact_identity(metadata, artifact_id=7, source_run_id=8, source_sha="c" * 40)
        metadata["expired"] = True
        with self.assertRaisesRegex(ValueError, "expired"):
            verify_artifact_identity(metadata, artifact_id=7, source_run_id=8, source_sha="b" * 40)


if __name__ == "__main__":
    unittest.main()
