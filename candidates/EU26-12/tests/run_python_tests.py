#!/usr/bin/env python3
"""Run every fail-closed EU26-12 candidate-local Python test."""

from __future__ import annotations

import argparse
import hashlib
import sys
import unittest
from pathlib import Path


CANDIDATE = Path(__file__).resolve().parents[1]
PYTHON_ENV = CANDIDATE / "environments" / "python"
TESTS = Path(__file__).resolve().parent / "python"
sys.path.insert(0, str(PYTHON_ENV))
sys.path.insert(0, str(TESTS))

from eu2612.canonical import bind_report, write_new_json  # noqa: E402
from eu2612.contract import load_contract  # noqa: E402


def _suite_manifest() -> dict[str, object]:
    paths = sorted(
        [
            *PYTHON_ENV.rglob("*.py"),
            *TESTS.glob("test_*.py"),
            Path(__file__).resolve(),
            *list((CANDIDATE / "environments" / "matlab").glob("*.m")),
            *list((CANDIDATE / "tests" / "matlab").glob("*.m")),
            CANDIDATE / "config" / "verification_contract.json",
        ],
        key=lambda path: path.relative_to(CANDIDATE).as_posix(),
    )
    digest = hashlib.sha256(b"EU26-12-FAIL-CLOSED-SUITE-V1\0")
    total = 0
    for path in paths:
        payload = path.read_bytes()
        total += len(payload)
        relative = path.relative_to(CANDIDATE).as_posix()
        digest.update(
            f"{relative},{len(payload)},{hashlib.sha256(payload).hexdigest()}\n".encode("ascii")
        )
    return {"members": len(paths), "bytes": total, "sha256": digest.hexdigest()}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.output is not None and (args.output.exists() or args.output.is_symlink()):
        parser.error("--output must be a new path")
    contract = load_contract()
    suite = unittest.defaultTestLoader.discover(str(TESTS), pattern="test_*.py")
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    minimum = contract["verification_execution"]["minimum_fail_closed_python_tests"]
    passed = result.wasSuccessful() and not result.skipped and result.testsRun >= minimum
    report = bind_report(
        {
            "schema_version": "1.0.0",
            "candidate_id": "EU26-12",
            "status": "PASS_FAIL_CLOSED_SUITE" if passed else "FAIL_OR_INCOMPLETE",
            "tests_run": result.testsRun,
            "failures": len(result.failures),
            "errors": len(result.errors),
            "skipped": len(result.skipped),
            "minimum_tests": minimum,
            "suite_manifest": _suite_manifest(),
            "forbidden_claims": contract["forbidden_claims"],
        },
        domain=b"EU26-12-FAIL-CLOSED-REPORT-V1",
    )
    if args.output is not None:
        write_new_json(args.output, report)
    print(f"EU26-12 Python tests: {result.testsRun}; status={report['status']}")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
