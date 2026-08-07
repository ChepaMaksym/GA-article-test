from __future__ import annotations

import copy
import hashlib
import importlib.util
from pathlib import Path
import sys
import unittest


CANDIDATE = Path(__file__).resolve().parents[2]
PYTHON = CANDIDATE / "environments" / "python"
sys.path.insert(0, str(PYTHON))

from banditverify.canonical import canonical_json, formula_digest, record_digest, sha256_file  # noqa: E402
from banditverify.controller import (  # noqa: E402
    standard_deviation_witness,
    tile_boundary_witness,
    tie_ambiguity_witness,
)
from banditverify.matlab_report import canonical_matlab_payload, payload_sha256  # noqa: E402
from banditverify.provenance import (  # noqa: E402
    git_head,
    matlab_source_hashes,
    repository_root,
    source_hashes,
)
from banditverify.security import EvidenceValidationError  # noqa: E402


COMPARATOR = CANDIDATE / "tests" / "hardware" / "compare_portability_reports.py"
SPEC = importlib.util.spec_from_file_location("usa2604_comparator", COMPARATOR)
assert SPEC and SPEC.loader
module = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = module
SPEC.loader.exec_module(module)

REPOSITORY = repository_root(CANDIDATE)
HEAD = git_head(REPOSITORY)
EXPECTED_RECORDS = module._expected_records()
EXPECTED_SOURCES = source_hashes(REPOSITORY)


def _hardware(role: str, workers: int, head: str) -> dict:
    before = list(range(max(workers, 8 if role != "github_actions_4core" else workers)))
    target = before[:workers]
    github = role == "github_actions_4core"
    repository = "owner/repo" if github else None
    ref = "refs/heads/test" if github else None
    return {
        "platform": "Linux-test",
        "system": "Linux",
        "machine": "x86_64",
        "python": "3.12-test",
        "cpu_model": "test-cpu",
        "cpu_mhz_snapshot": {"minimum": 1000.0, "median": 1100.0, "maximum": 1200.0},
        "ghz_controlled": False,
        "os_cpu_count": len(before),
        "affinity_before": before,
        "target_affinity": target,
        "affinity_after": target,
        "cgroup_cpu_max": "max 100000",
        "cgroup_cpuset": "0-7",
        "cgroup_memory_max": "max",
        "thread_environment": {name: "1" for name in module.THREAD_ENV},
        "execution_context": {
            "github_actions": github,
            "github_run_id": "123" if github else None,
            "github_run_attempt": "1" if github else None,
            "runner_name": "GitHub Actions 1" if github else None,
            "github_repository": repository,
            "github_workflow_ref": (
                f"{repository}/{module.GITHUB_WORKFLOW_PATH}@{ref}" if github else None
            ),
            "github_sha": head if github else None,
            "github_ref": ref,
            "github_server_url": "https://github.com" if github else None,
        },
    }


def _h2(records: list[dict], head: str) -> dict:
    payload = next(row["result"] for row in records if row["case_id"] == "controller-fixed-tape")
    sources = matlab_source_hashes(CANDIDATE)
    report = {
        "schema_version": "USA26-04-MATLAB-H2-REPORT-v1",
        "protocol_id": module.PROTOCOL_ID,
        "git_sha": head,
        "implementation": "matlab_octave_clean_room",
        "engine": {"name": "GNU Octave", "version": "9.1.0"},
        "matlab_sources": [
            {"path": name, "sha256": digest} for name, digest in sorted(sources.items())
        ],
        "fixture_path": "fixtures/fixed_controller_tape.json",
        "fixture_sha256": sha256_file(CANDIDATE / "fixtures" / "fixed_controller_tape.json"),
        "payload": payload,
        "canonical_payload": canonical_matlab_payload(payload),
        "canonical_payload_sha256": payload_sha256(payload),
    }
    return {
        "status": "PASS_CROSS_ENV_FIXED_TAPE",
        "report_origin": "RUNNER_INVOKED_ENGINE",
        "report_sha256": "1" * 64,
        "state_provenance": module.STATE_PROVENANCE,
        "exact_mismatches": [],
        "numeric_mismatches": [],
        "paper_level_status": module.PAPER_STATUS,
        "published_result_status": module.PUBLISHED_STATUS,
        "git_sha": head,
        "engine": report["engine"],
        "engine_executable": "/usr/bin/octave",
        "engine_executable_sha256": "2" * 64,
        "engine_version_probe_sha256": "3" * 64,
        "matlab_source_sha256": sources,
        "fixture_sha256": report["fixture_sha256"],
        "canonical_payload_sha256": report["canonical_payload_sha256"],
        "matlab_report_canonical_sha256": hashlib.sha256(canonical_json(report)).hexdigest(),
        "matlab_report": report,
    }


