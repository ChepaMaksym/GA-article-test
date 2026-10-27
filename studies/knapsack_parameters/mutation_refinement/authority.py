"""Fail-closed technical authority; imports perform no scientific work."""
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
REL = "studies/knapsack_parameters/mutation_refinement/"
PROTOCOL = "GA-KNAPSACK-MUTATION-REFINEMENT-V1"
REGISTRATION_SHA = "ef211e41bc0803d29369ec44412aa099cf0e2e71"
PROTOCOL_SHA256 = "032576358a6adc27e2a45b57151d2d6ea69c78859e0295a70416656632370dc6"
BRANCH = "research/masters-ga-diversity-crossover"
REPOSITORY = "ChepaMaksym/GA-article-test"
WORKFLOW = ".github/workflows/knapsack-mutation-refinement.yml"
PHASES = ("tests", "prepare-pilot", "pilot")
METHODS = ("fixed_0.005", "fixed_0.01", "fixed_0.02", "legacy", "gentle")
PILOT_TASKS = ("UC-s000", "WC-s001", "SC-s005", "SC-s000")
STARTS = ("cloned", "bank")
RESERVATIONS = {"tests": 9, "prepare-pilot": 7, "pilot": 34}
TIMEOUTS = {"gate": 1, "tests": 6, "prepare": 4, "worker": 6, "aggregate": 4}
REQUIREMENTS = "studies/knapsack_parameters/ga_study/dependencies/requirements.lock"
ENVIRONMENT = "studies/knapsack_parameters/ga_study/dependencies/environment.lock.json"
IMMUTABLE = {
    REQUIREMENTS: "6818e0e12843daa10947f7554cb3edd573d9f7cdbc33e63f98f9f3a068869017",
    ENVIRONMENT: "9907e3a46971303d8285b7ae160b5b8eafcab9942565d376bd038a92789745c6",
    "studies/knapsack_parameters/two_signal_mutation/banks.py": "88bd027845eca7347ea189827fd2705d895ebfeaea03ef443527087c39dde7df",
    "studies/knapsack_parameters/two_signal_mutation/authority.py": "23ef92cb10dfb74cc3c12418ef0e7d9fddf360a93b5d729e59cdd459032940dd",
    "studies/knapsack_parameters/two_signal_mutation/registration.json": "647e33b927a400f337fbad26cfa14e3c398952680b1ab858f882722d265825f5",
    "studies/knapsack_parameters/parameter_dynamics/engine.py": "ab02267cae2381564195ccf2b3beb71f28d14a34c19ee9717168a0b438726976",
    "studies/knapsack_parameters/parameter_dynamics/verifier.py": "7c9c4a19104202b171df3e26f5cab4a02618ee1e0a13879e3aa3c8173ad3c82a",
}


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
    raw = Path(path).read_bytes()
    return {"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def safe_child(directory, relative):
    require(type(relative) is str, "Evidence path must be text")
    rel = PurePosixPath(relative)
    require(bool(rel.parts) and not rel.is_absolute() and ".." not in rel.parts and
            ":" not in relative and "\\" not in relative, "Unsafe evidence path")
    target = Path(directory).joinpath(*rel.parts)
    require(target.resolve().is_relative_to(Path(directory).resolve()), "Escaping evidence path")
    return target


def write_manifest(directory):
    directory = Path(directory)
    files = [{"path": p.relative_to(directory).as_posix(), **identity(p)}
             for p in sorted(directory.rglob("*")) if p.is_file() and p != directory / "file_manifest.json"]
    write_json(directory / "file_manifest.json", {"schema": "mutation-refinement-files-v1", "files": files})


def verify_manifest(directory):
    directory = Path(directory)
    manifest = read_json(directory / "file_manifest.json")
    require(manifest.get("schema") == "mutation-refinement-files-v1" and type(manifest.get("files")) is list,
            "Wrong file manifest")
    seen = set()
    for row in manifest["files"]:
        relative = row["path"]
        require(relative not in seen and relative != "file_manifest.json", "Duplicate/self manifest entry")
        seen.add(relative)
        require(identity(safe_child(directory, relative)) == {"bytes": row["bytes"], "sha256": row["sha256"]},
                "Manifest identity differs: " + relative)
    actual = {p.relative_to(directory).as_posix() for p in directory.rglob("*")
              if p.is_file() and p != directory / "file_manifest.json"}
    require(actual == seen, "Incomplete or extra evidence inventory")
    return manifest


def phase(message):
    markers = re.findall(r"\[([^\[\]\r\n]+)\]", message)
    require(len(markers) == 1 and markers[0].startswith("mutation-refinement:"), "Exactly one phase marker required")
    selected = markers[0].split(":", 1)[1]
    require(selected in PHASES, "BLOCKED_UNREGISTERED_OR_SCIENTIFIC_PHASE")
    return selected


def source_manifest():
    paths = {*MODULE.glob("*.py"), *MODULE.glob("tests/*.py"), *MODULE.glob("*.md"), ROOT / WORKFLOW,
             *(ROOT / name for name in IMMUTABLE)}
    # Resource grants and later frozen receipts are mutable authority/data, not
    # algorithm sources. A permit binds the grant separately byte-for-byte.
    for parent in (ROOT / "studies", ROOT / "studies/knapsack_parameters", MODULE, MODULE / "tests"):
        initializer = parent / "__init__.py"
        if initializer.exists():
            paths.add(initializer)
    files = [{"path": p.relative_to(ROOT).as_posix(), **identity(p)} for p in sorted(paths)]
    return {"files": files, "sha256": hashlib.sha256(canonical(files)).hexdigest()}


def authenticate(runtime=False):
    require(os.environ.get("GITHUB_ACTIONS") == "true", "Execution is GitHub-Actions only")
    require(os.environ.get("GITHUB_REPOSITORY") == REPOSITORY and
            os.environ.get("GITHUB_REF") == "refs/heads/" + BRANCH, "Wrong repository or branch")
    sha = os.environ.get("GITHUB_SHA", "")
    require(bool(re.fullmatch("[0-9a-f]{40}", sha)) and os.environ.get("EXPECTED_SHA") == sha,
            "Exact expected source SHA required")
    require(subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip() == sha,
            "Checkout differs from execution SHA")
    require(not subprocess.check_output(["git", "status", "--porcelain", "--untracked-files=no"], cwd=ROOT),
            "Tracked execution files changed")
    subprocess.run(["git", "merge-base", "--is-ancestor", REGISTRATION_SHA, sha], cwd=ROOT, check=True)
    registered = subprocess.check_output(["git", "show", REGISTRATION_SHA + ":" + REL + "PROTOCOL_UK.md"], cwd=ROOT)
    require(registered == (MODULE / "PROTOCOL_UK.md").read_bytes() and
            hashlib.sha256(registered).hexdigest() == PROTOCOL_SHA256, "Registered protocol changed")
    for relative, digest in IMMUTABLE.items():
        require(identity(ROOT / relative)["sha256"] == digest, "Immutable dependency changed: " + relative)
    fingerprint = source_manifest()
    for row in fingerprint["files"]:
        original = subprocess.check_output(["git", "show", sha + ":" + row["path"]], cwd=ROOT)
        require(hashlib.sha256(original).hexdigest() == row["sha256"], "Uncommitted source in execution inventory")
    environment = None
    if runtime:
        lock = read_json(ROOT / ENVIRONMENT)
        require(sys.version.split()[0] == lock["python_version"] == "3.12.14", "Wrong Python patch version")
        require(sys.platform == "linux" and os.environ.get("RUNNER_OS") == "Linux", "Unexpected runner platform")
        packages = {r["name"]: importlib.metadata.version(r["name"]) for r in lock["packages"]}
        require(all(packages[r["name"]] == r["version"] for r in lock["packages"]), "Installed dependency drift")
        environment = {"python": sys.version.split()[0], "packages": packages}
    return {"protocol_id": PROTOCOL, "registration_sha": REGISTRATION_SHA, "implementation_sha": sha,
            "source_manifest": fingerprint, "run_id": int(os.environ["GITHUB_RUN_ID"]),
            "run_attempt": int(os.environ.get("GITHUB_RUN_ATTEMPT", "1")), "environment": environment}


def grant_for(selected):
    require(selected in PHASES, "BLOCKED_UNREGISTERED_OR_SCIENTIFIC_PHASE")
    authorization = read_json(MODULE / "resource_authorization.json")
    require(authorization.get("protocol_id") == PROTOCOL, "Wrong resource protocol")
    grant = authorization.get("technical", {})
    require(grant.get("explicit_user_approval") is True, "BLOCKED_SEPARATE_RESOURCE_APPROVAL_REQUIRED")
    require(type(grant.get("runner_minutes_ceiling")) is int and grant["runner_minutes_ceiling"] == 60 and
            grant.get("allowed_phases") == list(PHASES) and grant.get("phase_reservations") == RESERVATIONS and
            grant.get("job_timeouts") == TIMEOUTS and grant.get("max_parallel") == 4 and
            grant.get("fail_fast") is False and grant.get("workflow_serial") is True and
            grant.get("pilot_runs") == 40 and grant.get("initial_banks") == 8 and
            grant.get("new_calls_per_run") == 5000 and grant.get("calibration_authorized") is False and
            grant.get("main_search_authorized") is False and grant.get("new_exact_solves_authorized") is False and
            grant.get("maximum_compressed_bytes_per_worker") == 536870912,
            "Incompatible bounded technical grant")
    require(authorization.get("calibration", {}).get("explicit_user_approval") is False and
            authorization.get("main", {}).get("explicit_user_approval") is False,
            "Scientific phases require a separately registered contract")
    return grant


def api(endpoint):
    token = os.environ.get("GITHUB_TOKEN")
    require(bool(token), "Read-only Actions token required")
    request = urllib.request.Request("https://api.github.com/repos/" + REPOSITORY + endpoint,
        headers={"Authorization": "Bearer " + token, "Accept": "application/vnd.github+json",
                 "User-Agent": "mutation-refinement-audit", "X-GitHub-Api-Version": "2022-11-28"})
    with urllib.request.urlopen(request, timeout=25) as response:
        return json.load(response)


def pages(endpoint, key):
    separator = "&" if "?" in endpoint else "?"
    page = 1
    while True:
        response = api(endpoint + separator + f"per_page=100&page={page}")
        require(type(response.get(key)) is list, "Unknown Actions resource response")
        rows = response[key]
        yield from rows
        if len(rows) < 100:
            return
        page += 1


def runner_usage():
    """All prior workflow attempts, including failures/cancellations, rounded per job."""
    current = (int(os.environ["GITHUB_RUN_ID"]), int(os.environ.get("GITHUB_RUN_ATTEMPT", "1")))
    endpoint = "/actions/workflows/" + Path(WORKFLOW).name + "/runs?branch=" + urllib.parse.quote(BRANCH, safe="")
    jobs, seen_runs, seen_jobs = [], set(), set()
    for run in pages(endpoint, "workflow_runs"):
        require(run["id"] not in seen_runs and type(run.get("run_attempt")) is int, "Duplicate/unknown workflow attempt")
        seen_runs.add(run["id"])
        for attempt in range(1, run["run_attempt"] + 1):
            if (run["id"], attempt) == current:
                continue
            allocated = [job for job in pages(f"/actions/runs/{run['id']}/attempts/{attempt}/jobs", "jobs")
                         if job.get("conclusion") != "skipped"]
            if not allocated:
                continue
            source_phase = phase(run.get("head_commit", {}).get("message", ""))
            require(run["id"] == current[0] or run.get("status") == "completed", "Concurrent resource usage unknown")
            for job in allocated:
                require(job["id"] not in seen_jobs and job.get("started_at") and job.get("completed_at") and
                        job.get("status") == "completed", "Incomplete/duplicate allocated job duration")
                seen_jobs.add(job["id"])
                seconds = (datetime.fromisoformat(job["completed_at"].replace("Z", "+00:00")) -
                           datetime.fromisoformat(job["started_at"].replace("Z", "+00:00"))).total_seconds()
                require(seconds >= 0, "Negative allocated duration")
                jobs.append({"run_id": run["id"], "run_attempt": attempt, "job_id": job["id"],
                             "phase": source_phase, "name": job["name"], "conclusion": job.get("conclusion"),
                             "runner_minutes": max(1, math.ceil(seconds / 60))})
    return {"used_runner_minutes": sum(row["runner_minutes"] for row in jobs), "jobs": jobs}


def check_allowance(selected, usage, grant):
    used = usage.get("used_runner_minutes")
    require(type(used) is int and used >= 0 and selected in RESERVATIONS and
            used + RESERVATIONS[selected] <= grant["runner_minutes_ceiling"],
            "BLOCKED_INSUFFICIENT_CUMULATIVE_BUDGET")


def validate_source_receipt(receipt, expected_phase):
    require(receipt.get("protocol_id") == PROTOCOL and receipt.get("registration_sha") == REGISTRATION_SHA and
            receipt.get("source_manifest") == source_manifest(), "Changed or foreign green source fingerprint")
    sha = receipt.get("implementation_sha", "")
    require(bool(re.fullmatch("[0-9a-f]{40}", sha)), "Invalid receipt source SHA")
    subprocess.run(["git", "merge-base", "--is-ancestor", sha, os.environ["GITHUB_SHA"]], cwd=ROOT, check=True)
    run = api(f"/actions/runs/{receipt['run_id']}/attempts/{receipt['run_attempt']}")
    require(run.get("conclusion") == "success" and run.get("head_sha") == sha and
            run.get("head_branch") == BRANCH and run.get("path") == WORKFLOW and
            phase(run.get("head_commit", {}).get("message", "")) == expected_phase, "Receipt phase did not succeed")
    for row in source_manifest()["files"]:
        raw = subprocess.check_output(["git", "show", sha + ":" + row["path"]], cwd=ROOT)
        require(hashlib.sha256(raw).hexdigest() == row["sha256"], "Receipt original source bytes differ")
    return run


def frozen_artifact(descriptor, expected_name, receipt):
    require(type(descriptor.get("artifact_id")) is int and descriptor["artifact_id"] > 0 and
            bool(re.fullmatch("[0-9a-f]{64}", descriptor.get("zip_sha256", ""))), "Missing frozen artifact identity")
    artifact = api(f"/actions/artifacts/{descriptor['artifact_id']}")
    require(artifact.get("expired") is False and artifact.get("workflow_run", {}).get("id") == receipt["run_id"] and
            artifact.get("name") == f"mutation-refinement-{expected_name}-{receipt['run_id']}-{receipt['run_attempt']}" and
            artifact.get("digest") == "sha256:" + descriptor["zip_sha256"], "Frozen artifact unavailable or altered")


def seal_frozen_files(descriptor_path, directory, manifest):
    freeze_sha = subprocess.check_output(["git", "log", "-1", "--format=%H", "--", descriptor_path.relative_to(ROOT).as_posix()],
                                         cwd=ROOT, text=True).strip()
    require(bool(re.fullmatch("[0-9a-f]{40}", freeze_sha)), "Data freeze commit missing")
    allowed_descriptor = descriptor_path.relative_to(ROOT).as_posix()
    prefix = directory.relative_to(ROOT).as_posix() + "/"
    changed = subprocess.check_output(["git", "diff-tree", "--no-commit-id", "--name-only", "-r", freeze_sha],
                                      cwd=ROOT, text=True).splitlines()
    require(changed and all(p == allowed_descriptor or p.startswith(prefix) for p in changed),
            "Freeze commit must contain only the relevant retained data")
    paths = [descriptor_path, directory / "file_manifest.json"] + [safe_child(directory, r["path"]) for r in manifest["files"]]
    requests = b"".join((freeze_sha + ":" + p.relative_to(ROOT).as_posix() + "\n").encode() for p in paths)
    stream = io.BytesIO(subprocess.check_output(["git", "cat-file", "--batch"], input=requests, cwd=ROOT))
    for path in paths:
        header = stream.readline().split()
        require(len(header) == 3 and header[1] == b"blob", "Frozen evidence blob missing")
        require(stream.read(int(header[2])) == path.read_bytes() and stream.read(1) == b"\n", "Evidence changed after freeze")
    require(stream.read() == b"", "Unexpected frozen inventory")
    return freeze_sha


def validated_tests():
    descriptor_path = MODULE / "frozen_tests.json"
    frozen = read_json(descriptor_path)
    require(frozen.get("frozen") is True, "Green tests receipt not frozen")
    receipt_path = safe_child(MODULE, frozen["receipt_path"])
    require(receipt_path.resolve().is_relative_to((MODULE / "evidence").resolve()) and
            identity(receipt_path) == frozen["receipt_identity"], "Wrong retained test receipt")
    manifest = verify_manifest(receipt_path.parent)
    receipt = read_json(receipt_path)
    require(receipt.get("tests_passed") is True and receipt.get("failures") == receipt.get("errors") == receipt.get("skipped") == 0 and
            type(receipt.get("tests_run")) is int and receipt["tests_run"] > 0 and
            receipt.get("scientific_search_performed") is False, "Tests not fully green")
    validate_source_receipt(receipt, "tests")
    frozen_artifact(frozen, "tests", receipt)
    require(seal_frozen_files(descriptor_path, receipt_path.parent, manifest) != receipt["implementation_sha"],
            "Tests require a separate retained-data commit")
    return receipt


def preflight(selected, output):
    provenance = authenticate()
    require(phase(os.environ.get("COMMIT_MESSAGE", "")) == selected, "Wrong requested phase")
    grant = grant_for(selected)
    usage = runner_usage()
    check_allowance(selected, usage, grant)
    if selected != "tests":
        validated_tests()
    if selected == "pilot":
        from .driver import load_frozen_banks
        load_frozen_banks(check_scores=False)
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    permit = {**provenance, "phase": selected, "grant": grant, "usage": usage,
              "resource_authorization_identity": identity(MODULE / "resource_authorization.json"),
              "reserved_runner_minutes": RESERVATIONS[selected]}
    write_json(output / "permit.json", permit)
    write_manifest(output)
    if os.environ.get("GITHUB_OUTPUT"):
        with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as stream:
            stream.write("phase=" + selected + "\n")
            stream.write("worker_matrix=" + json.dumps({"worker": list(PILOT_TASKS) if selected == "pilot" else []}) + "\n")
    return permit


def check_permit(directory, selected):
    provenance = authenticate(runtime=True)
    require(phase(os.environ.get("COMMIT_MESSAGE", "")) == selected, "Wrong worker phase marker")
    verify_manifest(directory)
    permit = read_json(Path(directory) / "permit.json")
    for field in ("protocol_id", "registration_sha", "implementation_sha", "source_manifest", "run_id", "run_attempt"):
        require(permit.get(field) == provenance[field], "Stale or mixed permit: " + field)
    grant = grant_for(selected)
    require(permit.get("phase") == selected and permit.get("grant") == grant and
            permit.get("resource_authorization_identity") == identity(MODULE / "resource_authorization.json") and
            permit.get("reserved_runner_minutes") == RESERVATIONS[selected], "Changed resource permit")
    check_allowance(selected, permit["usage"], grant)
    return provenance
