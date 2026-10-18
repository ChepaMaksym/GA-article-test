"""Only tests are implemented as execution phases; all scientific stages closed."""
from __future__ import annotations

import argparse
from pathlib import Path
import unittest

from . import authority as a


def run_tests(output):
    provenance = a.check_preflight(output)
    output = Path(output)
    suite = unittest.defaultTestLoader.discover(str(a.MODULE / "tests"), pattern="test_*.py",
                                               top_level_dir=str(a.ROOT))
    with (output / "tests.txt").open("w", encoding="utf-8") as stream:
        result = unittest.TextTestRunner(stream=stream, verbosity=2).run(suite)
    a.write_json(output / "tests_receipt.json", {**provenance,
        "tests_run": result.testsRun, "tests_passed": result.wasSuccessful(),
        "failures": len(result.failures), "errors": len(result.errors), "skipped": len(result.skipped),
        "scientific_KPLIB_search_performed": False, "scientific_statistics_performed": False,
        "lambda_search_performed": False,
        "scope": "CI unit checks and labelled synthetic fixtures only"})
    a.write_manifest(output)
    a.verify_manifest(output)
    print((output / "tests.txt").read_text(encoding="utf-8"))
    a.require(result.wasSuccessful() and result.testsRun > 0 and not result.skipped,
              "Independent checks must all pass")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=("preflight", "tests"))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.phase == "preflight":
        a.preflight(args.output)
    else:
        run_tests(args.output)


if __name__ == "__main__":
    main()
