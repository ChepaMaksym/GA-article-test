#!/usr/bin/env python3
"""Strictly compare EU26-05 Work4, Work8 and GitHub4 formula reports."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from typing import Any


SCRIPT = Path(__file__).resolve()
CANDIDATE = SCRIPT.parents[2]
REPOSITORY = CANDIDATE.parents[1]
PYTHON_ENV = CANDIDATE / "environments" / "python"
sys.path.insert(0, str(PYTHON_ENV))

from eu2605.canonical import (  # noqa: E402
    canonical_bytes,
    sha256_value,
    strict_json_load,
)
from eu2605.core import (  # noqa: E402
    H0_SOURCE_STATUS,
    PAPER_LEVEL_STATUS,
    PROFILE,
    SOURCE_BYTE_STATUS,
    SOURCE_FREEZE_STATUS,
)
from eu2605.portability import expected_parallel_cases, scientific_payload  # noqa: E402
from run_portability_suite import (  # noqa: E402
    PROFILE_STATUS,
    PROTOCOL_ID,
    PUBLISHED_RESULT_STATUS,
    current_source_hashes,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("profiles", nargs="+", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--allow-incomplete", action="store_true")
    parser.add_argument("--github-attestation", type=Path)
    return parser.parse_args()


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _git_head() -> str:
    completed = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=REPOSITORY,
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    return completed.stdout.strip()


def _require_exact_keys(value: Any, expected: set[str], label: str) -> None:
    if not isinstance(value, dict) or set(value) != expected:
        missing = sorted(expected - set(value)) if isinstance(value, dict) else sorted(expected)
        extra = sorted(set(value) - expected) if isinstance(value, dict) else []
        raise ValueError(f"{label}: non-exact schema; missing={missing}, extra={extra}")


def _is_hex(value: Any, length: int) -> bool:
    return (
        isinstance(value, str)
        and len(value) == length
        and all(character in "0123456789abcdef" for character in value)
    )


def _frozen_config() -> tuple[dict[str, Any], dict[str, Any]]:
    contract = strict_json_load(CANDIDATE / "config" / "validation_contract.json")
    profiles = strict_json_load(CANDIDATE / "config" / "hardware_profiles.json")
    return contract, profiles


def validate_report(
    report: dict[str, Any],
    *,
    source_hashes: dict[str, str],
    git_head: str,
    contract: dict[str, Any],
    profile_config: dict[str, Any],
) -> None:
    _require_exact_keys(
        report,
        {
            "schema_version",
            "protocol_id",
            "profile_label",
            "requested_workers",
            "requested_logical_cpus",
            "timing_repeats",
            "git_head",
            "git_clean_at_start",
            "source_hashes",
            "source_digest",
            "contract_digest",
            "fixture_digest",
            "scientific_digest",
            "scientific_payload_bytes",
            "scientific_payload",
            "repeat_scientific_digests",
            "profile_status",
            "scope",
            "paper_level_status",
            "source_byte_status",
            "source_freeze_status",
            "h0_source_status",
            "published_result_status",
            "published_27_of_30_evaluated",
            "author_code_replayed",
            "cec2017_reproduced",
            "pass_full_claimed",
            "gates",
            "hardware",
            "hardware_role_authentication",
            "contract_strongest_allowed",
        },
        "profile report",
    )
    label = report.get("profile_label")
    expected = next(
        (item for item in profile_config.get("profiles", []) if item.get("label") == label),
        None,
    )
    if expected is None:
        raise ValueError(f"unknown profile label: {label!r}")
    if report.get("schema_version") != "1.0.0" or report.get("protocol_id") != PROTOCOL_ID:
        raise ValueError(f"{label}: portability protocol changed")
    if report.get("profile_status") != PROFILE_STATUS:
        raise ValueError(f"{label}: profile formula gates did not pass")
    if (
        report.get("requested_workers") != expected["workers"]
        or report.get("requested_logical_cpus") != expected["logical_cpus"]
        or report.get("timing_repeats") != 5
    ):
        raise ValueError(f"{label}: hardware/repeat contract changed")
    if report.get("git_head") != git_head:
        raise ValueError(f"{label}: report was generated from a different commit")
    if report.get("git_clean_at_start") is not True:
        raise ValueError(f"{label}: report did not start from a clean tree")
    if report.get("source_hashes") != source_hashes:
        raise ValueError(f"{label}: source hashes differ from the checked-out tree")
    if not all(isinstance(path, str) and _is_hex(digest, 64) for path, digest in source_hashes.items()):
        raise ValueError(f"{label}: current source map is malformed")
    if report.get("source_digest") != sha256_value(source_hashes):
        raise ValueError(f"{label}: source aggregate digest is invalid")
    for digest_name in ("source_digest", "contract_digest", "fixture_digest", "scientific_digest"):
        if not _is_hex(report.get(digest_name), 64):
            raise ValueError(f"{label}: {digest_name} is not a lowercase SHA-256")

    contract_path = CANDIDATE / "config" / "validation_contract.json"
    fixture_path = CANDIDATE / "fixtures" / "formula_transition_cases.json"
    if report.get("contract_digest") != _sha256_file(contract_path):
        raise ValueError(f"{label}: contract digest changed")
    if report.get("fixture_digest") != _sha256_file(fixture_path):
        raise ValueError(f"{label}: fixture digest changed")

    if (
        report.get("scope") != PROFILE
        or report.get("paper_level_status") != PAPER_LEVEL_STATUS
        or report.get("source_byte_status") != SOURCE_BYTE_STATUS
        or report.get("source_freeze_status") != SOURCE_FREEZE_STATUS
        or report.get("h0_source_status") != H0_SOURCE_STATUS
        or report.get("published_result_status") != PUBLISHED_RESULT_STATUS
        or report.get("published_27_of_30_evaluated") is not False
        or report.get("author_code_replayed") is not False
        or report.get("cec2017_reproduced") is not False
        or report.get("pass_full_claimed") is not False
    ):
        raise ValueError(f"{label}: a scope or blocker label changed")
    if report.get("contract_strongest_allowed") != contract["required_labels"]["strongest_allowed"]:
        raise ValueError(f"{label}: strongest formula-only label changed")

    h0 = report.get("gates", {}).get("H0_provenance", {})
    if h0 != {
        "status": SOURCE_BYTE_STATUS,
        "blocker": SOURCE_FREEZE_STATUS,
        "combined_status": H0_SOURCE_STATUS,
        "postprint_bytes": 2_921_299,
        "postprint_sha256": "SHA256_UNRESOLVED",
    }:
        raise ValueError(f"{label}: H0 metadata-only gate changed")
    gates = report.get("gates", {})
    if gates != {
        "H0_provenance": h0,
        "H1_unit_formula": {"status": "PASS_PYTHON_FORMULA_FIXTURES"},
        "H2_property_adversarial": {"status": "PASS_PROPERTY_ADVERSARIAL"},
        "H3_fixed_transition": {"status": "PASS_FIXED_TAPE_PYTHON"},
        "H4_repeatability": {
            "status": "PASS_FIVE_REPEAT_SCIENTIFIC_BYTES",
            "repeat_count": 5,
        },
        "H5_cross_profile": {"status": "NOT_EVALUATED_SINGLE_PROFILE"},
    }:
        raise ValueError(f"{label}: H1-H5 single-profile gates changed")

    fixture = strict_json_load(fixture_path)
    expected_payload = scientific_payload(fixture, expected_parallel_cases())
    payload = report.get("scientific_payload")
    if payload != expected_payload:
        raise ValueError(f"{label}: scientific payload differs from recomputation")
    payload_bytes = canonical_bytes(payload)
    digest = hashlib.sha256(payload_bytes).hexdigest()
    if (
        digest != profile_config.get("expected_scientific_digest")
        or digest != contract.get("micro_oracle_digests", {}).get(
            "five_repeat_scientific_payload_sha256"
        )
        or report.get("scientific_digest") != digest
        or report.get("scientific_payload_bytes") != len(payload_bytes)
        or report.get("repeat_scientific_digests") != [digest] * 5
    ):
        raise ValueError(f"{label}: scientific repeat digest/size is invalid")

    hardware = report.get("hardware", {})
    _require_exact_keys(
        hardware,
        {
            "execution_context",
            "platform_system",
            "platform_machine",
            "python_version",
            "os_cpu_count",
            "affinity_visible_cpus",
            "exact_visible_cpus_enforced",
        },
        f"{label} hardware",
    )
    context = hardware.get("execution_context", {})
    if hardware.get("exact_visible_cpus_enforced") is not True:
        raise ValueError(f"{label}: exact affinity-visible CPUs were not enforced")
    if len(hardware.get("affinity_visible_cpus", [])) != expected["logical_cpus"]:
        raise ValueError(f"{label}: affinity-visible CPU count differs from profile")
    if label == "github-4":
        _require_exact_keys(
            context,
            {"github_actions", "github_run_id", "github_run_attempt"},
            "github-4 context claim",
        )
        if (
            context.get("github_actions") is not True
            or not context.get("github_run_id")
            or not context.get("github_run_attempt")
        ):
            raise ValueError("github-4 lacks GitHub Actions run provenance")
        if report.get("hardware_role_authentication") != "UNAUTHENTICATED_CONTEXT_CLAIM":
            raise ValueError("github-4 context claim was improperly treated as authentication")
    elif context != {"github_actions": False}:
        raise ValueError(f"{label}: Work profile execution context is invalid")
    elif report.get("hardware_role_authentication") != "NOT_APPLICABLE_WORK_PROFILE":
        raise ValueError(f"{label}: Work role-authentication label changed")


def validate_github_attestation(
    attestation: dict[str, Any],
    *,
    github_report: dict[str, Any],
    github_report_sha256: str,
    profile_config: dict[str, Any],
) -> None:
    """Validate a separate authenticated-API evidence record.

    The profile's own environment variables are only a context claim. H5 is
    never authorized from that claim; the caller must separately acquire this
    attestation from authenticated GitHub API metadata and bind it to the
    downloaded report bytes.
    """

    _require_exact_keys(
        attestation,
        {
            "schema_version",
            "attestation_type",
            "retrieval_method",
            "repository",
            "workflow_path",
            "head_sha",
            "run_id",
            "run_attempt",
            "workflow_conclusion",
            "artifact_id",
            "artifact_name",
            "artifact_expired",
            "report_member",
            "report_sha256",
            "workflow_run_api_url",
            "artifact_api_url",
            "h0_source_status",
            "source_byte_status",
            "source_freeze_status",
        },
        "GitHub API attestation",
    )
    frozen = profile_config["github_api_attestation"]
    expected_scalars = {
        "schema_version": "1.0.0",
        "attestation_type": frozen["attestation_type"],
        "retrieval_method": "authenticated_github_api",
        "repository": frozen["repository"],
        "workflow_path": frozen["workflow_path"],
        "head_sha": github_report["git_head"],
        "run_id": github_report["hardware"]["execution_context"]["github_run_id"],
        "run_attempt": github_report["hardware"]["execution_context"]["github_run_attempt"],
        "workflow_conclusion": "success",
        "artifact_name": frozen["artifact_name"],
        "artifact_expired": False,
        "report_member": frozen["report_member"],
        "report_sha256": github_report_sha256,
        "h0_source_status": H0_SOURCE_STATUS,
        "source_byte_status": SOURCE_BYTE_STATUS,
        "source_freeze_status": SOURCE_FREEZE_STATUS,
    }
    for key, expected in expected_scalars.items():
        if attestation.get(key) != expected:
            raise ValueError(f"GitHub API attestation field differs: {key}")
    if not _is_hex(github_report_sha256, 64):
        raise ValueError("GitHub report byte digest is malformed")
    if not _is_hex(attestation.get("head_sha"), 40):
        raise ValueError("GitHub attestation head SHA is malformed")
    if not isinstance(attestation.get("run_id"), str) or not attestation["run_id"].isdigit() or int(attestation["run_id"]) <= 0:
        raise ValueError("GitHub run ID must be a positive decimal string")
    if not isinstance(attestation.get("run_attempt"), str) or not attestation["run_attempt"].isdigit() or int(attestation["run_attempt"]) <= 0:
        raise ValueError("GitHub run attempt must be a positive decimal string")
    if not isinstance(attestation.get("artifact_id"), int) or isinstance(attestation["artifact_id"], bool) or attestation["artifact_id"] <= 0:
        raise ValueError("GitHub API artifact ID must be a positive integer")
    run_id = str(attestation["run_id"])
    artifact_id = str(attestation["artifact_id"])
    expected_run_url = f"https://api.github.com/repos/{frozen['repository']}/actions/runs/{run_id}"
    expected_artifact_url = f"https://api.github.com/repos/{frozen['repository']}/actions/artifacts/{artifact_id}"
    if attestation.get("workflow_run_api_url") != expected_run_url:
        raise ValueError("GitHub workflow-run API URL is not exact")
    if attestation.get("artifact_api_url") != expected_artifact_url:
        raise ValueError("GitHub artifact API URL is not exact")


def compare_reports(
    reports: list[dict[str, Any]],
    *,
    github_attestation: dict[str, Any] | None = None,
    report_sha256_by_label: dict[str, str] | None = None,
) -> tuple[dict[str, Any], bool]:
    contract, profile_config = _frozen_config()
    source_hashes = current_source_hashes()
    git_head = _git_head()
    by_label: dict[str, dict[str, Any]] = {}
    for report in reports:
        validate_report(
            report,
            source_hashes=source_hashes,
            git_head=git_head,
            contract=contract,
            profile_config=profile_config,
        )
        label = report["profile_label"]
        if label in by_label:
            raise ValueError(f"duplicate profile label: {label}")
        by_label[label] = report

    required = profile_config["comparison"]["required_profiles"]
    missing = [label for label in required if label not in by_label]
    summary: dict[str, Any] = {
        "schema_version": "1.0.0",
        "protocol_id": PROTOCOL_ID,
        "required_profiles": required,
        "observed_profiles": [label for label in required if label in by_label],
        "missing_profiles": missing,
        "paper_level_status": PAPER_LEVEL_STATUS,
        "source_byte_status": SOURCE_BYTE_STATUS,
        "source_freeze_status": SOURCE_FREEZE_STATUS,
        "h0_source_status": H0_SOURCE_STATUS,
        "published_result_status": PUBLISHED_RESULT_STATUS,
        "published_27_of_30_evaluated": False,
        "pass_full_claimed": False,
        "profile_digests": {
            label: {
                "source_digest": report["source_digest"],
                "scientific_digest": report["scientific_digest"],
            }
            for label, report in sorted(by_label.items())
        },
    }
    if missing:
        summary["status"] = profile_config["comparison"]["missing_profile_status"]
        summary["strongest_result"] = "NOT_RUN"
        summary["github_role_authentication"] = "NOT_EVALUATED_MISSING_PROFILE"
        return summary, False

    for field in profile_config["comparison"]["exact_fields"]:
        values = {report.get(field) for report in by_label.values()}
        if len(values) != 1:
            raise ValueError(f"cross-profile exact field differs: {field}")
    if github_attestation is None:
        summary["status"] = profile_config["github_api_attestation"]["missing_status"]
        summary["strongest_result"] = "NOT_RUN"
        summary["github_role_authentication"] = "UNAUTHENTICATED_SELF_ASSERTED_CONTEXT"
        return summary, False
    if report_sha256_by_label is None or "github-4" not in report_sha256_by_label:
        raise ValueError("GitHub API attestation requires the actual report byte digest")
    validate_github_attestation(
        github_attestation,
        github_report=by_label["github-4"],
        github_report_sha256=report_sha256_by_label["github-4"],
        profile_config=profile_config,
    )
    summary["status"] = profile_config["comparison"]["pass_status"]
    summary["strongest_result"] = contract["required_labels"]["strongest_allowed"]
    summary["scientific_digest"] = by_label[required[0]]["scientific_digest"]
    summary["github_role_authentication"] = "PASS_SEPARATE_GITHUB_API_ATTESTATION"
    summary["github_attestation"] = {
        "run_id": github_attestation["run_id"],
        "run_attempt": github_attestation["run_attempt"],
        "artifact_id": github_attestation["artifact_id"],
        "artifact_name": github_attestation["artifact_name"],
        "report_sha256": github_attestation["report_sha256"],
    }
    return summary, True


def main() -> None:
    args = parse_args()
    reports = [strict_json_load(path) for path in args.profiles]
    report_sha256_by_label: dict[str, str] = {}
    for path, report in zip(args.profiles, reports):
        label = report.get("profile_label") if isinstance(report, dict) else None
        if isinstance(label, str):
            report_sha256_by_label[label] = _sha256_file(path)
    attestation = strict_json_load(args.github_attestation) if args.github_attestation else None
    try:
        summary, complete = compare_reports(
            reports,
            github_attestation=attestation,
            report_sha256_by_label=report_sha256_by_label,
        )
    except (KeyError, TypeError, ValueError) as error:
        raise SystemExit(f"EU26-05 portability comparison failed: {error}") from error
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(canonical_bytes(summary) + b"\n")
    print(json.dumps({"status": summary["status"], "h0": H0_SOURCE_STATUS}, sort_keys=True))
    if not complete and not args.allow_incomplete:
        raise SystemExit("EU26-05 portability comparison is incomplete")


if __name__ == "__main__":
    main()
