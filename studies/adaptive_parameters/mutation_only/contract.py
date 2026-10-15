"""Independent authority for the own mutation heuristic; no old gate is relaxed."""
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
REL = "studies/adaptive_parameters/mutation_only/"
WORKFLOW = ".github/workflows/adaptive-mutation-only.yml"
REGISTRATION_SHA = "23014ffd96cc479ce6e90f237a62fc88f76f38b8"
BASE_SHA = "9c0c6405ff9ce05436e01eaf936f0d68c683a7cc"
REPOSITORY = "ChepaMaksym/GA-article-test"
BRANCH = "research/masters-ga-diversity-crossover"
PROTOCOL = "GA-ADAPTIVE-MUTATION-ONLY-TECHNICAL-V1"
TIMEOUTS = {"tests": 2, "prepare": 3, "pilot": 10}


def require(ok, message):
    if not ok:
        raise ValueError(message)


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
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
    files = list(MODULE.glob("*.py")) + [MODULE / p for p in
        ("PROTOCOL_UK.md", "registration.json", "environment.json", "pilot_approval.json")]
    files += [ROOT / WORKFLOW, ROOT / read_json(MODULE / "registration.json")["requirements_path"]]
    rows = [{"path": p.relative_to(ROOT).as_posix(), **identity(p)} for p in sorted(files)]
    return {"files": rows, "sha256": hashlib.sha256(canonical(rows)).hexdigest()}


def write_manifest(directory):
    directory = Path(directory)
    rows = [{"path": p.relative_to(directory).as_posix(), **identity(p)}
            for p in sorted(directory.rglob("*"))
            if p.is_file() and p.name != "file_manifest.json"]
    write_json(directory / "file_manifest.json", {
        "protocol_id": PROTOCOL, "excludes_self": True, "files": rows})


def verify_manifest(directory):
    directory = Path(directory).resolve()
    manifest = read_json(directory / "file_manifest.json")
    require(manifest.get("protocol_id") == PROTOCOL and manifest.get("excludes_self") is True,
            "Wrong artifact manifest")
    seen = set()
    for row in manifest["files"]:
        name = row["path"]
        rel = PurePosixPath(name)
        require(not rel.is_absolute() and ".." not in rel.parts and ":" not in name and
                "\\" not in name and name not in seen and name != "file_manifest.json",
                "Unsafe or duplicate manifest member")
        path = directory / rel
        require(path.resolve().is_relative_to(directory) and not path.is_symlink() and
                identity(path) == {"bytes": row["bytes"], "sha256": row["sha256"]},
                "Artifact checksum mismatch")
        seen.add(name)
    require(seen | {"file_manifest.json"} ==
            {p.relative_to(directory).as_posix() for p in directory.rglob("*") if p.is_file()},
            "Missing or extra artifact member")
    return manifest


def phase(message):
    markers = re.findall(r"\[([a-z-]+):([^\]]+)\]", message)
    require(len(markers) == 1 and markers[0][0] == "adaptive-mutation" and
            markers[0][1] in TIMEOUTS, "Missing, unknown or mixed phase marker")
    return markers[0][1]


