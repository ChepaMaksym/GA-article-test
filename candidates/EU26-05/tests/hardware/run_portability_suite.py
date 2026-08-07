#!/usr/bin/env python3
"""Run one deterministic EU26-05 formula-portability hardware profile."""

from __future__ import annotations

import argparse
from concurrent.futures import ProcessPoolExecutor
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
from typing import Any


SCRIPT = Path(__file__).resolve()
CANDIDATE = SCRIPT.parents[2]
REPOSITORY = CANDIDATE.parents[1]
PYTHON_ENV = CANDIDATE / "environments" / "python"
sys.path.insert(0, str(PYTHON_ENV))

from eu2605.canonical import canonical_bytes, sha256_value, strict_json_load  # noqa: E402
from eu2605.core import (  # noqa: E402
    H0_SOURCE_STATUS,
    PAPER_LEVEL_STATUS,
    PROFILE,
    SOURCE_BYTE_STATUS,
    SOURCE_FREEZE_STATUS,
)
from eu2605.portability import (  # noqa: E402
    PARALLEL_CASE_COUNT,
    parallel_case,
    scientific_payload,
)


PROTOCOL_ID = "EU26-05-HARDWARE-PORTABILITY-v1"
PROFILE_STATUS = "PASS_PROFILE_FORMULA"
PUBLISHED_RESULT_STATUS = "BLOCKED_MISSING_AUTHOR_CODE_RAW_SEEDS_AND_COMPLETE_SEMANTICS"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--label", required=True)
    parser.add_argument("--workers", required=True, type=int)
    parser.add_argument("--logical-cpus", required=True, type=int)
    parser.add_argument("--timing-repeats", required=True, type=int)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--hashes", required=True, type=Path)
    parser.add_argument("--require-clean", action="store_true")
    parser.add_argument("--require-exact-visible-cpus", action="store_true")
    return parser.parse_args()


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _source_paths() -> list[Path]:
    paths: set[Path] = set()
    for path in CANDIDATE.rglob("*"):
        if not path.is_file():
            continue
        relative = path.relative_to(CANDIDATE)
        if (
            "results" in relative.parts
            or "__pycache__" in relative.parts
            or path.suffix in {".pyc", ".pyo"}
        ):
            continue
        paths.add(path)
    for workflow_name in ("eu26-05-validation.yml", "eu26-05-attest.yml"):
        workflow = REPOSITORY / ".github" / "workflows" / workflow_name
        if workflow.is_file():
            paths.add(workflow)
    registry = REPOSITORY / "registry" / "cohort_2026_12"
    for path in registry.rglob("*"):
        if path.is_file() and "__pycache__" not in path.parts and path.suffix not in {".pyc", ".pyo"}:
            paths.add(path)
    return sorted(paths)


def current_source_hashes() -> dict[str, str]:
    return {
        path.resolve().relative_to(REPOSITORY.resolve()).as_posix(): _sha256_file(path)
        for path in _source_paths()
    }