def profile(role: str, *, complete_h2: bool = False) -> dict:
    head = HEAD
    records = copy.deepcopy(EXPECTED_RECORDS)
    digest = formula_digest(records)
    workers = 8 if role == "work_8core" else 4
    h2 = (
        _h2(records, head)
        if complete_h2
        else {
            "status": "NOT_EVALUATED_MATLAB_REPORT_ABSENT",
            "state_provenance": module.STATE_PROVENANCE,
            "paper_level_status": module.PAPER_STATUS,
        }
    )
    repeats = [1.0, 2.0, 3.0, 4.0, 5.0]
    return {
        "protocol_id": module.PROTOCOL_ID,
        "verification_scope": module.SCOPE,
        "paper_level_status": module.PAPER_STATUS,
        "published_result_status": module.PUBLISHED_STATUS,
        "registry_status": module.REGISTRY_STATUS,
        "fixed_controller_state_provenance": module.STATE_PROVENANCE,
        "profile_label": module.ROLE_LABELS[role],
        "profile_status": (
            "PASS_PROFILE_H0_H4"
            if complete_h2
            else "INCONCLUSIVE_H2_MATLAB_NOT_EVALUATED"
        ),
        "requested_workers": workers,
        "requested_logical_cpus": workers,
        "git_sha": head,
        "source_sha256": EXPECTED_SOURCES,
        "protocol_summary": {
            "protocol_id": module.PROTOCOL_ID,
            "scope": module.SCOPE,
            "paper_level_status": module.PAPER_STATUS,
            "published_result_status": module.PUBLISHED_STATUS,
            "registry_status": module.REGISTRY_STATUS,
            "source_identity_count": 7,
            "absence_count": 15,
            "descriptive_target_count": 6,
            "executable_target_count": 0,
        },
        "hardware": _hardware(role, workers, head),
        "gates": {
            "H0_provenance": {
                "status": "PASS_PROVENANCE_AND_ABSENCE",
                "source_state_before": [],
                "source_state_after": [],
                "head_stable": True,
                "source_hashes_stable": True,
            },
            "H1_formula": {"status": "PASS_LOCAL_FORMULAS"},
            "H2_fixed_tape": h2,
            "H3_adversarial": {
                "status": "PASS_FAIL_CLOSED_AND_AMBIGUITIES_RETAINED",
                "rejection_checks": {
                    "nonfinite_objective": True,
                    "linear_log_domain": True,
                    "printed_eq2_singleton": True,
                },
                "boundary": tile_boundary_witness(),
                "tie": tie_ambiguity_witness([0.0, 0.0, 0.0, 0.0], 0.0),
                "standard_deviation": standard_deviation_witness(),
                "paper_level_status": module.PAPER_STATUS,
            },
            "H4_batch": {
                "status": "PASS_SERIAL_PARALLEL_REPEATABILITY",
                "serial_digest": digest,
                "warmup_digest": digest,
                "repeat_digests": [digest] * 5,
                "worker_pid_counts": [workers] * 6,
            },
            "H5_cross_profile": {"status": "NOT_EVALUATED_SINGLE_PROFILE"},
        },
        "correctness": {
            "case_ids": [row["case_id"] for row in records],
            "record_sha256": {row["case_id"]: record_digest(row) for row in records},
            "aggregate_digest": digest,
            "cases": records,
        },
        "timing": {
            "serial_seconds": 1.0,
            "warmup_parallel_seconds": 1.0,
            "retained_parallel_seconds": repeats,
            "retained_repeat_count": 5,
            "median_parallel_seconds": 3.0,
            "median_cases_per_second": 8.0 / 3.0,
            "timing_gate": "DESCRIPTIVE_ONLY",
        },
        "claim_limits": {
            "full_ga_implemented": False,
            "table1_executed": False,
            "published_result_equivalence_tested": False,
            "pass_full_allowed": False,
            "ghz_effect_identifiable": False,
        },
    }


