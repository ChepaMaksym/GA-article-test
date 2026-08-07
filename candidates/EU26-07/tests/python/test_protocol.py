from __future__ import annotations

import csv
import json
import unittest
from pathlib import Path


CANDIDATE = Path(__file__).resolve().parents[2]


class FrozenProtocolTests(unittest.TestCase):
    def test_verification_contract_profiles_are_isolated(self):
        contract = json.loads(
            (CANDIDATE / "config" / "verification_contract.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(contract["candidate_id"], "EU26-07")
        self.assertEqual(contract["problem"], {
            "name": "Jump",
            "n": 20,
            "k": 4,
            "sense": "maximize",
            "target_fitness": 24,
        })
        profiles = contract["profiles"]
        self.assertEqual(profiles["paper_algorithm3"]["rounding"], "nearest_half_up")
        self.assertEqual(
            profiles["artifact_jump_optimized"]["rounding"],
            "python_ties_to_even",
        )
        self.assertNotEqual(
            profiles["paper_algorithm3"]["final_pool"],
            profiles["artifact_jump_optimized"]["final_pool"],
        )
        self.assertFalse(contract["acceptance"]["pass_full_allowed"])

    def test_seed_ledger_is_the_exact_driver_mapping(self):
        path = CANDIDATE / "config" / "seed_ledger.csv"
        with path.open(newline="", encoding="utf-8") as handle:
            rows = list(csv.DictReader(handle))
        self.assertEqual(len(rows), 500)
        self.assertEqual([int(row["run"]) for row in rows], list(range(1, 501)))
        self.assertEqual(
            [int(row["effective_seed"]) for row in rows],
            list(range(816_114_842, 816_115_342)),
        )

    def test_source_manifest_retains_gpl_and_nonarchival_boundaries(self):
        path = CANDIDATE / "source_manifest" / "sources.csv"
        with path.open(newline="", encoding="utf-8") as handle:
            rows = {row["role"]: row for row in csv.DictReader(handle)}
        self.assertEqual(rows["license"]["status"], "PASS_GPL_3_0")
        self.assertIn("NO_ARCHIVAL_TAG", rows["author_repository"]["status"])
        self.assertEqual(
            rows["raw_target"]["sha256"],
            "b2ac8c81efaf786823d49dcef26eeb20f0257ca7fe9e1e2394d02ca5e26dd9a6",
        )

    def test_claim_blockers_are_documented(self):
        audit = (CANDIDATE / "source_manifest" / "audit_notes.md").read_text(
            encoding="utf-8"
        )
        for required in (
            "Algorithm 3",
            "half-up",
            "all mutants",
            "GPL-3.0",
            "PASS_FULL",
        ):
            self.assertIn(required, audit)


if __name__ == "__main__":
    unittest.main()
