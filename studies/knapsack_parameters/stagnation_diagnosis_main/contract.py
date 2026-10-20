"""Fail-closed authority for the separate 200-minute, 8-GiB main-series grant."""
from __future__ import annotations

import hashlib
import os
from pathlib import Path
import platform
import re
import subprocess
import tempfile
import urllib.parse

from ..stagnation_diagnosis import contract as old

ROOT, MODULE = old.ROOT, Path(__file__).resolve().parent
REL = "studies/knapsack_parameters/stagnation_diagnosis_main/"
WORKFLOW = ".github/workflows/knapsack-stagnation-main.yml"
REGISTRATION_SHA = "03c9433304856c884d962d5095feeed2397ddbaa"
PROTOCOL_ID = "GA-KNAPSACK-STAGNATION-DIAGNOSIS-MAIN-V1"
SCIENTIFIC_ID = old.PROTOCOL_ID
TECHNICAL_FINGERPRINT = "bbe9cf6b252eca08bd40cfd1b830a3b87a94b91b33b9b0fb05a7c2daf9c72197"
BANK_SHA = "a1d8fc9b151d4a229727cfea209bb55b9d09f592a1511c3028df55f4929eba08"
RESERVATIONS = {"tests": 12, "main": 160}
BYTE_CEILING = 8 * 1024 ** 3
WORKER_CAP = SUMMARY_CAP = 256 * 1024 ** 2
TESTS_CAP = 32 * 1024 ** 2
MAIN_PAYLOAD_RESERVATION = 30 * WORKER_CAP + SUMMARY_CAP + 1024 ** 2
PROVENANCE_KEYS = old.PROVENANCE_KEYS + ("scientific_protocol_id", "technical_fingerprint")
require, canonical, identity = old.require, old.canonical, old.identity
read_json, write_json = old.read_json, old.write_json
write_manifest, verify_manifest, safe_path = old.write_manifest, old.verify_manifest, old.safe_path
api, pages, load_context = old.api, old.pages, old.load_context


def phase(message):
    markers = re.findall(r"\[([^\[\]\r\n]+)\]", message)
    require(len(markers) == 1 and markers[0] in
            tuple("knapsack-stagnation-main:" + value for value in RESERVATIONS),
            "Exactly one main-series phase marker required")
    return markers[0].split(":", 1)[1]


def source_manifest():
    files = {row["path"]: row for row in old.source_manifest()["files"]}
    paths = list(MODULE.rglob("*.py")) + [MODULE / "protocol.json", MODULE / "PROTOCOL_UK.md", ROOT / WORKFLOW]
    paths += [old.MODULE / name for name in ("frozen_banks.json", "frozen_tests.json",
              "evidence/prepare-run-39418724226-1/bank_registry.json")]
    for name in ("frozen_banks.json", "frozen_tests.json"):
        paths.append(old.MODULE / read_json(old.MODULE / name)["receipt_path"])
    for path in paths:
        relative = path.relative_to(ROOT).as_posix()
        files[relative] = {"path": relative, **identity(path)}
    rows = [files[key] for key in sorted(files)]
    return {"files": rows, "sha256": hashlib.sha256(canonical(rows)).hexdigest()}


def fingerprint():
    return source_manifest()["sha256"]


