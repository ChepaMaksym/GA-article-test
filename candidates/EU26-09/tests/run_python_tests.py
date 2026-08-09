#!/usr/bin/env python3
"""Run the complete fail-closed EU26-09 candidate-local Python suite."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import unittest
from pathlib import Path


CANDIDATE = Path(__file__).resolve().parents[1]
PYTHON_ENV = CANDIDATE / "environments" / "python"
TESTS = Path(__file__).resolve().parent / "python"
sys.path.insert(0, str(PYTHON_ENV))
sys.path.insert(0, str(TESTS))

from eu2609.canonical import bind_report, write_new_json  # noqa: E402
from eu2609.contract import load_contract  # noqa: E402
from eu2609.source import authenticate_checkout  # noqa: E402


def _suite_manifest() -> dict[str, object]:
    paths = sorted(
        [
            *PYTHON_ENV.rglob("*.py"),
            *TESTS.glob("test_*.py"),
            Path(__file__).resolve(),
            *list((CANDIDATE / "environments" / "matlab").glob("*.m")),
            CANDIDATE / "config" / "verification_contract.json",
            CANDIDATE / "config" / "source_native_environment.json",
        ],
        key=lambda path: path.relative_to(CANDIDATE).as_posix(),
    )
    digest = hashlib.sha256(b"EU26-09-FAIL-CLOSED-SUITE-V1\0")
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
    checkout_value = os.environ.get("EU2609_UPSTREAM")
    if not checkout_value:
        parser.error("EU2609_UPSTREAM must name the authenticated checkout")
    contract = load_contract()
    source = authenticate_checkout(Path(checkout_value), contract)
    suite = unittest.defaultTestLoader.discover(str(TESTS), pattern="test_*.py")
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    execution = contract["verification_execution"]
    passed = (
        result.wasSuccessful()
        and len(result.skipped) == 0
        and result.testsRun >= execution["minimum_fail_closed_python_tests"]
    )
    report = bind_report(
        {
            "schema_version": "1.0.0",
            "candidate_id": "EU26-09",
            "status": "PASS_FAIL_CLOSED_SUITE" if passed else "FAIL_OR_INCOMPLETE",
            "tests_run": result.testsRun,
            "failures": len(result.failures),
            "errors": len(result.errors),
            "skipped": len(result.skipped),
            "minimum_tests": execution["minimum_fail_closed_python_tests"],
            "source": {"commit": source["commit"], "tree": source["tree"], "clean": source["clean"]},
            "suite_manifest": _suite_manifest(),
            "forbidden_claims": contract["forbidden_claims"],
        },
        domain=b"EU26-09-FAIL-CLOSED-REPORT-V1",
    )
    if args.output is not None:
        write_new_json(args.output, report)
    print(f"EU26-09 Python tests: {result.testsRun}; status={report['status']}")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
