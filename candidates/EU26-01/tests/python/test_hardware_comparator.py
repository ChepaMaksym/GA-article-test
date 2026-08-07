from __future__ import annotations

import copy
import importlib.util
from pathlib import Path
import tempfile
import unittest

from tworateverify.canonical import canonical_sha256


CANDIDATE = Path(__file__).resolve().parents[2]
COMPARATOR_PATH = CANDIDATE / "tests" / "hardware" / "compare_portability_reports.py"
SPEC = importlib.util.spec_from_file_location("eu26_01_comparator", COMPARATOR_PATH)
assert SPEC and SPEC.loader
comparator = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(comparator)


def synthetic_bindings() -> dict[str, object]:
    vector = [61624] * 100
    statistics = {
        "count": 100,
        "mean_exact": "61623.78",
        "population_variance_exact": "327085104.6716",
        "mean_published_rounding": 61624,
        "population_variance_published_rounding": "3.271e+08",
        "matches_published_mean": True,
        "matches_published_population_variance": True,
    }
    return {
        "archive_sha256": "a" * 64,
        "member_sha256": "b" * 64,
        "completion_vector_sha256": canonical_sha256(
            vector, domain="EU26-01-COMPLETION-FES-V1"
        ),
        "completion_statistics_sha256": canonical_sha256(
            statistics, domain="EU26-01-COMPLETION-STATISTICS-V1"
        ),
        "mean_exact": "61623.78",
        "population_variance_exact": "327085104.6716",
        "fixture_file_sha256": "c" * 64,
        "fixture_result_sha256": "d" * 64,
        "formula_correctness_sha256": "e" * 64,
        "timing_endpoint_sha256": "f" * 64,
    }


def make_profile(role: str, bindings: dict[str, object]) -> dict[str, object]:
    workers = comparator.ROLE_WORKERS[role]
    vector = [61624] * 100
    statistics = {
        "count": 100,
        "mean_exact": "61623.78",
        "population_variance_exact": "327085104.6716",
        "mean_published_rounding": 61624,
        "population_variance_published_rounding": "3.271e+08",
        "matches_published_mean": True,
        "matches_published_population_variance": True,
    }
    custody = {
        "archive_sha256": bindings["archive_sha256"],
        "archive_sha256_end": bindings["archive_sha256"],
        "snapshot_sha256_end": bindings["archive_sha256"],
        "member_sha256": bindings["member_sha256"],
    }
    report: dict[str, object] = {
        "protocol_id": comparator.PROTOCOL_ID,
        "candidate_id": "EU26-01",
        "scope": "ARCHIVE_AND_FORMULA_VALIDATION_ONLY",
        "profile_role": role,
        "profile_status": "PASS_PROFILE",
        "paper_level_status": comparator.PAPER_STATUS,
        "eligibility_status": "conditional_noneligible",
        "pass_full_allowed": False,
        "algorithm2_conflict": comparator.ALGORITHM2_CONFLICT,
        "requested_workers": workers,
        "requested_logical_cpus": workers,
        "timing_repeats": 5,
        "git_sha_start": "1" * 40,
        "git_sha_end": "1" * 40,
        "git_clean_start": True,
        "git_clean_end": True,
        "git_status_start": [],
        "git_status_end": [],
        "source_sha256_start": {"candidate": "2" * 64},
        "source_sha256_end": {"candidate": "2" * 64},
        "bindings": copy.deepcopy(bindings),
        "gates": {
            "H0_provenance": {"status": "PASS", "failures": []},
            "H1_worker_allocation": {"status": "PASS", "failures": []},
            "H2_archive_identity": {"status": "PASS", "failures": []},
            "H3_formula_invariants": {"status": "PASS", "failures": []},
            "H4_repeatability": {"status": "PASS", "failures": []},
            "H5_cross_profile": {
                "status": "NOT_EVALUATED_SINGLE_PROFILE",
                "failures": [],
            },
        },
        "worker_pool": {
            "unique_worker_pids": list(range(100, 100 + workers)),
            "unique_worker_pid_count": workers,
            "affinity_failure_pids": [],
            "thread_limit_failure_pids": [],
            "inconsistencies": [],
        },
        "hardware": {
            "cpu_allocation_valid": True,
            "exact_visible_cpu_set": role == "github4",
            "github_actions": role == "github4",
            "github_run_id": "123456" if role == "github4" else None,
            "github_run_attempt": "2" if role == "github4" else None,
            "github_repository": comparator.GITHUB_REPOSITORY if role == "github4" else None,
            "github_workflow_ref": (
                f"{comparator.GITHUB_REPOSITORY}/"
                f"{comparator.GITHUB_WORKFLOW_PATH}@refs/heads/research/test"
                if role == "github4"
                else None
            ),
            "github_sha": "1" * 40 if role == "github4" else None,
        },
        "archive": {
            "custody_start": copy.deepcopy(custody),
            "custody_end": copy.deepcopy(custody),
            "completion_vector": vector,
            "completion_vector_sha256": bindings["completion_vector_sha256"],
            "statistics": statistics,
            "completion_statistics_sha256": bindings["completion_statistics_sha256"],
            "serial_parallel_match": True,
        },
        "formula": {
            "fixture_file_sha256": bindings["fixture_file_sha256"],
            "fixture_result_sha256": bindings["fixture_result_sha256"],
            "correctness_case_count": 64,
            "formula_correctness_sha256": bindings["formula_correctness_sha256"],
            "invalid_input_gate": {"passed": True, "unexpectedly_accepted": []},
        },
        "timing": {
            "warmup_endpoint_sha256": bindings["timing_endpoint_sha256"],
            "retained_endpoint_sha256": [bindings["timing_endpoint_sha256"]] * 5,
            "retained_seconds": [1.0, 1.1, 1.2, 1.3, 1.4],
            "threshold_applied": False,
        },
    }
    report["report_sha256"] = canonical_sha256(
        report, domain="EU26-01-PORTABILITY-PROFILE-V1"
    )
    return report


