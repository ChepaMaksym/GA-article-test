"""CI-only all30 registry and per-upload producer-attempt identity checks."""
from __future__ import annotations

import copy
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from chc_qx_alignment_study import contract


SHA = "a"*40
RUN_ID = 37


class RegistryIdentityTests(unittest.TestCase):
    def fixture(self, directory):
        preparation = {
            "schema": contract.PREPARATION_SCHEMA, "seed": 44001, "status": "PASS_PREPARATION",
            "provenance": {"protocol_id": contract.PROTOCOL_ID,
                           "protocol_sha256": contract.PROTOCOL_SHA256,
                           "implementation_sha": SHA, "workflow_sha": SHA,
                           "run_id": RUN_ID, "run_attempt": 1},
        }
        preparation_path = directory/"preparation.json"
        identity = contract.write_json(preparation_path, preparation)
        cases = [{
            "seed": seed, "status": "PASS_PREPARATION", "preparation": dict(identity),
            "source_run_id": RUN_ID, "source_artifact_id": 100000+seed,
            "source_artifact_name": f"eu26-21-qx-preparation-{seed}-{RUN_ID}-{1 if seed == 44001 else 2}",
            "source_artifact_digest": "sha256:"+"d"*64,
        } for seed in contract.CASE_SEEDS]
        registry = {
            "schema": contract.REGISTRY_SCHEMA, "protocol_id": contract.PROTOCOL_ID,
            "protocol_sha256": contract.PROTOCOL_SHA256, "implementation_sha": SHA,
            "source_run_id": RUN_ID, "all_30_accounted": True, "frozen_before_main_search": True,
            "cases": cases,
        }
        registry_path = directory/"registry.json"
        contract.write_json(registry_path, registry)
        return preparation_path, registry_path, preparation, registry

    def reject_registry(self, mutate):
        with tempfile.TemporaryDirectory() as temporary:
            path, registry_path, _, registry = self.fixture(Path(temporary))
            changed = copy.deepcopy(registry)
            mutate(changed)
            contract.write_json(registry_path, changed)
            with self.assertRaises(ValueError):
                contract.load_registered_preparation(path, registry_path, seed=44001, expected_sha=SHA)

    def reject_provenance(self, mutate):
        with tempfile.TemporaryDirectory() as temporary:
            path, registry_path, preparation, registry = self.fixture(Path(temporary))
            mutate(preparation["provenance"])
            registry["cases"][0]["preparation"] = contract.write_json(path, preparation)
            contract.write_json(registry_path, registry)
            with self.assertRaises(ValueError):
                contract.load_registered_preparation(path, registry_path, seed=44001, expected_sha=SHA)

    def test_mixed_upload_attempts_remain_valid_without_rerunning_preparations(self):
        with tempfile.TemporaryDirectory() as temporary:
            path, registry_path, _, registry = self.fixture(Path(temporary))
            row, source = contract.load_registered_preparation(path, registry_path, seed=44001, expected_sha=SHA)
            self.assertEqual(row["provenance"]["run_attempt"], 1)
            self.assertTrue(registry["cases"][1]["source_artifact_name"].endswith("-2"))
            self.assertEqual(source["source_run_id"], RUN_ID)

    def test_another_seed_cannot_silently_point_to_another_run(self):
        self.reject_registry(lambda row: row["cases"][-1].update(source_run_id=RUN_ID+1))
        self.reject_registry(lambda row: row.update(source_run_id=RUN_ID+1))

    def test_all30_artifact_ids_and_names_must_be_unique(self):
        self.reject_registry(lambda row: row["cases"][-1].update(
            source_artifact_id=row["cases"][0]["source_artifact_id"]))
        self.reject_registry(lambda row: row["cases"][-1].update(
            source_artifact_name=row["cases"][0]["source_artifact_name"]))

    def test_artifact_names_bind_the_seed_and_run_and_positive_attempt(self):
        self.reject_registry(lambda row: row["cases"][-1].update(
            source_artifact_name=f"eu26-21-qx-preparation-44001-{RUN_ID}-2"))
        self.reject_registry(lambda row: row["cases"][-1].update(
            source_artifact_name=f"eu26-21-qx-preparation-44030-{RUN_ID+1}-2"))
        self.reject_registry(lambda row: row["cases"][-1].update(
            source_artifact_name=f"eu26-21-qx-preparation-44030-{RUN_ID}-0"))

    def test_embedded_producer_attempt_must_match_its_own_upload_not_the_current_job(self):
        self.reject_provenance(lambda row: row.update(run_attempt=2))
        self.reject_provenance(lambda row: row.update(run_attempt=True))

    def test_current_preparation_protocol_and_workflow_identity_are_checked(self):
        self.reject_provenance(lambda row: row.update(workflow_sha="b"*40))
        self.reject_provenance(lambda row: row.update(protocol_id="another-study"))
        self.reject_provenance(lambda row: row.update(run_id=RUN_ID+1))

    def test_registry_is_complete_frozen_and_bound_to_the_protocol(self):
        self.reject_registry(lambda row: row.update(all_30_accounted=False))
        self.reject_registry(lambda row: row.update(frozen_before_main_search=False))
        self.reject_registry(lambda row: row.update(protocol_id="another-study"))
        self.reject_registry(lambda row: row["cases"].pop())

    def test_unrelated_entry_metadata_cannot_be_empty_or_coerced(self):
        self.reject_registry(lambda row: row["cases"][-1].update(source_artifact_id=True))
        self.reject_registry(lambda row: row["cases"][-1].update(source_artifact_digest="missing"))
        self.reject_registry(lambda row: row["cases"][-1]["preparation"].update(bytes=0))
        self.reject_registry(lambda row: row["cases"][-1]["preparation"].update(sha256="not-a-hash"))
        self.reject_registry(lambda row: row["cases"][-1].update(status="incomplete"))


if __name__ == "__main__":
    unittest.main()
