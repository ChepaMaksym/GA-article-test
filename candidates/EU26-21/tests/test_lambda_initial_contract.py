"""Contract/replay fixtures, executed by GitHub Actions only."""
from __future__ import annotations

import os
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from lambda_initial_study import contract  # noqa: E402


def masks():
    return tuple(tuple([1] * (1 + index % 4) + [0] * (39 - index % 4)) for index in range(50))


def score(mask):
    count = sum(mask)
    return (0.5 + count / 100, -count / 40) if count else (0.0, -1.0)


class RegistrationTests(unittest.TestCase):
    def test_protocol_original_byte_hash_and_complete_ledger(self):
        protocol = contract.validate_protocol(ROOT / "lambda_initial_study/protocol.json")
        self.assertEqual(protocol["comparison"]["lambda_initial_values"], [1, 5, 10, 20, 40])
        self.assertEqual(protocol["rng"]["case_seeds"], list(range(43001, 43031)))
        self.assertEqual(len(contract.SEARCH_ARMS), 6)
        self.assertEqual(protocol["execution"]["physical_validation_invocations_total"], 64500)

    def test_unregistered_digest_rejected(self):
        with self.assertRaises(ValueError):
            contract.validate_protocol(ROOT / "lambda_initial_study/protocol.json", "0" * 64)

    def test_protocol_edit_rejected_before_json_interpretation(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "protocol.json"
            path.write_bytes((ROOT / "lambda_initial_study/protocol.json").read_bytes() + b" ")
            with self.assertRaises(ValueError):
                contract.validate_protocol(path)

    def test_registration_ancestor_and_reused_files_have_original_bytes(self):
        identity = contract.verify_registration()
        self.assertEqual(identity["content_freeze_commit_sha"], contract.CONTENT_FREEZE_SHA)
        self.assertEqual(len(identity["reused_files"]), len(contract.REUSED_FILES))
        self.assertIn("candidates/EU26-21/local_optima_study/aggregate.py", identity["reused_files"])

    def test_missing_registration_ancestor_rejected(self):
        result = SimpleNamespace(returncode=1)
        with mock.patch.object(contract.subprocess, "run", return_value=result), self.assertRaises(ValueError):
            contract.verify_registration()

    def test_wrong_registered_blob_rejected(self):
        with mock.patch.object(contract.subprocess, "run", return_value=SimpleNamespace(returncode=0)), \
             mock.patch.object(contract, "git_blob", return_value=b"not-the-registered-protocol"), \
             self.assertRaises(ValueError):
            contract.verify_registration()

    def test_reused_kernel_change_rejected(self):
        real_blob = contract.git_blob
        def altered_blob(revision, relative):
            content = real_blob(revision, relative)
            return content + b" " if revision == contract.REUSED_KERNEL_SHA else content
        with mock.patch.object(contract, "git_blob", side_effect=altered_blob), self.assertRaises(ValueError):
            contract.verify_registration()

    def test_local_execution_rejected_before_git_or_environment(self):
        with mock.patch.dict(os.environ, {"GITHUB_ACTIONS": "false"}), \
             mock.patch.object(contract, "git") as git_call, self.assertRaises(ValueError):
            contract.authenticate(protocol_path=ROOT / "lambda_initial_study/protocol.json", expected_sha="a" * 40)
        git_call.assert_not_called()

    def test_dirty_scientific_checkout_rejected(self):
        with mock.patch.dict(os.environ, {"GITHUB_ACTIONS": "true"}), \
             mock.patch.object(contract, "git", side_effect=["a" * 40, " M changed.py"]), \
             self.assertRaises(ValueError):
            contract.authenticate(protocol_path=ROOT / "lambda_initial_study/protocol.json", expected_sha="a" * 40)

    def test_workflow_sha_mismatch_rejected(self):
        env = {"GITHUB_ACTIONS": "true", "GITHUB_RUN_ID": "3", "GITHUB_RUN_ATTEMPT": "1",
               "STUDY_WORKFLOW_SHA": "b" * 40, "GITHUB_REF": "refs/heads/fixture"}
        with mock.patch.dict(os.environ, env), \
             mock.patch.object(contract, "git", side_effect=["a" * 40, ""]), \
             self.assertRaises(ValueError):
            contract.authenticate(protocol_path=ROOT / "lambda_initial_study/protocol.json", expected_sha="a" * 40)

    def test_inventory_includes_transport_and_all_reused_kernels(self):
        inventory = contract.implementation_inventory()
        self.assertIn(".github/scripts/download_study_artifacts.py", inventory)
        for relative in contract.REUSED_FILES:
            self.assertIn(f"candidates/EU26-21/{relative}", inventory)


class ReplayTests(unittest.TestCase):
    def test_exact_fifty_physical_initial_calls_even_with_duplicates(self):
        objective = mock.Mock(side_effect=score)
        shared = contract.SharedInitialization(objective, masks())
        self.assertEqual(objective.call_count, 50)
        self.assertEqual(shared.physical_validation_calls, 50)
        self.assertEqual(shared.unique_mask_count, 4)
        self.assertEqual(shared.actual_tree_fits, 50)

    def test_replay_initial_fifty_do_not_retrain(self):
        objective = mock.Mock(side_effect=score)
        shared = contract.SharedInitialization(objective, masks())
        replay = shared.replay(objective)
        for mask, expected in zip(shared.masks, shared.scores):
            self.assertEqual(replay(mask), expected)
        self.assertEqual(objective.call_count, 50)
        self.assertEqual(replay.calls, 50)
        self.assertEqual(replay.physical_validation_calls, 0)

    def test_wrong_initial_mask_order_fails_without_call_or_rng(self):
        objective = mock.Mock(side_effect=score)
        shared = contract.SharedInitialization(objective, masks())
        replay = shared.replay(objective)
        with self.assertRaises(ValueError):
            replay(shared.masks[1])
        self.assertEqual(replay.calls, 0)
        self.assertEqual(objective.call_count, 50)

    def test_every_duplicate_after_initialization_is_physical(self):
        objective = mock.Mock(side_effect=score)
        shared = contract.SharedInitialization(objective, masks())
        replay = shared.replay(objective)
        for mask in shared.masks:
            replay(mask)
        for _ in range(350):
            replay(shared.masks[0])
        ledger = replay.complete()
        self.assertEqual(objective.call_count, 400)
        self.assertEqual(ledger["logical_calls"], 400)
        self.assertEqual(ledger["post_initial_physical_calls"], 350)
        self.assertEqual(ledger["post_initial_duplicate_queries"], 350)
        with self.assertRaises(ValueError):
            replay(shared.masks[0])
        self.assertEqual(objective.call_count, 400)

    def test_independent_replays_do_not_share_search_state(self):
        objective = mock.Mock(side_effect=score)
        shared = contract.SharedInitialization(objective, masks())
        first, second = shared.replay(objective), shared.replay(objective)
        first(shared.masks[0])
        self.assertEqual(first.calls, 1)
        self.assertEqual(second.calls, 0)
        for mask in shared.masks:
            second(mask)
        self.assertEqual(objective.call_count, 50)

    def test_empty_initial_masks_count_queries_but_not_tree_fits(self):
        shared = contract.SharedInitialization(score, [[0] * 40] * 50)
        self.assertEqual(shared.physical_validation_calls, 50)
        self.assertEqual(shared.actual_tree_fits, 0)
        replay = shared.replay(score)
        for _ in range(400):
            replay([0] * 40)
        self.assertEqual(replay.complete()["post_initial_actual_tree_fits"], 0)

    def test_incomplete_replay_is_not_success(self):
        replay = contract.SharedInitialization(score, masks()).replay(score)
        replay(masks()[0])
        with self.assertRaises(ValueError):
            replay.complete()

    def test_invalid_mask_or_score_rejected(self):
        for invalid in ([[1] * 39] * 50, [[True] + [0] * 39] * 50, masks()[:49]):
            with self.subTest(value=invalid), self.assertRaises(ValueError):
                contract.SharedInitialization(score, invalid)
        with self.assertRaises(ValueError):
            contract.SharedInitialization(lambda mask: (float("nan"), -sum(mask) / 40), masks())

    def test_objective_contains_no_test_arrays_or_prepared_container(self):
        prepared = SimpleNamespace(active_instances=np.array([0, 1]), x_train=np.zeros((3, 40)),
            y_train=np.array([0, 1, 0]), weight_train=np.ones(3), x_validation=np.zeros((2, 40)),
            y_validation=np.array([0, 1]), weight_validation=np.ones(2),
            x_test="forbidden", y_test="forbidden", weight_test="forbidden")
        objective = contract.objective_for(prepared)
        self.assertFalse(any("test" in key.lower() for key in vars(objective)))
        self.assertFalse(any(value is prepared for value in vars(objective).values()))


class ManifestTests(unittest.TestCase):
    def provenance(self):
        protocol = contract.validate_protocol(ROOT / "lambda_initial_study/protocol.json")
        registration = contract.verify_registration()
        environment = {"python_implementation": "fixture", "python_version": "fixture", "packages": {}}
        files = contract.implementation_inventory()
        return {**registration, "protocol_id": contract.PROTOCOL_ID,
                "protocol_sha256": contract.PROTOCOL_SHA256,
                "implementation_sha": "a" * 40, "workflow_sha": "a" * 40,
                "implementation_files": files, "implementation_files_sha256": contract.canonical_sha256(files),
                "environment": environment, "environment_sha256": contract.canonical_sha256(environment),
                "run_id": 3, "run_attempt": 1,
                "data_sha256": {key: protocol["data"][f"{key}_sha256"] for key in ("archive", "train", "test")}}

    def fixture(self, directory):
        provenance = self.provenance()
        contract.write_json(directory / "case.json", {"schema": contract.CASE_SCHEMA})
        path = contract.write_manifest(directory, seed=43001, artifact_name="case-fixture", provenance=provenance)
        return path, provenance

    def test_complete_flat_manifest_verifies_without_deserializing_model(self):
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)
            (directory / "model.joblib").write_bytes(b"never-deserialize-downloaded-fixture")
            path, provenance = self.fixture(directory)
            with mock.patch.object(contract, "runtime_environment", return_value=provenance["environment"]):
                result = contract.verify_manifest(path, expected_sha="a" * 40)
            self.assertEqual(len(result["files"]), 2)

    def test_unlisted_or_changed_bytes_rejected(self):
        for variant in ("unlisted", "changed"):
            with self.subTest(variant=variant), tempfile.TemporaryDirectory() as temp:
                directory = Path(temp)
                path, provenance = self.fixture(directory)
                if variant == "unlisted":
                    (directory / "other.txt").write_bytes(b"extra")
                else:
                    (directory / "case.json").write_bytes(b"modified")
                with mock.patch.object(contract, "runtime_environment", return_value=provenance["environment"]), \
                     self.assertRaises(ValueError):
                    contract.verify_manifest(path, expected_sha="a" * 40)

    def test_wrong_contract_source_or_workflow_rejected(self):
        for field in ("workflow_sha", "registration_protocol_blob_sha256", "reused_files_sha256"):
            with self.subTest(field=field), tempfile.TemporaryDirectory() as temp:
                directory = Path(temp)
                path, provenance = self.fixture(directory)
                manifest = contract.read_json(path)
                manifest["provenance"][field] = "0" * len(manifest["provenance"][field])
                contract.write_json(path, manifest)
                with mock.patch.object(contract, "runtime_environment", return_value=provenance["environment"]), \
                     self.assertRaises(ValueError):
                    contract.verify_manifest(path, expected_sha="a" * 40)

    def test_artifact_directories_or_bad_basename_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)
            contract.write_json(directory / "case.json", {})
            with self.assertRaises(ValueError):
                contract.write_manifest(directory, seed=43001, artifact_name="../escape", provenance={})
            (directory / "nested").mkdir()
            with self.assertRaises(ValueError):
                contract.write_manifest(directory, seed=43001, artifact_name="case", provenance={})


if __name__ == "__main__":
    unittest.main()
