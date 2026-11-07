"""Fresh CI authority and cumulative accounting for the population-size pilot.

No import starts a search, downloads inputs, or executes a scientific check.
The permit covers software tests, preparation or the registered technical pilot;
tuning and final validation deliberately have no authorized execution phase here.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
import math
import os
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys
import urllib.parse
import urllib.request

ROOT = Path(__file__).resolve().parents[3]
MODULE = Path(__file__).resolve().parent
PROTOCOL = "GA-KNAPSACK-POPULATION-SIZE-V1"
REPOSITORY = "ChepaMaksym/GA-article-test"
BRANCH = "research/masters-ga-diversity-crossover"
WORKFLOW = ".github/workflows/knapsack-population-size.yml"
PHASES = ("tests", "prepare-pilot", "pilot")
TIMEOUTS = {"gate": 1, "tests": 8, "prepare": 20, "worker": 8, "aggregate": 6}
RESERVATIONS = {"tests": 11, "prepare-pilot": 23, "pilot": 90}
BYTE_RESERVATIONS = {"tests": 16 * 1024**2, "prepare-pilot": 768 * 1024**2, "pilot": 3 * 1024**3}
MAX_WORKER_COMPRESSED_BYTES = (BYTE_RESERVATIONS["pilot"] - 16 * 1024**2) // 9
PILOT_WORKERS = tuple(range(9))
REQUIREMENTS = "studies/knapsack_parameters/ga_study/dependencies/requirements.lock"
ENVIRONMENT = "studies/knapsack_parameters/ga_study/dependencies/environment.lock.json"
LEGACY_FIXTURES = (
    "studies/knapsack_parameters/presentation_package/data/parameters/UC-s020.json",
    "studies/knapsack_parameters/presentation_package/tests/references/parameters/UC-s020-bank-97001-p00.json.gz",
)


def require(condition, message):
    if not condition:
        raise ValueError(message)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
                      allow_nan=False).encode("utf-8")


def read_json(path):
    return json.loads(Path(path).read_bytes())


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(canonical(value) + b"\n")


def identity(path):
    path = Path(path)
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return {"bytes": path.stat().st_size, "sha256": digest.hexdigest()}


def safe_child(directory, relative):
    require(type(relative) is str, "Evidence path must be text")
    rel = PurePosixPath(relative)
    require(bool(rel.parts) and not rel.is_absolute() and ".." not in rel.parts
            and ":" not in relative and "\\" not in relative, "Unsafe evidence path")
    root = Path(directory)
    target = root.joinpath(*rel.parts)
    require(target.resolve().is_relative_to(root.resolve()), "Evidence path escapes its root")
    require(not any(candidate.is_symlink() for candidate in (root, *target.parents, target)),
            "Linked evidence paths are not accepted")
    return target


def write_manifest(directory):
    directory = Path(directory)
    require(not directory.is_symlink(), "Linked evidence directories are not accepted")
    files = []
    for path in sorted(directory.rglob("*")):
        if not path.is_file() or path == directory / "file_manifest.json":
            continue
        require(not path.is_symlink() and path.resolve().is_relative_to(directory.resolve()),
                "Linked or escaping evidence file")
        files.append({"path": path.relative_to(directory).as_posix(), **identity(path)})
    write_json(directory / "file_manifest.json", {"schema": "population-size-files-v1", "files": files})


def verify_manifest(directory):
    directory = Path(directory)
    require(not directory.is_symlink(), "Linked evidence directories are not accepted")
    manifest = read_json(directory / "file_manifest.json")
    require(manifest.get("schema") == "population-size-files-v1"
            and type(manifest.get("files")) is list, "Unknown evidence manifest")
    seen = set()
    for row in manifest["files"]:
        relative = row.get("path")
        require(type(relative) is str and relative not in seen
                and relative != "file_manifest.json", "Duplicate or self manifest entry")
        seen.add(relative)
        require(identity(safe_child(directory, relative)) ==
                {"bytes": row.get("bytes"), "sha256": row.get("sha256")}, "Evidence identity changed")
    actual = {path.relative_to(directory).as_posix() for path in directory.rglob("*")
              if path.is_file() and path != directory / "file_manifest.json"}
    require(actual == seen, "Evidence inventory is incomplete or contains extra files")
    return manifest


def require_ci():
    require(os.environ.get("GITHUB_ACTIONS") == "true", "Execution is GitHub-Actions only")
    require(os.environ.get("GITHUB_REPOSITORY") == REPOSITORY
            and os.environ.get("GITHUB_REF") == "refs/heads/" + BRANCH,
            "Wrong execution repository or research branch")


def source_manifest():
    paths = {*MODULE.glob("*.py"), *(path for path in MODULE.glob("*.md") if path.name != "STATUS_UK.md"), *MODULE.glob("*.R"),
             *MODULE.glob("tests/**/*.py"), *MODULE.glob("tests/**/*.json"),
             *(ROOT / relative for relative in (WORKFLOW, REQUIREMENTS, ENVIRONMENT, *LEGACY_FIXTURES))}
    paths.update((ROOT / "studies/knapsack_parameters/presentation_package/program").rglob("*.py"))
    for name in ("source_tree_manifest.json", "protocol.json"):
        path = MODULE / name
        if path.exists():
            paths.add(path)
    for parent in (ROOT / "studies", ROOT / "studies/knapsack_parameters",
                   ROOT / "studies/knapsack_parameters/presentation_package",
                   ROOT / "studies/knapsack_parameters/presentation_package/program",
                   MODULE, MODULE / "tests"):
        path = parent / "__init__.py"
        if path.exists():
            paths.add(path)
    files = []
    for path in sorted(paths):
        require(path.is_file() and not path.is_symlink(), "Missing or linked execution source")
        require(path.resolve().is_relative_to(ROOT.resolve()), "Execution source escapes checkout")
        files.append({"path": path.relative_to(ROOT).as_posix(), **identity(path)})
    return {"files": files, "sha256": hashlib.sha256(canonical(files)).hexdigest()}


def authenticate(runtime=False):
    require_ci()
    source_sha = os.environ.get("GITHUB_SHA", "")
    require(bool(re.fullmatch(r"[0-9a-f]{40}", source_sha))
            and os.environ.get("EXPECTED_SHA") == source_sha, "Exact expected source SHA is required")
    require(subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip() == source_sha,
            "Checked-out source differs from execution SHA")
    require(not subprocess.check_output(["git", "status", "--porcelain", "--untracked-files=no"], cwd=ROOT),
            "Tracked execution sources changed")
    fingerprint = source_manifest()
    for row in fingerprint["files"]:
        original = subprocess.check_output(["git", "show", source_sha + ":" + row["path"]], cwd=ROOT)
        require(hashlib.sha256(original).hexdigest() == row["sha256"], "Uncommitted execution source")
    # Mutable grants and frozen receipts are excluded from the algorithm digest,
    # but their actual bytes must still belong to this checked-out commit.
    for name in ("resource_authorization.json", "frozen_tests.json", "frozen_pilot.json", "resource_usage.json"):
        path = MODULE / name
        if path.exists():
            original = subprocess.check_output(["git", "show", source_sha + ":" + path.relative_to(ROOT).as_posix()], cwd=ROOT)
            require(original == path.read_bytes(), "Uncommitted grant or retained evidence descriptor")
    run_id = os.environ.get("GITHUB_RUN_ID", "")
    attempt = os.environ.get("GITHUB_RUN_ATTEMPT", "1")
    actor = os.environ.get("GITHUB_ACTOR", "")
    require(run_id.isdecimal() and int(run_id) > 0 and attempt.isdecimal()
            and int(attempt) > 0 and bool(actor.strip()), "Missing execution identity or actor")
    environment = None
    if runtime:
        lock = read_json(ROOT / ENVIRONMENT)
        require(sys.version.split()[0] == lock["python_version"] == "3.12.14", "Wrong Python patch version")
        require(sys.platform == "linux" and os.environ.get("RUNNER_OS") == "Linux", "Wrong runner platform")
        packages = {row["name"]: importlib.metadata.version(row["name"]) for row in lock["packages"]}
        require(all(packages[row["name"]] == row["version"] for row in lock["packages"]),
                "Installed package versions differ from the lock")
        environment = {"python": sys.version.split()[0], "packages": packages}
    return {"protocol_id": PROTOCOL, "implementation_sha": source_sha,
            "source_manifest": fingerprint, "run_id": int(run_id), "run_attempt": int(attempt),
            "actor": actor, "environment": environment}


def _date(value, label):
    require(type(value) is str and bool(value.strip()), "Missing authorization date: " + label)
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("Invalid authorization date: " + label) from exc
    require(parsed.tzinfo is not None and parsed.utcoffset() is not None, "Authorization date lacks a timezone")
    return parsed


def validate_grant(authorization, phase, now=None):
    require(phase in PHASES, "BLOCKED_UNREGISTERED_EXECUTION_PHASE")
    require(type(authorization) is dict and authorization.get("protocol_id") == PROTOCOL,
            "Wrong resource protocol")
    require(authorization.get("explicit_user_numeric_approval") is True
            and authorization.get("execution_authorized") is True,
            "BLOCKED_SEPARATE_NUMERIC_RESOURCE_APPROVAL_REQUIRED")
    minutes, compressed = authorization.get("runner_minutes_ceiling"), authorization.get("compressed_bytes_ceiling")
    require(type(minutes) is int and minutes >= RESERVATIONS[phase]
            and type(compressed) is int and compressed >= BYTE_RESERVATIONS[phase], "Invalid resource ceilings")
    require(authorization.get("historical_budgets_reassigned") is False
            and authorization.get("approved_phases") == list(PHASES)
            and authorization.get("tuning_authorized") is False
            and authorization.get("main_authorized") is False, "Grant does not match the technical-only scope")
    record = authorization.get("approval_record")
    require(type(record) is dict and type(record.get("user_message")) is str
            and bool(record["user_message"].strip()), "Missing explicit approval record")
    require(record.get("runner_minutes_ceiling") == minutes
            and record.get("compressed_bytes_ceiling") == compressed, "Approval and resource ceilings differ")
    current = now or datetime.now(timezone.utc)
    require(current.tzinfo is not None, "Current time lacks a timezone")
    approved = _date(record.get("approved_at_utc"), "approved_at_utc")
    require(approved <= current, "Authorization approval is in the future")
    if authorization.get("valid_until_utc") is not None:
        until = _date(authorization["valid_until_utc"], "valid_until_utc")
        require(approved <= until and current <= until, "Resource authorization expired")
    return authorization


def grant_for(phase):
    return validate_grant(read_json(MODULE / "resource_authorization.json"), phase)


def api(endpoint):
    require(type(endpoint) is str and endpoint.startswith("/actions/")
            and ".." not in endpoint and not endpoint.startswith("//"), "Unapproved resource API endpoint")
    token = os.environ.get("GITHUB_TOKEN")
    require(bool(token), "A read-only Actions token is required")
    request = urllib.request.Request("https://api.github.com/repos/" + REPOSITORY + endpoint,
        headers={"Authorization": "Bearer " + token, "Accept": "application/vnd.github+json",
                 "User-Agent": "knapsack-population-size-resource-audit", "X-GitHub-Api-Version": "2022-11-28"})
    try:
        with urllib.request.urlopen(request, timeout=25) as response:
            result = json.load(response)
    except (OSError, ValueError) as exc:
        raise ValueError("BLOCKED_UNKNOWN_GITHUB_RESOURCE_USAGE") from exc
    require(type(result) is dict, "Unknown GitHub resource response")
    return result


def pages(endpoint, key):
    separator = "&" if "?" in endpoint else "?"
    page, received, expected = 1, 0, None
    while True:
        result = api(endpoint + separator + f"per_page=100&page={page}")
        rows = result.get(key)
        count = result.get("total_count")
        require(type(rows) is list and len(rows) <= 100 and type(count) is int and count >= 0,
                "Unknown paginated Actions response")
        if expected is None:
            expected = count
        require(count == expected, "Actions inventory changed during pagination")
        received += len(rows)
        require(received <= expected, "Actions inventory exceeds its reported count")
        yield from rows
        if len(rows) < 100:
            require(received == expected, "BLOCKED_INCOMPLETE_PAGINATED_RESOURCE_USAGE")
            return
        page += 1


def _duration_minutes(job):
    require(type(job.get("id")) is int and job["id"] > 0
            and job.get("status") == "completed" and bool(job.get("conclusion")),
            "Unknown allocated job state")
    started = _date(job.get("started_at"), "job.started_at")
    completed = _date(job.get("completed_at"), "job.completed_at")
    seconds = (completed - started).total_seconds()
    require(seconds >= 0, "Negative allocated job duration")
    return max(1, math.ceil(seconds / 60))


def resource_usage(current_run_id, current_attempt):
    """Account for every prior attempt, including failed and cancelled jobs.

    The current attempt is reserved in full instead of estimating running gate
    time. Artifact sizes include retained metadata for expired artifacts; known
    frozen artifact identifiers may not silently disappear from the API ledger.
    """
    endpoint = "/actions/workflows/" + Path(WORKFLOW).name + "/runs?branch=" + urllib.parse.quote(BRANCH, safe="")
    jobs, artifacts, seen_runs, seen_jobs, seen_artifacts = [], [], set(), set(), set()
    for run in pages(endpoint, "workflow_runs"):
        run_id, attempts = run.get("id"), run.get("run_attempt")
        require(type(run_id) is int and run_id > 0 and run_id not in seen_runs
                and type(attempts) is int and attempts > 0, "Duplicate or unknown workflow run")
        seen_runs.add(run_id)
        require(run.get("path") == WORKFLOW and run.get("head_branch") == BRANCH,
                "Unexpected workflow in resource inventory")
        if run_id != current_run_id:
            require(run.get("status") == "completed", "BLOCKED_ACTIVE_OR_UNKNOWN_PRIOR_WORKFLOW")
        else:
            require(attempts == current_attempt, "Current attempt identity differs from Actions metadata")
        for attempt in range(1, attempts + 1):
            if (run_id, attempt) == (current_run_id, current_attempt):
                continue
            for job in pages(f"/actions/runs/{run_id}/attempts/{attempt}/jobs", "jobs"):
                if job.get("conclusion") == "skipped":
                    continue
                minutes = _duration_minutes(job)
                require(job["id"] not in seen_jobs, "Duplicate allocated job")
                seen_jobs.add(job["id"])
                jobs.append({"run_id": run_id, "run_attempt": attempt, "job_id": job["id"],
                             "name": job.get("name"), "conclusion": job["conclusion"], "runner_minutes": minutes})
        for artifact in pages(f"/actions/runs/{run_id}/artifacts", "artifacts"):
            identifier, size = artifact.get("id"), artifact.get("size_in_bytes")
            require(type(identifier) is int and identifier > 0 and identifier not in seen_artifacts
                    and type(size) is int and size >= 0 and type(artifact.get("expired")) is bool,
                    "Duplicate or unknown artifact size")
            require(artifact.get("workflow_run", {}).get("id") == run_id, "Artifact belongs to another workflow run")
            seen_artifacts.add(identifier)
            artifacts.append({"artifact_id": identifier, "run_id": run_id, "name": artifact.get("name"),
                              "compressed_bytes": size, "expired": artifact["expired"]})
    for name in ("frozen_tests.json", "frozen_pilot.json", "resource_usage.json"):
        path = MODULE / name
        if not path.exists():
            continue
        retained = read_json(path)
        required_artifacts = set(retained.get("known_artifact_ids", []))
        if "artifact_id" in retained:
            required_artifacts.add(retained["artifact_id"])
        require(required_artifacts <= seen_artifacts, "BLOCKED_MISSING_PREVIOUSLY_RECORDED_ARTIFACT_USAGE")
    require(current_attempt == 1 or current_run_id in seen_runs,
            "BLOCKED_UNKNOWN_PREVIOUS_ATTEMPTS_OF_CURRENT_RUN")
    return {"used_runner_minutes": sum(row["runner_minutes"] for row in jobs),
            "used_compressed_bytes": sum(row["compressed_bytes"] for row in artifacts),
            "jobs": jobs, "artifacts": artifacts}


def check_allowance(phase, usage, grant):
    require(phase in PHASES, "BLOCKED_UNREGISTERED_EXECUTION_PHASE")
    minutes, compressed = usage.get("used_runner_minutes"), usage.get("used_compressed_bytes")
    require(type(minutes) is int and minutes >= 0 and type(compressed) is int and compressed >= 0,
            "BLOCKED_UNKNOWN_CUMULATIVE_RESOURCE_USAGE")
    require(minutes + RESERVATIONS[phase] <= grant["runner_minutes_ceiling"],
            "BLOCKED_INSUFFICIENT_CUMULATIVE_RUNNER_MINUTES")
    require(compressed + BYTE_RESERVATIONS[phase] <= grant["compressed_bytes_ceiling"],
            "BLOCKED_INSUFFICIENT_CUMULATIVE_ARTIFACT_CAPACITY")


def _frozen_receipt_identities():
    return {name: identity(MODULE / name) for name in ("frozen_tests.json", "frozen_pilot.json")
            if (MODULE / name).exists()}


def validate_requested_phase(phase, event_name, commit_message=""):
    require(phase in PHASES, "BLOCKED_UNREGISTERED_EXECUTION_PHASE")
    require(event_name in ("push", "workflow_dispatch"), "Unregistered workflow event")
    if event_name == "push":
        require(type(commit_message) is str, "Missing push commit message")
        markers = re.findall(r"\[population-size:([^\]\r\n]*)\]", commit_message)
        require(markers == [phase], "Exactly one matching population-size phase marker is required")
    return phase


def preflight(phase):
    provenance = authenticate()
    event = os.environ.get("GITHUB_EVENT_NAME", "")
    message = os.environ.get("COMMIT_MESSAGE", "")
    validate_requested_phase(phase, event, message)
    if event == "push":
        actual_message = subprocess.check_output(["git", "log", "-1", "--format=%B"], cwd=ROOT, text=True)
        require(actual_message.strip() == message.strip(), "Push marker is not the checked-out commit message")
    grant = grant_for(phase)
    current = api(f"/actions/runs/{provenance['run_id']}/attempts/{provenance['run_attempt']}")
    require(current.get("id") == provenance["run_id"]
            and current.get("run_attempt") == provenance["run_attempt"]
            and current.get("head_sha") == provenance["implementation_sha"]
            and current.get("head_branch") == BRANCH and current.get("path") == WORKFLOW
            and current.get("event") == event, "Current workflow metadata differs from its source")
    usage = resource_usage(provenance["run_id"], provenance["run_attempt"])
    check_allowance(phase, usage, grant)
    return {**provenance, "phase": phase, "grant": grant, "usage": usage,
            "resource_authorization_identity": identity(MODULE / "resource_authorization.json"),
            "frozen_receipt_identities": _frozen_receipt_identities(),
            "reserved_runner_minutes": RESERVATIONS[phase], "reserved_compressed_bytes": BYTE_RESERVATIONS[phase]}


def check_permit(permit, expected_phase):
    provenance = authenticate(runtime=True)
    validate_requested_phase(expected_phase, os.environ.get("GITHUB_EVENT_NAME", ""),
                             os.environ.get("COMMIT_MESSAGE", ""))
    require(type(permit) is dict, "Invalid resource permit")
    for field in ("protocol_id", "implementation_sha", "source_manifest", "run_id", "run_attempt", "actor"):
        require(permit.get(field) == provenance[field], "Stale or foreign resource permit: " + field)
    grant = grant_for(expected_phase)
    require(permit.get("phase") == expected_phase and permit.get("grant") == grant
            and permit.get("resource_authorization_identity") == identity(MODULE / "resource_authorization.json")
            and permit.get("frozen_receipt_identities") == _frozen_receipt_identities()
            and permit.get("reserved_runner_minutes") == RESERVATIONS[expected_phase]
            and permit.get("reserved_compressed_bytes") == BYTE_RESERVATIONS[expected_phase],
            "Changed resource authorization or frozen evidence")
    check_allowance(expected_phase, permit.get("usage", {}), grant)
    return provenance
