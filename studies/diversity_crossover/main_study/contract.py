"""Separate main-series authority; never relax the historical pilot contract."""
from __future__ import annotations

import argparse
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

REPO_ROOT = Path(__file__).resolve().parents[3]
STUDY_ROOT = REPO_ROOT / "studies/diversity_crossover"
MAIN_ROOT = STUDY_ROOT / "main_study"
PROTOCOL_ID = "GA-DIVERSITY-CROSSOVER-MAIN-V1"
REGISTRATION_SHA = "d1a3c69434b67c0f8281370d92c7a0f4d2bcabee"
BASE_SHA = "78ef1bfdca361699cd2bdf5a926e50b45ce41e95"
BRANCH = "research/masters-ga-diversity-crossover"
REPOSITORY = "ChepaMaksym/GA-article-test"
AUTHORITY = json.loads((STUDY_ROOT / "main_authority.json").read_text(encoding="utf-8"))
LOCK_ROOT = REPO_ROOT / "studies/knapsack_parameters/ga_study/dependencies"
REQUIREMENTS_SHA = "6818e0e12843daa10947f7554cb3edd573d9f7cdbc33e63f98f9f3a068869017"
PHASE_RESERVES = {"tests": 16, "prepare": 16, "main": 1057, "aggregate": 21, "closure": 6}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def ci_only():
    require(os.environ.get("GITHUB_ACTIONS") == "true", "Scientific execution is allowed only in GitHub Actions")
    require(os.environ.get("GITHUB_REPOSITORY") == REPOSITORY, "Wrong CI repository")
    require(os.environ.get("GITHUB_REF") == "refs/heads/" + BRANCH, "Wrong CI branch")


scientific_ci_guard = ci_only


