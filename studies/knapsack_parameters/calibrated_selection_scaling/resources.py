"""Whole-process-tree CPU and RAM enclosure for every numerical CI phase.

The host launcher computes half of the runner's effective resources, then
Docker places the parent Python process and all descendants in one cgroup.
Thread environment variables and per-process RSS are not resource evidence.
"""
from __future__ import annotations

import argparse
from fractions import Fraction
import json
import os
from pathlib import Path
import platform
import re
import subprocess
import sys


ENVIRONMENT = "CALIBRATED_SELECTION_RESOURCE_LIMITS"
SCHEMA = "calibrated-selection-resource-enclosure-v1"
MAX_WORKERS = 2
GIB = 1024 ** 3


def _require(condition, message):
    if not condition:
        raise ValueError("Resource enclosure: " + message)


def _read(path):
    return Path(path).read_text(encoding="ascii").strip()


def _memory_total(proc_root):
    rows = dict(line.split(":", 1) for line in _read(Path(proc_root) / "meminfo").splitlines())
    fields = rows["MemTotal"].split()
    _require(len(fields) == 2 and fields[1] == "kB", "unrecognized MemTotal unit")
    return int(fields[0]) * 1024


def _current_cgroup(proc_root, cgroup_root, *, allow_unconstrained_root=False):
    """Locate our unified cgroup in both host and private cgroup namespaces."""
    lines = _read(Path(proc_root) / "self/cgroup").splitlines()
    unified = [line.split(":", 2)[2] for line in lines if line.startswith("0::")]
    _require(len(unified) == 1, "Linux cgroup v2 is required")
    root = Path(cgroup_root).resolve()
    relative = unified[0].lstrip("/")
    _require(".." not in Path(relative).parts, "unsafe cgroup membership")
    candidate = root / relative
    # Docker may expose the current subtree as the mount root.
    if not ((candidate / "cpu.max").is_file() and (candidate / "memory.max").is_file()):
        candidate = root
    uncapped_root = allow_unconstrained_root and relative == "" and candidate == root
    _require(uncapped_root or ((candidate / "cpu.max").is_file() and (candidate / "memory.max").is_file()),
             "CPU and memory controllers must both be available")
    _require(candidate.resolve().is_relative_to(root), "cgroup path escapes its mount")
    return candidate


def _ancestors(cgroup, cgroup_root):
    root = Path(cgroup_root).resolve()
    cursor = cgroup.resolve()
    while True:
        yield cursor
        if cursor == root:
            break
        cursor = cursor.parent


def _cpu_limit(raw):
    fields = raw.split()
    _require(len(fields) == 2 and int(fields[1]) > 0, "malformed cpu.max")
    return None if fields[0] == "max" else Fraction(int(fields[0]), int(fields[1]))


def host_limits(*, proc_root="/proc", cgroup_root="/sys/fs/cgroup", affinity=None):
    """Read effective host/parent limits; never round the half-CPU cap upward."""
    _require(platform.system() == "Linux", "the enclosing launcher requires Linux")
    logical = os.cpu_count()
    _require(type(logical) is int and logical > 0, "logical CPU count unavailable")
    cpu_ids = sorted(os.sched_getaffinity(0) if affinity is None else affinity)
    _require(cpu_ids and all(type(value) is int and value >= 0 for value in cpu_ids),
             "CPU affinity is unavailable")
    memory = _memory_total(proc_root)
    cpu = Fraction(min(logical, len(cpu_ids)), 1)
    cgroup = _current_cgroup(proc_root, cgroup_root, allow_unconstrained_root=True)
    for parent in _ancestors(cgroup, cgroup_root):
        is_root = parent == Path(cgroup_root).resolve()
        cpu_path, memory_path = parent / "cpu.max", parent / "memory.max"
        _require(is_root or (cpu_path.is_file() and memory_path.is_file()), "Missing non-root cgroup controllers")
        quota = _cpu_limit(_read(cpu_path)) if cpu_path.is_file() else None
        if quota is not None:
            _require(quota > 0, "nonpositive enclosing CPU quota")
            cpu = min(cpu, quota)
        raw = _read(memory_path) if memory_path.is_file() else "max"
        if raw != "max":
            _require(int(raw) > 0, "nonpositive enclosing RAM limit")
            memory = min(memory, int(raw))
    half_cpu = cpu / 2
    # Docker's --cpus is an exact decimal fraction with a microsecond period.
    # Truncation preserves the ceiling when an existing quota is fractional.
    cpu_micros = half_cpu.numerator * 1_000_000 // half_cpu.denominator
    _require(cpu_micros >= 1_000 and memory // 2 >= 64 * 1024 ** 2,
             "runner is too small for a safe half-resource enclosure")
    return {"schema": SCHEMA, "logical_cpus": logical, "affinity_cpus": cpu_ids,
            "effective_cpu_numerator": cpu.numerator, "effective_cpu_denominator": cpu.denominator,
            "effective_memory_bytes": memory, "cpu_micros": cpu_micros,
            "cpu_period_micros": 1_000_000, "memory_bytes": memory // 2,
            "maximum_workers": MAX_WORKERS, "scope": "parent_and_all_descendants_one_cgroup"}


