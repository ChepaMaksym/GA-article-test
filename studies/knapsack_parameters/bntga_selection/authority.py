"""Operator/transfer tests only; historical scientific gates remain closed."""
from __future__ import annotations

from datetime import datetime
import hashlib
import importlib.metadata
import math
import os
from pathlib import Path, PurePosixPath
import platform
import re
import subprocess
import urllib.parse

# Transport primitives only: never call the previous module's phase authority.
from studies.knapsack_parameters.mutation_rules.authority import (
    canonical, identity, pages, read_json, require, write_json,
)

ROOT = Path(__file__).resolve().parents[3]
MODULE = Path(__file__).resolve().parent
REL = "studies/knapsack_parameters/bntga_selection/"
WORKFLOW = ".github/workflows/knapsack-bntga-selection.yml"
BASE_SHA = "656f5240e6d972626ae8e256ecb2290c27005027"
REGISTRATION_SHA = "1f4b82fa9487a1e57e39e60657d93fafb9f3b103"
SOURCE_AUDIT_SHA = "e2062d8987a71a3bfdc416576d68f64c37ef20de"
INTERFACE_SHA = "c7c64b010e50723fd3e720429410bbf8df38ab2e"
TRANSFER_SHA = "a30e89b2897150a25ec66cd7769a1c1023932281"
PROTOCOL = "GA-BNTGA-KNAPSACK-TRANSFER-V1"
REPOSITORY = "ChepaMaksym/GA-article-test"
BRANCH = "research/masters-ga-diversity-crossover"
WORKFLOWS = ("knapsack-mutation-population.yml", "knapsack-mutation-rules.yml",
             "knapsack-bntga-selection.yml")
ALLOWANCE = 6
TIMEOUT = 3


def phase(message):
    require(re.findall(r"\[([^\[\]\r\n]+)\]", message) == ["bntga-selection:tests"],
            "Exactly one tests marker required; scientific search phases remain closed")
    return "tests"


def protected_files():
    result = dict(read_json(MODULE / "registration.json")["protected_sha256"])
    for name, digest in read_json(MODULE / "transfer_registration.json")["protected_sha256"].items():
        require(name not in result or result[name] == digest, "Conflicting protected identities")
        result[name] = digest
    return result


def source_manifest():
    files = list(MODULE.rglob("*.py"))
    files += [MODULE / name for name in (".gitattributes", "PROTOCOL_UK.md", "registration.json", "source_gate.json",
                "SOURCE_AUDIT_UK.md", "INTERFACE_UK.md", "KNAPSACK_TRANSFER_PROTOCOL_UK.md",
                "transfer_registration.json")]
    files += [ROOT / WORKFLOW]
    files += [ROOT / name for name in protected_files()]
    rows = [{"path": p.relative_to(ROOT).as_posix(), **identity(p)} for p in sorted(set(files))]
    return {"files": rows, "sha256": hashlib.sha256(canonical(rows)).hexdigest()}


def authenticate(runtime=False):
    require(os.environ.get("GITHUB_ACTIONS") == "true", "Execution is CI-only")
    require(os.environ.get("GITHUB_REPOSITORY") == REPOSITORY and
            os.environ.get("GITHUB_REF") == "refs/heads/" + BRANCH, "Wrong repository or branch")
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    require(head == os.environ.get("GITHUB_SHA") == os.environ.get("EXPECTED_SHA"), "Wrong exact checkout")
    for revision, names in ((REGISTRATION_SHA, ("PROTOCOL_UK.md", "registration.json")),
                            (SOURCE_AUDIT_SHA, ("source_gate.json", "SOURCE_AUDIT_UK.md")),
                            (INTERFACE_SHA, ("INTERFACE_UK.md",)),
                            (TRANSFER_SHA, ("KNAPSACK_TRANSFER_PROTOCOL_UK.md", "transfer_registration.json"))):
        subprocess.run(["git", "merge-base", "--is-ancestor", revision, head], cwd=ROOT, check=True)
        for name in names:
            original = subprocess.check_output(["git", "show", revision + ":" + REL + name], cwd=ROOT)
            require(original == (MODULE / name).read_bytes(), "Frozen admission/transfer changed: " + name)
    changed = subprocess.check_output(["git", "diff", "--name-only", BASE_SHA, head],
                                      cwd=ROOT, text=True).splitlines()
    require(all(name.startswith(REL) or name == WORKFLOW for name in changed),
            "Historical files changed outside the new module")
    for name, digest in protected_files().items():
        require(identity(ROOT / name)["sha256"] == digest, "Historical source/input changed: " + name)
    require(not subprocess.check_output(["git", "status", "--porcelain", "--untracked-files=no"],
                                       cwd=ROOT, text=True).strip(), "Dirty tracked checkout")
    result = {"protocol_id": PROTOCOL, "registration_sha": REGISTRATION_SHA,
              "source_audit_sha": SOURCE_AUDIT_SHA, "interface_sha": INTERFACE_SHA,
              "transfer_registration_sha": TRANSFER_SHA, "implementation_sha": head,
              "run_id": int(os.environ["GITHUB_RUN_ID"]),
              "run_attempt": int(os.environ.get("GITHUB_RUN_ATTEMPT", "1")),
              "source_manifest": source_manifest()}
    if runtime:
        require(platform.python_implementation() == "CPython" and platform.python_version() == "3.12.14",
                "Wrong Python environment")
        locked = read_json(ROOT / "studies/knapsack_parameters/ga_study/dependencies/environment.lock.json")
        versions = {p["name"]: importlib.metadata.version(p["name"]) for p in locked["packages"]}
        require(all(versions[p["name"]] == p["version"] for p in locked["packages"]),
                "Wrong historical hash-locked dependencies")
        result["environment"] = {"python": platform.python_version(), "packages": versions,
                                 "historical_environment_unchanged": True}
    return result


