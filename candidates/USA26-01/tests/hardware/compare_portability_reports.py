#!/usr/bin/env python3
"""Compare two or more GESMR hardware-portability reports."""

from __future__ import annotations

import argparse
import itertools
import json
import math
from pathlib import Path
from typing import Any


ATOL = 1e-12
RTOL = 1e-12


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("profiles", nargs="+", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    return parser.parse_args()


def _flatten_numbers(value: Any) -> list[float]:
    if isinstance(value, bool):
        return []
    if isinstance(value, (int, float)):
        return [float(value)]
    if isinstance(value, list):
        result: list[float] = []
        for child in value:
            result.extend(_flatten_numbers(child))
        return result
    if isinstance(value, dict):
        result = []
        for key in sorted(value):
            result.extend(_flatten_numbers(value[key]))
        return result
    return []


def _numeric_close(left: Any, right: Any) -> bool:
    a = _flatten_numbers(left)
    b = _flatten_numbers(right)
    return len(a) == len(b) and all(
        math.isclose(x, y, rel_tol=RTOL, abs_tol=ATOL) for x, y in zip(a, b)
    )


def _compare_pair(left: dict[str, Any], right: dict[str, Any]) -> dict[str, Any]:
    left_cases = {row["case_id"]: row for row in left["correctness"]["cases"]}
    right_cases = {row["case_id"]: row for row in right["correctness"]["cases"]}
    ids_match = set(left_cases) == set(right_cases)
    bitwise_mismatches: list[str] = []
    numeric_mismatches: list[str] = []
    if ids_match:
        for case_id in sorted(left_cases):
            a = left_cases[case_id]
            b = right_cases[case_id]
            if a["sha256_v1"] != b["sha256_v1"]:
                bitwise_mismatches.append(case_id)
                if not _numeric_close(a["numeric_signature"], b["numeric_signature"]):
                    numeric_mismatches.append(case_id)
    else:
        numeric_mismatches.append("CASE_ID_SET_MISMATCH")

    source_hashes_match = left.get("source_sha256") == right.get("source_sha256")
    if not source_hashes_match:
        status = "INCONCLUSIVE_SOURCE_MISMATCH"
    elif not bitwise_mismatches and ids_match:
        status = "PASS_BITWISE"
    else:
        status = "INCONCLUSIVE_NUMERIC_REVIEW_REQUIRED"
    return {
        "left": left["profile_label"],
        "right": right["profile_label"],
        "status": status,
        "source_hashes_match": source_hashes_match,
        "case_ids_match": ids_match,
        "bitwise_mismatch_count": len(bitwise_mismatches),
        "numeric_mismatch_count": len(numeric_mismatches),
        "bitwise_mismatches": bitwise_mismatches,
        "numeric_mismatches": numeric_mismatches,
    }


def main() -> int:
    args = parse_args()
    profiles = [json.loads(path.read_text(encoding="utf-8")) for path in args.profiles]
    if len(profiles) < 2:
        raise SystemExit("at least two profiles are required")
    if any(profile.get("protocol_id") != "GESMR-HW-PORTABILITY-v1" for profile in profiles):
        raise SystemExit("all profiles must use the frozen protocol")
    labels = [profile.get("profile_label") for profile in profiles]
    if len(set(labels)) != len(labels):
        raise SystemExit("profile labels must be unique")

    pairs = [_compare_pair(left, right) for left, right in itertools.combinations(profiles, 2)]
    profile_failures = [
        profile["profile_label"] for profile in profiles if profile.get("profile_status") != "PASS"
    ]
    inconclusive_pairs = [
        f"{pair['left']}::{pair['right']}"
        for pair in pairs
        if not pair["status"].startswith("PASS_")
    ]
    cpu_counts = sorted({profile["requested_logical_cpus"] for profile in profiles})
    cpu_models = sorted(
        {profile["hardware"].get("cpu_model") for profile in profiles if profile["hardware"].get("cpu_model")}
    )
    execution_contexts = {
        profile["profile_label"]: profile["hardware"].get("execution_context", {})
        for profile in profiles
    }
    required_roles = {
        "work_4core": False,
        "work_8core": False,
        "github_actions_4core": False,
    }
    for profile in profiles:
        context = profile["hardware"].get("execution_context", {})
        cpus = profile.get("requested_logical_cpus")
        workers = profile.get("requested_workers")
        if not context.get("github_actions") and cpus == workers == 4:
            required_roles["work_4core"] = True
        elif not context.get("github_actions") and cpus == workers == 8:
            required_roles["work_8core"] = True
        elif (
            context.get("github_actions")
            and cpus == workers == 4
            and context.get("github_run_id")
            and context.get("github_run_attempt")
        ):
            required_roles["github_actions_4core"] = True
    required_cpu_counts_present = {4, 8}.issubset(cpu_counts)
    required_execution_contexts_present = all(required_roles.values())
    throughput = {
        profile["profile_label"]: {
            "workers": profile["requested_workers"],
            "logical_cpus": profile["requested_logical_cpus"],
            "median_batch_seconds": profile["timing"]["median_batch_seconds"],
            "median_jobs_per_second": profile["timing"]["median_jobs_per_second"],
            "observed_mhz": profile["hardware"].get("cpu_mhz_snapshot"),
        }
        for profile in profiles
    }
    overall = (
        "PASS"
        if not profile_failures
        and not inconclusive_pairs
        and required_cpu_counts_present
        and required_execution_contexts_present
        else "INCONCLUSIVE"
    )
    report = {
        "protocol_id": "GESMR-HW-PORTABILITY-v1",
        "verification_scope": "FORMULA_HARDWARE_PORTABILITY_NOT_PUBLISHED_REPRODUCTION",
        "profiles": [profile["profile_label"] for profile in profiles],
        "profile_failures": profile_failures,
        "pairwise_correctness": pairs,
        "tested_logical_cpu_counts": cpu_counts,
        "distinct_observed_cpu_models": cpu_models,
        "execution_contexts": execution_contexts,
        "required_cpu_counts_present": required_cpu_counts_present,
        "required_execution_contexts_present": required_execution_contexts_present,
        "required_profile_roles": required_roles,
        "throughput": throughput,
        "ghz_effect_status": "NOT_IDENTIFIABLE_FROM_UNCONTROLLED_VM_METADATA",
        "overall_status": overall,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if overall == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
