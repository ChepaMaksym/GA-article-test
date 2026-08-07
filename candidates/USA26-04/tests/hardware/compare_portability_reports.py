#!/usr/bin/env python3
"""Strictly compare provenance-bound USA26-04 formula profiles.

GitHub role authenticity is not inferable from JSON. This offline comparator
can validate an API-record metadata binding, but formal H5 remains blocked on
an external authenticated API retrieval/download/hash step.
"""

from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import math
from datetime import datetime
from pathlib import Path
import re
import statistics
import sys
from typing import Any


SCRIPT = Path(__file__).resolve()
CANDIDATE = SCRIPT.parents[2]
sys.path.insert(0, str(CANDIDATE / "environments" / "python"))

from banditverify.canonical import (  # noqa: E402
    canonical_json,
    formula_digest,
    record_digest,
    sha256_file,
)
from banditverify.cases import EXPECTED_CASE_IDS, execute_case, load_matrix  # noqa: E402
from banditverify.controller import (  # noqa: E402
    standard_deviation_witness,
    tile_boundary_witness,
    tie_ambiguity_witness,
)
from banditverify.matlab_report import (  # noqa: E402
    payload_sha256,
    validate_matlab_report,
)
from banditverify.provenance import (  # noqa: E402
    git_head,
    repository_root,
    source_git_state,
    source_hashes,
)
from banditverify.security import (  # noqa: E402
    EvidenceValidationError,
    require_exact_keys,
    require_int,
    require_string,
    strict_json_load,
)


