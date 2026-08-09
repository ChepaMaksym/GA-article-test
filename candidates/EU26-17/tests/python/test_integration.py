from __future__ import annotations

import json
import os
from pathlib import Path
import sys
import unittest


CANDIDATE_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(CANDIDATE_ROOT / "environments" / "python"))

from eu2617.validation import build_report  # noqa: E402


class AuthenticatedIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        names = (
            "EU2617_CORE_REPO",
            "EU2617_EXPERIMENT_REPO",
            "EU2617_PAPER_PDF",
            "EU2617_UCI_ARCHIVE",
        )
        missing = [name for name in names if not os.environ.get(name)]
        if missing:
            raise unittest.SkipTest("integration paths not supplied: " + ", ".join(missing))
        octave = os.environ.get("EU2617_OCTAVE_TSV")
        cls.report = build_report(
            CANDIDATE_ROOT,
            Path(os.environ["EU2617_CORE_REPO"]),
            Path(os.environ["EU2617_EXPERIMENT_REPO"]),
            Path(os.environ["EU2617_PAPER_PDF"]),
            Path(os.environ["EU2617_UCI_ARCHIVE"]),
            Path(octave) if octave else None,
        )

    def test_authenticated_methods_and_revisions_pass(self) -> None:
        source = self.report["source_identity"]
        self.assertEqual(source["status"], "PASS_SOURCE_IDENTITY")
        self.assertFalse(source["author_pinned_experiment_core"])
        self.assertEqual(source["tracked_mlruns_paths"], [])
        self.assertEqual(
            source["timing"]["first_loop_statement"], "adjust_rates"
        )
        self.assertEqual(
            self.report["source_method_transitions"]["status"],
            "PASS_SOURCE_METHOD_TRANSITIONS",
        )
        divergence = self.report["source_method_transitions"]["guard_divergence"]
        self.assertFalse(divergence["upstream_has_explicit_guard"])
        self.assertEqual(divergence["upstream_zero_maximum"]["gdm"], "NaN")
        self.assertEqual(divergence["upstream_nonfinite"]["gdm"], "NaN")
        self.assertEqual(divergence["clean_room_policy"], "REJECT_BEFORE_DIVISION")
        addition = source["core_algorithm_addition"]
        self.assertEqual(
            addition["requested_revision"],
            "cefd949488dbe23c030f17bb50b6c7c73a44ae3",
        )
        self.assertEqual(
            addition["commit"],
            "cefd949488dbe23c030f17bb50b6c7c73a44ae3a",
        )

    def test_seed_derivation_is_source_fact_not_run_provenance(self) -> None:
        protocol = self.report["experiment_protocol"]
        self.assertEqual(protocol["master_seed"], 42)
        self.assertEqual(len(protocol["model_seeds"]), 8)
        self.assertEqual(protocol["nominal_model_split_fits"], 64)
        self.assertFalse(protocol["historical_execution_proven"])

    def test_paper_loader_csv_and_uci_member_agree(self) -> None:
        parkinson = self.report["parkinson"]
        self.assertEqual(parkinson["status"], "PASS_PARKINSON_DIMENSION_FACT")
        self.assertEqual(parkinson["applied_dimension_status"], "PASS_APPLIED_DIMENSION")
        self.assertEqual(parkinson["repository_data"]["input_dimension"], 18)
        self.assertEqual(parkinson["repository_data"]["rows"], 5875)
        self.assertEqual(parkinson["paper_table"]["input_dimension"], 18)
        self.assertEqual(parkinson["paper_table"]["sample_count"], 5875)
        self.assertTrue(
            parkinson["uci_primary_input"]["repository_byte_identity"]
        )
        self.assertEqual(parkinson["uci_primary_input"]["license"], "CC-BY-4.0")

    def test_report_cannot_be_misread_as_empirical_replay(self) -> None:
        self.assertEqual(self.report["eligibility_status"], "HARD_FAIL")
        self.assertIsNone(self.report["published_numeric_endpoint"])
        self.assertIsNone(self.report["acceptance_tolerance"])
        self.assertIn("HARD_FAIL_ELIGIBILITY_UNCHANGED", self.report["outcomes"])
        self.assertNotIn("PASS_FULL", self.report["outcomes"])
        self.assertFalse(self.report["claim_boundary"]["raw_mlruns_present"])
        self.assertFalse(
            self.report["claim_boundary"]["approximate_prose_used_as_target"]
        )
        json.dumps(self.report, allow_nan=False)

    def test_octave_status_matches_supplied_evidence(self) -> None:
        if os.environ.get("EU2617_OCTAVE_TSV"):
            self.assertEqual(
                self.report["cross_language"]["status"], "PASS_CROSS_LANGUAGE"
            )
            self.assertIn("PASS_CROSS_LANGUAGE", self.report["outcomes"])
        else:
            self.assertEqual(self.report["cross_language"]["status"], "NOT_RUN")
            self.assertNotIn("PASS_CROSS_LANGUAGE", self.report["outcomes"])


if __name__ == "__main__":
    unittest.main()
