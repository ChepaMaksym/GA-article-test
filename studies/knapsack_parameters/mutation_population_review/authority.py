"""Bounded authority for a descriptive review, never for a GA search."""
from __future__ import annotations

from datetime import datetime
import hashlib
import importlib.metadata
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request

ROOT = Path(__file__).resolve().parents[3]
MODULE = Path(__file__).resolve().parent
REL = MODULE.relative_to(ROOT).as_posix()
PROTOCOL = "GA-KNAPSACK-MUTATION-POPULATION-REVIEW-V1"
REGISTRATION_SHA = "3de47c9ca4fc468fc521bdb470c1e2bf7667adb5"
PROTOCOL_HASH = "26340824eee666581bfc1f93f65584f04179044a81d9982867c7cf554429cb42"
REPOSITORY = "ChepaMaksym/GA-article-test"
BRANCH = "research/masters-ga-diversity-crossover"
WORKFLOW = ".github/workflows/knapsack-mutation-population-review.yml"
MARKER = "[mutation-population:review]"
SOURCE_SHA = "3e28c407db41a31d251e8063b31f67c83ecc606b"
SOURCE_RUN = 40205451045
SOURCE_MANIFEST_SHA = "9f76b21e4c139ec22491e5a752f38b4c5ca45f6262185d5a60cb62533ce4d22a"
SOURCE = ROOT / "studies/knapsack_parameters/parameter_dynamics/evidence/main-40205451045-1"
INPUT_HASHES = {
    "series_summary.json": "22e5703c370f2b78a916fdf9952608248317fbfd793aa7dd99eda3c430b4411d",
    "compact_records.json.gz": "d31cc14f897faca885ba0bd5295aa731cbb6e8b6954db9896d7708d9e6965fd8",
    "audit_status.json": "30d71edca326242f02fd9fce67d8e89d8877bec720a8279a8fb35e50cfe6805d",
}
ARTIFACT_ID = 12603474114
ZIP_SHA = "39f37adb2283370eaf6f77bde6f83562684d6aa0a1b824a796ae3817ba08ed79"


def require(ok, message):
    if not ok:
        raise ValueError("Mutation/population review: " + message)


def ci_only():
    require(os.environ.get("GITHUB_ACTIONS") == "true" and os.environ.get("GITHUB_REPOSITORY") == REPOSITORY and
            os.environ.get("GITHUB_REF") == "refs/heads/" + BRANCH,
            "scientific processing is restricted to the registered CI branch")


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def read(path):
    return json.loads(Path(path).read_bytes())


def write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(canonical(value) + b"\n")


def api(endpoint):
    token = os.environ.get("GITHUB_TOKEN")
    require(bool(token), "Actions read token is required")
    request = urllib.request.Request("https://api.github.com/repos/" + REPOSITORY + endpoint,
        headers={"Authorization": "Bearer " + token, "Accept": "application/vnd.github+json",
                 "User-Agent": "mutation-population-secondary-review", "X-GitHub-Api-Version": "2022-11-28"})
    with urllib.request.urlopen(request, timeout=60) as response:
        return json.load(response)


def pages(endpoint, key):
    sep = "&" if "?" in endpoint else "?"
    page = 1
    while True:
        values = api(endpoint + sep + f"per_page=100&page={page}")[key]
        yield from values
        if len(values) < 100:
            break
        page += 1


def source_files():
    paths = sorted([*MODULE.glob("*.py"), *MODULE.glob("tests/*.py"), MODULE / "PROTOCOL_UK.md",
                    MODULE / "resource_authorization.json", ROOT / WORKFLOW])
    return [{"path": p.relative_to(ROOT).as_posix(), "sha256": sha(p.read_bytes())} for p in paths]


def runtime(packages=False):
    ci_only()
    require(subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip() == os.environ["GITHUB_SHA"],
            "checkout differs from exact execution SHA")
    subprocess.run(["git", "merge-base", "--is-ancestor", REGISTRATION_SHA, "HEAD"], cwd=ROOT, check=True)
    require(sha((MODULE / "PROTOCOL_UK.md").read_bytes()) == PROTOCOL_HASH, "registered protocol changed")
    for path, digest in INPUT_HASHES.items():
        require(sha((SOURCE / path).read_bytes()) == digest, "changed historical input " + path)
    audit = read(SOURCE / "audit_status.json")
    require(audit["complete"] and not audit["errors"] and audit["verified_runs"] == 28800 and
            audit["implementation_sha"] == SOURCE_SHA and audit["run_id"] == SOURCE_RUN and audit["run_attempt"] == 1 and
            audit["source_manifest"]["sha256"] == SOURCE_MANIFEST_SHA, "historical audit identity")
    for row in audit["source_manifest"]["files"]:
        require(sha((ROOT / row["path"]).read_bytes()) == row["sha256"], "historical protected source changed")
    environment = None
    if packages:
        require(sys.version.split()[0] == "3.12.14", "unexpected Python version")
        lock = read(ROOT / "studies/knapsack_parameters/ga_study/dependencies/environment.lock.json")
        installed = {row["name"]: importlib.metadata.version(row["name"]) for row in lock["packages"]}
        require(all(installed[row["name"]] == row["version"] for row in lock["packages"]), "unexpected dependency version")
        environment = {"python": sys.version.split()[0], "packages": installed}
    return {"protocol": PROTOCOL, "registration_sha": REGISTRATION_SHA, "implementation_sha": os.environ["GITHUB_SHA"],
            "run_id": int(os.environ["GITHUB_RUN_ID"]), "run_attempt": int(os.environ.get("GITHUB_RUN_ATTEMPT", "1")),
            "files": source_files(), "environment": environment}


