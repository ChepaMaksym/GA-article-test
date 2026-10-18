"""Separate 60-minute scientific pilot grant; no main or lambda release."""
from __future__ import annotations

import argparse
from datetime import datetime
import hashlib
import math
import os
from pathlib import Path, PurePosixPath
import re
import subprocess
import urllib.parse
import urllib.request
import zipfile

from . import authority as a

PROTOCOL = "GA-KNAPSACK-ADAPTATION-ANALYSIS-PILOT-V1"
REGISTRATION_SHA = "c5922a34e8b97503324be27f19c7c09e4e039114"
WORKFLOW = ".github/workflows/knapsack-adaptation-pilot.yml"
TASKS = ("UC-s000", "WC-s001", "SC-s005", "SC-s000")
STARTS = ("cloned", "bank")
RESERVATIONS = {"prepare": 5, "pilot": 49}
require = a.require


def phase(message):
    markers = re.findall(r"\[([^\[\]\r\n]+)\]", message)
    require(len(markers) == 1 and markers[0] in
            ("adaptation-pilot:prepare", "adaptation-pilot:pilot"), "Unregistered pilot phase")
    return markers[0].split(":")[1]


def resource_grant():
    path = a.MODULE / "pilot_resource_authorization.json"
    require(path.is_file(), "BLOCKED_PILOT_RESOURCE_APPROVAL")
    grant = a.read_json(path)
    expected = {
        "protocol_id": PROTOCOL,
        "parent_protocol_id": a.PROTOCOL,
        "explicit_user_approval": True,
        "allowed_phases": ["prepare", "pilot", "aggregate"],
        "runner_minutes_ceiling": 60,
        "phase_reservation_minutes": RESERVATIONS,
        "job_timeout_minutes": {"gate": 1, "prepare": 4, "pilot": 5, "aggregate": 8},
        "max_parallel": 4,
        "maximum_compressed_bytes_per_job": 536870912,
        "search_seed": 86001,
        "preparation_seed": 86000,
        "expected_initial_conditions": 8,
        "expected_search_runs": 40,
        "new_evaluations_per_run": 5000,
        "main_search_authorized": False,
        "lambda_search_authorized": False,
        "confirmatory_statistics_authorized": False,
    }
    require(type(grant) is dict, "Incompatible bounded pilot grant")
    for name, value in expected.items():
        # Canonical JSON also distinguishes bool/int/float inside nested maps.
        require(name in grant and a.canonical(grant[name]) == a.canonical(value),
                "Incompatible bounded pilot grant field: " + name)
    return grant


def authenticate(runtime=False):
    provenance = a.authenticate(runtime=runtime)
    subprocess.run(["git", "merge-base", "--is-ancestor", REGISTRATION_SHA,
                    provenance["implementation_sha"]], cwd=a.ROOT, check=True)
    for name in ("PILOT_EXECUTION_UK.md", "pilot_resource_authorization.json"):
        original = subprocess.check_output(["git", "show", REGISTRATION_SHA + ":" + a.REL + name], cwd=a.ROOT)
        require(original == (a.MODULE / name).read_bytes(), "Frozen pilot contract changed: " + name)
    resource_grant()
    return {**provenance, "pilot_protocol_id": PROTOCOL, "pilot_registration_sha": REGISTRATION_SHA}


def runner_usage():
    endpoint = "/actions/workflows/" + Path(WORKFLOW).name + "/runs?branch=" + urllib.parse.quote(a.BRANCH, safe="")
    current = (int(os.environ["GITHUB_RUN_ID"]), int(os.environ.get("GITHUB_RUN_ATTEMPT", "1")))
    rows, seen_runs, seen_jobs = [], set(), set()
    for run in a.pages(endpoint, "workflow_runs"):
        require(run["id"] not in seen_runs, "Duplicate pilot workflow run")
        seen_runs.add(run["id"])
        require(run["id"] == current[0] or run["status"] == "completed", "Concurrent pilot use unknown")
        for attempt in range(1, run["run_attempt"] + 1):
            if (run["id"], attempt) == current:
                continue
            for job in a.pages(f"/actions/runs/{run['id']}/attempts/{attempt}/jobs", "jobs"):
                if job.get("conclusion") == "skipped":
                    continue
                require(job["id"] not in seen_jobs, "Duplicate allocated pilot job")
                seen_jobs.add(job["id"])
                require(job.get("started_at") and job.get("completed_at"), "Unknown pilot duration")
                seconds = (datetime.fromisoformat(job["completed_at"].replace("Z", "+00:00")) -
                           datetime.fromisoformat(job["started_at"].replace("Z", "+00:00"))).total_seconds()
                require(seconds >= 0, "Negative pilot duration")
                rows.append({"run_id": run["id"], "attempt": attempt, "job_id": job["id"],
                             "conclusion": job["conclusion"], "minutes": max(1, math.ceil(seconds / 60))})
    return {"used_runner_minutes": sum(row["minutes"] for row in rows), "prior_jobs": rows}


