"""Independent fail-closed authority for the registered 60-minute technical stage."""
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
import zipfile

ROOT = Path(__file__).resolve().parents[3]
MODULE = Path(__file__).resolve().parent
REL = "studies/knapsack_parameters/stagnation_diagnosis/"
WORKFLOW = ".github/workflows/knapsack-stagnation-diagnosis.yml"
PROTOCOL_ID = "GA-KNAPSACK-STAGNATION-DIAGNOSIS-V1"
REGISTRATION_SHA = "f5e965d3cb7ca1c9450f40576400d0410e421edf"
REPOSITORY = "ChepaMaksym/GA-article-test"
BRANCH = "research/masters-ga-diversity-crossover"
RESERVATIONS = {"tests": 12, "prepare": 9, "probe": 31}
MAX_BYTES = 536870912
PROBE_CASES = ("UC-s000", "SC-s005", "SC-s000")
PROVENANCE_KEYS = ("protocol_id", "registration_commit_sha", "implementation_commit_sha",
                   "protocol_sha256", "implementation_fingerprint", "data_manifest_sha256",
                   "registry_sha256", "run_id", "run_attempt")


def require(condition, message):
    if not condition:
        raise ValueError(message)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
                      allow_nan=False).encode("utf-8")


def identity(path):
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
    with tempfile.NamedTemporaryFile(mode="wb", prefix="." + path.name + ".", suffix=".part",
                                     dir=path.parent, delete=False) as stream:
        temporary = Path(stream.name)
        stream.write(canonical(value) + b"\n")
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)


def safe_path(root, relative):
    require(type(relative) is str, "Artifact path must be text")
    pure = PurePosixPath(relative)
    require(relative and relative not in (".", "..") and not pure.is_absolute() and
            ".." not in pure.parts and ":" not in relative and "\\" not in relative,
            "Unsafe artifact member")
    root = Path(root).resolve()
    result = root.joinpath(*pure.parts)
    require(result.resolve().is_relative_to(root) and not result.is_symlink(), "Artifact escapes root")
    return result


def write_manifest(directory):
    # Pure byte-level transport helpers, not the historical execution authority.
    from ..ga_study.contract import write_file_manifest
    return write_file_manifest(directory)


def verify_manifest(directory):
    from ..ga_study.contract import verify_file_manifest
    return verify_file_manifest(directory)


def phase(message):
    markers = re.findall(r"\[([^\[\]\r\n]+)\]", message)
    require(len(markers) == 1 and markers[0] in
            tuple("knapsack-stagnation:" + p for p in RESERVATIONS),
            "Exactly one registered stagnation marker is required")
    return markers[0].split(":", 1)[1]


def source_manifest():
    protocol = read_json(MODULE / "protocol.json")
    paths = list(MODULE.rglob("*.py")) + [MODULE / "protocol.json", MODULE / "PROTOCOL_UK.md", ROOT / WORKFLOW]
    paths += [ROOT / name for name in protocol["frozen_files"]]
    paths += [ROOT / "studies/knapsack_parameters/inputs/data_manifest.json",
              ROOT / "studies/knapsack_parameters/inputs/file_manifest.json",
              ROOT / "studies/knapsack_parameters/evidence/run-37637475385/registry.json"]
    rows = [{"path": p.relative_to(ROOT).as_posix(), **identity(p)} for p in sorted(set(paths))]
    return {"files": rows, "sha256": hashlib.sha256(canonical(rows)).hexdigest()}


def fingerprint():
    return source_manifest()["sha256"]


def load_context():
    from ..feasibility.frozen_inputs import verify_input_bundle
    protocol = read_json(MODULE / "protocol.json")
    instances, manifest = verify_input_bundle()
    require(identity(ROOT / "studies/knapsack_parameters/inputs/data_manifest.json")["sha256"] ==
            protocol["data_manifest_sha256"], "Frozen data manifest changed")
    path = ROOT / "studies/knapsack_parameters/evidence/run-37637475385/registry.json"
    require(identity(path)["sha256"] == protocol["registry_sha256"], "Frozen exact registry changed")
    registry = read_json(path)
    require(registry.get("all_30_accounted") is True and registry.get("case_count") == 30,
            "Incomplete original registry")
    cases = {row["instance_id"]: row for row in registry["cases"]}
    require(len(cases) == 30 and list(cases) == [i.instance_id for i in instances], "Input order differs")
    return instances, cases, manifest


