from __future__ import annotations

import json
import math
import os
import tempfile
import unittest
from pathlib import Path

from eu2612.canonical import ReportError, bind_report, canonical_bytes, write_new_json


class CanonicalTests(unittest.TestCase):
    def test_canonical_order_is_stable(self) -> None:
        self.assertEqual(canonical_bytes({"b": 1, "a": 2}), b'{"a":2,"b":1}')

    def test_non_finite_value_fails(self) -> None:
        with self.assertRaises(ReportError):
            canonical_bytes({"x": math.nan})

    def test_empty_domain_fails(self) -> None:
        with self.assertRaises(ReportError):
            bind_report({"x": 1}, domain=b"")

    def test_prebound_report_fails(self) -> None:
        with self.assertRaises(ReportError):
            bind_report({"report_digest": "x"}, domain=b"D")

    def test_domain_separation_changes_digest(self) -> None:
        left = bind_report({"x": 1}, domain=b"A")
        right = bind_report({"x": 1}, domain=b"B")
        self.assertNotEqual(left["report_digest"], right["report_digest"])

    def test_new_report_is_mode_600_and_parseable(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "report.json"
            write_new_json(path, {"value": 3})
            self.assertEqual(json.loads(path.read_text()), {"value": 3})
            self.assertEqual(os.stat(path).st_mode & 0o777, 0o600)

    def test_existing_report_is_not_overwritten(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "report.json"
            path.write_text("original", encoding="utf-8")
            with self.assertRaises(FileExistsError):
                write_new_json(path, {"value": 3})
            self.assertEqual(path.read_text(), "original")

    def test_symlink_report_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            target = root / "target.json"
            link = root / "link.json"
            link.symlink_to(target)
            with self.assertRaises(FileExistsError):
                write_new_json(link, {"value": 3})
            self.assertFalse(target.exists())


if __name__ == "__main__":
    unittest.main()
