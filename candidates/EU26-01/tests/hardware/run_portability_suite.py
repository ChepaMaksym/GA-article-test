#!/usr/bin/env python3
"""Run one frozen EU26-01 deterministic H0-H4 portability profile."""

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
import csv
import hashlib
import json
import multiprocessing
from pathlib import Path
import platform
import statistics
import subprocess
import sys
import time
from typing import Any, Iterable


SCRIPT = Path(__file__).resolve()
CANDIDATE = SCRIPT.parents[2]
REPOSITORY = CANDIDATE.parents[1]
PYTHON_ENV = CANDIDATE / "environments" / "python"
sys.path.insert(0, str(PYTHON_ENV))

from tworateverify.archive import (  # noqa: E402
    ArchiveSpec,
    ArchiveValidationError,
    completion_statistics,
    load_authenticated_member,
    parse_focus_csv,
)
from tworateverify.canonical import (  # noqa: E402
    canonical_sha256,
    sha256_file,
    strict_json_load,
)
from tworateverify.kernels import (  # noqa: E402
    FormulaValidationError,
    adapt_two_rate,
    hypervolume_2d,
    oneminmax,
    validate_fixture,
)


PROTOCOL_ID = "EU26-01-HW-PORTABILITY-v1"
SCOPE = "ARCHIVE_AND_FORMULA_VALIDATION_ONLY"
PAPER_STATUS = "BLOCKED_SOURCE_NATIVE_REPLAY"
ALGORITHM2_CONFLICT = (
    "literal_one_based_pseudocode_4_low_6_high_vs_prose_and_source_5_low_5_high"
)
ROLE_WORKERS = {"work4": 4, "work8": 8, "github4": 4}
EXPECTED_MATRIX = {
    ("fixture-correctness", "formula", 64),
    ("fixture-throughput", "formula", 512),
    ("table1-focus-runs", "archive", 100),
}

_PAYLOAD = b""
_SPEC: ArchiveSpec | None = None
_FIXTURE: dict[str, Any] = {}


def _outside_repository(value: str) -> Path:
    path = Path(value).resolve()
    try:
        path.relative_to(REPOSITORY.resolve())
    except ValueError:
        return path
    raise argparse.ArgumentTypeError("formal outputs must be outside the repository")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile-role", choices=sorted(ROLE_WORKERS), required=True)
    parser.add_argument("--label", required=True)
    parser.add_argument("--workers", required=True, type=int)
    parser.add_argument("--logical-cpus", required=True, type=int)
    parser.add_argument("--timing-repeats", default=5, type=int)
    parser.add_argument("--archive", required=True, type=Path)
    parser.add_argument(
        "--matrix",
        type=Path,
        default=CANDIDATE / "config" / "hardware_smoke_matrix.csv",
    )
    parser.add_argument("--output", required=True, type=_outside_repository)
    parser.add_argument("--hashes", required=True, type=_outside_repository)
    return parser.parse_args()


def _read_json(path: Path) -> dict[str, Any]:
    try:
        document = strict_json_load(path)
    except (OSError, ValueError) as error:
        raise ValueError(f"cannot read strict JSON: {path}") from error
    if not isinstance(document, dict):
        raise ValueError(f"JSON root must be an object: {path}")
    return document


def _load_matrix(path: Path) -> dict[str, int]:
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames != ["workload_id", "kind", "replicates"]:
            raise ValueError("hardware matrix header differs from the frozen schema")
        rows = []
        for raw in reader:
            try:
                row = (raw["workload_id"], raw["kind"], int(raw["replicates"]))
            except (KeyError, TypeError, ValueError) as error:
                raise ValueError("hardware matrix row is malformed") from error
            rows.append(row)
    if set(rows) != EXPECTED_MATRIX or len(rows) != len(EXPECTED_MATRIX):
        raise ValueError("hardware matrix differs from the frozen workloads")
    return {row[0]: row[2] for row in rows}