def authenticate(runtime=False):
    require(os.environ.get("GITHUB_ACTIONS") == "true" and
            os.environ.get("GITHUB_REPOSITORY") == REPOSITORY and
            os.environ.get("GITHUB_REF") == "refs/heads/" + BRANCH, "Wrong CI repository or branch")
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    require(re.fullmatch(r"[0-9a-f]{40}", head) and
            head == os.environ.get("GITHUB_SHA") == os.environ.get("EXPECTED_SHA"), "Wrong exact checkout")
    subprocess.run(["git", "merge-base", "--is-ancestor", REGISTRATION_SHA, head], cwd=ROOT, check=True)
    for name in ("protocol.json", "PROTOCOL_UK.md"):
        anchored = subprocess.check_output(["git", "show", REGISTRATION_SHA + ":" + REL + name], cwd=ROOT)
        require(anchored == (MODULE / name).read_bytes(), "Registered protocol bytes changed")
    changed = subprocess.check_output(["git", "diff", "--name-only", REGISTRATION_SHA, head],
                                      cwd=ROOT, text=True).splitlines()
    require(all(name.startswith(REL) or name == WORKFLOW for name in changed), "Historical files changed")
    require(not subprocess.check_output(["git", "status", "--porcelain", "--untracked-files=no"],
                                       cwd=ROOT, text=True).strip(), "Dirty tracked checkout")
    protocol = read_json(MODULE / "protocol.json")
    require(protocol["protocol_id"] == PROTOCOL_ID and
            protocol["resource_policy"]["phase_reservations_runner_minutes"] == RESERVATIONS and
            protocol["resource_policy"]["technical_ceiling_runner_minutes"] == 60 and
            protocol["execution"]["full_main_series_authorized"] is False, "Resource grant differs")
    for name, digest in protocol["frozen_files"].items():
        require(identity(ROOT / name)["sha256"] == digest, "Protected dependency changed: " + name)
    load_context()
    result = {"protocol_id": PROTOCOL_ID, "registration_commit_sha": REGISTRATION_SHA,
              "implementation_commit_sha": head, "protocol_sha256": identity(MODULE / "protocol.json")["sha256"],
              "implementation_fingerprint": fingerprint(), "data_manifest_sha256": protocol["data_manifest_sha256"],
              "registry_sha256": protocol["registry_sha256"], "run_id": int(os.environ["GITHUB_RUN_ID"]),
              "run_attempt": int(os.environ.get("GITHUB_RUN_ATTEMPT", "1"))}
    if runtime:
        require(platform.python_implementation() == "CPython" and platform.python_version() == "3.12.14",
                "Wrong exact Python runtime")
        lock = read_json(ROOT / "studies/knapsack_parameters/ga_study/dependencies/environment.lock.json")
        packages = {row["name"]: importlib.metadata.version(row["name"]) for row in lock["packages"]}
        require(all(packages[row["name"]] == row["version"] for row in lock["packages"]), "Dependency version differs")
        result["environment"] = {"implementation": platform.python_implementation(),
                                 "python": platform.python_version(), "packages": packages,
                                 "lock_sha256": identity(ROOT / "studies/knapsack_parameters/ga_study/dependencies/environment.lock.json")["sha256"]}
    return result


def api(path):
    require(path.startswith("/actions/") and ".." not in path, "Invalid GitHub API endpoint")
    token = os.environ.get("GITHUB_TOKEN")
    require(token, "Authenticated API accounting required")
    request = urllib.request.Request("https://api.github.com/repos/" + REPOSITORY + path,
        headers={"Authorization": "Bearer " + token, "Accept": "application/vnd.github+json",
                 "User-Agent": "ga-stagnation-authority"})
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response)


