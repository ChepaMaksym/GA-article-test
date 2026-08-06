#!/usr/bin/env python3
"""Dependency-light test runner for the USA26-01 clean-room scaffold."""

from __future__ import annotations

from pathlib import Path
import unittest


def main() -> int:
    test_dir = Path(__file__).resolve().parent / "python"
    suite = unittest.defaultTestLoader.discover(str(test_dir), pattern="test_*.py")
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
