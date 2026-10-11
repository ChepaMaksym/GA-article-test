"""Immutable pilot authority, CI identity, file evidence and runner-minute ceiling."""
from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
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

REPO_ROOT = Path(__file__).resolve().parents[3]
STUDY_ROOT = REPO_ROOT / "studies/diversity_crossover"
REGISTRATION_SHA = "760c14ba63933d1662aca878f73ec2d72cfe662d"
BASE_SHA = "d023331626d0b564f558229f8fb314cf25d0736d"
PROTOCOL_ID = "GA-DIVERSITY-CROSSOVER-TECHNICAL-PILOT-V1"
BRANCH = "research/masters-ga-diversity-crossover"
REPOSITORY = "ChepaMaksym/GA-article-test"
AUTHORITY = json.loads((STUDY_ROOT / "pilot_authority.json").read_text(encoding="utf-8"))
LOCK_ROOT = REPO_ROOT / "studies/knapsack_parameters/ga_study/dependencies"
REQUIREMENTS_SHA = "6818e0e12843daa10947f7554cb3edd573d9f7cdbc33e63f98f9f3a068869017"


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


def sha256_bytes(raw):
    return hashlib.sha256(raw).hexdigest()


def file_identity(path):
    raw = Path(path).read_bytes()
    return {"bytes": len(raw), "sha256": sha256_bytes(raw)}


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(canonical_bytes(value) + b"\n")


def source_manifest():
    paths = list((STUDY_ROOT / "implementation").rglob("*.py"))
    paths += [STUDY_ROOT / name for name in ("STAGE2_PROTOCOL_UK.md", "pilot_authority.json")]
    paths += [STUDY_ROOT / "provenance.json"]
    paths += [REPO_ROOT / ".github/workflows/diversity-crossover.yml"]
    paths += [LOCK_ROOT / name for name in ("requirements.lock", "environment.lock.json")]
    paths += [REPO_ROOT / "studies/knapsack_parameters/feasibility" / name for name in ("frozen_inputs.py", "data_audit.py")]
    rows = [{"path": path.relative_to(REPO_ROOT).as_posix(), **file_identity(path)} for path in sorted(paths)]
    return {"schema_version": 1, "protocol_id": PROTOCOL_ID, "files": rows, "sha256": sha256_bytes(canonical_bytes(rows))}


def write_file_manifest(directory):
    directory = Path(directory)
    rows = [{"path": p.relative_to(directory).as_posix(), **file_identity(p)} for p in sorted(directory.rglob("*"))
            if p.is_file() and p.name != "file_manifest.json"]
    result = {"schema_version": 1, "protocol_id": PROTOCOL_ID, "excludes_self": True, "files": rows}
    write_json(directory / "file_manifest.json", result)
    return result


def verify_file_manifest(directory):
    directory = Path(directory).resolve()
    manifest = read_json(directory / "file_manifest.json")
    require(manifest.get("schema_version") == 1 and manifest.get("protocol_id") == PROTOCOL_ID and
            manifest.get("excludes_self") is True, "Wrong file manifest")
    seen = set()
    for row in manifest["files"]:
        member = PurePosixPath(row["path"])
        require(not member.is_absolute() and ".." not in member.parts and ":" not in row["path"] and
                "\\" not in row["path"] and row["path"] not in seen and row["path"] != "file_manifest.json", "Unsafe/duplicate member")
        seen.add(row["path"])
        path = directory / member
        require(path.resolve().is_relative_to(directory) and not path.is_symlink(), "Unsafe member path")
        require(file_identity(path) == {"bytes": row["bytes"], "sha256": row["sha256"]}, "Member checksum mismatch")
    actual = {p.relative_to(directory).as_posix() for p in directory.rglob("*") if p.is_file()}
    require(actual == seen | {"file_manifest.json"}, "Missing or unexpected members")
    return manifest