REPOSITORY = repository_root(CANDIDATE)
PROTOCOL_ID = "USA26-04-FORMULA-PORTABILITY-v1"
PAPER_STATUS = "BLOCKED_G5_G9"
PUBLISHED_STATUS = "INCONCLUSIVE_PUBLISHED_RESULT"
SCOPE = "FORMULA_AND_AMBIGUITY_VALIDATION_ONLY"
REGISTRY_STATUS = "conditional_noneligible"
STATE_PROVENANCE = "synthetic_fixture_not_article_state"
EXPECTED_CASE_ID_TUPLE = tuple(sorted(EXPECTED_CASE_IDS))
THREAD_ENV = (
    "OMP_NUM_THREADS",
    "OPENBLAS_NUM_THREADS",
    "MKL_NUM_THREADS",
    "NUMEXPR_NUM_THREADS",
    "VECLIB_MAXIMUM_THREADS",
)
ROLES = ("work_4core", "work_8core", "github_actions_4core")
ROLE_LABELS = {
    "work_4core": "work-4core",
    "work_8core": "work-8core",
    "github_actions_4core": "github-actions-4core",
}
GITHUB_WORKFLOW_PATH = ".github/workflows/usa26-04-validation.yml"
GITHUB_ARTIFACT_NAME = "usa26-04-github-4core-formula-profile"
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
UTC_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--work-4", type=Path)
    parser.add_argument("--work-8", type=Path)
    parser.add_argument("--github-4", type=Path)
    parser.add_argument("--github-api-provenance", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    return parser.parse_args()


def _digest(value: Any, context: str) -> str:
    text = require_string(value, context)
    if not SHA256_RE.fullmatch(text):
        raise EvidenceValidationError(f"{context} must be a lowercase SHA-256")
    return text


def _positive_number(value: Any, context: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise EvidenceValidationError(f"{context} must be numeric")
    result = float(value)
    if not math.isfinite(result) or result <= 0.0:
        raise EvidenceValidationError(f"{context} must be finite and positive")
    return result


def _require_type_exact(value: Any, expected: Any, context: str) -> None:
    if canonical_json(value) != canonical_json(expected):
        raise EvidenceValidationError(f"{context} differs from the frozen typed value")


def _expected_records() -> list[dict[str, Any]]:
    cases = load_matrix(CANDIDATE / "config" / "hardware_formula_matrix.csv")
    return [execute_case(case, CANDIDATE) for case in cases]


def _validate_protocol_summary(value: Any) -> None:
    expected = {
        "protocol_id": PROTOCOL_ID,
        "scope": SCOPE,
        "paper_level_status": PAPER_STATUS,
        "published_result_status": PUBLISHED_STATUS,
        "registry_status": REGISTRY_STATUS,
        "source_identity_count": 7,
        "absence_count": 15,
        "descriptive_target_count": 6,
        "executable_target_count": 0,
    }
    _require_type_exact(value, expected, "profile.protocol_summary")


def _validate_hardware(value: Any, role: str, requested: int, head: str) -> None:
    hardware = require_exact_keys(
        value,
        {
            "platform",
            "system",
            "machine",
            "python",
            "cpu_model",
            "cpu_mhz_snapshot",
            "ghz_controlled",
            "os_cpu_count",
            "affinity_before",
            "target_affinity",
            "affinity_after",
            "cgroup_cpu_max",
            "cgroup_cpuset",
            "cgroup_memory_max",
            "thread_environment",
            "execution_context",
        },
        "profile.hardware",
    )
    if hardware["system"] != "Linux" or hardware["ghz_controlled"] is not False:
        raise EvidenceValidationError("profile hardware must be Linux with uncontrolled GHz")
    require_string(hardware["platform"], "hardware.platform")
    require_string(hardware["machine"], "hardware.machine")
    require_string(hardware["python"], "hardware.python")
    if hardware["cpu_model"] is not None:
        require_string(hardware["cpu_model"], "hardware.cpu_model")
    mhz = require_exact_keys(
        hardware["cpu_mhz_snapshot"], {"minimum", "median", "maximum"}, "cpu_mhz_snapshot"
    )
    for key, item in mhz.items():
        if item is not None:
            _positive_number(item, f"cpu_mhz_snapshot.{key}")
    require_int(hardware["os_cpu_count"], "hardware.os_cpu_count", minimum=1)
    target = hardware["target_affinity"]
    before = hardware["affinity_before"]
    after = hardware["affinity_after"]
    for name, affinity in (("before", before), ("target", target), ("after", after)):
        if (
            not isinstance(affinity, list)
            or not affinity
            or not all(
                isinstance(item, int) and not isinstance(item, bool) and item >= 0
                for item in affinity
            )
            or affinity != sorted(set(affinity))
        ):
            raise EvidenceValidationError(
                f"{name} affinity must be a sorted unique list of nonnegative CPU IDs"
            )
    if len(target) != requested or len(set(target)) != requested:
        raise EvidenceValidationError("target affinity does not match requested CPUs")
    if after != target or target != before[:requested]:
        raise EvidenceValidationError("profile affinity evidence is inconsistent")
    for key in ("cgroup_cpu_max", "cgroup_cpuset", "cgroup_memory_max"):
        if hardware[key] is not None and not isinstance(hardware[key], str):
            raise EvidenceValidationError(f"hardware.{key} must be string or null")
    thread_environment = require_exact_keys(
        hardware["thread_environment"], THREAD_ENV, "hardware.thread_environment"
    )
    if any(value != "1" for value in thread_environment.values()):
        raise EvidenceValidationError("numerical thread limits are not all one")

    context = require_exact_keys(
        hardware["execution_context"],
        {
            "github_actions",
            "github_run_id",
            "github_run_attempt",
            "runner_name",
            "github_repository",
            "github_workflow_ref",
            "github_sha",
            "github_ref",
            "github_server_url",
        },
        "hardware.execution_context",
    )
    is_github = role == "github_actions_4core"
    if context["github_actions"] is not is_github:
        raise EvidenceValidationError(f"{role} has incompatible GitHub execution flag")
    if is_github:
        if hardware["os_cpu_count"] != requested or before != target:
            raise EvidenceValidationError("GitHub profile did not expose exactly four CPUs")
        for key in (
            "github_run_id",
            "github_run_attempt",
            "runner_name",
            "github_repository",
            "github_workflow_ref",
            "github_sha",
            "github_ref",
            "github_server_url",
        ):
            require_string(context[key], f"execution_context.{key}")
        if context["github_sha"] != head:
            raise EvidenceValidationError("GitHub context SHA differs from profile/current HEAD")
        if context["github_server_url"] != "https://github.com":
            raise EvidenceValidationError("GitHub server URL is not canonical")
        if not re.fullmatch(r"[1-9][0-9]{0,19}", context["github_run_id"]):
            raise EvidenceValidationError("GitHub run ID must be a positive decimal string")
        if not re.fullmatch(r"[1-9][0-9]{0,9}", context["github_run_attempt"]):
            raise EvidenceValidationError("GitHub run attempt must be a positive decimal string")
        expected_workflow_ref = (
            f"{context['github_repository']}/{GITHUB_WORKFLOW_PATH}@{context['github_ref']}"
        )
        if context["github_workflow_ref"] != expected_workflow_ref:
            raise EvidenceValidationError(
                "GitHub workflow ref is not the exact frozen workflow/ref"
            )
    else:
        for key in (
            "github_run_id",
            "github_run_attempt",
            "runner_name",
            "github_repository",
            "github_workflow_ref",
            "github_sha",
            "github_ref",
            "github_server_url",
        ):
            if context[key] is not None:
                raise EvidenceValidationError(f"work profile unexpectedly sets {key}")


def _validate_h2(value: Any, head: str, expected_payload_digest: str) -> str:
    if not isinstance(value, dict):
        raise EvidenceValidationError("H2_fixed_tape must be an object")
    status = value.get("status")
    if status == "NOT_EVALUATED_MATLAB_REPORT_ABSENT":
        expected_absent = {
            "status": status,
            "state_provenance": STATE_PROVENANCE,
            "paper_level_status": PAPER_STATUS,
        }
        _require_type_exact(value, expected_absent, "absent H2 report")
        return status
    if status not in {
        "NOT_EVALUATED_EXTERNAL_NATIVE_RUNTIME_AUTH_REQUIRED",
        "NOT_EVALUATED_UNAUTHENTICATED_EXTERNAL_MATLAB_REPORT",
    }:
        raise EvidenceValidationError(
            "profile contains a failed or impermissible offline H2 status"
        )
    h2 = require_exact_keys(
        value,
        {
            "status",
            "content_validation_status",
            "report_origin",
            "report_sha256",
            "state_provenance",
            "exact_mismatches",
            "numeric_mismatches",
            "paper_level_status",
            "published_result_status",
            "git_sha",
            "engine",
            "engine_executable",
            "engine_executable_sha256",
            "engine_version_probe_sha256",
            "matlab_source_sha256",
            "fixture_sha256",
            "canonical_payload_sha256",
            "matlab_report_canonical_sha256",
            "matlab_report",
        },
        "H2_fixed_tape",
    )
    if status == "NOT_EVALUATED_EXTERNAL_NATIVE_RUNTIME_AUTH_REQUIRED":
        if h2["report_origin"] != "RUNNER_INVOKED_ENGINE_LOCAL_SELF_ATTESTED":
            raise EvidenceValidationError("native-content H2 origin is not local self-attestation")
        if h2["content_validation_status"] != "PASS_CROSS_ENV_FIXED_TAPE_CONTENT":
            raise EvidenceValidationError("native-content H2 did not retain a content match")
        require_string(h2["engine_executable"], "H2.engine_executable")
        _digest(h2["engine_executable_sha256"], "H2.engine_executable_sha256")
        _digest(h2["engine_version_probe_sha256"], "H2.engine_version_probe_sha256")
    else:
        if h2["report_origin"] != "EXTERNAL_UNAUTHENTICATED":
            raise EvidenceValidationError("diagnostic H2 origin is not explicitly unauthenticated")
        if any(
            h2[key] is not None
            for key in (
                "engine_executable",
                "engine_executable_sha256",
                "engine_version_probe_sha256",
            )
        ):
            raise EvidenceValidationError("external diagnostic asserted runner-only engine data")
        if h2["content_validation_status"] not in {
            "PASS_CROSS_ENV_FIXED_TAPE_CONTENT",
            "FAIL_CROSS_ENV_FIXED_TAPE_CONTENT",
        }:
            raise EvidenceValidationError("external diagnostic content status is invalid")
    for key in (
        "report_sha256",
        "fixture_sha256",
        "canonical_payload_sha256",
        "matlab_report_canonical_sha256",
    ):
        _digest(h2[key], f"H2_fixed_tape.{key}")
    if h2["git_sha"] != head or h2["state_provenance"] != STATE_PROVENANCE:
        raise EvidenceValidationError("H2 Git/state provenance mismatch")
    if h2["paper_level_status"] != PAPER_STATUS or h2["published_result_status"] != PUBLISHED_STATUS:
        raise EvidenceValidationError("H2 attempted scientific status promotion")
    for key in ("exact_mismatches", "numeric_mismatches"):
        mismatches = h2[key]
        if (
            not isinstance(mismatches, list)
            or not all(isinstance(item, str) and item for item in mismatches)
            or len(mismatches) != len(set(mismatches))
        ):
            raise EvidenceValidationError(f"H2 {key} must be a unique string array")
    if status == "NOT_EVALUATED_EXTERNAL_NATIVE_RUNTIME_AUTH_REQUIRED" and (
        h2["exact_mismatches"] != [] or h2["numeric_mismatches"] != []
    ):
        raise EvidenceValidationError("native-content match retains mismatches")
    metadata = validate_matlab_report(h2["matlab_report"], CANDIDATE, head)
    if h2["engine"] != metadata["engine"]:
        raise EvidenceValidationError("H2 engine metadata differs from embedded MATLAB report")
    if h2["matlab_source_sha256"] != metadata["matlab_source_sha256"]:
        raise EvidenceValidationError("H2 MATLAB source map differs from current checkout")
    fixture_digest = sha256_file(CANDIDATE / "fixtures" / "fixed_controller_tape.json")
    if (
        h2["fixture_sha256"] != metadata["fixture_sha256"]
        or metadata["fixture_sha256"] != fixture_digest
    ):
        raise EvidenceValidationError("H2 fixture digest differs from current checkout")
    if h2["canonical_payload_sha256"] != metadata["canonical_payload_sha256"]:
        raise EvidenceValidationError("H2 payload metadata differs from embedded report")
    if (
        status == "NOT_EVALUATED_EXTERNAL_NATIVE_RUNTIME_AUTH_REQUIRED"
        and h2["canonical_payload_sha256"] != expected_payload_digest
    ):
        raise EvidenceValidationError("H2 payload digest differs from current Python transition")
    embedded_digest = hashlib.sha256(canonical_json(h2["matlab_report"])).hexdigest()
    if h2["matlab_report_canonical_sha256"] != embedded_digest:
        raise EvidenceValidationError("embedded MATLAB report digest mismatch")
    return status


def _validate_gates(
    value: Any,
    aggregate: str,
    workers: int,
    head: str,
    expected_payload_digest: str,
) -> str:
    gates = require_exact_keys(
        value,
        {"H0_provenance", "H1_formula", "H2_fixed_tape", "H3_adversarial", "H4_batch", "H5_cross_profile"},
        "profile.gates",
    )
    expected_h0 = {
        "status": "PASS_PROVENANCE_AND_ABSENCE",
        "source_state_before": [],
        "source_state_after": [],
        "head_stable": True,
        "source_hashes_stable": True,
    }
    _require_type_exact(gates["H0_provenance"], expected_h0, "H0 profile provenance")
    _require_type_exact(
        gates["H1_formula"], {"status": "PASS_LOCAL_FORMULAS"}, "H1 local formula"
    )
    h2_status = _validate_h2(
        gates["H2_fixed_tape"], head, expected_payload_digest
    )
    expected_h3 = {
        "status": "PASS_FAIL_CLOSED_AND_AMBIGUITIES_RETAINED",
        "rejection_checks": {
            "nonfinite_objective": True,
            "linear_log_domain": True,
            "printed_eq2_singleton": True,
        },
        "boundary": tile_boundary_witness(),
        "tie": tie_ambiguity_witness([0.0, 0.0, 0.0, 0.0], 0.0),
        "standard_deviation": standard_deviation_witness(),
        "paper_level_status": PAPER_STATUS,
    }
    _require_type_exact(gates["H3_adversarial"], expected_h3, "H3 adversarial payload")
    h4 = require_exact_keys(
        gates["H4_batch"],
        {"status", "serial_digest", "warmup_digest", "repeat_digests", "worker_pid_counts"},
        "H4_batch",
    )
    if h4["status"] != "PASS_SERIAL_PARALLEL_REPEATABILITY":
        raise EvidenceValidationError("H4 batch status did not pass")
    if h4["serial_digest"] != aggregate or h4["warmup_digest"] != aggregate:
        raise EvidenceValidationError("H4 serial/warmup digest mismatch")
    if h4["repeat_digests"] != [aggregate] * 5:
        raise EvidenceValidationError("H4 must retain exactly five matching repeat digests")
    if (
        not isinstance(h4["worker_pid_counts"], list)
        or not all(
            isinstance(item, int) and not isinstance(item, bool)
            for item in h4["worker_pid_counts"]
        )
        or h4["worker_pid_counts"] != [workers] * 6
    ):
        raise EvidenceValidationError("H4 worker PID counts must match warmup plus five repeats")
    _require_type_exact(
        gates["H5_cross_profile"],
        {"status": "NOT_EVALUATED_SINGLE_PROFILE"},
        "single-profile H5 status",
    )
    return h2_status


def _validate_timing(value: Any) -> None:
    timing = require_exact_keys(
        value,
        {
            "serial_seconds",
            "warmup_parallel_seconds",
            "retained_parallel_seconds",
            "retained_repeat_count",
            "median_parallel_seconds",
            "median_cases_per_second",
            "timing_gate",
        },
        "profile.timing",
    )
    serial = _positive_number(timing["serial_seconds"], "timing.serial_seconds")
    warmup = _positive_number(timing["warmup_parallel_seconds"], "timing.warmup_parallel_seconds")
    del serial, warmup
    repeats = timing["retained_parallel_seconds"]
    if not isinstance(repeats, list) or len(repeats) != 5:
        raise EvidenceValidationError("timing must retain exactly five repeats")
    normalized = [
        _positive_number(item, f"timing.retained_parallel_seconds[{index}]")
        for index, item in enumerate(repeats)
    ]
    if require_int(
        timing["retained_repeat_count"], "timing.retained_repeat_count", minimum=1
    ) != 5:
        raise EvidenceValidationError("timing retained repeat count must be five")
    median = _positive_number(
        timing["median_parallel_seconds"], "timing.median_parallel_seconds"
    )
    if not math.isclose(
        median, statistics.median(normalized), rel_tol=0.0, abs_tol=1e-15
    ):
        raise EvidenceValidationError("timing median is inconsistent with retained repeats")
    throughput = _positive_number(
        timing["median_cases_per_second"], "timing.median_cases_per_second"
    )
    if not math.isclose(
        throughput,
        len(EXPECTED_CASE_ID_TUPLE) / median,
        rel_tol=1e-15,
        abs_tol=0.0,
    ):
        raise EvidenceValidationError("timing throughput is inconsistent with case count/median")
    if timing["timing_gate"] != "DESCRIPTIVE_ONLY":
        raise EvidenceValidationError("timing cannot be an outcome gate")


def validate_profile(
    profile: Any,
    role: str,
    head: str,
    expected_sources: dict[str, str],
    expected_records: list[dict[str, Any]],
) -> dict[str, Any]:
    profile = require_exact_keys(
        profile,
        {
            "protocol_id",
            "verification_scope",
            "paper_level_status",
            "published_result_status",
            "registry_status",
            "fixed_controller_state_provenance",
            "profile_label",
            "profile_status",
            "requested_workers",
            "requested_logical_cpus",
            "git_sha",
            "source_sha256",
            "protocol_summary",
            "hardware",
            "gates",
            "correctness",
            "timing",
            "claim_limits",
        },
        f"profile[{role}]",
    )
    expected_top = {
        "protocol_id": PROTOCOL_ID,
        "verification_scope": SCOPE,
        "paper_level_status": PAPER_STATUS,
        "published_result_status": PUBLISHED_STATUS,
        "registry_status": REGISTRY_STATUS,
        "fixed_controller_state_provenance": STATE_PROVENANCE,
        "git_sha": head,
    }
    for key, expected in expected_top.items():
        if profile[key] != expected:
            raise EvidenceValidationError(f"profile[{role}].{key} differs from current contract")
    if profile["profile_label"] != ROLE_LABELS[role]:
        raise EvidenceValidationError(f"profile[{role}] label is not the frozen role label")
    requested = 8 if role == "work_8core" else 4
    if (
        require_int(profile["requested_workers"], f"profile[{role}].requested_workers")
        != requested
        or require_int(
            profile["requested_logical_cpus"],
            f"profile[{role}].requested_logical_cpus",
        )
        != requested
    ):
        raise EvidenceValidationError(f"profile[{role}] worker/CPU count mismatch")
    if not isinstance(profile["source_sha256"], dict) or not profile["source_sha256"]:
        raise EvidenceValidationError(f"profile[{role}] source map is empty")
    if profile["source_sha256"] != expected_sources:
        raise EvidenceValidationError(f"profile[{role}] source map differs from current checkout")
    _validate_protocol_summary(profile["protocol_summary"])
    _validate_hardware(profile["hardware"], role, requested, head)

    correctness = require_exact_keys(
        profile["correctness"],
        {"case_ids", "record_sha256", "aggregate_digest", "cases"},
        "profile.correctness",
    )
    case_ids = correctness["case_ids"]
    if not isinstance(case_ids, list) or tuple(case_ids) != EXPECTED_CASE_ID_TUPLE:
        raise EvidenceValidationError("profile case IDs are missing, duplicated, extra, or out of order")
    records = correctness["cases"]
    if not isinstance(records, list) or len(records) != len(EXPECTED_CASE_ID_TUPLE):
        raise EvidenceValidationError("profile must contain exactly eight formula records")
    actual_ids = [record.get("case_id") if isinstance(record, dict) else None for record in records]
    if tuple(actual_ids) != EXPECTED_CASE_ID_TUPLE or len(actual_ids) != len(set(actual_ids)):
        raise EvidenceValidationError("formula record case set is incomplete or duplicated")
    if canonical_json(records) != canonical_json(expected_records):
        raise EvidenceValidationError("formula records differ from recomputation at current checkout")
    expected_record_hashes = {
        record["case_id"]: record_digest(record) for record in expected_records
    }
    if correctness["record_sha256"] != expected_record_hashes:
        raise EvidenceValidationError("per-record digest map differs from recomputation")
    aggregate = formula_digest(expected_records)
    if correctness["aggregate_digest"] != aggregate:
        raise EvidenceValidationError("aggregate formula digest differs from recomputation")

    controller_payload = next(
        record["result"]
        for record in expected_records
        if record["case_id"] == "controller-fixed-tape"
    )
    h2_status = _validate_gates(
        profile["gates"],
        aggregate,
        requested,
        head,
        payload_sha256(controller_payload),
    )
    expected_profile_status = (
        "INCONCLUSIVE_H2_EXTERNAL_NATIVE_RUNTIME_AUTH_REQUIRED"
        if h2_status == "NOT_EVALUATED_EXTERNAL_NATIVE_RUNTIME_AUTH_REQUIRED"
        else "INCONCLUSIVE_H2_MATLAB_NOT_EVALUATED"
    )
    if profile["profile_status"] != expected_profile_status:
        raise EvidenceValidationError("profile status is inconsistent with H0-H4 gates")
    _validate_timing(profile["timing"])
    expected_claim_limits = {
        "full_ga_implemented": False,
        "table1_executed": False,
        "published_result_equivalence_tested": False,
        "pass_full_allowed": False,
        "ghz_effect_identifiable": False,
    }
    _require_type_exact(profile["claim_limits"], expected_claim_limits, "profile claim limits")
    return profile


def _validate_api_provenance(
    value: Any,
    github_profile: dict[str, Any],
    head: str,
    report_sha256: str,
) -> tuple[bool, str]:
    try:
        _digest(report_sha256, "supplied GitHub report SHA-256")
        record = require_exact_keys(
            value,
            {
                "schema_version",
                "provider",
                "repository",
                "workflow_path",
                "head_sha",
                "run_id",
                "run_attempt",
                "artifact_id",
                "artifact_name",
                "report_sha256",
                "api_url",
                "retrieved_at_utc",
            },
            "github_api_provenance",
        )
        if record["schema_version"] != "USA26-04-GITHUB-API-PROVENANCE-v1":
            raise EvidenceValidationError("API provenance schema mismatch")
        if record["provider"] != "api.github.com":
            raise EvidenceValidationError("API provenance provider mismatch")
        repository = require_string(record["repository"], "api.repository")
        if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repository):
            raise EvidenceValidationError("API repository has invalid owner/name syntax")
        if record["workflow_path"] != GITHUB_WORKFLOW_PATH or record["head_sha"] != head:
            raise EvidenceValidationError("API workflow/head binding mismatch")
        run_id = require_int(record["run_id"], "api.run_id", minimum=1)
        run_attempt = require_int(record["run_attempt"], "api.run_attempt", minimum=1)
        artifact_id = require_int(record["artifact_id"], "api.artifact_id", minimum=1)
        if record["artifact_name"] != GITHUB_ARTIFACT_NAME:
            raise EvidenceValidationError("API artifact name mismatch")
        _digest(record["report_sha256"], "api.report_sha256")
        if record["report_sha256"] != report_sha256:
            raise EvidenceValidationError("API report digest does not bind supplied GitHub report")
        expected_url = f"https://api.github.com/repos/{repository}/actions/artifacts/{artifact_id}"
        if record["api_url"] != expected_url:
            raise EvidenceValidationError("API artifact URL mismatch")
        if not isinstance(record["retrieved_at_utc"], str) or not UTC_RE.fullmatch(record["retrieved_at_utc"]):
            raise EvidenceValidationError("API retrieval timestamp must be UTC second precision")
        try:
            datetime.strptime(record["retrieved_at_utc"], "%Y-%m-%dT%H:%M:%SZ")
        except ValueError as exc:
            raise EvidenceValidationError("API retrieval timestamp is not a real UTC date") from exc
        context = github_profile["hardware"]["execution_context"]
        if context["github_repository"] != repository:
            raise EvidenceValidationError("API/profile repository mismatch")
        if context["github_sha"] != head:
            raise EvidenceValidationError("API/profile head mismatch")
        if context["github_run_id"] != str(run_id) or context["github_run_attempt"] != str(run_attempt):
            raise EvidenceValidationError("API/profile run or attempt mismatch")
        if GITHUB_WORKFLOW_PATH not in context["github_workflow_ref"]:
            raise EvidenceValidationError("API/profile workflow mismatch")
        return True, "API_METADATA_BINDING_VALID_BUT_NOT_EXTERNALLY_AUTHENTICATED"
    except EvidenceValidationError as exc:
        return False, str(exc)


def compare_reports(
    profiles_by_role: dict[str, Any],
    *,
    github_api_provenance: Any | None = None,
    github_report_sha256: str | None = None,
    repository: Path = REPOSITORY,
) -> dict[str, Any]:
    if not profiles_by_role or not set(profiles_by_role) <= set(ROLES):
        raise EvidenceValidationError("profiles must be explicitly assigned to frozen roles")
    if len(profiles_by_role) < 2:
        raise EvidenceValidationError("at least two explicitly assigned profiles are required")
    if source_git_state(repository):
        raise EvidenceValidationError("current checkout source scope must be clean")
    head = git_head(repository)
    expected_sources = source_hashes(repository)
    expected_records = _expected_records()
    validated = {
        role: validate_profile(profile, role, head, expected_sources, expected_records)
        for role, profile in profiles_by_role.items()
    }
    labels = [profile["profile_label"] for profile in validated.values()]
    if len(labels) != len(set(labels)):
        raise EvidenceValidationError("profile labels must be unique")

    pairs = []
    for (left_role, left), (right_role, right) in itertools.combinations(validated.items(), 2):
        checks = {
            "git_sha_match": left["git_sha"] == right["git_sha"] == head,
            "source_hashes_match": left["source_sha256"] == right["source_sha256"] == expected_sources,
            "case_ids_match": left["correctness"]["case_ids"] == right["correctness"]["case_ids"],
            "record_hashes_match": left["correctness"]["record_sha256"]
            == right["correctness"]["record_sha256"],
            "aggregate_digest_match": left["correctness"]["aggregate_digest"]
            == right["correctness"]["aggregate_digest"],
            "paper_status_match": left["paper_level_status"] == right["paper_level_status"] == PAPER_STATUS,
            "state_provenance_match": left["fixed_controller_state_provenance"]
            == right["fixed_controller_state_provenance"]
            == STATE_PROVENANCE,
        }
        pairs.append(
            {
                "left_role": left_role,
                "right_role": right_role,
                "left": left["profile_label"],
                "right": right["profile_label"],
                "status": "PASS_STRICT_FORMULA_MATCH"
                if all(checks.values())
                else "INCONCLUSIVE_STRICT_MISMATCH",
                "checks": checks,
            }
        )
    strict_pairs_pass = all(pair["status"] == "PASS_STRICT_FORMULA_MATCH" for pair in pairs)
    required_roles = {role: role in validated for role in ROLES}

    github_api_binding_valid = False
    github_authentication_reason = "GITHUB_PROFILE_OR_API_PROVENANCE_ABSENT"
    github_profile = validated.get("github_actions_4core")
    if github_profile is not None:
        if github_api_provenance is None or github_report_sha256 is None:
            github_authentication_reason = "GITHUB_JSON_ALONE_CANNOT_AUTHENTICATE_ARTIFACT_OR_RUN"
        else:
            github_api_binding_valid, github_authentication_reason = _validate_api_provenance(
                github_api_provenance, github_profile, head, github_report_sha256
            )
    profile_gate_failures = [profile["profile_label"] for profile in validated.values()]
    if not strict_pairs_pass:
        h5_status = "INCONCLUSIVE_STRICT_MISMATCH"
    else:
        h5_status = "NOT_EVALUATED_EXTERNAL_GITHUB_AUTH_REQUIRED"
    overall_status = "INCONCLUSIVE_ENGINEERING_PORTABILITY"
    return {
        "protocol_id": PROTOCOL_ID,
        "verification_scope": SCOPE,
        "paper_level_status": PAPER_STATUS,
        "published_result_status": PUBLISHED_STATUS,
        "registry_status": REGISTRY_STATUS,
        "fixed_controller_state_provenance": STATE_PROVENANCE,
        "current_git_sha": head,
        "profiles": {role: profile["profile_label"] for role, profile in validated.items()},
        "required_roles": required_roles,
        "pairwise": pairs,
        "profile_gate_failures": profile_gate_failures,
        "github_api_metadata_binding": {
            "metadata_binding_valid": github_api_binding_valid,
            "external_authentication_established": False,
            "reason": github_authentication_reason,
            "external_authenticity_boundary": (
                "The comparator validates API-record metadata binding only. The provenance "
                "record must be retrieved and authenticated independently from the GitHub API; "
                "profile or attestation JSON alone cannot establish run/artifact authenticity."
            ),
        },
        "H5_status": h5_status,
        "overall_status": overall_status,
        "claim_limits": {
            "full_ga_implemented": False,
            "table1_executed": False,
            "published_result_equivalence_tested": False,
            "paper_status_can_be_cleared": False,
        },
    }


def main() -> int:
    args = parse_args()
    paths = {
        role: path
        for role, path in (
            ("work_4core", args.work_4),
            ("work_8core", args.work_8),
            ("github_actions_4core", args.github_4),
        )
        if path is not None
    }
    output_path = args.output.resolve()
    input_paths = {path.resolve() for path in paths.values()}
    if args.github_api_provenance is not None:
        input_paths.add(args.github_api_provenance.resolve())
    if output_path in input_paths:
        raise SystemExit("comparison output cannot overwrite an input artifact")
    if output_path.is_relative_to(REPOSITORY):
        raise SystemExit("comparison artifacts must be written outside the repository")
    profiles = {role: strict_json_load(path) for role, path in paths.items()}
    api_record = (
        strict_json_load(args.github_api_provenance)
        if args.github_api_provenance is not None
        else None
    )
    github_report_digest = (
        sha256_file(args.github_4) if args.github_4 is not None else None
    )
    report = compare_reports(
        profiles,
        github_api_provenance=api_record,
        github_report_sha256=github_report_digest,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report, indent=2, sort_keys=True, allow_nan=False))
    return 0 if report["overall_status"].startswith("PASS_") else 1


if __name__ == "__main__":
    raise SystemExit(main())
