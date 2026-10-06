"""Preregistration, artifact and preparation identity fixtures; CI only."""
from __future__ import annotations

import copy
from contextlib import ExitStack
import os
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from chc_qx_alignment_study import contract  # noqa: E402


class ContractTests(unittest.TestCase):
    def test_registered_protocol_byte_hash_and_scalar_qx_contract(self):
        protocol = contract.validate_protocol(ROOT / "chc_qx_alignment_study/protocol.json")
        self.assertEqual(protocol["rng"]["case_seeds"], list(range(44001, 44031)))
        self.assertEqual(protocol["comparison"]["search_arms"], list(contract.SEARCH_ARMS))
        self.assertFalse(protocol["comparison"]["smaller_features_in_search_success"])
        self.assertFalse(protocol["search"]["equal_objective_budget"])
        self.assertTrue(protocol["analysis"]["descriptive_only"])

    def test_changed_protocol_bytes_or_requested_digest_rejected(self):
        with self.assertRaises(ValueError):
            contract.validate_protocol(ROOT / "chc_qx_alignment_study/protocol.json", "0" * 64)
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "protocol.json"
            path.write_bytes((ROOT / "chc_qx_alignment_study/protocol.json").read_bytes() + b" ")
            with self.assertRaises(ValueError):
                contract.validate_protocol(path)

    def test_registration_ancestor_and_frozen_dependency_bytes(self):
        identity = contract.verify_registration()
        self.assertEqual(identity["content_freeze_commit_sha"], contract.CONTENT_FREEZE_SHA)
        self.assertEqual(identity["reused_kernel_revision"], contract.REUSED_KERNEL_SHA)
        self.assertEqual(len(identity["reused_files"]), len(contract.REUSED_FILES))

    def test_missing_registration_or_altered_blob_rejected(self):
        with mock.patch.object(contract.subprocess, "run", return_value=SimpleNamespace(returncode=1)), \
             self.assertRaises(ValueError):
            contract.verify_registration()
        with mock.patch.object(contract.subprocess, "run", return_value=SimpleNamespace(returncode=0)), \
             mock.patch.object(contract, "git_blob", return_value=b"changed"), self.assertRaises(ValueError):
            contract.verify_registration()

    def test_local_execution_fails_before_git_or_data(self):
        with mock.patch.dict(os.environ, {"GITHUB_ACTIONS": "false"}), \
             mock.patch.object(contract, "git") as git_call, self.assertRaises(ValueError):
            contract.authenticate(protocol_path=ROOT / "chc_qx_alignment_study/protocol.json", expected_sha="a" * 40)
        git_call.assert_not_called()

    def test_dirty_or_wrong_workflow_checkout_rejected(self):
        for responses, workflow_sha in ((["a" * 40, " M edited.py"], "a" * 40),
                                        (["a" * 40, ""], "b" * 40)):
            with self.subTest(responses=responses):
                env = {"GITHUB_ACTIONS": "true", "GITHUB_RUN_ID": "3", "GITHUB_RUN_ATTEMPT": "1",
                       "STUDY_WORKFLOW_SHA": workflow_sha, "GITHUB_REF": "refs/heads/fixture"}
                with mock.patch.dict(os.environ, env), mock.patch.object(contract, "git", side_effect=responses), \
                     self.assertRaises(ValueError):
                    contract.authenticate(protocol_path=ROOT / "chc_qx_alignment_study/protocol.json", expected_sha="a" * 40)

    def test_scalar_score_and_masks_reject_lexicographic_or_coercible_values(self):
        for value in ((0.7, -0.5), True, float("nan"), -0.1, 1.1):
            with self.subTest(value=value), self.assertRaises(ValueError):
                contract.scalar_score(value)
        self.assertEqual(contract.scalar_score(0.7), 0.7)
        for mask in ([1] * 39, [True] + [0] * 39, [1.0] + [0] * 39):
            with self.subTest(mask=mask), self.assertRaises(ValueError):
                contract.validate_mask(mask)

    def test_output_guard_never_modifies_existing_evidence(self):
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp) / "artifact"
            directory.mkdir()
            member = directory / "case.json"
            member.write_bytes(b"preserved")
            with self.assertRaises(ValueError):
                contract.ensure_empty_output(directory)
            self.assertEqual(member.read_bytes(), b"preserved")
            self.assertEqual([path.name for path in directory.iterdir()], ["case.json"])