def pages(path, key):
    result, page = [], 1
    while True:
        data = api(path + ("&" if "?" in path else "?") + f"per_page=100&page={page}")
        batch = data[key]
        require(type(batch) is list, "Malformed paginated API result")
        result.extend(batch)
        if len(batch) < 100:
            return result
        page += 1


def job_minutes(job):
    require(job.get("status") == "completed" and job.get("conclusion") and
            job.get("started_at") and job.get("completed_at"), "Unknown allocated job duration")
    elapsed = (datetime.fromisoformat(job["completed_at"].replace("Z", "+00:00")) -
               datetime.fromisoformat(job["started_at"].replace("Z", "+00:00"))).total_seconds()
    require(math.isfinite(elapsed) and elapsed >= 0, "Invalid job duration")
    return max(1, math.ceil(elapsed / 60))


def runner_usage():
    current = (int(os.environ["GITHUB_RUN_ID"]), int(os.environ.get("GITHUB_RUN_ATTEMPT", "1")))
    endpoint = "/actions/workflows/" + Path(WORKFLOW).name + "/runs?branch=" + urllib.parse.quote(BRANCH, safe="")
    rows, seen_runs, seen_jobs, current_seen = [], set(), set(), False
    for run in pages(endpoint, "workflow_runs"):
        require(type(run.get("id")) is int and run["id"] not in seen_runs, "Invalid or duplicate run")
        seen_runs.add(run["id"])
        require(run["id"] == current[0] or run.get("status") == "completed", "Concurrent usage unknown")
        require(type(run.get("run_attempt")) is int and run["run_attempt"] >= 1, "Missing attempt history")
        for attempt in range(1, run["run_attempt"] + 1):
            here = (run["id"], attempt) == current
            current_seen |= here
            for job in pages(f"/actions/runs/{run['id']}/attempts/{attempt}/jobs", "jobs"):
                if job.get("conclusion") == "skipped":
                    continue
                require(type(job.get("id")) is int and job["id"] not in seen_jobs, "Invalid or duplicate allocated job")
                seen_jobs.add(job["id"])
                if here and job.get("name") == "gate" and job.get("status") == "in_progress":
                    # The entire current gate is already inside this phase reservation.
                    continue
                if here and job.get("status") == "queued" and not job.get("started_at"):
                    continue
                rows.append({"run_id": run["id"], "run_attempt": attempt, "job_id": job["id"],
                             "minutes": job_minutes(job), "conclusion": job["conclusion"]})
    require(current_seen, "Current accounting run missing from API")
    return {"used_runner_minutes": sum(row["minutes"] for row in rows), "jobs": rows,
            "current_gate_covered_by_reservation": True}


def check_allowance(usage, selected):
    require(selected in RESERVATIONS, "Unregistered resource phase")
    used = usage.get("used_runner_minutes")
    require(type(used) is int and used >= 0 and used + RESERVATIONS[selected] <= 60,
            "Insufficient cumulative technical allowance")


