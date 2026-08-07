#!/usr/bin/env python3
"""Validate independently bound Python and MATLAB/Octave fixture reports."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys
from typing import Any


SCRIPT = Path(__file__).resolve()
CANDIDATE = SCRIPT.parents[1]
REPOSITORY = CANDIDATE.parents[1]
sys.path.insert(0, str(CANDIDATE / "environments" / "python"))

from eu2605.canonical import (  # noqa: E402
    canonical_bytes,
    sha256_value,
    strict_json_load,
)
from eu2605.core import (  # noqa: E402
    H0_SOURCE_STATUS,
    SOURCE_BYTE_STATUS,
    SOURCE_FREEZE_STATUS,
    fixture_report,
)
from eu2605.reporting import (  # noqa: E402
    exclusive_write_bytes,
    git_head,
    matlab_implementation_paths,
    python_implementation_paths,
    prepare_exclusive_outputs,
    source_digest,
    source_hash_rows,
)


REPORT_KIND = "EU26-05-INDEPENDENT-FIXTURE-v1"
SEMANTIC_DIGEST = "6f560ccd36492e9fb1c4057d67ea2e54fffa032e72ddd02557bad077aacaf502"
ENVELOPE_KEYS = {
    "schema_version",
    "report_kind",
    "implementation",
    "git_head",
    "runtime",
    "implementation_source_hashes",
    "implementation_source_digest",
    "execution_authentication",
    "h0_source_status",
    "source_byte_status",
    "source_freeze_status",
    "semantic_payload",
    "semantic_payload_sha256",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("python_report", type=Path)
    parser.add_argument("matlab_report", type=Path)
    parser.add_argument("--output", type=Path)
    return parser.parse_args()


def _require_exact_keys(value: Any, expected: set[str], label: str) -> None:
    if not isinstance(value, dict) or set(value) != expected:
        missing = sorted(expected - set(value)) if isinstance(value, dict) else sorted(expected)
        extra = sorted(set(value) - expected) if isinstance(value, dict) else []
        raise ValueError(f"{label} schema is not exact; missing={missing}, extra={extra}")


def _expected_rows(implementation: str) -> list[dict[str, str]]:
    if implementation == "python":
        paths = python_implementation_paths(CANDIDATE)
    elif implementation == "matlab_octave":
        paths = matlab_implementation_paths(CANDIDATE)
    else:
        raise ValueError(f"unsupported implementation: {implementation}")
    return source_hash_rows(paths, REPOSITORY)


def validate_implementation_report(report: dict[str, Any], implementation: str) -> None:
    _require_exact_keys(report, ENVELOPE_KEYS, f"{implementation} envelope")
    if (
        report.get("schema_version") != "1.0.0"
        or report.get("report_kind") != REPORT_KIND
        or report.get("implementation") != implementation
    ):
        raise ValueError(f"{implementation} report identity is invalid")
    if report.get("execution_authentication") != "SELF_ASSERTED_RUNTIME_CONTEXT_ONLY":
        raise ValueError(f"{implementation} execution context was overstated")
    if report.get("git_head") != git_head(REPOSITORY):
        raise ValueError(f"{implementation} report git HEAD differs from the checkout")
    if (
        report.get("h0_source_status") != H0_SOURCE_STATUS
        or report.get("source_byte_status") != SOURCE_BYTE_STATUS
        or report.get("source_freeze_status") != SOURCE_FREEZE_STATUS
    ):
        raise ValueError(f"{implementation} report changed the source-byte blocker")

    runtime = report.get("runtime")
    _require_exact_keys(runtime, {"engine", "version", "platform"}, f"{implementation} runtime")
    if not isinstance(runtime.get("version"), str) or not runtime["version"]:
        raise ValueError(f"{implementation} runtime version is missing")
    if not isinstance(runtime.get("platform"), str) or not runtime["platform"]:
        raise ValueError(f"{implementation} runtime platform is missing")
    expected_engines = {"python"} if implementation == "python" else {"matlab", "octave"}
    if runtime.get("engine") not in expected_engines:
        raise ValueError(f"{implementation} runtime engine is not independent")

    expected_rows = _expected_rows(implementation)
    rows = report.get("implementation_source_hashes")
    if rows != expected_rows:
        raise ValueError(f"{implementation} implementation source hashes differ")
    if not isinstance(rows, list) or any(
        not isinstance(row, dict)
        or set(row) != {"path", "sha256"}
        or not isinstance(row["path"], str)
        or not isinstance(row["sha256"], str)
        for row in rows
    ):
        raise ValueError(f"{implementation} source row schema is not exact")
    if report.get("implementation_source_digest") != source_digest(expected_rows):
        raise ValueError(f"{implementation} implementation source digest differs")

    fixture = strict_json_load(CANDIDATE / "fixtures" / "formula_transition_cases.json")
    expected_payload = fixture_report(fixture)
    if report.get("semantic_payload") != expected_payload:
        raise ValueError(f"{implementation} semantic fixture payload differs")
    digest = sha256_value(expected_payload)
    if digest != SEMANTIC_DIGEST or report.get("semantic_payload_sha256") != digest:
        raise ValueError(f"{implementation} semantic fixture digest differs")


def compare_reports(
    python_report: dict[str, Any], matlab_report: dict[str, Any]
) -> dict[str, Any]:
    validate_implementation_report(python_report, "python")
    validate_implementation_report(matlab_report, "matlab_octave")
    if python_report["semantic_payload"] != matlab_report["semantic_payload"]:
        raise ValueError("Python and MATLAB/Octave semantic payloads differ")
    if python_report["semantic_payload_sha256"] != matlab_report["semantic_payload_sha256"]:
        raise ValueError("Python and MATLAB/Octave semantic digests differ")
    if python_report["implementation_source_digest"] == matlab_report["implementation_source_digest"]:
        raise ValueError("independent implementations unexpectedly share a source digest")
    return {
        "schema_version": "1.0.0",
        "status": "PASS_H3_PAYLOAD_FORMULA_EQUIVALENCE_ONLY",
        "native_runtime_execution_status": (
            "NOT_EVALUATED_EXTERNAL_EXECUTION_AUTH_REQUIRED"
        ),
        "offline_comparison_authorizes_native_execution": False,
        "git_head": python_report["git_head"],
        "h0_source_status": H0_SOURCE_STATUS,
        "source_byte_status": SOURCE_BYTE_STATUS,
        "source_freeze_status": SOURCE_FREEZE_STATUS,
        "semantic_payload_sha256": SEMANTIC_DIGEST,
        "python_source_digest": python_report["implementation_source_digest"],
        "matlab_octave_source_digest": matlab_report["implementation_source_digest"],
        "matlab_octave_runtime": matlab_report["runtime"],
        "published_27_of_30_evaluated": False,
        "pass_full_claimed": False,
    }


def main() -> None:
    args = parse_args()
    python_value = strict_json_load(args.python_report)
    matlab_value = strict_json_load(args.matlab_report)
    try:
        summary = compare_reports(python_value, matlab_value)
    except (KeyError, TypeError, ValueError) as error:
        raise SystemExit(f"EU26-05 cross-language comparison failed: {error}") from error
    if args.output:
        (output_path,) = prepare_exclusive_outputs(
            [args.output], REPOSITORY, labels=["fixture-comparison output"]
        )
        exclusive_write_bytes(output_path, canonical_bytes(summary) + b"\n")
    print("EU26-05 CROSS-LANGUAGE PAYLOAD EQUIVALENCE PASS; NATIVE EXECUTION NOT AUTHENTICATED")


if __name__ == "__main__":
    main()
