#!/usr/bin/env python3
"""Run a frozen GESMR hardware-portability profile.

The algorithm inside each seed-run remains sequential. Independent seeds are
dispatched to a fixed-size process pool to test four/eight-worker batching.
"""

from __future__ import annotations

import os

for _name in (
    "OMP_NUM_THREADS",
    "OPENBLAS_NUM_THREADS",
    "MKL_NUM_THREADS",
    "NUMEXPR_NUM_THREADS",
    "VECLIB_MAXIMUM_THREADS",
):
    os.environ[_name] = "1"

import argparse
import csv
from concurrent.futures import ProcessPoolExecutor
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import platform
import statistics
import struct
import subprocess
import sys
import time
from typing import Any

import numpy as np


SCRIPT = Path(__file__).resolve()
CANDIDATE = SCRIPT.parents[2]
PYTHON_ENV = CANDIDATE / "environments" / "python"
sys.path.insert(0, str(PYTHON_ENV))

from gesmr import GESMRConfig, get_benchmark, run_gesmr  # noqa: E402


PROTOCOL_ID = "GESMR-HW-PORTABILITY-v1"
HASH_DOMAIN = b"GESMR-HW-V1\0"
THREAD_ENV = (
    "OMP_NUM_THREADS",
    "OPENBLAS_NUM_THREADS",
    "MKL_NUM_THREADS",
    "NUMEXPR_NUM_THREADS",
    "VECLIB_MAXIMUM_THREADS",
)
CONFIG = GESMRConfig()
CORRECTNESS_SPEC = {
    ("sphere", 30, 1.0, 300, seed) for seed in range(40)
}
THROUGHPUT_SPEC = {
    (function, 100, 10.0, 1000, seed)
    for function in ("ackley", "griewank", "rastrigin", "rosenbrock", "sphere")
    for seed in range(8)
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--label", required=True)
    parser.add_argument("--workers", required=True, type=int)
    parser.add_argument("--logical-cpus", required=True, type=int)
    parser.add_argument("--timing-repeats", type=int, default=5)
    parser.add_argument(
        "--matrix",
        type=Path,
        default=CANDIDATE / "config" / "hardware_smoke_matrix.csv",
    )
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--hashes", required=True, type=Path)
    return parser.parse_args()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _read_text(path: str) -> str | None:
    try:
        return Path(path).read_text(encoding="utf-8").strip()
    except (OSError, UnicodeDecodeError):
        return None


def _git_sha() -> str | None:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=CANDIDATE,
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def _git_source_state(paths: dict[str, Path]) -> dict[str, list[str]]:
    """Return source-scoped Git state without inspecting unrelated user changes."""

    try:
        root = Path(
            subprocess.check_output(
                ["git", "rev-parse", "--show-toplevel"],
                cwd=CANDIDATE,
                text=True,
                stderr=subprocess.DEVNULL,
            ).strip()
        ).resolve()
    except (OSError, subprocess.CalledProcessError):
        return {"untracked": sorted(paths), "different_from_head": sorted(paths)}

    untracked: list[str] = []
    different: list[str] = []
    for name, path in paths.items():
        try:
            relative = path.resolve().relative_to(root)
        except ValueError:
            untracked.append(name)
            different.append(name)
            continue
        tracked = subprocess.run(
            ["git", "ls-files", "--error-unmatch", "--", str(relative)],
            cwd=root,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        ).returncode == 0
        if not tracked:
            untracked.append(name)
            continue
        clean = subprocess.run(
            ["git", "diff", "--quiet", "HEAD", "--", str(relative)],
            cwd=root,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        ).returncode == 0
        if not clean:
            different.append(name)
    return {"untracked": sorted(untracked), "different_from_head": sorted(different)}


def _cpu_model_and_mhz() -> tuple[str | None, dict[str, float | None]]:
    model = None
    mhz: list[float] = []
    try:
        for line in Path("/proc/cpuinfo").read_text(encoding="utf-8").splitlines():
            if line.startswith("model name") and model is None:
                model = line.split(":", 1)[1].strip()
            elif line.startswith("cpu MHz"):
                mhz.append(float(line.split(":", 1)[1]))
    except (OSError, ValueError, IndexError):
        pass
    samples = {
        "minimum": min(mhz) if mhz else None,
        "median": statistics.median(mhz) if mhz else None,
        "maximum": max(mhz) if mhz else None,
    }
    return model, samples


def _memory_bytes() -> int | None:
    try:
        return os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES")
    except (ValueError, OSError):
        return None


def _hardware_manifest(affinity_before: list[int], affinity_after: list[int]) -> dict[str, Any]:
    model, mhz = _cpu_model_and_mhz()
    blas = np.__config__.CONFIG.get("Build Dependencies", {}).get("blas", {})
    return {
        "platform": platform.platform(),
        "system": platform.system(),
        "machine": platform.machine(),
        "cpu_model": model,
        "cpu_mhz_snapshot": mhz,
        "ghz_controlled": False,
        "os_cpu_count": os.cpu_count(),
        "affinity_before": affinity_before,
        "affinity_after": affinity_after,
        "cgroup_cpu_max": _read_text("/sys/fs/cgroup/cpu.max"),
        "cgroup_cpuset": _read_text("/sys/fs/cgroup/cpuset.cpus.effective"),
        "cgroup_memory_max": _read_text("/sys/fs/cgroup/memory.max"),
        "visible_memory_bytes": _memory_bytes(),
        "python": sys.version,
        "numpy": np.__version__,
        "blas_name": blas.get("name"),
        "blas_version": blas.get("version"),
        "thread_environment": {name: os.environ.get(name) for name in THREAD_ENV},
        "execution_context": {
            "github_actions": os.environ.get("GITHUB_ACTIONS") == "true",
            "github_run_id": os.environ.get("GITHUB_RUN_ID"),
            "github_run_attempt": os.environ.get("GITHUB_RUN_ATTEMPT"),
            "runner_name": os.environ.get("RUNNER_NAME"),
            "runner_environment": os.environ.get("RUNNER_ENVIRONMENT"),
        },
    }


def _load_matrix(path: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    correctness: list[dict[str, Any]] = []
    throughput: list[dict[str, Any]] = []
    with path.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            if row["suite"] not in {"correctness", "throughput"}:
                raise ValueError(f"unknown suite {row['suite']!r}")
            base = {
                "function": row["function"],
                "dimension": int(row["dimension"]),
                "initial_std": float(row["initial_std"]),
                "generations": int(row["generations"]),
            }
            for seed in range(int(row["seed_start"]), int(row["seed_end"]) + 1):
                case = dict(base, seed=seed)
                case["case_id"] = (
                    f"{case['function']}-d{case['dimension']}-s{case['initial_std']:g}"
                    f"-g{case['generations']}-seed{seed:02d}"
                )
                (correctness if row["suite"] == "correctness" else throughput).append(case)
    correctness_spec = {
        (
            case["function"],
            case["dimension"],
            case["initial_std"],
            case["generations"],
            case["seed"],
        )
        for case in correctness
    }
    throughput_spec = {
        (
            case["function"],
            case["dimension"],
            case["initial_std"],
            case["generations"],
            case["seed"],
        )
        for case in throughput
    }
    if correctness_spec != CORRECTNESS_SPEC or len(correctness) != len(CORRECTNESS_SPEC):
        raise ValueError("correctness matrix differs from the frozen 40-case specification")
    if throughput_spec != THROUGHPUT_SPEC or len(throughput) != len(THROUGHPUT_SPEC):
        raise ValueError("throughput matrix differs from the frozen 40-case specification")
    return correctness, throughput


def _hash_part(digest: Any, name: str, payload: bytes) -> None:
    encoded = name.encode("utf-8")
    digest.update(struct.pack("<Q", len(encoded)))
    digest.update(encoded)
    digest.update(struct.pack("<Q", len(payload)))
    digest.update(payload)


def _canonical_array(value: Any) -> np.ndarray:
    return np.ascontiguousarray(np.asarray(value, dtype="<f8"))


def _result_hash(case: dict[str, Any], result: Any) -> str:
    digest = hashlib.sha256(HASH_DOMAIN)
    metadata = {
        "function": case["function"],
        "dimension": case["dimension"],
        "initial_std": case["initial_std"],
        "generations": case["generations"],
        "seed": case["seed"],
        "objective_call_count": result.objective_call_count,
        "objective_row_evaluation_count": result.objective_row_evaluation_count,
        "gesmr_config": asdict(CONFIG),
    }
    _hash_part(digest, "metadata", json.dumps(metadata, sort_keys=True).encode("utf-8"))
    for name in (
        "final_population",
        "final_fitness",
        "final_sigmas",
        "best_fitness_history",
        "geometric_mean_sigma_history",
        "arithmetic_mean_sigma_history",
        "sigma_history",
    ):
        array = _canonical_array(getattr(result, name))
        _hash_part(digest, f"{name}.shape", json.dumps(array.shape).encode("ascii"))
        _hash_part(digest, name, array.tobytes(order="C"))
    return digest.hexdigest()


def _numeric_signature(result: Any) -> dict[str, Any]:
    checkpoints = (0, 1, 10, 50, 100, 200, 300)
    return {
        "best_fitness": [float(result.best_fitness_history[index]) for index in checkpoints],
        "geometric_mean_sigma": [
            float(result.geometric_mean_sigma_history[index]) for index in checkpoints
        ],
        "arithmetic_mean_sigma": [
            float(result.arithmetic_mean_sigma_history[index]) for index in checkpoints
        ],
        "final_sigmas": [float(value) for value in result.final_sigmas],
        "final_fitness_min": float(np.min(result.final_fitness)),
        "final_fitness_median": float(np.median(result.final_fitness)),
        "final_fitness_max": float(np.max(result.final_fitness)),
    }


def _run(case: dict[str, Any]) -> Any:
    return run_gesmr(
        get_benchmark(case["function"]),
        dimension=case["dimension"],
        initial_std=case["initial_std"],
        seed=case["seed"],
        generations=case["generations"],
        config=CONFIG,
    )


def _worker_state() -> dict[str, Any]:
    return {
        "pid": os.getpid(),
        "affinity": sorted(os.sched_getaffinity(0)),
        "thread_environment": {name: os.environ.get(name) for name in THREAD_ENV},
    }


def _correctness_case(case: dict[str, Any]) -> dict[str, Any]:
    result = _run(case)
    arrays = (
        result.final_population,
        result.final_fitness,
        result.final_sigmas,
        result.best_fitness_history,
        result.geometric_mean_sigma_history,
        result.arithmetic_mean_sigma_history,
        result.sigma_history,
    )
    finite = all(np.all(np.isfinite(array)) for array in arrays)
    positive_sigmas = bool(np.all(result.sigma_history > 0.0))
    mutation_changed = bool(np.any(result.sigma_history[1:] != result.sigma_history[:-1]))
    scale = np.maximum(1.0, np.abs(result.best_fitness_history[:-1]))
    elitism_ok = bool(np.all(np.diff(result.best_fitness_history) <= 1e-12 * scale))
    expected_calls = case["generations"] + 1
    expected_rows = (CONFIG.non_elite_size + 1) * expected_calls
    accounting_ok = (
        result.objective_call_count == expected_calls
        and result.objective_row_evaluation_count == expected_rows
    )
    return {
        "case_id": case["case_id"],
        "seed": case["seed"],
        "sha256_v1": _result_hash(case, result),
        "numeric_signature": _numeric_signature(result),
        "finite": finite,
        "positive_sigmas": positive_sigmas,
        "mutation_changed": mutation_changed,
        "elitism_ok": elitism_ok,
        "accounting_ok": accounting_ok,
        "worker": _worker_state(),
    }


def _timing_case(case: dict[str, Any]) -> tuple[str, str, int, int, dict[str, Any], float]:
    cpu_started = time.process_time()
    result = _run(case)
    algorithm_cpu_seconds = time.process_time() - cpu_started
    return (
        case["case_id"],
        _result_hash(case, result),
        result.objective_call_count,
        result.objective_row_evaluation_count,
        _worker_state(),
        algorithm_cpu_seconds,
    )


def _endpoint_digest(rows: list[tuple[str, str, int, int, dict[str, Any], float]]) -> str:
    algorithm_endpoints = sorted(row[:4] for row in rows)
    payload = json.dumps(
        algorithm_endpoints, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _aggregate_correctness_hash(rows: list[dict[str, Any]]) -> str:
    payload = "\n".join(
        f"{row['case_id']}\t{row['sha256_v1']}" for row in sorted(rows, key=lambda x: x["case_id"])
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def main() -> int:
    args = parse_args()
    if args.workers not in (4, 8) or args.logical_cpus not in (4, 8):
        raise SystemExit("--workers and --logical-cpus must be 4 or 8")
    if args.workers != args.logical_cpus:
        raise SystemExit("the frozen profiles require one worker per requested logical CPU")
    if args.timing_repeats != 5:
        raise SystemExit("the frozen protocol requires exactly five timing repetitions")
    if not hasattr(os, "sched_getaffinity") or not hasattr(os, "sched_setaffinity"):
        raise SystemExit("Linux CPU-affinity support is required")

    affinity_before = sorted(os.sched_getaffinity(0))
    if len(affinity_before) < args.logical_cpus:
        raise SystemExit(
            f"profile requests {args.logical_cpus} CPUs but only {affinity_before} are available"
        )
    selected = set(affinity_before[: args.logical_cpus])
    os.sched_setaffinity(0, selected)
    affinity_after = sorted(os.sched_getaffinity(0))
    if len(affinity_after) != args.logical_cpus:
        raise SystemExit("failed to enforce the requested CPU affinity")

    correctness_cases, throughput_cases = _load_matrix(args.matrix)
    source_paths = {
        "core.py": PYTHON_ENV / "gesmr" / "core.py",
        "benchmarks.py": PYTHON_ENV / "gesmr" / "benchmarks.py",
        "requirements.txt": PYTHON_ENV / "requirements.txt",
        "optimizer_config.json": CANDIDATE / "config" / "optimizer_config.json",
        "hardware_smoke_matrix.csv": args.matrix,
        "hardware_portability_contract.md": CANDIDATE
        / "preregistration"
        / "hardware_portability_contract.md",
        "run_portability_suite.py": SCRIPT,
    }
    git_sha_start = _git_sha()
    source_sha256_start = {name: _sha256_file(path) for name, path in source_paths.items()}
    git_source_state_start = _git_source_state(source_paths)
    hardware = _hardware_manifest(affinity_before, affinity_after)

    serial = [_correctness_case(case) for case in correctness_cases]
    serial_by_id = {row["case_id"]: row for row in serial}

    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        parallel = list(pool.map(_correctness_case, correctness_cases))
        warm_rows = list(pool.map(_timing_case, throughput_cases))
        warm_digest = _endpoint_digest(warm_rows)
        timings: list[float] = []
        timed_digests: list[str] = []
        timed_worker_cpu_seconds: list[float] = []
        worker_states = [row["worker"] for row in parallel]
        worker_states.extend(row[4] for row in warm_rows)
        for _ in range(args.timing_repeats):
            started = time.perf_counter()
            rows = list(pool.map(_timing_case, throughput_cases))
            timings.append(time.perf_counter() - started)
            timed_digests.append(_endpoint_digest(rows))
            timed_worker_cpu_seconds.append(sum(row[5] for row in rows))
            worker_states.extend(row[4] for row in rows)

    git_sha_end = _git_sha()
    source_sha256_end = {name: _sha256_file(path) for name, path in source_paths.items()}
    git_source_state_end = _git_source_state(source_paths)

    parallel_by_id = {row["case_id"]: row for row in parallel}
    mismatches = sorted(
        case_id
        for case_id, row in serial_by_id.items()
        if parallel_by_id.get(case_id, {}).get("sha256_v1") != row["sha256_v1"]
    )
    invariant_failures = sorted(
        row["case_id"]
        for row in parallel
        if not all(
            row[key]
            for key in (
                "finite",
                "positive_sigmas",
                "mutation_changed",
                "elitism_ok",
                "accounting_ok",
            )
        )
    )
    timing_repeatable = all(value == warm_digest for value in timed_digests)
    worker_pids = sorted({state["pid"] for state in worker_states})
    worker_affinity_failures = sorted(
        {
            state["pid"]
            for state in worker_states
            if state["affinity"] != affinity_after
        }
    )
    worker_thread_failures = sorted(
        {
            state["pid"]
            for state in worker_states
            if any(state["thread_environment"].get(name) != "1" for name in THREAD_ENV)
        }
    )
    worker_pool_failures: list[str] = []
    if len(worker_pids) != args.workers:
        worker_pool_failures.append("unique_worker_pid_count_mismatch")
    if worker_affinity_failures:
        worker_pool_failures.append("worker_affinity_mismatch")
    if worker_thread_failures:
        worker_pool_failures.append("worker_thread_limit_mismatch")
    median_seconds = statistics.median(timings)
    deviations = [abs(value - median_seconds) for value in timings]
    mad_seconds = statistics.median(deviations)
    profile_pass = (
        not mismatches
        and not invariant_failures
        and timing_repeatable
        and not worker_pool_failures
    )

    provenance_failures: list[str] = []
    if not git_sha_start:
        provenance_failures.append("missing_git_sha")
    if any(len(value) != 64 for value in source_sha256_start.values()):
        provenance_failures.append("invalid_source_hash")
    if git_source_state_start["untracked"]:
        provenance_failures.append("source_not_tracked_at_git_sha")
    if git_source_state_start["different_from_head"]:
        provenance_failures.append("source_differs_from_git_sha")
    if (
        git_sha_start != git_sha_end
        or source_sha256_start != source_sha256_end
        or git_source_state_start != git_source_state_end
    ):
        provenance_failures.append("source_or_git_head_changed_during_execution")
    for field in ("platform", "machine", "cpu_model", "cgroup_cpu_max", "cgroup_cpuset"):
        if not hardware.get(field):
            provenance_failures.append(f"missing_hardware_{field}")
    if not hardware.get("cgroup_memory_max") and not hardware.get("visible_memory_bytes"):
        provenance_failures.append("missing_memory_metadata")
    if not hardware.get("python") or not hardware.get("numpy") or not hardware.get("blas_name"):
        provenance_failures.append("missing_runtime_metadata")
    if any(hardware["thread_environment"].get(name) != "1" for name in THREAD_ENV):
        provenance_failures.append("numerical_thread_limit_not_one")
    if hardware.get("affinity_after") != affinity_after:
        provenance_failures.append("affinity_manifest_mismatch")

    profile_pass = profile_pass and not provenance_failures
    report = {
        "protocol_id": PROTOCOL_ID,
        "profile_label": args.label,
        "verification_scope": "FORMULA_HARDWARE_PORTABILITY_NOT_PUBLISHED_REPRODUCTION",
        "git_sha": git_sha_start,
        "source_sha256": source_sha256_start,
        "git_source_state": git_source_state_start,
        "provenance_window": {
            "git_sha_end": git_sha_end,
            "source_sha256_end": source_sha256_end,
            "git_source_state_end": git_source_state_end,
        },
        "requested_workers": args.workers,
        "requested_logical_cpus": args.logical_cpus,
        "hardware": hardware,
        "provenance_failures": provenance_failures,
        "worker_pool": {
            "unique_worker_pids": worker_pids,
            "unique_worker_pid_count": len(worker_pids),
            "affinity_failure_pids": worker_affinity_failures,
            "thread_limit_failure_pids": worker_thread_failures,
            "failures": worker_pool_failures,
        },
        "correctness": {
            "case_count": len(parallel),
            "seeds": sorted(row["seed"] for row in parallel),
            "serial_parallel_hash_mismatches": mismatches,
            "invariant_failures": invariant_failures,
            "aggregate_sha256_v1": _aggregate_correctness_hash(parallel),
            "cases": sorted(parallel, key=lambda row: row["case_id"]),
        },
        "timing": {
            "warmup_endpoint_digest": warm_digest,
            "timed_endpoint_digests": timed_digests,
            "repeatable_endpoints": timing_repeatable,
            "batch_case_count": len(throughput_cases),
            "retained_batch_seconds": timings,
            "median_batch_seconds": median_seconds,
            "mad_batch_seconds": mad_seconds,
            "mad_over_median": mad_seconds / median_seconds,
            "median_jobs_per_second": len(throughput_cases) / median_seconds,
            "retained_algorithm_worker_cpu_seconds": timed_worker_cpu_seconds,
            "median_algorithm_worker_cpu_seconds": statistics.median(
                timed_worker_cpu_seconds
            ),
        },
        "profile_status": "PASS" if profile_pass else "FAIL",
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.hashes.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    with args.hashes.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, delimiter="\t", lineterminator="\n")
        writer.writerow(("case_id", "seed", "sha256_v1"))
        for row in sorted(parallel, key=lambda value: value["case_id"]):
            writer.writerow((row["case_id"], row["seed"], row["sha256_v1"]))

    summary = {
        "profile_label": args.label,
        "profile_status": report["profile_status"],
        "aggregate_sha256_v1": report["correctness"]["aggregate_sha256_v1"],
        "median_batch_seconds": median_seconds,
        "median_jobs_per_second": report["timing"]["median_jobs_per_second"],
        "hash_mismatch_count": len(mismatches),
        "invariant_failure_count": len(invariant_failures),
    }
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if profile_pass else 1


if __name__ == "__main__":
    raise SystemExit(main())