def _download_zip(metadata, destination):
    require(metadata.get("expired") is False and type(metadata.get("id")) is int and
            type(metadata.get("size_in_bytes")) is int and 0 < metadata["size_in_bytes"] <= MAX_BYTES and
            re.fullmatch(r"sha256:[0-9a-f]{64}", str(metadata.get("digest"))), "Invalid artifact metadata")
    request = urllib.request.Request(
        f"https://api.github.com/repos/{REPOSITORY}/actions/artifacts/{metadata['id']}/zip",
        headers={"Authorization": "Bearer " + os.environ["GITHUB_TOKEN"], "Accept": "application/vnd.github+json",
                 "User-Agent": "ga-stagnation-evidence"})
    class StorageRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, newurl):
            require(newurl.startswith("https://"), "Non-HTTPS artifact redirect")
            return urllib.request.Request(newurl, headers={"User-Agent": "ga-stagnation-evidence"})
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=True)
    require(not any(destination.iterdir()), "Refuse transport directory overwrite")
    temporary = destination.parent / ("." + destination.name + ".zip.part")
    require(not temporary.exists(), "Refuse ZIP overwrite")
    digest, count = hashlib.sha256(), 0
    with urllib.request.build_opener(StorageRedirect()).open(request, timeout=45) as response, temporary.open("xb") as stream:
        while block := response.read(1024 * 1024):
            count += len(block)
            require(count <= MAX_BYTES, "Artifact exceeds compressed byte limit")
            stream.write(block)
            digest.update(block)
    require(count == metadata["size_in_bytes"] and "sha256:" + digest.hexdigest() == metadata["digest"],
            "ZIP checksum/size differs")
    with zipfile.ZipFile(temporary) as archive:
        seen, total = set(), 0
        for member in archive.infolist():
            relative = member.filename.rstrip("/")
            safe_path(destination, relative)
            total += member.file_size
            require(relative not in seen and total <= 2147483648 and not member.flag_bits & 1 and
                    (member.external_attr >> 16) & 0o170000 != 0o120000, "Unsafe or duplicate ZIP member")
            seen.add(relative)
        archive.extractall(destination)
    temporary.unlink()
    verify_manifest(destination)
    return {"artifact_id": metadata["id"], "zip_sha256": digest.hexdigest(), "zip_bytes": count,
            "file_manifest_sha256": identity(destination / "file_manifest.json")["sha256"]}


def frozen_bundle(kind, destination):
    require(kind in ("tests", "banks"), "Unknown frozen evidence type")
    descriptor_path = MODULE / ("frozen_tests.json" if kind == "tests" else "frozen_banks.json")
    frozen = read_json(descriptor_path)
    require(frozen.get("schema") == "knapsack-stagnation-freeze-v1" and
            frozen.get("protocol_id") == PROTOCOL_ID and frozen.get("frozen") is True and
            frozen.get("implementation_fingerprint") == fingerprint(), "Missing or stale frozen evidence")
    receipt_path = safe_path(MODULE, frozen["receipt_path"])
    require(frozen["receipt_path"].startswith("evidence/") and
            identity(receipt_path)["sha256"] == frozen.get("receipt_sha256"), "Frozen receipt changed")
    stage = "tests" if kind == "tests" else "prepare"
    run = api(f"/actions/runs/{frozen['run_id']}/attempts/{frozen['run_attempt']}")
    require(run.get("conclusion") == "success" and run.get("head_sha") == frozen.get("implementation_commit_sha") and
            run.get("head_branch") == BRANCH and run.get("event") == "push" and run.get("path") == WORKFLOW and
            phase(run.get("head_commit", {}).get("message", "")) == stage, "Wrong frozen source run")
    subprocess.run(["git", "merge-base", "--is-ancestor", frozen["implementation_commit_sha"], os.environ["GITHUB_SHA"]],
                   cwd=ROOT, check=True)
    metadata = api(f"/actions/artifacts/{frozen['artifact_id']}")
    require(metadata.get("workflow_run", {}).get("id") == frozen["run_id"] and
            metadata.get("workflow_run", {}).get("head_sha") == frozen["implementation_commit_sha"] and
            metadata.get("digest") == "sha256:" + frozen.get("zip_sha256", "") and
            metadata.get("name") == f"knapsack-stagnation-{stage}-{frozen['run_id']}-{frozen['run_attempt']}",
            "Foreign frozen artifact")
    transport = _download_zip(metadata, destination)
    require(transport["file_manifest_sha256"] == frozen.get("file_manifest_sha256"), "Frozen member ledger differs")
    receipt_name = "tests_receipt.json" if kind == "tests" else "preparation_receipt.json"
    require((Path(destination) / receipt_name).read_bytes() == receipt_path.read_bytes(), "Downloaded receipt differs")
    receipt = read_json(receipt_path)
    require(all(receipt.get(k) == frozen.get(k) for k in
                ("run_id", "run_attempt", "implementation_commit_sha", "implementation_fingerprint")) and
            receipt.get("protocol_id") == PROTOCOL_ID and receipt.get("registration_commit_sha") == REGISTRATION_SHA,
            "Mixed receipt provenance")
    if kind == "tests":
        require(receipt.get("tests_passed") is True and type(receipt.get("tests_run")) is int and
                receipt["tests_run"] > 0 and all(receipt.get(k) == 0 for k in ("failures", "errors", "skipped")),
                "Invalid green test receipt")
    else:
        require(receipt.get("bank_count") == 903 and receipt.get("status") == "COMPLETE_VERIFIED_INPUTS",
                "Incomplete initial bank preparation")
    return receipt, transport


