#!/usr/bin/env python3
"""Run one frozen USA26-04 formula-portability profile.

Only independent deterministic formula cases are parallelized. No genetic
algorithm, stochastic paper endpoint, or Table 1 comparison is executed.
"""

from __future__ import annotations

import os

THREAD_ENV = (
    "OMP_NUM_THREADS",
    "OPENBLAS_NUM_THREADS",
    "MKL_NUM_THREADS",
    "NUMEXPR_NUM_THREADS",
    "VECLIB_MAXIMUM_THREADS",
)
for _thread_name in THREAD_ENV:
    os.environ[_thread_name] = "1"

import argparse
from concurrent.futures import ProcessPoolExecutor
import hashlib
import json
import math
import multiprocessing
from pathlib import Path
import platform
import statistics
import subprocess
import sys
import time
from typing import Any


SCRIPT = Path(__file__).resolve()
CANDIDATE = SCRIPT.parents[2]
REPOSITORY = Path(
    subprocess.check_output(
        ["git", "rev-parse", "--show-toplevel"], cwd=CANDIDATE, text=True
    ).strip()
)
sys.path.insert(0, str(CANDIDATE / "environments" / "python"))

from banditverify.canonical import (  # noqa: E402
    canonical_json,
    formula_digest,
    sha256_file,
)
from banditverify.cases import execute_case, load_matrix  # noqa: E402
from banditverify.controller import (  # noqa: E402
    FIXTURE_STATE_PROVENANCE,
    standard_deviation_witness,
    tile_boundary_witness,
    tie_ambiguity_witness,
)
from banditverify.objectives import evaluate_objective  # noqa: E402
from banditverify.protocol import validate_protocol  # noqa: E402
from banditverify.rewards import evaluate_reward, printed_eq2_literal  # noqa: E402


PROTOCOL_ID = "USA26-04-FORMULA-PORTABILITY-v1"
_WORKER_BARRIER: Any = None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--label", required=True)
    parser.add_argument("--workers", required=True, type=int)
    parser.add_argument("--logical-cpus", required=True, type=int)
    parser.add_argument("--timing-repeats", default=5, type=int)
    parser.add_argument(
        "--matrix",
        type=Path,
        default=CANDIDATE / "config" / "hardware_formula_matrix.csv",
    )
    parser.add_argument("--matlab-report", type=Path)
    parser.add_argument("--require-matlab-report", action="store_true")
    parser.add_argument("--require-exact-visible-cpus", action="store_true")
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--hashes", required=True, type=Path)
    return parser.parse_args()


def _read_text(path: str) -> str | None:
    try:
        return Path(path).read_text(encoding="utf-8").strip()
    except (OSError, UnicodeDecodeError):
        return None


def _git_head() -> str:
    return subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=REPOSITORY, text=True
    ).strip()


def _source_paths() -> list[Path]:
    tracked = subprocess.check_output(
        [
            "git",
            "ls-files",
            "--",
            "candidates/USA26-04",
            ".github/workflows/usa26-04-validation.yml",
            "registry/cohort_2026_12/registry.json",
            "registry/cohort_2026_12/hard_gate_assessments.json",
            "registry/cohort_2026_12/README.md",
            "registry/cohort_2026_12/screening_report.md",
        ],
        cwd=REPOSITORY,
        text=True,
    ).splitlines()
    paths = [REPOSITORY / item for item in tracked if "/results/" not in item]
    if not paths:
        raise RuntimeError("no tracked USA26-04 source files were found")
    return sorted(paths)


def _source_hashes(paths: list[Path]) -> dict[str, str]:
    return {
        str(path.relative_to(REPOSITORY)): sha256_file(path)
        for path in paths
    }


def _source_git_state() -> list[str]:
    output = subprocess.check_output(
        [
            "git",
            "status",
            "--porcelain",
            "--untracked-files=all",
            "--",
            "candidates/USA26-04",
            ".github/workflows/usa26-04-validation.yml",
            "registry/cohort_2026_12/registry.json",
            "registry/cohort_2026_12/hard_gate_assessments.json",
            "registry/cohort_2026_12/README.md",
            "registry/cohort_2026_12/screening_report.md",
        ],
        cwd=REPOSITORY,
        text=True,
    )
    return sorted(line for line in output.splitlines() if line.strip())