def check_allowance(usage, selected, grant):
    require(selected in RESERVATIONS, "Unregistered resource phase")
    used = usage.get("used_runner_minutes")
    require(type(used) is int and used >= 0 and used + RESERVATIONS[selected] <= grant["runner_minutes_ceiling"],
            "Insufficient cumulative pilot allowance")


def _successful_source(receipt, workflow):
    run = a.api(f"/actions/runs/{receipt['run_id']}/attempts/{receipt['run_attempt']}")
    require(run.get("conclusion") == "success" and run.get("head_sha") == receipt.get("implementation_sha") and
            run.get("head_branch") == a.BRANCH and run.get("event") == "push" and run.get("path") == workflow,
            "Unsuccessful or foreign source run")
    subprocess.run(["git", "merge-base", "--is-ancestor", receipt["implementation_sha"],
                    os.environ["GITHUB_SHA"]], cwd=a.ROOT, check=True)
    require(receipt.get("source_manifest") == a.source_manifest(), "Source fingerprint changed")
    for row in a.source_manifest()["files"]:
        original = subprocess.check_output(["git", "show", receipt["implementation_sha"] + ":" + row["path"]], cwd=a.ROOT)
        require(hashlib.sha256(original).hexdigest() == row["sha256"], "Green source bytes differ")
    return run


def _artifact_identity(frozen, source):
    artifact = a.api(f"/actions/artifacts/{frozen['artifact_id']}")
    require(artifact.get("workflow_run", {}).get("id") == source["run_id"] and
            artifact.get("workflow_run", {}).get("head_sha") == source["implementation_sha"] and
            artifact.get("digest") == "sha256:" + frozen.get("zip_sha256", "") and
            artifact.get("expired") is False, "Source artifact identity unavailable or changed")
    return artifact


def validated_tests():
    frozen = a.read_json(a.MODULE / "frozen_tests.json")
    require(frozen.get("pilot_protocol_id") == PROTOCOL and frozen.get("frozen") is True,
            "Green tests have not been frozen")
    relative = PurePosixPath(frozen["receipt_directory"])
    require(str(relative).startswith("evidence/") and ".." not in relative.parts and not relative.is_absolute() and
            ":" not in str(relative) and "\\" not in str(relative),
            "Unsafe tests receipt path")
    directory = a.MODULE / relative
    a.verify_manifest(directory)
    receipt = a.read_json(directory / "tests_receipt.json")
    require(receipt.get("protocol_id") == a.PROTOCOL and receipt.get("tests_passed") is True and
            type(receipt.get("tests_run")) is int and receipt["tests_run"] >= 79 and
            receipt.get("failures") == 0 and receipt.get("errors") == 0 and receipt.get("skipped") == 0 and
            receipt.get("scientific_KPLIB_search_performed") is False and
            receipt.get("lambda_search_performed") is False, "Invalid green software receipt")
    _successful_source(receipt, a.WORKFLOW)
    _artifact_identity(frozen, receipt)
    return receipt


def gate(output, selected):
    provenance = authenticate()
    require(phase(os.environ.get("COMMIT_MESSAGE", "")) == selected, "Wrong pilot marker")
    grant = resource_grant()
    usage = runner_usage()
    check_allowance(usage, selected, grant)
    tests = validated_tests()
    if selected == "pilot":
        # Validation of frozen preparation is a gate, never a new selection.
        load_banks(validate_initial=False)
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    a.write_json(output / "pilot_permit.json", {**provenance, **usage, "phase": selected,
        "resource_grant": grant, "reserved_runner_minutes": RESERVATIONS[selected],
        "green_tests_run": tests["run_id"], "main_search_authorized": False,
        "lambda_search_authorized": False})
    a.write_manifest(output)


