"""Fail-closed CI authority for the separately approved tournament study."""
from __future__ import annotations

from datetime import datetime
import hashlib
import importlib.metadata
import io
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
REL = "studies/knapsack_parameters/tournament_feedback/"
PROTOCOL = "GA-KNAPSACK-TOURNAMENT-FEEDBACK-V1"
REGISTRATION_SHA = "1993e4fe5d9ba2715663d0519571d1a0355d3d5f"
REPOSITORY = "ChepaMaksym/GA-article-test"
BRANCH = "research/masters-ga-diversity-crossover"
WORKFLOW = ".github/workflows/knapsack-tournament-feedback.yml"
PROFILES = ("k2", "k3", "k4", "k5", "adaptive", "replay")
PILOT_TASKS = ("UC-s000", "WC-s001", "SC-s005", "SC-s000")
MAIN_WORKERS = tuple(f"s{i:03d}" for i in range(40, 50))
PHASES = ("tests", "prepare-pilot", "pilot-donors", "pilot-recipients", "prepare-main", "main-donors", "main-recipients", "aggregate")
TIMEOUTS = {"tests": 6, "prepare-pilot": 4, "pilot-donors": 2, "pilot-recipients": 4,
            "prepare-main": 11, "main-donors": 5, "main-recipients": 16, "aggregate": 5}
# Gate + source timeouts + aggregator timeout + one rounding minute/job.
RESERVATIONS = {"tests": 8, "prepare-pilot": 6, "pilot-donors": 19, "pilot-recipients": 27,
                "prepare-main": 13, "main-donors": 67, "main-recipients": 177, "aggregate": 7}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode("utf-8")


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
    require(type(relative) is str, "Non-string relative path")
    rel = PurePosixPath(relative)
    require(not rel.is_absolute() and rel.parts and ".." not in rel.parts and ":" not in relative and "\\" not in relative,
            "Unsafe evidence path")
    target = Path(directory).joinpath(*rel.parts)
    require(target.resolve().is_relative_to(Path(directory).resolve()), "Escaping path")
    return target


def write_manifest(directory):
    directory = Path(directory)
    files = [{"path": p.relative_to(directory).as_posix(), **identity(p)} for p in sorted(directory.rglob("*"))
             if p.is_file() and p != directory / "file_manifest.json"]
    write_json(directory / "file_manifest.json", {"schema": "tournament-feedback-manifest-v1", "files": files})


def verify_manifest(directory):
    directory = Path(directory)
    result = read_json(directory / "file_manifest.json")
    require(result.get("schema") == "tournament-feedback-manifest-v1", "Foreign manifest")
    seen = set()
    for row in result["files"]:
        require(row["path"] not in seen and row["path"] != "file_manifest.json", "Duplicate manifest entry")
        seen.add(row["path"])
        require(identity(safe_child(directory, row["path"])) == {"bytes": row["bytes"], "sha256": row["sha256"]}, "Evidence checksum mismatch")
    require(seen == {p.relative_to(directory).as_posix() for p in directory.rglob("*") if p.is_file() and p != directory / "file_manifest.json"}, "Incomplete evidence inventory")
    return result


def phase(message):
    markers = re.findall(r"\[([^\[\]\r\n]+)\]", message)
    require(len(markers) == 1 and markers[0].startswith("tournament-feedback:"), "Exactly one registered phase marker required")
    result = markers[0].split(":", 1)[1]
    require(result in PHASES, "Unknown phase")
    return result


def source_manifest():
    paths = {*MODULE.glob("*.py"), *MODULE.glob("tests/*.py"), ROOT / WORKFLOW, ROOT / ".gitattributes",
             ROOT / "studies/knapsack_parameters/parameter_dynamics/engine.py",
             ROOT / "studies/knapsack_parameters/parameter_dynamics/banks.py",
             ROOT / "studies/knapsack_parameters/two_signal_mutation/banks.py"}
    paths.update(MODULE / name for name in ("PROTOCOL_UK.md", "protocol.json", "registration.json", "environment.json", "SOURCE_AUDIT_UK.md", "source_registry.json"))
    paths.update(ROOT / path for path in read_json(MODULE / "environment.json").values()
                 if type(path) is str and path.startswith("studies/") and path.endswith((".json", ".lock")))
    rows = [{"path": p.relative_to(ROOT).as_posix(), **identity(p)} for p in sorted(paths)]
    return {"files": rows, "sha256": hashlib.sha256(canonical(rows)).hexdigest()}


