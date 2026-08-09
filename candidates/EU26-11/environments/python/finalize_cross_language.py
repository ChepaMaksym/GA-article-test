#!/usr/bin/env python3
"""Bind an Octave formula result to an authenticated Python report."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

from eu2611.report import load_json, write_new_json


CANDIDATE = Path(__file__).resolve().parents[2]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--octave-raw", type=Path, required=True)
    parser.add_argument("--python-report", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    contract = load_json(CANDIDATE / "config" / "verification_contract.json")
    octave = load_json(args.octave_raw.resolve())
    python_report = load_json(args.python_report.resolve())
    if octave.get("candidate_id") != "EU26-11":
        raise ValueError("Octave report candidate identity mismatch")
    if python_report.get("candidate_id") != "EU26-11":
        raise ValueError("Python report candidate identity mismatch")
    if python_report.get("status") != "PASS_TARGET_ARTIFACT_REPLAY":
        raise ValueError("Python target report did not pass")
    octave_l2 = float(octave["l2_star"])
    octave_log10 = float(octave["log10_l2_star"])
    python_l2 = float(python_report["observed"]["l2_star"])
    python_log10 = float(python_report["observed"]["log10_l2_star"])
    if not all(math.isfinite(value) for value in (octave_l2, octave_log10)):
        raise ValueError("Octave report contains a non-finite value")
    tolerance = contract["endpoint"]["cross_language_l2_absolute_tolerance"]
    if abs(octave_l2 - python_l2) > tolerance:
        raise ValueError("Octave and Python L2-star values exceed tolerance")
    if octave.get("display_two_decimals") != contract["endpoint"]["paper_display"]:
        raise ValueError("Octave result does not reproduce the paper display")

    report = {
        "schema_version": "1.0.0",
        "candidate_id": "EU26-11",
        "status": "PASS_CROSS_LANGUAGE_FORMULA",
        "scope": contract["status"],
        "paper_level_status": contract["paper_level_status"],
        "forbidden_claims": contract["forbidden_claims"],
        "python_l2_star": python_l2,
        "octave_l2_star": octave_l2,
        "absolute_l2_difference": abs(octave_l2 - python_l2),
        "absolute_log10_difference": abs(octave_log10 - python_log10),
        "tolerance": tolerance,
        "python_report_digest": python_report["report_digest"],
    }
    digest_payload = json.dumps(
        report, allow_nan=False, ensure_ascii=True, separators=(",", ":"), sort_keys=True
    ).encode("ascii")
    report["report_digest"] = hashlib.sha256(
        b"EU26-11-CROSS-LANGUAGE-V1\0" + digest_payload
    ).hexdigest()
    write_new_json(args.output.resolve(), report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
