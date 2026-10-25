"""Fail-closed authority, immutable registration and cumulative CI accounting.

Standard-library only: the gate runs before third-party packages are installed.
No search, tests, preparation or statistics are dispatched on import.
"""
from __future__ import annotations

from datetime import datetime
import hashlib
import importlib.metadata
import json
import math
import os
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request

ROOT = Path(__file__).resolve().parents[3]
MODULE = Path(__file__).resolve().parent
REL = "studies/knapsack_parameters/parameter_dynamics/"
PROTOCOL = "GA-KNAPSACK-PARAMETER-DYNAMICS-V1"
REGISTRATION_SHA = "8ac7d65a3268b9ccda75d1ac5a2c34db5a7621c5"
BRANCH = "research/masters-ga-diversity-crossover"
REPOSITORY = "ChepaMaksym/GA-article-test"
WORKFLOW = ".github/workflows/knapsack-parameter-dynamics.yml"
PROFILES = METHODS = tuple(range(32))
PILOT_TASKS = ("UC-s000", "WC-s001", "SC-s005", "SC-s000")
MAIN_WORKERS = tuple(f"s{i:03d}-b{block}" for i in range(20, 30) for block in range(5))
PHASES = ("tests", "prepare-pilot", "pilot", "prepare-main", "main")
TECH_RESERVATIONS = {"tests": 13, "prepare-pilot": 8, "pilot": 99}
TECH_TIMEOUTS = {"gate": 1, "tests": 10, "prepare": 5, "worker": 20, "aggregate": 10}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False).encode("utf-8")


def read_json(path):
    return json.loads(Path(path).read_bytes())


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(canonical(value) + b"\n")


