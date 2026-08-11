from __future__ import annotations

import json
import os
from pathlib import Path
import unittest

from eu2607.published import (
    PublishedDataError,
    canonical_rows_sha256,
    parse_processed_targets,
    parse_raw_rows,
    summarize_rows,
)


CANDIDATE = Path(__file__).resolve().parents[2]
UPSTREAM = os.environ.get("EU2607_UPSTREAM")


@unittest.skipUnless(UPSTREAM, "set EU2607_UPSTREAM for authenticated data tests")
class PublishedArtifactTests(unittest.TestCase):
    def test_all_500_rows_recompute_the_processed_targets(self):
        root = Path(UPSTREAM or "")
        rows = parse_raw_rows(root)
        self.assertEqual(len(rows), 500)
        summary = summarize_rows(rows).to_dict()
        declared = parse_processed_targets(root)
        for key, value in declared.items():
            self.assertEqual(summary[key], value)
        fixture = json.loads(
            (CANDIDATE / "fixtures" / "published_summary.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(declared, fixture["published"])
        self.assertEqual(
            canonical_rows_sha256(rows),
            fixture["derived_from_authenticated_raw_not_published"][
                "canonical_rows_sha256"
            ],
        )

    def test_missing_checkout_fails_closed(self):
        with self.assertRaises(PublishedDataError):
            parse_raw_rows(Path("/definitely/not/eu2607"))


if __name__ == "__main__":
    unittest.main()
