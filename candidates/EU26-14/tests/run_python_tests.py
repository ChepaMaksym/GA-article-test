#!/usr/bin/env python3
"""Run the candidate-local Python suite without third-party test runners."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path


TEST_ROOT = Path(__file__).resolve().parent
PYTHON_ENV = TEST_ROOT.parent / "environments" / "python"
sys.path.insert(0, str(PYTHON_ENV))


def main() -> int:
    suite = unittest.defaultTestLoader.discover(
        start_dir=str(TEST_ROOT / "python"), pattern="test_*.py"
    )
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
