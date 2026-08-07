#!/usr/bin/env python3
"""Strictly compare USA26-04 Work-4, Work-8, and GitHub-4 reports."""

from __future__ import annotations

import argparse
import itertools
import json
from pathlib import Path
from typing import Any


PROTOCOL_ID = "USA26-04-FORMULA-PORTABILITY-v1"
PAPER_STATUS = "BLOCKED_G5_G9"
PUBLISHED_STATUS = "INCONCLUSIVE_PUBLISHED_RESULT"
STATE_PROVENANCE = "synthetic_fixture_not_article_state"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("profiles", nargs="+", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    return parser.parse_args()


def _role(profile: dict[str, Any]) -> str | None:
    context = profile.get("hardware", {}).get("execution_context", {})
    cpus = profile.get("requested_logical_cpus")
    workers = profile.get("requested_workers")
    if cpus != workers:
        return None
    if context.get("github_actions") and cpus == 4:
        if context.get("github_run_id") and context.get("github_run_attempt"):
            return "github_actions_4core"
        return None
    if not context.get("github_actions") and cpus == 4:
        return "work_4core"
    if not context.get("github_actions") and cpus == 8:
        return "work_8core"
    return None


def compare_reports(profiles: list[dict[str, Any]]) -> dict[str, Any]:
    if len(profiles) < 2:
        raise ValueError("at least two profiles are required")
    labels = [profile.get("profile_label") for profile in profiles]
    if any(not isinstance(label, str) or not label for label in labels):
        raise ValueError("every profile needs a label")
    if len(set(labels)) != len(labels):
        raise ValueError("profile labels must be unique")
    for profile in profiles:
        if profile.get("protocol_id") != PROTOCOL_ID:
            raise ValueError("profile protocol ID mismatch")
        if profile.get("paper_level_status") != PAPER_STATUS:
            raise ValueError("profile attempted to clear the paper-level block")
        if profile.get("published_result_status") != PUBLISHED_STATUS:
            raise ValueError("profile attempted to promote the published result")
        if profile.get("fixed_controller_state_provenance") != STATE_PROVENANCE:
            raise ValueError("profile lost synthetic controller-state provenance")

    pairs = []
    for left, right in itertools.combinations(profiles, 2):
        left_correctness = left.get("correctness", {})
        right_correctness = right.get("correctness", {})
        checks = {
            "protocol_id_match": left["protocol_id"] == right["protocol_id"],
            "source_hashes_match": left.get("source_sha256") == right.get("source_sha256"),
            "case_ids_match": left_correctness.get("case_ids")
            == right_correctness.get("case_ids"),
            "aggregate_digest_match": left_correctness.get("aggregate_digest")
            == right_correctness.get("aggregate_digest"),
            "paper_status_match": left["paper_level_status"]
            == right["paper_level_status"]
            == PAPER_STATUS,
            "published_status_match": left["published_result_status"]
            == right["published_result_status"]
            == PUBLISHED_STATUS,
            "state_provenance_match": left["fixed_controller_state_provenance"]
            == right["fixed_controller_state_provenance"]
            == STATE_PROVENANCE,
        }
        pairs.append(
            {
                "left": left["profile_label"],
                "right": right["profile_label"],
                "status": "PASS_STRICT_FORMULA_MATCH"
                if all(checks.values())
                else "INCONCLUSIVE_STRICT_MISMATCH",
                "checks": checks,
            }
        )

    required_roles = {
        "work_4core": False,
        "work_8core": False,
        "github_actions_4core": False,
    }
    role_by_profile = {}
    duplicate_roles: list[str] = []
    for profile in profiles:
        role = _role(profile)
        role_by_profile[profile["profile_label"]] = role
        if role in required_roles:
            if required_roles[role]:
                duplicate_roles.append(role)
            required_roles[role] = True

    strict_pairs_pass = all(pair["status"].startswith("PASS_") for pair in pairs)
    required_roles_present = all(required_roles.values()) and not duplicate_roles
    profile_gate_failures = [
        profile["profile_label"]
        for profile in profiles
        if profile.get("profile_status") != "PASS_PROFILE_H0_H4"
    ]
    h5_status = (
        "PASS_FORMULA_PORTABILITY"
        if strict_pairs_pass and required_roles_present
        else (
            "INCOMPLETE_REQUIRED_PROFILE"
            if strict_pairs_pass and not required_roles_present
            else "INCONCLUSIVE_STRICT_MISMATCH"
        )
    )
    overall_status = (
        "PASS_ENGINEERING_FORMULA_PORTABILITY"
        if h5_status == "PASS_FORMULA_PORTABILITY" and not profile_gate_failures
        else "INCONCLUSIVE_ENGINEERING_PORTABILITY"
    )
    return {
        "protocol_id": PROTOCOL_ID,
        "verification_scope": "FORMULA_AND_AMBIGUITY_VALIDATION_ONLY",
        "paper_level_status": PAPER_STATUS,
        "published_result_status": PUBLISHED_STATUS,
        "registry_status": "conditional_noneligible",
        "fixed_controller_state_provenance": STATE_PROVENANCE,
        "profiles": labels,
        "role_by_profile": role_by_profile,
        "required_roles": required_roles,
        "duplicate_roles": sorted(duplicate_roles),
        "pairwise": pairs,
        "profile_gate_failures": profile_gate_failures,
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
    profiles = [json.loads(path.read_text(encoding="utf-8")) for path in args.profiles]
    report = compare_reports(profiles)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report, indent=2, sort_keys=True, allow_nan=False))
    return 0 if report["overall_status"].startswith("PASS_") else 1


if __name__ == "__main__":
    raise SystemExit(main())
