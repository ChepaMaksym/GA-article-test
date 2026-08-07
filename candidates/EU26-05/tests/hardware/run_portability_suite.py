#!/usr/bin/env python3
"""Run one deterministic EU26-05 formula-portability hardware profile."""

from __future__ import annotations

import argparse
from concurrent.futures import ProcessPoolExecutor
import hashlib
import json
import multiprocessing
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
from eu2605.reporting import (  # noqa: E402
    exclusive_write_bytes,
    exclusive_write_text,
    prepare_exclusive_outputs,
)


PROTOCOL_ID = "EU26-05-HARDWARE-PORTABILITY-v1"
PROFILE_STATUS = "PASS_PROFILE_FORMULA"
PUBLISHED_RESULT_STATUS = "BLOCKED_MISSING_AUTHOR_CODE_RAW_SEEDS_AND_COMPLETE_SEMANTICS"
_WORKER_STARTUP_BARRIER: Any | None = None


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
    workflow = REPOSITORY / ".github" / "workflows" / "eu26-05-validation.yml"
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

    expected_profile_rows = [
        {"label": "work-4", "workers": 4, "logical_cpus": 4},
        {"label": "work-8", "workers": 8, "logical_cpus": 8},
        {"label": "github-4", "workers": 4, "logical_cpus": 4},
    ]
    if profiles.get("profiles") != expected_profile_rows:
        raise ValueError("frozen hardware profile rows changed or use non-exact types")
    expected = next(
        (item for item in expected_profile_rows if item["label"] == args.label),
        None,
    )
    if expected is None:
        raise ValueError(f"profile label is not frozen: {args.label}")
    if (
        type(args.workers) is not int
        or type(args.logical_cpus) is not int
        or (args.workers, args.logical_cpus)
        != (expected["workers"], expected["logical_cpus"])
    ):
        raise ValueError("workers/logical CPUs differ from the frozen profile")
    if (
        type(args.timing_repeats) is not int
        or type(profiles.get("timing_repeats")) is not int
        or args.timing_repeats != profiles.get("timing_repeats")
        or args.timing_repeats != 5
    ):
        raise ValueError("the frozen profile requires exactly five repeats")
    if (
        contract.get("schema_version") != "1.0.0"
        or contract.get("protocol_id") != "EU26-05-FORMULA-TRANSITION-v1"
        or contract.get("evidence_boundary_amendment")
        != "preregistration/amendment-001-offline-evidence-boundary.md"
        or contract.get("scope") != PROFILE
    ):
        raise ValueError("formula-only scope changed")
    if contract.get("paper_level_status") != PAPER_LEVEL_STATUS:
        raise ValueError("paper-level blocker changed")
    if contract.get("source_byte_status") != SOURCE_BYTE_STATUS:
        raise ValueError("postprint metadata-only status changed")
    postprint = contract.get("postprint", {})
    if (
        type(postprint.get("component")) is not int
        or postprint.get("component") != 3
        or type(postprint.get("bytes")) is not int
        or postprint.get("bytes") != 2_921_299
        or postprint.get("sha256") != "SHA256_UNRESOLVED"
        or postprint.get("freeze_status") != SOURCE_FREEZE_STATUS
    ):
        raise ValueError("postprint unresolved-byte identity changed")
    if contract.get("forbidden_claims") != [
        "PASS_FULL",
        "CEC2017_REPRODUCED",
        "PUBLISHED_27_OF_30_REPRODUCED",
        "AUTHOR_CODE_REPLAYED",
    ]:
        raise ValueError("forbidden claim set changed")
    if contract.get("required_labels") != {
        "strongest_allowed": "PASS_FORMULA_AND_TRANSITION_PORTABILITY",
        "published_result": PUBLISHED_RESULT_STATUS,
    }:
        raise ValueError("formula-only result labels changed")
    if contract.get("publication_facts", {}).get("descriptive_endpoint", {}).get("execution_authorized") is not False:
        raise ValueError("published 27/30 endpoint was improperly authorized")
    if type(profiles.get("parallel_case_count")) is not int or profiles.get(
        "parallel_case_count"
    ) != PARALLEL_CASE_COUNT:
        raise ValueError("parallel formula case count changed")
    if profiles.get("comparison") != {
        "required_profiles": ["work-4", "work-8", "github-4"],
        "exact_fields": [
            "git_head",
            "source_digest",
            "contract_digest",
            "fixture_digest",
            "scientific_digest",
            "paper_level_status",
            "source_byte_status",
        ],
        "missing_profile_status": "NOT_RUN_MISSING_PROFILES",
    }:
        raise ValueError("cross-profile comparison contract changed")
    if profiles.get("github_content_match") != {
        "record_type": "CALLER_SUPPLIED_GITHUB_METADATA_CONTENT_MATCH_v1",
        "repository": "ChepaMaksym/GA-article-test",
        "workflow_path": ".github/workflows/eu26-05-validation.yml",
        "artifact_name": "eu26-05-github-4-formula-portability",
        "report_member": "github-4.json",
        "missing_status": "NOT_RUN_GITHUB_CONTENT_MATCH_RECORD",
        "external_authentication_status": "NOT_EVALUATED_EXTERNAL_GITHUB_AUTH_REQUIRED",
        "offline_authorizes_h5": False,
    }:
        raise ValueError("offline GitHub content-match boundary changed")
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


