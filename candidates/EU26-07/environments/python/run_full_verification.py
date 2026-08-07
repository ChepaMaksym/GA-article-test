#!/usr/bin/env python3
"""Run the frozen 500-row source-native and clean-room EU26-07 replay."""

from __future__ import annotations

import argparse
from concurrent.futures import Future, ProcessPoolExecutor
import csv
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import tempfile
from typing import Any

import numpy as np
import scipy

from eu2607.canonical import (
    ARTIFACT_GENERIC,
    PAPER_ALGORITHM3,
    controls,
    crossover_from_mutant_positions,
    fixed_tape_generation,
    mutate_exact_positions,
    next_lambda,
    rounded_offspring,
)
from eu2607.core import RunRow, run_artifact_jump_optimized
from eu2607.published import (
    EXPECTED_RUNS,
    RAW_SHA256,
    PublishedRow,
    canonical_rows_sha256,
    parse_processed_targets,
    parse_raw_rows,
    summarize_rows,
)
from eu2607.source_adapter import authenticate_checkout, run_author_artifact


CANDIDATE = Path(__file__).resolve().parents[2]
REPOSITORY = CANDIDATE.parents[1]
LOCAL_CONTRACT_FILES = {
    "preregistration/eligibility_audit.md": (
        "e83c129aefc1a5c995a5de40f5ee99746abc84b3b7e483c275604738e1cc17d4"
    ),
    "preregistration/verification_contract.md": (
        "e7959622061600b5770e71349cdb6d35f5aaaed2c1c98fba7c481758317105e0"
    ),
    "fixtures/fixed_tape_cases.json": (
        "c80b9290d1e3eb21c9fbf1a12b2a981884752549d76d9d10d9d4df0dc17238ae"
    ),
    "config/verification_contract.json": (
        "06c81757cb2c076983e5a647259e7cfe7287a94de05e4e3c301c7c3a44c41f48"
    ),
    "config/environment_lock.json": (
        "3b547f8165c4e3622c9a64538b762e3f632d4da2ae32c96c54f44c5c4fe1bb5e"
    ),
    "config/seed_ledger.csv": (
        "08d48530350ebbafd0a4a9b18d1921b264a5635d323d1d7e4f6734d0d1e4a18d"
    ),
    "fixtures/published_summary.json": (
        "0e67d366a70b406535772948ce4b6da104071fa7a5c70bdb98de9daff18cc2c4"
    ),
    "source_manifest/sources.csv": (
        "96e754e95d2b7d2a52173381ca36b9f11a0d5bfe25cc50fefb39eac4e71bac01"
    ),
    "preregistration/amendment-001-pre-replay-review.md": (
        "ad68617bb8827476baf0c647fe92d4cad9f5c0b3065e0b16d7711c4b089df373"
    ),
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--upstream", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--runs", type=int, default=EXPECTED_RUNS)
    parser.add_argument("--workers", type=int, default=max(1, min(8, os.cpu_count() or 1)))
    return parser.parse_args()


def _pair(upstream: str, run: int) -> tuple[RunRow, RunRow]:
    root = Path(upstream)
    source = run_author_artifact(root, run)
    clean = run_artifact_jump_optimized(run)
    return source, clean


def _different(expected: PublishedRow, observed: RunRow) -> dict[str, Any]:
    expected_values = expected.to_dict()
    observed_values = observed.to_dict()
    return {
        key: {"expected": expected_values[key], "observed": observed_values[key]}
        for key in expected_values
        if expected_values[key] != observed_values[key]
    }


def _authenticate_local_contract() -> dict[str, str]:
    observed: dict[str, str] = {}
    for relative, expected_hash in LOCAL_CONTRACT_FILES.items():
        path = CANDIDATE / relative
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if digest != expected_hash:
            raise ValueError(
                f"local frozen-contract SHA-256 mismatch for {relative}: "
                f"{digest} != {expected_hash}"
            )
        observed[relative] = digest
    return observed


