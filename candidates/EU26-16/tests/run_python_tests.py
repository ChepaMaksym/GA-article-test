from __future__ import annotations

import argparse
import os
import sys
import unittest
from pathlib import Path

CANDIDATE = Path(__file__).resolve().parents[1]
PYTHON_ROOT = CANDIDATE / "environments" / "python"
TEST_ROOT = Path(__file__).resolve().parent / "python"
for path in (PYTHON_ROOT, TEST_ROOT):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from eu2616.canonical import bind_report, write_new_json
from eu2616.contract import load_contract
from eu2616.source import authenticate_checkout


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    arguments = parser.parse_args()
    upstream_value = os.environ.get("EU2616_UPSTREAM")
    if not upstream_value:
        raise SystemExit("EU2616_UPSTREAM is required")
    contract = load_contract()
    source = authenticate_checkout(Path(upstream_value), contract)
    suite = unittest.defaultTestLoader.discover(str(TEST_ROOT), pattern="test_*.py")
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    execution = contract["verification_execution"]
    passed = (
        result.wasSuccessful()
        and result.testsRun >= execution["minimum_python_tests"]
        and (not execution["require_zero_skips"] or len(result.skipped) == 0)
    )
    report = bind_report(
        {
            "schema_version": "1.0.0",
            "candidate_id": "EU26-16",
            "status": (
                "PASS_FORMULA_AND_SOURCE_TRANSITION_ONLY"
                if passed
                else "FAIL_OR_INCOMPLETE"
            ),
            "test_gate": "PASS_SOURCE_TRANSITION" if passed else "FAIL_OR_INCOMPLETE",
            "readiness": contract["readiness"],
            "paper_mapping": contract["paper_mapping"],
            "tests_run": result.testsRun,
            "failures": len(result.failures),
            "errors": len(result.errors),
            "skipped": len(result.skipped),
            "minimum_tests": execution["minimum_python_tests"],
            "source": {
                "commit": source["commit"],
                "tree": source["tree"],
                "tag": source["tag"],
                "clean": source["clean"],
            },
            "empirical_claim_made": False,
            "forbidden_claims": contract["forbidden_claims"],
        }
    )
    if arguments.output is not None:
        write_new_json(arguments.output, report)
    print(f"EU26-16 Python tests: {result.testsRun}; status={report['status']}")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
