"""Checks-only driver. No KPLIB preparation, search, matrix, or statistics CLI."""
from __future__ import annotations

import argparse
from pathlib import Path
import unittest

from . import authority as a


def run_tests(output):
    provenance = a.check_preflight(output)
    output = Path(output)
    suite = unittest.TestSuite()
    loader = unittest.TestLoader()
    for name in ("test_authority", "test_operator", "test_knapsack", "test_comparison"):
        suite.addTests(loader.loadTestsFromName(
            "studies.knapsack_parameters.bntga_selection.tests." + name))
    with (output / "tests.txt").open("w", encoding="utf-8") as stream:
        result = unittest.TextTestRunner(stream=stream, verbosity=2).run(suite)
    instructional_error = None
    if result.wasSuccessful():
        try:
            from .comparison import teaching_comparison
            from .knapsack_comparison import teaching_knapsack_comparison
            a.write_json(output / "instructional_selection_comparison.json", teaching_comparison())
            a.write_json(output / "instructional_knapsack_comparison.json", teaching_knapsack_comparison())
        except Exception as error:
            instructional_error = f"{type(error).__name__}: {error}"
    a.write_json(output / "tests_receipt.json", {**provenance, "tests_passed": result.wasSuccessful(),
        "tests_run": result.testsRun, "failures": len(result.failures), "errors": len(result.errors),
        "skipped": len(result.skipped), "scientific_KPLIB_search_performed": False,
        "auxiliary_archive_transfer_approved": True,
        "instructional_examples_passed": result.wasSuccessful() and instructional_error is None,
        "instructional_error": instructional_error,
        "scope": "unit verification and explicitly labelled instructional examples only"})
    a.write_manifest(output)
    a.verify_manifest(output)
    print((output / "tests.txt").read_text(encoding="utf-8"))
    a.require(result.wasSuccessful() and result.testsRun > 0 and not result.skipped,
              "All independent CI checks must pass")
    a.require(instructional_error is None, "Instructional comparison failed: " + str(instructional_error))


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
