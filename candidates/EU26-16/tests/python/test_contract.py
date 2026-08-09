from __future__ import annotations

import copy
import json
import math
import tempfile
import unittest
from pathlib import Path

from eu2616.canonical import bind_report, canonical_bytes, write_new_json
from eu2616.contract import ContractError, load_contract, validate_contract

from support import CONTRACT


class ClaimBoundaryTests(unittest.TestCase):
    def test_status_is_formula_only(self) -> None:
        self.assertEqual(CONTRACT["status"], "FORMULA_AND_SOURCE_TRANSITION_VALIDATION_ONLY")

    def test_readiness_is_conditional_noneligible(self) -> None:
        self.assertEqual(CONTRACT["readiness"], "CONDITIONAL_NONELIGIBLE")

    def test_table_7_target_is_disabled(self) -> None:
        self.assertFalse(CONTRACT["paper_protocol"]["table_7_target_enabled"])

    def test_mandatory_claims_are_forbidden(self) -> None:
        self.assertTrue(
            {
                "PASS_FULL",
                "PASS_TABLE_7_REPLAY",
                "PASS_EMPIRICAL_REPRODUCTION",
                "DATASET_LICENSE_RESOLVED",
            }.issubset(CONTRACT["forbidden_claims"])
        )

    def test_no_global_bounds_claim(self) -> None:
        self.assertFalse(CONTRACT["transition"]["global_bounds_claim"])
        self.assertFalse(CONTRACT["transition"]["probability_clamp"])

    def test_contract_rejects_status_upgrade(self) -> None:
        changed = copy.deepcopy(CONTRACT)
        changed["status"] = "PASS_FULL"
        with self.assertRaises(ContractError):
            validate_contract(changed)

    def test_contract_rejects_missing_blocker(self) -> None:
        changed = copy.deepcopy(CONTRACT)
        changed["blockers"].remove("DATASET_LICENSE_UNRESOLVED")
        with self.assertRaises(ContractError):
            validate_contract(changed)

    def test_contract_rejects_clamp_invention(self) -> None:
        changed = copy.deepcopy(CONTRACT)
        changed["transition"]["probability_clamp"] = True
        with self.assertRaises(ContractError):
            validate_contract(changed)

    def test_contract_rejects_parent_member_path(self) -> None:
        changed = copy.deepcopy(CONTRACT)
        changed["required_members"][0]["path"] = "../LICENSE.md"
        with self.assertRaises(ContractError):
            validate_contract(changed)

    def test_loader_round_trip(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "contract.json"
            path.write_text(json.dumps(CONTRACT), encoding="utf-8")
            self.assertEqual(load_contract(path), CONTRACT)


class CanonicalReportTests(unittest.TestCase):
    def test_canonical_object_order_is_stable(self) -> None:
        self.assertEqual(canonical_bytes({"b": 2, "a": 1}), canonical_bytes({"a": 1, "b": 2}))

    def test_canonical_rejects_nonfinite(self) -> None:
        with self.assertRaises(ValueError):
            canonical_bytes({"value": math.inf})

    def test_report_digest_is_deterministic(self) -> None:
        self.assertEqual(bind_report({"value": 1}), bind_report({"value": 1}))

    def test_new_writer_refuses_overwrite(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "report.json"
            write_new_json(path, {"value": 1})
            with self.assertRaises(FileExistsError):
                write_new_json(path, {"value": 2})
            self.assertEqual(json.loads(path.read_text(encoding="ascii")), {"value": 1})


if __name__ == "__main__":
    unittest.main()