def verify_environment():
    require(platform.python_version() == "3.12.14" and platform.python_implementation() == "CPython", "Wrong Python runtime")
    require(file_identity(LOCK_ROOT / "requirements.lock")["sha256"] == REQUIREMENTS_SHA, "Dependency lock changed")
    inherited = read_json(LOCK_ROOT / "environment.lock.json")
    versions = {p["name"]: importlib.metadata.version(p["name"]) for p in inherited["packages"]}
    require(all(versions[p["name"]] == p["version"] for p in inherited["packages"]), "Installed dependency version differs from lock")
    return {"protocol_id": PROTOCOL_ID, "python_version": platform.python_version(), "platform": platform.platform(),
            "versions": versions, "requirements_lock_sha256": REQUIREMENTS_SHA,
            "inherited_environment_lock": file_identity(LOCK_ROOT / "environment.lock.json")}


def authenticate(expected_sha=None, require_runtime=True):
    ci_only()
    expected_sha = expected_sha or os.environ.get("EXPECTED_SHA") or os.environ.get("GITHUB_SHA")
    require(isinstance(expected_sha, str) and re.fullmatch(r"[0-9a-f]{40}", expected_sha), "Expected SHA missing")
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, text=True).strip()
    require(head == expected_sha == os.environ.get("GITHUB_SHA"), "Checkout SHA mismatch")
    subprocess.run(["git", "merge-base", "--is-ancestor", REGISTRATION_SHA, head], cwd=REPO_ROOT, check=True)
    for name in ("STAGE2_PROTOCOL_UK.md", "pilot_authority.json"):
        path = "studies/diversity_crossover/" + name
        original = subprocess.check_output(["git", "show", REGISTRATION_SHA + ":" + path], cwd=REPO_ROOT)
        require(original == (REPO_ROOT / path).read_bytes(), "Registered authority changed")
    historical_paths = ["studies/diversity_crossover/provenance.json",
                        "studies/knapsack_parameters/ga_study/dependencies/requirements.lock",
                        "studies/knapsack_parameters/ga_study/dependencies/environment.lock.json",
                        "studies/knapsack_parameters/feasibility/frozen_inputs.py",
                        "studies/knapsack_parameters/feasibility/data_audit.py"]
    for path in historical_paths:
        original = subprocess.check_output(["git", "show", BASE_SHA + ":" + path], cwd=REPO_ROOT)
        require(original == (REPO_ROOT / path).read_bytes(), "Historical input/validation dependency changed")
    require(AUTHORITY["protocol_id"] == PROTOCOL_ID and AUTHORITY["cumulative_runner_minutes"] == 60,
            "Pilot authority mismatch")
    result = {"protocol_id": PROTOCOL_ID, "implementation_sha": head, "registration_sha": REGISTRATION_SHA,
              "run_id": int(os.environ["GITHUB_RUN_ID"]), "run_attempt": int(os.environ.get("GITHUB_RUN_ATTEMPT", "1")),
              "repository": REPOSITORY, "workflow_sha": os.environ.get("STUDY_WORKFLOW_SHA", head)}
    if require_runtime:
        result["environment"] = verify_environment()
    return result


def api(path):
    token = os.environ.get("GITHUB_TOKEN")
    require(bool(token), "GitHub token required for provenance/budget lookup")
    request = urllib.request.Request("https://api.github.com/repos/" + REPOSITORY + path,
        headers={"Authorization": "Bearer " + token, "Accept": "application/vnd.github+json", "User-Agent": "diversity-pilot"})
    with urllib.request.urlopen(request, timeout=20) as response:
        return json.load(response)


