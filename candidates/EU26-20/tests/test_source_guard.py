#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import unittest

MODULE_PATH = Path(__file__).resolve().parents[1] / "old" / "run_author_colon_guarded.py"
OLD_DIR = MODULE_PATH.parent
sys.path.insert(0, str(OLD_DIR))
SPEC = importlib.util.spec_from_file_location("eu26_20_source_guard", MODULE_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("cannot load source guard")
GUARD = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(GUARD)


class SourceGuardTests(unittest.TestCase):
    def test_two_repository_loops_are_guarded_without_reindenting_body(self) -> None:
        source = """count=0
while (count<10):
   distance=[]
   count += 1

def loop():
    count=0
    while (count<10):
       distance=[]
       count += 1
"""
        patched = GUARD.add_repository_guards(source, 123)
        self.assertEqual(patched.count(GUARD.GUARD_MARKER), 2)
        self.assertEqual(patched.count("_eu_repository_attempts = 0"), 2)
        compile(patched, "guarded.py", "exec")

    def test_missing_loop_fails_closed(self) -> None:
        with self.assertRaises(RuntimeError):
            GUARD.add_repository_guards("while (count<10):\n   pass\n", 10)

    def test_invalid_limit_fails(self) -> None:
        with self.assertRaises(ValueError):
            GUARD.add_repository_guards(
                "while (count<10):\n   pass\nwhile (count<10):\n   pass\n",
                0,
            )


if __name__ == "__main__":
    unittest.main()
