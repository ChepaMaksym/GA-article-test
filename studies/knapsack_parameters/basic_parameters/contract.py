"""Separate fail-closed CI authority; historical study contracts are untouched."""
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
import tempfile
import urllib.parse
import urllib.request

ROOT = Path(__file__).resolve().parents[3]
MODULE = Path(__file__).resolve().parent
REL = "studies/knapsack_parameters/basic_parameters/"
PROTOCOL = "GA-KNAPSACK-BASIC-PARAMETERS-V1"
REGISTRATION_SHA = "b2a2b444bb9a316efd17b192821e333b975313b1"
BRANCH = "research/masters-ga-diversity-crossover"
REPOSITORY = "ChepaMaksym/GA-article-test"
WORKFLOW = ".github/workflows/knapsack-basic-parameters.yml"
# Reserve entire phase, including the current gate and every possible matrix job.
RESERVATIONS = {"tests": 8, "prepare": 6, "pilot": 31, "audit": 12,
                "certify": 17, "main": 607}


def require(ok, message):
    if not ok:
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
    files = list(MODULE.rglob("*.py"))
    files += [MODULE / p for p in ("PROTOCOL_UK.md", "registration.json", "environment.json",
                                   "source_gate.json", "SOURCE_AUDIT_UK.md")]
    files += [ROOT / WORKFLOW, ROOT / "studies/knapsack_parameters/ga_study/dependencies/requirements.lock"]
    # Bind all reused pure implementations, not their historical CLI authority.
    for directory in ("ga_study", "feasibility"):
        files += list((ROOT / "studies/knapsack_parameters" / directory).glob("*.py"))
    rows = [{"path": p.relative_to(ROOT).as_posix(), **identity(p)} for p in sorted(set(files))]
    return {"files": rows, "sha256": hashlib.sha256(canonical(rows)).hexdigest()}


def manifest(directory):
    directory = Path(directory)
    rows = [{"path": p.relative_to(directory).as_posix(), **identity(p)}
            for p in sorted(directory.rglob("*")) if p.is_file() and p.name != "file_manifest.json"]
    write_json(directory / "file_manifest.json", {"protocol_id": PROTOCOL, "excludes_self": True, "files": rows})


def verify_manifest(directory):
    directory = Path(directory).resolve()
    value = read_json(directory / "file_manifest.json")
    require(value["protocol_id"] == PROTOCOL and value["excludes_self"] is True, "Wrong manifest authority")
    names = set()
    for row in value["files"]:
        name = row["path"]
        rel = PurePosixPath(name)
        require(not rel.is_absolute() and ".." not in rel.parts and ":" not in name and
                "\\" not in name and name not in names and name != "file_manifest.json", "Unsafe inventory")
        member = directory / rel
        require(member.resolve().is_relative_to(directory) and not member.is_symlink() and
                identity(member) == {"bytes": row["bytes"], "sha256": row["sha256"]}, "Member hash mismatch")
        names.add(name)
    require(names | {"file_manifest.json"} == {p.relative_to(directory).as_posix()
            for p in directory.rglob("*") if p.is_file()}, "Missing or extra evidence")
    return value


def phase(message):
    markers = re.findall(r"\[([a-z-]+):([^\]]+)\]", message)
    require(len(markers) == 1 and markers[0][0] == "basic-parameters" and
            markers[0][1] in RESERVATIONS, "Unknown or mixed phase markers")
    return markers[0][1]