def check_permit(directory, selected):
    provenance = authenticate(runtime=True)
    expected = "pilot" if selected == "aggregate" else selected
    require(expected in RESERVATIONS and phase(os.environ.get("COMMIT_MESSAGE", "")) == expected,
            "Wrong worker phase")
    a.verify_manifest(directory)
    permit = a.read_json(Path(directory) / "pilot_permit.json")
    for field in ("protocol_id", "pilot_protocol_id", "pilot_registration_sha", "implementation_sha",
                  "source_manifest", "run_id", "run_attempt"):
        require(permit.get(field) == provenance[field], "Stale or foreign central pilot permit")
    grant = resource_grant()
    require(permit.get("phase") == expected and permit.get("resource_grant") == grant and
            permit.get("reserved_runner_minutes") == RESERVATIONS[expected] and
            permit.get("main_search_authorized") is False and permit.get("lambda_search_authorized") is False,
            "Wrong resource permit")
    check_allowance(permit, expected, grant)
    # No concurrent API re-scan here: the entire phase was reserved centrally.
    return provenance


def load_banks(validate_initial=True):
    from studies.knapsack_parameters.mutation_population.driver import source_task, independent_score
    root = a.MODULE / "inputs" / "pilot"
    a.verify_manifest(root)
    registry = a.read_json(root / "bank_registry.json")
    frozen = a.read_json(a.MODULE / "frozen_banks.json")
    require(frozen.get("pilot_protocol_id") == PROTOCOL and frozen.get("frozen") is True and
            frozen.get("registry_identity") == a.identity(root / "bank_registry.json"), "Preparation is not frozen")
    require(registry.get("schema") == "ga-adaptation-pilot-banks-v1" and
            registry.get("pilot_protocol_id") == PROTOCOL and registry.get("scope") == "pilot" and
            registry.get("initial_conditions") == 8 and registry.get("scientific_search_calls") == 0,
            "Wrong preparation scope")
    _successful_source(registry, WORKFLOW)
    source_run = a.api(f"/actions/runs/{registry['run_id']}/attempts/{registry['run_attempt']}")
    require(phase(source_run.get("head_commit", {}).get("message", "")) == "prepare", "Source is not preparation")
    _artifact_identity(frozen, registry)
    freeze_sha = subprocess.check_output(["git", "log", "-1", "--format=%H", "--", a.REL + "frozen_banks.json"],
                                         cwd=a.ROOT, text=True).strip()
    require(bool(freeze_sha) and freeze_sha != registry["implementation_sha"], "Banks need a separate freeze commit")
    frozen_changes = subprocess.check_output(["git", "diff", "--name-only", freeze_sha + "^", freeze_sha],
                                            cwd=a.ROOT, text=True).splitlines()
    require(bool(frozen_changes) and all(name.startswith(a.REL + "inputs/pilot/") or
            name == a.REL + "frozen_banks.json" for name in frozen_changes),
            "Bank freeze commit must contain data only")
    expected = {(task, start, 86001) for task in TASKS for start in STARTS}
    historical = a.read_json(a.ROOT / "studies/knapsack_parameters/evidence/run-37637475385/registry.json")
    result, seen = [], set()
    for row in registry["banks"]:
        key = (row["task"], row["start"], row["seed"])
        require(key in expected - seen, "Duplicate or unknown initial condition")
        seen.add(key)
        require(row["path"] == f"banks/{key[0]}-{key[1]}-{key[2]}.json", "Unsafe bank path")
        path = root / row["path"]
        require(a.identity(path) == {"bytes": row["bytes"], "sha256": row["sha256"]}, "Corrupted bank")
        bank = a.read_json(path)
        problem, case, source = source_task(key[0])
        ti, si = historical["case_order"].index(key[0]), STARTS.index(key[1])
        require(bank.get("problem") == problem and bank.get("source_identity") == source and
                bank.get("task") == key[0] and bank.get("start") == key[1] and
                bank.get("search_seed") == 86001 and bank.get("preparation_seed") == 86000 and
                bank.get("task_index") == ti and bank.get("start_index") == si and
                all(bank.get(field) == registry.get(field) for field in
                    ("protocol_id", "pilot_protocol_id", "implementation_sha", "source_manifest", "run_id", "run_attempt")),
                "Bank identity differs")
        if validate_initial:
            # Validation is not a second preparation evaluation. Reconstruct masks
            # and independently rescore them without invoking the search evaluator.
            from copy import deepcopy
            import numpy as np
            rng = np.random.Generator(np.random.PCG64(np.random.SeedSequence([86000, 86001, ti, si, 0])))
            before = deepcopy(rng.bit_generator.state)
            masks = ([case["certificate"]["center"]["mask"]] * 30 if key[1] == "cloned" else
                     ["0" * 100] + ["".join("1" if bit else "0" for bit in rng.random(100) < 0.5)
                                     for _ in range(29)])
            require(bank.get("initial_masks") == masks and bank.get("initial_scores") ==
                    [independent_score(problem, mask) for mask in masks] and
                    bank.get("initialization_before") == before and bank.get("initialization_after") == rng.bit_generator.state and
                    bank.get("physical_preparation_evaluations") == len(set(masks)) and
                    bank.get("independent_preparation_checks") == 30 and bank.get("logical_initial_positions") == 30,
                    "Independent bank reconstruction differs")
        result.append(bank)
    require(seen == expected and len(result) == 8, "Incomplete preparation")
    require(registry.get("physical_preparation_evaluations") ==
            sum(bank["physical_preparation_evaluations"] for bank in result) and
            registry.get("independent_preparation_checks") == 240, "Preparation counters differ")
    return result


