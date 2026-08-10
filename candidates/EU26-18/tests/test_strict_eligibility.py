#!/usr/bin/env python3
"""Fail-closed checks for the EU26-18 eligibility-only contract."""

from __future__ import annotations

import csv
import json
from pathlib import Path
import unittest
from urllib.parse import urlparse


CANDIDATE_ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = CANDIDATE_ROOT / "config" / "eligibility_contract.json"
SOURCES_PATH = CANDIDATE_ROOT / "source_manifest" / "sources.csv"
EXPECTED_TAG = "STRICT_ADAPTIVE_GA_2026-08-10"
ALLOWED_CONTROLS = {
    "crossover_probability",
    "mutation_probability",
    "mutation_strength",
    "population_size",
    "tournament_size",
    "selection_pressure",
}


class StrictEligibilityContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))

    def test_identity_and_new_requirements_tag_are_frozen(self) -> None:
        self.assertEqual(self.contract["requirements_tag"], EXPECTED_TAG)
        self.assertEqual(self.contract["candidate_id"], "EU26-18")
        self.assertEqual(
            self.contract["identity"]["doi"], "10.1007/s00500-023-09049-0"
        )
        self.assertGreaterEqual(self.contract["identity"]["year"], 2020)
        self.assertIn(self.contract["identity"]["region"], {"EU", "USA"})

    def test_pass_strict_requires_every_hard_gate(self) -> None:
        self.assertEqual(self.contract["decision"], "PASS_STRICT")
        self.assertTrue(self.contract["hard_gates"])
        self.assertEqual(set(self.contract["hard_gates"].values()), {"PASS"})

    def test_dynamic_control_set_is_nonempty_and_strict_subset(self) -> None:
        controls = {
            item["canonical_name"] for item in self.contract["dynamic_controls"]
        }
        self.assertTrue(controls)
        self.assertLessEqual(controls, ALLOWED_CONTROLS)
        self.assertEqual(controls, {"mutation_strength"})
        self.assertEqual(self.contract["out_of_set_dynamic_controls"], [])

    def test_hybrid_and_schedule_boundaries_fail_closed(self) -> None:
        self.assertEqual(self.contract["hybrid_component_set"], [])
        feedback = self.contract["feedback_classification"]
        self.assertEqual(feedback["type"], "self_adaptive_under_selection")
        self.assertFalse(feedback["time_only_schedule"])
        self.assertFalse(feedback["offline_tuning"])
        self.assertFalse(feedback["unselected_random_schedule"])

    def test_no_reproduction_claim_is_smuggled_into_eligibility(self) -> None:
        boundary = self.contract["claim_boundary"]
        self.assertTrue(boundary["eligibility_only"])
        self.assertFalse(boundary["numeric_reproduction_claimed"])
        self.assertFalse(boundary["source_native_execution_claimed"])
        self.assertFalse(boundary["pass_full_claimed"])

    def test_more_than_10_preference_cannot_change_decision(self) -> None:
        preference = self.contract["auxiliary_preference"]
        self.assertEqual(preference["more_than_10_other_parameters"], "UNKNOWN")
        self.assertTrue(preference["does_not_affect_decision"])

    def test_primary_source_manifest_is_complete_and_https(self) -> None:
        with SOURCES_PATH.open(newline="", encoding="utf-8") as source_file:
            rows = list(csv.DictReader(source_file))
        self.assertEqual({row["source_id"] for row in rows}, {"S1", "S2", "S3"})
        for row in rows:
            parsed = urlparse(row["url"])
            self.assertEqual(parsed.scheme, "https")
            self.assertTrue(parsed.netloc)
            self.assertTrue(row["locators"])
            self.assertTrue(row["claims_supported"])
        method = next(row for row in rows if row["source_id"] == "S3")
        self.assertEqual(
            method["sha256"],
            "377e6ba5e834d6cf40919bd690fc384cf76db0ff5b5531f7356258b24de2d3b3",
        )
        self.assertEqual(int(method["byte_length"]), 829623)


if __name__ == "__main__":
    unittest.main()
