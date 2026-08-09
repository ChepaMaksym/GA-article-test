from __future__ import annotations

import csv
import json
import math
import unittest
from pathlib import Path


CANDIDATE_ROOT = Path(__file__).resolve().parents[2]


class FixtureProtocolTests(unittest.TestCase):
    def test_json_identity_seed_order_and_claim_ceiling(self) -> None:
        value = json.loads(
            (CANDIDATE_ROOT / "fixtures" / "frozen_endpoint.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(value["candidate_id"], "EU26-14")
        self.assertEqual(value["status"], "TARGETED_ARTIFACT_REPLAY_ONLY")
        self.assertEqual(value["paper_mapping"], "PAPER_CONTEXT_ONLY")
        self.assertEqual(value["endpoint"]["seeds"], list(range(51)))
        self.assertEqual(value["run0"]["nfev_total"], 2893419)
        self.assertEqual(value["stop_semantic_conflict"]["unspent_evaluations"], 106581)
        self.assertTrue(value["stop_semantic_conflict"]["budget_exhaustion_claim_forbidden"])
        self.assertIn("PASS_FULL", value["forbidden_claims"])

    def test_csv_cycle_alternation_reuse_and_arithmetic(self) -> None:
        with (CANDIDATE_ROOT / "fixtures" / "run0_cycles.csv").open(
            encoding="utf-8", newline=""
        ) as stream:
            rows = list(csv.DictReader(stream))
        self.assertEqual(len(rows), 30)
        prior_end = 0
        for index, row in enumerate(rows):
            start = int(row["nfev_start"])
            end = int(row["nfev_end"])
            self.assertEqual(int(row["cycle"]), index)
            self.assertEqual(start, prior_end)
            self.assertEqual(int(row["nfev_delta"]), end - start)
            self.assertEqual(row["mode"], f"alt-{index % 2}")
            self.assertEqual(row["sample_reused"], "true" if index % 2 else "false")
            self.assertEqual(int(row["nfev_phase0"]), 0 if index % 2 else 4096)
            if index == 0:
                self.assertTrue(math.isinf(float(row["best_f_start"])))
                self.assertTrue(math.isinf(float(row["improvement"])))
            else:
                arithmetic = float(row["best_f_start"]) - float(row["best_f_end"])
                self.assertEqual(float(row["improvement"]), arithmetic)
            prior_end = end
        self.assertEqual(prior_end, 2876679)


if __name__ == "__main__":
    unittest.main()
