"""Bounded paper-audit identity; this module cannot authorize scientific campaigns."""

from __future__ import annotations

import hashlib
import json
import math
import os
from pathlib import Path, PurePosixPath
import platform
import re
import subprocess
from datetime import datetime
import urllib.parse
import urllib.request

ROOT = Path(__file__).resolve().parents[3]
REPO_ROOT = ROOT
MODULE_ROOT = Path(__file__).resolve().parent
PROTOCOL_ID = "GA-KNAPSACK-LAMBDA-COMPARISON-V1"
PROTOCOL_SHA = "8a7e2dfd63968da9e50cda7015529222dd5f0bb17f7826af46af26479af10623"
REGISTRATION_SHA = "6a1936084629ada822eca7dc210e202c33bb0c0b"
AUTHOR_REPO = "mariohevia/Parameter-Control-Mechanisms-Genetic-Algorithm"
AUTHOR_SHA = "49949a55208359ac93b7110afb23ed276bda158d"
INPUT_REPO = "brianwgoldman/P3"
INPUT_SHA = "712f76bb6ca79d39694d92a42fdabf9d30c2b91f"
BRANCH = "research/masters-ga-knapsack-parameters"
REPOSITORY = "ChepaMaksym/GA-article-test"
DATA_SHA = "528fee8da7d7cb776fb851e6a05949133830e9533c4091cbb4e8698ac19fb0df"
REGISTRY_SHA = "7e9b8fc893889426e2d3b57610e3a91c09263fcdff488cf15a2b84efe1bdc70f"
REQUIREMENTS_SHA = "6818e0e12843daa10947f7554cb3edd573d9f7cdbc33e63f98f9f3a068869017"
RUNTIME_SHA = "9907e3a46971303d8285b7ae160b5b8eafcab9942565d376bd038a92789745c6"
AUTHOR_RUNTIME_SHA = "17c35272fbf402a2fe021bb8f494a0eee0f8ae00e041f20fc7d3008512d06a84"
AUTHOR_REQUIREMENTS_SHA = "20d177be7f60ba929224edb37cd173653e59d0d0e729031d2ef58d861f4a5cb3"


def require(condition, message):
    if not condition:
        raise ValueError(message)


