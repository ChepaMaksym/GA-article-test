from __future__ import annotations

import json
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path

from eu2612.contract import CONTRACT_PATH, ContractError, load_contract, validate_contract


class ContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.contract = load_contract()

    def test_default_contract_passes_frozen_byte_hash(self) -> None:
        self.assertEqual(self.contract["candidate_id"], "EU26-12")

    def test_forbidden_claims_are_complete(self) -> None:
        self.assertTrue(
            {
                "PASS_FULL",
                "FULL_ARCHIVE_MD5_RECOMPUTED",
                "EXACT_ARTIFACT_GIT_TREE_MATCH",
            }.issubset(
                self.contract["forbidden_claims"]
            )
        )

    def test_status_mutation_fails(self) -> None:
        value = deepcopy(self.contract)
        value["status"] = "PASS_FULL"
        with self.assertRaises(ContractError):
            validate_contract(value)

    def test_exact_tree_promotion_fails(self) -> None:
        value = deepcopy(self.contract)
        value["upstream"]["artifact_exact_tree_match"] = True
        with self.assertRaises(ContractError):
            validate_contract(value)

    def test_superseded_mapping_field_fails(self) -> None:
        value = deepcopy(self.contract)
        value["upstream"]["artifact_maps_to_commit"] = True
        with self.assertRaises(ContractError):
            validate_contract(value)

    def test_git_blob_count_promotion_fails(self) -> None:
        value = deepcopy(self.contract)
        value["upstream"]["matched_git_blobs"] = 15
        with self.assertRaises(ContractError):
            validate_contract(value)

    def test_missing_git_workflow_removal_fails(self) -> None:
        value = deepcopy(self.contract)
        value["upstream"]["missing_tracked_paths"] = []
        with self.assertRaises(ContractError):
            validate_contract(value)

    def test_artifact_only_inventory_mutation_fails(self) -> None:
        value = deepcopy(self.contract)
        value["upstream"]["artifact_only_entries"].pop()
        with self.assertRaises(ContractError):
            validate_contract(value)

    def test_endpoint_mutation_fails(self) -> None:
        value = deepcopy(self.contract)
        value["endpoint"]["best_y_decimal"] = "0"
        with self.assertRaises(ContractError):
            validate_contract(value)

    def test_full_download_permission_fails(self) -> None:
        value = deepcopy(self.contract)
        value["verification_execution"]["full_raw_archive_download_forbidden"] = False
        with self.assertRaises(ContractError):
            validate_contract(value)

    def test_oversized_range_cap_fails(self) -> None:
        value = deepcopy(self.contract)
        value["verification_execution"]["maximum_raw_archive_bytes_per_request"] = 8_000_001
        with self.assertRaises(ContractError):
            validate_contract(value)

    def test_duplicate_code_member_fails(self) -> None:
        value = deepcopy(self.contract)
        value["required_code_members"][1]["path"] = value["required_code_members"][0]["path"]
        with self.assertRaises(ContractError):
            validate_contract(value)

    def test_unsafe_raw_path_fails(self) -> None:
        value = deepcopy(self.contract)
        value["raw_members"]["json"]["path"] = "../target.json"
        with self.assertRaises(ContractError):
            validate_contract(value)

    def test_duplicate_json_key_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "contract.json"
            path.write_text('{"candidate_id":"EU26-12","candidate_id":"x"}', encoding="utf-8")
            with self.assertRaises(ContractError):
                load_contract(path)

    def test_non_object_contract_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "contract.json"
            path.write_text("[]", encoding="utf-8")
            with self.assertRaises(ContractError):
                load_contract(path)

    def test_contract_is_valid_json(self) -> None:
        self.assertIsInstance(json.loads(CONTRACT_PATH.read_text(encoding="utf-8")), dict)


if __name__ == "__main__":
    unittest.main()