class FrozenPreparationTests(unittest.TestCase):
    def fixture(self, directory):
        preparation = {"schema": contract.PREPARATION_SCHEMA, "seed": 44001, "status": "PASS_PREPARATION",
                       "provenance": {"implementation_sha": "a" * 40, "protocol_sha256": contract.PROTOCOL_SHA256,
                                      "protocol_id": contract.PROTOCOL_ID, "workflow_sha": "a" * 40,
                                      "run_id": 3, "run_attempt": 1}}
        path = directory / "preparation.json"
        identity = contract.write_json(path, preparation)
        cases = [{"seed": seed, "status": "PASS_PREPARATION", "preparation": identity,
                  "source_run_id": 3, "source_artifact_id": seed + 90000,
                  "source_artifact_name": f"eu26-21-qx-preparation-{seed}-3-1",
                  "source_artifact_digest": "sha256:" + "d" * 64}
                 for seed in contract.CASE_SEEDS]
        registry = {"schema": contract.REGISTRY_SCHEMA, "implementation_sha": "a" * 40,
                    "protocol_id": contract.PROTOCOL_ID, "protocol_sha256": contract.PROTOCOL_SHA256,
                    "source_run_id": 3, "all_30_accounted": True, "frozen_before_main_search": True,
                    "cases": cases}
        registry_path = directory / "registry.json"
        contract.write_json(registry_path, registry)
        return path, registry_path, registry

    def test_exact_preparation_source_identity_without_loading_models(self):
        with tempfile.TemporaryDirectory() as temp:
            path, registry_path, _ = self.fixture(Path(temp))
            row, identity = contract.load_registered_preparation(path, registry_path, seed=44001, expected_sha="a" * 40)
            self.assertEqual(row["status"], "PASS_PREPARATION")
            self.assertEqual(identity["source_run_id"], 3)
            self.assertEqual(identity["source_artifact_id"], 134001)

    def test_duplicate_missing_wrong_seed_sha_or_byte_identity_rejected(self):
        for variant in ("duplicate", "missing", "sha", "bytes", "source", "status"):
            with self.subTest(variant=variant), tempfile.TemporaryDirectory() as temp:
                path, registry_path, registry = self.fixture(Path(temp))
                registry = copy.deepcopy(registry)
                if variant == "duplicate":
                    registry["cases"][1]["seed"] = 44001
                elif variant == "missing":
                    registry["cases"].pop()
                elif variant == "sha":
                    registry["implementation_sha"] = "b" * 40
                elif variant == "bytes":
                    path.write_bytes(path.read_bytes() + b" ")
                elif variant == "source":
                    registry["cases"][0]["source_run_id"] = 4
                else:
                    registry["cases"][0]["status"] = "NOT_EVALUABLE_SAMPLER"
                contract.write_json(registry_path, registry)
                with self.assertRaises(ValueError):
                    contract.load_registered_preparation(path, registry_path, seed=44001, expected_sha="a" * 40)


class ManifestTests(unittest.TestCase):
    def provenance(self):
        protocol = contract.validate_protocol(ROOT / "chc_qx_alignment_study/protocol.json")
        environment = {"python_implementation": "fixture", "python_version": "fixture", "packages": {}}
        files = contract.implementation_inventory()
        return {**contract.verify_registration(), "protocol_id": contract.PROTOCOL_ID,
                "protocol_sha256": contract.PROTOCOL_SHA256, "implementation_sha": "a" * 40,
                "workflow_sha": "a" * 40, "run_id": 3, "run_attempt": 1,
                "implementation_files": files, "implementation_files_sha256": contract.canonical_sha256(files),
                "environment": environment, "environment_sha256": contract.canonical_sha256(environment),
                "data_sha256": {key: protocol["data"][f"{key}_sha256"] for key in ("archive", "train", "test")}}

    def test_flat_case_manifest_checks_exact_bytes_not_deserialized_model(self):
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)
            provenance = self.provenance()
            contract.write_json(directory / "case.json", {"schema": contract.CASE_SCHEMA})
            (directory / "model.joblib").write_bytes(b"untrusted-downloaded-model-must-never-be-loaded")
            path = contract.write_manifest(directory, seed=44001, artifact_name="case-fixture", provenance=provenance)
            with mock.patch.object(contract, "runtime_environment", return_value=provenance["environment"]):
                manifest = contract.verify_manifest(path, expected_sha="a" * 40)
            self.assertEqual(set(manifest["files"]), {"case.json", "model.joblib"})

    def test_unlisted_or_changed_file_rejected(self):
        for variant in ("unlisted", "changed"):
            with self.subTest(variant=variant), tempfile.TemporaryDirectory() as temp:
                directory = Path(temp)
                provenance = self.provenance()
                contract.write_json(directory / "case.json", {})
                path = contract.write_manifest(directory, seed=44001, artifact_name="case", provenance=provenance)
                (directory / ("extra.txt" if variant == "unlisted" else "case.json")).write_bytes(b"changed")
                with mock.patch.object(contract, "runtime_environment", return_value=provenance["environment"]), \
                     self.assertRaises(ValueError):
                    contract.verify_manifest(path, expected_sha="a" * 40)