def cumulative_usage():
    current = (int(os.environ["GITHUB_RUN_ID"]), int(os.environ.get("GITHUB_RUN_ATTEMPT", "1")))
    endpoint = "/actions/workflows/" + Path(WORKFLOW).name + "/runs?branch=" + urllib.parse.quote(BRANCH, safe="")
    jobs, seen = [], set()
    for run in pages(endpoint, "workflow_runs"):
        for attempt in range(1, run["run_attempt"] + 1):
            if (run["id"], attempt) == current:
                continue
            allocated = [j for j in pages(f"/actions/runs/{run['id']}/attempts/{attempt}/jobs", "jobs")
                         if j.get("conclusion") != "skipped"]
            for job in allocated:
                require(job["id"] not in seen and job.get("started_at") and job.get("completed_at"),
                        "unknown or duplicate prior resource usage")
                seen.add(job["id"])
                seconds = (datetime.fromisoformat(job["completed_at"].replace("Z", "+00:00")) -
                           datetime.fromisoformat(job["started_at"].replace("Z", "+00:00"))).total_seconds()
                require(seconds >= 0, "negative job duration")
                jobs.append({"run_id": run["id"], "attempt": attempt, "job_id": job["id"],
                             "runner_minutes": max(1, math.ceil(seconds / 60))})
    return {"jobs": jobs, "used_runner_minutes": sum(j["runner_minutes"] for j in jobs)}


def preflight(output):
    receipt = runtime()
    message = os.environ.get("COMMIT_MESSAGE", "")
    require(message.count(MARKER) == 1 and message.count("[") == 1 and message.count("]") == 1, "mixed/unregistered phase")
    grant = read(MODULE / "resource_authorization.json")
    require(grant.get("explicit_user_approval") is True and grant.get("runner_minutes_ceiling") == 20 and
            grant.get("new_ga_search_authorized") is False, "separate resource approval is required")
    usage = cumulative_usage()
    require(usage["used_runner_minutes"] + 13 <= 20, "insufficient cumulative budget for bounded attempt")
    write(Path(output) / "permit.json", {**receipt, "usage_before_attempt": usage, "reserved_runner_minutes": 13,
                                        "ceiling_runner_minutes": 20, "new_ga_search_authorized": False})


def validate_permit(path):
    permit = read(Path(path) / "permit.json")
    current = runtime(packages=True)
    for key in ("protocol", "registration_sha", "implementation_sha", "run_id", "run_attempt", "files"):
        require(current[key] == permit[key], "foreign or stale exact-source permit")
    return current, permit


def download_archive(destination):
    meta = api(f"/actions/artifacts/{ARTIFACT_ID}")
    require(meta["id"] == ARTIFACT_ID and not meta["expired"] and meta["workflow_run"]["id"] == SOURCE_RUN and
            meta["workflow_run"]["head_sha"] == SOURCE_SHA, "wrong/unavailable historical worker artifact")
    token = os.environ["GITHUB_TOKEN"]
    request = urllib.request.Request("https://api.github.com/repos/" + REPOSITORY + f"/actions/artifacts/{ARTIFACT_ID}/zip",
        headers={"Authorization": "Bearer " + token, "Accept": "application/vnd.github+json", "User-Agent": "secondary-review"})
    # The Actions token belongs only to api.github.com. Do not forward it to
    # the storage host named by GitHub's temporary signed redirect.
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, newurl):
            return None

    try:
        urllib.request.build_opener(NoRedirect).open(request, timeout=60)
    except urllib.error.HTTPError as error:
        require(error.code == 302, "artifact download did not return the expected redirect")
        location = error.headers.get("Location", "")
    else:
        raise ValueError("Artifact endpoint unexpectedly omitted its storage redirect")
    parsed = urllib.parse.urlsplit(location)
    require(parsed.scheme == "https" and bool(parsed.hostname) and parsed.username is None,
            "invalid artifact storage redirect")
    storage_request = urllib.request.Request(location, headers={"User-Agent": "secondary-review"})
    with urllib.request.urlopen(storage_request, timeout=90) as response, Path(destination).open("wb") as stream:
        while block := response.read(1024 * 1024):
            stream.write(block)
            require(stream.tell() <= 256 * 1024 * 1024, "worker ZIP exceeds declared bound")
    require(sha(Path(destination).read_bytes()) == ZIP_SHA, "worker ZIP checksum mismatch")
    return {key: meta.get(key) for key in ("id", "name", "size_in_bytes", "created_at", "expires_at", "digest")}
