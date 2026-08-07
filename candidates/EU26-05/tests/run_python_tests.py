#!/usr/bin/env python3
"""Run all outcome-blind EU26-05 Python validation tests."""

from __future__ import annotations

from pathlib import Path
import sys
import unittest


CANDIDATE = Path(__file__).resolve().parents[1]
PYTHON_ENV = CANDIDATE / "environments" / "python"
sys.path.insert(0, str(PYTHON_ENV))


if __name__ == "__main__":
    suite = unittest.defaultTestLoader.discover(
        str(CANDIDATE / "tests" / "python"), pattern="test_*.py"
    )
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    raise SystemExit(0 if result.wasSuccessful() else 1)