def authenticate(runtime=False):
    require(os.environ.get("GITHUB_ACTIONS") == "true", "CI-only science")
    require(os.environ.get("GITHUB_REPOSITORY") == REPOSITORY and
            os.environ.get("GITHUB_REF") == "refs/heads/" + BRANCH, "Wrong branch/repository")
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    require(head == os.environ.get("GITHUB_SHA") == os.environ.get("EXPECTED_SHA"), "Checkout SHA mismatch")
    subprocess.run(["git", "merge-base", "--is-ancestor", REGISTRATION_SHA, head], cwd=ROOT, check=True)
    for name in ("PROTOCOL_UK.md", "registration.json"):
        frozen = subprocess.check_output(["git", "show", REGISTRATION_SHA + ":" + REL + name], cwd=ROOT)
        require(frozen == (MODULE / name).read_bytes(), "Preregistration changed")
    changes = subprocess.check_output(["git", "diff", "--name-only", REGISTRATION_SHA, head], cwd=ROOT, text=True).splitlines()
    require(all(p.startswith(REL) or p in {WORKFLOW, "README.md"} for p in changes), "Historical files modified")
    registration = read_json(MODULE / "registration.json")
    require(identity(ROOT / registration["requirements_path"])["sha256"] == registration["requirements_sha256"], "Lock changed")
    require(identity(ROOT / "studies/knapsack_parameters/ga_study/engine.py")["sha256"] ==
            registration["protected_engine_sha256"], "Frozen engine changed")
    require(not subprocess.check_output(["git", "status", "--porcelain", "--untracked-files=all"], cwd=ROOT).strip(), "Dirty checkout")
    result = {"protocol_id": PROTOCOL, "implementation_sha": head,
              "run_id": int(os.environ["GITHUB_RUN_ID"]),
              "run_attempt": int(os.environ.get("GITHUB_RUN_ATTEMPT", "1")),
              "source_manifest": source_manifest()}
    if runtime:
        require(platform.python_version() == "3.12.14" and platform.python_implementation() == "CPython", "Wrong Python")
        lock = read_json(ROOT / "studies/knapsack_parameters/ga_study/dependencies/environment.lock.json")
        versions = {p["name"]: importlib.metadata.version(p["name"]) for p in lock["packages"]}
        require(all(versions[p["name"]] == p["version"] for p in lock["packages"]), "Dependency version mismatch")
        result["environment"] = {"python": platform.python_version(), "packages": versions}
    return result


def api(path):
    token = os.environ.get("GITHUB_TOKEN")
    require(bool(token), "API token absent")
    request = urllib.request.Request("https://api.github.com/repos/" + REPOSITORY + path,
        headers={"Authorization": "Bearer " + token, "Accept": "application/vnd.github+json",
                 "User-Agent": "basic-parameters-budget", "X-GitHub-Api-Version": "2022-11-28"})
    with urllib.request.urlopen(request, timeout=25) as response:
        return json.load(response)


def pages(path, field):
    separator = "&" if "?" in path else "?"
    rows, number = [], 1
    while True:
        result = api(path + separator + f"per_page=100&page={number}")
        batch = result[field]
        rows.extend(batch)
        if len(batch) < 100:
            require(len(rows) == result.get("total_count", len(rows)), "Incomplete API pagination")
            return rows
        number += 1


def runner_usage():
    own = "/actions/workflows/" + Path(WORKFLOW).name + "/runs?branch=" + urllib.parse.quote(BRANCH, safe="")
    current, now = int(os.environ["GITHUB_RUN_ID"]), int(os.environ.get("GITHUB_RUN_ATTEMPT", "1"))
    rows = []
    for run in pages(own, "workflow_runs"):
        for attempt in range(1, run["run_attempt"] + 1):
            if run["id"] == current and attempt == now:
                continue  # entire current phase reserved by its single gate job
            require(run["id"] == current or run["status"] == "completed", "Concurrent study run")
            selected = None
            if run.get("head_commit"):
                try:
                    selected = phase(run["head_commit"]["message"])
                except ValueError:
                    pass
            for job in pages(f"/actions/runs/{run['id']}/attempts/{attempt}/jobs", "jobs"):
                if job.get("conclusion") == "skipped":
                    continue
                require(job.get("started_at") and job.get("completed_at"), "Unknown usage")
                seconds = (datetime.fromisoformat(job["completed_at"].replace("Z", "+00:00")) -
                           datetime.fromisoformat(job["started_at"].replace("Z", "+00:00"))).total_seconds()
                require(seconds >= 0, "Invalid duration")
                rows.append({"run_id": run["id"], "attempt": attempt, "job_id": job["id"],
                             "minutes": max(1, math.ceil(seconds / 60)), "phase": selected})
    require(len({r["job_id"] for r in rows}) == len(rows), "Duplicated job usage")
    require(all(r["phase"] in RESERVATIONS for r in rows), "Unclassified study resource usage")
    return {"used_runner_minutes": sum(r["minutes"] for r in rows),
            "technical_runner_minutes": sum(r["minutes"] for r in rows if r["phase"] != "main"), "jobs": rows}


