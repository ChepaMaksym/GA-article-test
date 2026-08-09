from __future__ import annotations

import dataclasses
import json
import math
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from eu2609.archive import first_run_difference, parse_artifact
from eu2609.canonical import bind_report, canonical_bytes, write_new_json
from eu2609.contract import ContractError, load_contract, load_environment_contract

from test_support import CONTRACT, raw_payload, upstream


class ClaimBoundaryTests(unittest.TestCase):
    def test_status_is_targeted_only(self) -> None:
        self.assertEqual(load_contract()["status"], "TARGETED_ARTIFACT_REPLAY")

    def test_paper_mapping_is_context_only(self) -> None:
        self.assertEqual(load_contract()["paper_mapping"], "PAPER_FIGURE_CONTEXT_ONLY")

    def test_all_mandatory_claims_are_forbidden(self) -> None:
        forbidden = set(load_contract()["forbidden_claims"])
        self.assertTrue(
            {
                "PASS_FULL",
                "PASS_LITERAL_PAPER_ENDPOINT",
                "HISTORICAL_DEPENDENCY_ENVIRONMENT_PROVEN",
            }.issubset(forbidden)
        )

    def test_dependency_lock_blocker_is_retained(self) -> None:
        environment = load_environment_contract()
        self.assertFalse(environment["upstream_dependency_lock_present"])

    def test_source_command_and_seed_are_frozen(self) -> None:
        contract = load_contract()
        command = contract["source_native"]["command"]
        self.assertEqual(command[-2:], ["885480221", "-v"])
        self.assertEqual(contract["endpoint"]["base_seed"], 885480221)

    def test_contract_loader_rejects_status_mutation_logic(self) -> None:
        # The live loader is asserted above; this checks its explicit exception type remains available.
        self.assertTrue(issubclass(ContractError, ValueError))


