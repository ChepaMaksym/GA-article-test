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
import shutil
import statistics
import subprocess
import sys
import tempfile
import time
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
from banditverify.cases import execute_case, load_matrix  # noqa: E402
from banditverify.controller import (  # noqa: E402
    FIXTURE_STATE_PROVENANCE,
    standard_deviation_witness,
    tile_boundary_witness,
    tie_ambiguity_witness,
)
from banditverify.objectives import evaluate_objective  # noqa: E402
from banditverify.matlab_report import payload_sha256, validate_matlab_report  # noqa: E402
from banditverify.protocol import validate_protocol  # noqa: E402
from banditverify.provenance import (  # noqa: E402
    git_head,
    repository_root,
    source_git_state,
    source_hashes,
    source_paths,
)
from banditverify.rewards import evaluate_reward, printed_eq2_literal  # noqa: E402
from banditverify.security import (  # noqa: E402
    EvidenceValidationError,
    strict_json_load,
)


PROTOCOL_ID = "USA26-04-FORMULA-PORTABILITY-v1"
REPOSITORY = repository_root(CANDIDATE)
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
    parser.add_argument("--matlab-engine", choices=("octave", "matlab"))
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
            "github_repository": os.environ.get("GITHUB_REPOSITORY"),
            "github_workflow_ref": os.environ.get("GITHUB_WORKFLOW_REF"),
            "github_sha": os.environ.get("GITHUB_SHA"),
            "github_ref": os.environ.get("GITHUB_REF"),
            "github_server_url": os.environ.get("GITHUB_SERVER_URL"),
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
    path: Path | None,
    serial_records: list[dict[str, Any]],
    current_head: str,
    *,
    trusted_origin: bool,
    expected_engine: str | None = None,
    engine_executable: str | None = None,
    engine_executable_sha256: str | None = None,
    engine_version_probe_sha256: str | None = None,
    engine_version_probe: str | None = None,
) -> dict[str, Any]:
    if path is None:
        return {
            "status": "NOT_EVALUATED_MATLAB_REPORT_ABSENT",
            "state_provenance": FIXTURE_STATE_PROVENANCE,
            "paper_level_status": "BLOCKED_G5_G9",
        }
    try:
        report = strict_json_load(path, maximum_bytes=2 * 1024 * 1024)
        metadata = validate_matlab_report(
            report,
            CANDIDATE,
            current_head,
            expected_engine=expected_engine,
        )
        if trusted_origin and (
            not engine_version_probe
            or report["engine"]["version"] not in engine_version_probe
        ):
            raise EvidenceValidationError(
                "MATLAB report version is absent from independent runtime probe"
            )
    except (EvidenceValidationError, KeyError, TypeError, ValueError) as exc:
        return {
            "status": "REJECTED_MALFORMED_OR_UNBOUND_MATLAB_REPORT",
            "state_provenance": FIXTURE_STATE_PROVENANCE,
            "paper_level_status": "BLOCKED_G5_G9",
            "rejection_reason": str(exc),
        }
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
        key for key in exact_keys if report["payload"].get(key) != python_result.get(key)
    ]
    numeric_keys = (
        "base_weights",
        "log_rate",
        "rate",
        "immediate_reward",
        "updates",
    )
    left = _flatten_numeric({key: python_result[key] for key in numeric_keys})
    right = _flatten_numeric({key: report["payload"].get(key) for key in numeric_keys})
    numeric_mismatches: list[str] = []
    if [path for path, _ in left] != [path for path, _ in right]:
        numeric_mismatches.append("NUMERIC_FIELD_SHAPE_MISMATCH")
    else:
        for (field, first), (_, second) in zip(left, right):
            if not math.isclose(first, second, abs_tol=1e-12, rel_tol=1e-12):
                numeric_mismatches.append(field)
    if metadata["canonical_payload_sha256"] != payload_sha256(python_result):
        numeric_mismatches.append("CANONICAL_PAYLOAD_DIGEST_MISMATCH")
    passed = (
        not exact_mismatches
        and not numeric_mismatches
        and report["payload"].get("state_provenance") == FIXTURE_STATE_PROVENANCE
    )
    content_validation_status = (
        "PASS_CROSS_ENV_FIXED_TAPE_CONTENT"
        if passed
        else "FAIL_CROSS_ENV_FIXED_TAPE_CONTENT"
    )
    if not trusted_origin:
        status = "NOT_EVALUATED_UNAUTHENTICATED_EXTERNAL_MATLAB_REPORT"
        report_origin = "EXTERNAL_UNAUTHENTICATED"
    elif passed:
        status = "NOT_EVALUATED_EXTERNAL_NATIVE_RUNTIME_AUTH_REQUIRED"
        report_origin = "RUNNER_INVOKED_ENGINE_LOCAL_SELF_ATTESTED"
    else:
        status = "REJECTED_CROSS_ENV_FIXED_TAPE_CONTENT_MISMATCH"
        report_origin = "RUNNER_INVOKED_ENGINE_LOCAL_SELF_ATTESTED"
    return {
        "status": status,
        "content_validation_status": content_validation_status,
        "report_origin": report_origin,
        "report_sha256": sha256_file(path),
        "state_provenance": FIXTURE_STATE_PROVENANCE,
        "exact_mismatches": exact_mismatches,
        "numeric_mismatches": numeric_mismatches,
        "paper_level_status": "BLOCKED_G5_G9",
        "published_result_status": "INCONCLUSIVE_PUBLISHED_RESULT",
        "git_sha": current_head,
        "engine": report["engine"],
        "engine_executable": engine_executable,
        "engine_executable_sha256": engine_executable_sha256,
        "engine_version_probe_sha256": engine_version_probe_sha256,
        "matlab_source_sha256": metadata["matlab_source_sha256"],
        "fixture_sha256": metadata["fixture_sha256"],
        "canonical_payload_sha256": metadata["canonical_payload_sha256"],
        "matlab_report_canonical_sha256": hashlib.sha256(
            canonical_json(report)
        ).hexdigest(),
        "matlab_report": report,
    }


