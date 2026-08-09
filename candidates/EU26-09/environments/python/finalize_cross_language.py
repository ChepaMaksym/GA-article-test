#!/usr/bin/env python3
"""Bind independent MATLAB/Octave output to authenticated Python evidence."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


PYTHON_ENV = Path(__file__).resolve().parent
sys.path.insert(0, str(PYTHON_ENV))

from eu2609.canonical import bind_report, write_new_json  # noqa: E402
from eu2609.contract import load_contract  # noqa: E402


def _object(path: Path) -> dict:
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
        raise SystemExit("Python artifact report did not pass")
    if octave_report.get("status") != "PASS_MATLAB_OCTAVE_INDEPENDENT":
        raise SystemExit("MATLAB/Octave report did not pass")
    if python_report.get("paper_mapping") != "PAPER_FIGURE_CONTEXT_ONLY":
        raise SystemExit("Python report lost the paper mapping boundary")
    if octave_report.get("paper_mapping") != "PAPER_FIGURE_CONTEXT_ONLY":
        raise SystemExit("MATLAB/Octave report lost the paper mapping boundary")
    expected_totals = contract["endpoint"]["raw_totals"]
    expected_means = contract["endpoint"]["raw_means"]
    if python_report.get("artifact", {}).get("totals") != expected_totals:
        raise SystemExit("Python totals differ from contract")
    if octave_report.get("totals") != expected_totals:
        raise SystemExit("MATLAB/Octave totals differ from contract")
    if python_report.get("artifact", {}).get("means") != expected_means:
        raise SystemExit("Python means differ from contract")
    if octave_report.get("means") != expected_means:
        raise SystemExit("MATLAB/Octave means differ from contract")
    if (
        octave_report.get("source_half_integer_count") != 2
        or octave_report.get("paper_half_integer_count") != 3
    ):
        raise SystemExit("MATLAB/Octave paper/source conflict fixture differs")
    if not set(contract["forbidden_claims"]).issubset(octave_report.get("forbidden_claims", [])):
        raise SystemExit("MATLAB/Octave report lost a forbidden claim")

    report = bind_report(
        {
            "schema_version": "1.0.0",
            "candidate_id": "EU26-09",
            "status": "TARGETED_ARTIFACT_REPLAY",
            "paper_mapping": "PAPER_FIGURE_CONTEXT_ONLY",
            "cross_language_gate": "PASS_CROSS_LANGUAGE",
            "totals": expected_totals,
            "means": expected_means,
            "source_half_integer_count": 2,
            "paper_half_integer_count": 3,
            "octave_assertions": octave_report.get("assertions"),
            "python_report_digest": python_report.get("report_digest"),
            "forbidden_claims": contract["forbidden_claims"],
        },
        domain=b"EU26-09-CROSS-LANGUAGE-REPORT-V1",
    )
    write_new_json(args.output, report)
    print(report["cross_language_gate"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