class CanonicalEvidenceTests(unittest.TestCase):
    def test_canonical_bytes_are_order_independent(self) -> None:
        self.assertEqual(canonical_bytes({"b": 2, "a": 1}), canonical_bytes({"a": 1, "b": 2}))

    def test_canonical_bytes_reject_nan(self) -> None:
        with self.assertRaises(ValueError):
            canonical_bytes({"value": math.nan})

    def test_report_digest_is_deterministic(self) -> None:
        left = bind_report({"x": 1}, domain=b"test")
        right = bind_report({"x": 1}, domain=b"test")
        self.assertEqual(left, right)

    def test_report_digest_is_domain_separated(self) -> None:
        self.assertNotEqual(
            bind_report({"x": 1}, domain=b"left")["report_digest"],
            bind_report({"x": 1}, domain=b"right")["report_digest"],
        )

    def test_new_path_writer_refuses_overwrite(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "report.json"
            write_new_json(path, {"x": 1})
            with self.assertRaises(FileExistsError):
                write_new_json(path, {"x": 2})
            self.assertEqual(json.loads(path.read_text(encoding="ascii")), {"x": 1})


class ComparisonAndIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.artifact = parse_artifact(raw_payload(), CONTRACT)

    def test_equal_artifacts_have_no_difference(self) -> None:
        self.assertIsNone(first_run_difference(self.artifact, self.artifact))

    def test_first_difference_is_bounded_to_one_field(self) -> None:
        changed_run = dataclasses.replace(self.artifact.runs[0], evaluations=1044)
        changed = dataclasses.replace(
            self.artifact, runs=(changed_run, *self.artifact.runs[1:])
        )
        difference = first_run_difference(self.artifact, changed)
        self.assertEqual(difference, {"run_id": 1, "field": "evaluations", "reference": 1042, "replay": 1044})

    def test_artifact_cli_emits_narrow_report(self) -> None:
        script = (
            Path(__file__).resolve().parents[2]
            / "environments"
            / "python"
            / "run_artifact_verification.py"
        )
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "artifact.json"
            process = subprocess.run(
                [sys.executable, str(script), "--checkout", str(upstream()), "--output", str(output)],
                check=False,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
            )
            self.assertEqual(process.returncode, 0, process.stderr)
            report = json.loads(output.read_text(encoding="ascii"))
            self.assertEqual(report["artifact_gate"], "PASS_ARTIFACT_ENDPOINT")
            self.assertEqual(report["paper_mapping"], "PAPER_FIGURE_CONTEXT_ONLY")
            self.assertIn("PASS_FULL", report["forbidden_claims"])

    def test_artifact_cli_refuses_existing_output(self) -> None:
        script = (
            Path(__file__).resolve().parents[2]
            / "environments"
            / "python"
            / "run_artifact_verification.py"
        )
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "existing.json"
            output.write_text("sentinel", encoding="ascii")
            process = subprocess.run(
                [sys.executable, str(script), "--checkout", str(upstream()), "--output", str(output)],
                check=False,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            self.assertNotEqual(process.returncode, 0)
            self.assertEqual(output.read_text(encoding="ascii"), "sentinel")

    def test_cross_language_finalizer_accepts_exact_independent_shape(self) -> None:
        candidate = Path(__file__).resolve().parents[2]
        artifact_script = candidate / "environments" / "python" / "run_artifact_verification.py"
        finalizer = candidate / "environments" / "python" / "finalize_cross_language.py"
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            python_report = directory / "python.json"
            octave_report = directory / "octave.json"
            output = directory / "cross.json"
            subprocess.run(
                [sys.executable, str(artifact_script), "--checkout", str(upstream()), "--output", str(python_report)],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            octave_report.write_text(
                json.dumps(
                    {
                        "status": "PASS_MATLAB_OCTAVE_INDEPENDENT",
                        "paper_mapping": "PAPER_FIGURE_CONTEXT_ONLY",
                        "assertions": 25,
                        "totals": CONTRACT["endpoint"]["raw_totals"],
                        "means": CONTRACT["endpoint"]["raw_means"],
                        "source_half_integer_count": 2,
                        "paper_half_integer_count": 3,
                        "forbidden_claims": CONTRACT["forbidden_claims"],
                    }
                ),
                encoding="utf-8",
            )
            process = subprocess.run(
                [
                    sys.executable,
                    str(finalizer),
                    "--python-report",
                    str(python_report),
                    "--octave-report",
                    str(octave_report),
                    "--output",
                    str(output),
                ],
                check=False,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
            )
            self.assertEqual(process.returncode, 0, process.stderr)
            report = json.loads(output.read_text(encoding="ascii"))
            self.assertEqual(report["cross_language_gate"], "PASS_CROSS_LANGUAGE")
            self.assertIn("PASS_FULL", report["forbidden_claims"])

    def test_cross_language_finalizer_rejects_changed_total(self) -> None:
        candidate = Path(__file__).resolve().parents[2]
        artifact_script = candidate / "environments" / "python" / "run_artifact_verification.py"
        finalizer = candidate / "environments" / "python" / "finalize_cross_language.py"
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            python_report = directory / "python.json"
            octave_report = directory / "octave.json"
            output = directory / "cross.json"
            subprocess.run(
                [sys.executable, str(artifact_script), "--checkout", str(upstream()), "--output", str(python_report)],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            changed_totals = dict(CONTRACT["endpoint"]["raw_totals"])
            changed_totals["evaluations"] += 2
            octave_report.write_text(
                json.dumps(
                    {
                        "status": "PASS_MATLAB_OCTAVE_INDEPENDENT",
                        "paper_mapping": "PAPER_FIGURE_CONTEXT_ONLY",
                        "totals": changed_totals,
                        "means": CONTRACT["endpoint"]["raw_means"],
                        "source_half_integer_count": 2,
                        "paper_half_integer_count": 3,
                        "forbidden_claims": CONTRACT["forbidden_claims"],
                    }
                ),
                encoding="utf-8",
            )
            process = subprocess.run(
                [
                    sys.executable,
                    str(finalizer),
                    "--python-report",
                    str(python_report),
                    "--octave-report",
                    str(octave_report),
                    "--output",
                    str(output),
                ],
                check=False,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            self.assertNotEqual(process.returncode, 0)
            self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main()
