from __future__ import annotations

import copy
import csv
import unittest

from eu2615.contract import (
    CONTRACT_SHA256,
    FIXTURE_SHA256,
    SOURCE_MANIFEST_PATH,
    SOURCE_MANIFEST_SHA256,
    ContractError,
    load_contract,
    load_fixtures,
    sha256_file,
    validate_contract,
)


class ContractTests(unittest.TestCase):
    def test_bound_files_and_claim_boundary(self):
        contract = load_contract()
        fixture = load_fixtures()
        self.assertEqual(CONTRACT_SHA256, "be6a54889ae28febd2c71de64316794b58500483d8b322a11142140a534f2114")
        self.assertEqual(FIXTURE_SHA256, "5d4d49ab993184bfb9f335cd62154d0ad41f2f2e27e7c76fb6fea76d5049ecb0")
        self.assertEqual(sha256_file(SOURCE_MANIFEST_PATH), SOURCE_MANIFEST_SHA256)
        self.assertEqual(contract["candidate_status"], "CONDITIONAL_NONELIGIBLE")
        self.assertFalse(contract["pass_full"])
        self.assertIn("PASS_FULL", contract["claim_boundary"]["forbidden"])
        self.assertEqual(fixture["candidate_id"], "EU26-15")

    def test_exact_source_manifest_inventory(self):
        with SOURCE_MANIFEST_PATH.open(newline="", encoding="utf-8") as handle:
            rows = list(csv.DictReader(handle))
        self.assertEqual(len(rows), 8)
        licensed = {
            row["path"]: row
            for row in rows
            if row["role"] in {"licensed-source", "license-text"}
        }
        self.assertEqual(
            licensed["GARBO.py"]["sha256"],
            "1ef92bbcf1ae66a0996a7aa7c56d7b057a50de9b0d4a7cbdfc9b25c724b63a67",
        )
        self.assertEqual(
            licensed["runGARBO.py"]["sha256"],
            "0cda6df4129a0e56d251a349c74b6556df6e1dadd90726ac1c8bc50e9e356469",
        )
        self.assertEqual(
            licensed["LICENSE"]["sha256"],
            "3972dc9744f6499f0f9b2dbf76696f2ae7ad8af9b23dde66d6af86c9dfb36986",
        )

    def test_status_promotion_is_rejected(self):
        contract = copy.deepcopy(load_contract())
        contract["candidate_status"] = "HARD_PASS"
        contract["pass_full"] = True
        with self.assertRaises(ContractError):
            validate_contract(contract)

    def test_intft_correction_is_rejected(self):
        contract = copy.deepcopy(load_contract())
        contract["source_quirks"]["mutation_antecedent"] = "intFT(ft_input)"
        with self.assertRaises(ContractError):
            validate_contract(contract)

    def test_dataset_license_promotion_is_rejected(self):
        contract = copy.deepcopy(load_contract())
        contract["applied_dimension"]["dataset_license_status"] = "LICENSED"
        with self.assertRaises(ContractError):
            validate_contract(contract)


if __name__ == "__main__":
    unittest.main()
