#!/usr/bin/env python3
"""Run EU26-13 unit/mutation tests and optionally emit a write-once attestation."""

from __future__ import annotations

import argparse
import sys
import unittest
from pathlib import Path


CANDIDATE = Path(__file__).resolve().parents[1]
PYTHON_ENV = CANDIDATE / "environments" / "python"
TESTS = Path(__file__).resolve().parent / "python"
sys.path.insert(0, str(PYTHON_ENV))
sys.path.insert(0, str(TESTS))

from eu2613.report import write_json_once  # noqa: E402
from eu2613.integrity import implementation_manifest  # noqa: E402
from eu2613.attestations import (  # noqa: E402
    EXPECTED_MUTATION_TESTS,
    EXPECTED_TESTS_RUN,
)


def flatten(suite):
    for item in suite:
        if isinstance(item, unittest.TestSuite):
            yield from flatten(item)
        else:
            yield item


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--attestation", type=Path)
    args = parser.parse_args()
    suite = unittest.defaultTestLoader.discover(str(TESTS), pattern="test_*.py")
    test_ids = [test.id() for test in flatten(suite)]
    mutation_tests = sum(".test_mutation_" in test_id for test_id in test_ids)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    if result.testsRun != EXPECTED_TESTS_RUN or mutation_tests != EXPECTED_MUTATION_TESTS:
        print(
            f"test inventory drift: expected {EXPECTED_TESTS_RUN}/{EXPECTED_MUTATION_TESTS}, "
            f"got {result.testsRun}/{mutation_tests}",
            file=sys.stderr,
        )
        return 2
    if result.skipped or result.expectedFailures or result.unexpectedSuccesses:
        print(
            "non-zero skip/expected-failure/unexpected-success inventory is forbidden",
            file=sys.stderr,
        )
        return 2
    if result.wasSuccessful() and args.attestation is not None:
        manifest = implementation_manifest()
        write_json_once(
            args.attestation,
            {
                "schema_version": "1.0.0",
                "candidate_id": "EU26-13",
                "status": "PASS_FAIL_CLOSED_MUTATION_SUITE",
                "tests_run": result.testsRun,
                "mutation_tests": mutation_tests,
                "failures": len(result.failures),
                "errors": len(result.errors),
                "skipped": len(result.skipped),
                "expected_failures": len(result.expectedFailures),
                "unexpected_successes": len(result.unexpectedSuccesses),
                "implementation_files": manifest["files"],
                "implementation_manifest_sha256": manifest["sha256"],
                "source_native_status": "BLOCKED_UNPINNED_TOOLCHAIN_DEPS",
            },
        )
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
