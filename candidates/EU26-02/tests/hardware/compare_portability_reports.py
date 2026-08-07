#!/usr/bin/env python3
"""Evaluate EU26-02 H5 across Work-4, Work-8 and GitHub-4 reports."""

from __future__ import annotations

import argparse
import csv
import hashlib
import itertools
import json
import math
from pathlib import Path
from typing import Any


PROTOCOL_ID = "EU26-02-HW-PORTABILITY-v1"
PAPER_LEVEL_STATUS = "BLOCKED_MULTIPLE_SOURCE_CONFLICTS"
ARCHIVE_SHA256 = "1b7e8cf1ef637005bd994104f6e1ee520256ed387994b126bbe875a137632e41"
CANDIDATE = Path(__file__).resolve().parents[2]
REPOSITORY = CANDIDATE.parents[1]
EXPECTED_FORMULA_IDS = {
    f"deleter-small-seed{2602000 + index}" for index in range(64)
}
REQUIRED_SOURCE_PATHS = {
    ".github/workflows/eu26-02-validation.yml",
    "candidates/EU26-02/config/ahead_deleter_optimizer_config.json",
    "candidates/EU26-02/environments/matlab/ahead_deleter_initial_state.m",
    "candidates/EU26-02/environments/matlab/ahead_deleter_transition.m",
    "candidates/EU26-02/environments/python/aheadverify/__init__.py",
    "candidates/EU26-02/environments/python/aheadverify/archive.py",
    "candidates/EU26-02/environments/python/aheadverify/canonical.py",
    "candidates/EU26-02/environments/python/aheadverify/deleter.py",
    "candidates/EU26-02/environments/python/aheadverify/witness.py",
    "candidates/EU26-02/environments/python/run_archive_validation.py",
    "candidates/EU26-02/environments/python/run_selected_witness.py",
    "candidates/EU26-02/tests/hardware/compare_portability_reports.py",
    "candidates/EU26-02/tests/hardware/run_portability_suite.py",
    "registry/cohort_2026_12/hard_gate_assessments.json",
    "registry/cohort_2026_12/registry.json",
    "registry/cohort_2026_12/tests/run_registry_tests.py",
    "registry/cohort_2026_12/validate_registry.py",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("profiles", nargs="+", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    return parser.parse_args()


def _is_hex(value: Any, length: int) -> bool:
    return (
        isinstance(value, str)
        and len(value) == length
        and all(character in "0123456789abcdef" for character in value)
    )


def _sha256_value(value: Any) -> str:
    payload = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _expected_archive_ids() -> set[str]:
    fixture = CANDIDATE / "fixtures" / "published_table2_ahead_deleter.csv"
    with fixture.open(newline="", encoding="utf-8") as handle:
        values = {row["instance"] for row in csv.DictReader(handle)}
    if len(values) != 31:
        raise ValueError("frozen archive fixture must contain 31 unique instances")
    return values


def _require_case_rows(
    section: dict[str, Any], key: str, expected_ids: set[str], label: str
) -> list[dict[str, Any]]:
    rows = section.get("cases")
    if not isinstance(rows, list) or len(rows) != len(expected_ids):
        raise ValueError(f"{label} must retain exactly {len(expected_ids)} cases")
    ids = [row.get(key) for row in rows if isinstance(row, dict)]
    if len(ids) != len(rows) or set(ids) != expected_ids or len(set(ids)) != len(ids):
        raise ValueError(f"{label} case identities differ from the frozen set")
    for row in rows:
        digest = row.get("sha256")
        canonical = row.get("canonical_result")
        if not _is_hex(digest, 64) or digest != _sha256_value(canonical):
            raise ValueError(f"{label} case {row.get(key)!r} has an invalid digest")
    expected_aggregate = _sha256_value(
        sorted((str(row[key]), str(row["sha256"])) for row in rows)
    )
    if section.get("aggregate_sha256") != expected_aggregate:
        raise ValueError(f"{label} aggregate digest is invalid")
    return rows


def _profile_role(profile: dict[str, Any]) -> str | None:
    context = profile.get("hardware", {}).get("execution_context", {})
    cpus = profile.get("requested_logical_cpus")
    workers = profile.get("requested_workers")
    if cpus != workers or cpus not in (4, 8):
        return None
    if context.get("github_actions") is False and cpus == 4:
        return "work_4core"
    if context.get("github_actions") is False and cpus == 8:
        return "work_8core"
    if (
        context.get("github_actions") is True
        and cpus == 4
        and context.get("github_run_id")
        and context.get("github_run_attempt")
    ):
        return "github_actions_4core"
    return None


def _validate_profile(profile: dict[str, Any]) -> str:
    """Reject incomplete or self-asserted evidence before cross-profile comparison."""

    if not isinstance(profile, dict):
        raise ValueError("profile must be a JSON object")
    if profile.get("protocol_id") != PROTOCOL_ID:
        raise ValueError(f"profile must use {PROTOCOL_ID}")
    if profile.get("paper_level_status") != PAPER_LEVEL_STATUS:
        raise ValueError("profile cleared the mandatory paper-level block")
    if profile.get("profile_status") != "PASS_PROFILE":
        raise ValueError("profile did not pass its own H0-H4 gates")

    git_sha = profile.get("git_sha")
    provenance = profile.get("provenance_window", {})
    if not _is_hex(git_sha, 40) or provenance.get("git_sha_end") != git_sha:
        raise ValueError("Git SHA is missing or changed during execution")
    clean_state = {"untracked": [], "different_from_head": []}
    if profile.get("git_source_state") != clean_state:
        raise ValueError("profile sources were not tracked and clean at start")
    if provenance.get("git_source_state_end") != clean_state:
        raise ValueError("profile sources were not tracked and clean at end")

    source_hashes = profile.get("source_sha256")
    if not isinstance(source_hashes, dict) or not source_hashes:
        raise ValueError("source hash map must be nonempty")
    if not REQUIRED_SOURCE_PATHS <= set(source_hashes):
        missing = sorted(REQUIRED_SOURCE_PATHS - set(source_hashes))
        raise ValueError(f"source hash map is missing required paths: {missing}")
    if any(
        not isinstance(path, str) or not _is_hex(digest, 64)
        for path, digest in source_hashes.items()
    ):
        raise ValueError("source hash map contains an invalid path or SHA-256")
    if provenance.get("source_sha256_end") != source_hashes:
        raise ValueError("source hashes changed during execution")

    archive = profile.get("archive", {})
    if (
        archive.get("provided") is not True
        or archive.get("required") is not True
        or archive.get("expected_sha256") != ARCHIVE_SHA256
        or archive.get("sha256") != ARCHIVE_SHA256
        or archive.get("sha256_end") != ARCHIVE_SHA256
        or archive.get("instance_count") != 31
    ):
        raise ValueError("pinned archive identity/count evidence is incomplete")
    temporary_sha = archive.get("temporary_uncompressed_tar_sha256")
    if not _is_hex(temporary_sha, 64) or (
        archive.get("temporary_uncompressed_tar_sha256_end") != temporary_sha
    ):
        raise ValueError("temporary parser archive identity changed or is invalid")

    gates = profile.get("gates", {})
    for gate in (
        "H0_provenance",
        "H1_worker_allocation",
        "H2_archive_identity",
        "H3_formula_invariants",
        "H4_repeatability",
    ):
        if gates.get(gate, {}).get("status") != "PASS":
            raise ValueError(f"{gate} is not PASS")
    if gates.get("H5_cross_profile", {}).get("status") != "NOT_EVALUATED_SINGLE_PROFILE":
        raise ValueError("single profile must not self-assert H5")
    if profile.get("provenance_failures") != []:
        raise ValueError("profile retains provenance failures")

    role = _profile_role(profile)
    if role is None:
        raise ValueError("profile does not match a required Work/GitHub role")
    workers = profile["requested_workers"]
    pool = profile.get("worker_pool", {})
    pids = pool.get("unique_worker_pids")
    if (
        pool.get("failures") != []
        or pool.get("affinity_failure_pids") != []
        or pool.get("thread_limit_failure_pids") != []
        or pool.get("unique_worker_pid_count") != workers
        or not isinstance(pids, list)
        or len(pids) != workers
        or len(set(pids)) != workers
    ):
        raise ValueError("worker allocation evidence is incomplete")
    cpu = profile.get("cpu_allocation_evidence", {})
    if cpu.get("valid") is not True or cpu.get("requested_logical_cpus") != workers:
        raise ValueError("CPU allocation evidence is invalid")

    formula = profile.get("formula_correctness", {})
    if (
        formula.get("case_count") != 64
        or formula.get("serial_parallel_mismatches") != []
        or formula.get("invariant_failures") != []
        or formula.get("invalid_input_gate", {}).get("passed") is not True
    ):
        raise ValueError("formula correctness evidence is incomplete")
    _require_case_rows(formula, "case_id", EXPECTED_FORMULA_IDS, "formula")

    archive_section = profile.get("archive_correctness", {})
    if (
        archive_section.get("status") != "EVALUATED"
        or archive_section.get("instance_count") != 31
        or archive_section.get("serial_parallel_mismatches") != []
        or archive_section.get("aggregate_match") is not True
        or archive_section.get("serial_aggregate")
        != archive_section.get("parallel_aggregate")
        or archive_section.get("parallel_aggregate", {}).get("status")
        != "PASS_AGGREGATE_EXACT"
    ):
        raise ValueError("archive correctness evidence is incomplete")
    _require_case_rows(
        archive_section, "instance", _expected_archive_ids(), "archive"
    )

    timing = profile.get("timing", {})
    retained_seconds = timing.get("retained_batch_seconds")
    retained_digests = timing.get("timed_endpoint_digests")
    warm_digest = timing.get("warmup_endpoint_digest")
    if (
        not isinstance(retained_seconds, list)
        or len(retained_seconds) != 5
        or any(
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not math.isfinite(float(value))
            or value <= 0
            for value in retained_seconds
        )
        or not isinstance(retained_digests, list)
        or len(retained_digests) != 5
        or not _is_hex(warm_digest, 64)
        or any(digest != warm_digest for digest in retained_digests)
        or timing.get("repeatable_endpoints") is not True
        or timing.get("formula_case_count") != 1024
        or timing.get("archive_case_count") != 31
    ):
        raise ValueError("five-batch repeatability evidence is incomplete")
    return role


def _indexed_cases(report: dict[str, Any], section: str, key: str) -> dict[str, Any]:
    return {
        str(row[key]): row.get("canonical_result")
        for row in report.get(section, {}).get("cases", [])
    }


def _compare_pair(left: dict[str, Any], right: dict[str, Any]) -> dict[str, Any]:
    formula_left = _indexed_cases(left, "formula_correctness", "case_id")
    formula_right = _indexed_cases(right, "formula_correctness", "case_id")
    archive_left = _indexed_cases(left, "archive_correctness", "instance")
    archive_right = _indexed_cases(right, "archive_correctness", "instance")

    formula_ids_match = set(formula_left) == set(formula_right)
    archive_ids_match = set(archive_left) == set(archive_right)
    formula_mismatches = (
        sorted(
            case_id
            for case_id in formula_left
            if formula_left[case_id] != formula_right[case_id]
        )
        if formula_ids_match
        else ["CASE_ID_SET_MISMATCH"]
    )
    archive_mismatches = (
        sorted(
            instance
            for instance in archive_left
            if archive_left[instance] != archive_right[instance]
        )
        if archive_ids_match
        else ["INSTANCE_SET_MISMATCH"]
    )
    source_hashes_match = left.get("source_sha256") == right.get("source_sha256")
    archive_hashes_match = (
        left.get("archive", {}).get("sha256")
        == right.get("archive", {}).get("sha256")
        and bool(left.get("archive", {}).get("sha256"))
        and left.get("archive", {}).get("temporary_uncompressed_tar_sha256")
        == right.get("archive", {}).get("temporary_uncompressed_tar_sha256")
        and bool(
            left.get("archive", {}).get("temporary_uncompressed_tar_sha256")
        )
    )
    archive_aggregates_match = (
        left.get("archive_correctness", {}).get("parallel_aggregate")
        == right.get("archive_correctness", {}).get("parallel_aggregate")
    )
    passed = (
        source_hashes_match
        and archive_hashes_match
        and archive_aggregates_match
        and formula_ids_match
        and archive_ids_match
        and not formula_mismatches
        and not archive_mismatches
    )
    return {
        "left": left["profile_label"],
        "right": right["profile_label"],
        "status": "PASS_BITWISE" if passed else "INCONCLUSIVE",
        "source_hashes_match": source_hashes_match,
        "archive_hashes_match": archive_hashes_match,
        "archive_aggregates_match": archive_aggregates_match,
        "formula_case_ids_match": formula_ids_match,
        "archive_instance_ids_match": archive_ids_match,
        "formula_mismatch_count": len(formula_mismatches),
        "archive_mismatch_count": len(archive_mismatches),
        "formula_mismatches": formula_mismatches,
        "archive_mismatches": archive_mismatches,
    }


def _profile_roles(profiles: list[dict[str, Any]]) -> dict[str, bool]:
    roles = {
        "work_4core": False,
        "work_8core": False,
        "github_actions_4core": False,
    }
    for profile in profiles:
        role = _profile_role(profile)
        if role is not None:
            roles[role] = True
    return roles


def main() -> int:
    args = parse_args()
    if len(args.profiles) != 3:
        raise SystemExit("exactly three Work4/Work8/GitHub4 reports are required")
    if args.output.resolve() in {path.resolve() for path in args.profiles}:
        raise SystemExit("--output must not overwrite an input profile")
    profiles = [json.loads(path.read_text(encoding="utf-8")) for path in args.profiles]
    try:
        profile_roles = [_validate_profile(profile) for profile in profiles]
    except ValueError as error:
        raise SystemExit(f"invalid profile evidence: {error}") from error
    if len(set(profile_roles)) != 3:
        raise SystemExit("the three profiles must provide distinct required roles")
    labels = [profile.get("profile_label") for profile in profiles]
    if any(not isinstance(label, str) or not label for label in labels):
        raise SystemExit("profile labels must be nonempty strings")
    if len(set(labels)) != len(labels):
        raise SystemExit("profile labels must be unique")

    pairs = [
        _compare_pair(left, right)
        for left, right in itertools.combinations(profiles, 2)
    ]
    profile_failures = [
        profile["profile_label"]
        for profile in profiles
        if profile.get("profile_status") != "PASS_PROFILE"
    ]
    inconclusive_pairs = [
        f"{pair['left']}::{pair['right']}"
        for pair in pairs
        if pair["status"] != "PASS_BITWISE"
    ]
    roles = _profile_roles(profiles)
    required_roles_present = all(roles.values())
    h5_pass = not profile_failures and not inconclusive_pairs and required_roles_present
    report = {
        "protocol_id": PROTOCOL_ID,
        "verification_scope": "ARCHIVE_AND_FORMULA_HARDWARE_VALIDATION_ONLY",
        "paper_level_status": PAPER_LEVEL_STATUS,
        "portability_status": "PASS_PORTABILITY" if h5_pass else "INCONCLUSIVE",
        "H5_cross_profile": "PASS_BITWISE" if h5_pass else "INCONCLUSIVE",
        "profiles": labels,
        "profile_failures": profile_failures,
        "required_profile_roles": roles,
        "required_profile_roles_present": required_roles_present,
        "pairwise_correctness": pairs,
        "inconclusive_pairs": inconclusive_pairs,
        "throughput": {
            profile["profile_label"]: {
                "workers": profile.get("requested_workers"),
                "logical_cpus": profile.get("requested_logical_cpus"),
                "median_batch_seconds": profile.get("timing", {}).get(
                    "median_batch_seconds"
                ),
                "observed_mhz": profile.get("hardware", {}).get(
                    "cpu_mhz_snapshot"
                ),
            }
            for profile in profiles
        },
        "ghz_effect_status": "NOT_IDENTIFIABLE_FROM_UNCONTROLLED_VM_METADATA",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if h5_pass else 1


if __name__ == "__main__":
    raise SystemExit(main())
