from __future__ import annotations

import hashlib
import tempfile
import unittest
from pathlib import Path

from eu2614.canonical import bind_report, write_new_json
from eu2614.contract import CONTRACT_PATH, CONTRACT_SHA256, load_contract
from eu2614.errors import VerificationError


class ContractAndOutputTests(unittest.TestCase):
    def test_claim_ceiling_is_immutable(self) -> None:
        contract = load_contract()
        self.assertEqual(contract["status"], "TARGETED_ARTIFACT_REPLAY_ONLY")
        self.assertEqual(contract["paper_mapping"], "PAPER_CONTEXT_ONLY")
        self.assertEqual(contract["execution"]["source_native"], "NOT_ATTEMPTED_OUT_OF_SCOPE")
        self.assertIn("PASS_FULL", contract["forbidden_claims"])

    def test_contract_bytes_are_frozen(self) -> None:
        self.assertEqual(hashlib.sha256(CONTRACT_PATH.read_bytes()).hexdigest(), CONTRACT_SHA256)

    def test_contract_rejects_any_frozen_constant_drift(self) -> None:
        original = CONTRACT_PATH.read_bytes()
        mutations = (
            (
                "endpoint",
                b'"nfev_total": 2893419',
                b'"nfev_total": 1',
            ),
            (
                "archive-hash",
                b'"sha256": "22c0468ce1d01e03c30826abcd0952942a5d03d7822c0cc509897c6f7a40540e"',
                b'"sha256": "0000000000000000000000000000000000000000000000000000000000000000"',
            ),
            (
                "conflict",
                b"Paper/README remaining-budget wording conflicts",
                b"Paper/README remaining-budget wording conceals ",
            ),
        )
        with tempfile.TemporaryDirectory() as directory:
            exact_copy = Path(directory) / "exact-copy.json"
            exact_copy.write_bytes(original)
            self.assertEqual(load_contract(exact_copy)["candidate_id"], "EU26-14")
            for label, before, after in mutations:
                with self.subTest(label=label):
                    self.assertEqual(original.count(before), 1)
                    path = Path(directory) / f"{label}.json"
                    path.write_bytes(original.replace(before, after, 1))
                    with self.assertRaisesRegex(VerificationError, "byte identity"):
                        load_contract(path)

    def test_pull_request_ci_requires_the_complete_artifact(self) -> None:
        workflow = (
            CONTRACT_PATH.parents[3] / ".github" / "workflows" / "eu26-14-validation.yml"
        ).read_text(encoding="utf-8")
        self.assertIn("pull_request:", workflow)
        self.assertIn("registry-gates:", workflow)
        full_job = workflow.split("\n  full-artifact:\n", 1)[1]
        self.assertIn("needs: [registry-gates, python-unit, octave-controls]", full_job)
        self.assertNotIn("github.event_name == 'workflow_dispatch'", full_job)
        self.assertIn("python-version: \"3.13.5\"", full_job)
        self.assertIn("--max-filesize 318000000", full_job)
        self.assertIn("--require-full-artifact", full_job)

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

    def test_report_write_rejects_symlinked_parent(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            real_parent = root / "real"
            linked_parent = root / "linked"
            real_parent.mkdir()
            linked_parent.symlink_to(real_parent, target_is_directory=True)
            with self.assertRaises(VerificationError):
                write_new_json(linked_parent / "report.json", {"gate": "TEST"})
            self.assertFalse((real_parent / "report.json").exists())


if __name__ == "__main__":
    unittest.main()
