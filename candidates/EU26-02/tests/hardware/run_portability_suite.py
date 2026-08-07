#!/usr/bin/env python3
"""Run one frozen EU26-02 deterministic hardware-validation profile.

The profile parallelizes independent Deleter formula simulations and, when an
archive is supplied, independent parsers for the 31 frozen Table-2 instances.
It never runs the stochastic AHEAD graph-colouring solver and it never changes
the mandatory paper-level ``BLOCKED_MULTIPLE_SOURCE_CONFLICTS`` outcome.
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
import csv
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
from types import MappingProxyType
from typing import Any, Iterable, Mapping


SCRIPT = Path(__file__).resolve()
CANDIDATE = SCRIPT.parents[2]
REPOSITORY = CANDIDATE.parents[1]
PYTHON_ENV = CANDIDATE / "environments" / "python"
sys.path.insert(0, str(PYTHON_ENV))

from aheadverify.archive import (  # noqa: E402
    ARCHIVE_BYTES,
    ArchiveValidationError,
    archive_payload_manifest,
    load_authenticated_member_payloads,
)
from aheadverify.deleter import DeleterState, simulate_deleter  # noqa: E402


PROTOCOL_ID = "EU26-02-HW-PORTABILITY-v1"
PAPER_LEVEL_STATUS = "BLOCKED_MULTIPLE_SOURCE_CONFLICTS"
ARCHIVE_PROFILE = "artifact_actual_10800"
ARCHIVE_SHA256 = "1b7e8cf1ef637005bd994104f6e1ee520256ed387994b126bbe875a137632e41"
UNCOMPRESSED_TAR_BYTES = 276_705_280
UNCOMPRESSED_TAR_SHA256 = "a3c5893a1a7de480a05b26cbef24a2e07d161f8ed5923354444d6ea2d2fb5cf8"
ARCHIVE_PAYLOAD_BYTES = 104_406_336
ARCHIVE_PAYLOAD_MANIFEST_SHA256 = (
    "d50f4be5378357a45fc65047849f2ad1e99d01a8a005da42538f2d27fd585a36"
)
EXPECTED_FORMULA_AGGREGATE_SHA256 = (
    "5e0f1346a7eb931a7c5bda08f2df082c2a0027c9b359f37c78b1be5ef5f3d61a"
)
EXPECTED_ARCHIVE_AGGREGATE_SHA256 = (
    "9b0b90fca330fd89c259b907a215f9336add73f6ad599a4a94c9946d632183c9"
)
EXPECTED_COMBINED_ENDPOINT_SHA256 = (
    "3fe3d29b882589784d4cc136dc1aced17400e86e12fd0fd0371076a865819962"
)
EXPECTED_FORMULA_ROWS = {
    ("deleter-small", "formula", 64, 80, 2602000),
    ("deleter-throughput", "formula", 1024, 500, 2602100),
}
EXPECTED_ARCHIVE_ROW = ("table2-all", "archive", 31, 0, 0)


ArchiveMemberPayloads = tuple[tuple[str, bytes], ...]
_ARCHIVE_MEMBER_PAYLOADS: Mapping[str, ArchiveMemberPayloads] = MappingProxyType({})


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
    parser.add_argument(
        "--archive",
        type=Path,
        help="Pinned 64,960,102-byte Deleter archive; omission runs formula-only gates.",
    )
    parser.add_argument(
        "--require-archive",
        action="store_true",
        help="Fail unless the pinned archive is supplied and H2 passes.",
    )
    parser.add_argument(
        "--require-exact-visible-cpus",
        action="store_true",
        help="Require os.cpu_count, affinity and cpuset to expose exactly the requested CPUs.",
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


def _canonical(value: Any) -> Any:
    """Return a strict JSON value, rejecting non-finite or opaque state."""

    if value is None or isinstance(value, (bool, str)):
        return value
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("canonical scientific result contains NaN or Inf")
        return value
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        result: dict[str, Any] = {}
        for key, child in value.items():
            if not isinstance(key, str):
                raise TypeError("canonical result dictionary keys must be strings")
            result[key] = _canonical(child)
        return result
    if isinstance(value, (list, tuple)):
        return [_canonical(child) for child in value]
    if hasattr(value, "item"):
        return _canonical(value.item())
    if hasattr(value, "tolist"):
        return _canonical(value.tolist())
    raise TypeError(f"unsupported canonical result type: {type(value).__name__}")


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        _canonical(value),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def _sha256_value(value: Any) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _freeze_archive_member_payloads(
    payloads: dict[str, ArchiveMemberPayloads],
) -> Mapping[str, ArchiveMemberPayloads]:
    """Validate and freeze the authenticated bytes inherited by fork workers."""

    frozen: dict[str, ArchiveMemberPayloads] = {}
    for instance, members in sorted(payloads.items()):
        if not isinstance(instance, str) or not instance:
            raise TypeError("archive payload instance keys must be non-empty strings")
        if not isinstance(members, tuple):
            raise TypeError("archive instance payloads must be tuples")
        normalized: list[tuple[str, bytes]] = []
        for member in members:
            if (
                not isinstance(member, tuple)
                or len(member) != 2
                or not isinstance(member[0], str)
                or not isinstance(member[1], bytes)
            ):
                raise TypeError("archive members must be (name, immutable bytes) tuples")
            normalized.append((member[0], member[1]))
        frozen[instance] = tuple(normalized)
    return MappingProxyType(frozen)


def _archive_payload_manifest(
    payloads: Mapping[str, ArchiveMemberPayloads],
) -> dict[str, Any]:
    """Bind every parsed member to its instance, name, byte length and digest."""

    return archive_payload_manifest(payloads)


def _read_text(path: str) -> str | None:
    try:
        return Path(path).read_text(encoding="utf-8").strip()
    except (OSError, UnicodeDecodeError):
        return None


def _parse_cpu_set(value: Any) -> list[int] | None:
    if not isinstance(value, str) or not value.strip():
        return None
    cpus: set[int] = set()
    try:
        for item in value.split(","):
            bounds = item.strip().split("-", 1)
            start = int(bounds[0])
            stop = int(bounds[-1])
            if start < 0 or stop < start:
                return None
            cpus.update(range(start, stop + 1))
    except (TypeError, ValueError):
        return None
    return sorted(cpus) if cpus else None


def _parse_cpu_quota(value: Any) -> float | None:
    if not isinstance(value, str):
        return None
    fields = value.split()
    if len(fields) != 2 or fields[0] == "max":
        return None
    try:
        quota = int(fields[0])
        period = int(fields[1])
    except ValueError:
        return None
    if quota <= 0 or period <= 0:
        return None
    return quota / period


def _cpu_allocation_evidence(
    hardware: dict[str, Any], requested: int, require_exact_visible: bool
) -> dict[str, Any]:
    affinity_before = hardware.get("affinity_before")
    affinity_after = hardware.get("affinity_after")
    cpuset = _parse_cpu_set(hardware.get("cgroup_cpuset"))
    quota_cpus = _parse_cpu_quota(hardware.get("cgroup_cpu_max"))
    exact_visible_set = (
        isinstance(affinity_before, list)
        and isinstance(affinity_after, list)
        and len(affinity_before) == requested
        and len(set(affinity_before)) == requested
        and affinity_before == affinity_after
        and cpuset == affinity_before
        and hardware.get("os_cpu_count") == requested
    )
    quota_supports_request = quota_cpus is not None and quota_cpus + 1e-12 >= requested
    valid = exact_visible_set if require_exact_visible else (
        quota_supports_request or exact_visible_set
    )
    if exact_visible_set:
        mode = "exact_visible_cpu_set"
    elif quota_supports_request:
        mode = "cgroup_cpu_quota_plus_enforced_affinity"
    else:
        mode = "insufficient"
    return {
        "valid": valid,
        "mode": mode,
        "require_exact_visible_cpus": require_exact_visible,
        "requested_logical_cpus": requested,
        "os_cpu_count": hardware.get("os_cpu_count"),
        "affinity_before": affinity_before,
        "affinity_after": affinity_after,
        "parsed_cgroup_cpuset": cpuset,
        "parsed_quota_cpus": quota_cpus,
        "exact_visible_cpu_set": exact_visible_set,
        "quota_supports_request": quota_supports_request,
    }


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
    except (ValueError, OSError):
        return None


def _hardware_manifest(
    affinity_before: list[int], affinity_after: list[int]
) -> dict[str, Any]:
    model, mhz = _cpu_model_and_mhz()
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
        "thread_environment": {name: os.environ.get(name) for name in THREAD_ENV},
        "execution_context": {
            "github_actions": os.environ.get("GITHUB_ACTIONS") == "true",
            "github_run_id": os.environ.get("GITHUB_RUN_ID"),
            "github_run_attempt": os.environ.get("GITHUB_RUN_ATTEMPT"),
            "runner_name": os.environ.get("RUNNER_NAME"),
            "runner_environment": os.environ.get("RUNNER_ENVIRONMENT"),
        },
    }


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


def _source_paths() -> dict[str, Path]:
    paths: set[Path] = {
        SCRIPT,
        SCRIPT.with_name("compare_portability_reports.py"),
        CANDIDATE / "README.md",
        CANDIDATE / "tests" / "run_python_tests.py",
        REPOSITORY / ".github" / "workflows" / "eu26-02-validation.yml",
    }
    for directory in (
        PYTHON_ENV,
        CANDIDATE / "environments" / "matlab",
        CANDIDATE / "config",
        CANDIDATE / "fixtures",
        CANDIDATE / "preregistration",
        CANDIDATE / "source_manifest",
        CANDIDATE / "tests" / "python",
        CANDIDATE / "tests" / "matlab",
        REPOSITORY / "registry" / "cohort_2026_12",
    ):
        if directory.is_dir():
            paths.update(
                path
                for path in directory.rglob("*")
                if path.is_file()
                and "__pycache__" not in path.parts
                and path.suffix not in {".pyc", ".pyo"}
            )
    result: dict[str, Path] = {}
    for path in sorted(paths):
        relative = path.resolve().relative_to(REPOSITORY.resolve()).as_posix()
        result[relative] = path
    return result


def _git_source_state(paths: dict[str, Path]) -> dict[str, list[str]]:
    untracked: list[str] = []
    different: list[str] = []
    for name, path in paths.items():
        tracked = subprocess.run(
            ["git", "ls-files", "--error-unmatch", "--", name],
            cwd=REPOSITORY,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        ).returncode == 0
        if not tracked:
            untracked.append(name)
            continue
        clean = subprocess.run(
            ["git", "diff", "--quiet", "HEAD", "--", name],
            cwd=REPOSITORY,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        ).returncode == 0
        if not clean:
            different.append(name)
        if not path.is_file():
            different.append(name)
    return {
        "untracked": sorted(set(untracked)),
        "different_from_head": sorted(set(different)),
    }


def _load_workloads(path: Path) -> tuple[list[dict[str, int | str]], list[dict[str, int | str]]]:
    formula_rows: list[dict[str, int | str]] = []
    archive_rows: list[dict[str, int | str]] = []
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        required = {"workload_id", "kind", "replicates", "turns", "base_seed"}
        if set(reader.fieldnames or []) != required:
            raise ValueError("hardware matrix columns differ from the frozen schema")
        for raw in reader:
            row: dict[str, int | str] = {
                "workload_id": raw["workload_id"],
                "kind": raw["kind"],
                "replicates": int(raw["replicates"]),
                "turns": int(raw["turns"]),
                "base_seed": int(raw["base_seed"]),
            }
            (formula_rows if row["kind"] == "formula" else archive_rows).append(row)
    frozen_formula = {
        (
            str(row["workload_id"]),
            str(row["kind"]),
            int(row["replicates"]),
            int(row["turns"]),
            int(row["base_seed"]),
        )
        for row in formula_rows
    }
    frozen_archive = {
        (
            str(row["workload_id"]),
            str(row["kind"]),
            int(row["replicates"]),
            int(row["turns"]),
            int(row["base_seed"]),
        )
        for row in archive_rows
    }
    if frozen_formula != EXPECTED_FORMULA_ROWS or len(formula_rows) != 2:
        raise ValueError("formula workloads differ from the frozen contract")
    if frozen_archive != {EXPECTED_ARCHIVE_ROW} or len(archive_rows) != 1:
        raise ValueError("archive workload differs from the frozen contract")
    return formula_rows, archive_rows


def _formula_contract_invariants(result: dict[str, Any], turns: int) -> dict[str, bool]:
    state = result.get("final_state")
    events = result.get("deletion_events")
    invariants = result.get("invariants")
    expected_invariant_keys = {
        "count_accounting",
        "finite_means",
        "partition",
        "deletion_cadence",
        "adaptation_observed",
    }
    valid_state = isinstance(state, dict)
    counts = state.get("counts", []) if valid_state else []
    means = state.get("means", []) if valid_state else []
    surviving = state.get("surviving", []) if valid_state else []
    removed = state.get("removed", []) if valid_state else []
    event_turns = (
        [event.get("source_turn") for event in events]
        if isinstance(events, list) and all(isinstance(event, dict) for event in events)
        else []
    )
    event_operators = (
        [event.get("operator") for event in events]
        if isinstance(events, list) and all(isinstance(event, dict) for event in events)
        else []
    )
    expected_deletion_turns = [
        source_turn for source_turn in range(30, min(turns, 51), 5)
    ]
    return {
        "canonical_fields": {
            "final_state",
            "deletion_events",
            "selection_history_digest",
            "invariants",
        } <= set(result),
        "declared_invariant_schema": (
            isinstance(invariants, dict)
            and expected_invariant_keys <= set(invariants)
            and all(
                isinstance(invariants[key], bool) and invariants[key]
                for key in expected_invariant_keys
            )
        ),
        "turn_accounting": valid_state and state.get("turn") == turns,
        "operator_dimensions": (
            valid_state
            and state.get("nb_operators") == 6
            and state.get("nb_selected") == 2
            and len(counts) == len(means) == 6
        ),
        "update_accounting": (
            isinstance(counts, list)
            and all(isinstance(value, int) and value >= 0 for value in counts)
            and sum(counts) == turns * 2
        ),
        "finite_lifetime_means": (
            isinstance(means, list)
            and all(
                isinstance(value, (int, float))
                and not isinstance(value, bool)
                and math.isfinite(float(value))
                for value in means
            )
        ),
        "deletion_schedule": event_turns == expected_deletion_turns,
        "deleted_operators_unique": (
            all(isinstance(value, int) for value in event_operators)
            and len(event_operators) == len(set(event_operators))
        ),
        "one_survivor_boundary": (
            turns >= 51
            and isinstance(surviving, list)
            and isinstance(removed, list)
            and len(surviving) == 1
            and len(removed) == 5
            and set(surviving) | set(removed) == set(range(6))
            and not (set(surviving) & set(removed))
        ),
        "history_digest": (
            isinstance(result.get("selection_history_digest"), str)
            and len(result["selection_history_digest"]) == 64
            and all(character in "0123456789abcdef" for character in result["selection_history_digest"])
        ),
    }


def _expand_formula(row: dict[str, int | str]) -> list[dict[str, int | str]]:
    return [
        {
            "case_id": f"{row['workload_id']}-seed{int(row['base_seed']) + index}",
            "workload_id": str(row["workload_id"]),
            "seed": int(row["base_seed"]) + index,
            "turns": int(row["turns"]),
        }
        for index in range(int(row["replicates"]))
    ]


def _worker_state() -> dict[str, Any]:
    return {
        "pid": os.getpid(),
        "affinity": sorted(os.sched_getaffinity(0)),
        "thread_environment": {name: os.environ.get(name) for name in THREAD_ENV},
    }


def _worker_probe(_: int) -> dict[str, Any]:
    time.sleep(0.03)
    return _worker_state()


def _formula_case(case: dict[str, int | str]) -> dict[str, Any]:
    result = _canonical(
        simulate_deleter(seed=int(case["seed"]), turns=int(case["turns"]))
    )
    required = {"final_state", "deletion_events", "selection_history_digest", "invariants"}
    if not isinstance(result, dict) or not required <= set(result):
        raise ValueError("simulate_deleter result is missing canonical fields")
    contract_invariants = _formula_contract_invariants(result, int(case["turns"]))
    invariant_pass = all(contract_invariants.values())
    deletion_pass = (
        isinstance(result["deletion_events"], list)
        and len(result["deletion_events"]) >= 1
    )
    return {
        "case_id": str(case["case_id"]),
        "seed": int(case["seed"]),
        "turns": int(case["turns"]),
        "canonical_result": result,
        "sha256": _sha256_value(result),
        "contract_invariants": contract_invariants,
        "invariant_pass": invariant_pass,
        "deletion_pass": deletion_pass,
        "worker": _worker_state(),
    }


def _formula_timing_case(case: dict[str, int | str]) -> tuple[str, str, dict[str, Any]]:
    result = _canonical(
        simulate_deleter(seed=int(case["seed"]), turns=int(case["turns"]))
    )
    return str(case["case_id"]), _sha256_value(result), _worker_state()


def _archive_case(payload: tuple[str, str]) -> dict[str, Any]:
    instance, profile_name = payload
    from aheadverify.archive import validate_instance_payloads

    try:
        member_payloads = _ARCHIVE_MEMBER_PAYLOADS[instance]
    except KeyError as error:
        raise ValueError(f"missing inherited archive payloads for {instance}") from error
    result = _canonical(
        validate_instance_payloads(member_payloads, instance, profile_name)
    )
    return {
        "instance": instance,
        "canonical_result": result,
        "sha256": _sha256_value(result),
        "worker": _worker_state(),
    }


def _archive_timing_case(payload: tuple[str, str]) -> tuple[str, str, dict[str, Any]]:
    row = _archive_case(payload)
    return f"archive-{row['instance']}", str(row["sha256"]), row["worker"]


def _aggregate_archive(rows: list[dict[str, Any]], profile_name: str) -> dict[str, Any]:
    from aheadverify.archive import aggregate_results

    ordered = [
        row["canonical_result"] for row in sorted(rows, key=lambda item: item["instance"])
    ]
    return _canonical(aggregate_results(ordered, profile_name))


def _archive_instances(
    payloads: Mapping[str, ArchiveMemberPayloads],
) -> list[str]:
    instances = sorted(payloads)
    expected = []
    fixture = CANDIDATE / "fixtures" / "published_table2_ahead_deleter.csv"
    with fixture.open(newline="", encoding="utf-8") as handle:
        expected = sorted(row["instance"] for row in csv.DictReader(handle))
    if instances != expected or len(instances) != 31 or len(set(instances)) != 31:
        raise ValueError("archive instance set differs from the frozen 31-row fixture")
    return instances


def _endpoint_digest(rows: Iterable[tuple[str, str, dict[str, Any]]]) -> str:
    endpoints = sorted((case_id, digest) for case_id, digest, _worker in rows)
    return _sha256_value(endpoints)


def _aggregate_case_hash(rows: list[dict[str, Any]], key: str) -> str:
    pairs = sorted((str(row[key]), str(row["sha256"])) for row in rows)
    return _sha256_value(pairs)


def _invalid_input_gate() -> dict[str, Any]:
    state_for_index = DeleterState.initialize()
    state_for_score = DeleterState.initialize()
    probes = {
        "negative_turns": lambda: simulate_deleter(seed=0, turns=-1),
        "zero_operators": lambda: simulate_deleter(seed=0, turns=80, nb_operators=0),
        "zero_selected": lambda: simulate_deleter(seed=0, turns=80, nb_selected=0),
        "invalid_selected_index": lambda: state_for_index.advance([6, 0], [1, 1]),
        "nonfinite_score": lambda: state_for_score.advance([0, 1], [float("inf"), 1]),
    }
    failures: list[str] = []
    for name, operation in probes.items():
        try:
            operation()
        except (TypeError, ValueError):
            continue
        failures.append(name)
    return {"passed": not failures, "unexpectedly_accepted": failures}


def _status(passed: bool) -> str:
    return "PASS" if passed else "FAIL"


def main() -> int:
    global _ARCHIVE_MEMBER_PAYLOADS

    args = parse_args()
    if args.workers not in (4, 8) or args.logical_cpus not in (4, 8):
        raise SystemExit("--workers and --logical-cpus must each be 4 or 8")
    if args.workers != args.logical_cpus:
        raise SystemExit("the frozen profiles require one worker per requested logical CPU")
    if args.timing_repeats != 5:
        raise SystemExit("the frozen contract requires exactly five retained timing batches")
    if args.require_archive and args.archive is None:
        raise SystemExit("--require-archive requires --archive")
    if platform.system() != "Linux" or not hasattr(os, "sched_getaffinity"):
        raise SystemExit("the frozen hardware profile requires Linux CPU affinity")

    affinity_before = sorted(os.sched_getaffinity(0))
    if len(affinity_before) < args.logical_cpus:
        raise SystemExit(
            f"requested {args.logical_cpus} CPUs but affinity exposes {affinity_before}"
        )
    selected = set(affinity_before[: args.logical_cpus])
    os.sched_setaffinity(0, selected)
    affinity_after = sorted(os.sched_getaffinity(0))
    if len(affinity_after) != args.logical_cpus:
        raise SystemExit("failed to enforce the requested CPU affinity")

    formula_rows, _archive_rows = _load_workloads(args.matrix)
    correctness_row = next(row for row in formula_rows if row["workload_id"] == "deleter-small")
    throughput_row = next(
        row for row in formula_rows if row["workload_id"] == "deleter-throughput"
    )
    correctness_cases = _expand_formula(correctness_row)
    throughput_cases = _expand_formula(throughput_row)

    source_paths = _source_paths()
    git_sha_start = _git_sha()
    source_sha256_start = {name: _sha256_file(path) for name, path in source_paths.items()}
    git_source_state_start = _git_source_state(source_paths)
    hardware = _hardware_manifest(affinity_before, affinity_after)
    cpu_evidence = _cpu_allocation_evidence(
        hardware, args.logical_cpus, args.require_exact_visible_cpus
    )

    archive_sha_start: str | None = None
    archive_bytes_start: int | None = None
    parse_archive_sha_start: str | None = None
    parse_archive_bytes_start: int | None = None
    archive_payload_manifest_start: dict[str, Any] | None = None
    archive_instances: list[str] = []
    archive_tasks: list[tuple[str, str]] = []
    if args.archive is not None:
        try:
            loaded_payloads, identity = load_authenticated_member_payloads(
                args.archive,
                ARCHIVE_SHA256,
                ARCHIVE_BYTES,
            )
            _ARCHIVE_MEMBER_PAYLOADS = _freeze_archive_member_payloads(
                loaded_payloads
            )
        except (ArchiveValidationError, OSError, TypeError) as error:
            raise SystemExit(
                f"cannot load authenticated archive member payloads: {error}"
            ) from error
        archive_sha_start = identity.archive_sha256
        archive_bytes_start = identity.archive_bytes
        parse_archive_sha_start = identity.uncompressed_tar_sha256
        parse_archive_bytes_start = identity.uncompressed_tar_bytes
        archive_payload_manifest_start = _archive_payload_manifest(
            _ARCHIVE_MEMBER_PAYLOADS
        )
        archive_instances = _archive_instances(_ARCHIVE_MEMBER_PAYLOADS)
        archive_tasks = [
            (instance, ARCHIVE_PROFILE)
            for instance in archive_instances
        ]

    serial_formula = [_formula_case(case) for case in correctness_cases]
    serial_archive = (
        [_archive_case(payload) for payload in archive_tasks]
        if archive_tasks
        else []
    )
    serial_archive_aggregate = (
        _aggregate_archive(serial_archive, ARCHIVE_PROFILE) if serial_archive else None
    )

    worker_states: list[dict[str, Any]] = []
    timings: list[float] = []
    timed_digests: list[str] = []
    fork_context = multiprocessing.get_context("fork")
    with ProcessPoolExecutor(
        max_workers=args.workers,
        mp_context=fork_context,
    ) as pool:
        probes = list(pool.map(_worker_probe, range(args.workers * 4)))
        worker_states.extend(probes)

        parallel_formula = list(pool.map(_formula_case, correctness_cases))
        worker_states.extend(row["worker"] for row in parallel_formula)
        parallel_archive = (
            list(pool.map(_archive_case, archive_tasks)) if archive_tasks else []
        )
        worker_states.extend(row["worker"] for row in parallel_archive)

        warm_formula = list(pool.map(_formula_timing_case, throughput_cases))
        warm_archive = (
            list(pool.map(_archive_timing_case, archive_tasks))
            if archive_tasks
            else []
        )
        worker_states.extend(row[2] for row in warm_formula + warm_archive)
        warm_digest = _endpoint_digest(warm_formula + warm_archive)

        for _repeat in range(args.timing_repeats):
            started = time.perf_counter()
            formula_rows_timed = list(pool.map(_formula_timing_case, throughput_cases))
            archive_rows_timed = (
                list(pool.map(_archive_timing_case, archive_tasks))
                if archive_tasks
                else []
            )
            timings.append(time.perf_counter() - started)
            timed_digests.append(
                _endpoint_digest(formula_rows_timed + archive_rows_timed)
            )
            worker_states.extend(row[2] for row in formula_rows_timed + archive_rows_timed)

    parallel_archive_aggregate = (
        _aggregate_archive(parallel_archive, ARCHIVE_PROFILE)
        if parallel_archive
        else None
    )

    formula_serial_by_id = {row["case_id"]: row for row in serial_formula}
    formula_parallel_by_id = {row["case_id"]: row for row in parallel_formula}
    formula_mismatches = sorted(
        case_id
        for case_id, row in formula_serial_by_id.items()
        if formula_parallel_by_id.get(case_id, {}).get("canonical_result")
        != row["canonical_result"]
    )
    formula_invariant_failures = sorted(
        row["case_id"]
        for row in parallel_formula
        if not row["invariant_pass"] or not row["deletion_pass"]
    )
    d10 = _invalid_input_gate()

    archive_serial_by_id = {row["instance"]: row for row in serial_archive}
    archive_parallel_by_id = {row["instance"]: row for row in parallel_archive}
    archive_mismatches = sorted(
        instance
        for instance, row in archive_serial_by_id.items()
        if archive_parallel_by_id.get(instance, {}).get("canonical_result")
        != row["canonical_result"]
    )
    archive_aggregate_match = (
        serial_archive_aggregate == parallel_archive_aggregate
        if archive_tasks
        else None
    )
    archive_aggregate_pass = (
        isinstance(parallel_archive_aggregate, dict)
        and parallel_archive_aggregate.get("status") == "PASS_AGGREGATE_EXACT"
        and parallel_archive_aggregate.get("complete_31_instance_set") is True
        and parallel_archive_aggregate.get("all_published_cells_match") is True
    )
    formula_aggregate_sha256 = _aggregate_case_hash(parallel_formula, "case_id")
    archive_case_aggregate_sha256 = (
        _aggregate_case_hash(parallel_archive, "instance")
        if parallel_archive
        else None
    )

    worker_pids = sorted({int(state["pid"]) for state in worker_states})
    worker_affinity_failures = sorted(
        {
            int(state["pid"])
            for state in worker_states
            if state.get("affinity") != affinity_after
        }
    )
    worker_thread_failures = sorted(
        {
            int(state["pid"])
            for state in worker_states
            if any(
                state.get("thread_environment", {}).get(name) != "1"
                for name in THREAD_ENV
            )
        }
    )
    worker_failures: list[str] = []
    if len(worker_pids) != args.workers:
        worker_failures.append("unique_worker_pid_count_mismatch")
    if worker_affinity_failures:
        worker_failures.append("worker_affinity_mismatch")
    if worker_thread_failures:
        worker_failures.append("worker_thread_limit_mismatch")

    git_sha_end = _git_sha()
    source_sha256_end = {name: _sha256_file(path) for name, path in source_paths.items()}
    git_source_state_end = _git_source_state(source_paths)
    archive_sha_end = _sha256_file(args.archive) if args.archive is not None else None
    # The authenticated tar snapshot is anonymous and never exposed by path.
    # Workers inherit only immutable extracted bytes; re-hashing those bytes
    # binds the end of the execution window to exactly what every parser read.
    parse_archive_sha_end = parse_archive_sha_start
    archive_payload_manifest_end = (
        _archive_payload_manifest(_ARCHIVE_MEMBER_PAYLOADS)
        if archive_tasks
        else None
    )

    provenance_failures: list[str] = []
    if not git_sha_start or len(git_sha_start) != 40:
        provenance_failures.append("missing_or_invalid_git_sha")
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
    if archive_sha_start != archive_sha_end:
        provenance_failures.append("archive_changed_during_execution")
    if parse_archive_sha_start != parse_archive_sha_end:
        provenance_failures.append("authenticated_tar_snapshot_changed_during_execution")
    if (
        args.archive is not None
        and (
            parse_archive_sha_start != UNCOMPRESSED_TAR_SHA256
            or parse_archive_bytes_start != UNCOMPRESSED_TAR_BYTES
        )
    ):
        provenance_failures.append("authenticated_tar_snapshot_identity_mismatch")
    if archive_payload_manifest_start != archive_payload_manifest_end:
        provenance_failures.append("archive_payloads_changed_during_execution")
    if (
        archive_payload_manifest_start is not None
        and (
            archive_payload_manifest_start.get("sha256")
            != ARCHIVE_PAYLOAD_MANIFEST_SHA256
            or archive_payload_manifest_start.get("payload_bytes")
            != ARCHIVE_PAYLOAD_BYTES
            or archive_payload_manifest_start.get("member_count") != 1_143
            or archive_payload_manifest_start.get("instance_count") != 31
        )
    ):
        provenance_failures.append("archive_payload_manifest_identity_mismatch")
    if args.archive is not None and archive_sha_start != ARCHIVE_SHA256:
        provenance_failures.append("archive_sha256_mismatch")
    if not cpu_evidence["valid"]:
        provenance_failures.append("missing_cpu_allocation_evidence")
    for field in ("platform", "machine", "cpu_model", "python"):
        if not hardware.get(field):
            provenance_failures.append(f"missing_hardware_{field}")
    if not hardware.get("cgroup_memory_max") and not hardware.get("visible_memory_bytes"):
        provenance_failures.append("missing_memory_metadata")
    if any(hardware["thread_environment"].get(name) != "1" for name in THREAD_ENV):
        provenance_failures.append("numerical_thread_limit_not_one")

    h0_pass = not provenance_failures
    h1_pass = not worker_failures
    h2_pass = (
        not archive_mismatches
        and archive_aggregate_match is True
        and archive_aggregate_pass
        and len(parallel_archive) == 31
        and archive_case_aggregate_sha256 == EXPECTED_ARCHIVE_AGGREGATE_SHA256
    ) if archive_tasks else False
    h3_pass = (
        not formula_mismatches
        and not formula_invariant_failures
        and d10["passed"]
        and formula_aggregate_sha256 == EXPECTED_FORMULA_AGGREGATE_SHA256
    )
    h4_pass = all(digest == warm_digest for digest in timed_digests) and (
        not archive_tasks or warm_digest == EXPECTED_COMBINED_ENDPOINT_SHA256
    )
    full_profile_pass = h0_pass and h1_pass and h2_pass and h3_pass and h4_pass
    formula_only_pass = h0_pass and h1_pass and h3_pass and h4_pass
    if full_profile_pass:
        profile_status = "PASS_PROFILE"
    elif formula_only_pass and not args.require_archive and not archive_tasks:
        profile_status = "PASS_FORMULA_ONLY"
    else:
        profile_status = "FAIL"

    median_seconds = statistics.median(timings)
    mad_seconds = statistics.median(
        abs(value - median_seconds) for value in timings
    )
    report = {
        "protocol_id": PROTOCOL_ID,
        "profile_label": args.label,
        "verification_scope": "ARCHIVE_AND_FORMULA_HARDWARE_VALIDATION_ONLY",
        "paper_level_status": PAPER_LEVEL_STATUS,
        "profile_status": profile_status,
        "git_sha": git_sha_start,
        "source_sha256": source_sha256_start,
        "git_source_state": git_source_state_start,
        "provenance_window": {
            "git_sha_end": git_sha_end,
            "source_sha256_end": source_sha256_end,
            "git_source_state_end": git_source_state_end,
        },
        "archive": {
            "provided": args.archive is not None,
            "required": args.require_archive,
            "profile": ARCHIVE_PROFILE if args.archive is not None else None,
            "expected_sha256": ARCHIVE_SHA256,
            "expected_bytes": ARCHIVE_BYTES,
            "bytes": archive_bytes_start,
            "sha256": archive_sha_start,
            "sha256_end": archive_sha_end,
            "temporary_uncompressed_tar_bytes": parse_archive_bytes_start,
            "temporary_uncompressed_tar_sha256": parse_archive_sha_start,
            "temporary_uncompressed_tar_sha256_end": parse_archive_sha_end,
            "authenticated_tar_snapshot_bytes": parse_archive_bytes_start,
            "authenticated_tar_snapshot_sha256_start": parse_archive_sha_start,
            "authenticated_tar_snapshot_sha256_end": parse_archive_sha_end,
            "payload_manifest": archive_payload_manifest_start,
            "payload_manifest_end": archive_payload_manifest_end,
            "payload_manifest_sha256_start": (
                archive_payload_manifest_start.get("sha256")
                if archive_payload_manifest_start is not None
                else None
            ),
            "payload_manifest_sha256_end": (
                archive_payload_manifest_end.get("sha256")
                if archive_payload_manifest_end is not None
                else None
            ),
            "instance_count": len(archive_instances),
        },
        "requested_workers": args.workers,
        "requested_logical_cpus": args.logical_cpus,
        "hardware": hardware,
        "cpu_allocation_evidence": cpu_evidence,
        "provenance_failures": provenance_failures,
        "worker_pool": {
            "unique_worker_pids": worker_pids,
            "unique_worker_pid_count": len(worker_pids),
            "affinity_failure_pids": worker_affinity_failures,
            "thread_limit_failure_pids": worker_thread_failures,
            "failures": worker_failures,
        },
        "formula_correctness": {
            "case_count": len(parallel_formula),
            "serial_parallel_mismatches": formula_mismatches,
            "invariant_failures": formula_invariant_failures,
            "invalid_input_gate": d10,
            "aggregate_sha256": formula_aggregate_sha256,
            "cases": sorted(parallel_formula, key=lambda row: row["case_id"]),
        },
        "archive_correctness": {
            "status": "EVALUATED" if archive_tasks else "NOT_RUN",
            "instance_count": len(parallel_archive),
            "serial_parallel_mismatches": archive_mismatches,
            "aggregate_match": archive_aggregate_match,
            "serial_aggregate": serial_archive_aggregate,
            "parallel_aggregate": parallel_archive_aggregate,
            "aggregate_sha256": archive_case_aggregate_sha256,
            "cases": sorted(parallel_archive, key=lambda row: row["instance"]),
        },
        "timing": {
            "warmup_endpoint_digest": warm_digest,
            "timed_endpoint_digests": timed_digests,
            "repeatable_endpoints": h4_pass,
            "formula_case_count": len(throughput_cases),
            "archive_case_count": len(archive_tasks),
            "retained_batch_seconds": timings,
            "median_batch_seconds": median_seconds,
            "mad_batch_seconds": mad_seconds,
            "mad_over_median": mad_seconds / median_seconds,
            "median_formula_jobs_per_second": len(throughput_cases) / median_seconds,
        },
        "gates": {
            "H0_provenance": {"status": _status(h0_pass), "failures": provenance_failures},
            "H1_worker_allocation": {"status": _status(h1_pass), "failures": worker_failures},
            "H2_archive_identity": {
                "status": _status(h2_pass) if archive_tasks else "NOT_RUN",
                "mismatch_count": len(archive_mismatches),
                "aggregate_match": archive_aggregate_match,
                "aggregate_status": (
                    parallel_archive_aggregate.get("status")
                    if isinstance(parallel_archive_aggregate, dict)
                    else None
                ),
            },
            "H3_formula_invariants": {
                "status": _status(h3_pass),
                "serial_parallel_mismatch_count": len(formula_mismatches),
                "invariant_failure_count": len(formula_invariant_failures),
                "invalid_input_gate": d10,
            },
            "H4_repeatability": {
                "status": _status(h4_pass),
                "retained_batch_count": len(timed_digests),
            },
            "H5_cross_profile": {
                "status": "NOT_EVALUATED_SINGLE_PROFILE",
                "required_profiles": ["work-4core", "work-8core", "github-actions-4core"],
            },
        },
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.hashes.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    with args.hashes.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, delimiter="\t", lineterminator="\n")
        writer.writerow(("kind", "case_id", "sha256"))
        for row in sorted(parallel_formula, key=lambda item: item["case_id"]):
            writer.writerow(("formula", row["case_id"], row["sha256"]))
        for row in sorted(parallel_archive, key=lambda item: item["instance"]):
            writer.writerow(("archive", row["instance"], row["sha256"]))

    summary = {
        "profile_label": args.label,
        "profile_status": profile_status,
        "paper_level_status": PAPER_LEVEL_STATUS,
        "gate_statuses": {name: value["status"] for name, value in report["gates"].items()},
        "median_batch_seconds": median_seconds,
    }
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if profile_status in {"PASS_PROFILE", "PASS_FORMULA_ONLY"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
