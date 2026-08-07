#!/usr/bin/env python3
"""Fail-closed H5 comparator for EU26-01 Work4/Work8/GitHub4 reports."""

from __future__ import annotations

import argparse
import copy
import json
import os
from pathlib import Path
import sys
from typing import Any


SCRIPT = Path(__file__).resolve()
CANDIDATE = SCRIPT.parents[2]
REPOSITORY = CANDIDATE.parents[1]
PYTHON_ENV = CANDIDATE / "environments" / "python"
sys.path.insert(0, str(PYTHON_ENV))

from tworateverify.canonical import (  # noqa: E402
    canonical_sha256,
    sha256_file,
    strict_json_load,
)


PROTOCOL_ID = "EU26-01-HW-PORTABILITY-v1"
PAPER_STATUS = "BLOCKED_SOURCE_NATIVE_REPLAY"
ALGORITHM2_CONFLICT = (
    "literal_one_based_pseudocode_4_low_6_high_vs_prose_and_source_5_low_5_high"
)
ROLE_WORKERS = {"work4": 4, "work8": 8, "github4": 4}
LOCAL_ROLES = {"work4", "work8"}
ALL_ROLES = set(ROLE_WORKERS)
GITHUB_REPOSITORY = "ChepaMaksym/GA-article-test"
GITHUB_WORKFLOW_PATH = ".github/workflows/eu26-01-validation.yml"
GITHUB_ARTIFACT_NAME = "eu26-01-github4-validation"
GITHUB_REPORT_MEMBER = "github4.json"
GITHUB_ATTESTATION_TYPE = "GITHUB_ACTIONS_ARTIFACT_API_v1"
GITHUB_ATTESTATION_DOMAIN = "EU26-01-GITHUB-API-ATTESTATION-V1"


def _outside_repository(value: str) -> Path:
    path = Path(value).resolve()
    try:
        path.relative_to(REPOSITORY.resolve())
    except ValueError:
        return path
    raise argparse.ArgumentTypeError("formal reports and outputs must be outside the repository")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("reports", nargs="+", type=_outside_repository)
    parser.add_argument("--github-attestation", type=_outside_repository)
    parser.add_argument("--output", required=True, type=_outside_repository)
    return parser.parse_args()


def _read_object(path: Path) -> dict[str, Any]:
    try:
        document = strict_json_load(path)
    except (OSError, ValueError) as error:
        raise ValueError(f"cannot load strict JSON report: {path}") from error
    if not isinstance(document, dict):
        raise ValueError("profile report root must be an object")
    return document


def _is_lower_hex(value: Any, length: int) -> bool:
    return (
        isinstance(value, str)
        and len(value) == length
        and all(character in "0123456789abcdef" for character in value)
    )