def _native_engine_environment(directory: str) -> dict[str, str]:
    environment = {
        "PATH": "/usr/bin:/bin",
        "LANG": "C",
        "LC_ALL": "C",
        "TMPDIR": directory,
        **{name: "1" for name in THREAD_ENV},
    }
    for license_name in ("MLM_LICENSE_FILE", "LM_LICENSE_FILE"):
        if os.environ.get(license_name):
            environment[license_name] = os.environ[license_name]
    return environment


def _runner_generated_matlab_gate(
    engine: str,
    serial_records: list[dict[str, Any]],
    current_head: str,
) -> dict[str, Any]:
    executable = shutil.which(engine)
    if executable is None:
        return {
            "status": "REJECTED_REQUESTED_MATLAB_ENGINE_NOT_FOUND",
            "state_provenance": FIXTURE_STATE_PROVENANCE,
            "paper_level_status": "BLOCKED_G5_G9",
        }
    executable_path = Path(executable).resolve()
    allowed_engine_path = (
        engine == "octave"
        and executable_path.is_relative_to(Path("/usr/bin"))
        and executable_path.name.startswith("octave")
    ) or (
        engine == "matlab"
        and (
            executable_path.is_relative_to(Path("/usr/local/MATLAB"))
            or executable_path.is_relative_to(Path("/opt/MATLAB"))
            or executable_path.is_relative_to(Path("/opt/hostedtoolcache/MATLAB"))
        )
        and executable_path.name == "matlab"
    )
    if not allowed_engine_path or executable_path.stat().st_mode & 0o022:
        return {
            "status": "REJECTED_UNTRUSTED_MATLAB_ENGINE_PATH",
            "state_provenance": FIXTURE_STATE_PROVENANCE,
            "paper_level_status": "BLOCKED_G5_G9",
            "engine_executable": str(executable_path),
        }
    executable_digest = sha256_file(executable_path)
    with tempfile.TemporaryDirectory(prefix="usa26-04-matlab-h2-") as directory:
        report_path = Path(directory) / "matlab-fixed-tape.json"
        implementation = (CANDIDATE / "environments" / "matlab").resolve()
        if "'" in str(implementation) or "'" in str(report_path):
            raise RuntimeError("MATLAB paths cannot contain a single quote")
        expected_writer = implementation / "write_fixed_tape_report.m"
        expression = (
            f"addpath('{implementation}','-begin'); "
            f"resolved=which('write_fixed_tape_report'); "
            f"if ~strcmp(resolved,'{expected_writer}'), error('untrusted writer path'); end; "
            f"write_fixed_tape_report('{report_path}')"
        )
        command = (
            [
                str(executable_path),
                "--no-gui",
                "--no-init-file",
                "--no-site-file",
                "--no-history",
                "--quiet",
                "--eval",
                expression,
            ]
            if engine == "octave"
            else [str(executable_path), "-sd", directory, "-batch", expression]
        )
        probe_command = (
            [str(executable_path), "--no-init-file", "--no-site-file", "--version"]
            if engine == "octave"
            else [str(executable_path), "-sd", directory, "-batch", "disp(version)"]
        )
        child_environment = _native_engine_environment(directory)
        try:
            probe = subprocess.run(
                probe_command,
                cwd=directory,
                env=child_environment,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                check=False,
                timeout=60,
            )
            completed = subprocess.run(
                command,
                cwd=directory,
                env=child_environment,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                check=False,
                timeout=180,
            )
        except subprocess.TimeoutExpired as exc:
            return {
                "status": "REJECTED_MATLAB_ENGINE_TIMEOUT",
                "state_provenance": FIXTURE_STATE_PROVENANCE,
                "paper_level_status": "BLOCKED_G5_G9",
                "engine_executable": str(executable_path),
                "engine_executable_sha256": executable_digest,
                "timeout_seconds": exc.timeout,
            }
        if probe.returncode != 0 or completed.returncode != 0 or not report_path.is_file():
            return {
                "status": "REJECTED_MATLAB_ENGINE_EXECUTION_FAILED",
                "state_provenance": FIXTURE_STATE_PROVENANCE,
                "paper_level_status": "BLOCKED_G5_G9",
                "engine_executable": str(executable_path),
                "engine_executable_sha256": executable_digest,
                "version_probe_return_code": probe.returncode,
                "return_code": completed.returncode,
                "output_sha256": hashlib.sha256(completed.stdout.encode("utf-8")).hexdigest(),
            }
        expected_name = "GNU Octave" if engine == "octave" else "MATLAB"
        return _matlab_fixed_tape_gate(
            report_path,
            serial_records,
            current_head,
            trusted_origin=True,
            expected_engine=expected_name,
            engine_executable=str(executable_path),
            engine_executable_sha256=executable_digest,
            engine_version_probe_sha256=hashlib.sha256(
                probe.stdout.encode("utf-8")
            ).hexdigest(),
            engine_version_probe=probe.stdout,
        )


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
        digest = record_digest(record)
        lines.append(f"{record['case_id']}\t{digest}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _validate_artifact_paths(args: argparse.Namespace) -> None:
    output = args.output.resolve()
    hashes = args.hashes.resolve()
    if output == hashes:
        raise SystemExit("--output and --hashes must be distinct files")
    if output.is_relative_to(REPOSITORY) or hashes.is_relative_to(REPOSITORY):
        raise SystemExit("formal profile artifacts must be written outside the repository")
    if args.matlab_report is not None:
        report = args.matlab_report.resolve()
        if report in {output, hashes}:
            raise SystemExit("diagnostic MATLAB input cannot collide with an output artifact")


def main() -> int:
    args = parse_args()
    _validate_artifact_paths(args)
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
    if args.matlab_report is not None and args.matlab_engine is not None:
        raise SystemExit("choose either diagnostic --matlab-report or formal --matlab-engine")
    if args.require_matlab_report and args.matlab_engine is None:
        raise SystemExit("formal --require-matlab-report requires --matlab-engine")

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
    tracked_source_paths = source_paths(REPOSITORY)
    head_before = git_head(REPOSITORY)
    source_state_before = source_git_state(REPOSITORY)
    source_hashes_before = source_hashes(REPOSITORY, tracked_source_paths)

    serial_started = time.perf_counter()
    serial_records = [execute_case(case, CANDIDATE) for case in cases]
    serial_seconds = time.perf_counter() - serial_started
    serial_digest = formula_digest(serial_records)
    warmup = _run_parallel(cases, args.workers, target_affinity)
    repeats = [
        _run_parallel(cases, args.workers, target_affinity)
        for _ in range(args.timing_repeats)
    ]

    h1_pass = all(row["status"] == "PASS_FORMULA_CASE" for row in serial_records)
    if args.matlab_engine is not None:
        h2 = _runner_generated_matlab_gate(args.matlab_engine, serial_records, head_before)
    else:
        h2 = _matlab_fixed_tape_gate(
            args.matlab_report,
            serial_records,
            head_before,
            trusted_origin=False,
        )
    head_after = git_head(REPOSITORY)
    source_state_after = source_git_state(REPOSITORY)
    source_hashes_after = source_hashes(REPOSITORY, tracked_source_paths)
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
    core_pass = h0_pass and h1_pass and h3["status"].startswith("PASS_") and h4_pass
    if core_pass and h2["status"] == "NOT_EVALUATED_EXTERNAL_NATIVE_RUNTIME_AUTH_REQUIRED":
        profile_status = "INCONCLUSIVE_H2_EXTERNAL_NATIVE_RUNTIME_AUTH_REQUIRED"
    elif core_pass and h2["status"] in {
        "NOT_EVALUATED_MATLAB_REPORT_ABSENT",
        "NOT_EVALUATED_UNAUTHENTICATED_EXTERNAL_MATLAB_REPORT",
    }:
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
            "record_sha256": {
                record["case_id"]: record_digest(record) for record in serial_records
            },
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
        return 0 if h2.get("content_validation_status") == "PASS_CROSS_ENV_FIXED_TAPE_CONTENT" else 1
    return 0 if profile_status in {
        "INCONCLUSIVE_H2_EXTERNAL_NATIVE_RUNTIME_AUTH_REQUIRED",
        "INCONCLUSIVE_H2_MATLAB_NOT_EVALUATED",
    } else 1


if __name__ == "__main__":
    raise SystemExit(main())
