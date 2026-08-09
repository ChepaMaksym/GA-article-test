#!/usr/bin/env python3
"""Run the fail-closed EU26-15 standard-library verification suite."""

from __future__ import annotations

import json
from pathlib import Path
import sys
import unittest


CANDIDATE = Path(__file__).resolve().parents[1]
PYTHON_ENV = CANDIDATE / "environments" / "python"
TESTS = Path(__file__).resolve().parent / "python"
sys.path.insert(0, str(PYTHON_ENV))


def main() -> int:
    suite = unittest.defaultTestLoader.discover(str(TESTS), pattern="test_*.py")
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    if result.skipped or result.expectedFailures or result.unexpectedSuccesses:
        print("skips and expected-failure states are forbidden", file=sys.stderr)
        return 2
    if not result.wasSuccessful():
        return 1
    print(
        json.dumps(
            {
                "candidate_id": "EU26-15",
                "candidate_status": "CONDITIONAL_NONELIGIBLE",
                "verification_scope": "FORMULA_AND_SOURCE_TRANSITION_VALIDATION_ONLY",
                "status": "PASS_PYTHON_TRANSITION_FIXTURES",
                "tests_run": result.testsRun,
                "pass_full": False,
                "empirical_replay": False,
                "table_2_replay": False,
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
