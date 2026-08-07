from __future__ import annotations

import csv
import json
from pathlib import Path
import unittest


CANDIDATE = Path(__file__).resolve().parents[2]
REPOSITORY = CANDIDATE.parents[1]


class ContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.contract = json.loads(
            (CANDIDATE / "config" / "validation_contract.json").read_text(encoding="utf-8")
        )

    def test_postprint_is_metadata_only_and_hash_unresolved(self) -> None:
        self.assertEqual(self.contract["source_byte_status"], "PASS_METADATA_ONLY")
        self.assertEqual(self.contract["postprint"]["bytes"], 2921299)
        self.assertEqual(self.contract["postprint"]["sha256"], "SHA256_UNRESOLVED")
        self.assertEqual(self.contract["postprint"]["freeze_status"], "BLOCKED_SOURCE_BYTE_FREEZE")

        with (CANDIDATE / "source_manifest" / "sources.csv").open(
            newline="", encoding="utf-8"
        ) as handle:
            rows = {row["source_id"]: row for row in csv.DictReader(handle)}
        self.assertEqual(rows["PAPER_POSTPRINT"]["bytes"], "2921299")
        self.assertEqual(rows["PAPER_POSTPRINT"]["sha256"], "SHA256_UNRESOLVED")
        self.assertEqual(rows["PAPER_POSTPRINT"]["freeze_status"], "BLOCKED_SOURCE_BYTE_FREEZE")
        self.assertEqual(
            rows["AUTHOR_THESIS"]["sha256"],
            "fd0a947833b703d1729f5d44c4bee082b7e1999ba57ba2b8adccbc83d15e13ba",
        )

    def test_published_endpoint_is_frozen_but_not_executable(self) -> None:
        endpoint = self.contract["publication_facts"]["descriptive_endpoint"]
        self.assertEqual((endpoint["improved_functions"], endpoint["total_functions"]), (27, 30))
        self.assertIs(endpoint["execution_authorized"], False)

    def test_selected_protocol_cell_is_frozen(self) -> None:
        facts = self.contract["publication_facts"]
        self.assertEqual(
            {
                "decision_dimension": facts["decision_dimension"],
                "chromosome_bits": facts["chromosome_bits"],
                "bits_per_coordinate": facts["bits_per_coordinate"],
                "population": facts["population"],
                "tournament_size": facts["tournament_size"],
                "generations": facts["generations"],
                "evaluations": facts["evaluations"],
                "independent_runs": facts["independent_runs"],
            },
            {
                "decision_dimension": 30,
                "chromosome_bits": 600,
                "bits_per_coordinate": 20,
                "population": 400,
                "tournament_size": 3,
                "generations": 200,
                "evaluations": 80000,
                "independent_runs": 30,
            },
        )
        self.assertEqual(facts["preference_labels"], [0, 1, 2, 3])
        self.assertEqual(facts["initial_probabilities"], [0.25] * 4)
        self.assertEqual(facts["probability_floor"], 0.1)
        self.assertEqual(facts["competitive_probability_mass"], 0.6)
        self.assertEqual((facts["lower_bound"], facts["upper_bound"]), (-100, 100))
        self.assertEqual((facts["crossover_probability"], facts["mutation_probability"]), (1.0, 0.0))
        self.assertEqual(
            self.contract["authorized_profiles"]["extension_ray"],
            "thesis_maximum_binary_profile",
        )
        self.assertEqual(
            self.contract["authorized_profiles"]["probability_update"],
            "complete_positive_denominators_only",
        )

    def test_pass_full_is_forbidden(self) -> None:
        self.assertIn("PASS_FULL", self.contract["forbidden_claims"])
        self.assertNotEqual(self.contract["required_labels"]["strongest_allowed"], "PASS_FULL")
        self.assertTrue(self.contract["paper_level_status"].startswith("BLOCKED_"))

    def test_formula_digests_are_preregistered_but_not_paper_outcomes(self) -> None:
        self.assertEqual(
            self.contract["evidence_boundary_amendment"],
            "preregistration/amendment-001-offline-evidence-boundary.md",
        )
        digests = self.contract["micro_oracle_digests"]
        self.assertEqual(
            digests["shared_fixture_report_sha256"],
            "6f560ccd36492e9fb1c4057d67ea2e54fffa032e72ddd02557bad077aacaf502",
        )
        self.assertEqual(
            digests["five_repeat_scientific_payload_sha256"],
            "6c55a35ccf72f0c86aa926c59b2382f5526bbcfcbeeec4fd782743ea5af89dd3",
        )
        self.assertIs(
            self.contract["publication_facts"]["descriptive_endpoint"]["execution_authorized"],
            False,
        )
        hardware = json.loads(
            (CANDIDATE / "config" / "hardware_profiles.json").read_text(encoding="utf-8")
        )
        self.assertEqual(hardware["parallel_case_count"], 128)
        content_match = hardware["github_content_match"]
        self.assertEqual(
            content_match["missing_status"], "NOT_RUN_GITHUB_CONTENT_MATCH_RECORD"
        )
        self.assertEqual(
            content_match["external_authentication_status"],
            "NOT_EVALUATED_EXTERNAL_GITHUB_AUTH_REQUIRED",
        )
        self.assertIs(content_match["offline_authorizes_h5"], False)

    def test_registry_stays_conditional_and_g5_g6_unresolved(self) -> None:
        registry = json.loads(
            (REPOSITORY / "registry" / "cohort_2026_12" / "registry.json").read_text(
                encoding="utf-8"
            )
        )
        gates = json.loads(
            (
                REPOSITORY
                / "registry"
                / "cohort_2026_12"
                / "hard_gate_assessments.json"
            ).read_text(encoding="utf-8")
        )
        record = next(item for item in registry if item["candidate_id"] == "EU26-05")
        assessment = next(item for item in gates if item["candidate_id"] == "EU26-05")
        self.assertEqual(record["eligibility_status"], "conditional_noneligible")
        self.assertIsNone(record["final_score"])
        for gate in ("c1_full_text", "g5", "g6", "g7", "g8", "g9"):
            self.assertEqual(assessment[gate]["status"], "unresolved")

    def test_no_cec_or_published_result_runner_exists(self) -> None:
        allowed_names = {path.name.lower() for path in CANDIDATE.rglob("*") if path.is_file()}
        forbidden = {"run_cec2017.py", "run_reproduction.py", "replay_27_of_30.py"}
        self.assertTrue(allowed_names.isdisjoint(forbidden))


if __name__ == "__main__":
    unittest.main()