def authenticate(runtime=False):
    require(os.environ.get("GITHUB_ACTIONS") == "true" and os.environ.get("GITHUB_REPOSITORY") == REPOSITORY and
            os.environ.get("GITHUB_REF") == "refs/heads/" + BRANCH, "Registered GitHub Actions context required")
    sha = os.environ.get("GITHUB_SHA", "")
    require(re.fullmatch(r"[0-9a-f]{40}", sha) and os.environ.get("EXPECTED_SHA") == sha, "Exact SHA required")
    require(subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip() == sha, "Wrong checkout")
    require(not subprocess.check_output(["git", "status", "--porcelain", "--untracked-files=no"], cwd=ROOT), "Tracked execution sources changed")
    subprocess.run(["git", "merge-base", "--is-ancestor", REGISTRATION_SHA, sha], cwd=ROOT, check=True)
    registration = read_json(MODULE / "registration.json")
    for row in registration["scientific_files"]:
        require(identity(ROOT / row["path"])["sha256"] == row["sha256"], "Registered science changed")
        require(subprocess.check_output(["git", "show", REGISTRATION_SHA + ":" + row["path"]], cwd=ROOT) == (ROOT / row["path"]).read_bytes(), "Registration snapshot changed")
    environment = None
    if runtime:
        env = read_json(MODULE / "environment.json")
        require(sys.version.split()[0] == env["python"], "Wrong CPython patch version")
        for stem in ("requirements_lock", "environment_lock"):
            require(identity(ROOT / env[stem + "_path"])["sha256"] == env[stem + "_sha256"], "Dependency lock changed")
        lock = read_json(ROOT / env["environment_lock_path"])
        packages = {row["name"]: importlib.metadata.version(row["name"]) for row in lock["packages"]}
        require(all(packages[row["name"]] == row["version"] for row in lock["packages"]), "Wrong dependency version")
        environment = {"python": env["python"], "packages": packages}
    return {"protocol_id": PROTOCOL, "registration_sha": subprocess.check_output(["git", "rev-parse", REGISTRATION_SHA], cwd=ROOT, text=True).strip(),
            "implementation_sha": sha, "source_manifest": source_manifest(), "run_id": int(os.environ["GITHUB_RUN_ID"]),
            "run_attempt": int(os.environ.get("GITHUB_RUN_ATTEMPT", "1")), "environment": environment}


def grant_for(selected):
    require(selected in PHASES, "Unknown grant phase")
    grant = read_json(MODULE / "resource_authorization.json")
    require(grant.get("protocol_id") == PROTOCOL and grant.get("explicit_user_numeric_approval") is True and
            grant.get("execution_authorized") is True and grant.get("runner_minutes_ceiling") == 300 and
            grant.get("compressed_bytes_ceiling") == 6 * 2 ** 30 and grant.get("historical_budgets_reassigned") is False,
            "Separate explicit 300-minute/six-GiB approval required")
    return grant


def api(endpoint):
    token = os.environ.get("GITHUB_TOKEN")
    require(bool(token), "Read-only Actions token required")
    req = urllib.request.Request("https://api.github.com/repos/" + REPOSITORY + endpoint,
          headers={"Authorization": "Bearer " + token, "Accept": "application/vnd.github+json", "User-Agent": "tournament-feedback-audit", "X-GitHub-Api-Version": "2022-11-28"})
    with urllib.request.urlopen(req, timeout=60) as response:
        return json.load(response)


def pages(endpoint, key):
    for number in range(1, 10001):
        rows = api(endpoint + ("&" if "?" in endpoint else "?") + f"per_page=100&page={number}")[key]
        yield from rows
        if len(rows) < 100:
            return
    raise ValueError("Unexpected API pagination length")


