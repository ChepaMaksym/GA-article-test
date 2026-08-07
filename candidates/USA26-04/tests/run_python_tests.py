#!/usr/bin/env python3
"""Run the USA26-04 clean-room formula and ambiguity tests."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path


CANDIDATE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(CANDIDATE / "environments" / "python"))


if __name__ == "__main__":
    suite = unittest.defaultTestLoader.discover(
        str(Path(__file__).resolve().parent / "python"), pattern="test_*.py"
    )
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    raise SystemExit(0 if result.wasSuccessful() else 1)