def authenticate(runtime=False):
    require(os.environ.get("GITHUB_ACTIONS") == "true" and
            os.environ.get("GITHUB_REPOSITORY") == old.REPOSITORY and
            os.environ.get("GITHUB_REF") == "refs/heads/" + old.BRANCH, "Wrong CI context")
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    require(re.fullmatch(r"[0-9a-f]{40}", head) and
            head == os.environ.get("GITHUB_SHA") == os.environ.get("EXPECTED_SHA"), "Wrong exact checkout")
    subprocess.run(["git", "merge-base", "--is-ancestor", REGISTRATION_SHA, head], cwd=ROOT, check=True)
    for name in ("protocol.json", "PROTOCOL_UK.md"):
        anchored = subprocess.check_output(["git", "show", REGISTRATION_SHA + ":" + REL + name], cwd=ROOT)
        require(anchored == (MODULE / name).read_bytes(), "Main registration changed")
    changed = subprocess.check_output(["git", "diff", "--name-only", REGISTRATION_SHA, head],
                                      cwd=ROOT, text=True).splitlines()
    require(all(name.startswith(REL) or name == WORKFLOW for name in changed), "Protected historical change")
    require(not subprocess.check_output(["git", "status", "--porcelain", "--untracked-files=no"],
                                       cwd=ROOT, text=True).strip(), "Dirty tracked checkout")
    protocol = read_json(MODULE / "protocol.json")
    grant = protocol["authorization"]
    require(protocol["protocol_id"] == PROTOCOL_ID and grant["main_series_authorized"] is True and
            grant["runner_minutes_ceiling"] == 200 and grant["evidence_payload_bytes_ceiling"] == BYTE_CEILING and
            grant["phase_reservations_runner_minutes"] == RESERVATIONS, "Grant differs")
    require(old.fingerprint() == TECHNICAL_FINGERPRINT, "Immutable technical implementation changed")
    require(identity(old.MODULE / "protocol.json")["sha256"] == protocol["prior_protocol_sha256"] and
            identity(old.MODULE / "evidence/prepare-run-39418724226-1/bank_registry.json")["sha256"] == BANK_SHA,
            "Immutable registration or banks changed")
    prior = read_json(old.MODULE / "protocol.json")
    for name, digest in prior["frozen_files"].items():
        require(identity(ROOT / name)["sha256"] == digest, "Protected dependency changed")
    load_context()
    result = {"protocol_id": PROTOCOL_ID, "scientific_protocol_id": SCIENTIFIC_ID,
              "registration_commit_sha": REGISTRATION_SHA, "implementation_commit_sha": head,
              "protocol_sha256": identity(MODULE / "protocol.json")["sha256"],
              "implementation_fingerprint": fingerprint(), "technical_fingerprint": TECHNICAL_FINGERPRINT,
              "data_manifest_sha256": prior["data_manifest_sha256"], "registry_sha256": prior["registry_sha256"],
              "bank_manifest_sha256": BANK_SHA, "run_id": int(os.environ["GITHUB_RUN_ID"]),
              "run_attempt": int(os.environ.get("GITHUB_RUN_ATTEMPT", "1"))}
    if runtime:
        import importlib.metadata
        require(platform.python_implementation() == "CPython" and platform.python_version() == "3.12.14", "Wrong Python")
        lock = read_json(ROOT / "studies/knapsack_parameters/ga_study/dependencies/environment.lock.json")
        versions = {row["name"]: importlib.metadata.version(row["name"]) for row in lock["packages"]}
        require(all(versions[row["name"]] == row["version"] for row in lock["packages"]), "Wrong dependencies")
        result["environment"] = {"python": platform.python_version(), "packages": versions}
    return result


def resource_usage():
    current = (int(os.environ["GITHUB_RUN_ID"]), int(os.environ.get("GITHUB_RUN_ATTEMPT", "1")))
    endpoint = "/actions/workflows/" + Path(WORKFLOW).name + "/runs?branch=" + urllib.parse.quote(old.BRANCH, safe="")
    jobs, artifacts, seen_jobs, seen_artifacts, seen_runs = [], [], set(), set(), set()
    current_seen = False
    previous_main_workers = 0
    for run in pages(endpoint, "workflow_runs"):
        require(type(run.get("id")) is int and run["id"] not in seen_runs, "Duplicate workflow run")
        seen_runs.add(run["id"])
        require(run["id"] == current[0] or run.get("status") == "completed", "Concurrent unknown usage")
        require(type(run.get("run_attempt")) is int and run["run_attempt"] >= 1, "Unknown attempts")
        for attempt in range(1, run["run_attempt"] + 1):
            here = (run["id"], attempt) == current
            current_seen |= here
            for job in pages(f"/actions/runs/{run['id']}/attempts/{attempt}/jobs", "jobs"):
                if job.get("conclusion") == "skipped":
                    continue
                require(type(job.get("id")) is int and job["id"] not in seen_jobs, "Duplicate allocated job")
                seen_jobs.add(job["id"])
                if here and job.get("name") == "gate" and job.get("status") == "in_progress":
                    continue
                if here and job.get("status") == "queued" and not job.get("started_at"):
                    continue
                jobs.append({"run_id": run["id"], "run_attempt": attempt, "job_id": job["id"],
                             "name": job.get("name"), "minutes": old.job_minutes(job), "conclusion": job["conclusion"]})
                if not here and str(job.get("name", "")).startswith("worker ("):
                    previous_main_workers += 1
        for artifact in pages(f"/actions/runs/{run['id']}/artifacts", "artifacts"):
            require(type(artifact.get("id")) is int and artifact["id"] not in seen_artifacts and
                    type(artifact.get("size_in_bytes")) is int and artifact["size_in_bytes"] >= 0,
                    "Unknown artifact usage")
            seen_artifacts.add(artifact["id"])
            name = str(artifact.get("name", ""))
            prefix = "knapsack-stagnation-main-"
            require(name.startswith(prefix), "Unregistered storage payload")
            if name.startswith(prefix + "worker-"):
                cap = WORKER_CAP
            elif name.startswith(prefix + "summary-"):
                cap = SUMMARY_CAP
            elif name.startswith(prefix + "tests-"):
                cap = TESTS_CAP
            elif name.startswith(prefix + "permit-"):
                cap = 1024 ** 2
            else:
                raise ValueError("Unregistered artifact payload category")
            artifacts.append({"run_id": run["id"], "artifact_id": artifact["id"],
                              "zip_bytes": artifact["size_in_bytes"], "expired": artifact.get("expired"),
                              "payload_upper_bound_bytes": cap})
    require(current_seen, "Current usage not yet visible")
    return {"used_runner_minutes": sum(row["minutes"] for row in jobs), "jobs": jobs,
            "previous_artifact_zip_bytes": sum(row["zip_bytes"] for row in artifacts), "artifacts": artifacts,
            "previous_payload_upper_bound_bytes": sum(row["payload_upper_bound_bytes"] for row in artifacts),
            "previous_main_workers": previous_main_workers, "current_gate_reserved": True}