def make_attestation(
    github_profile: dict[str, object], report_file_sha256: str
) -> dict[str, object]:
    artifact_id = 987654
    record: dict[str, object] = {
        "schema_version": "1.0.0",
        "attestation_type": comparator.GITHUB_ATTESTATION_TYPE,
        "retrieval_method": "authenticated_github_api",
        "repository": comparator.GITHUB_REPOSITORY,
        "workflow_path": comparator.GITHUB_WORKFLOW_PATH,
        "head_sha": github_profile["git_sha_start"],
        "run_id": 123456,
        "run_attempt": 2,
        "artifact_id": artifact_id,
        "artifact_name": comparator.GITHUB_ARTIFACT_NAME,
        "artifact_expired": False,
        "report_member": comparator.GITHUB_REPORT_MEMBER,
        "report_sha256": report_file_sha256,
        "profile_report_sha256": github_profile["report_sha256"],
        "workflow_run_api_url": (
            f"https://api.github.com/repos/{comparator.GITHUB_REPOSITORY}/"
            "actions/runs/123456"
        ),
        "artifact_api_url": (
            f"https://api.github.com/repos/{comparator.GITHUB_REPOSITORY}/"
            f"actions/artifacts/{artifact_id}"
        ),
        "workflow_run_api_sha256": "a" * 64,
        "artifact_api_sha256": "b" * 64,
    }
    record["attestation_sha256"] = canonical_sha256(
        record, domain=comparator.GITHUB_ATTESTATION_DOMAIN
    )
    return record