def _local_git(*arguments: str) -> str:
    completed = subprocess.run(
        ["git", "-C", str(REPOSITORY), *arguments],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    return completed.stdout.strip()


def _local_source_identity() -> dict[str, Any]:
    paths = [
        "candidates/EU26-07",
        ".github/workflows/eu26-07-validation.yml",
    ]
    status = _local_git("status", "--porcelain", "--untracked-files=all", "--", *paths)
    if status:
        raise ValueError(f"EU26-07 verifier worktree is not clean:\n{status}")
    return {
        "commit": _local_git("rev-parse", "HEAD"),
        "repository_tree": _local_git("rev-parse", "HEAD^{tree}"),
        "candidate_tree": _local_git("rev-parse", "HEAD:candidates/EU26-07"),
        "workflow_blob": _local_git(
            "rev-parse", "HEAD:.github/workflows/eu26-07-validation.yml"
        ),
        "scoped_worktree_clean": True,
        "scoped_paths": paths,
    }


def _load_and_validate_local_protocol() -> dict[str, Any]:
    contract = json.loads(
        (CANDIDATE / "config/verification_contract.json").read_text(
            encoding="utf-8"
        )
    )
    expected_contract_values = {
        "candidate_id": "EU26-07",
        "problem": {
            "name": "Jump",
            "n": 20,
            "k": 4,
            "sense": "maximize",
            "target_fitness": 24,
        },
        "seeds": {
            "base_seed": 816_114_841,
            "first_run": 1,
            "last_run": 500,
            "effective_seed_expression": "base_seed + run",
            "rngs": ["numpy.random legacy global", "python random global"],
        },
    }
    for key, expected in expected_contract_values.items():
        if contract.get(key) != expected:
            raise ValueError(f"frozen verification contract changed at {key}")
    algorithm = contract.get("algorithm", {})
    required_algorithm = {
        "lambda_initial": 1.0,
        "lambda_max": 20.0,
        "update_factor": 1.5,
        "crossover_coefficient": 1.0,
        "logical_evaluations_per_generation": "2 * rounded_lambda",
        "initial_parent_evaluation_charged": False,
        "finish_after_full_generation": True,
    }
    if algorithm != required_algorithm:
        raise ValueError("frozen algorithm configuration changed")
    if contract.get("acceptance", {}).get("pass_full_allowed") is not False:
        raise ValueError("PASS_FULL claim blocker was weakened")

    with (CANDIDATE / "config/seed_ledger.csv").open(
        newline="", encoding="utf-8"
    ) as handle:
        seed_rows = list(csv.DictReader(handle))
    if len(seed_rows) != EXPECTED_RUNS:
        raise ValueError("seed ledger must contain exactly 500 rows")
    for run, row in enumerate(seed_rows, start=1):
        expected_row = {
            "run": str(run),
            "effective_seed": str(816_114_841 + run),
            "n": "20",
            "k": "4",
            "base_seed": "816114841",
            "profile": "artifact_jump_optimized",
        }
        if row != expected_row:
            raise ValueError(f"seed ledger mismatch at run {run}")

    environment_lock = json.loads(
        (CANDIDATE / "config/environment_lock.json").read_text(encoding="utf-8")
    )
    return {
        "published_targets": contract["published_targets"],
        "declared_environment": environment_lock,
        "seed_rows": len(seed_rows),
    }


def _formula_gates() -> dict[str, Any]:
    fixture = json.loads(
        (CANDIDATE / "fixtures/fixed_tape_cases.json").read_text(encoding="utf-8")
    )
    operator = fixture["operator_case"]
    cases = {case["profile"]: case for case in fixture["cases"]}
    paper_case = dict(cases[PAPER_ALGORITHM3.name])
    artifact_case = dict(cases[ARTIFACT_GENERIC.name])
    paper_expected = paper_case.pop("expected")
    artifact_expected = artifact_case.pop("expected")
    paper_case.pop("name")
    artifact_case.pop("name")
    paper = fixed_tape_generation(**paper_case)
    artifact = fixed_tape_generation(**artifact_case)
    paper_controls = controls(2.5, 20, PAPER_ALGORITHM3)
    h2_values = {
        "exact_mutant": mutate_exact_positions(
            operator["parent"],
            operator["n"],
            operator["mutation_positions_zero_based_lsb"],
        ),
        "biased_crossover": crossover_from_mutant_positions(
            operator["parent"],
            operator["expected_mutant"],
            operator["n"],
            operator["crossover_take_mutant_positions_zero_based_lsb"],
        ),
        "grow_to_cap": next_lambda(
            19.0,
            strict_success=False,
            update_factor=1.5,
            lambda_max=20.0,
        ),
        "reset_from_cap": next_lambda(
            20.0,
            strict_success=False,
            update_factor=1.5,
            lambda_max=20.0,
        ),
        "paper_strict_success": paper.strict_success,
        "paper_parent_after": paper.parent_after,
        "paper_lambda_after_success": paper.lambda_after,
        "paper_round_2_5": paper_controls.offspring_count,
        "paper_mutation_probability": paper_controls.mutation_probability,
        "paper_crossover_probability": paper_controls.crossover_probability,
        "logical_evaluations": paper.logical_evaluations,
    }
    h2_expected = {
        "exact_mutant": operator["expected_mutant"],
        "biased_crossover": operator["expected_crossover"],
        "grow_to_cap": 20.0,
        "reset_from_cap": 1.0,
        "paper_strict_success": True,
        "paper_parent_after": paper_expected["parent_after"],
        "paper_lambda_after_success": 2.0 / 1.5,
        "paper_round_2_5": 3,
        "paper_mutation_probability": 0.125,
        "paper_crossover_probability": 0.4,
        "logical_evaluations": paper_expected["logical_evaluations"],
    }
    h3_values = {
        "paper_round_2_5": rounded_offspring(2.5, PAPER_ALGORITHM3),
        "artifact_round_2_5": rounded_offspring(2.5, ARTIFACT_GENERIC),
        "paper_selected_candidate": paper.selected_candidate,
        "artifact_selected_candidate": artifact.selected_candidate,
    }
    h3_expected = {
        "paper_round_2_5": 3,
        "artifact_round_2_5": 2,
        "paper_selected_candidate": paper_expected["selected_candidate"],
        "artifact_selected_candidate": artifact_expected["selected_candidate"],
    }
    return {
        "H2_paper_formula": {
            "status": "PASS" if h2_values == h2_expected else "FAIL",
            "observed": h2_values,
            "expected": h2_expected,
        },
        "H3_profile_isolation": {
            "status": "PASS" if h3_values == h3_expected else "FAIL",
            "observed": h3_values,
            "expected": h3_expected,
        },
    }


def _replay(
    upstream: Path,
    expected_rows: list[PublishedRow],
    workers: int,
) -> tuple[list[RunRow], list[RunRow], dict[str, Any] | None, int]:
    source_rows: list[RunRow] = []
    clean_rows: list[RunRow] = []
    mismatch: dict[str, Any] | None = None
    rows_examined = 0
    count = len(expected_rows)
    with ProcessPoolExecutor(max_workers=workers) as executor:
        pending: dict[int, Future[tuple[RunRow, RunRow]]] = {}
        next_to_submit = 1
        while next_to_submit <= min(workers, count):
            pending[next_to_submit] = executor.submit(
                _pair, str(upstream), next_to_submit
            )
            next_to_submit += 1

        for expected in expected_rows:
            future = pending.pop(expected.run)
            rows_examined += 1
            try:
                source, clean = future.result()
            except Exception as exc:  # preserve a fail-closed execution record
                mismatch = {
                    "run": expected.run,
                    "execution_error": {
                        "type": type(exc).__name__,
                        "message": str(exc),
                    },
                }
                for remaining in pending.values():
                    remaining.cancel()
                break
            source_difference = _different(expected, source)
            clean_difference = _different(expected, clean)
            cross_difference = {
                key: {"source": source.to_dict()[key], "clean": clean.to_dict()[key]}
                for key in source.to_dict()
                if source.to_dict()[key] != clean.to_dict()[key]
            }
            if not source_difference:
                source_rows.append(source)
            if not clean_difference:
                clean_rows.append(clean)
            if source_difference or clean_difference or cross_difference:
                mismatch = {
                    "run": expected.run,
                    "source_vs_raw": source_difference,
                    "cleanroom_vs_raw": clean_difference,
                    "source_vs_cleanroom": cross_difference,
                }
                for remaining in pending.values():
                    remaining.cancel()
                break
            if next_to_submit <= count:
                pending[next_to_submit] = executor.submit(
                    _pair, str(upstream), next_to_submit
                )
                next_to_submit += 1
    return source_rows, clean_rows, mismatch, rows_examined


def _write_report_atomic(path: Path, report: dict[str, Any]) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = (
        json.dumps(report, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False)
        + "\n"
    )
    temporary_name: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            temporary_name = handle.name
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_name, path)
    finally:
        if temporary_name is not None:
            temporary = Path(temporary_name)
            if temporary.exists():
                temporary.unlink()


