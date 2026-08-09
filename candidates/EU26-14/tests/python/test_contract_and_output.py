from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from eu2614.canonical import bind_report, write_new_json
from eu2614.contract import load_contract
from eu2614.errors import VerificationError


class ContractAndOutputTests(unittest.TestCase):
    def test_claim_ceiling_is_immutable(self) -> None:
        contract = load_contract()
        self.assertEqual(contract["status"], "TARGETED_ARTIFACT_REPLAY_ONLY")
        self.assertEqual(contract["paper_mapping"], "PAPER_CONTEXT_ONLY")
        self.assertEqual(contract["execution"]["source_native"], "NOT_ATTEMPTED_OUT_OF_SCOPE")
        self.assertIn("PASS_FULL", contract["forbidden_claims"])

    def test_report_write_is_create_only(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "report.json"
            report = bind_report({"gate": "TEST"}, domain=b"TEST")
            write_new_json(output, report)
            first = output.read_bytes()
            with self.assertRaises(VerificationError):
                write_new_json(output, report)
            self.assertEqual(output.read_bytes(), first)

    def test_report_write_rejects_symlink_even_if_target_is_absent(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            output = root / "report.json"
            target = root / "missing-target.json"
            output.symlink_to(target)
            with self.assertRaises(VerificationError):
                write_new_json(output, {"gate": "TEST"})
            self.assertFalse(target.exists())


if __name__ == "__main__":
    unittest.main()