def _git_text(*arguments: str) -> str:
    completed = subprocess.run(
        ["git", *arguments],
        cwd=REPOSITORY,
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    return completed.stdout.strip()


def _validate_frozen_contract(args: argparse.Namespace) -> tuple[dict[str, Any], dict[str, Any]]:
    contract_path = CANDIDATE / "config" / "validation_contract.json"
    profiles_path = CANDIDATE / "config" / "hardware_profiles.json"
    contract = strict_json_load(contract_path)
    profiles = strict_json_load(profiles_path)

    expected = next(
        (item for item in profiles.get("profiles", []) if item.get("label") == args.label),
        None,
    )
    if expected is None:
        raise ValueError(f"profile label is not frozen: {args.label}")
    if (args.workers, args.logical_cpus) != (expected["workers"], expected["logical_cpus"]):
        raise ValueError("workers/logical CPUs differ from the frozen profile")
    if args.timing_repeats != profiles.get("timing_repeats") or args.timing_repeats != 5:
        raise ValueError("the frozen profile requires exactly five repeats")
    if contract.get("scope") != PROFILE:
        raise ValueError("formula-only scope changed")
    if contract.get("source_byte_status") != SOURCE_BYTE_STATUS:
        raise ValueError("postprint metadata-only status changed")
    postprint = contract.get("postprint", {})
    if (
        postprint.get("bytes") != 2_921_299
        or postprint.get("sha256") != "SHA256_UNRESOLVED"
        or postprint.get("freeze_status") != SOURCE_FREEZE_STATUS
    ):
        raise ValueError("postprint unresolved-byte identity changed")
    if "PASS_FULL" not in contract.get("forbidden_claims", []):
        raise ValueError("PASS_FULL is no longer explicitly forbidden")
    if contract.get("publication_facts", {}).get("descriptive_endpoint", {}).get("execution_authorized") is not False:
        raise ValueError("published 27/30 endpoint was improperly authorized")
    if profiles.get("parallel_case_count") != PARALLEL_CASE_COUNT:
        raise ValueError("parallel formula case count changed")
    return contract, profiles


def _execution_context(label: str) -> dict[str, Any]:
    github_actions = os.environ.get("GITHUB_ACTIONS", "").lower() == "true"
    if label == "github-4" and not github_actions:
        raise ValueError("github-4 may run only in a GitHub Actions context")
    if label.startswith("work-") and github_actions:
        raise ValueError("Work profiles may not be relabelled GitHub Actions runs")
    context: dict[str, Any] = {"github_actions": github_actions}
    if github_actions:
        run_id = os.environ.get("GITHUB_RUN_ID")
        run_attempt = os.environ.get("GITHUB_RUN_ATTEMPT")
        if not run_id or not run_attempt:
            raise ValueError("GitHub profile requires run ID and run attempt")
        context.update({"github_run_id": run_id, "github_run_attempt": run_attempt})
    return context


def _visible_cpus() -> list[int]:
    if hasattr(os, "sched_getaffinity"):
        return sorted(os.sched_getaffinity(0))
    count = os.cpu_count()
    return list(range(count or 1))


def _parallel_rows(workers: int) -> list[dict[str, Any]]:
    with ProcessPoolExecutor(max_workers=workers) as executor:
        return list(executor.map(parallel_case, range(PARALLEL_CASE_COUNT)))


def build_report(args: argparse.Namespace) -> tuple[dict[str, Any], dict[str, str]]:
    contract, profiles = _validate_frozen_contract(args)
    context = _execution_context(args.label)
    visible = _visible_cpus()
    if args.require_exact_visible_cpus and len(visible) != args.logical_cpus:
        raise ValueError(
            f"expected {args.logical_cpus} affinity-visible CPUs, found {visible}"
        )

    git_head = _git_text("rev-parse", "HEAD")
    git_status = _git_text("status", "--porcelain", "--untracked-files=all")
    if args.require_clean and git_status:
        raise ValueError("--require-clean set but the worktree has changes")

    fixture_path = CANDIDATE / "fixtures" / "formula_transition_cases.json"
    contract_path = CANDIDATE / "config" / "validation_contract.json"
    fixture = strict_json_load(fixture_path)
    hashes = current_source_hashes()

    repeat_digests: list[str] = []
    retained_payload: dict[str, Any] | None = None
    retained_bytes: bytes | None = None
    for _ in range(args.timing_repeats):
        payload = scientific_payload(fixture, _parallel_rows(args.workers))
        payload_bytes = canonical_bytes(payload)
        if retained_bytes is None:
            retained_payload = payload
            retained_bytes = payload_bytes
        elif payload_bytes != retained_bytes:
            raise AssertionError("same-profile scientific repeat bytes differ")
        repeat_digests.append(hashlib.sha256(payload_bytes).hexdigest())
    if retained_payload is None or retained_bytes is None:
        raise AssertionError("no formula repeats ran")

    scientific_digest = hashlib.sha256(retained_bytes).hexdigest()
    if scientific_digest != profiles.get("expected_scientific_digest"):
        raise AssertionError("scientific payload differs from the preregistered digest")
    if scientific_digest != contract.get("micro_oracle_digests", {}).get(
        "five_repeat_scientific_payload_sha256"
    ):
        raise AssertionError("contract and hardware scientific digests disagree")
    report = {
        "schema_version": "1.0.0",
        "protocol_id": PROTOCOL_ID,
        "profile_label": args.label,
        "requested_workers": args.workers,
        "requested_logical_cpus": args.logical_cpus,
        "timing_repeats": args.timing_repeats,
        "git_head": git_head,
        "git_clean_at_start": not bool(git_status),
        "source_hashes": hashes,
        "source_digest": sha256_value(hashes),
        "contract_digest": _sha256_file(contract_path),
        "fixture_digest": _sha256_file(fixture_path),
        "scientific_digest": scientific_digest,
        "scientific_payload_bytes": len(retained_bytes),
        "scientific_payload": retained_payload,
        "repeat_scientific_digests": repeat_digests,
        "profile_status": PROFILE_STATUS,
        "scope": PROFILE,
        "paper_level_status": PAPER_LEVEL_STATUS,
        "source_byte_status": SOURCE_BYTE_STATUS,
        "source_freeze_status": SOURCE_FREEZE_STATUS,
        "h0_source_status": H0_SOURCE_STATUS,
        "published_result_status": PUBLISHED_RESULT_STATUS,
        "published_27_of_30_evaluated": False,
        "author_code_replayed": False,
        "cec2017_reproduced": False,
        "pass_full_claimed": False,
        "gates": {
            "H0_provenance": {
                "status": SOURCE_BYTE_STATUS,
                "blocker": SOURCE_FREEZE_STATUS,
                "combined_status": H0_SOURCE_STATUS,
                "postprint_bytes": 2_921_299,
                "postprint_sha256": "SHA256_UNRESOLVED",
            },
            "H1_unit_formula": {"status": "PASS_PYTHON_FORMULA_FIXTURES"},
            "H2_property_adversarial": {"status": "PASS_PROPERTY_ADVERSARIAL"},
            "H3_fixed_transition": {"status": "PASS_FIXED_TAPE_PYTHON"},
            "H4_repeatability": {
                "status": "PASS_FIVE_REPEAT_SCIENTIFIC_BYTES",
                "repeat_count": args.timing_repeats,
            },
            "H5_cross_profile": {"status": "NOT_EVALUATED_SINGLE_PROFILE"},
        },
        "hardware": {
            "execution_context": context,
            "platform_system": platform.system(),
            "platform_machine": platform.machine(),
            "python_version": platform.python_version(),
            "os_cpu_count": os.cpu_count(),
            "affinity_visible_cpus": visible,
            "exact_visible_cpus_enforced": args.require_exact_visible_cpus,
        },
        "hardware_role_authentication": (
            "UNAUTHENTICATED_CONTEXT_CLAIM"
            if args.label == "github-4"
            else "NOT_APPLICABLE_WORK_PROFILE"
        ),
        "contract_strongest_allowed": contract["required_labels"]["strongest_allowed"],
    }
    return report, hashes


def main() -> None:
    args = parse_args()
    for name in (
        "OMP_NUM_THREADS",
        "OPENBLAS_NUM_THREADS",
        "MKL_NUM_THREADS",
        "NUMEXPR_NUM_THREADS",
        "VECLIB_MAXIMUM_THREADS",
    ):
        os.environ[name] = "1"
    report, hashes = build_report(args)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.hashes.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(canonical_bytes(report) + b"\n")
    args.hashes.write_text(
        "".join(f"{digest}\t{path}\n" for path, digest in sorted(hashes.items())),
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "profile": report["profile_label"],
                "status": report["profile_status"],
                "h0": report["h0_source_status"],
                "scientific_digest": report["scientific_digest"],
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