def _execute(args: argparse.Namespace) -> int:
    local_contract = _authenticate_local_contract()
    local_source = _local_source_identity()
    local_protocol = _load_and_validate_local_protocol()
    identity = authenticate_checkout(args.upstream)
    all_published = parse_raw_rows(args.upstream)
    published = all_published[: args.runs]
    processed = parse_processed_targets(args.upstream)
    raw_summary = summarize_rows(all_published)
    declared = {
        "runs": raw_summary.runs,
        "mean_evaluations": raw_summary.mean_evaluations,
        "median_evaluations": raw_summary.median_evaluations,
        "q1_evaluations": raw_summary.q1_evaluations,
        "q3_evaluations": raw_summary.q3_evaluations,
    }
    h4_pass = declared == processed == local_protocol["published_targets"]
    formula = _formula_gates()
    source_rows, clean_rows, mismatch, rows_examined = _replay(
        Path(args.upstream).resolve(), published, args.workers
    )
    post_run_authentication: dict[str, Any]
    try:
        identity_end = authenticate_checkout(args.upstream)
        local_contract_end = _authenticate_local_contract()
        local_source_end = _local_source_identity()
        ending_rows = parse_raw_rows(args.upstream)
        ending_processed = parse_processed_targets(args.upstream)
        h0_pass = (
            identity_end == identity
            and local_contract_end == local_contract
            and local_source_end == local_source
            and canonical_rows_sha256(ending_rows)
            == canonical_rows_sha256(all_published)
            and ending_processed == processed
        )
        post_run_authentication = {
            "status": "PASS" if h0_pass else "FAIL",
            "source_identity": identity_end.to_dict(),
            "local_contract_sha256": local_contract_end,
            "local_source_identity": local_source_end,
        }
    except Exception as exc:
        h0_pass = False
        post_run_authentication = {
            "status": "FAIL",
            "error": {"type": type(exc).__name__, "message": str(exc)},
        }
    source_rows_pass = len(source_rows) == args.runs
    clean_rows_pass = len(clean_rows) == args.runs
    complete = args.runs == EXPECTED_RUNS
    source_difference = (mismatch or {}).get("source_vs_raw")
    clean_difference = (mismatch or {}).get("cleanroom_vs_raw")
    execution_error = (mismatch or {}).get("execution_error")
    h5_status = (
        "PASS"
        if source_rows_pass and complete
        else "PASS_PREFIX_ONLY"
        if source_rows_pass
        else "FAIL"
        if source_difference or execution_error
        else "NOT_EVALUATED_AFTER_OTHER_GATE_FAILURE"
    )
    h6_status = (
        "PASS"
        if clean_rows_pass and complete
        else "PASS_PREFIX_ONLY"
        if clean_rows_pass
        else "FAIL"
        if clean_difference
        else "NOT_EVALUATED_AFTER_OTHER_GATE_FAILURE"
    )
    formula_pass = all(
        formula[name]["status"] == "PASS"
        for name in ("H2_paper_formula", "H3_profile_isolation")
    )
    h0_to_h6_pass = (
        complete
        and h0_pass
        and formula_pass
        and h4_pass
        and h5_status == "PASS"
        and h6_status == "PASS"
    )
    target_status = (
        "PASS_TARGET_ARTIFACT_REPLAY"
        if h0_to_h6_pass
        else "PASS_PREFIX_ONLY"
        if h0_pass
        and source_rows_pass
        and clean_rows_pass
        and formula_pass
        and h4_pass
        else "FAIL"
    )

    report = {
        "schema_version": 1,
        "candidate_id": "EU26-07",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "claim_status": target_status,
        "paper_level_status": "BLOCKED_PAPER_SOURCE_DIVERGENCES",
        "requested_runs": args.runs,
        "requested_workers": args.workers,
        "environment": {
            "python": sys.version.split()[0],
            "numpy": np.__version__,
            "scipy": scipy.__version__,
            "platform": platform.platform(),
        },
        "source_identity": identity.to_dict(),
        "local_contract_sha256": local_contract,
        "local_source_identity": local_source,
        "local_protocol": local_protocol,
        "post_run_authentication": post_run_authentication,
        "published": {
            "raw_artifact_sha256": RAW_SHA256,
            "canonical_rows_sha256": canonical_rows_sha256(all_published),
            "processed_targets": processed,
            "recomputed_summary": raw_summary.to_dict(),
            "sd_provenance": "derived diagnostic; not printed in processed artifact",
        },
        "replay": {
            "rows_examined": rows_examined,
            "source_rows_compared": len(source_rows),
            "cleanroom_rows_compared": len(clean_rows),
            "first_failure": mismatch,
            "source_rows_sha256": canonical_rows_sha256(source_rows) if source_rows else None,
            "cleanroom_rows_sha256": canonical_rows_sha256(clean_rows) if clean_rows else None,
            "expected_prefix_sha256": canonical_rows_sha256(published),
        },
        "gates": {
            "H0_source_freeze": "PASS" if h0_pass else "FAIL",
            "H1_eligibility": "PASS_FROZEN_AUDIT",
            "H2_paper_formula": formula["H2_paper_formula"]["status"],
            "H3_profile_isolation": formula["H3_profile_isolation"]["status"],
            "H4_published_data_integrity": "PASS" if h4_pass else "FAIL",
            "H5_source_native_replay": h5_status,
            "H6_cleanroom_replay": h6_status,
            "H7_cross_language": "NOT_RUN_BY_THIS_SCRIPT",
        },
        "formula_witness": formula,
        "claim_boundaries": [
            "The source adapter verifies an author-linked Git commit, not an archival release.",
            "Artifact replay uses the Jump-specialized source profile, not literal paper pseudocode.",
            "PASS_FULL is forbidden by frozen paper/source semantic differences.",
        ],
    }
    _write_report_atomic(args.output, report)
    print(json.dumps({"claim_status": target_status, "rows": len(source_rows)}))
    return 0 if target_status != "FAIL" else 1


