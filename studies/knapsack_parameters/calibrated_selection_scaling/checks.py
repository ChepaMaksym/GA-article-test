"""Run the small CI test suite and retain machine-readable failures."""
import argparse
from pathlib import Path
from time import perf_counter
import unittest

from .common import ROOT, REPOSITORY, guard_stage, write_json
from .resources import require_enclosure


def run(output):
    guard_stage("technical")
    enclosure = require_enclosure(workers=1)
    started = perf_counter()
    suite = unittest.defaultTestLoader.discover(str(ROOT / "tests"), top_level_dir=str(REPOSITORY))
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    write_json(output, {"status": "PASSED" if result.wasSuccessful() else "FAILED",
                       "tests_run": result.testsRun, "seconds": perf_counter() - started,
                       "failures": [{"test": str(test), "traceback": trace} for test, trace in result.failures],
                       "errors": [{"test": str(test), "traceback": trace} for test, trace in result.errors],
                       "skipped": [{"test": str(test), "reason": reason} for test, reason in result.skipped],
                       "resource_enclosure": enclosure}, max_bytes=32 * 1024 ** 2)
    if not result.wasSuccessful() or result.skipped:
        raise SystemExit("Every admitted test must pass without skips")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    run(parser.parse_args().output)
