#!/usr/bin/env python3
"""Bind independent MATLAB/Octave controls to authenticated Python evidence."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


PYTHON_ENV = Path(__file__).resolve().parent
sys.path.insert(0, str(PYTHON_ENV))

from eu2612.canonical import bind_report, write_new_json  # noqa: E402
from eu2612.contract import load_contract  # noqa: E402
from eu2612.controls import fixture_report  # noqa: E402


def _object(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise SystemExit(f"cannot read report {path}: {error}") from error
    if not isinstance(value, dict):
        raise SystemExit(f"report {path} must be a JSON object")
    return value


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--python-report", required=True, type=Path)
    parser.add_argument("--octave-report", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if args.output.exists() or args.output.is_symlink():
        parser.error("--output must be a new path")
    contract = load_contract()
    python_report = _object(args.python_report)
    octave_report = _object(args.octave_report)
    if python_report.get("artifact_gate") != "PASS_ARTIFACT_ENDPOINT":
        raise SystemExit("Python artifact endpoint did not pass")
    if python_report.get("status") != "TARGETED_ARTIFACT_REPLAY_ONLY":
        raise SystemExit("Python report lost the claim ceiling")
    if octave_report.get("status") != "PASS_MATLAB_OCTAVE_INDEPENDENT_CONTROLS":
        raise SystemExit("MATLAB/Octave controls did not pass")
    if octave_report.get("candidate_id") != "EU26-12":
        raise SystemExit("MATLAB/Octave candidate identity differs")
    if octave_report.get("paper_mapping") != contract["paper_mapping"]:
        raise SystemExit("MATLAB/Octave paper mapping differs")
    expected_controls = fixture_report(contract)
    if python_report.get("control_fixtures") != expected_controls:
        raise SystemExit("Python control fixtures differ from contract")
    if octave_report.get("control_fixtures") != expected_controls:
        raise SystemExit("MATLAB/Octave control fixtures differ from Python")
    if not set(contract["forbidden_claims"]).issubset(octave_report.get("forbidden_claims", [])):
        raise SystemExit("MATLAB/Octave report lost a forbidden claim")
    report = bind_report(
        {
            "schema_version": "1.0.0",
            "candidate_id": "EU26-12",
            "status": "TARGETED_ARTIFACT_REPLAY_ONLY",
            "paper_mapping": contract["paper_mapping"],
            "cross_language_gate": "PASS_CROSS_LANGUAGE",
            "control_fixtures": expected_controls,
            "octave_assertions": octave_report.get("assertions"),
            "python_report_digest": python_report.get("report_digest"),
            "forbidden_claims": contract["forbidden_claims"],
        },
        domain=b"EU26-12-CROSS-LANGUAGE-REPORT-V1",
    )
    write_new_json(args.output, report)
    print(report["cross_language_gate"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