def _cpu_model_and_mhz() -> tuple[str | None, dict[str, float | None]]:
    model = None
    samples: list[float] = []
    try:
        for line in Path("/proc/cpuinfo").read_text(encoding="utf-8").splitlines():
            if line.startswith("model name") and model is None:
                model = line.split(":", 1)[1].strip()
            elif line.startswith("cpu MHz"):
                samples.append(float(line.split(":", 1)[1]))
    except (OSError, ValueError, IndexError):
        pass
    return model, {
        "minimum": min(samples) if samples else None,
        "median": statistics.median(samples) if samples else None,
        "maximum": max(samples) if samples else None,
    }


def _hardware_manifest(
    affinity_before: list[int], target_affinity: list[int], affinity_after: list[int]
) -> dict[str, Any]:
    model, mhz = _cpu_model_and_mhz()
    return {
        "platform": platform.platform(),
        "system": platform.system(),
        "machine": platform.machine(),
        "python": sys.version,
        "cpu_model": model,
        "cpu_mhz_snapshot": mhz,
        "ghz_controlled": False,
        "os_cpu_count": os.cpu_count(),
        "affinity_before": affinity_before,
        "target_affinity": target_affinity,
        "affinity_after": affinity_after,
        "cgroup_cpu_max": _read_text("/sys/fs/cgroup/cpu.max"),
        "cgroup_cpuset": _read_text("/sys/fs/cgroup/cpuset.cpus.effective"),
        "cgroup_memory_max": _read_text("/sys/fs/cgroup/memory.max"),
        "thread_environment": {name: os.environ.get(name) for name in THREAD_ENV},
        "execution_context": {
            "github_actions": os.environ.get("GITHUB_ACTIONS") == "true",
            "github_run_id": os.environ.get("GITHUB_RUN_ID"),
            "github_run_attempt": os.environ.get("GITHUB_RUN_ATTEMPT"),
            "runner_name": os.environ.get("RUNNER_NAME"),
        },
    }


def _worker_initialize(barrier: Any, target_affinity: list[int]) -> None:
    global _WORKER_BARRIER
    for name in THREAD_ENV:
        os.environ[name] = "1"
    if hasattr(os, "sched_setaffinity"):
        os.sched_setaffinity(0, set(target_affinity))
    _WORKER_BARRIER = barrier


def _worker_case(case: dict[str, Any], candidate_text: str) -> dict[str, Any]:
    global _WORKER_BARRIER
    if _WORKER_BARRIER is not None:
        _WORKER_BARRIER.wait(timeout=60)
        _WORKER_BARRIER = None
    record = execute_case(case, Path(candidate_text))
    return {
        "record": record,
        "pid": os.getpid(),
        "affinity": sorted(os.sched_getaffinity(0))
        if hasattr(os, "sched_getaffinity")
        else None,
        "thread_environment": {name: os.environ.get(name) for name in THREAD_ENV},
    }


def _run_parallel(
    cases: list[dict[str, Any]], workers: int, target_affinity: list[int]
) -> dict[str, Any]:
    context = multiprocessing.get_context("fork")
    barrier = context.Barrier(workers)
    started = time.perf_counter()
    with ProcessPoolExecutor(
        max_workers=workers,
        mp_context=context,
        initializer=_worker_initialize,
        initargs=(barrier, target_affinity),
    ) as executor:
        futures = [
            executor.submit(_worker_case, case, str(CANDIDATE)) for case in cases
        ]
        rows = [future.result() for future in futures]
    elapsed = time.perf_counter() - started
    records = sorted((row["record"] for row in rows), key=lambda item: item["case_id"])
    return {
        "elapsed_seconds": elapsed,
        "records": records,
        "digest": formula_digest(records),
        "worker_pids": sorted({row["pid"] for row in rows}),
        "worker_affinities": {
            str(row["pid"]): row["affinity"] for row in rows
        },
        "worker_thread_environments": {
            str(row["pid"]): row["thread_environment"] for row in rows
        },
    }


