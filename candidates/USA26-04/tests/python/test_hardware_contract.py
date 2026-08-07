from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import unittest


CANDIDATE = Path(__file__).resolve().parents[2]
COMPARATOR = CANDIDATE / "tests" / "hardware" / "compare_portability_reports.py"
SPEC = importlib.util.spec_from_file_location("usa2604_comparator", COMPARATOR)
assert SPEC and SPEC.loader
module = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = module
SPEC.loader.exec_module(module)


def profile(label: str, cpus: int, github: bool = False) -> dict:
    return {
        "protocol_id": "USA26-04-FORMULA-PORTABILITY-v1",
        "verification_scope": "FORMULA_AND_AMBIGUITY_VALIDATION_ONLY",
        "paper_level_status": "BLOCKED_G5_G9",
        "published_result_status": "INCONCLUSIVE_PUBLISHED_RESULT",
        "fixed_controller_state_provenance": "synthetic_fixture_not_article_state",
        "profile_label": label,
        "profile_status": "PASS_PROFILE_H0_H4",
        "requested_workers": cpus,
        "requested_logical_cpus": cpus,
        "source_sha256": {"source.py": "abc"},
        "correctness": {"case_ids": ["a", "b"], "aggregate_digest": "digest"},
        "hardware": {
            "execution_context": {
                "github_actions": github,
                "github_run_id": "1" if github else None,
                "github_run_attempt": "1" if github else None,
            }
        },
    }


class HardwareComparatorTests(unittest.TestCase):
    def test_three_required_profiles_pass_engineering_only(self) -> None:
        result = module.compare_reports(
            [profile("work4", 4), profile("work8", 8), profile("github4", 4, True)]
        )
        self.assertEqual(result["H5_status"], "PASS_FORMULA_PORTABILITY")
        self.assertEqual(result["overall_status"], "PASS_ENGINEERING_FORMULA_PORTABILITY")
        self.assertEqual(result["paper_level_status"], "BLOCKED_G5_G9")
        self.assertFalse(result["claim_limits"]["published_result_equivalence_tested"])

    def test_two_work_profiles_are_strict_match_but_incomplete(self) -> None:
        result = module.compare_reports([profile("work4", 4), profile("work8", 8)])
        self.assertEqual(result["pairwise"][0]["status"], "PASS_STRICT_FORMULA_MATCH")
        self.assertEqual(result["H5_status"], "INCOMPLETE_REQUIRED_PROFILE")
        self.assertEqual(result["overall_status"], "INCONCLUSIVE_ENGINEERING_PORTABILITY")

    def test_digest_mismatch_fails_closed(self) -> None:
        left = profile("work4", 4)
        right = profile("work8", 8)
        right["correctness"]["aggregate_digest"] = "different"
        result = module.compare_reports([left, right])
        self.assertEqual(result["H5_status"], "INCONCLUSIVE_STRICT_MISMATCH")

    def test_paper_status_promotion_is_rejected(self) -> None:
        left = profile("work4", 4)
        right = profile("work8", 8)
        right["paper_level_status"] = "PASS"
        with self.assertRaisesRegex(ValueError, "paper-level block"):
            module.compare_reports([left, right])

    def test_missing_synthetic_provenance_is_rejected(self) -> None:
        left = profile("work4", 4)
        right = profile("work8", 8)
        right["fixed_controller_state_provenance"] = "article_state"
        with self.assertRaisesRegex(ValueError, "synthetic controller-state"):
            module.compare_reports([left, right])


if __name__ == "__main__":
    unittest.main()