def identity(path):
    raw = Path(path).read_bytes()
    return {"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def safe_child(directory, relative):
    require(type(relative) is str, "Evidence path must be a string")
    rel = PurePosixPath(relative)
    require(type(relative) is str and not rel.is_absolute() and bool(rel.parts) and
            ".." not in rel.parts and ":" not in relative and "\\" not in relative,
            "Unsafe relative evidence path")
    target = Path(directory).joinpath(*rel.parts)
    require(target.resolve().is_relative_to(Path(directory).resolve()), "Escaping evidence path")
    return target


def write_manifest(directory):
    directory = Path(directory)
    entries = [{"path": path.relative_to(directory).as_posix(), **identity(path)}
               for path in sorted(directory.rglob("*")) if path.is_file() and
               path != directory / "file_manifest.json"]
    write_json(directory / "file_manifest.json", {"schema": "parameter-dynamics-file-manifest-v1", "files": entries})


def verify_manifest(directory):
    directory = Path(directory)
    manifest = read_json(directory / "file_manifest.json")
    require(manifest.get("schema") == "parameter-dynamics-file-manifest-v1", "Unknown evidence manifest")
    seen = set()
    for row in manifest["files"]:
        require(row["path"] not in seen and row["path"] != "file_manifest.json", "Duplicate/self manifest entry")
        seen.add(row["path"])
        require(identity(safe_child(directory, row["path"])) == {"bytes": row["bytes"], "sha256": row["sha256"]},
                "Evidence bytes do not match manifest: " + row["path"])
    actual = {p.relative_to(directory).as_posix() for p in directory.rglob("*") if p.is_file() and
              p != directory / "file_manifest.json"}
    require(actual == seen, "Incomplete or extra evidence files")
    return manifest


def phase(message):
    markers = re.findall(r"\[([^\[\]\r\n]+)\]", message)
    require(len(markers) == 1 and markers[0].startswith("parameter-dynamics:"), "Exactly one registered phase marker required")
    selected = markers[0].split(":", 1)[1]
    require(selected in PHASES, "Unregistered parameter-dynamics phase")
    return selected


def scope(selected):
    require(selected in PHASES, "Unregistered phase")
    return "main" if selected in ("prepare-main", "main") else "technical"


def source_manifest():
    registration = read_json(MODULE / "registration.json")
    paths = sorted({*MODULE.glob("*.py"), *MODULE.glob("tests/*.py"),
                    *(MODULE / name for name in (*registration["immutable_documents"], "registration.json")),
                    ROOT / WORKFLOW,
                    *(ROOT / relative for relative in registration["historical_sources"]),
                    ROOT / "studies/knapsack_parameters/two_signal_mutation/registration.json"})
    entries = [{"path": p.relative_to(ROOT).as_posix(), **identity(p)} for p in paths]
    return {"files": entries, "sha256": hashlib.sha256(canonical(entries)).hexdigest()}


def authenticate(runtime=False):
    require(os.environ.get("GITHUB_ACTIONS") == "true", "Execution is GitHub-Actions only")
    require(os.environ.get("GITHUB_REPOSITORY") == REPOSITORY, "Wrong repository")
    require(os.environ.get("GITHUB_REF") == "refs/heads/" + BRANCH, "Wrong branch")
    sha = os.environ.get("GITHUB_SHA", "")
    require(bool(re.fullmatch(r"[0-9a-f]{40}", sha)) and os.environ.get("EXPECTED_SHA") == sha,
            "Exact expected SHA required")
    require(subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip() == sha,
            "Checkout differs from execution SHA")
    require(not subprocess.check_output(["git", "status", "--porcelain", "--untracked-files=no"], cwd=ROOT),
            "Tracked source changed during execution")
    subprocess.run(["git", "merge-base", "--is-ancestor", REGISTRATION_SHA, sha], cwd=ROOT, check=True)
    for name in ("PROTOCOL_UK.md", "protocol.json", "registration.json", "environment.json", "ADMISSION_UK.md"):
        frozen = subprocess.check_output(["git", "show", REGISTRATION_SHA + ":" + REL + name], cwd=ROOT)
        require(frozen == (MODULE / name).read_bytes(), "Registered document changed: " + name)
    registration = read_json(MODULE / "registration.json")
    for relative, expected in registration["immutable_documents"].items():
        require(identity(MODULE / relative)["sha256"] == expected, "Registered document digest differs")
    for relative, expected in registration["historical_sources"].items():
        require(identity(ROOT / relative)["sha256"] == expected, "Frozen historical source changed: " + relative)
    environment = None
    if runtime:
        env = read_json(MODULE / "environment.json")
        require(sys.version.split()[0] == env["python"], "Unexpected Python patch version")
        require(identity(ROOT / env["requirements_lock_path"])["sha256"] == env["requirements_lock_sha256"] and
                identity(ROOT / env["environment_lock_path"])["sha256"] == env["environment_lock_sha256"],
                "Dependency lock changed")
        lock = read_json(ROOT / env["environment_lock_path"])
        packages = {row["name"]: importlib.metadata.version(row["name"]) for row in lock["packages"]}
        require(all(packages[row["name"]] == row["version"] for row in lock["packages"]), "Unexpected installed package")
        environment = {"python": sys.version.split()[0], "packages": packages}
    return {"protocol_id": PROTOCOL, "registration_sha": REGISTRATION_SHA, "implementation_sha": sha,
            "source_manifest": source_manifest(), "run_id": int(os.environ["GITHUB_RUN_ID"]),
            "run_attempt": int(os.environ.get("GITHUB_RUN_ATTEMPT", "1")), "environment": environment}


def grant_for(selected):
    grant = read_json(MODULE / "resource_authorization.json")
    require(grant.get("protocol_id") == PROTOCOL, "Wrong resource protocol")
    selected_scope = scope(selected)
    details = grant.get(selected_scope, {})
    require(details.get("explicit_user_approval") is True, "BLOCKED_SEPARATE_RESOURCE_APPROVAL_REQUIRED")
    require(type(details.get("runner_minutes_ceiling")) is int and details["runner_minutes_ceiling"] > 0,
            "Missing bounded resource ceiling")
    if selected_scope == "technical":
        require(details.get("runner_minutes_ceiling") == 120 and details.get("allowed_phases") == list(TECH_RESERVATIONS) and
                details.get("phase_reservations") == TECH_RESERVATIONS and details.get("job_timeouts") == TECH_TIMEOUTS and
                details.get("main_search_authorized") is False and details.get("pilot_runs") == 256 and
                details.get("new_calls_per_run") == 5000, "Incompatible technical grant")
    else:
        require(details.get("main_search_authorized") is True and details.get("main_runs") == 28800 and
                details.get("new_calls_per_run") == 5000 and details.get("allowed_phases") == ["prepare-main", "main"],
                "BLOCKED_MAIN_COST_APPROVAL_REQUIRED")
        require(type(details.get("pilot_cost_receipt")) is dict and details["pilot_cost_receipt"].get("pilot_runs") == 256,
                "Missing measured complete pilot cost")
        total = details.get("maximum_compressed_journal_bytes_total")
        require(type(total) is int and total > 0, "Missing explicit total main journal ceiling")
        timeouts = details.get("job_timeouts", {})
        require(set(timeouts) == set(TECH_TIMEOUTS) and all(type(v) is int and 1 <= v <= 120 for v in timeouts.values()),
                "Invalid measured main timeouts")
        reservations = details.get("phase_reservations", {})
        require(reservations.get("prepare-main", 0) >= timeouts["gate"] + timeouts["prepare"] + 2 and
                reservations.get("main", 0) >= timeouts["gate"] + 1 + 50 * (timeouts["worker"] + 1) + timeouts["aggregate"] + 1,
                "Main reservation cannot cover maximum job timeouts")
    require(details.get("max_parallel") == 4 and details.get("maximum_compressed_bytes_per_worker") == 536870912,
            "Unexpected concurrency or journal cap")
    return details


def journal_allowance(selected, grant):
    """Reserve disjoint journal quotas across fifty main family/block workers."""
    limit = grant["maximum_compressed_bytes_per_worker"]
    if scope(selected) == "main":
        total = grant["maximum_compressed_journal_bytes_total"]
        require(type(total) is int and total > 0, "Invalid total journal ceiling")
        limit = min(limit, total // 50)
    return limit


def api(endpoint):
    token = os.environ.get("GITHUB_TOKEN")
    require(bool(token), "Read-only Actions token required")
    request = urllib.request.Request("https://api.github.com/repos/" + REPOSITORY + endpoint,
                                    headers={"Authorization": "Bearer " + token, "Accept": "application/vnd.github+json",
                                             "User-Agent": "parameter-dynamics-audit", "X-GitHub-Api-Version": "2022-11-28"})
    with urllib.request.urlopen(request, timeout=90) as response:
        return json.load(response)


def pages(endpoint, key):
    separator = "&" if "?" in endpoint else "?"
    page_number = 1
    while True:
        rows = api(endpoint + separator + f"per_page=100&page={page_number}")[key]
        yield from rows
        if len(rows) < 100:
            return
        page_number += 1


def runner_usage(selected):
    selected_scope = scope(selected)
    current = (int(os.environ["GITHUB_RUN_ID"]), int(os.environ.get("GITHUB_RUN_ATTEMPT", "1")))
    endpoint = "/actions/workflows/" + Path(WORKFLOW).name + "/runs?branch=" + urllib.parse.quote(BRANCH, safe="")
    jobs, seen_runs, seen_jobs = [], set(), set()
    for run in pages(endpoint, "workflow_runs"):
        require(run["id"] not in seen_runs, "Duplicate workflow run")
        seen_runs.add(run["id"])
        message = run.get("head_commit", {}).get("message", "")
        try:
            source_phase = phase(message)
        except ValueError:
            source_phase = None
        for attempt in range(1, run["run_attempt"] + 1):
            if (run["id"], attempt) == current:
                continue
            allocated = [job for job in pages(f"/actions/runs/{run['id']}/attempts/{attempt}/jobs", "jobs")
                         if job.get("conclusion") != "skipped"]
            if not allocated:
                continue
            require(source_phase is not None, "Unknown allocated workflow phase")
            if scope(source_phase) != selected_scope:
                continue
            require(run["id"] == current[0] or run["status"] == "completed", "Concurrent resource use unknown")
            for job in allocated:
                require(job["id"] not in seen_jobs and job.get("started_at") and job.get("completed_at"),
                        "Duplicate or incomplete allocated job duration")
                seen_jobs.add(job["id"])
                seconds = (datetime.fromisoformat(job["completed_at"].replace("Z", "+00:00")) -
                           datetime.fromisoformat(job["started_at"].replace("Z", "+00:00"))).total_seconds()
                require(seconds >= 0, "Negative job duration")
                jobs.append({"run_id": run["id"], "run_attempt": attempt, "job_id": job["id"], "phase": source_phase,
                             "name": job["name"], "conclusion": job["conclusion"],
                             "runner_minutes": max(1, math.ceil(seconds / 60))})
    return {"scope": selected_scope, "used_runner_minutes": sum(row["runner_minutes"] for row in jobs), "jobs": jobs}


def check_allowance(selected, usage, grant):
    used = usage.get("used_runner_minutes")
    reservation = grant["phase_reservations"].get(selected)
    require(type(used) is int and used >= 0 and type(reservation) is int and reservation > 0 and
            used + reservation <= grant["runner_minutes_ceiling"], "BLOCKED_INSUFFICIENT_CUMULATIVE_BUDGET")


def validate_source_receipt(receipt, expected_phase):
    require(receipt.get("protocol_id") == PROTOCOL and receipt.get("source_manifest") == source_manifest(),
            "Foreign or changed green source fingerprint")
    source_sha = receipt.get("implementation_sha", "")
    require(bool(re.fullmatch(r"[0-9a-f]{40}", source_sha)), "Invalid receipt SHA")
    subprocess.run(["git", "merge-base", "--is-ancestor", source_sha, os.environ["GITHUB_SHA"]], cwd=ROOT, check=True)
    run = api(f"/actions/runs/{receipt['run_id']}/attempts/{receipt['run_attempt']}")
    require(run.get("conclusion") == "success" and run.get("head_sha") == source_sha and
            run.get("head_branch") == BRANCH and run.get("path") == WORKFLOW and
            phase(run.get("head_commit", {}).get("message", "")) == expected_phase,
            "Source execution was not a successful exact phase")
    for row in source_manifest()["files"]:
        original = subprocess.check_output(["git", "show", source_sha + ":" + row["path"]], cwd=ROOT)
        require(hashlib.sha256(original).hexdigest() == row["sha256"], "Receipt source file changed")
    return run


def validated_tests():
    frozen = read_json(MODULE / "frozen_tests.json")
    require(frozen.get("frozen") is True, "Green tests not frozen")
    receipt_path = safe_child(MODULE, frozen["receipt_path"])
    require(receipt_path.is_relative_to(MODULE / "evidence") and identity(receipt_path) == frozen["receipt_identity"],
            "Wrong frozen tests receipt")
    verify_manifest(receipt_path.parent)
    receipt = read_json(receipt_path)
    require(receipt.get("tests_passed") is True and receipt.get("failures") == 0 and receipt.get("errors") == 0 and
            receipt.get("skipped") == 0 and receipt.get("scientific_search_performed") is False and
            type(receipt.get("tests_run")) is int and receipt["tests_run"] >= 1, "Tests were not fully green")
    validate_source_receipt(receipt, "tests")
    artifact = api(f"/actions/artifacts/{frozen['artifact_id']}")
    require(artifact.get("expired") is False and artifact.get("workflow_run", {}).get("id") == receipt["run_id"] and
            artifact.get("digest") == "sha256:" + frozen["zip_sha256"], "Green artifact unavailable or altered")
    return receipt


def validated_pilot(grant):
    """A main grant cannot turn an incomplete pilot into a measured success."""
    frozen = grant["pilot_cost_receipt"]
    path = safe_child(MODULE, frozen["receipt_path"])
    require(path.is_relative_to(MODULE / "evidence") and identity(path) == frozen["receipt_identity"],
            "Wrong retained complete pilot receipt")
    receipt = read_json(path)
    require(receipt.get("stage") == "pilot" and receipt.get("complete") is True and
            receipt.get("verified_runs") == receipt.get("expected_runs") == 256 and not receipt.get("errors"),
            "BLOCKED_INCOMPLETE_MEASURED_PILOT")
    validate_source_receipt(receipt, "pilot")
    artifact = api(f"/actions/artifacts/{frozen['artifact_id']}")
    require(artifact.get("expired") is False and artifact.get("workflow_run", {}).get("id") == receipt["run_id"] and
            artifact.get("digest") == "sha256:" + frozen["zip_sha256"], "Measured pilot artifact unavailable")
    return receipt


def preflight(selected, output):
    provenance = authenticate()
    require(phase(os.environ.get("COMMIT_MESSAGE", "")) == selected, "Wrong requested phase")
    grant = grant_for(selected)
    usage = runner_usage(selected)
    check_allowance(selected, usage, grant)
    if scope(selected) == "main":
        validated_pilot(grant)
    if selected != "tests":
        validated_tests()
    if selected in ("pilot", "main"):
        from .banks import load_frozen_banks
        load_frozen_banks("pilot" if selected == "pilot" else "main", check_scores=False)
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    permit = {**provenance, "phase": selected, "grant": grant, "usage": usage,
              "resource_authorization_identity": identity(MODULE / "resource_authorization.json"),
              "reserved_runner_minutes": grant["phase_reservations"][selected]}
    write_json(output / "permit.json", permit)
    write_manifest(output)
    github_output = os.environ.get("GITHUB_OUTPUT")
    if github_output:
        with open(github_output, "a", encoding="utf-8") as stream:
            stream.write("phase=" + selected + "\n")
            stream.write("worker_timeout=" + str(grant["job_timeouts"]["worker"]) + "\n")
            stream.write("aggregate_timeout=" + str(grant["job_timeouts"]["aggregate"]) + "\n")
            stream.write("prepare_timeout=" + str(grant["job_timeouts"]["prepare"]) + "\n")
            matrix = PILOT_TASKS if selected == "pilot" else MAIN_WORKERS if selected == "main" else ()
            stream.write("worker_matrix=" + json.dumps({"worker": list(matrix)}, separators=(",", ":")) + "\n")
    return permit


def check_permit(directory, selected):
    provenance = authenticate(runtime=True)
    require(phase(os.environ.get("COMMIT_MESSAGE", "")) == selected, "Wrong worker phase marker")
    verify_manifest(directory)
    permit = read_json(Path(directory) / "permit.json")
    for field in ("protocol_id", "registration_sha", "implementation_sha", "source_manifest", "run_id", "run_attempt"):
        require(permit.get(field) == provenance[field], "Stale permit: " + field)
    grant = grant_for(selected)
    require(permit.get("phase") == selected and permit.get("grant") == grant and
            permit.get("resource_authorization_identity") == identity(MODULE / "resource_authorization.json"),
            "Wrong resource permit")
    check_allowance(selected, permit["usage"], grant)
    return provenance