def check_allowance(usage, selected):
    require(selected in RESERVATIONS, "Unregistered phase")
    used, byte_count = usage.get("used_runner_minutes"), usage.get("previous_payload_upper_bound_bytes")
    require(type(used) is int and used >= 0 and used + RESERVATIONS[selected] <= 200, "Insufficient runner allowance")
    reservation = MAIN_PAYLOAD_RESERVATION if selected == "main" else TESTS_CAP + 1024 ** 2
    require(type(byte_count) is int and byte_count >= 0 and byte_count + reservation <= BYTE_CEILING,
            "Insufficient cumulative storage allowance")
    zipped = usage.get("previous_artifact_zip_bytes")
    require(type(zipped) is int and 0 <= zipped <= BYTE_CEILING, "Unknown or excessive ZIP storage")
    if selected == "main":
        require(usage.get("previous_main_workers") == 0, "Do not repeat or replace previously allocated main runs")


def frozen_banks(destination):
    require(old.fingerprint() == TECHNICAL_FINGERPRINT, "Historical source fingerprint changed")
    receipt, transport = old.frozen_bundle("banks", destination)
    require(receipt["bank_manifest_sha256"] == BANK_SHA, "Wrong frozen 903-bank registry")
    return receipt, transport


def frozen_tests(destination):
    frozen = read_json(MODULE / "frozen_tests.json")
    require(frozen.get("schema") == "knapsack-stagnation-main-freeze-v1" and frozen.get("frozen") is True and
            frozen.get("protocol_id") == PROTOCOL_ID and frozen.get("implementation_fingerprint") == fingerprint(),
            "No exact green main-executor tests")
    receipt_path = safe_path(MODULE, frozen["receipt_path"])
    require(identity(receipt_path)["sha256"] == frozen["receipt_sha256"], "Changed frozen test receipt")
    run = api(f"/actions/runs/{frozen['run_id']}/attempts/{frozen['run_attempt']}")
    require(run.get("conclusion") == "success" and run.get("head_sha") == frozen["implementation_commit_sha"] and
            run.get("head_branch") == old.BRANCH and run.get("event") == "push" and run.get("path") == WORKFLOW and
            phase(run.get("head_commit", {}).get("message", "")) == "tests", "Invalid frozen tests run")
    subprocess.run(["git", "merge-base", "--is-ancestor", frozen["implementation_commit_sha"], os.environ["GITHUB_SHA"]],
                   cwd=ROOT, check=True)
    metadata = api(f"/actions/artifacts/{frozen['artifact_id']}")
    require(metadata.get("workflow_run", {}).get("id") == frozen["run_id"] and
            metadata.get("workflow_run", {}).get("head_sha") == frozen["implementation_commit_sha"] and
            metadata.get("name") == f"knapsack-stagnation-main-tests-{frozen['run_id']}-{frozen['run_attempt']}" and
            metadata.get("digest") == "sha256:" + frozen["zip_sha256"], "Foreign test artifact")
    transport = old._download_zip(metadata, destination)
    require(transport["file_manifest_sha256"] == frozen["file_manifest_sha256"] and
            (Path(destination) / "tests_receipt.json").read_bytes() == receipt_path.read_bytes(), "Wrong test members")
    receipt = read_json(receipt_path)
    require(receipt.get("protocol_id") == PROTOCOL_ID and receipt.get("implementation_fingerprint") == fingerprint() and
            receipt.get("tests_passed") is True and receipt.get("tests_run", 0) > 0 and
            all(receipt.get(name) == 0 for name in ("failures", "errors", "skipped")), "Tests not green")
    return receipt, transport


