from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path

from eu2612.canonical import bind_report
from eu2612.contract import load_contract
from eu2612.controls import fixture_report
from eu2612.http_range import MemoryRangeReader
from eu2612.pipeline import verify_artifact_inputs
from eu2612.zip64 import Zip64Error
from test_support import make_zip64, synthetic_dat, synthetic_ioh_json, synthetic_record, tiny_code_contract


RUNNER_MARKERS = "\n".join(
    (
        "np.random.seed(seed)",
        "for iid in range(10):",
        "for seed in range(5):",
        "budget=50000",
        "'L-SHADE'",
        "'mutation_base':'target'",
        "'mutation_reference':'pbest'",
        "'lpsr':True",
        "'lambda_' : 18*dim",
        "'adaptation_method_F' :'shade'",
        "'adaptation_method_CR' : 'shade'",
    )
).encode()


def pipeline_fixture():
    contract = deepcopy(load_contract())
    endpoint_json = synthetic_ioh_json(contract)
    from eu2612.artifact import parse_endpoint

    endpoint = parse_endpoint(endpoint_json, contract)
    dat = synthetic_dat(endpoint.run_evaluations)
    json_path = contract["raw_members"]["json"]["path"]
    dat_path = contract["raw_members"]["dat"]["path"]
    raw_archive, raw_contract = make_zip64({json_path: endpoint_json, dat_path: dat})
    contract["zip64"] = raw_contract["zip64"]
    contract["raw_members"] = {
        "json": raw_contract["raw_members"][json_path],
        "dat": raw_contract["raw_members"][dat_path],
    }
    contract["zenodo_files"]["raw_data.zip"]["bytes"] = len(raw_archive)
    contract["zenodo_files"]["raw_data.zip"]["md5"] = hashlib.md5(raw_archive).hexdigest()

    code_archive, code_contract = tiny_code_contract(
        {"LICENCE": b"MIT License\npermission\n", "modde/core.py": b"x = 1\r\n"}
    )
    contract["zenodo_files"]["ModDE.zip"].update(code_contract["zenodo_files"]["ModDE.zip"])
    contract["required_code_members"] = code_contract["required_code_members"]
    contract["upstream"] = code_contract["upstream"]
    contract["zenodo_files"]["Common_DE_runner.py"].update(
        {
            "bytes": len(RUNNER_MARKERS),
            "md5": hashlib.md5(RUNNER_MARKERS).hexdigest(),
            "sha256": hashlib.sha256(RUNNER_MARKERS).hexdigest(),
        }
    )
    record = synthetic_record(contract)
    reader = MemoryRangeReader(raw_archive, maximum_request=len(raw_archive))
    return contract, record, code_archive, RUNNER_MARKERS, raw_archive, reader


class PipelineTests(unittest.TestCase):
    def test_complete_synthetic_pipeline_passes_narrowly(self) -> None:
        contract, record, code, runner, _archive, reader = pipeline_fixture()
        report = verify_artifact_inputs(
            contract=contract,
            zenodo_record=record,
            code_archive=code,
            runner=runner,
            raw_reader=reader,
        )
        self.assertEqual(report["artifact_gate"], "PASS_ARTIFACT_ENDPOINT")
        self.assertEqual(report["range_gate"], "PASS_RANGE_AUTHENTICATED_MEMBER")
        self.assertEqual(report["status"], "TARGETED_ARTIFACT_REPLAY_ONLY")
        self.assertIn("PASS_FULL", report["forbidden_claims"])
        self.assertFalse(report["dat_diagnostic"]["accepted_as_exact_endpoint"])

    def test_pipeline_rejects_mutated_archive(self) -> None:
        contract, record, code, runner, archive, _reader = pipeline_fixture()
        value = bytearray(archive)
        value[-1] ^= 1
        reader = MemoryRangeReader(bytes(value), maximum_request=len(value))
        with self.assertRaises(Zip64Error):
            verify_artifact_inputs(
                contract=contract,
                zenodo_record=record,
                code_archive=code,
                runner=runner,
                raw_reader=reader,
            )

    def test_pipeline_preserves_declared_only_md5(self) -> None:
        contract, record, code, runner, _archive, reader = pipeline_fixture()
        report = verify_artifact_inputs(
            contract=contract,
            zenodo_record=record,
            code_archive=code,
            runner=runner,
            raw_reader=reader,
        )
        self.assertEqual(report["zip64"]["full_archive_md5_status"], "ZENODO_DECLARED_NOT_RECOMPUTED")


class CrossLanguageProtocolTests(unittest.TestCase):
    def setUp(self) -> None:
        self.contract = load_contract()
        self.script = (
            Path(__file__).resolve().parents[2]
            / "environments"
            / "python"
            / "finalize_cross_language.py"
        )

    def _reports(self, root: Path) -> tuple[Path, Path, Path]:
        controls = fixture_report(self.contract)
        python_report = bind_report(
            {
                "artifact_gate": "PASS_ARTIFACT_ENDPOINT",
                "status": "TARGETED_ARTIFACT_REPLAY_ONLY",
                "control_fixtures": controls,
            },
            domain=b"TEST",
        )
        octave_report = {
            "candidate_id": "EU26-12",
            "status": "PASS_MATLAB_OCTAVE_INDEPENDENT_CONTROLS",
            "paper_mapping": self.contract["paper_mapping"],
            "control_fixtures": controls,
            "assertions": 33,
            "forbidden_claims": self.contract["forbidden_claims"],
        }
        python_path = root / "python.json"
        octave_path = root / "octave.json"
        output = root / "bound.json"
        python_path.write_text(json.dumps(python_report), encoding="utf-8")
        octave_path.write_text(json.dumps(octave_report), encoding="utf-8")
        return python_path, octave_path, output

    def _run(self, python_path: Path, octave_path: Path, output: Path):
        return subprocess.run(
            [
                sys.executable,
                str(self.script),
                "--python-report",
                str(python_path),
                "--octave-report",
                str(octave_path),
                "--output",
                str(output),
            ],
            text=True,
            capture_output=True,
            check=False,
            env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
        )

    def test_cross_language_binding_passes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            paths = self._reports(Path(temporary))
            completed = self._run(*paths)
            self.assertEqual(completed.returncode, 0, completed.stderr)
            report = json.loads(paths[2].read_text())
            self.assertEqual(report["cross_language_gate"], "PASS_CROSS_LANGUAGE")
            self.assertIn("PASS_FULL", report["forbidden_claims"])

    def test_octave_control_mutation_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            python_path, octave_path, output = self._reports(Path(temporary))
            report = json.loads(octave_path.read_text())
            report["control_fixtures"]["schedule"]["logged_evaluations"] = 50000
            octave_path.write_text(json.dumps(report), encoding="utf-8")
            completed = self._run(python_path, octave_path, output)
            self.assertNotEqual(completed.returncode, 0)
            self.assertFalse(output.exists())

    def test_octave_forbidden_claim_removal_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            python_path, octave_path, output = self._reports(Path(temporary))
            report = json.loads(octave_path.read_text())
            report["forbidden_claims"].remove("PASS_FULL")
            octave_path.write_text(json.dumps(report), encoding="utf-8")
            completed = self._run(python_path, octave_path, output)
            self.assertNotEqual(completed.returncode, 0)

    def test_existing_cross_language_output_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            python_path, octave_path, output = self._reports(Path(temporary))
            output.write_text("original", encoding="utf-8")
            completed = self._run(python_path, octave_path, output)
            self.assertNotEqual(completed.returncode, 0)
            self.assertEqual(output.read_text(), "original")


if __name__ == "__main__":
    unittest.main()