class ComparatorTests(unittest.TestCase):
    def setUp(self):
        self.bindings = synthetic_bindings()

    def test_local_pair_passes_without_claiming_h5(self):
        result = comparator.compare_profiles(
            [
                make_profile("work4", self.bindings),
                make_profile("work8", self.bindings),
            ],
            self.bindings,
        )
        self.assertEqual(result["comparison_status"], "PASS_REQUIRED_LOCAL_PAIR")
        self.assertEqual(
            result["H5_cross_profile"]["status"],
            "NOT_EVALUATED_MISSING_GITHUB4",
        )
        self.assertFalse(result["pass_full_allowed"])

    def test_three_self_asserted_roles_do_not_evaluate_h5(self):
        profiles = [make_profile(role, self.bindings) for role in ("work4", "work8", "github4")]
        result = comparator.compare_profiles(profiles, self.bindings)
        self.assertEqual(
            result["comparison_status"],
            "NOT_EVALUATED_UNAUTHENTICATED_GITHUB4",
        )
        self.assertEqual(
            result["H5_cross_profile"]["status"],
            "NOT_EVALUATED_UNAUTHENTICATED_GITHUB4",
        )

    def test_three_required_roles_pass_h5_with_api_attestation(self):
        profiles = [make_profile(role, self.bindings) for role in ("work4", "work8", "github4")]
        report_file_sha256 = "9" * 64
        attestation = make_attestation(profiles[2], report_file_sha256)
        result = comparator.compare_profiles(
            profiles,
            self.bindings,
            github_attestation=attestation,
            report_file_sha256_by_role={"github4": report_file_sha256},
        )
        self.assertEqual(result["comparison_status"], "PASS_PORTABILITY")
        self.assertEqual(result["H5_cross_profile"]["status"], "PASS")
        self.assertEqual(
            result["github_role_authentication"],
            "PASS_SEPARATE_GITHUB_API_ATTESTATION",
        )

    def test_minimal_or_forged_github_profile_fails_closed(self):
        forged = {
            "profile_role": "github4",
            "hardware": {
                "github_actions": True,
                "github_run_id": "123456",
                "github_run_attempt": "2",
            },
        }
        with self.assertRaisesRegex(ValueError, "protocol or candidate"):
            comparator.compare_profiles(
                [
                    make_profile("work4", self.bindings),
                    make_profile("work8", self.bindings),
                    forged,
                ],
                self.bindings,
            )

    def test_minimal_api_attestation_fails_closed(self):
        profiles = [make_profile(role, self.bindings) for role in ("work4", "work8", "github4")]
        with self.assertRaisesRegex(ValueError, "non-exact schema"):
            comparator.compare_profiles(
                profiles,
                self.bindings,
                github_attestation={"artifact_id": 1},
                report_file_sha256_by_role={"github4": "9" * 64},
            )

    def test_attestation_cannot_bind_different_report_bytes(self):
        profiles = [make_profile(role, self.bindings) for role in ("work4", "work8", "github4")]
        attestation = make_attestation(profiles[2], "9" * 64)
        with self.assertRaisesRegex(ValueError, "report_sha256"):
            comparator.compare_profiles(
                profiles,
                self.bindings,
                github_attestation=attestation,
                report_file_sha256_by_role={"github4": "8" * 64},
            )

    def test_strict_json_rejects_duplicate_and_nonfinite_values(self):
        with tempfile.TemporaryDirectory() as directory:
            duplicate = Path(directory) / "duplicate.json"
            duplicate.write_text('{"profile_role":"work4","profile_role":"github4"}')
            nonfinite = Path(directory) / "nonfinite.json"
            nonfinite.write_text('{"timing":NaN}')
            for path in (duplicate, nonfinite):
                with self.subTest(path=path.name):
                    with self.assertRaisesRegex(ValueError, "strict JSON"):
                        comparator._read_object(path)

    def test_cleared_paper_block_fails_closed(self):
        profile = make_profile("work4", self.bindings)
        profile["paper_level_status"] = "PASS_FULL"
        profile["report_sha256"] = canonical_sha256(
            {key: value for key, value in profile.items() if key != "report_sha256"},
            domain="EU26-01-PORTABILITY-PROFILE-V1",
        )
        with self.assertRaisesRegex(ValueError, "paper-level block"):
            comparator.compare_profiles(
                [profile, make_profile("work8", self.bindings)], self.bindings
            )

    def test_forged_vector_content_fails_even_with_claimed_binding(self):
        profile = make_profile("work4", self.bindings)
        profile["archive"]["completion_vector"][0] += 1
        profile["report_sha256"] = canonical_sha256(
            {key: value for key, value in profile.items() if key != "report_sha256"},
            domain="EU26-01-PORTABILITY-PROFILE-V1",
        )
        with self.assertRaisesRegex(ValueError, "content digest"):
            comparator.compare_profiles(
                [profile, make_profile("work8", self.bindings)], self.bindings
            )

    def test_duplicate_roles_fail(self):
        with self.assertRaisesRegex(ValueError, "unique"):
            comparator.compare_profiles(
                [make_profile("work4", self.bindings), make_profile("work4", self.bindings)],
                self.bindings,
            )


if __name__ == "__main__":
    unittest.main()