def _flatten_numeric(value: Any, path: str = "") -> list[tuple[str, float]]:
    if isinstance(value, bool) or value is None or isinstance(value, str):
        return []
    if isinstance(value, (int, float)):
        return [(path, float(value))]
    if isinstance(value, list):
        result: list[tuple[str, float]] = []
        for index, child in enumerate(value):
            result.extend(_flatten_numeric(child, f"{path}[{index}]"))
        return result
    if isinstance(value, dict):
        result = []
        for key in sorted(value):
            result.extend(_flatten_numeric(value[key], f"{path}.{key}"))
        return result
    raise TypeError(f"unsupported comparison type at {path}: {type(value).__name__}")


def _matlab_fixed_tape_gate(
    path: Path | None, serial_records: list[dict[str, Any]]
) -> dict[str, Any]:
    if path is None:
        return {
            "status": "NOT_EVALUATED_MATLAB_REPORT_ABSENT",
            "state_provenance": FIXTURE_STATE_PROVENANCE,
            "paper_level_status": "BLOCKED_G5_G9",
        }
    report = json.loads(path.read_text(encoding="utf-8"))
    python_result = next(
        row["result"] for row in serial_records if row["case_id"] == "controller-fixed-tape"
    )
    exact_keys = (
        "verification_scope",
        "paper_level_status",
        "published_result_status",
        "state_provenance",
        "branch",
        "argmax_tile",
        "selected_tile",
    )
    exact_mismatches = [
        key for key in exact_keys if report.get(key) != python_result.get(key)
    ]
    numeric_keys = (
        "base_weights",
        "log_rate",
        "rate",
        "immediate_reward",
        "updates",
    )
    left = _flatten_numeric({key: python_result[key] for key in numeric_keys})
    right = _flatten_numeric({key: report.get(key) for key in numeric_keys})
    numeric_mismatches: list[str] = []
    if [path for path, _ in left] != [path for path, _ in right]:
        numeric_mismatches.append("NUMERIC_FIELD_SHAPE_MISMATCH")
    else:
        for (field, first), (_, second) in zip(left, right):
            if not math.isclose(first, second, abs_tol=1e-12, rel_tol=1e-12):
                numeric_mismatches.append(field)
    passed = (
        not exact_mismatches
        and not numeric_mismatches
        and report.get("state_provenance") == FIXTURE_STATE_PROVENANCE
    )
    return {
        "status": "PASS_CROSS_ENV_FIXED_TAPE" if passed else "FAIL_CROSS_ENV_FIXED_TAPE",
        "matlab_report": str(path.resolve()),
        "state_provenance": FIXTURE_STATE_PROVENANCE,
        "exact_mismatches": exact_mismatches,
        "numeric_mismatches": numeric_mismatches,
        "paper_level_status": "BLOCKED_G5_G9",
    }


def _adversarial_gate() -> dict[str, Any]:
    checks: dict[str, bool] = {}

    def rejects(name: str, action: Any) -> None:
        try:
            action()
        except (ArithmeticError, TypeError, ValueError, ZeroDivisionError):
            checks[name] = True
        else:
            checks[name] = False

    rejects("nonfinite_objective", lambda: evaluate_objective("sphere", [math.inf]))
    rejects("linear_log_domain", lambda: evaluate_reward("P2", [-2.0], [0.0]))
    rejects("printed_eq2_singleton", lambda: printed_eq2_literal([9.0], [3.0]))
    boundary = tile_boundary_witness()
    tie = tie_ambiguity_witness([0.0, 0.0, 0.0, 0.0], 0.0)
    sd = standard_deviation_witness()
    passed = (
        all(checks.values())
        and boundary["status"] == "AMBIGUITY_CONFIRMED"
        and boundary["resolution_chosen"] is False
        and tie["status"] == "AMBIGUITY_CONFIRMED"
        and tie["resolution_chosen"] is False
        and sd["status"] == "AMBIGUITY_CONFIRMED"
        and sd["resolution_chosen"] is False
    )
    return {
        "status": "PASS_FAIL_CLOSED_AND_AMBIGUITIES_RETAINED"
        if passed
        else "FAIL_ADVERSARIAL_GATE",
        "rejection_checks": checks,
        "boundary": boundary,
        "tie": tie,
        "standard_deviation": sd,
        "paper_level_status": "BLOCKED_G5_G9",
    }