def _validate_limits(limits):
    _require(type(limits) is dict and limits.get("schema") == SCHEMA, "wrong limits schema")
    for key in ("effective_cpu_numerator", "effective_cpu_denominator", "effective_memory_bytes",
                "cpu_micros", "cpu_period_micros", "memory_bytes", "maximum_workers"):
        _require(type(limits.get(key)) is int and limits[key] > 0, "invalid limit " + key)
    cpu = Fraction(limits["cpu_micros"], limits["cpu_period_micros"])
    host = Fraction(limits["effective_cpu_numerator"], limits["effective_cpu_denominator"])
    _require(cpu <= host / 2 and limits["memory_bytes"] <= limits["effective_memory_bytes"] // 2,
             "limits exceed half of the runner's effective resources")
    _require(limits["maximum_workers"] <= MAX_WORKERS and
             limits.get("scope") == "parent_and_all_descendants_one_cgroup", "invalid process-tree scope")
    return cpu


def launch_command(argv, workspace, limits, *, image, memory_ceiling_bytes=None):
    """Construct an auditable Docker command enclosing the entire CI phase."""
    _validate_limits(limits)
    _require(type(argv) is list and argv and all(type(word) is str and word for word in argv),
             "a nonempty argument vector is required")
    _require(type(image) is str and re.fullmatch(r"[^\s]+@sha256:[0-9a-f]{64}", image),
             "a digest-pinned OCI image is required")
    _require(not os.environ.get(ENVIRONMENT), "nested resource launch refused")
    root = Path(workspace).resolve()
    _require(root.is_dir() and "," not in str(root), "invalid workspace mount")
    bounded = dict(limits)
    cpu_ids = bounded.get("affinity_cpus")
    _require(type(cpu_ids) is list and cpu_ids and len(cpu_ids) == len(set(cpu_ids)) and
             all(type(value) is int and value >= 0 for value in cpu_ids), "invalid host CPU affinity")
    quota = Fraction(bounded["cpu_micros"], bounded["cpu_period_micros"])
    count = max(1, min(len(cpu_ids) // 2, (quota.numerator + quota.denominator - 1) // quota.denominator))
    bounded["cpuset_cpus"] = cpu_ids[:count]
    if memory_ceiling_bytes is not None:
        _require(type(memory_ceiling_bytes) is int and memory_ceiling_bytes > 0, "invalid phase RAM ceiling")
        bounded["memory_bytes"] = min(bounded["memory_bytes"], memory_ceiling_bytes)
    memory = str(bounded["memory_bytes"])
    # Format as a finite decimal: host_limits always uses period 1_000_000.
    _require(bounded["cpu_period_micros"] == 1_000_000, "unsupported CPU quota period")
    cpus = f"{bounded['cpu_micros'] // 1_000_000}.{bounded['cpu_micros'] % 1_000_000:06d}"
    environment = []
    for name in ("GITHUB_REPOSITORY", "GITHUB_REF", "GITHUB_RUN_ID", "GITHUB_RUN_ATTEMPT", "GITHUB_SHA",
                 "GITHUB_WORKFLOW", "GITHUB_JOB"):
        if name in os.environ:
            environment += ["--env", name + "=" + os.environ[name]]
    return ["docker", "run", "--rm", "--init", "--cpus", cpus, "--cpuset-cpus",
            ",".join(str(value) for value in bounded["cpuset_cpus"]), "--memory", memory,
            "--memory-swap", memory, "--pids-limit", "256", "--cap-drop", "ALL",
            "--security-opt", "no-new-privileges", "--mount", f"type=bind,src={root},dst=/workspace",
            "--workdir", "/workspace", "--env", "GITHUB_ACTIONS=true", "--env",
            ENVIRONMENT + "=" + json.dumps(bounded, sort_keys=True, separators=(",", ":")),
            "--env", "OMP_NUM_THREADS=1", "--env", "OPENBLAS_NUM_THREADS=1", "--env",
            "MKL_NUM_THREADS=1", "--env", "NUMEXPR_NUM_THREADS=1", "--env", "MPLBACKEND=Agg", "--env",
            "PYTHONDONTWRITEBYTECODE=1", "--env", "PYTHONHASHSEED=0", *environment, image, *argv]


def require_enclosure(*, workers=1, proc_root="/proc", cgroup_root="/sys/fs/cgroup"):
    """Reject numerical work unless kernel CPU/RAM caps enclose this process."""
    _require(os.environ.get("GITHUB_ACTIONS") == "true", "numerical work is CI-only")
    _require(platform.system() == "Linux", "Linux cgroup v2 is required")
    _require(type(workers) is int and 1 <= workers <= MAX_WORKERS, "at most two workers are allowed")
    try:
        limits = json.loads(os.environ[ENVIRONMENT])
    except (KeyError, json.JSONDecodeError) as error:
        raise ValueError("Resource enclosure: outer Docker launch receipt is absent") from error
    expected_cpu = _validate_limits(limits)
    cgroup = _current_cgroup(proc_root, cgroup_root)
    actual_cpu = _cpu_limit(_read(cgroup / "cpu.max"))
    raw_memory = _read(cgroup / "memory.max")
    _require(actual_cpu is not None and actual_cpu > 0 and actual_cpu <= expected_cpu,
             "kernel CPU quota is absent or larger than the enclosing ceiling")
    _require(raw_memory != "max" and 0 < int(raw_memory) <= limits["memory_bytes"],
             "kernel RAM cap is absent or larger than the enclosing ceiling")
    swap = cgroup / "memory.swap.max"
    _require(swap.is_file() and _read(swap) == "0", "swap must be disabled for the enclosing cgroup")
    _require(workers <= limits["maximum_workers"], "worker count exceeds launch receipt")
    allowed = limits.get("cpuset_cpus")
    _require(type(allowed) is list and allowed and set(os.sched_getaffinity(0)) <= set(allowed),
             "kernel CPU affinity differs from the enclosing CPU set")
    return {"schema": SCHEMA, "status": "VERIFIED_KERNEL_PROCESS_TREE_LIMITS",
            "limits": limits, "cgroup": str(cgroup), "kernel_cpu_max": _read(cgroup / "cpu.max"),
            "kernel_memory_max": int(raw_memory), "kernel_swap_max": 0,
            "workers": workers, "scope": "parent_and_all_descendants_one_cgroup"}


def launch(argv, workspace, *, image, memory_ceiling_bytes=None):
    _require(os.environ.get("GITHUB_ACTIONS") == "true", "resource launch is CI-only")
    limits = host_limits()
    command = launch_command(argv, workspace, limits, image=image,
                             memory_ceiling_bytes=memory_ceiling_bytes)
    return subprocess.run(command, check=True).returncode


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", required=True)
    parser.add_argument("--image", required=True)
    parser.add_argument("--memory-ceiling-bytes", type=int)
    parser.add_argument("command", nargs=argparse.REMAINDER)
    arguments = sys.argv[2:] if sys.argv[1:2] == ["launch"] else sys.argv[1:]
    args = parser.parse_args(arguments)
    command = args.command[1:] if args.command[:1] == ["--"] else args.command
    raise SystemExit(launch(command, args.workspace, image=args.image,
                            memory_ceiling_bytes=args.memory_ceiling_bytes))


if __name__ == "__main__":
    main()