def canonical_bytes(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def file_identity(path):
    raw = Path(path).read_bytes()
    return {"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(canonical_bytes(value) + b"\n")


def source_manifest():
    paths = list(MAIN_ROOT.rglob("*.py"))
    paths += list((STUDY_ROOT / "implementation").rglob("*.py"))
    paths += [STUDY_ROOT / n for n in ("MAIN_PROTOCOL_UK.md", "MAIN_APPROVAL_UK.md", "main_authority.json", "provenance.json")]
    paths += [REPO_ROOT / ".github/workflows/diversity-crossover-main.yml"]
    paths += [LOCK_ROOT / n for n in ("requirements.lock", "environment.lock.json")]
    paths += [REPO_ROOT / "studies/knapsack_parameters/feasibility" / n for n in ("frozen_inputs.py", "data_audit.py")]
    rows = [{"path": p.relative_to(REPO_ROOT).as_posix(), **file_identity(p)} for p in sorted(set(paths))]
    return {"schema_version": 1, "protocol_id": PROTOCOL_ID, "files": rows,
            "sha256": hashlib.sha256(canonical_bytes(rows)).hexdigest()}


def write_file_manifest(directory):
    directory = Path(directory)
    rows = [{"path": p.relative_to(directory).as_posix(), **file_identity(p)}
            for p in sorted(directory.rglob("*")) if p.is_file() and p.name != "file_manifest.json"]
    manifest = {"schema_version": 1, "protocol_id": PROTOCOL_ID, "excludes_self": True, "files": rows}
    write_json(directory / "file_manifest.json", manifest)
    return manifest


def verify_file_manifest(directory):
    directory = Path(directory).resolve()
    manifest = read_json(directory / "file_manifest.json")
    require(manifest.get("schema_version") == 1 and manifest.get("protocol_id") == PROTOCOL_ID and
            manifest.get("excludes_self") is True, "Wrong main file manifest")
    seen = set()
    for row in manifest["files"]:
        member = PurePosixPath(row["path"])
        require(not member.is_absolute() and ".." not in member.parts and ":" not in row["path"] and
                "\\" not in row["path"] and row["path"] not in seen and row["path"] != "file_manifest.json",
                "Unsafe or duplicate main member")
        seen.add(row["path"])
        path = directory / member
        require(path.resolve().is_relative_to(directory) and not path.is_symlink(), "Unsafe main member path")
        require(file_identity(path) == {"bytes": row["bytes"], "sha256": row["sha256"]}, "Main member checksum mismatch")
    actual = {p.relative_to(directory).as_posix() for p in directory.rglob("*") if p.is_file()}
    require(actual == seen | {"file_manifest.json"}, "Missing or unexpected main members")
    return manifest


def verify_environment():
    require(platform.python_version() == "3.12.14" and platform.python_implementation() == "CPython", "Wrong Python runtime")
    require(file_identity(LOCK_ROOT / "requirements.lock")["sha256"] == REQUIREMENTS_SHA, "Dependency lock changed")
    inherited = read_json(LOCK_ROOT / "environment.lock.json")
    versions = {p["name"]: importlib.metadata.version(p["name"]) for p in inherited["packages"]}
    require(all(versions[p["name"]] == p["version"] for p in inherited["packages"]), "Installed dependency version differs")
    return {"protocol_id": PROTOCOL_ID, "python_version": platform.python_version(),
            "platform": platform.platform(), "versions": versions,
            "requirements_lock_sha256": REQUIREMENTS_SHA,
            "inherited_environment_lock": file_identity(LOCK_ROOT / "environment.lock.json")}


def authenticate(expected_sha=None, require_runtime=True):
    ci_only()
    sha = expected_sha or os.environ.get("EXPECTED_SHA") or os.environ.get("GITHUB_SHA")
    require(isinstance(sha, str) and re.fullmatch(r"[0-9a-f]{40}", sha), "Expected SHA missing")
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, text=True).strip()
    require(head == sha == os.environ.get("GITHUB_SHA"), "Checkout SHA mismatch")
    subprocess.run(["git", "merge-base", "--is-ancestor", REGISTRATION_SHA, head], cwd=REPO_ROOT, check=True)
    for name in ("MAIN_PROTOCOL_UK.md", "MAIN_APPROVAL_UK.md", "main_authority.json"):
        path = "studies/diversity_crossover/" + name
        original = subprocess.check_output(["git", "show", REGISTRATION_SHA + ":" + path], cwd=REPO_ROOT)
        require(original == (REPO_ROOT / path).read_bytes(), "Registered main authority changed")
    historical = list((STUDY_ROOT / "implementation").rglob("*.py"))
    historical += [STUDY_ROOT / n for n in ("STAGE2_PROTOCOL_UK.md", "pilot_authority.json", "provenance.json")]
    historical += [LOCK_ROOT / n for n in ("requirements.lock", "environment.lock.json")]
    historical += [REPO_ROOT / "studies/knapsack_parameters/feasibility" / n for n in ("frozen_inputs.py", "data_audit.py")]
    for path in historical:
        relative = path.relative_to(REPO_ROOT).as_posix()
        original = subprocess.check_output(["git", "show", BASE_SHA + ":" + relative], cwd=REPO_ROOT)
        require(original == path.read_bytes(), "Historical implementation or dependency changed: " + relative)
    require(AUTHORITY["protocol_id"] == PROTOCOL_ID and AUTHORITY["resources"]["approved"] is True and
            AUTHORITY["resources"]["approved_runner_minutes"] == 1200, "Main authority mismatch")
    result = {"protocol_id": PROTOCOL_ID, "implementation_sha": sha, "registration_sha": REGISTRATION_SHA,
              "run_id": int(os.environ["GITHUB_RUN_ID"]), "run_attempt": int(os.environ.get("GITHUB_RUN_ATTEMPT", "1")),
              "repository": REPOSITORY, "workflow_sha": os.environ.get("STUDY_WORKFLOW_SHA", head)}
    if require_runtime:
        result["environment"] = verify_environment()
    return result


def api(path):
    token = os.environ.get("GITHUB_TOKEN")
    require(bool(token), "GitHub token required for provenance and budget")
    request = urllib.request.Request("https://api.github.com/repos/" + REPOSITORY + path,
        headers={"Authorization": "Bearer " + token, "Accept": "application/vnd.github+json",
                 "User-Agent": "diversity-main-evidence", "X-GitHub-Api-Version": "2022-11-28"})
    with urllib.request.urlopen(request, timeout=40) as response:
        return json.load(response)


def validate_artifact_receipt(run_id, artifact_id, head_sha, zip_sha256):
    ci_only()
    require(type(run_id) is int and type(artifact_id) is int and run_id > 0 and artifact_id > 0, "Invalid artifact IDs")
    require(isinstance(zip_sha256, str) and re.fullmatch(r"[0-9a-f]{64}", zip_sha256), "Missing artifact ZIP digest")
    run = api(f"/actions/runs/{run_id}")
    require(run["status"] == "completed" and run["conclusion"] == "success" and
            run["head_sha"] == head_sha and run["head_branch"] == BRANCH, "Source run incomplete or identity mismatch")
    artifact = api(f"/actions/artifacts/{artifact_id}")
    require(not artifact["expired"] and artifact["workflow_run"]["id"] == run_id and
            artifact["workflow_run"]["head_sha"] == head_sha and
            artifact.get("digest") == "sha256:" + zip_sha256, "Artifact expired or digest mismatch")
    return {"run": run, "artifact": artifact}


def validate_tests_receipt():
    ci_only()
    receipt = read_json(STUDY_ROOT / "main_validated_implementation.json")
    require(receipt.get("protocol_id") == PROTOCOL_ID and receipt.get("tests_passed") is True and
            type(receipt.get("tests_run")) is int and receipt["tests_run"] > 0, "Missing successful main tests")
    require(receipt["source_manifest"] == source_manifest(), "Main implementation changed after green tests")
    return validate_artifact_receipt(receipt["tests_run_id"], receipt["tests_artifact_id"],
                                     receipt["tests_sha"], receipt["tests_zip_sha256"])


def _date(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def runner_usage(include_current=False):
    """All branch jobs after registration, every attempt, rounded individually."""
    cutoff = _date(api("/commits/" + REGISTRATION_SHA)["commit"]["committer"]["date"])
    current = int(os.environ["GITHUB_RUN_ID"])
    current_attempt = int(os.environ.get("GITHUB_RUN_ATTEMPT", "1"))
    runs, page = [], 1
    while True:
        batch = api("/actions/runs?branch=" + urllib.parse.quote(BRANCH, safe="") + f"&per_page=100&page={page}")["workflow_runs"]
        runs.extend(r for r in batch if _date(r.get("updated_at", r["created_at"])) >= cutoff)
        if len(batch) < 100:
            break
        page += 1
    details, current_jobs = [], []
    for run in runs:
        is_current = run["id"] == current
        if is_current:
            attempts = range(1, current_attempt + int(include_current))
        else:
            # Other workflows from this same push may contain only skipped jobs.
            require(run["status"] == "completed", "Another branch workflow is still active")
            attempts = range(1, run["run_attempt"] + 1)
        for attempt in attempts:
            page = 1
            while True:
                jobs = api(f"/actions/runs/{run['id']}/attempts/{attempt}/jobs?per_page=100&page={page}")["jobs"]
                for job in jobs:
                    if job.get("conclusion") == "skipped":
                        continue
                    if is_current and attempt == current_attempt and not job.get("completed_at"):
                        current_jobs.append({"job_id": job["id"], "name": job["name"], "status": job["status"]})
                        continue
                    require(job.get("started_at") and job.get("completed_at"), "Unknown runner usage")
                    if _date(job["started_at"]) < cutoff:
                        continue
                    seconds = (_date(job["completed_at"]) - _date(job["started_at"])).total_seconds()
                    require(seconds >= 0, "Negative runner duration")
                    details.append({"run_id": run["id"], "attempt": attempt, "job_id": job["id"],
                                    "name": job["name"], "minutes": max(1, math.ceil(seconds / 60)),
                                    "conclusion": job.get("conclusion")})
                if len(jobs) < 100:
                    break
                page += 1
    require(len({r["job_id"] for r in details}) == len(details), "Repeated runner job")
    return {"protocol_id": PROTOCOL_ID, "used_runner_minutes": sum(r["minutes"] for r in details),
            "prior_jobs": details, "unfinished_current_jobs": current_jobs,
            "registration_cutoff": cutoff.isoformat(), "ceiling": 1200}


def budget_preflight(stage):
    require(stage in PHASE_RESERVES, "Unknown main phase")
    authenticate(require_runtime=False)
    usage = runner_usage()
    reserve = PHASE_RESERVES[stage]
    require(usage["used_runner_minutes"] + reserve <= 1200,
            f"Runner ceiling prevents phase: used={usage['used_runner_minutes']}, reserve={reserve}")
    return dict(usage, stage=stage, reserved_runner_minutes=reserve)


def job_budget_preflight(job_id, diagnostic=False):
    """Re-check retries and current parallel reservations before any new search."""
    ci_only()
    usage = runner_usage(include_current=True)
    reserved, current_seen = 0, False
    for job in usage["unfinished_current_jobs"]:
        name = job["name"]
        if name.startswith("main ("):
            reserved += 8 if name.startswith("main (global-") else 10
            current_seen |= name == f"main ({job_id})"
        elif name == "phase":
            reserved += 1
        elif name not in ("aggregate", "closure"):
            require(False, "Unknown active main-series job")
    if not current_seen:
        reserved += 8 if diagnostic else 10
    # Retain room for post-search integrity/statistics and accounting.
    reserved += 20
    require(usage["used_runner_minutes"] + reserved <= 1200,
            "Insufficient cumulative budget for current source/retry reservations")
    return dict(usage, job_id=job_id, reserved_runner_minutes=reserved)


def nonsearch_budget_preflight(job_name):
    ci_only()
    caps = {"tests": 10, "prepare": 10, "aggregate": 15, "closure": 5, "phase": 1}
    require(job_name in caps, "Unknown service job")
    usage = runner_usage(include_current=True)
    reserved, seen_names = 0, set()
    for job in usage["unfinished_current_jobs"]:
        name = job["name"]
        seen_names.add(name)
        if name.startswith("main ("):
            reserved += 8 if name.startswith("main (global-") else 10
        else:
            require(name in caps, "Unknown pending service job")
            reserved += caps[name]
    if job_name not in seen_names:
        reserved += caps[job_name]
    if job_name != "closure" and "closure" not in seen_names:
        reserved += caps["closure"]
    require(usage["used_runner_minutes"] + reserved <= 1200,
            "Insufficient cumulative budget for current service/retry reservations")
    return dict(usage, service_job=job_name, reserved_runner_minutes=reserved)


def parse_phase(message):
    markers = re.findall(r"\[diversity-main:([^\]]+)\]", message)
    require(len(markers) == 1 and markers[0] in PHASE_RESERVES, "Unknown or mixed main markers")
    require(not re.search(r"\[(?:diversity|knapsack|knapsack-ga|lambda-paper|knapsack-review):", message), "Mixed research marker")
    return markers[0]


def matrix_jobs():
    tasks = AUTHORITY["inputs"]["models"] + AUTHORITY["inputs"]["knapsack_instances"]
    return ([{"id": f"{task}-b{block}", "task": task, "block": block, "kind": "main"}
             for task in tasks for block in range(3)] +
            [{"id": f"global-b{block}", "task": "global", "block": block, "kind": "diagnostic"}
             for block in range(2)])


def phase_main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    stage = parse_phase(os.environ.get("COMMIT_MESSAGE", ""))
    write_json(args.output / "budget-preflight.json", budget_preflight(stage))
    write_file_manifest(args.output)
    with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as stream:
        stream.write("phase=" + stage + "\n")
        stream.write("matrix=" + json.dumps({"include": matrix_jobs()}, separators=(",", ":")) + "\n")
    print("Authorized main phase:", stage)


if __name__ == "__main__":
    phase_main()