def download_artifacts(destination, kind):
    """Fetch only current-run artifacts, verify GitHub ZIP digest and safe members."""
    authenticate()
    require(kind in ("permit", "workers"), "Unknown download kind")
    run_id, attempt = int(os.environ["GITHUB_RUN_ID"]), int(os.environ.get("GITHUB_RUN_ATTEMPT", "1"))
    suffix = f"-{run_id}-{attempt}"
    rows = a.pages(f"/actions/runs/{run_id}/artifacts", "artifacts")
    chosen = [row for row in rows if (row["name"] == "adaptation-pilot-permit" + suffix if kind == "permit" else
              row["name"].startswith("adaptation-pilot-worker-") and row["name"].endswith(suffix))]
    require((kind != "permit" or len(chosen) == 1) and len({row["name"] for row in chosen}) == len(chosen),
            "Missing or duplicate current permit")
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=True)
    for row in chosen:
        require(not row.get("expired") and re.fullmatch(r"[A-Za-z0-9_.-]+", row["name"]) and
                row.get("digest", "").startswith("sha256:") and row["size_in_bytes"] <= 536870912,
                "Unsafe, expired or excessive artifact")
        metadata = a.api(f"/actions/artifacts/{row['id']}")
        require(metadata.get("workflow_run", {}).get("head_sha") == os.environ["GITHUB_SHA"], "Mixed artifact SHA")
        request = urllib.request.Request(
            f"https://api.github.com/repos/{a.REPOSITORY}/actions/artifacts/{row['id']}/zip",
            headers={"Authorization": "Bearer " + os.environ["GITHUB_TOKEN"],
                     "Accept": "application/vnd.github+json", "User-Agent": "ga-pilot-evidence"})
        # urllib removes no header automatically on redirect; use a redirect handler
        # which deliberately strips credentials before following signed storage URLs.
        class StorageRedirect(urllib.request.HTTPRedirectHandler):
            def redirect_request(self, req, fp, code, msg, headers, newurl):
                require(newurl.startswith("https://"), "Non-HTTPS artifact redirect")
                return urllib.request.Request(newurl, headers={"User-Agent": "ga-pilot-evidence"})
        opener = urllib.request.build_opener(StorageRedirect())
        temporary = destination / (row["name"] + ".zip.part")
        require(not temporary.exists(), "Refuse artifact overwrite")
        size, digest = 0, hashlib.sha256()
        with opener.open(request, timeout=30) as response, temporary.open("xb") as stream:
            while data := response.read(1024 * 1024):
                size += len(data)
                require(size <= 536870912, "Artifact download exceeds limit")
                digest.update(data)
                stream.write(data)
        require(size == row["size_in_bytes"] and "sha256:" + digest.hexdigest() == row["digest"], "ZIP digest mismatch")
        target = destination if kind == "permit" else destination / row["name"]
        target.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(temporary) as archive:
            seen, expanded = set(), 0
            for entry in archive.infolist():
                rel = PurePosixPath(entry.filename)
                expanded += entry.file_size
                require(entry.filename not in seen and not rel.is_absolute() and ".." not in rel.parts and
                        ":" not in entry.filename and "\\" not in entry.filename and
                        (entry.external_attr >> 16) & 0o170000 != 0o120000 and expanded <= 2147483648,
                        "Unsafe artifact ZIP member")
                seen.add(entry.filename)
                path = target / rel
                require(path.resolve().is_relative_to(target.resolve()) and not path.exists(), "ZIP target collision")
            archive.extractall(target)
        temporary.unlink()
        a.verify_manifest(target)
    return [row["name"] for row in chosen]


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("operation", choices=("download",))
    parser.add_argument("--kind", choices=("permit", "workers"), required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    download_artifacts(args.output, args.kind)