def _read_text(path: str) -> str | None:
    try:
        return Path(path).read_text(encoding="utf-8").strip()
    except (OSError, UnicodeDecodeError):
        return None


def _parse_cpu_set(value: str | None) -> list[int] | None:
    if not value:
        return None
    result: set[int] = set()
    try:
        for item in value.split(","):
            bounds = item.strip().split("-", 1)
            start = int(bounds[0])
            stop = int(bounds[-1])
            if start < 0 or stop < start:
                return None
            result.update(range(start, stop + 1))
    except ValueError:
        return None
    return sorted(result) if result else None


def _parse_quota(value: str | None) -> float | None:
    if not value:
        return None
    fields = value.split()
    if len(fields) != 2 or fields[0] == "max":
        return None
    try:
        quota = int(fields[0])
        period = int(fields[1])
    except ValueError:
        return None
    return quota / period if quota > 0 and period > 0 else None


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
    return model, {
        "minimum": min(mhz) if mhz else None,
        "median": statistics.median(mhz) if mhz else None,
        "maximum": max(mhz) if mhz else None,
    }


def _memory_bytes() -> int | None:
    try:
        return os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES")
    except (OSError, ValueError):
        return None


def _git_sha() -> str | None:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=REPOSITORY,
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def _git_clean() -> tuple[bool, list[str]]:
    try:
        output = subprocess.check_output(
            ["git", "status", "--porcelain", "--untracked-files=all"],
            cwd=REPOSITORY,
            text=True,
            stderr=subprocess.STDOUT,
        )
    except (OSError, subprocess.CalledProcessError) as error:
        return False, [str(error)]
    rows = [line for line in output.splitlines() if line]
    return not rows, rows


def _source_paths() -> dict[str, Path]:
    paths: set[Path] = {
        REPOSITORY / ".github" / "workflows" / "eu26-01-validation.yml",
    }
    for directory in (CANDIDATE, REPOSITORY / "registry" / "cohort_2026_12"):
        for path in directory.rglob("*"):
            if (
                path.is_file()
                and "__pycache__" not in path.parts
                and "results" not in path.parts
                and path.suffix not in {".pyc", ".pyo"}
            ):
                paths.add(path)
    result: dict[str, Path] = {}
    for path in sorted(paths):
        relative = path.resolve().relative_to(REPOSITORY.resolve()).as_posix()
        result[relative] = path
    return result


