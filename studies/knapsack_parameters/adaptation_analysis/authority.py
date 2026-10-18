"""Fail-closed execution authority: implementation is not a resource grant."""
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
import time
import urllib.parse
import urllib.request

ROOT = Path(__file__).resolve().parents[3]
MODULE = Path(__file__).resolve().parent
REL = "studies/knapsack_parameters/adaptation_analysis/"
WORKFLOW = ".github/workflows/knapsack-adaptation-analysis.yml"
BASE_SHA = "07ee6ad1a636318d4e6e839ec1688ef6642bbb2e"
REGISTRATION_SHA = "d11e4af45cd3b2c46b7b3fac03b32b520e61cf8d"
PROTOCOL = "GA-KNAPSACK-ADAPTATION-ANALYSIS-V1"
REPOSITORY = "ChepaMaksym/GA-article-test"
BRANCH = "research/masters-ga-diversity-crossover"
SHARED_WORKFLOWS = ("knapsack-mutation-population.yml", "knapsack-mutation-rules.yml",
                    "knapsack-bntga-selection.yml", "knapsack-adaptation-analysis.yml")
JOB_RESERVATION = 3


def require(condition, message):
    if not condition:
        raise ValueError(message)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False).encode("utf-8")


def identity(path):
    raw = Path(path).read_bytes()
    return {"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(canonical(value) + b"\n")


def phase(message):
    require(re.findall(r"\[([^\[\]\r\n]+)\]", message) == ["adaptation-analysis:tests"],
            "Only one exact tests marker admitted; preparation/pilot/main/statistics/lambda remain closed")
    return "tests"


def resource_grant():
    path = MODULE / "resource_authorization.json"
    require(path.is_file(), "BLOCKED_RESOURCE_APPROVAL: no additional CI budget granted")
    grant = read_json(path)
    require(grant.get("protocol_id") == PROTOCOL and grant.get("explicit_user_approval") is True and
            grant.get("allowed_phases") == ["tests"] and
            all(type(grant.get(name)) is int for name in
                ("additional_runner_minutes", "shared_ceiling_minutes", "job_reservation_minutes")) and
            grant.get("additional_runner_minutes") == 6 and grant.get("shared_ceiling_minutes") == 12 and
            grant.get("job_reservation_minutes") == JOB_RESERVATION and
            grant.get("scientific_search_authorized") is False and
            grant.get("lambda_search_authorized") is False,
            "Missing or incompatible tests-only resource grant")
    return grant


def source_manifest():
    files = list(MODULE.rglob("*.py"))
    files += [MODULE / name for name in (".gitattributes", "PROTOCOL_UK.md", "registration.json")]
    if (MODULE / "resource_authorization.json").is_file():
        files.append(MODULE / "resource_authorization.json")
    files += [ROOT / WORKFLOW]
    files += [ROOT / name for name in read_json(MODULE / "registration.json")["protected_sha256"]]
    rows = [{"path": p.relative_to(ROOT).as_posix(), **identity(p)} for p in sorted(set(files))]
    return {"files": rows, "sha256": hashlib.sha256(canonical(rows)).hexdigest()}


def authenticate(runtime=False):
    require(os.environ.get("GITHUB_ACTIONS") == "true" and
            os.environ.get("GITHUB_REPOSITORY") == REPOSITORY and
            os.environ.get("GITHUB_REF") == "refs/heads/" + BRANCH, "Wrong execution environment")
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    require(head == os.environ.get("GITHUB_SHA") == os.environ.get("EXPECTED_SHA"), "Wrong exact checkout")
    subprocess.run(["git", "merge-base", "--is-ancestor", REGISTRATION_SHA, head], cwd=ROOT, check=True)
    for name in ("PROTOCOL_UK.md", "registration.json", ".gitattributes"):
        original = subprocess.check_output(["git", "show", REGISTRATION_SHA + ":" + REL + name], cwd=ROOT)
        require(original == (MODULE / name).read_bytes(), "Frozen protocol changed: " + name)
    changed = subprocess.check_output(["git", "diff", "--name-only", BASE_SHA, head],
                                      cwd=ROOT, text=True).splitlines()
    require(all(name.startswith(REL) or name == WORKFLOW for name in changed), "Historical files changed")
    for name, digest in read_json(MODULE / "registration.json")["protected_sha256"].items():
        require(identity(ROOT / name)["sha256"] == digest, "Historical dependency/input changed: " + name)
    require(not subprocess.check_output(["git", "status", "--porcelain", "--untracked-files=no"],
                                       cwd=ROOT, text=True).strip(), "Dirty tracked checkout")
    result = {"protocol_id": PROTOCOL, "registration_sha": REGISTRATION_SHA,
              "implementation_sha": head, "source_manifest": source_manifest(),
              "run_id": int(os.environ["GITHUB_RUN_ID"]),
              "run_attempt": int(os.environ.get("GITHUB_RUN_ATTEMPT", "1"))}
    if runtime:
        require(platform.python_implementation() == "CPython" and platform.python_version() == "3.12.14",
                "Wrong Python environment")
        lock = read_json(ROOT / "studies/knapsack_parameters/ga_study/dependencies/environment.lock.json")
        versions = {row["name"]: importlib.metadata.version(row["name"]) for row in lock["packages"]}
        require(all(versions[row["name"]] == row["version"] for row in lock["packages"]), "Wrong dependencies")
        result["environment"] = {"python": platform.python_version(), "packages": versions}
    return result


def api(path):
    require(path.startswith("/actions/") and ".." not in path, "Invalid API endpoint")
    token = os.environ.get("GITHUB_TOKEN")
    require(token, "API token required for resource accounting")
    request = urllib.request.Request("https://api.github.com/repos/" + REPOSITORY + path,
        headers={"Authorization": "Bearer " + token, "Accept": "application/vnd.github+json",
                 "User-Agent": "ga-adaptation-resource-accounting"})
    with urllib.request.urlopen(request, timeout=15) as response:
        return json.load(response)


def pages(path, key):
    result, page = [], 1
    while True:
        batch = api(path + ("&" if "?" in path else "?") + f"per_page=100&page={page}")[key]
        result.extend(batch)
        if len(batch) < 100:
            return result
        page += 1


def runner_usage():
    current = (int(os.environ["GITHUB_RUN_ID"]), int(os.environ.get("GITHUB_RUN_ATTEMPT", "1")))
    rows, seen_runs, seen_jobs = [], set(), set()
    for workflow in SHARED_WORKFLOWS:
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
                    require(duration >= 0, "Negative allocated duration")
                    rows.append({"workflow": workflow, "run_id": run["id"], "attempt": attempt,
                                 "job_id": job["id"], "conclusion": job["conclusion"],
                                 "minutes": max(1, math.ceil(duration / 60))})
    return {"used_runner_minutes": sum(row["minutes"] for row in rows), "prior_jobs": rows}


def check_allowance(usage, grant):
    used = usage.get("used_runner_minutes")
    require(type(used) is int and 0 <= used <= grant["shared_ceiling_minutes"] - JOB_RESERVATION,
            "Insufficient shared resource allowance")


def preflight(output):
    provenance = authenticate()
    phase(os.environ.get("COMMIT_MESSAGE", ""))
    grant = resource_grant()
    # Independent workflow groups may take a few seconds to finish skipped jobs.
    # Unknown or genuinely concurrent usage is never omitted from accounting.
    for attempt in range(4):
        try:
            usage = runner_usage()
            break
        except ValueError as error:
            if str(error) != "Concurrent usage unknown" or attempt == 3:
                raise
            time.sleep(3)
    check_allowance(usage, grant)
    write_json(Path(output) / "preflight.json", {**provenance, **usage,
        "resource_grant": grant, "phase": "tests", "scientific_search_authorized": False,
        "lambda_search_authorized": False})


def check_preflight(output):
    record = authenticate(runtime=True)
    phase(os.environ.get("COMMIT_MESSAGE", ""))
    grant = resource_grant()
    permit = read_json(Path(output) / "preflight.json")
    for field in ("protocol_id", "implementation_sha", "source_manifest", "run_id", "run_attempt"):
        require(permit.get(field) == record[field], "Stale or foreign preflight")
    require(permit.get("phase") == "tests" and permit.get("resource_grant") == grant and
            permit.get("scientific_search_authorized") is False and
            permit.get("lambda_search_authorized") is False, "Wrong tests-only permit")
    check_allowance(permit, grant)
    return record


def write_manifest(output):
    output = Path(output)
    write_json(output / "file_manifest.json", {"protocol_id": PROTOCOL,
        "files": [{"path": p.relative_to(output).as_posix(), **identity(p)}
                  for p in sorted(output.rglob("*")) if p.is_file() and p.name != "file_manifest.json"]})


def verify_manifest(output):
    root = Path(output).resolve()
    manifest = read_json(root / "file_manifest.json")
    require(manifest.get("protocol_id") == PROTOCOL, "Wrong artifact protocol")
    seen = set()
    for row in manifest["files"]:
        name = row["path"]
        relative = PurePosixPath(name)
        require(name and name not in seen and not relative.is_absolute() and ".." not in relative.parts and
                ":" not in name and "\\" not in name and name != "file_manifest.json", "Unsafe artifact member")
        path = root / relative
        require(path.resolve().is_relative_to(root) and not path.is_symlink() and
                identity(path) == {"bytes": row["bytes"], "sha256": row["sha256"]}, "Checksum mismatch")
        seen.add(name)
    require(seen | {"file_manifest.json"} ==
            {p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file()}, "Incomplete artifact")
    return manifest
