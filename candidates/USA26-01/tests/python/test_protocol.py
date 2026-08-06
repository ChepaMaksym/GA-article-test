from __future__ import annotations

import csv
from itertools import product
from pathlib import Path
import re
import unittest

CANDIDATE_ROOT = Path(__file__).resolve().parents[2]


class FrozenProtocolTests(unittest.TestCase):
    def test_source_manifest_has_pinned_hashes_and_commit(self) -> None:
        with (CANDIDATE_ROOT / "source_manifest" / "sources.csv").open(
            encoding="utf-8", newline=""
        ) as handle:
            rows = list(csv.DictReader(handle))
        by_id = {row["source_id"]: row for row in rows}
        self.assertIn("PAPER_PDF", by_id)
        self.assertIn("PAPER_SOURCE", by_id)
        self.assertIn("UPSTREAM_REPO", by_id)
        self.assertIn(
            "2bcb6e1528a561d4e3117af6b7ebca99d961337f",
            by_id["UPSTREAM_REPO"]["revision_or_path"],
        )
        hash_pattern = re.compile(r"^[0-9a-f]{64}$")
        hashed_rows = [row for row in rows if row["sha256"]]
        self.assertGreaterEqual(len(hashed_rows), 10)
        self.assertTrue(
            all(hash_pattern.fullmatch(row["sha256"]) for row in hashed_rows)
        )

    def test_seed_ledger_is_exactly_zero_through_39(self) -> None:
        with (CANDIDATE_ROOT / "config" / "seed_ledger.csv").open(
            encoding="utf-8", newline=""
        ) as handle:
            rows = list(csv.DictReader(handle))
        self.assertEqual([int(row["seed"]) for row in rows], list(range(40)))
        self.assertEqual(len({row["seed_id"] for row in rows}), 40)
        self.assertTrue(
            all(row["scope"] == "every_experiment_matrix_config" for row in rows)
        )

    def test_experiment_matrix_is_complete_and_unique(self) -> None:
        with (CANDIDATE_ROOT / "config" / "experiment_matrix.csv").open(
            encoding="utf-8", newline=""
        ) as handle:
            rows = list(csv.DictReader(handle))
        observed = {
            (row["function"], int(row["dimension"]), int(row["initial_std"]))
            for row in rows
        }
        expected = set(
            product(
                ("ackley", "griewank", "rastrigin", "rosenbrock", "sphere"),
                (2, 30, 100, 1000),
                (1, 10),
            )
        )
        self.assertEqual(observed, expected)
        self.assertEqual(len(rows), 40)
        self.assertEqual(len({row["config_id"] for row in rows}), 40)
        generation_by_dimension = {2: 100, 30: 300, 100: 1000, 1000: 2500}
        for row in rows:
            self.assertEqual(int(row["generations"]), generation_by_dimension[int(row["dimension"])])
            self.assertEqual(row["seed_ids"], "S00-S39")
            self.assertEqual(int(row["full_population"]), 101)
            self.assertEqual(int(row["n_groups"]), 10)


if __name__ == "__main__":
    unittest.main()