def runner_usage(selected=None):
    current = (int(os.environ["GITHUB_RUN_ID"]), int(os.environ.get("GITHUB_RUN_ATTEMPT", "1")))
    rows, jobs_seen = [], set()
    endpoint = "/actions/workflows/" + Path(WORKFLOW).name + "/runs?branch=" + urllib.parse.quote(BRANCH, safe="")
    for run in pages(endpoint, "workflow_runs"):
        for attempt in range(1, run["run_attempt"] + 1):
            if (run["id"], attempt) == current:
                continue
            jobs = [job for job in pages(f"/actions/runs/{run['id']}/attempts/{attempt}/jobs", "jobs") if job.get("conclusion") != "skipped"]
            if not jobs:
                continue
            source_phase = phase(run.get("head_commit", {}).get("message", ""))
            for job in jobs:
                require(job["id"] not in jobs_seen and job.get("started_at") and job.get("completed_at"), "Unknown or concurrent runner duration")
                jobs_seen.add(job["id"])
                seconds = (datetime.fromisoformat(job["completed_at"].replace("Z", "+00:00")) - datetime.fromisoformat(job["started_at"].replace("Z", "+00:00"))).total_seconds()
                require(seconds >= 0, "Negative runner duration")
                rows.append({"run_id": run["id"], "attempt": attempt, "job_id": job["id"], "phase": source_phase,
                             "name": job["name"], "runner_minutes": max(1, math.ceil(seconds / 60))})
    return {"jobs": rows, "used_runner_minutes": sum(row["runner_minutes"] for row in rows)}


def validate_source_receipt(receipt, expected_phase):
    require(receipt.get("protocol_id") == PROTOCOL and receipt.get("source_manifest") == source_manifest(), "Mixed or changed code fingerprint")
    source_sha = receipt.get("implementation_sha", "")
    require(re.fullmatch(r"[0-9a-f]{40}", source_sha), "Invalid receipt SHA")
    subprocess.run(["git", "merge-base", "--is-ancestor", source_sha, os.environ["GITHUB_SHA"]], cwd=ROOT, check=True)
    run = api(f"/actions/runs/{receipt['run_id']}/attempts/{receipt['run_attempt']}")
    require(run.get("conclusion") == "success" and run.get("head_sha") == source_sha and run.get("path") == WORKFLOW and
            run.get("head_branch") == BRANCH and phase(run.get("head_commit", {}).get("message", "")) == expected_phase,
            "Source phase was not successfully completed")


def frozen_receipt(kind, expected_phase):
    frozen = read_json(MODULE / ("frozen_" + kind + ".json"))
    path = safe_child(MODULE, frozen["receipt_path"])
    require(frozen.get("frozen") is True and identity(path) == frozen["receipt_identity"], "Receipt not frozen")
    verify_manifest(path.parent)
    receipt = read_json(path)
    validate_source_receipt(receipt, expected_phase)
    artifact = api(f"/actions/artifacts/{frozen['artifact_id']}")
    require(artifact.get("expired") is False and artifact.get("digest") == "sha256:" + frozen["zip_sha256"] and
            artifact.get("workflow_run", {}).get("id") == receipt["run_id"], "Canonical artifact unavailable")
    freeze_sha = subprocess.check_output(["git", "log", "-1", "--format=%H", "--", REL + "frozen_" + kind + ".json"], cwd=ROOT, text=True).strip()
    require(freeze_sha and freeze_sha != receipt["implementation_sha"], "Separate receipt freeze commit required")
    changed = subprocess.check_output(["git", "diff-tree", "--no-commit-id", "--name-only", "-r", freeze_sha], cwd=ROOT, text=True).splitlines()
    allowed = {REL + "frozen_" + kind + ".json"}
    require(changed and all(item in allowed or item.startswith(path.parent.relative_to(ROOT).as_posix() + "/") for item in changed), "Freeze commit mixes code with evidence")
    paths = [MODULE / ("frozen_" + kind + ".json"), path.parent / "file_manifest.json"]
    paths += [safe_child(path.parent, row["path"]) for row in read_json(path.parent / "file_manifest.json")["files"]]
    queries = b"".join((freeze_sha + ":" + target.relative_to(ROOT).as_posix() + "\n").encode() for target in paths)
    stream = io.BytesIO(subprocess.check_output(["git", "cat-file", "--batch"], input=queries, cwd=ROOT))
    for target in paths:
        header = stream.readline().split()
        require(len(header) == 3 and header[1] == b"blob", "Frozen evidence blob missing")
        require(stream.read(int(header[2])) == target.read_bytes() and stream.read(1) == b"\n", "Frozen bytes changed")
    require(stream.read() == b"", "Unexpected freeze bytes")
    return receipt, path.parent