def _is_positive_integer(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value > 0


def _positive_decimal(value: Any) -> bool:
    return isinstance(value, str) and value.isascii() and value.isdecimal() and int(value) > 0


def _require_exact_keys(value: Any, expected: set[str], label: str) -> None:
    if not isinstance(value, dict) or set(value) != expected:
        observed = set(value) if isinstance(value, dict) else set()
        raise ValueError(
            f"{label}: non-exact schema; missing={sorted(expected - observed)}, "
            f"extra={sorted(observed - expected)}"
        )


def _validate_profile(profile: dict[str, Any], bindings: dict[str, Any]) -> str:
    role = profile.get("profile_role")
    if role not in ROLE_WORKERS:
        raise ValueError("profile role is not one of work4/work8/github4")
    if profile.get("protocol_id") != PROTOCOL_ID or profile.get("candidate_id") != "EU26-01":
        raise ValueError(f"{role}: protocol or candidate identity mismatch")
    if profile.get("scope") != "ARCHIVE_AND_FORMULA_VALIDATION_ONLY":
        raise ValueError(f"{role}: scope was widened")
    if profile.get("profile_status") != "PASS_PROFILE":
        raise ValueError(f"{role}: profile did not pass H0-H4")
    if profile.get("paper_level_status") != PAPER_STATUS:
        raise ValueError(f"{role}: paper-level block was cleared")
    if profile.get("eligibility_status") != "conditional_noneligible":
        raise ValueError(f"{role}: eligibility status changed")
    if profile.get("pass_full_allowed") is not False:
        raise ValueError(f"{role}: PASS_FULL prohibition changed")
    if profile.get("algorithm2_conflict") != ALGORITHM2_CONFLICT:
        raise ValueError(f"{role}: Algorithm 2 4/6-vs-5/5 conflict is absent")
    if (
        profile.get("requested_workers") != ROLE_WORKERS[role]
        or profile.get("requested_logical_cpus") != ROLE_WORKERS[role]
        or profile.get("timing_repeats") != 5
    ):
        raise ValueError(f"{role}: worker/CPU/timing profile mismatch")

    claimed_digest = profile.get("report_sha256")
    unsigned = copy.deepcopy(profile)
    unsigned.pop("report_sha256", None)
    calculated = canonical_sha256(unsigned, domain="EU26-01-PORTABILITY-PROFILE-V1")
    if claimed_digest != calculated:
        raise ValueError(f"{role}: report canonical digest mismatch")
    if (
        profile.get("git_sha_start") is None
        or profile.get("git_sha_start") != profile.get("git_sha_end")
        or profile.get("git_clean_start") is not True
        or profile.get("git_clean_end") is not True
        or profile.get("git_status_start") != []
        or profile.get("git_status_end") != []
        or profile.get("source_sha256_start") != profile.get("source_sha256_end")
    ):
        raise ValueError(f"{role}: Git/source provenance is incomplete")
    if profile.get("bindings") != bindings:
        raise ValueError(f"{role}: frozen digest bindings differ")

    gates = profile.get("gates")
    if not isinstance(gates, dict):
        raise ValueError(f"{role}: gates are missing")
    for gate in (
        "H0_provenance",
        "H1_worker_allocation",
        "H2_archive_identity",
        "H3_formula_invariants",
        "H4_repeatability",
    ):
        if gates.get(gate) != {"status": "PASS", "failures": []}:
            raise ValueError(f"{role}: {gate} is not an exact PASS")
    if gates.get("H5_cross_profile") != {
        "status": "NOT_EVALUATED_SINGLE_PROFILE",
        "failures": [],
    }:
        raise ValueError(f"{role}: single profile self-asserted H5")

    pool = profile.get("worker_pool", {})
    pids = pool.get("unique_worker_pids")
    if (
        pool.get("unique_worker_pid_count") != ROLE_WORKERS[role]
        or not isinstance(pids, list)
        or len(pids) != ROLE_WORKERS[role]
        or len(set(pids)) != ROLE_WORKERS[role]
        or pool.get("affinity_failure_pids") != []
        or pool.get("thread_limit_failure_pids") != []
        or pool.get("inconsistencies") != []
    ):
        raise ValueError(f"{role}: worker-pool evidence is incomplete")
    hardware = profile.get("hardware", {})
    if hardware.get("cpu_allocation_valid") is not True:
        raise ValueError(f"{role}: CPU allocation evidence is invalid")
    if role == "github4":
        workflow_ref = hardware.get("github_workflow_ref")
        if (
            hardware.get("exact_visible_cpu_set") is not True
            or hardware.get("github_actions") is not True
            or not _positive_decimal(hardware.get("github_run_id"))
            or not _positive_decimal(hardware.get("github_run_attempt"))
            or hardware.get("github_repository") != GITHUB_REPOSITORY
            or hardware.get("github_sha") != profile.get("git_sha_start")
            or not isinstance(workflow_ref, str)
            or not workflow_ref.startswith(
                f"{GITHUB_REPOSITORY}/{GITHUB_WORKFLOW_PATH}@"
            )
        ):
            raise ValueError("github4: complete GitHub Actions context claim is required")
    elif (
        hardware.get("github_actions") is not False
        or any(
            hardware.get(key) is not None
            for key in (
                "github_run_id",
                "github_run_attempt",
                "github_repository",
                "github_workflow_ref",
                "github_sha",
            )
        )
    ):
        raise ValueError(f"{role}: local profile contains a GitHub context claim")

    archive = profile.get("archive", {})
    custody_start = archive.get("custody_start", {})
    custody_end = archive.get("custody_end", {})
    if (
        custody_start.get("archive_sha256") != bindings.get("archive_sha256")
        or custody_end.get("archive_sha256") != bindings.get("archive_sha256")
        or custody_start.get("member_sha256") != bindings.get("member_sha256")
        or custody_end.get("member_sha256") != bindings.get("member_sha256")
        or custody_start.get("archive_sha256_end") != bindings.get("archive_sha256")
        or custody_end.get("archive_sha256_end") != bindings.get("archive_sha256")
        or custody_start.get("snapshot_sha256_end") != bindings.get("archive_sha256")
        or custody_end.get("snapshot_sha256_end") != bindings.get("archive_sha256")
        or archive.get("completion_vector_sha256") != bindings.get("completion_vector_sha256")
        or archive.get("completion_statistics_sha256")
        != bindings.get("completion_statistics_sha256")
        or archive.get("serial_parallel_match") is not True
    ):
        raise ValueError(f"{role}: archive identity/output binding is incomplete")
    vector = archive.get("completion_vector")
    if (
        not isinstance(vector, list)
        or len(vector) != 100
        or any(isinstance(value, bool) or not isinstance(value, int) for value in vector)
    ):
        raise ValueError(f"{role}: completion vector is invalid")
    statistics = archive.get("statistics", {})
    if canonical_sha256(vector, domain="EU26-01-COMPLETION-FES-V1") != archive.get(
        "completion_vector_sha256"
    ):
        raise ValueError(f"{role}: completion vector content digest mismatch")
    if canonical_sha256(
        statistics, domain="EU26-01-COMPLETION-STATISTICS-V1"
    ) != archive.get("completion_statistics_sha256"):
        raise ValueError(f"{role}: completion statistics content digest mismatch")
    if (
        statistics.get("count") != 100
        or statistics.get("mean_exact") != bindings.get("mean_exact")
        or statistics.get("population_variance_exact")
        != bindings.get("population_variance_exact")
        or statistics.get("mean_published_rounding") != 61624
        or statistics.get("population_variance_published_rounding") != "3.271e+08"
        or statistics.get("matches_published_mean") is not True
        or statistics.get("matches_published_population_variance") is not True
    ):
        raise ValueError(f"{role}: exact Table 1 statistics are incomplete")

    formula = profile.get("formula", {})
    if (
        formula.get("fixture_file_sha256") != bindings.get("fixture_file_sha256")
        or formula.get("fixture_result_sha256") != bindings.get("fixture_result_sha256")
        or formula.get("correctness_case_count") != 64
        or formula.get("formula_correctness_sha256")
        != bindings.get("formula_correctness_sha256")
        or formula.get("invalid_input_gate")
        != {"passed": True, "unexpectedly_accepted": []}
    ):
        raise ValueError(f"{role}: formula evidence is incomplete")
    timing = profile.get("timing", {})
    retained_digests = timing.get("retained_endpoint_sha256")
    retained_seconds = timing.get("retained_seconds")
    if (
        timing.get("warmup_endpoint_sha256") != bindings.get("timing_endpoint_sha256")
        or not isinstance(retained_digests, list)
        or retained_digests != [bindings.get("timing_endpoint_sha256")] * 5
        or not isinstance(retained_seconds, list)
        or len(retained_seconds) != 5
        or any(
            isinstance(value, bool) or not isinstance(value, (int, float)) or value < 0
            for value in retained_seconds
        )
        or timing.get("threshold_applied") is not False
    ):
        raise ValueError(f"{role}: timing/repeatability evidence is incomplete")
    return role


def validate_github_attestation(
    attestation: dict[str, Any],
    *,
    github_profile: dict[str, Any],
    github_report_file_sha256: str,
) -> None:
    """Bind a separately acquired authenticated GitHub API record to GitHub4.

    Environment variables inside ``github4.json`` are only self-asserted
    context. They never authorize H5 without this distinct record, which must
    be acquired from the authenticated workflow-run and artifact API objects.
    """

    expected_keys = {
        "schema_version",
        "attestation_type",
        "retrieval_method",
        "repository",
        "workflow_path",
        "head_sha",
        "run_id",
        "run_attempt",
        "artifact_id",
        "artifact_name",
        "artifact_expired",
        "report_member",
        "report_sha256",
        "profile_report_sha256",
        "workflow_run_api_url",
        "artifact_api_url",
        "workflow_run_api_sha256",
        "artifact_api_sha256",
        "attestation_sha256",
    }
    _require_exact_keys(attestation, expected_keys, "GitHub API attestation")
    claimed_attestation_sha256 = attestation.get("attestation_sha256")
    unsigned = copy.deepcopy(attestation)
    unsigned.pop("attestation_sha256", None)
    if claimed_attestation_sha256 != canonical_sha256(
        unsigned, domain=GITHUB_ATTESTATION_DOMAIN
    ):
        raise ValueError("GitHub API attestation canonical digest mismatch")

    hardware = github_profile["hardware"]
    scalar_expectations = {
        "schema_version": "1.0.0",
        "attestation_type": GITHUB_ATTESTATION_TYPE,
        "retrieval_method": "authenticated_github_api",
        "repository": GITHUB_REPOSITORY,
        "workflow_path": GITHUB_WORKFLOW_PATH,
        "head_sha": github_profile["git_sha_start"],
        "run_id": int(hardware["github_run_id"]),
        "run_attempt": int(hardware["github_run_attempt"]),
        "artifact_name": GITHUB_ARTIFACT_NAME,
        "artifact_expired": False,
        "report_member": GITHUB_REPORT_MEMBER,
        "report_sha256": github_report_file_sha256,
        "profile_report_sha256": github_profile["report_sha256"],
    }
    for key, expected in scalar_expectations.items():
        if attestation.get(key) != expected:
            raise ValueError(f"GitHub API attestation field differs: {key}")
    if not _is_lower_hex(github_report_file_sha256, 64):
        raise ValueError("GitHub4 report file SHA-256 is malformed")
    if not _is_positive_integer(attestation.get("artifact_id")):
        raise ValueError("GitHub API artifact ID must be a positive integer")
    for key in ("workflow_run_api_sha256", "artifact_api_sha256"):
        if not _is_lower_hex(attestation.get(key), 64):
            raise ValueError(f"GitHub API attestation field is malformed: {key}")
    run_id = attestation["run_id"]
    artifact_id = attestation["artifact_id"]
    expected_run_url = (
        f"https://api.github.com/repos/{GITHUB_REPOSITORY}/actions/runs/{run_id}"
    )
    expected_artifact_url = (
        f"https://api.github.com/repos/{GITHUB_REPOSITORY}/actions/artifacts/"
        f"{artifact_id}"
    )
    if attestation.get("workflow_run_api_url") != expected_run_url:
        raise ValueError("GitHub workflow-run API URL is not exact")
    if attestation.get("artifact_api_url") != expected_artifact_url:
        raise ValueError("GitHub artifact API URL is not exact")


def compare_profiles(
    profiles: list[dict[str, Any]],
    bindings: dict[str, Any],
    *,
    github_attestation: dict[str, Any] | None = None,
    report_file_sha256_by_role: dict[str, str] | None = None,
) -> dict[str, Any]:
    if len(profiles) not in (2, 3):
        raise ValueError("H5 comparator requires exactly two or three profiles")
    roles = [_validate_profile(profile, bindings) for profile in profiles]
    if len(set(roles)) != len(roles):
        raise ValueError("profile roles must be unique")
    role_set = set(roles)
    if len(profiles) == 2 and role_set != LOCAL_ROLES:
        raise ValueError("two-profile comparison is reserved for work4/work8")
    if len(profiles) == 3 and role_set != ALL_ROLES:
        raise ValueError("three-profile H5 requires work4/work8/github4")
    if github_attestation is not None and role_set != ALL_ROLES:
        raise ValueError("GitHub API attestation is only valid for the three-profile H5")

    by_role = {profile["profile_role"]: profile for profile in profiles}
    comparable_paths = (
        ("git_sha", lambda value: value["git_sha_start"]),
        ("source_sha256", lambda value: value["source_sha256_start"]),
        ("bindings", lambda value: value["bindings"]),
        ("archive_completion_vector", lambda value: value["archive"]["completion_vector"]),
        ("archive_completion_sha256", lambda value: value["archive"]["completion_vector_sha256"]),
        ("archive_statistics", lambda value: value["archive"]["statistics"]),
        ("archive_statistics_sha256", lambda value: value["archive"]["completion_statistics_sha256"]),
        ("fixture_file_sha256", lambda value: value["formula"]["fixture_file_sha256"]),
        ("fixture_result_sha256", lambda value: value["formula"]["fixture_result_sha256"]),
        ("formula_correctness_sha256", lambda value: value["formula"]["formula_correctness_sha256"]),
        ("timing_endpoint_sha256", lambda value: value["timing"]["warmup_endpoint_sha256"]),
    )
    pairwise: list[dict[str, Any]] = []
    mismatches: list[str] = []
    ordered_roles = sorted(roles)
    for left_index, left_role in enumerate(ordered_roles):
        for right_role in ordered_roles[left_index + 1 :]:
            fields: dict[str, bool] = {}
            for label, getter in comparable_paths:
                equal = getter(by_role[left_role]) == getter(by_role[right_role])
                fields[label] = equal
                if not equal:
                    mismatches.append(f"{left_role}:{right_role}:{label}")
            pairwise.append(
                {
                    "left": left_role,
                    "right": right_role,
                    "fields": fields,
                    "status": "PASS" if all(fields.values()) else "FAIL",
                }
            )

    full_h5_profiles_match = role_set == ALL_ROLES and not mismatches
    local_pair = role_set == LOCAL_ROLES and not mismatches
    github_authentication = "NOT_EVALUATED_CROSS_PROFILE_FAILURE"
    attestation_summary: dict[str, Any] | None = None
    if mismatches:
        comparison_status = "FAIL_CROSS_PROFILE"
        h5_status = "FAIL"
    elif full_h5_profiles_match and github_attestation is None:
        comparison_status = "NOT_EVALUATED_UNAUTHENTICATED_GITHUB4"
        h5_status = "NOT_EVALUATED_UNAUTHENTICATED_GITHUB4"
        github_authentication = "UNAUTHENTICATED_SELF_ASSERTED_PROFILE"
    elif full_h5_profiles_match:
        if report_file_sha256_by_role is None or "github4" not in report_file_sha256_by_role:
            raise ValueError("GitHub API attestation requires the actual github4 file digest")
        validate_github_attestation(
            github_attestation,
            github_profile=by_role["github4"],
            github_report_file_sha256=report_file_sha256_by_role["github4"],
        )
        comparison_status = "PASS_PORTABILITY"
        h5_status = "PASS"
        github_authentication = "PASS_SEPARATE_GITHUB_API_ATTESTATION"
        attestation_summary = {
            key: github_attestation[key]
            for key in (
                "repository",
                "workflow_path",
                "head_sha",
                "run_id",
                "run_attempt",
                "artifact_id",
                "artifact_name",
                "report_sha256",
                "attestation_sha256",
            )
        }
    elif local_pair:
        comparison_status = "PASS_REQUIRED_LOCAL_PAIR"
        h5_status = "NOT_EVALUATED_MISSING_GITHUB4"
        github_authentication = "NOT_EVALUATED_MISSING_GITHUB4"
    else:
        raise ValueError("unreachable profile-role combination")
    return {
        "schema_version": "1.0.0",
        "protocol_id": PROTOCOL_ID,
        "candidate_id": "EU26-01",
        "scope": "ARCHIVE_AND_FORMULA_VALIDATION_ONLY",
        "comparison_status": comparison_status,
        "H5_cross_profile": {"status": h5_status, "failures": sorted(mismatches)},
        "github_role_authentication": github_authentication,
        "github_api_attestation": attestation_summary,
        "paper_level_status": PAPER_STATUS,
        "eligibility_status": "conditional_noneligible",
        "pass_full_allowed": False,
        "algorithm2_conflict": ALGORITHM2_CONFLICT,
        "profile_roles": ordered_roles,
        "profile_report_sha256": {
            role: by_role[role]["report_sha256"] for role in ordered_roles
        },
        "bindings": bindings,
        "pairwise": pairwise,
    }


def _write_new(path: Path, document: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(
        path,
        os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_CLOEXEC", 0),
        0o600,
    )
    with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(document, handle, sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False)
        handle.write("\n")


def main() -> int:
    arguments = parse_args()
    bindings = _read_object(CANDIDATE / "config" / "hardware_expected_digests.json")
    profiles = [_read_object(path) for path in arguments.reports]
    report_file_sha256_by_role: dict[str, str] = {}
    for path, profile in zip(arguments.reports, profiles):
        role = profile.get("profile_role")
        if isinstance(role, str):
            if role in report_file_sha256_by_role:
                raise ValueError("profile roles must be unique")
            report_file_sha256_by_role[role] = sha256_file(path)
    attestation = (
        _read_object(arguments.github_attestation)
        if arguments.github_attestation is not None
        else None
    )
    result = compare_profiles(
        profiles,
        bindings,
        github_attestation=attestation,
        report_file_sha256_by_role=report_file_sha256_by_role,
    )
    result["report_sha256"] = canonical_sha256(
        result, domain="EU26-01-PORTABILITY-COMPARISON-V1"
    )
    _write_new(arguments.output, result)
    print(json.dumps({
        "comparison_status": result["comparison_status"],
        "H5_cross_profile": result["H5_cross_profile"]["status"],
        "paper_level_status": PAPER_STATUS,
        "report_sha256": result["report_sha256"],
    }, sort_keys=True))
    return 1 if result["comparison_status"] in {
        "FAIL_CROSS_PROFILE",
        "NOT_EVALUATED_UNAUTHENTICATED_GITHUB4",
    } else 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, TypeError, KeyError) as error:
        print(f"EU26-01 portability comparison failed closed: {error}", file=sys.stderr)
        raise SystemExit(2)