def _date(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def validate_artifact_receipt(run_id, artifact_id, head_sha, zip_sha256):
    """Authenticate a previously downloaded, byte-pinned CI artifact."""
    require(type(run_id) is int and type(artifact_id) is int and run_id > 0 and artifact_id > 0,
            "Invalid source run/artifact identity")
    require(re.fullmatch(r"[0-9a-f]{40}", head_sha or "") and
            re.fullmatch(r"[0-9a-f]{64}", zip_sha256 or ""), "Invalid source digest")
    run = api(f"/actions/runs/{run_id}")
    require(run["head_sha"] == head_sha and run["head_branch"] == BRANCH and
            run["status"] == "completed" and run["conclusion"] == "success", "Source phase did not pass")
    artifact = api(f"/actions/artifacts/{artifact_id}")
    require(not artifact["expired"] and artifact["digest"] == "sha256:" + zip_sha256 and
            artifact["workflow_run"]["id"] == run_id and artifact["workflow_run"]["head_sha"] == head_sha,
            "Source artifact digest/run differs or has expired")
    return artifact


def validate_tests_receipt():
    ci_only()
    receipt = read_json(STUDY_ROOT / "validated_implementation.json")
    require(receipt["protocol_id"] == PROTOCOL_ID and receipt["tests_passed"] is True and
            type(receipt["tests_run"]) is int and receipt["tests_run"] > 0, "Missing successful test evidence")
    require(receipt["source_manifest"] == source_manifest(), "Implementation/workflow changed after green tests")
    return validate_artifact_receipt(receipt["tests_run_id"], receipt["tests_artifact_id"],
                                     receipt["tests_sha"], receipt["tests_zip_sha256"])


def budget_preflight(stage):
    require(stage in AUTHORITY["authorized_phases"], "Unauthorized phase")
    authenticate(require_runtime=False)
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
    used, details = 0, []
    for run in runs:
        if run["id"] == current:
            attempts = range(1, current_attempt)
        else:
            require(run["status"] == "completed", "A previous branch workflow is still active")
            attempts = range(1, run["run_attempt"] + 1)
        for attempt in attempts:
            page = 1
            while True:
                jobs = api(f"/actions/runs/{run['id']}/attempts/{attempt}/jobs?per_page=100&page={page}")["jobs"]
                for job in jobs:
                    if job.get("conclusion") == "skipped":
                        continue
                    require(job.get("started_at") and job.get("completed_at"), "Unknown prior runner usage")
                    if _date(job["started_at"]) < cutoff:
                        continue
                    seconds = (_date(job["completed_at"]) - _date(job["started_at"])).total_seconds()
                    minutes = max(1, math.ceil(max(0, seconds) / 60))
                    used += minutes
                    details.append({"run_id": run["id"], "attempt": attempt, "job_id": job["id"], "minutes": minutes,
                                    "name": job["name"], "conclusion": job.get("conclusion")})
                if len(jobs) < 100:
                    break
                page += 1
    reserve = AUTHORITY["phase_reserves"][stage]
    require(used + reserve <= 60, f"Runner ceiling prevents phase: used={used}, reserve={reserve}, ceiling=60")
    return {"protocol_id": PROTOCOL_ID, "stage": stage, "used_runner_minutes": used, "reserved_runner_minutes": reserve,
            "ceiling": 60, "prior_jobs": details, "registration_cutoff": cutoff.isoformat()}


def phase_main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    message = os.environ.get("COMMIT_MESSAGE", "")
    markers = re.findall(r"\[diversity:([^\]]+)\]", message)
    require(len(markers) <= 1 and all(p in AUTHORITY["authorized_phases"] for p in markers), "Unknown/mixed pilot markers")
    require(not re.search(r"\[(?:knapsack|knapsack-ga|lambda-paper|knapsack-review):", message), "Mixed research authorization")
    stage = markers[0] if markers else "none"
    if stage != "none":
        write_json(args.output / "budget-preflight.json", budget_preflight(stage))
        write_file_manifest(args.output)
    with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as stream:
        stream.write("phase=" + stage + "\n")
    print("Authorized pilot phase:", stage)


if __name__ == "__main__":
    phase_main()
