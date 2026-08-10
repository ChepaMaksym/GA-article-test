#!/usr/bin/env python3
"""Fail-closed claim-boundary checks for the EU26-18 verification stage."""

from __future__ import annotations

import json
from pathlib import Path
import unittest


CANDIDATE_ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = CANDIDATE_ROOT / "verification" / "verification_contract.json"


class VerificationContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))

    def test_stage_does_not_claim_complete_or_numeric_reproduction(self) -> None:
        scope = self.contract["verification_scope"]
        self.assertEqual(scope["complete_nsga2"], "NOT_IMPLEMENTED")
        self.assertEqual(scope["author_implementation"], "NOT_AVAILABLE")
        self.assertEqual(scope["published_numeric_reproduction"], "BLOCKED")
        self.assertTrue(self.contract["claim_boundary"]["pass_full_is_not_claimed"])

    def test_every_declared_interpretation_is_explicit(self) -> None:
        interpretations = self.contract["declared_interpretations"]
        self.assertEqual(interpretations["algorithm_2_x_c"], "current_coordinate_x")
        self.assertEqual(interpretations["repair_semantics"], "clamp_to_nearest_bound")
        self.assertEqual(
            interpretations["initial_eta_distribution"], "UNSPECIFIED_BY_PAPER"
        )
        self.assertEqual(interpretations["rng"], "NOT_RECONSTRUCTED")

    def test_blockers_are_unique_and_prevent_pass_full(self) -> None:
        blockers = self.contract["blockers"]
        self.assertGreaterEqual(len(blockers), 9)
        self.assertEqual(len({blocker["id"] for blocker in blockers}), len(blockers))
        self.assertGreaterEqual(
            sum(blocker["severity"] == "HARD" for blocker in blockers), 7
        )

    def test_ci_covers_three_operating_system_families(self) -> None:
        systems = {entry["os"] for entry in self.contract["ci_matrix"]}
        self.assertEqual(
            systems, {"ubuntu-latest", "macos-latest", "windows-latest"}
        )
        self.assertEqual(
            self.contract["determinism_probe"]["worker_counts"], [1, 2, 4]
        )

    def test_source_and_requirements_identity_are_pinned(self) -> None:
        self.assertEqual(
            self.contract["requirements_tag"], "STRICT_ADAPTIVE_GA_2026-08-10"
        )
        self.assertEqual(
            self.contract["source_pdf_sha256"],
            "d534e4a0d2612d409adea33f899133cf346cdeb6c5ef04e6820565d67e4a35f2",
        )

    def test_full_batch_budget_witness_exposes_25000_ambiguity(self) -> None:
        evaluations = 300
        while evaluations < 25000:
            evaluations += 300
        self.assertEqual(evaluations, 25200)
        self.assertNotEqual(evaluations, 25000)


if __name__ == "__main__":
    unittest.main()