def validated_tests():
    receipt, _ = frozen_receipt("tests", "tests")
    require(receipt.get("tests_passed") is True and receipt.get("failures") == receipt.get("errors") == receipt.get("skipped") == 0 and
            receipt.get("tests_run", 0) > 0, "Fully green software checks required")
    return receipt


def main_forecast(usage):
    receipt, _ = frozen_receipt("pilot", "pilot-recipients")
    require(receipt.get("complete") is True and receipt.get("physical_runs_including_donors") == 56, "Complete pilot required")
    forecast = receipt["cost_review"]
    require(forecast.get("future_runs") == 6300 and forecast["forecast_main_runner_minutes"] + usage["used_runner_minutes"] <= 300 and
            forecast["forecast_total_journal_bytes"] <= 6 * 2 ** 30 and forecast["forecast_main_donor_timeout"] <= TIMEOUTS["main-donors"] and
            forecast["forecast_main_recipient_timeout"] <= TIMEOUTS["main-recipients"], "Measured main forecast exceeds remaining approval or timeouts")


def preflight(selected, output):
    provenance = authenticate()
    require(phase(os.environ.get("COMMIT_MESSAGE", "")) == selected, "Wrong phase request")
    grant, usage = grant_for(selected), runner_usage(selected)
    require(usage["used_runner_minutes"] + RESERVATIONS[selected] <= grant["runner_minutes_ceiling"], "Insufficient cumulative resource budget")
    if selected != "tests":
        validated_tests()
    if selected == "prepare-main":
        main_forecast(usage)
    if selected.endswith(("donors", "recipients")):
        from . import banks
        banks.load_frozen_banks(selected.split("-")[0], check_scores=False)
    if selected.endswith("recipients"):
        from . import banks
        banks.load_frozen_schedules(selected.split("-")[0])
    if selected in ("main-donors", "main-recipients"):
        frozen_receipt("pilot", "pilot-recipients")
        main_forecast({"used_runner_minutes": 0})  # Current remaining phase is separately reserved above.
    permit = {**provenance, "phase": selected, "grant": grant, "usage": usage,
              "resource_authorization_identity": identity(MODULE / "resource_authorization.json"), "reservation": RESERVATIONS[selected]}
    write_json(Path(output) / "permit.json", permit)
    write_manifest(output)
    if os.environ.get("GITHUB_OUTPUT"):
        workers = list(PILOT_TASKS if selected.startswith("pilot-") else MAIN_WORKERS)
        with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as stream:
            stream.write("phase=" + selected + "\nworker_timeout=" + str(TIMEOUTS[selected]) + "\n")
            stream.write("worker_matrix=" + json.dumps({"worker": workers}) + "\n")
    return permit


def check_permit(directory, selected):
    provenance = authenticate(runtime=True)
    require(phase(os.environ.get("COMMIT_MESSAGE", "")) == selected, "Worker phase differs")
    verify_manifest(directory)
    permit = read_json(Path(directory) / "permit.json")
    for key in ("protocol_id", "registration_sha", "implementation_sha", "source_manifest", "run_id", "run_attempt"):
        require(permit.get(key) == provenance[key], "Stale or mixed permit: " + key)
    grant = grant_for(selected)
    require(permit.get("phase") == selected and permit.get("grant") == grant and permit.get("resource_authorization_identity") == identity(MODULE / "resource_authorization.json") and
            permit["usage"]["used_runner_minutes"] + RESERVATIONS[selected] <= 300, "Invalid bounded permit")
    return provenance


def journal_allowance(selected):
    if selected == "main-donors":
        return (2 ** 30) // 10
    if selected == "main-recipients":
        return (18 * 2 ** 28) // 10  # 4.5 GiB across ten workers; pilot phases share .5 GiB.
    return 2 ** 26  # Four pilot workers/phase share at most .25 GiB.