def gate(output, selected):
    provenance = authenticate()
    require(phase(os.environ.get("COMMIT_MESSAGE", "")) == selected, "Wrong phase")
    usage = resource_usage()
    check_allowance(usage, selected)
    checks = {}
    if selected == "main":
        with tempfile.TemporaryDirectory(prefix="main-evidence-gate-") as directory:
            checks["tests_receipt"], checks["tests_transport"] = frozen_tests(Path(directory) / "tests")
            checks["banks_receipt"], checks["banks_transport"] = frozen_banks(Path(directory) / "banks")
    write_json(Path(output) / "permit.json", {**provenance, **usage, "phase": selected,
        "reserved_runner_minutes": RESERVATIONS[selected], "runner_minutes_ceiling": 200,
        "evidence_payload_bytes_ceiling": BYTE_CEILING, "main_search_authorized": selected == "main", "checks": checks})
    write_manifest(output)


def check_permit(directory, selected):
    provenance = authenticate(runtime=True)
    expected = "main" if selected in ("worker", "aggregate") else selected
    require(expected in RESERVATIONS and phase(os.environ.get("COMMIT_MESSAGE", "")) == expected, "Wrong execution marker")
    verify_manifest(directory)
    permit = read_json(Path(directory) / "permit.json")
    require(all(permit.get(key) == provenance[key] for key in PROVENANCE_KEYS) and permit.get("phase") == expected and
            permit.get("reserved_runner_minutes") == RESERVATIONS[expected] and permit.get("runner_minutes_ceiling") == 200 and
            permit.get("evidence_payload_bytes_ceiling") == BYTE_CEILING and
            permit.get("main_search_authorized") is (expected == "main"), "Foreign main permit")
    check_allowance(permit, expected)
    return provenance


def payload_bytes(directory):
    return sum(path.stat().st_size for path in Path(directory).rglob("*") if path.is_file())


def download_current(destination, kind):
    provenance = authenticate()
    require(kind in ("permit", "workers"), "Unknown artifact kind")
    suffix = f"-{provenance['run_id']}-{provenance['run_attempt']}"
    prefix = "knapsack-stagnation-main-"
    rows = pages(f"/actions/runs/{provenance['run_id']}/artifacts", "artifacts")
    selected = [row for row in rows if (row["name"] == prefix + "permit" + suffix if kind == "permit" else
                row["name"].startswith(prefix + "worker-") and row["name"].endswith(suffix))]
    require((kind != "permit" or len(selected) == 1) and
            len({row["name"] for row in selected}) == len(selected), "Missing or duplicate current artifacts")
    destination = Path(destination)
    ledger = []
    if kind == "workers":
        write_json(destination / "transport_ledger.json", {**provenance, "artifacts": ledger})
    for row in sorted(selected, key=lambda value: value["name"]):
        require(re.fullmatch(r"[A-Za-z0-9_.-]+", row["name"]), "Unsafe artifact name")
        metadata = api(f"/actions/artifacts/{row['id']}")
        require(metadata.get("workflow_run", {}).get("id") == provenance["run_id"] and
                metadata.get("workflow_run", {}).get("head_sha") == provenance["implementation_commit_sha"] and
                metadata.get("name") == row["name"] and metadata.get("digest") == row.get("digest"), "Foreign current artifact")
        target = destination if kind == "permit" else destination / row["name"]
        transport = old._download_zip(metadata, target)
        require(payload_bytes(target) <= (1024 ** 2 if kind == "permit" else WORKER_CAP), "Artifact payload cap exceeded")
        require(payload_bytes(destination) <= BYTE_CEILING, "Aggregate materialized evidence exceeds 8 GiB")
        receipt = read_json(target / ("permit.json" if kind == "permit" else "worker_summary.json"))
        require(all(receipt.get(key) == provenance[key] for key in PROVENANCE_KEYS), "Mixed current receipt")
        ledger.append({"name": row["name"], **transport, "payload_bytes": payload_bytes(target)})
        if kind == "workers":
            write_json(destination / "transport_ledger.json", {**provenance, "artifacts": ledger})
    return ledger
