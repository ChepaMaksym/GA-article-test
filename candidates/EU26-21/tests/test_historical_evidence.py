"""Synthetic ledger guards for the analysis-only historical audit (CI-only)."""
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from evidence_audit.historical import SOURCES, seed_rows


class HistoricalEvidenceTests(unittest.TestCase):
    def test_profiles_pin_distinct_immutable_archives(self):
        self.assertEqual({entry["id"] for entry in SOURCES.values()}, {9260332711, 9297184026})
        self.assertEqual(len({entry["digest"] for entry in SOURCES.values()}), 2)

    def test_complete_ledger_and_missing_duplicate_bool_guards(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for seed in range(1, 31):
                (root / f"seed-{seed}.json").write_text(json.dumps({"seed": seed}))
            self.assertEqual([row["seed"] for row in seed_rows(root)], list(range(1, 31)))
            target = root / "seed-1.json"
            for value in (2, True, "1"):
                target.write_text(json.dumps({"seed": value}))
                with self.subTest(value=value), self.assertRaises(ValueError):
                    seed_rows(root)
            target.unlink()
            with self.assertRaisesRegex(ValueError, "exactly 30"):
                seed_rows(root)


if __name__ == "__main__":
    unittest.main()
