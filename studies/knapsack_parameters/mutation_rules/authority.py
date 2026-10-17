"""Separate, fail-closed tests authority; historical authorizations stay closed."""
from __future__ import annotations

from datetime import datetime
import hashlib
import importlib.metadata
import json
import math
import os
from pathlib import Path, PurePosixPath
import platform
import re
import subprocess
import urllib.parse
import urllib.request


ROOT = Path(__file__).resolve().parents[3]
MODULE = Path(__file__).resolve().parent
REL = "studies/knapsack_parameters/mutation_rules/"
WORKFLOW = ".github/workflows/knapsack-mutation-rules.yml"
REGISTRATION_SHA = "570748ec9fbacadfd91964342f540f34e66d1c01"
SOURCE_AUDIT_SHA = "5557808996b39684acbc95f34da681b4bee6ca34"
BASE_SHA = "e03572d1a74ad793a0e004bc6fad66d325a2961b"
PROTOCOL = "GA-KNAPSACK-MUTATION-RULES-V1"
REPOSITORY = "ChepaMaksym/GA-article-test"
BRANCH = "research/masters-ga-diversity-crossover"
SHARED_WORKFLOWS = ("knapsack-mutation-population.yml", "knapsack-mutation-rules.yml")
ALLOWANCE = 6
TIMEOUT = 3


def require(condition, message):
    if not condition:
        raise ValueError(message)


def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False,
                      separators=(",", ":"), allow_nan=False).encode("utf-8")


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(canonical(value) + b"\n")