def authenticate(runtime=False):
    require(os.environ.get("GITHUB_ACTIONS") == "true", "CI-only scientific execution")
    require(os.environ.get("GITHUB_REPOSITORY") == REPOSITORY and
            os.environ.get("GITHUB_REF") == "refs/heads/" + BRANCH, "Wrong repository or branch")
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    require(head == os.environ.get("GITHUB_SHA") == os.environ.get("EXPECTED_SHA"), "Wrong checkout SHA")
    subprocess.run(["git", "merge-base", "--is-ancestor", REGISTRATION_SHA, head], cwd=ROOT, check=True)
    for name in ("PROTOCOL_UK.md", "registration.json"):
        original = subprocess.check_output(["git", "show", REGISTRATION_SHA + ":" + REL + name], cwd=ROOT)
        require(original == (MODULE / name).read_bytes(), "Preregistered contract changed")
    changed = subprocess.check_output(["git", "diff", "--name-only", BASE_SHA, head], cwd=ROOT, text=True).splitlines()
    require(all(p.startswith(REL) or p == WORKFLOW for p in changed), "Historical files changed")
    registration = read_json(MODULE / "registration.json")
    for path, digest in registration["input_sha256"].items():
        require(identity(ROOT / path)["sha256"] == digest, "Input checksum mismatch: " + path)
    require(identity(ROOT / registration["requirements_path"])["sha256"] ==
            registration["requirements_sha256"], "Dependency lock changed")
    require(identity(ROOT / "studies/knapsack_parameters/ga_study/engine.py")["sha256"] ==
            registration["protected_engine_sha256"], "Historical engine changed")
    result = {"protocol_id": PROTOCOL, "registration_sha": REGISTRATION_SHA,
              "implementation_sha": head, "run_id": int(os.environ["GITHUB_RUN_ID"]),
              "run_attempt": int(os.environ.get("GITHUB_RUN_ATTEMPT", "1")),
              "source_manifest": source_manifest()}
    if runtime:
        require(platform.python_version() == "3.12.14" and
                platform.python_implementation() == "CPython", "Wrong runtime")
        inherited = read_json(ROOT / "studies/knapsack_parameters/ga_study/dependencies/environment.lock.json")
        versions = {p["name"]: importlib.metadata.version(p["name"]) for p in inherited["packages"]}
        require(all(versions[p["name"]] == p["version"] for p in inherited["packages"]), "Wrong dependency versions")
        result["environment"] = {"python": platform.python_version(), "versions": versions,
                                 "new_environment_record": identity(MODULE / "environment.json")}
    return result


def api(path):
    token = os.environ.get("GITHUB_TOKEN")
    require(bool(token), "Token required for resource audit")
    request = urllib.request.Request("https://api.github.com/repos/" + REPOSITORY + path,
        headers={"Authorization": "Bearer " + token, "Accept": "application/vnd.github+json",
                 "User-Agent": "mutation-only-resource-audit", "X-GitHub-Api-Version": "2022-11-28"})
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
    """Every attempt of this workflow since registration, individually rounded."""
    own = f"/actions/workflows/{Path(WORKFLOW).name}/runs?branch=" + urllib.parse.quote(BRANCH, safe="")
    current = int(os.environ["GITHUB_RUN_ID"])
    attempt_now = int(os.environ.get("GITHUB_RUN_ATTEMPT", "1"))
    rows = []
    for run in pages(own, "workflow_runs"):
        for attempt in range(1, run["run_attempt"] + 1):
            if run["id"] == current and attempt == attempt_now:
                continue
            require(run["id"] == current or run["status"] == "completed", "Concurrent mutation workflow")
            for job in pages(f"/actions/runs/{run['id']}/attempts/{attempt}/jobs", "jobs"):
                if job.get("conclusion") == "skipped":
                    continue
                require(job.get("started_at") and job.get("completed_at"), "Unknown runner usage")
                seconds = (datetime.fromisoformat(job["completed_at"].replace("Z", "+00:00")) -
                           datetime.fromisoformat(job["started_at"].replace("Z", "+00:00"))).total_seconds()
                require(seconds >= 0, "Negative runner duration")
                rows.append({"run_id": run["id"], "attempt": attempt, "job_id": job["id"],
                             "minutes": max(1, math.ceil(seconds / 60)), "conclusion": job["conclusion"]})
    require(len({r["job_id"] for r in rows}) == len(rows), "Duplicate runner job")
    return {"used_runner_minutes": sum(r["minutes"] for r in rows), "prior_jobs": rows}


def preflight(output):
    provenance = authenticate()
    selected = phase(os.environ.get("COMMIT_MESSAGE", ""))
    approved = False
    if (MODULE / "pilot_approval.json").exists():
        approval = read_json(MODULE / "pilot_approval.json")
        approved = (approval.get("protocol_id") == PROTOCOL and approval.get("approved") is True and
                    approval.get("runner_minutes") == 20 and approval.get("approved_runs") == 16)
    if selected != "tests":
        require(approved, "Separate user approval missing")
    usage = runner_usage()
    reserve = TIMEOUTS[selected]
    # Without pilot approval, tests alone must stay inside a single 4-minute allowance.
    ceiling = 20 if approved else 4
    require(usage["used_runner_minutes"] + reserve <= ceiling, "Insufficient cumulative resource allowance")
    write_json(Path(output) / "preflight.json", {**provenance, **usage,
        "phase": selected, "reserved_runner_minutes": reserve, "ceiling": ceiling})
    return selected