def _write_hashes(path: Path, records: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# protocol_id\tUSA26-04-FORMULA-PORTABILITY-v1",
        "# verification_scope\tFORMULA_AND_AMBIGUITY_VALIDATION_ONLY",
        "# paper_level_status\tBLOCKED_G5_G9",
        "# published_result_status\tINCONCLUSIVE_PUBLISHED_RESULT",
        f"# fixed_controller_state_provenance\t{FIXTURE_STATE_PROVENANCE}",
        "case_id\tcanonical_record_sha256",
    ]
    for record in sorted(records, key=lambda item: item["case_id"]):
        digest = hashlib.sha256(canonical_json(record)).hexdigest()
        lines.append(f"{record['case_id']}\t{digest}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    args = parse_args()
    if platform.system() != "Linux" or not hasattr(os, "sched_getaffinity"):
        raise SystemExit("the frozen hardware profiles require Linux CPU affinity")
    if args.workers not in {4, 8} or args.logical_cpus not in {4, 8}:
        raise SystemExit("workers and logical CPUs must each be exactly 4 or 8")
    if args.workers != args.logical_cpus:
        raise SystemExit("the frozen profiles require one worker per requested logical CPU")
    if args.timing_repeats != 5:
        raise SystemExit("the frozen protocol requires exactly five timing repeats")
    frozen_matrix = (CANDIDATE / "config" / "hardware_formula_matrix.csv").resolve()
    if args.matrix.resolve() != frozen_matrix:
        raise SystemExit("formal profiles require the tracked frozen formula matrix")
    if args.require_matlab_report and args.matlab_report is None:
        raise SystemExit("--require-matlab-report requires --matlab-report")

    affinity_before = sorted(os.sched_getaffinity(0))
    if len(affinity_before) < args.logical_cpus:
        raise SystemExit(
            f"requested {args.logical_cpus} CPUs but affinity exposes {affinity_before}"
        )
    if args.require_exact_visible_cpus and (
        len(affinity_before) != args.logical_cpus
        or os.cpu_count() != args.logical_cpus
    ):
        raise SystemExit(
            "exact-visible-CPU profile requires os.cpu_count and affinity to equal "
            f"{args.logical_cpus}; got os.cpu_count={os.cpu_count()}, "
            f"affinity={affinity_before}"
        )
    target_affinity = affinity_before[: args.logical_cpus]
    os.sched_setaffinity(0, set(target_affinity))
    affinity_after = sorted(os.sched_getaffinity(0))

    protocol_summary = validate_protocol()
    cases = load_matrix(args.matrix.resolve())
    source_paths = _source_paths()
    head_before = _git_head()
    source_state_before = _source_git_state()
    source_hashes_before = _source_hashes(source_paths)

    serial_started = time.perf_counter()
    serial_records = [execute_case(case, CANDIDATE) for case in cases]
    serial_seconds = time.perf_counter() - serial_started
    serial_digest = formula_digest(serial_records)
    warmup = _run_parallel(cases, args.workers, target_affinity)
    repeats = [
        _run_parallel(cases, args.workers, target_affinity)
        for _ in range(args.timing_repeats)
    ]

    head_after = _git_head()
    source_state_after = _source_git_state()
    source_hashes_after = _source_hashes(source_paths)
    hardware = _hardware_manifest(affinity_before, target_affinity, affinity_after)
    protocol_h0 = (
        protocol_summary["paper_level_status"] == "BLOCKED_G5_G9"
        and protocol_summary["published_result_status"]
        == "INCONCLUSIVE_PUBLISHED_RESULT"
        and protocol_summary["executable_target_count"] == 0
    )
    h0_pass = (
        protocol_h0
        and head_before == head_after
        and not source_state_before
        and not source_state_after
        and source_hashes_before == source_hashes_after
        and affinity_after == target_affinity
        and all(os.environ.get(name) == "1" for name in THREAD_ENV)
    )
    h1_pass = all(row["status"] == "PASS_FORMULA_CASE" for row in serial_records)
    h2 = _matlab_fixed_tape_gate(args.matlab_report, serial_records)
    h3 = _adversarial_gate()

    parallel_batches = [warmup, *repeats]
    h4_pass = all(
        batch["records"] == serial_records
        and batch["digest"] == serial_digest
        and len(batch["worker_pids"]) == args.workers
        and all(affinity == target_affinity for affinity in batch["worker_affinities"].values())
        and all(
            all(environment.get(name) == "1" for name in THREAD_ENV)
            for environment in batch["worker_thread_environments"].values()
        )
        for batch in parallel_batches
    )
    gate_statuses = {
        "H0_provenance": {
            "status": "PASS_PROVENANCE_AND_ABSENCE" if h0_pass else "FAIL_PROVENANCE",
            "source_state_before": source_state_before,
            "source_state_after": source_state_after,
            "head_stable": head_before == head_after,
            "source_hashes_stable": source_hashes_before == source_hashes_after,
        },
        "H1_formula": {
            "status": "PASS_LOCAL_FORMULAS" if h1_pass else "FAIL_LOCAL_FORMULAS",
        },
        "H2_fixed_tape": h2,
        "H3_adversarial": h3,
        "H4_batch": {
            "status": "PASS_SERIAL_PARALLEL_REPEATABILITY"
            if h4_pass
            else "FAIL_SERIAL_PARALLEL_REPEATABILITY",
            "serial_digest": serial_digest,
            "warmup_digest": warmup["digest"],
            "repeat_digests": [batch["digest"] for batch in repeats],
            "worker_pid_counts": [len(batch["worker_pids"]) for batch in parallel_batches],
        },
        "H5_cross_profile": {
            "status": "NOT_EVALUATED_SINGLE_PROFILE",
        },
    }
    h2_pass = h2["status"] == "PASS_CROSS_ENV_FIXED_TAPE"
    core_pass = h0_pass and h1_pass and h3["status"].startswith("PASS_") and h4_pass
    if core_pass and h2_pass:
        profile_status = "PASS_PROFILE_H0_H4"
    elif core_pass and h2["status"] == "NOT_EVALUATED_MATLAB_REPORT_ABSENT":
        profile_status = "INCONCLUSIVE_H2_MATLAB_NOT_EVALUATED"
    else:
        profile_status = "FAIL_PROFILE_GATE"

    elapsed = [batch["elapsed_seconds"] for batch in repeats]
    report = {
        "protocol_id": PROTOCOL_ID,
        "verification_scope": "FORMULA_AND_AMBIGUITY_VALIDATION_ONLY",
        "paper_level_status": "BLOCKED_G5_G9",
        "published_result_status": "INCONCLUSIVE_PUBLISHED_RESULT",
        "registry_status": "conditional_noneligible",
        "fixed_controller_state_provenance": FIXTURE_STATE_PROVENANCE,
        "profile_label": args.label,
        "profile_status": profile_status,
        "requested_workers": args.workers,
        "requested_logical_cpus": args.logical_cpus,
        "git_sha": head_before,
        "source_sha256": source_hashes_before,
        "protocol_summary": protocol_summary,
        "hardware": hardware,
        "gates": gate_statuses,
        "correctness": {
            "case_ids": [record["case_id"] for record in serial_records],
            "aggregate_digest": serial_digest,
            "cases": serial_records,
        },
        "timing": {
            "serial_seconds": serial_seconds,
            "warmup_parallel_seconds": warmup["elapsed_seconds"],
            "retained_parallel_seconds": elapsed,
            "retained_repeat_count": len(elapsed),
            "median_parallel_seconds": statistics.median(elapsed),
            "median_cases_per_second": len(cases) / statistics.median(elapsed),
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
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    _write_hashes(args.hashes, serial_records)
    print(json.dumps(report, indent=2, sort_keys=True, allow_nan=False))
    if args.require_matlab_report:
        return 0 if profile_status == "PASS_PROFILE_H0_H4" else 1
    return 0 if profile_status in {
        "PASS_PROFILE_H0_H4",
        "INCONCLUSIVE_H2_MATLAB_NOT_EVALUATED",
    } else 1


if __name__ == "__main__":
    raise SystemExit(main())