def validate_tests():
    receipt = read_json(MODULE / "validated_tests.json")
    require(receipt["protocol_id"] == PROTOCOL and receipt["success"] is True and
            receipt["source_manifest_sha256"] == source_manifest()["sha256"], "No green tests for current sources")
    run = api(f"/actions/runs/{receipt['run_id']}")
    require(run["conclusion"] == "success" and run["head_sha"] == receipt["implementation_sha"] and
            run["run_attempt"] == receipt["run_attempt"] and run["event"] == "push" and
            run["head_branch"] == BRANCH and run["path"] == WORKFLOW and
            phase(run["head_commit"]["message"]) == "tests", "Test CI receipt mismatch")
    descriptor = api(f"/actions/artifacts/{receipt['artifact_id']}")
    require(descriptor["name"] == f"basic-full-tests-single-{receipt['run_id']}-{receipt['run_attempt']}" and
            descriptor["digest"] == "sha256:" + receipt["artifact_zip_sha256"] and
            descriptor["size_in_bytes"] == receipt["artifact_bytes"] and
            descriptor["workflow_run"]["id"] == receipt["run_id"], "Test artifact provenance mismatch")
    actual = artifact_document(descriptor, "tests.json")
    require(actual["success"] is True and actual["failures"] == actual["errors"] == actual["skipped"] == 0 and
            actual["tests_run"] >= 20 and actual["implementation_sha"] == receipt["implementation_sha"] and
            actual["run_id"] == receipt["run_id"] and actual["run_attempt"] == receipt["run_attempt"] and
            actual["source_manifest"]["sha256"] == source_manifest()["sha256"], "Original test document mismatch")
    return receipt


def artifact_document(descriptor, name):
    # Lazy import avoids scientific dependencies in the stdlib-only gate.
    from .driver import download_artifact
    with tempfile.TemporaryDirectory() as temporary:
        target = Path(temporary) / "original"
        download_artifact(descriptor, target)
        return read_json(target / name)


def require_current_gate(provenance, selected):
    """Rerun-failed-jobs cannot reuse a previous attempt's reservation."""
    run, attempt = provenance["run_id"], provenance["run_attempt"]
    descriptors = pages(f"/actions/runs/{run}/artifacts", "artifacts")
    matches = [a for a in descriptors if a["name"] == f"basic-gate-{run}-{attempt}"]
    require(len(matches) == 1, "Fresh current-attempt budget gate is absent; rerun the whole workflow")
    gate = artifact_document(matches[0], "preflight.json")
    require(gate["implementation_sha"] == provenance["implementation_sha"] and
            gate["source_manifest"] == provenance["source_manifest"] and
            gate["run_id"] == run and gate["run_attempt"] == attempt and
            gate["phase"] == selected and gate["reserved_runner_minutes"] == RESERVATIONS[selected],
            "Budget gate SHA/attempt/phase mismatch")
    require(gate["used_runner_minutes"] + gate["reserved_runner_minutes"] <= 900 and
            (selected == "main" or gate["technical_runner_minutes"] + gate["reserved_runner_minutes"] <= 60),
            "Current gate has insufficient resources")
    return gate


def preflight(output):
    provenance = authenticate()
    selected = phase(os.environ.get("COMMIT_MESSAGE", ""))
    usage = runner_usage()
    reserve = RESERVATIONS[selected]
    require(usage["used_runner_minutes"] + reserve <= 900, "Total budget unavailable")
    if selected != "main":
        require(usage["technical_runner_minutes"] + reserve <= 60, "Technical budget unavailable")
    if selected != "tests":
        validate_tests()
    if selected == "main":
        receipt = read_json(MODULE / "pilot_receipt.json")
        require(receipt["source_manifest_sha256"] == source_manifest()["sha256"] and
                receipt["completed_runs"] == 27 and receipt["independent_mismatches"] == 0 and
                receipt["projected_total_minutes"] + usage["used_runner_minutes"] <= 900 and
                receipt["projected_journal_bytes"] <= 40 * 1024**3, "Pilot does not admit main series")
        pilot_run = api(f"/actions/runs/{receipt['run_id']}")
        require(pilot_run["conclusion"] == "success" and pilot_run["head_sha"] == receipt["implementation_sha"], "Pilot source run mismatch")
    write_json(Path(output) / "preflight.json", {**provenance, **usage, "phase": selected,
                                               "reserved_runner_minutes": reserve})
    return selected
