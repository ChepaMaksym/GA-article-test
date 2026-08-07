from __future__ import annotations

import math
from pathlib import Path
import sys
import unittest


CANDIDATE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(CANDIDATE / "environments" / "python"))

from banditverify.canonical import canonical_json, formula_digest  # noqa: E402


class CanonicalTests(unittest.TestCase):
    def test_key_and_record_order_are_canonical(self) -> None:
        left = [
            {"case_id": "b", "value": {"z": 2, "a": 1}},
            {"case_id": "a", "value": [1.0, 2.0]},
        ]
        right = [
            {"value": [1.0, 2.0], "case_id": "a"},
            {"value": {"a": 1, "z": 2}, "case_id": "b"},
        ]
        self.assertEqual(formula_digest(left), formula_digest(right))
        self.assertEqual(canonical_json({"b": 1, "a": 2}), b'{"a":2,"b":1}')

    def test_nonfinite_and_unsupported_values_fail_closed(self) -> None:
        for value in ({"x": math.nan}, {"x": math.inf}, {"x": object()}):
            with self.subTest(value=value), self.assertRaises((TypeError, ValueError)):
                canonical_json(value)


if __name__ == "__main__":
    unittest.main()