def runner_usage():
    current = (int(os.environ["GITHUB_RUN_ID"]), int(os.environ.get("GITHUB_RUN_ATTEMPT", "1")))
    seen_runs, seen_jobs, rows = set(), set(), []
    for workflow in WORKFLOWS:
        endpoint = "/actions/workflows/" + workflow + "/runs?branch=" + urllib.parse.quote(BRANCH, safe="")
        for run in pages(endpoint, "workflow_runs"):
            require(run["id"] not in seen_runs, "Duplicate workflow run")
            seen_runs.add(run["id"])
            require(run["id"] == current[0] or run["status"] == "completed", "Concurrent usage unknown")
            for attempt in range(1, run["run_attempt"] + 1):
                if (run["id"], attempt) == current:
                    continue
                for job in pages(f"/actions/runs/{run['id']}/attempts/{attempt}/jobs", "jobs"):
                    if job.get("conclusion") == "skipped":
                        continue
                    require(job["id"] not in seen_jobs, "Duplicate allocated job")
                    seen_jobs.add(job["id"])
                    require(job.get("started_at") and job.get("completed_at"), "Unknown allocated duration")
                    duration = (datetime.fromisoformat(job["completed_at"].replace("Z", "+00:00")) -
                                datetime.fromisoformat(job["started_at"].replace("Z", "+00:00"))).total_seconds()
                    require(duration >= 0, "Negative job duration")
                    rows.append({"workflow": workflow, "run_id": run["id"], "attempt": attempt,
                                 "job_id": job["id"], "conclusion": job["conclusion"],
                                 "minutes": max(1, math.ceil(duration / 60))})
    return {"used_runner_minutes": sum(row["minutes"] for row in rows), "prior_jobs": rows}


def check_allowance(usage):
    require(type(usage.get("used_runner_minutes")) is int and
            0 <= usage["used_runner_minutes"] <= ALLOWANCE - TIMEOUT,
            "Shared unit-check allowance insufficient; scientific searches remain closed")


def preflight(output):
    record = authenticate()
    selected = phase(os.environ.get("COMMIT_MESSAGE", ""))
    usage = runner_usage()
    check_allowance(usage)
    write_json(Path(output) / "preflight.json", {**record, **usage, "phase": selected,
        "shared_runner_ceiling": ALLOWANCE, "reserved_runner_minutes": TIMEOUT,
        "scientific_search_authorized": False, "auxiliary_archive_transfer_approved": True})


def check_preflight(output):
    record = authenticate(runtime=True)
    phase(os.environ.get("COMMIT_MESSAGE", ""))
    permit = read_json(Path(output) / "preflight.json")
    for name in ("protocol_id", "implementation_sha", "run_id", "run_attempt", "source_manifest"):
        require(permit.get(name) == record[name], "Stale or foreign preflight")
    require(permit.get("phase") == "tests" and permit.get("shared_runner_ceiling") == ALLOWANCE and
            permit.get("reserved_runner_minutes") == TIMEOUT and
            permit.get("scientific_search_authorized") is False and
            permit.get("auxiliary_archive_transfer_approved") is True, "Wrong tests-only permit")
    check_allowance(permit)
    return record


def write_manifest(output):
    output = Path(output)
    files = [{"path": p.relative_to(output).as_posix(), **identity(p)} for p in sorted(output.rglob("*"))
             if p.is_file() and p.name != "file_manifest.json"]
    write_json(output / "file_manifest.json", {"protocol_id": PROTOCOL, "files": files})


def verify_manifest(output):
    output = Path(output).resolve()
    record = read_json(output / "file_manifest.json")
    require(record.get("protocol_id") == PROTOCOL, "Wrong artifact authority")
    seen = set()
    for row in record["files"]:
        name = row["path"]
        relative = PurePosixPath(name)
        require(name and name not in seen and not relative.is_absolute() and ".." not in relative.parts and
                ":" not in name and "\\" not in name and name != "file_manifest.json", "Unsafe artifact path")
        path = output / relative
        require(path.resolve().is_relative_to(output) and not path.is_symlink() and
                identity(path) == {"bytes": row["bytes"], "sha256": row["sha256"]}, "Artifact checksum mismatch")
        seen.add(name)
    require(seen | {"file_manifest.json"} ==
            {p.relative_to(output).as_posix() for p in output.rglob("*") if p.is_file()},
            "Unlisted or missing artifact member")
    return record