def api_record(head: str, report_sha256: str) -> dict:
    return {
        "schema_version": "USA26-04-GITHUB-API-PROVENANCE-v1",
        "provider": "api.github.com",
        "repository": "owner/repo",
        "workflow_path": module.GITHUB_WORKFLOW_PATH,
        "head_sha": head,
        "run_id": 123,
        "run_attempt": 1,
        "artifact_id": 456,
        "artifact_name": module.GITHUB_ARTIFACT_NAME,
        "report_sha256": report_sha256,
        "api_url": "https://api.github.com/repos/owner/repo/actions/artifacts/456",
        "retrieved_at_utc": "2026-08-07T12:00:00Z",
    }


class HardwareComparatorTests(unittest.TestCase):
    def test_two_work_profiles_match_but_remain_incomplete(self) -> None:
        result = module.compare_reports(
            {"work_4core": profile("work_4core"), "work_8core": profile("work_8core")}
        )
        self.assertEqual(result["pairwise"][0]["status"], "PASS_STRICT_FORMULA_MATCH")
        self.assertEqual(result["H5_status"], "INCOMPLETE_REQUIRED_PROFILE")
        self.assertEqual(result["overall_status"], "INCONCLUSIVE_ENGINEERING_PORTABILITY")

    def test_github_json_without_api_attestation_is_incomplete(self) -> None:
        profiles = {role: profile(role, complete_h2=True) for role in module.ROLES}
        result = module.compare_reports(profiles)
        self.assertEqual(result["H5_status"], "INCOMPLETE_UNAUTHENTICATED_GITHUB_PROFILE")
        self.assertFalse(result["github_api_metadata_binding"]["metadata_binding_valid"])

    def test_exact_api_binding_can_pass_engineering_only(self) -> None:
        profiles = {role: profile(role, complete_h2=True) for role in module.ROLES}
        head = profiles["work_4core"]["git_sha"]
        report_sha = "a" * 64
        result = module.compare_reports(
            profiles,
            github_api_provenance=api_record(head, report_sha),
            github_report_sha256=report_sha,
        )
        self.assertEqual(result["H5_status"], "PASS_FORMULA_PORTABILITY")
        self.assertEqual(result["overall_status"], "PASS_ENGINEERING_FORMULA_PORTABILITY")
        self.assertEqual(result["paper_level_status"], "BLOCKED_G5_G9")
        self.assertFalse(result["claim_limits"]["published_result_equivalence_tested"])

    def test_original_minimal_forged_profiles_are_rejected(self) -> None:
        forged = {
            "protocol_id": module.PROTOCOL_ID,
            "profile_label": "work-4core",
            "source_sha256": {},
            "correctness": {"case_ids": ["fake"], "aggregate_digest": "fake"},
        }
        with self.assertRaises(EvidenceValidationError):
            module.compare_reports({"work_4core": forged, "work_8core": forged})

    def test_case_set_record_and_digest_mutations_fail_closed(self) -> None:
        baseline = profile("work_4core")
        mutations = []
        duplicate = copy.deepcopy(baseline)
        duplicate["correctness"]["case_ids"][1] = duplicate["correctness"]["case_ids"][0]
        mutations.append(duplicate)
        missing = copy.deepcopy(baseline)
        missing["correctness"]["cases"].pop()
        mutations.append(missing)
        extra = copy.deepcopy(baseline)
        extra["correctness"]["case_ids"].append("extra")
        mutations.append(extra)
        typed = copy.deepcopy(baseline)
        typed["correctness"]["cases"][0]["iterations"] = 20000.0
        typed["correctness"]["record_sha256"] = {
            row["case_id"]: record_digest(row) for row in typed["correctness"]["cases"]
        }
        typed["correctness"]["aggregate_digest"] = formula_digest(
            typed["correctness"]["cases"]
        )
        mutations.append(typed)
        bad_hash = copy.deepcopy(baseline)
        bad_hash["correctness"]["record_sha256"][baseline["correctness"]["case_ids"][0]] = "0" * 64
        mutations.append(bad_hash)
        for mutation in mutations:
            with self.subTest(case=len(mutation["correctness"].get("case_ids", []))):
                with self.assertRaises(EvidenceValidationError):
                    module.compare_reports(
                        {"work_4core": mutation, "work_8core": profile("work_8core")}
                    )

    def test_provenance_gate_status_and_type_promotions_fail_closed(self) -> None:
        mutations: list[dict] = []
        for path, value in (
            (("git_sha",), "0" * 40),
            (("source_sha256",), {}),
            (("paper_level_status",), "PASS_FULL"),
            (("fixed_controller_state_provenance",), "article_state"),
            (("profile_status",), "PASS_PROFILE_H0_H4"),
            (("gates", "H0_provenance", "head_stable"), 1),
            (("gates", "H3_adversarial", "rejection_checks", "nonfinite_objective"), 1),
            (("gates", "H4_batch", "worker_pid_counts", 0), 4.0),
            (("gates", "H5_cross_profile", "status"), "PASS_FORMULA_PORTABILITY"),
            (("claim_limits", "table1_executed"), 0),
            (("timing", "retained_repeat_count"), 5.0),
            (("timing", "median_parallel_seconds"), "3.0"),
            (("timing", "median_cases_per_second"), 1.0),
        ):
            mutation = copy.deepcopy(profile("work_4core"))
            cursor = mutation
            for key in path[:-1]:
                cursor = cursor[key]
            cursor[path[-1]] = value
            mutations.append(mutation)
        for index, mutation in enumerate(mutations):
            with self.subTest(index=index):
                with self.assertRaises(EvidenceValidationError):
                    module.compare_reports(
                        {"work_4core": mutation, "work_8core": profile("work_8core")}
                    )

    def test_role_spoof_and_h2_report_forgery_fail_closed(self) -> None:
        role_spoof = profile("work_4core")
        role_spoof["hardware"]["execution_context"]["github_actions"] = True
        with self.assertRaises(EvidenceValidationError):
            module.compare_reports(
                {"work_4core": role_spoof, "work_8core": profile("work_8core")}
            )

        copied = profile("work_4core", complete_h2=True)
        copied["gates"]["H2_fixed_tape"]["matlab_report"]["git_sha"] = "0" * 40
        with self.assertRaises(EvidenceValidationError):
            module.compare_reports(
                {"work_4core": copied, "work_8core": profile("work_8core")}
            )

        minimal_h2 = profile("work_4core")
        minimal_h2["gates"]["H2_fixed_tape"] = {"status": "PASS_CROSS_ENV_FIXED_TAPE"}
        minimal_h2["profile_status"] = "PASS_PROFILE_H0_H4"
        with self.assertRaises(EvidenceValidationError):
            module.compare_reports(
                {"work_4core": minimal_h2, "work_8core": profile("work_8core")}
            )

    def test_api_metadata_mismatch_never_passes_h5(self) -> None:
        profiles = {role: profile(role, complete_h2=True) for role in module.ROLES}
        report_sha = "a" * 64
        record = api_record(profiles["work_4core"]["git_sha"], report_sha)
        for key, value in (
            ("head_sha", "0" * 40),
            ("run_id", 999),
            ("run_attempt", 2),
            ("artifact_id", 999),
            ("artifact_name", "forged"),
            ("report_sha256", "b" * 64),
            ("workflow_path", ".github/workflows/other.yml"),
        ):
            mutation = copy.deepcopy(record)
            mutation[key] = value
            result = module.compare_reports(
                profiles,
                github_api_provenance=mutation,
                github_report_sha256=report_sha,
            )
            with self.subTest(key=key):
                self.assertEqual(
                    result["H5_status"], "INCOMPLETE_UNAUTHENTICATED_GITHUB_PROFILE"
                )


if __name__ == "__main__":
    unittest.main()