class RunnerOrderingTests(unittest.TestCase):
    def test_all_three_masks_are_persisted_before_loading_holdout_and_diagnostics_do_not_feed_back(self):
        from chc_qx_alignment_study import diagnostics, run_case, search, source_gate
        mask = [1] + [0] * 39
        source = {"registry_sha256": "r" * 64, "preparation": {"sha256": "p" * 64, "bytes": 1},
                  "source_run_id": 3, "source_artifact_id": 4}
        preparation = {"status": "PASS_PREPARATION", "initial_masks": [mask] * 50,
                       "initial_scores": [0.7] * 50, "sampling": {"selected_rows": [0, 1]},
                       "training_data": {}, "counts": {"shared_initial_actual_tree_fits": 50}}
        protocol = {"data": {"train_sha256": "f" * 64, "test_sha256": "h" * 64}}
        provenance = {"run_id": 3, "run_attempt": 1}
        events = []
        def fake_search(**arguments):
            events.append("search")
            arguments["active_objective"](mask)
            arguments["active_objective"](mask)
            arguments["full_objective"](mask)
            return {"selected_mask": mask, "full_validation_wba": 0.7, "active_physical_calls": 2,
                    "active_logical_calls": 52, "full_calls": 1, "snapshot": {"mask": mask, "active_wba": 0.7},
                    "status": "evaluable", "active_trace": [], "generation_trace": [], "checkpoints": [],
                    "full_evaluations": []}
        def fake_diagnostics(**arguments):
            events.append("diagnostics")
            for _ in range(41):
                arguments["active_objective"](mask)
                arguments["full_objective"](mask)
            return {"approximate": {"center_wba": 0.7}, "full": {"center_wba": 0.7}}
        metrics = {scale: {"confusion_matrix": [[9, 1], [2, 8]]} for scale in ("weighted", "unweighted")}
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp) / "case"
            def fake_holdout(*arguments, **kwargs):
                events.append("holdout")
                freeze = contract.read_json(directory / "terminal-masks.json")
                self.assertEqual(set(freeze["arms"]), set(contract.SEARCH_ARMS))
                self.assertEqual(freeze["test_evaluations_so_far"], 0)
                self.assertEqual(events.count("search"), 3)
                return SimpleNamespace()
            def fake_terminal(*arguments, **kwargs):
                events.append("test")
                return metrics, {"file": kwargs["path"].name}
            with ExitStack() as stack:
                patches = (
                    (run_case, "authenticate", mock.Mock(return_value=(protocol, provenance))),
                    (run_case, "load_registered_preparation", mock.Mock(return_value=(preparation, source))),
                    (run_case, "file_sha256", mock.Mock(return_value="f" * 64)),
                    (run_case, "prepare_training", mock.Mock(return_value=SimpleNamespace())),
                    (run_case, "verify_reconstructed_training", mock.Mock(return_value=([mask] * 50, [0.7] * 50))),
                    (run_case, "objective_for", mock.Mock(return_value=lambda value: 0.7)),
                    (source_gate, "load_evolution", mock.Mock(return_value=SimpleNamespace(Evolution=object(), creator=object()))),
                    (search, "run_qx_search", fake_search),
                    (diagnostics, "certify_snapshot", fake_diagnostics),
                    (run_case, "load_terminal_holdout", fake_holdout),
                    (run_case, "evaluate_and_persist", fake_terminal),
                )
                for module, name, replacement in patches:
                    stack.enter_context(mock.patch.object(module, name, replacement))
                row = run_case.run_case(train=Path("train"), test=Path("test"), upstream=Path("upstream"),
                    seed=44001, expected_sha="a" * 40, preparation_path=Path("preparation"),
                    registry_path=Path("registry"), output=directory)
            self.assertEqual(events, ["search"] * 3 + ["diagnostics"] * 3 + ["holdout"] + ["test"] * 3)
            self.assertEqual(row["counts"]["test_evaluations"], 3)
            self.assertEqual(row["counts"]["diagnostic_calls"], 246)
            self.assertEqual(row["counts"]["search_active_physical_calls"], 6)

    def test_invalid_sampler_status_never_reads_training_or_holdout_or_runs_search(self):
        from chc_qx_alignment_study import run_case
        source = {"registry_sha256": "r" * 64, "preparation": {"sha256": "p" * 64, "bytes": 1},
                  "source_run_id": 3, "source_artifact_id": 4}
        preparation = {"status": "NOT_EVALUABLE_SAMPLER", "initial_masks": [[0] * 40] * 50,
                       "initial_scores": None, "sampling": {}, "training_data": {}}
        with tempfile.TemporaryDirectory() as temp, \
             mock.patch.object(run_case, "authenticate", return_value=({}, {"run_id": 3, "run_attempt": 1})), \
             mock.patch.object(run_case, "load_registered_preparation", return_value=(preparation, source)), \
             mock.patch.object(run_case, "prepare_training") as train_loader, \
             mock.patch.object(run_case, "load_terminal_holdout") as test_loader:
            row = run_case.run_case(train=Path("train"), test=Path("test"), upstream=Path("upstream"),
                seed=44001, expected_sha="a" * 40, preparation_path=Path("preparation"),
                registry_path=Path("registry"), output=Path(temp) / "case")
            train_loader.assert_not_called()
            test_loader.assert_not_called()
        self.assertEqual(row["status"], "NOT_EVALUABLE_SAMPLER")
        self.assertEqual(row["arms"], {})
        self.assertEqual(row["counts"]["test_evaluations"], 0)


if __name__ == "__main__":
    unittest.main()