def _all_tracked(paths: dict[str, Path]) -> tuple[bool, list[str]]:
    missing: list[str] = []
    for relative in paths:
        completed = subprocess.run(
            ["git", "ls-files", "--error-unmatch", "--", relative],
            cwd=REPOSITORY,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
        if completed.returncode != 0:
            missing.append(relative)
    return not missing, missing


def _worker_state() -> dict[str, Any]:
    return {
        "pid": os.getpid(),
        "affinity": sorted(os.sched_getaffinity(0)),
        "thread_environment": {name: os.environ.get(name) for name in THREAD_ENV},
    }


def _worker_probe(_: int) -> dict[str, Any]:
    time.sleep(0.05)
    return _worker_state()


def _formula_case(case_id: int) -> tuple[int, str, dict[str, Any]]:
    result = validate_fixture(_FIXTURE)
    digest = canonical_sha256(result, domain="EU26-01-FIXTURE-RESULT-V1")
    return case_id, digest, _worker_state()


def _archive_partition(run_ids: list[int]) -> tuple[list[tuple[int, int]], dict[str, Any]]:
    if _SPEC is None or not _PAYLOAD:
        raise RuntimeError("worker archive payload was not initialized")
    table = parse_focus_csv(_PAYLOAD, _SPEC)
    vector = table["completion_fes"]
    return [(run_id, vector[run_id]) for run_id in run_ids], _worker_state()


def _formula_aggregate(rows: Iterable[tuple[int, str, dict[str, Any]]]) -> str:
    pairs = sorted((case_id, digest) for case_id, digest, _state in rows)
    return canonical_sha256(pairs, domain="EU26-01-FORMULA-CASES-V1")


def _combine_archive(rows: Iterable[tuple[list[tuple[int, int]], dict[str, Any]]], runs: int) -> list[int]:
    pairs = [pair for partition, _state in rows for pair in partition]
    if len(pairs) != runs or len({run_id for run_id, _value in pairs}) != runs:
        raise ValueError("parallel archive partitions do not cover every run exactly once")
    ordered = sorted(pairs)
    if [run_id for run_id, _value in ordered] != list(range(runs)):
        raise ValueError("parallel archive run IDs are not contiguous")
    return [value for _run_id, value in ordered]


def _endpoint_digest(
    formula_rows: Iterable[tuple[int, str, dict[str, Any]]],
    archive_rows: Iterable[tuple[list[tuple[int, int]], dict[str, Any]]],
    runs: int,
) -> str:
    completion = _combine_archive(archive_rows, runs)
    endpoint = {
        "formula_cases_sha256": _formula_aggregate(formula_rows),
        "archive_completion_sha256": canonical_sha256(
            completion, domain="EU26-01-COMPLETION-FES-V1"
        ),
    }
    return canonical_sha256(endpoint, domain="EU26-01-TIMING-ENDPOINT-V1")


def _invalid_formula_gate() -> dict[str, Any]:
    probes = {
        "invalid_bit": lambda: oneminmax([0, 2]),
        "invalid_hv_reference": lambda: hypervolume_2d([(0, 0)], (1, 1)),
        "invalid_q": lambda: adapt_two_rate(
            [(50, 50)], [(50, 50)] * 10, 1, "NaN", n=100
        ),
        "invalid_strength": lambda: adapt_two_rate(
            [(50, 50)], [(50, 50)] * 10, 26, 0, n=100
        ),
    }
    accepted: list[str] = []
    for name, operation in probes.items():
        try:
            operation()
        except (FormulaValidationError, ValueError, TypeError):
            continue
        accepted.append(name)
    return {"passed": not accepted, "unexpectedly_accepted": accepted}


def _worker_summary(states: list[dict[str, Any]], selected: list[int]) -> dict[str, Any]:
    by_pid: dict[int, dict[str, Any]] = {}
    inconsistencies: list[str] = []
    for state in states:
        pid = state.get("pid")
        if isinstance(pid, bool) or not isinstance(pid, int):
            inconsistencies.append("non_integer_pid")
            continue
        previous = by_pid.setdefault(pid, state)
        if previous != state:
            inconsistencies.append(f"state_changed:{pid}")
    affinity_failures = sorted(
        pid for pid, state in by_pid.items() if state.get("affinity") != selected
    )
    thread_failures = sorted(
        pid
        for pid, state in by_pid.items()
        if state.get("thread_environment") != {name: "1" for name in THREAD_ENV}
    )
    return {
        "unique_worker_pids": sorted(by_pid),
        "unique_worker_pid_count": len(by_pid),
        "worker_states": {str(pid): state for pid, state in sorted(by_pid.items())},
        "affinity_failure_pids": affinity_failures,
        "thread_limit_failure_pids": thread_failures,
        "inconsistencies": sorted(set(inconsistencies)),
    }


def _write_new(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(
        path,
        os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_CLOEXEC", 0),
        0o600,
    )
    with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)


def _status(passed: bool) -> str:
    return "PASS" if passed else "FAIL"


def main() -> int:
    global _PAYLOAD, _SPEC, _FIXTURE

    arguments = parse_args()
    expected_workers = ROLE_WORKERS[arguments.profile_role]
    if arguments.workers != expected_workers or arguments.logical_cpus != expected_workers:
        raise SystemExit("profile role, workers and logical CPU count disagree")
    if arguments.timing_repeats != 5:
        raise SystemExit("the frozen contract requires exactly five timing repeats")
    if platform.system() != "Linux" or not hasattr(os, "sched_getaffinity"):
        raise SystemExit("the frozen profiles require Linux CPU affinity")

    workloads = _load_matrix(arguments.matrix)
    correctness_count = workloads["fixture-correctness"]
    throughput_count = workloads["fixture-throughput"]
    run_count = workloads["table1-focus-runs"]
    protocol_path = CANDIDATE / "config" / "frozen_protocol.json"
    bindings_path = CANDIDATE / "config" / "hardware_expected_digests.json"
    fixture_path = CANDIDATE / "fixtures" / "tworate_fixed_tape.json"
    _SPEC = ArchiveSpec.from_protocol(protocol_path)
    if _SPEC.runs != run_count:
        raise SystemExit("matrix run count differs from the frozen archive spec")
    bindings = _read_json(bindings_path)
    _FIXTURE = _read_json(fixture_path)

    affinity_before = sorted(os.sched_getaffinity(0))
    if len(affinity_before) < arguments.logical_cpus:
        raise SystemExit(f"insufficient affinity for requested profile: {affinity_before}")
    selected = affinity_before[: arguments.logical_cpus]
    os.sched_setaffinity(0, set(selected))
    affinity_after = sorted(os.sched_getaffinity(0))
    if affinity_after != selected:
        raise SystemExit("failed to enforce exact requested CPU affinity")

    cpu_max = _read_text("/sys/fs/cgroup/cpu.max")
    cpuset_text = _read_text("/sys/fs/cgroup/cpuset.cpus.effective")
    quota_cpus = _parse_quota(cpu_max)
    parsed_cpuset = _parse_cpu_set(cpuset_text)
    exact_visible = (
        os.cpu_count() == arguments.logical_cpus
        and affinity_before == selected
        and affinity_after == selected
        and parsed_cpuset == selected
    )
    quota_supports = quota_cpus is not None and quota_cpus + 1e-12 >= arguments.logical_cpus
    cpu_valid = exact_visible if arguments.profile_role == "github4" else (quota_supports or exact_visible)

    source_paths = _source_paths()
    source_hashes_start = {name: sha256_file(path) for name, path in source_paths.items()}
    tracked, untracked_sources = _all_tracked(source_paths)
    git_sha_start = _git_sha()
    git_clean_start, git_rows_start = _git_clean()

    _PAYLOAD, custody_start = load_authenticated_member(arguments.archive, _SPEC)
    table_serial = parse_focus_csv(_PAYLOAD, _SPEC)
    completions_serial = table_serial["completion_fes"]
    statistics_serial = completion_statistics(completions_serial, _SPEC)
    fixture_result = validate_fixture(_FIXTURE)
    fixture_file_sha256 = sha256_file(fixture_path)
    fixture_result_sha256 = canonical_sha256(
        fixture_result, domain="EU26-01-FIXTURE-RESULT-V1"
    )

    correctness_ids = list(range(correctness_count))
    throughput_ids = list(range(throughput_count))
    partitions = [list(range(index, run_count, arguments.workers)) for index in range(arguments.workers)]
    all_worker_states: list[dict[str, Any]] = []
    timings: list[float] = []
    timed_digests: list[str] = []
    fork_context = multiprocessing.get_context("fork")
    with ProcessPoolExecutor(max_workers=arguments.workers, mp_context=fork_context) as pool:
        probes = list(pool.map(_worker_probe, range(arguments.workers * 8)))
        all_worker_states.extend(probes)

        correctness_rows = list(pool.map(_formula_case, correctness_ids))
        all_worker_states.extend(row[2] for row in correctness_rows)
        parallel_archive_rows = list(pool.map(_archive_partition, partitions))
        all_worker_states.extend(row[1] for row in parallel_archive_rows)

        warm_formula = list(pool.map(_formula_case, throughput_ids))
        warm_archive = list(pool.map(_archive_partition, partitions))
        all_worker_states.extend(row[2] for row in warm_formula)
        all_worker_states.extend(row[1] for row in warm_archive)
        warm_digest = _endpoint_digest(warm_formula, warm_archive, run_count)

        for _repeat in range(arguments.timing_repeats):
            started = time.perf_counter()
            formula_rows = list(pool.map(_formula_case, throughput_ids))
            archive_rows = list(pool.map(_archive_partition, partitions))
            timings.append(time.perf_counter() - started)
            timed_digests.append(_endpoint_digest(formula_rows, archive_rows, run_count))
            all_worker_states.extend(row[2] for row in formula_rows)
            all_worker_states.extend(row[1] for row in archive_rows)

    completions_parallel = _combine_archive(parallel_archive_rows, run_count)
    statistics_parallel = completion_statistics(completions_parallel, _SPEC)
    formula_correctness_sha256 = _formula_aggregate(correctness_rows)
    completion_sha256 = canonical_sha256(
        completions_serial, domain="EU26-01-COMPLETION-FES-V1"
    )
    statistics_sha256 = canonical_sha256(
        statistics_serial, domain="EU26-01-COMPLETION-STATISTICS-V1"
    )

    payload_end, custody_end = load_authenticated_member(arguments.archive, _SPEC)
    source_hashes_end = {name: sha256_file(path) for name, path in source_paths.items()}
    git_sha_end = _git_sha()
    git_clean_end, git_rows_end = _git_clean()

    worker_pool = _worker_summary(all_worker_states, selected)
    model, mhz = _cpu_model_and_mhz()
    hardware = {
        "platform": platform.platform(),
        "system": platform.system(),
        "machine": platform.machine(),
        "cpu_model": model,
        "cpu_mhz_snapshot": mhz,
        "ghz_controlled": False,
        "os_cpu_count": os.cpu_count(),
        "affinity_before": affinity_before,
        "affinity_after": affinity_after,
        "cgroup_cpu_max": cpu_max,
        "cgroup_cpuset": cpuset_text,
        "parsed_quota_cpus": quota_cpus,
        "parsed_cpuset": parsed_cpuset,
        "exact_visible_cpu_set": exact_visible,
        "quota_supports_request": quota_supports,
        "cpu_allocation_valid": cpu_valid,
        "visible_memory_bytes": _memory_bytes(),
        "python": sys.version,
        "thread_environment": {name: os.environ.get(name) for name in THREAD_ENV},
        "github_actions": os.environ.get("GITHUB_ACTIONS") == "true",
        "github_run_id": os.environ.get("GITHUB_RUN_ID"),
        "github_run_attempt": os.environ.get("GITHUB_RUN_ATTEMPT"),
        "github_repository": os.environ.get("GITHUB_REPOSITORY"),
        "github_workflow_ref": os.environ.get("GITHUB_WORKFLOW_REF"),
        "github_sha": os.environ.get("GITHUB_SHA"),
        "runner_name": os.environ.get("RUNNER_NAME"),
    }

    h0_failures: list[str] = []
    if not git_clean_start or not git_clean_end:
        h0_failures.append("git_not_clean")
    if not tracked or untracked_sources:
        h0_failures.append("source_not_tracked")
    if git_sha_start is None or git_sha_start != git_sha_end:
        h0_failures.append("git_sha_changed")
    if source_hashes_start != source_hashes_end:
        h0_failures.append("source_hash_changed")
    if not cpu_valid:
        h0_failures.append("cpu_allocation_invalid")
    github_context_fields = (
        hardware["github_run_id"],
        hardware["github_run_attempt"],
        hardware["github_repository"],
        hardware["github_workflow_ref"],
        hardware["github_sha"],
    )
    if arguments.profile_role == "github4":
        expected_workflow_prefix = (
            "ChepaMaksym/GA-article-test/"
            ".github/workflows/eu26-01-validation.yml@"
        )
        if (
            hardware["github_actions"] is not True
            or hardware["github_repository"] != "ChepaMaksym/GA-article-test"
            or hardware["github_sha"] != git_sha_start
            or not isinstance(hardware["github_run_id"], str)
            or not hardware["github_run_id"].isdecimal()
            or int(hardware["github_run_id"]) <= 0
            or not isinstance(hardware["github_run_attempt"], str)
            or not hardware["github_run_attempt"].isdecimal()
            or int(hardware["github_run_attempt"]) <= 0
            or not isinstance(hardware["github_workflow_ref"], str)
            or not hardware["github_workflow_ref"].startswith(expected_workflow_prefix)
        ):
            h0_failures.append("github_context_claim_invalid")
    elif hardware["github_actions"] is not False or any(
        value is not None for value in github_context_fields
    ):
        h0_failures.append("local_github_context_claim_present")
    if payload_end != _PAYLOAD:
        h0_failures.append("authenticated_member_changed")
    if custody_start["archive_sha256"] != custody_end["archive_sha256"]:
        h0_failures.append("archive_hash_changed")
    if custody_start["member_sha256"] != custody_end["member_sha256"]:
        h0_failures.append("member_hash_changed")
    if (
        custody_start["descriptor_device"], custody_start["descriptor_inode"]
    ) != (
        custody_end["descriptor_device"], custody_end["descriptor_inode"]
    ):
        h0_failures.append("archive_path_inode_changed")

    h1_failures: list[str] = []
    if worker_pool["unique_worker_pid_count"] != arguments.workers:
        h1_failures.append("worker_pid_count")
    if worker_pool["affinity_failure_pids"]:
        h1_failures.append("worker_affinity")
    if worker_pool["thread_limit_failure_pids"]:
        h1_failures.append("worker_thread_limits")
    if worker_pool["inconsistencies"]:
        h1_failures.append("worker_state_changed")

    h2_failures: list[str] = []
    if completions_serial != completions_parallel:
        h2_failures.append("serial_parallel_completion_mismatch")
    if statistics_serial != statistics_parallel:
        h2_failures.append("serial_parallel_statistics_mismatch")
    if completion_sha256 != bindings.get("completion_vector_sha256"):
        h2_failures.append("completion_binding_mismatch")
    if statistics_sha256 != bindings.get("completion_statistics_sha256"):
        h2_failures.append("statistics_binding_mismatch")
    if custody_start["archive_sha256"] != bindings.get("archive_sha256"):
        h2_failures.append("archive_binding_mismatch")
    if custody_start["member_sha256"] != bindings.get("member_sha256"):
        h2_failures.append("member_binding_mismatch")

    invalid_formula = _invalid_formula_gate()
    h3_failures: list[str] = []
    if fixture_file_sha256 != bindings.get("fixture_file_sha256"):
        h3_failures.append("fixture_file_binding_mismatch")
    if fixture_result_sha256 != bindings.get("fixture_result_sha256"):
        h3_failures.append("fixture_result_binding_mismatch")
    if formula_correctness_sha256 != bindings.get("formula_correctness_sha256"):
        h3_failures.append("formula_correctness_binding_mismatch")
    if any(row[1] != fixture_result_sha256 for row in correctness_rows):
        h3_failures.append("formula_replay_mismatch")
    if not invalid_formula["passed"]:
        h3_failures.append("invalid_formula_accepted")

    h4_failures: list[str] = []
    if warm_digest != bindings.get("timing_endpoint_sha256"):
        h4_failures.append("warmup_binding_mismatch")
    if len(timed_digests) != 5 or any(digest != warm_digest for digest in timed_digests):
        h4_failures.append("retained_repeat_mismatch")

    gates = {
        "H0_provenance": {"status": _status(not h0_failures), "failures": h0_failures},
        "H1_worker_allocation": {"status": _status(not h1_failures), "failures": h1_failures},
        "H2_archive_identity": {"status": _status(not h2_failures), "failures": h2_failures},
        "H3_formula_invariants": {"status": _status(not h3_failures), "failures": h3_failures},
        "H4_repeatability": {"status": _status(not h4_failures), "failures": h4_failures},
        "H5_cross_profile": {"status": "NOT_EVALUATED_SINGLE_PROFILE", "failures": []},
    }
    profile_pass = all(gates[f"H{index}_{name}"]["status"] == "PASS" for index, name in (
        (0, "provenance"),
        (1, "worker_allocation"),
        (2, "archive_identity"),
        (3, "formula_invariants"),
        (4, "repeatability"),
    ))

    report: dict[str, Any] = {
        "schema_version": "1.0.0",
        "protocol_id": PROTOCOL_ID,
        "candidate_id": "EU26-01",
        "scope": SCOPE,
        "profile_role": arguments.profile_role,
        "label": arguments.label,
        "profile_status": "PASS_PROFILE" if profile_pass else "FAIL_PROFILE",
        "paper_level_status": PAPER_STATUS,
        "eligibility_status": "conditional_noneligible",
        "pass_full_allowed": False,
        "algorithm2_conflict": ALGORITHM2_CONFLICT,
        "requested_workers": arguments.workers,
        "requested_logical_cpus": arguments.logical_cpus,
        "timing_repeats": arguments.timing_repeats,
        "git_sha_start": git_sha_start,
        "git_sha_end": git_sha_end,
        "git_clean_start": git_clean_start,
        "git_clean_end": git_clean_end,
        "git_status_start": git_rows_start,
        "git_status_end": git_rows_end,
        "source_sha256_start": source_hashes_start,
        "source_sha256_end": source_hashes_end,
        "hardware": hardware,
        "worker_pool": worker_pool,
        "archive": {
            "custody_start": custody_start,
            "custody_end": custody_end,
            "completion_vector": completions_serial,
            "completion_vector_sha256": completion_sha256,
            "statistics": statistics_serial,
            "completion_statistics_sha256": statistics_sha256,
            "serial_parallel_match": completions_serial == completions_parallel
            and statistics_serial == statistics_parallel,
        },
        "formula": {
            "fixture_file_sha256": fixture_file_sha256,
            "fixture_result_sha256": fixture_result_sha256,
            "correctness_case_count": correctness_count,
            "formula_correctness_sha256": formula_correctness_sha256,
            "invalid_input_gate": invalid_formula,
        },
        "timing": {
            "warmup_endpoint_sha256": warm_digest,
            "retained_seconds": timings,
            "retained_endpoint_sha256": timed_digests,
            "threshold_applied": False,
        },
        "bindings": bindings,
        "gates": gates,
    }
    report["report_sha256"] = canonical_sha256(
        report, domain="EU26-01-PORTABILITY-PROFILE-V1"
    )

    report_text = json.dumps(
        report, sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False
    ) + "\n"
    hash_lines = ["path\tsha256_start\tsha256_end"]
    hash_lines.extend(
        f"{name}\t{source_hashes_start[name]}\t{source_hashes_end[name]}"
        for name in sorted(source_hashes_start)
    )
    _write_new(arguments.output, report_text)
    _write_new(arguments.hashes, "\n".join(hash_lines) + "\n")
    print(json.dumps({
        "profile_role": arguments.profile_role,
        "profile_status": report["profile_status"],
        "paper_level_status": PAPER_STATUS,
        "report_sha256": report["report_sha256"],
        "retained_seconds": timings,
    }, sort_keys=True))
    return 0 if profile_pass else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ArchiveValidationError, FormulaValidationError, OSError, ValueError) as error:
        print(f"EU26-01 portability profile failed closed: {error}", file=sys.stderr)
        raise SystemExit(2)
