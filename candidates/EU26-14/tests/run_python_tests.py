#!/usr/bin/env python3
"""Run the candidate-local Python suite without third-party test runners."""

from __future__ import annotations

import argparse
import os
import sys
import unittest
from pathlib import Path


TEST_ROOT = Path(__file__).resolve().parent
PYTHON_ENV = TEST_ROOT.parent / "environments" / "python"
sys.path.insert(0, str(PYTHON_ENV))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--require-full-artifact",
        action="store_true",
        help="fail unless the complete artifact integration executes without skips",
    )
    args = parser.parse_args()
    if args.require_full_artifact and not os.environ.get("EU2614_ARTIFACT_DIR"):
        parser.error("--require-full-artifact needs EU2614_ARTIFACT_DIR")
    suite = unittest.defaultTestLoader.discover(
        start_dir=str(TEST_ROOT / "python"), pattern="test_*.py"
    )
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    if args.require_full_artifact and result.skipped:
        print("required full-artifact suite contained a skip", file=sys.stderr)
        return 1
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
