"""Independent, cumulative authority for the registered 90-minute probe only."""
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
REL = "studies/knapsack_parameters/final_study/"
WORKFLOW = ".github/workflows/knapsack-final-study.yml"
PROTOCOL = "GA-KNAPSACK-FINAL-COMPARISON-V1"
REGISTRATION_SHA = "a4306032c51b47a00fcac7f81a5dc8b97cbcc829"
REPOSITORY = "ChepaMaksym/GA-article-test"
BRANCH = "research/masters-ga-diversity-crossover"
METHODS = ("classical", "adaptive_mutation", "adaptive_crossover", "unbalanced_gap", "balanced_gap")
CONDITIONS = (("UC-s000", "cloned"), ("SC-s005", "bank"))
RESERVATIONS = {"tests": 8, "probe": 76}
MAX_BYTES = 536870912


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
    # Never expose a truncated index/manifest if a worker is interrupted.
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="wb", prefix="." + path.name + ".", suffix=".part",
                                         dir=path.parent, delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(canonical(value) + b"\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        temporary = None
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def phase(message):
    markers = re.findall(r"\[([^\[\]\r\n]+)\]", message)
    require(markers in (["knapsack-final:tests"], ["knapsack-final:probe"]),
            "Exactly one registered final-study marker required")
    return markers[0].split(":")[1]


def resource_grant():
    grant = read_json(MODULE / "resource_authorization.json")
    expected = {
        "protocol_id": PROTOCOL, "explicit_user_approval": True,
        "runner_minutes_ceiling": 90, "phase_reservation_minutes": RESERVATIONS,
        "job_timeout_minutes": {"tests": 6, "gate": 1, "probe": 5, "aggregate": 8},
        "max_parallel": 4, "maximum_compressed_bytes_per_job": MAX_BYTES,
        "probe_conditions": [{"task": task, "start": start} for task, start in CONDITIONS],
        "methods": list(METHODS), "probe_seed": 86001, "probe_expected_runs": 10,
        "new_evaluations_per_run": 5000,
        "main_search_authorized": False, "remaining_30_pilot_runs_authorized": False,
        "holdout_search_authorized": False, "lambda_search_authorized": False,
        "confirmatory_statistics_authorized": False,
    }
    require(type(grant) is dict, "Invalid final-study resource authorization")
    for name, value in expected.items():
        require(name in grant and canonical(grant[name]) == canonical(value),
                "Frozen resource field differs: " + name)
    return grant


def source_manifest():
    registration = read_json(MODULE / "registration.json")
    files = list(MODULE.rglob("*.py"))
    files += [MODULE / name for name in (".gitattributes", "PROTOCOL_UK.md", "registration.json",
                                         "resource_authorization.json")]
    files += [ROOT / WORKFLOW]
    files += [ROOT / name for name in registration["protected_sha256"]]
    rows = [{"path": path.relative_to(ROOT).as_posix(), **identity(path)} for path in sorted(set(files))]
    return {"files": rows, "sha256": hashlib.sha256(canonical(rows)).hexdigest()}


def authenticate(runtime=False):
    require(os.environ.get("GITHUB_ACTIONS") == "true" and
            os.environ.get("GITHUB_REPOSITORY") == REPOSITORY and
            os.environ.get("GITHUB_REF") == "refs/heads/" + BRANCH,
            "Wrong CI repository or branch")
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    require(head == os.environ.get("GITHUB_SHA") == os.environ.get("EXPECTED_SHA"), "Wrong exact checkout")
    subprocess.run(["git", "merge-base", "--is-ancestor", REGISTRATION_SHA, head], cwd=ROOT, check=True)
    for name in ("PROTOCOL_UK.md", "registration.json", "resource_authorization.json", ".gitattributes"):
        original = subprocess.check_output(["git", "show", REGISTRATION_SHA + ":" + REL + name], cwd=ROOT)
        require(original == (MODULE / name).read_bytes(), "Frozen final-study contract changed: " + name)
    registration = read_json(MODULE / "registration.json")
    changed = subprocess.check_output(["git", "diff", "--name-only", registration["base_sha"], head],
                                      cwd=ROOT, text=True).splitlines()
    require(all(name.startswith(REL) or name == WORKFLOW for name in changed), "Historical files changed")
    for name, digest in registration["protected_sha256"].items():
        require(identity(ROOT / name)["sha256"] == digest, "Historical input/dependency changed: " + name)
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
    require(path.startswith("/actions/") and ".." not in path, "Invalid GitHub API endpoint")
    token = os.environ.get("GITHUB_TOKEN")
    require(token, "Authenticated API accounting required")
    request = urllib.request.Request("https://api.github.com/repos/" + REPOSITORY + path,
        headers={"Authorization": "Bearer " + token, "Accept": "application/vnd.github+json",
                 "User-Agent": "ga-final-study-accounting"})
    with urllib.request.urlopen(request, timeout=15) as response:
        return json.load(response)


def pages(path, key):
    result, page = [], 1
    while True:
        batch = api(path + ("&" if "?" in path else "?") + f"per_page=100&page={page}")[key]
        require(type(batch) is list, "Malformed paginated API result")
        result.extend(batch)
        if len(batch) < 100:
            return result
        page += 1


def runner_usage():
    endpoint = "/actions/workflows/" + Path(WORKFLOW).name + "/runs?branch=" + urllib.parse.quote(BRANCH, safe="")
    current = (int(os.environ["GITHUB_RUN_ID"]), int(os.environ.get("GITHUB_RUN_ATTEMPT", "1")))
    rows, seen_runs, seen_jobs = [], set(), set()
    for run in pages(endpoint, "workflow_runs"):
        require(type(run.get("id")) is int and run["id"] not in seen_runs, "Duplicate or invalid workflow run")
        seen_runs.add(run["id"])
        require(run["id"] == current[0] or run.get("status") == "completed", "Concurrent usage unknown")
        require(type(run.get("run_attempt")) is int and run["run_attempt"] >= 1, "Missing attempt history")
        for attempt in range(1, run["run_attempt"] + 1):
            if (run["id"], attempt) == current:
                continue
            for job in pages(f"/actions/runs/{run['id']}/attempts/{attempt}/jobs", "jobs"):
                if job.get("conclusion") == "skipped":
                    continue
                require(type(job.get("id")) is int and job["id"] not in seen_jobs, "Duplicate or invalid allocated job")
                seen_jobs.add(job["id"])
                require(job.get("started_at") and job.get("completed_at") and job.get("conclusion"),
                        "Unknown allocated job duration")
                seconds = (datetime.fromisoformat(job["completed_at"].replace("Z", "+00:00")) -
                           datetime.fromisoformat(job["started_at"].replace("Z", "+00:00"))).total_seconds()
                require(math.isfinite(seconds) and seconds >= 0, "Negative or invalid allocated duration")
                rows.append({"run_id": run["id"], "attempt": attempt, "job_id": job["id"],
                             "conclusion": job["conclusion"], "minutes": max(1, math.ceil(seconds / 60))})
    return {"used_runner_minutes": sum(row["minutes"] for row in rows), "prior_jobs": rows}


def check_allowance(usage, selected, grant):
    require(selected in RESERVATIONS, "Unregistered resource phase")
    used = usage.get("used_runner_minutes")
    require(type(used) is int and used >= 0 and used + RESERVATIONS[selected] <= grant["runner_minutes_ceiling"],
            "Insufficient cumulative final-study allowance")


def write_manifest(directory):
    root = Path(directory)
    write_json(root / "file_manifest.json", {"protocol_id": PROTOCOL,
        "files": [{"path": path.relative_to(root).as_posix(), **identity(path)}
                  for path in sorted(root.rglob("*")) if path.is_file() and path.name != "file_manifest.json"]})


def verify_manifest(directory):
    root = Path(directory).resolve()
    manifest = read_json(root / "file_manifest.json")
    require(manifest.get("protocol_id") == PROTOCOL and type(manifest.get("files")) is list,
            "Wrong artifact protocol or manifest schema")
    seen = set()
    for row in manifest["files"]:
        require(type(row) is dict and set(row) == {"path", "bytes", "sha256"}, "Malformed artifact identity")
        name = row["path"]
        require(type(name) is str, "Unsafe artifact path")
        relative = PurePosixPath(name)
        require(name and name not in seen and not relative.is_absolute() and ".." not in relative.parts and
                ":" not in name and "\\" not in name and name != "file_manifest.json", "Unsafe artifact member")
        path = root / relative
        require(path.resolve().is_relative_to(root) and not path.is_symlink() and
                type(row["bytes"]) is int and row["bytes"] >= 0 and
                identity(path) == {"bytes": row["bytes"], "sha256": row["sha256"]}, "Artifact checksum mismatch")
        seen.add(name)
    require(seen | {"file_manifest.json"} ==
            {p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file()}, "Incomplete artifact manifest")
    return manifest


def validated_tests():
    frozen = read_json(MODULE / "frozen_tests.json")
    require(frozen.get("protocol_id") == PROTOCOL and frozen.get("frozen") is True, "Green checks not frozen")
    name = frozen.get("receipt_directory")
    require(type(name) is str, "Unsafe green receipt path")
    relative = PurePosixPath(name)
    require(name.startswith("evidence/") and ".." not in relative.parts and not relative.is_absolute() and
            ":" not in name and "\\" not in name, "Unsafe green receipt path")
    directory = MODULE / relative
    verify_manifest(directory)
    receipt = read_json(directory / "tests_receipt.json")
    require(receipt.get("protocol_id") == PROTOCOL and receipt.get("tests_passed") is True and
            type(receipt.get("tests_run")) is int and receipt["tests_run"] > 0 and
            all(type(receipt.get(name)) is int and receipt[name] == 0 for name in ("failures", "errors", "skipped")) and
            receipt.get("scientific_KPLIB_search_performed") is False and
            receipt.get("lambda_search_performed") is False, "Invalid green software receipt")
    run = api(f"/actions/runs/{receipt['run_id']}/attempts/{receipt['run_attempt']}")
    require(run.get("conclusion") == "success" and run.get("head_sha") == receipt.get("implementation_sha") and
            run.get("head_branch") == BRANCH and run.get("event") == "push" and run.get("path") == WORKFLOW and
            phase(run.get("head_commit", {}).get("message", "")) == "tests", "Foreign or unsuccessful green run")
    subprocess.run(["git", "merge-base", "--is-ancestor", receipt["implementation_sha"], os.environ["GITHUB_SHA"]],
                   cwd=ROOT, check=True)
    current = source_manifest()
    require(receipt.get("source_manifest") == current, "Source fingerprint changed since green checks")
    from .inputs import probe_binding
    require(receipt.get("input_binding") == probe_binding(), "Green checks bound different initial inputs")
    for row in current["files"]:
        original = subprocess.check_output(["git", "show", receipt["implementation_sha"] + ":" + row["path"]], cwd=ROOT)
        require(hashlib.sha256(original).hexdigest() == row["sha256"], "Green source bytes differ")
    artifact = api(f"/actions/artifacts/{frozen['artifact_id']}")
    require(artifact.get("workflow_run", {}).get("id") == receipt["run_id"] and
            artifact.get("workflow_run", {}).get("head_sha") == receipt["implementation_sha"] and
            artifact.get("digest") == "sha256:" + frozen.get("zip_sha256", "") and
            artifact.get("expired") is False, "Green artifact unavailable or changed")
    return receipt


def gate(output, selected):
    provenance = authenticate()
    require(phase(os.environ.get("COMMIT_MESSAGE", "")) == selected, "Wrong execution phase marker")
    grant, usage = resource_grant(), runner_usage()
    check_allowance(usage, selected, grant)
    green = None
    if selected == "probe":
        green = validated_tests()
        from .inputs import load_probe_bank, validate_probe_freeze
        validate_probe_freeze(provenance)
        for task, start in CONDITIONS:
            load_probe_bank(task, start, validate_initial=False)
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    write_json(output / "permit.json", {**provenance, **usage, "phase": selected,
        "resource_grant": grant, "reserved_runner_minutes": RESERVATIONS[selected],
        "green_tests_run": None if green is None else green["run_id"],
        "main_search_authorized": False, "holdout_search_authorized": False,
        "lambda_search_authorized": False})
    write_manifest(output)


def check_permit(directory, selected):
    provenance = authenticate(runtime=True)
    expected = "probe" if selected in ("worker", "aggregate") else selected
    require(expected in RESERVATIONS and phase(os.environ.get("COMMIT_MESSAGE", "")) == expected,
            "Wrong worker phase")
    verify_manifest(directory)
    permit = read_json(Path(directory) / "permit.json")
    for name in ("protocol_id", "registration_sha", "implementation_sha", "source_manifest", "run_id", "run_attempt"):
        require(permit.get(name) == provenance[name], "Stale or foreign central permit")
    grant = resource_grant()
    require(permit.get("phase") == expected and permit.get("resource_grant") == grant and
            permit.get("reserved_runner_minutes") == RESERVATIONS[expected] and
            all(permit.get(name) is False for name in
                ("main_search_authorized", "holdout_search_authorized", "lambda_search_authorized")),
            "Wrong bounded execution permit")
    check_allowance(permit, expected, grant)
    # Central reservation covers all parallel jobs; workers must not re-scan it.
    return provenance


def download_artifacts(destination, kind):
    authenticate()
    require(kind in ("permit", "workers"), "Unknown artifact kind")
    run_id, attempt = int(os.environ["GITHUB_RUN_ID"]), int(os.environ.get("GITHUB_RUN_ATTEMPT", "1"))
    suffix = f"-{run_id}-{attempt}"
    artifacts = pages(f"/actions/runs/{run_id}/artifacts", "artifacts")
    chosen = [row for row in artifacts if (row["name"] == "knapsack-final-permit" + suffix if kind == "permit" else
              row["name"].startswith("knapsack-final-worker-") and row["name"].endswith(suffix))]
    require((kind != "permit" or len(chosen) == 1) and
            len({row["name"] for row in chosen}) == len(chosen), "Missing or duplicate current artifacts")
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=True)
    for row in chosen:
        require(row.get("expired") is False and re.fullmatch(r"[A-Za-z0-9_.-]+", row["name"]) and
                row.get("digest", "").startswith("sha256:") and
                type(row.get("size_in_bytes")) is int and 0 < row["size_in_bytes"] <= MAX_BYTES,
                "Unsafe, expired or excessive artifact")
        metadata = api(f"/actions/artifacts/{row['id']}")
        require(metadata.get("workflow_run", {}).get("head_sha") == os.environ["GITHUB_SHA"] and
                metadata.get("workflow_run", {}).get("id") == run_id and
                metadata.get("digest") == row["digest"], "Mixed artifact provenance")
        request = urllib.request.Request(f"https://api.github.com/repos/{REPOSITORY}/actions/artifacts/{row['id']}/zip",
            headers={"Authorization": "Bearer " + os.environ["GITHUB_TOKEN"],
                     "Accept": "application/vnd.github+json", "User-Agent": "ga-final-evidence"})
        class StorageRedirect(urllib.request.HTTPRedirectHandler):
            def redirect_request(self, req, fp, code, msg, headers, newurl):
                require(newurl.startswith("https://"), "Non-HTTPS artifact redirect")
                return urllib.request.Request(newurl, headers={"User-Agent": "ga-final-evidence"})
        temporary = destination / (row["name"] + ".zip.part")
        require(not temporary.exists(), "Refuse artifact overwrite")
        digest, size = hashlib.sha256(), 0
        with urllib.request.build_opener(StorageRedirect()).open(request, timeout=30) as response, temporary.open("xb") as stream:
            while chunk := response.read(1024 * 1024):
                size += len(chunk)
                require(size <= MAX_BYTES, "Artifact download exceeds limit")
                digest.update(chunk)
                stream.write(chunk)
        require(size == row["size_in_bytes"] and "sha256:" + digest.hexdigest() == row["digest"], "ZIP digest mismatch")
        target = destination if kind == "permit" else destination / row["name"]
        target.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(temporary) as archive:
            seen, expanded = set(), 0
            for entry in archive.infolist():
                relative = PurePosixPath(entry.filename)
                expanded += entry.file_size
                require(entry.filename not in seen and not relative.is_absolute() and ".." not in relative.parts and
                        ":" not in entry.filename and "\\" not in entry.filename and expanded <= 2147483648 and
                        (entry.external_attr >> 16) & 0o170000 != 0o120000, "Unsafe ZIP member")
                seen.add(entry.filename)
                path = target / relative
                require(path.resolve().is_relative_to(target.resolve()) and not path.exists(), "ZIP target collision")
            archive.extractall(target)
        temporary.unlink()
        verify_manifest(target)
    return [row["name"] for row in chosen]
