"""New authority, independent of closed historical workflow permissions."""
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
REL = "studies/knapsack_parameters/mutation_population/"
WORKFLOW = ".github/workflows/knapsack-mutation-population.yml"
REGISTRATION_SHA = "06eb71fffd6caf4ddc21cad10e6c573ddd1ae8b4"
BASE_SHA = "e0e3ee88576f1ff325f3282e4a11fe7156a02f24"
PROTOCOL = "GA-KNAPSACK-MUTATION-POPULATION-V1"
REPOSITORY = "ChepaMaksym/GA-article-test"
BRANCH = "research/masters-ga-diversity-crossover"
TIMEOUTS = {"tests": 3, "prepare": 4, "pilot": 10}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False,
                      separators=(",", ":"), allow_nan=False).encode("utf-8")


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(canonical(value) + b"\n")


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def identity(path):
    raw = Path(path).read_bytes()
    return {"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def source_manifest():
    # Receipts, prepared banks and prose status updates are not executable sources.
    files = list(MODULE.rglob("*.py")) + [MODULE / name for name in
        ("PROTOCOL_UK.md", "registration.json", "environment.json", "population_source_gate.json")]
    files += [ROOT / WORKFLOW]
    files += [ROOT / name for name in read_json(MODULE / "registration.json")["protected_sha256"]]
    rows = [{"path": p.relative_to(ROOT).as_posix(), **identity(p)} for p in sorted(set(files))]
    return {"files": rows, "sha256": hashlib.sha256(canonical(rows)).hexdigest()}


def phase(message):
    # Recognize all bracket markers; an additional unknown marker cannot slip through.
    markers = re.findall(r"\[([^\[\]\r\n]+)\]", message)
    require(len(markers) == 1 and markers[0].startswith("mutation-population:"),
            "Exactly one registered mutation-population phase marker required")
    selected = markers[0].split(":", 1)[1]
    require(selected in TIMEOUTS, "Unknown or unimplemented phase")
    return selected


def write_manifest(directory):
    directory = Path(directory)
    rows = [{"path": p.relative_to(directory).as_posix(), **identity(p)}
            for p in sorted(directory.rglob("*")) if p.is_file() and p.name != "file_manifest.json"]
    write_json(directory / "file_manifest.json", {
        "protocol_id": PROTOCOL, "excludes_self": True, "files": rows})


def verify_manifest(directory):
    directory = Path(directory).resolve()
    manifest = read_json(directory / "file_manifest.json")
    require(manifest.get("protocol_id") == PROTOCOL and manifest.get("excludes_self") is True,
            "Wrong manifest authority")
    seen = set()
    for row in manifest["files"]:
        name = row["path"]
        rel = PurePosixPath(name)
        require(name and not rel.is_absolute() and ".." not in rel.parts and
                ":" not in name and "\\" not in name and name not in seen and
                name != "file_manifest.json", "Unsafe or duplicate artifact path")
        path = directory / rel
        require(path.resolve().is_relative_to(directory) and not path.is_symlink() and
                identity(path) == {"bytes": row["bytes"], "sha256": row["sha256"]},
                "Artifact checksum mismatch")
        seen.add(name)
    require(seen | {"file_manifest.json"} ==
            {p.relative_to(directory).as_posix() for p in directory.rglob("*") if p.is_file()},
            "Missing or unlisted artifact member")
    return manifest


def authenticate(runtime=False):
    require(os.environ.get("GITHUB_ACTIONS") == "true", "Scientific execution is CI-only")
    require(os.environ.get("GITHUB_REPOSITORY") == REPOSITORY and
            os.environ.get("GITHUB_REF") == "refs/heads/" + BRANCH, "Wrong repository or branch")
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    require(head == os.environ.get("GITHUB_SHA") == os.environ.get("EXPECTED_SHA"), "Wrong exact checkout")
    subprocess.run(["git", "merge-base", "--is-ancestor", REGISTRATION_SHA, head], cwd=ROOT, check=True)
    for name in ("PROTOCOL_UK.md", "registration.json"):
        original = subprocess.check_output(["git", "show", REGISTRATION_SHA + ":" + REL + name], cwd=ROOT)
        require(original == (MODULE / name).read_bytes(), "Preregistered contract changed")
    changed = subprocess.check_output(["git", "diff", "--name-only", BASE_SHA, head], cwd=ROOT, text=True).splitlines()
    require(all(name.startswith(REL) or name == WORKFLOW for name in changed), "Historical files changed")
    registration = read_json(MODULE / "registration.json")
    for name, digest in registration["protected_sha256"].items():
        require(identity(ROOT / name)["sha256"] == digest, "Protected input or engine changed: " + name)
    require(not subprocess.check_output(["git", "status", "--porcelain", "--untracked-files=no"],
                                       cwd=ROOT, text=True).strip(), "Dirty tracked CI checkout")
    result = {"protocol_id": PROTOCOL, "registration_sha": REGISTRATION_SHA,
              "implementation_sha": head, "run_id": int(os.environ["GITHUB_RUN_ID"]),
              "run_attempt": int(os.environ.get("GITHUB_RUN_ATTEMPT", "1")),
              "source_manifest": source_manifest()}
    if runtime:
        require(platform.python_implementation() == "CPython" and platform.python_version() == "3.12.14",
                "Wrong Python environment")
        inherited = read_json(ROOT / "studies/knapsack_parameters/ga_study/dependencies/environment.lock.json")
        versions = {p["name"]: importlib.metadata.version(p["name"]) for p in inherited["packages"]}
        require(all(versions[p["name"]] == p["version"] for p in inherited["packages"]),
                "Wrong hash-locked dependency versions")
        result["environment"] = {"python": platform.python_version(), "versions": versions,
                                 "record": identity(MODULE / "environment.json")}
    return result


def api(path):
    token = os.environ.get("GITHUB_TOKEN")
    require(bool(token), "Token required for CI resource/provenance audit")
    request = urllib.request.Request("https://api.github.com/repos/" + REPOSITORY + path,
        headers={"Authorization": "Bearer " + token, "Accept": "application/vnd.github+json",
                 "User-Agent": "mutation-population-audit", "X-GitHub-Api-Version": "2022-11-28"})
    with urllib.request.urlopen(request, timeout=25) as response:
        return json.load(response)


def pages(path, field):
    separator = "&" if "?" in path else "?"
    result, page_number = [], 1
    while True:
        batch = api(path + separator + f"per_page=100&page={page_number}")[field]
        result.extend(batch)
        if len(batch) < 100:
            return result
        page_number += 1


def runner_usage():
    """Round each prior allocated job, across every attempt of this workflow."""
    own = f"/actions/workflows/{Path(WORKFLOW).name}/runs?branch=" + urllib.parse.quote(BRANCH, safe="")
    current = (int(os.environ["GITHUB_RUN_ID"]), int(os.environ.get("GITHUB_RUN_ATTEMPT", "1")))
    rows = []
    for run in pages(own, "workflow_runs"):
        require(run["id"] == current[0] or run["status"] == "completed", "Concurrent workflow use unknown")
        for attempt in range(1, run["run_attempt"] + 1):
            if (run["id"], attempt) == current:
                continue
            for job in pages(f"/actions/runs/{run['id']}/attempts/{attempt}/jobs", "jobs"):
                if job.get("conclusion") == "skipped":
                    continue
                require(job.get("started_at") and job.get("completed_at"), "Unknown prior runner usage")
                duration = (datetime.fromisoformat(job["completed_at"].replace("Z", "+00:00")) -
                            datetime.fromisoformat(job["started_at"].replace("Z", "+00:00"))).total_seconds()
                require(duration >= 0, "Negative runner usage")
                rows.append({"run_id": run["id"], "attempt": attempt, "job_id": job["id"],
                             "minutes": max(1, math.ceil(duration / 60)), "conclusion": job["conclusion"]})
    require(len({r["job_id"] for r in rows}) == len(rows), "Duplicate runner accounting")
    return {"used_runner_minutes": sum(row["minutes"] for row in rows), "prior_jobs": rows}


def execution_permission(selected):
    require(selected in TIMEOUTS, "Unknown phase")
    if selected == "tests":
        return 6
    approval = read_json(MODULE / "execution_approval.json")
    require(approval.get("protocol_id") == PROTOCOL and approval.get("approved") is True and
            selected in approval.get("approved_phases", []) and bool(approval.get("approved_by")) and
            type(approval.get("runner_minutes")) is int and approval["runner_minutes"] > 0,
            "Separate scientific preparation/search resource approval missing")
    return approval["runner_minutes"]


def preflight(output):
    provenance = authenticate()
    selected = phase(os.environ.get("COMMIT_MESSAGE", ""))
    ceiling = execution_permission(selected)
    usage = runner_usage()
    require(usage["used_runner_minutes"] + TIMEOUTS[selected] <= ceiling,
            "Insufficient cumulative runner allowance")
    write_json(Path(output) / "preflight.json", {**provenance, **usage, "phase": selected,
        "ceiling": ceiling, "reserved_runner_minutes": TIMEOUTS[selected]})


def check_preflight(directory, selected):
    provenance = authenticate(runtime=True)
    require(phase(os.environ.get("COMMIT_MESSAGE", "")) == selected, "Phase mismatch")
    execution_permission(selected)
    permit = read_json(Path(directory) / "preflight.json")
    for field in ("protocol_id", "implementation_sha", "run_id", "run_attempt", "source_manifest"):
        require(permit.get(field) == provenance[field], "Stale or foreign preflight")
    require(permit.get("phase") == selected, "Preflight phase mismatch")
    return provenance


def validated_tests():
    receipt = read_json(MODULE / "validated_tests.json")
    require(receipt.get("protocol_id") == PROTOCOL and receipt.get("tests_passed") is True and
            type(receipt.get("tests_run")) is int and receipt["tests_run"] > 0 and
            receipt.get("source_manifest") == source_manifest(), "Missing or stale green CI tests")
    run = api(f"/actions/runs/{receipt['run_id']}/attempts/{receipt['run_attempt']}")
    require(run.get("conclusion") == "success" and run.get("head_sha") == receipt.get("implementation_sha") and
            run.get("head_branch") == BRANCH and run.get("event") == "push" and
            run.get("path") == WORKFLOW, "Tests did not finish successfully on this source")
    require(phase(run.get("head_commit", {}).get("message", "")) == "tests",
            "Successful run was not the tests phase")
    # Bind local source bytes to the recorded successful checkout, not a claimed fingerprint.
    for row in source_manifest()["files"]:
        original = subprocess.check_output(["git", "show", run["head_sha"] + ":" + row["path"]], cwd=ROOT)
        require(hashlib.sha256(original).hexdigest() == row["sha256"], "Green source differs from current source")
    return receipt