def gate(output, selected):
    provenance = authenticate()
    require(phase(os.environ.get("COMMIT_MESSAGE", "")) == selected, "Wrong phase marker")
    usage = runner_usage()
    check_allowance(usage, selected)
    checks = {}
    if selected in ("prepare", "probe"):
        with tempfile.TemporaryDirectory(prefix="stagnation-green-") as directory:
            checks["tests_receipt"], checks["tests_transport"] = frozen_bundle("tests", Path(directory) / "tests")
    if selected == "probe":
        with tempfile.TemporaryDirectory(prefix="stagnation-banks-") as directory:
            checks["banks_receipt"], checks["banks_transport"] = frozen_bundle("banks", Path(directory) / "banks")
    output = Path(output)
    write_json(output / "permit.json", {**provenance, **usage, "phase": selected,
        "reserved_runner_minutes": RESERVATIONS[selected], "technical_ceiling_runner_minutes": 60,
        "main_search_authorized": False, "checks": checks})
    write_manifest(output)


def check_permit(directory, selected):
    provenance = authenticate(runtime=True)
    expected = "probe" if selected in ("worker", "aggregate") else selected
    require(expected in RESERVATIONS and phase(os.environ.get("COMMIT_MESSAGE", "")) == expected,
            "Wrong worker phase")
    verify_manifest(directory)
    permit = read_json(Path(directory) / "permit.json")
    require(all(permit.get(k) == provenance[k] for k in PROVENANCE_KEYS) and permit.get("phase") == expected and
            permit.get("reserved_runner_minutes") == RESERVATIONS[expected] and
            permit.get("technical_ceiling_runner_minutes") == 60 and permit.get("main_search_authorized") is False,
            "Wrong bounded execution permit")
    check_allowance(permit, expected)
    return provenance


def download_current(destination, kind):
    provenance = authenticate()
    require(kind in ("permit", "workers"), "Unknown current artifact type")
    suffix = f"-{provenance['run_id']}-{provenance['run_attempt']}"
    prefix = "knapsack-stagnation-"
    rows = pages(f"/actions/runs/{provenance['run_id']}/artifacts", "artifacts")
    selected = [r for r in rows if (r["name"] == prefix + "permit" + suffix if kind == "permit" else
                r["name"].startswith(prefix + "worker-") and r["name"].endswith(suffix))]
    require((kind != "permit" or len(selected) == 1) and
            len({r["name"] for r in selected}) == len(selected), "Missing or duplicate current artifacts")
    destination = Path(destination)
    ledger = []
    if kind == "workers":
        write_json(destination / "transport_ledger.json", {**provenance, "artifacts": ledger})
    for row in selected:
        require(re.fullmatch(r"[A-Za-z0-9_.-]+", row["name"]), "Unsafe artifact name")
        metadata = api(f"/actions/artifacts/{row['id']}")
        require(metadata.get("workflow_run", {}).get("head_sha") == provenance["implementation_commit_sha"] and
                metadata.get("workflow_run", {}).get("id") == provenance["run_id"] and
                metadata.get("name") == row["name"] and metadata.get("digest") == row.get("digest"),
                "Mixed current artifact provenance")
        target = destination if kind == "permit" else destination / row["name"]
        transport = _download_zip(metadata, target)
        receipt_name = "permit.json" if kind == "permit" else "worker_summary.json"
        receipt = read_json(target / receipt_name)
        require(all(receipt.get(k) == provenance[k] for k in PROVENANCE_KEYS), "Foreign artifact receipt")
        ledger.append({"name": row["name"], **transport})
        if kind == "workers":
            write_json(destination / "transport_ledger.json", {**provenance, "artifacts": ledger})
    return ledger