def _initialize_worker(barrier: Any) -> None:
    global _WORKER_STARTUP_BARRIER
    _WORKER_STARTUP_BARRIER = barrier


def _worker_shard(slot: int, workers: int) -> dict[str, Any]:
    """Force one real process per shard and retain its execution evidence."""

    if _WORKER_STARTUP_BARRIER is None:
        raise RuntimeError("worker startup barrier was not initialized")
    _WORKER_STARTUP_BARRIER.wait(timeout=60)
    indices = list(range(slot, PARALLEL_CASE_COUNT, workers))
    return {
        "worker_slot": slot,
        "pid": os.getpid(),
        "affinity_visible_cpus": _visible_cpus(),
        "scientific_case_indices": indices,
        "rows": [parallel_case(index) for index in indices],
    }


def _parallel_rows(workers: int) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    try:
        context = multiprocessing.get_context("fork")
    except ValueError as error:
        raise RuntimeError("the frozen worker-evidence profile requires POSIX fork") from error
    barrier = context.Barrier(workers)
    with ProcessPoolExecutor(
        max_workers=workers,
        mp_context=context,
        initializer=_initialize_worker,
        initargs=(barrier,),
    ) as executor:
        futures = [executor.submit(_worker_shard, slot, workers) for slot in range(workers)]
        shard_records = [future.result() for future in futures]
    pids = [record["pid"] for record in shard_records]
    if len(set(pids)) != workers:
        raise AssertionError("startup barrier did not observe one distinct process per worker")
    rows = [row for record in shard_records for row in record.pop("rows")]
    rows.sort(key=lambda row: row["case_id"])
    return rows, shard_records


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
    worker_execution_repeats: list[list[dict[str, Any]]] = []
    retained_payload: dict[str, Any] | None = None
    retained_bytes: bytes | None = None
    for _ in range(args.timing_repeats):
        parallel_rows, worker_evidence = _parallel_rows(args.workers)
        for record in worker_evidence:
            if record["affinity_visible_cpus"] != visible:
                raise AssertionError("worker affinity differs from the parent profile mask")
        worker_execution_repeats.append(worker_evidence)
        payload = scientific_payload(fixture, parallel_rows)
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
        "worker_execution_repeats": worker_execution_repeats,
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
    output_path, hashes_path = prepare_exclusive_outputs(
        [args.output, args.hashes],
        REPOSITORY,
        labels=["profile report output", "source-hash output"],
    )
    report, hashes = build_report(args)
    exclusive_write_bytes(output_path, canonical_bytes(report) + b"\n")
    exclusive_write_text(
        hashes_path,
        "".join(f"{digest}\t{path}\n" for path, digest in sorted(hashes.items())),
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
