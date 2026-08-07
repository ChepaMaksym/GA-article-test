from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
from argparse import Namespace
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock


CANDIDATE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(CANDIDATE / "environments" / "python"))

from banditverify.canonical import canonical_json, sha256_file  # noqa: E402
from banditverify.cases import execute_case, load_matrix  # noqa: E402
from banditverify.matlab_report import (  # noqa: E402
    canonical_matlab_payload,
    payload_sha256,
)
from banditverify.provenance import (  # noqa: E402
    git_head,
    matlab_source_hashes,
    repository_root,
    source_hashes,
)
from banditverify.security import EvidenceValidationError, strict_json_load  # noqa: E402


RUNNER = CANDIDATE / "tests" / "hardware" / "run_portability_suite.py"
SPEC = importlib.util.spec_from_file_location("usa2604_runner", RUNNER)
assert SPEC and SPEC.loader
runner = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = runner
SPEC.loader.exec_module(runner)


def _serial_records() -> list[dict]:
    matrix = load_matrix(CANDIDATE / "config" / "hardware_formula_matrix.csv")
    return [execute_case(case, CANDIDATE) for case in matrix]


def _valid_report(head: str, payload: dict) -> dict:
    payload = copy.deepcopy(payload)
    sources = matlab_source_hashes(CANDIDATE)
    return {
        "schema_version": "USA26-04-MATLAB-H2-REPORT-v1",
        "protocol_id": "USA26-04-FORMULA-PORTABILITY-v1",
        "git_sha": head,
        "implementation": "matlab_octave_clean_room",
        "engine": {"name": "GNU Octave", "version": "9.1.0"},
        "matlab_sources": [
            {"path": name, "sha256": digest} for name, digest in sorted(sources.items())
        ],
        "fixture_path": "fixtures/fixed_controller_tape.json",
        "fixture_sha256": sha256_file(CANDIDATE / "fixtures" / "fixed_controller_tape.json"),
        "payload": payload,
        "canonical_payload": canonical_matlab_payload(payload),
        "canonical_payload_sha256": payload_sha256(payload),
    }


class StrictJsonTests(unittest.TestCase):
    def _load_text(self, text: str):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "evidence.json"
            path.write_text(text, encoding="utf-8")
            return strict_json_load(path)

    def test_duplicate_keys_nan_and_huge_numbers_are_rejected(self) -> None:
        attacks = (
            '{"a":1,"a":2}',
            '{"a":NaN}',
            '{"a":Infinity}',
            '{"a":' + "9" * 129 + "}",
            '{"a":1e999}',
        )
        for attack in attacks:
            with self.subTest(attack=attack[:24]), self.assertRaises(
                EvidenceValidationError
            ):
                self._load_text(attack)

    def test_empty_and_oversized_files_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "empty.json"
            path.write_bytes(b"")
            with self.assertRaises(EvidenceValidationError):
                strict_json_load(path)
            path.write_bytes(b"{}" + b" " * 100)
            with self.assertRaises(EvidenceValidationError):
                strict_json_load(path, maximum_bytes=10)

    def test_formal_source_map_covers_workflow_registry_and_rules(self) -> None:
        paths = set(source_hashes(repository_root(CANDIDATE)))
        required = {
            "AGENTS.md",
            ".github/workflows/usa26-04-validation.yml",
            "candidates/USA26-04/tests/hardware/compare_portability_reports.py",
            "registry/cohort_2026_12/validate_registry.py",
            "registry/cohort_2026_12/gate_definitions.json",
            "registry/cohort_2026_12/tests/run_registry_tests.py",
        }
        self.assertTrue(required <= paths)


class MatlabEvidenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.records = _serial_records()
        cls.head = git_head(repository_root(CANDIDATE))
        cls.payload = next(
            row["result"]
            for row in cls.records
            if row["case_id"] == "controller-fixed-tape"
        )

    def _gate(self, report: dict) -> dict:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "matlab.json"
            path.write_text(
                json.dumps(report, sort_keys=True, allow_nan=False), encoding="utf-8"
            )
            return runner._matlab_fixed_tape_gate(
                path, self.records, self.head, trusted_origin=False
            )

    def test_exact_external_report_is_diagnostic_never_h2_pass(self) -> None:
        gate = self._gate(_valid_report(self.head, self.payload))
        self.assertEqual(
            gate["status"], "NOT_EVALUATED_UNAUTHENTICATED_EXTERNAL_MATLAB_REPORT"
        )
        self.assertEqual(gate["report_origin"], "EXTERNAL_UNAUTHENTICATED")
        self.assertIsNone(gate["engine_executable"])
        self.assertEqual(
            gate["matlab_report_canonical_sha256"],
            hashlib.sha256(canonical_json(gate["matlab_report"])).hexdigest(),
        )

    def test_minimal_copied_and_mutated_reports_are_rejected(self) -> None:
        attacks = []
        attacks.append({"payload": self.payload})
        copied = _valid_report(self.head, self.payload)
        copied["git_sha"] = "0" * 40
        attacks.append(copied)
        source = _valid_report(self.head, self.payload)
        source["matlab_sources"][0]["sha256"] = "0" * 64
        attacks.append(source)
        fixture = _valid_report(self.head, self.payload)
        fixture["fixture_sha256"] = "0" * 64
        attacks.append(fixture)
        payload = _valid_report(self.head, self.payload)
        payload["payload"]["state_provenance"] = "article_state"
        attacks.append(payload)
        extra = _valid_report(self.head, self.payload)
        extra["extra"] = True
        attacks.append(extra)
        for index, attack in enumerate(attacks):
            with self.subTest(index=index):
                self.assertEqual(
                    self._gate(attack)["status"],
                    "REJECTED_MALFORMED_OR_UNBOUND_MATLAB_REPORT",
                )

    def test_bound_but_mismatching_external_payload_stays_diagnostic(self) -> None:
        report = _valid_report(self.head, self.payload)
        report["payload"]["state_provenance"] = "article_state"
        report["canonical_payload"] = canonical_matlab_payload(report["payload"])
        report["canonical_payload_sha256"] = payload_sha256(report["payload"])
        gate = self._gate(report)
        self.assertEqual(
            gate["status"], "NOT_EVALUATED_UNAUTHENTICATED_EXTERNAL_MATLAB_REPORT"
        )
        self.assertIn("state_provenance", gate["exact_mismatches"])

    def test_fake_path_engine_is_rejected_before_execution(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            fake = Path(directory) / "octave"
            fake.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
            fake.chmod(0o755)
            with mock.patch.object(runner.shutil, "which", return_value=str(fake)):
                gate = runner._runner_generated_matlab_gate(
                    "octave", self.records, self.head
                )
        self.assertEqual(gate["status"], "REJECTED_UNTRUSTED_MATLAB_ENGINE_PATH")

    def test_artifact_collisions_and_repository_outputs_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            outside = Path(directory) / "profile.json"
            collisions = (
                Namespace(output=outside, hashes=outside, matlab_report=None),
                Namespace(
                    output=CANDIDATE / "results" / "profile.json",
                    hashes=Path(directory) / "hashes.tsv",
                    matlab_report=None,
                ),
                Namespace(output=outside, hashes=Path(directory) / "hashes.tsv", matlab_report=outside),
            )
            for args in collisions:
                with self.subTest(args=args), self.assertRaises(SystemExit):
                    runner._validate_artifact_paths(args)


if __name__ == "__main__":
    unittest.main()