def canonical_bytes(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"), allow_nan=False).encode("utf-8")


def sha256_bytes(value):
    return hashlib.sha256(value).hexdigest()


def file_identity(path):
    path = Path(path)
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return {"bytes": path.stat().st_size, "sha256": digest.hexdigest()}


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(canonical_bytes(value))


def safe_member(root, relative):
    root = Path(root).resolve()
    pure = PurePosixPath(str(relative))
    require(str(relative) and not pure.is_absolute() and ".." not in pure.parts
            and "\\" not in str(relative) and ":" not in str(relative), "unsafe file path")
    path = root.joinpath(*pure.parts)
    require(path.resolve().is_relative_to(root) and not path.is_symlink(), "file outside evidence root")
    return path


def write_file_manifest(directory):
    directory = Path(directory)
    files = [{"path": path.relative_to(directory).as_posix(), **file_identity(path)}
             for path in sorted(directory.rglob("*"))
             if path.is_file() and path.relative_to(directory).as_posix() != "file_manifest.json"]
    # Reuse the already verified generic artifact transport without changing it.
    manifest = {"schema_version": "ga-knapsack-files-v1", "excludes_self": True, "files": files}
    write_json(directory / "file_manifest.json", manifest)
    return manifest


def implementation_fingerprint():
    files = [{"path": path.relative_to(ROOT).as_posix(), **file_identity(path)}
             for path in sorted(MODULE_ROOT.glob("*.py"))]
    return sha256_bytes(canonical_bytes(files))


def authenticate(expected_sha):
    require(os.environ.get("GITHUB_ACTIONS") == "true", "execution is allowed only in GitHub Actions")
    require(re.fullmatch(r"[0-9a-f]{40}", str(expected_sha)) is not None, "full checkout SHA required")
    actual = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    require(actual == expected_sha and os.environ.get("GITHUB_SHA") == expected_sha, "checkout SHA differs")
    require(os.environ.get("GITHUB_REF") == "refs/heads/" + BRANCH, "wrong research branch")
    require(os.environ.get("GITHUB_REPOSITORY") == REPOSITORY, "wrong repository")
    require(platform.python_version() == "3.12.14", "unexpected CPython patch version")
    require(file_identity(MODULE_ROOT / "protocol.json")["sha256"] == PROTOCOL_SHA, "registered protocol changed")
    registration = read_json(MODULE_ROOT / "registration.json")
    require(registration["registration_commit_sha"] == REGISTRATION_SHA
            and registration["protocol_sha256"] == PROTOCOL_SHA
            and registration["cleanup_verified_before_registration"] is True
            and registration["full_reproduction_authorized"] is False
            and registration["knapsack_execution_authorized"] is False,
            "registration or authority changed")
    protocol = read_json(MODULE_ROOT / "protocol.json")
    require(protocol["cleanup"]["status"] == "CLEANUP_COMPLETE"
            and protocol["authorized_now"]["cumulative_runner_minutes"] == 60
            and protocol["authorized_now"]["full_reproduction"] is False
            and protocol["authorized_now"]["knapsack_main"] is False,
            "unapproved scientific campaign")
    for relative, expected in (
        ("studies/knapsack_parameters/inputs/data_manifest.json", DATA_SHA),
        ("studies/knapsack_parameters/evidence/run-37637475385/registry.json", REGISTRY_SHA),
        ("studies/knapsack_parameters/ga_study/dependencies/requirements.lock", REQUIREMENTS_SHA),
        ("studies/knapsack_parameters/ga_study/dependencies/environment.lock.json", RUNTIME_SHA),
        ("studies/knapsack_parameters/lambda_study/author_runtime.json", AUTHOR_RUNTIME_SHA),
        ("studies/knapsack_parameters/lambda_study/requirements.author.lock", AUTHOR_REQUIREMENTS_SHA),
    ):
        require(file_identity(ROOT / relative)["sha256"] == expected, "historical input/runtime identity changed")
    return {"protocol_id": PROTOCOL_ID, "protocol_sha256": PROTOCOL_SHA,
            "registration_commit_sha": REGISTRATION_SHA, "implementation_commit_sha": expected_sha,
            "implementation_fingerprint": implementation_fingerprint(), "author_repository": AUTHOR_REPO,
            "author_commit_sha": AUTHOR_SHA, "input_repository": INPUT_REPO, "input_commit_sha": INPUT_SHA,
            "python_version": platform.python_version(), "runtime_lock_sha256": RUNTIME_SHA,
            "author_runtime_sha256": AUTHOR_RUNTIME_SHA, "author_requirements_sha256": AUTHOR_REQUIREMENTS_SHA,
            "run_id": int(os.environ["GITHUB_RUN_ID"]), "run_attempt": int(os.environ["GITHUB_RUN_ATTEMPT"]),
            "repository": REPOSITORY, "full_reproduction_authorized": False, "knapsack_execution_authorized": False}


def _github_json(endpoint):
    request = urllib.request.Request("https://api.github.com/repos/" + REPOSITORY + endpoint,
        headers={"Authorization": "Bearer " + os.environ["GITHUB_TOKEN"],
                 "Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"})
    with urllib.request.urlopen(request, timeout=60) as response:
        return json.load(response)


def _date(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def budget_preflight(phase):
    """Conservative billable-minute guard, including prior pushes and reruns.

    The two historical workflows also select a harmless stage on a branch push.
    Reserve ten minutes for them instead of assuming zero overhead. Any previous
    active run blocks a new stage; prior failure does not permit free retries.
    """
    maxima = {"audit": 28, "tests": 16, "pilot": 34}
    require(phase in maxima, "unapproved execution phase")
    require(re.search(r"\[knapsack(?:-ga)?:", os.environ.get("COMMIT_MESSAGE", "")) is None,
            "mixed historical execution markers cannot share the bounded paper budget")
    cutoff = _github_json("/commits/" + REGISTRATION_SHA)["commit"]["committer"]["date"]
    current_run = int(os.environ["GITHUB_RUN_ID"])
    current_attempt = int(os.environ.get("GITHUB_RUN_ATTEMPT", "1"))
    current_sha = os.environ["GITHUB_SHA"]
    branch = urllib.parse.quote(BRANCH, safe="")
    runs = []
    page = 1
    while True:
        payload = _github_json(f"/actions/runs?branch={branch}&per_page=100&page={page}")
        batch = payload["workflow_runs"]
        relevant = [run for run in batch
                    if _date(run.get("updated_at", run["created_at"])) >= _date(cutoff)]
        runs.extend(relevant)
        if not batch or len(batch) < 100:
            break
        page += 1
    used = 0
    rows = []
    for run in runs:
        legacy_current = run["head_sha"] == current_sha and run.get("path", "").split("@")[0] in (
            ".github/workflows/knapsack-parameters.yml", ".github/workflows/knapsack-feasibility.yml")
        if run["id"] == current_run:
            attempts = range(1, current_attempt)
        elif legacy_current:
            # Current harmless legacy jobs are covered by the ten-minute reserve.
            # Their earlier attempts, if any, still consume cumulative authority.
            attempts = range(1, run["run_attempt"])
        else:
            require(run["status"] == "completed", "prior branch workflow still active; do not spend concurrent budget")
            attempts = range(1, run["run_attempt"] + 1)
        jobs = []
        for attempt in attempts:
            job_page = 1
            while True:
                payload = _github_json(f"/actions/runs/{run['id']}/attempts/{attempt}/jobs?per_page=100&page={job_page}")
                batch = payload["jobs"]
                jobs.extend(batch)
                if len(batch) < 100:
                    break
                job_page += 1
        minutes = 0
        for job in jobs:
            if job["conclusion"] == "skipped":
                continue
            require(job.get("started_at") and job.get("completed_at"), "cannot authenticate previous runner time")
            if _date(job["started_at"]) < _date(cutoff):
                continue
            seconds = max(0, (_date(job["completed_at"]) - _date(job["started_at"])).total_seconds())
            minutes += max(1, math.ceil(seconds / 60))
        used += minutes
        rows.append({"run_id": run["id"], "run_attempt": run["run_attempt"],
                     "workflow": run["name"], "head_sha": run["head_sha"], "rounded_runner_minutes": minutes})
    reserved = maxima[phase] + 10
    require(used + reserved <= 60, f"runner budget exhausted: prior={used}, reserved={reserved}, limit=60")
    return {"schema_version": "ga-lambda-budget-preflight-v1", "phase": phase,
            "registration_cutoff_utc": cutoff, "previous_runs": rows,
            "previous_rounded_runner_minutes": used, "reserved_current_minutes": reserved,
            "cumulative_ceiling_minutes": 60, "authority": "bounded audit and technical pilot only"}