def identity(path):
    raw = Path(path).read_bytes()
    return {"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def phase(message):
    require(re.findall(r"\[([^\[\]\r\n]+)\]", message) == ["mutation-rules:tests"],
            "Only one exact tests marker is admitted; scientific phases are closed")
    return "tests"


def source_manifest():
    files = list(MODULE.rglob("*.py"))
    files += [MODULE / name for name in ("PROTOCOL_UK.md", "registration.json",
                                        "source_gate.json", "SOURCE_AUDIT_UK.md", "BIBLIOGRAPHIC_ERRATA_UK.md")]
    files += [ROOT / WORKFLOW]
    files += [ROOT / name for name in read_json(MODULE / "registration.json")["protected_sha256"]]
    rows = [{"path": p.relative_to(ROOT).as_posix(), **identity(p)} for p in sorted(set(files))]
    return {"files": rows, "sha256": hashlib.sha256(canonical(rows)).hexdigest()}


def authenticate(runtime=False):
    require(os.environ.get("GITHUB_ACTIONS") == "true", "Execution is CI-only")
    require(os.environ.get("GITHUB_REPOSITORY") == REPOSITORY and
            os.environ.get("GITHUB_REF") == "refs/heads/" + BRANCH, "Wrong repository or branch")
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    require(head == os.environ.get("GITHUB_SHA") == os.environ.get("EXPECTED_SHA"), "Wrong exact checkout")
    for revision, names in ((REGISTRATION_SHA, ("PROTOCOL_UK.md", "registration.json", "SOURCE_AUDIT_UK.md")),
                            (SOURCE_AUDIT_SHA, ("source_gate.json",))):
        subprocess.run(["git", "merge-base", "--is-ancestor", revision, head], cwd=ROOT, check=True)
        for name in names:
            original = subprocess.check_output(["git", "show", revision + ":" + REL + name], cwd=ROOT)
            require(original == (MODULE / name).read_bytes(), "Frozen source/protocol changed: " + name)
    changed = subprocess.check_output(["git", "diff", "--name-only", BASE_SHA, head],
                                      cwd=ROOT, text=True).splitlines()
    require(all(name.startswith(REL) or name == WORKFLOW for name in changed),
            "Historical files changed outside new module")
    for name, digest in read_json(MODULE / "registration.json")["protected_sha256"].items():
        require(identity(ROOT / name)["sha256"] == digest, "Frozen engine/input changed: " + name)
    require(not subprocess.check_output(["git", "status", "--porcelain", "--untracked-files=no"],
                                       cwd=ROOT, text=True).strip(), "Dirty tracked checkout")
    result = {"protocol_id": PROTOCOL, "registration_sha": REGISTRATION_SHA,
              "source_audit_sha": SOURCE_AUDIT_SHA, "implementation_sha": head,
              "run_id": int(os.environ["GITHUB_RUN_ID"]),
              "run_attempt": int(os.environ.get("GITHUB_RUN_ATTEMPT", "1")),
              "source_manifest": source_manifest()}
    if runtime:
        require(platform.python_implementation() == "CPython" and platform.python_version() == "3.12.14",
                "Wrong Python environment")
        record = read_json(ROOT / "studies/knapsack_parameters/ga_study/dependencies/environment.lock.json")
        versions = {p["name"]: importlib.metadata.version(p["name"]) for p in record["packages"]}
        require(all(versions[p["name"]] == p["version"] for p in record["packages"]),
                "Wrong hash-locked dependencies")
        result["environment"] = {"python": platform.python_version(), "packages": versions,
                                 "inherited_lock": identity(ROOT / "studies/knapsack_parameters/ga_study/dependencies/environment.lock.json")}
    return result


def api(path):
    token = os.environ.get("GITHUB_TOKEN")
    require(bool(token), "GitHub token needed for resource audit")
    request = urllib.request.Request("https://api.github.com/repos/" + REPOSITORY + path,
        headers={"Authorization": "Bearer " + token, "Accept": "application/vnd.github+json",
                 "User-Agent": "mutation-rules-audit", "X-GitHub-Api-Version": "2022-11-28"})
    with urllib.request.urlopen(request, timeout=25) as response:
        return json.load(response)


def pages(path, field):
    result, number = [], 1
    separator = "&" if "?" in path else "?"
    while True:
        rows = api(path + separator + f"per_page=100&page={number}")[field]
        result.extend(rows)
        if len(rows) < 100:
            return result
        number += 1


def runner_usage():
    """Share the existing six-minute allowance, not six new minutes per module."""
    current = (int(os.environ["GITHUB_RUN_ID"]), int(os.environ.get("GITHUB_RUN_ATTEMPT", "1")))
    rows, seen_runs, seen_jobs = [], set(), set()
    for workflow in SHARED_WORKFLOWS:
        path = "/actions/workflows/" + workflow + "/runs?branch=" + urllib.parse.quote(BRANCH, safe="")
        for run in pages(path, "workflow_runs"):
            require(run["id"] not in seen_runs, "Duplicate workflow run")
            seen_runs.add(run["id"])
            require(run["id"] == current[0] or run["status"] == "completed",
                    "Concurrent or unknown shared runner usage")
            for attempt in range(1, run["run_attempt"] + 1):
                if (run["id"], attempt) == current:
                    continue
                for job in pages(f"/actions/runs/{run['id']}/attempts/{attempt}/jobs", "jobs"):
                    if job.get("conclusion") == "skipped":
                        continue
                    require(job["id"] not in seen_jobs, "Duplicate runner job")
                    seen_jobs.add(job["id"])
                    require(job.get("started_at") and job.get("completed_at"), "Unknown prior job duration")
                    duration = (datetime.fromisoformat(job["completed_at"].replace("Z", "+00:00")) -
                                datetime.fromisoformat(job["started_at"].replace("Z", "+00:00"))).total_seconds()
                    require(duration >= 0, "Negative job duration")
                    rows.append({"workflow": workflow, "run_id": run["id"], "attempt": attempt,
                                 "job_id": job["id"], "minutes": max(1, math.ceil(duration / 60)),
                                 "conclusion": job["conclusion"]})
    return {"used_runner_minutes": sum(row["minutes"] for row in rows), "prior_jobs": rows}


def check_allowance(usage):
    require(type(usage.get("used_runner_minutes")) is int and
            0 <= usage["used_runner_minutes"] <= ALLOWANCE - TIMEOUT,
            "Insufficient shared tests allowance; no scientific execution authorized")


def preflight(output):
    provenance = authenticate()
    selected = phase(os.environ.get("COMMIT_MESSAGE", ""))
    usage = runner_usage()
    check_allowance(usage)
    write_json(Path(output) / "preflight.json", {**provenance, **usage, "phase": selected,
        "shared_runner_ceiling": ALLOWANCE, "reserved_runner_minutes": TIMEOUT,
        "scientific_execution_authorized": False})


def check_preflight(output):
    provenance = authenticate(runtime=True)
    phase(os.environ.get("COMMIT_MESSAGE", ""))
    permit = read_json(Path(output) / "preflight.json")
    for name in ("protocol_id", "implementation_sha", "source_manifest", "run_id", "run_attempt"):
        require(permit.get(name) == provenance[name], "Stale/foreign preflight")
    require(permit.get("phase") == "tests" and permit.get("shared_runner_ceiling") == ALLOWANCE and
            permit.get("reserved_runner_minutes") == TIMEOUT and
            permit.get("scientific_execution_authorized") is False, "Wrong tests-only permit")
    check_allowance(permit)
    return provenance


def write_manifest(directory):
    directory = Path(directory)
    rows = [{"path": p.relative_to(directory).as_posix(), **identity(p)}
            for p in sorted(directory.rglob("*")) if p.is_file() and p.name != "file_manifest.json"]
    write_json(directory / "file_manifest.json", {"protocol_id": PROTOCOL, "files": rows})


def verify_manifest(directory):
    directory = Path(directory).resolve()
    manifest = read_json(directory / "file_manifest.json")
    require(manifest.get("protocol_id") == PROTOCOL, "Wrong artifact authority")
    seen = set()
    for row in manifest["files"]:
        name = row["path"]
        path = PurePosixPath(name)
        require(name and not path.is_absolute() and ".." not in path.parts and ":" not in name and
                "\\" not in name and name not in seen and name != "file_manifest.json",
                "Unsafe or duplicate artifact entry")
        target = directory / path
        require(target.resolve().is_relative_to(directory) and not target.is_symlink() and
                identity(target) == {"bytes": row["bytes"], "sha256": row["sha256"]},
                "Artifact member checksum mismatch")
        seen.add(name)
    require(seen | {"file_manifest.json"} ==
            {p.relative_to(directory).as_posix() for p in directory.rglob("*") if p.is_file()},
            "Unlisted or missing artifact member")
    return manifest
