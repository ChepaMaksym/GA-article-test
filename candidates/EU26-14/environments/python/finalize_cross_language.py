#!/usr/bin/env python3
"""Bind an Octave fixture audit to the authenticated Python artifact report."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


PYTHON_ENV = Path(__file__).resolve().parent
sys.path.insert(0, str(PYTHON_ENV))

from eu2614.canonical import bind_report, write_new_json  # noqa: E402
from eu2614.contract import load_contract  # noqa: E402
from eu2614.errors import VerificationError  # noqa: E402


def _object(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise VerificationError(f"cannot read report {path}: {error}") from error
    if not isinstance(value, dict):
        raise VerificationError(f"report {path} must be an object")
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
    if python_report.get("overall_gate") != "PASS_TARGETED_ARTIFACT_REPLAY":
        raise VerificationError("Python targeted artifact gate did not pass")
    if python_report.get("status") != contract["status"]:
        raise VerificationError("Python report claim ceiling differs")
    if python_report.get("paper_mapping") != contract["paper_mapping"]:
        raise VerificationError("Python paper mapping differs")
    if python_report.get("source_native_gate") != "NOT_ATTEMPTED_OUT_OF_SCOPE":
        raise VerificationError("Python source-native boundary differs")
    expected_octave = {
        "candidate_id": "EU26-14",
        "status": "TARGETED_ARTIFACT_REPLAY_ONLY",
        "paper_mapping": "PAPER_CONTEXT_ONLY",
        "cross_language_gate": "PASS_CROSS_LANGUAGE_CONTROLS",
        "seed_count": 51,
        "cycle_count": 30,
        "reused_cycle_count": 15,
        "zero_eval_reused_cycle_count": 1,
        "final_cycle_nfev": 2876679,
        "run0_nfev_total": 2893419,
        "unspent_evaluations": 106581,
    }
    for field, expected in expected_octave.items():
        if octave_report.get(field) != expected:
            raise VerificationError(f"Octave report field differs: {field}")
    report = bind_report(
        {
            "schema_version": "1.0.0",
            "candidate_id": "EU26-14",
            "status": "TARGETED_ARTIFACT_REPLAY_ONLY",
            "paper_mapping": "PAPER_CONTEXT_ONLY",
            "cross_language_gate": "PASS_CROSS_LANGUAGE_CONTROLS",
            "python_report_digest": python_report.get("report_digest"),
            "octave_assertions": octave_report.get("assertions"),
            "seed_count": 51,
            "cycle_count": 30,
            "run0_nfev_total": 2893419,
            "unspent_evaluations": 106581,
            "source_native_gate": "NOT_ATTEMPTED_OUT_OF_SCOPE",
            "forbidden_claims": contract["forbidden_claims"],
        },
        domain=b"EU26-14-CROSS-LANGUAGE-REPORT-V1",
    )
    write_new_json(args.output, report)
    print(report["cross_language_gate"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