def main() -> int:
    args = parse_args()
    if args.runs < 1 or args.runs > EXPECTED_RUNS:
        raise SystemExit(f"--runs must lie in 1..{EXPECTED_RUNS}")
    if args.workers < 1:
        raise SystemExit("--workers must be positive")
    try:
        return _execute(args)
    except Exception as exc:
        failure = {
            "schema_version": 1,
            "candidate_id": "EU26-07",
            "generated_at_utc": datetime.now(timezone.utc).isoformat(),
            "claim_status": "FAIL",
            "paper_level_status": "BLOCKED_PAPER_SOURCE_DIVERGENCES",
            "requested_runs": args.runs,
            "requested_workers": args.workers,
            "failure_stage": "unhandled_verification_exception",
            "first_failure": {
                "type": type(exc).__name__,
                "message": str(exc),
            },
            "gates": {
                "H0_source_freeze": "FAIL_OR_NOT_EVALUATED",
                "H1_eligibility": "NOT_EVALUATED",
                "H2_paper_formula": "NOT_EVALUATED",
                "H3_profile_isolation": "NOT_EVALUATED",
                "H4_published_data_integrity": "NOT_EVALUATED",
                "H5_source_native_replay": "NOT_EVALUATED",
                "H6_cleanroom_replay": "NOT_EVALUATED",
                "H7_cross_language": "NOT_RUN_BY_THIS_SCRIPT",
            },
        }
        _write_report_atomic(args.output, failure)
        print(json.dumps({"claim_status": "FAIL", "error": type(exc).__name__}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
