"""Separate fail-closed authority; no previous resource grant is inherited."""
from __future__ import annotations

import hashlib
import importlib.metadata
import os
from pathlib import Path
import platform
import re
import subprocess
import tempfile
import urllib.parse

from ..stagnation_diagnosis import contract as old
from ..stagnation_diagnosis_main import contract as source

ROOT, MODULE = old.ROOT, Path(__file__).resolve().parent
REL = "studies/knapsack_parameters/stagnation_mechanisms/"
WORKFLOW = ".github/workflows/knapsack-stagnation-mechanisms.yml"
REGISTRATION_SHA = "75ec07e9dba0e9de1aaf7a105b645fade31caaa8"
PROTOCOL_ID = "GA-KNAPSACK-STAGNATION-MECHANISMS-SECONDARY-V1"
PREFIX = "knapsack-stagnation-mechanisms-"
RESERVATIONS = {"tests": 12, "analyze": 70}
CEILING, BYTE_CEILING = 90, 1024 ** 3
CAPS = {"permit": 1024 ** 2, "tests": 16 * 1024 ** 2,
        "worker": 32 * 1024 ** 2, "summary": 64 * 1024 ** 2}
require, canonical, identity = old.require, old.canonical, old.identity
read_json, write_json = old.read_json, old.write_json
write_manifest, verify_manifest, safe_path = old.write_manifest, old.verify_manifest, old.safe_path
api, pages = old.api, old.pages
PROVENANCE_KEYS = ("protocol_id", "registration_commit_sha", "implementation_commit_sha",
                   "implementation_fingerprint", "protocol_sha256", "authorization_sha256",
                   "source_summary_sha256", "run_id", "run_attempt")


def phase(message):
    markers = re.findall(r"\[([^\[\]\r\n]+)\]", message)
    require(len(markers) == 1 and markers[0] in
            tuple("knapsack-stagnation-mechanisms:" + p for p in RESERVATIONS),
            "Exactly one registered secondary-analysis phase is required")
    return markers[0].split(":", 1)[1]


def source_summary():
    registered = read_json(MODULE / "protocol.json")["source"]
    for key in ("summary", "registry"):
        require(identity(ROOT / registered[key + "_path"])["sha256"] == registered[key + "_sha256"],
                "Frozen historical " + key + " changed")
    require(source.fingerprint() == registered["main_implementation_fingerprint"],
            "Historical main implementation changed")
    require(old.fingerprint() == registered["technical_implementation_fingerprint"],
            "Historical technical implementation changed")
    result = read_json(ROOT / registered["summary_path"])
    provenance = result["provenance"]
    require(provenance["run_id"] == registered["run_id"] and
            provenance["run_attempt"] == registered["run_attempt"] and
            provenance["implementation_commit_sha"] == registered["head_sha"], "Wrong historical source")
    ledger = result["transport_ledger"]["artifacts"]
    expected = {f"knapsack-stagnation-main-worker-{label}-s{i:03d}-39465647096-1"
                for label in ("UC", "WC", "SC") for i in range(10)}
    require(len(ledger) == 30 and {r["name"] for r in ledger} == expected and
            len({r["artifact_id"] for r in ledger}) == 30, "Incomplete historical artifact ledger")
    return result


def source_manifest():
    files = {r["path"]: r for r in source.source_manifest()["files"]}
    protocol = read_json(MODULE / "protocol.json")
    paths = list(MODULE.rglob("*.py")) + [MODULE / "protocol.json", MODULE / "PROTOCOL_UK.md", ROOT / WORKFLOW]
    paths += [ROOT / protocol["source"][key + "_path"] for key in ("summary", "registry")]
    # Authorization is intentionally separate from the immutable preregistration.
    if (MODULE / "authorization.json").exists():
        paths.append(MODULE / "authorization.json")
    for path in paths:
        relative = path.relative_to(ROOT).as_posix()
        files[relative] = {"path": relative, **identity(path)}
    rows = [files[key] for key in sorted(files)]
    return {"files": rows, "sha256": hashlib.sha256(canonical(rows)).hexdigest()}


def fingerprint():
    return source_manifest()["sha256"]


def validate_grant(grant):
    require(grant.get("protocol_id") == PROTOCOL_ID and grant.get("authorized") is True and
            grant.get("runner_minutes_ceiling") == CEILING and
            grant.get("output_payload_bytes_ceiling") == BYTE_CEILING and
            type(grant.get("user_answer")) is str and bool(grant["user_answer"].strip()) and
            grant.get("new_search_authorized") is False, "No separate secondary-analysis resource grant")


def authenticate(runtime=False):
    require(os.environ.get("GITHUB_ACTIONS") == "true" and
            os.environ.get("GITHUB_REPOSITORY") == old.REPOSITORY and
            os.environ.get("GITHUB_REF") == "refs/heads/" + old.BRANCH, "Wrong CI context")
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    require(re.fullmatch(r"[0-9a-f]{40}", head) and
            head == os.environ.get("GITHUB_SHA") == os.environ.get("EXPECTED_SHA"), "Wrong exact checkout")
    subprocess.run(["git", "merge-base", "--is-ancestor", REGISTRATION_SHA, head], cwd=ROOT, check=True)
    for name in ("protocol.json", "PROTOCOL_UK.md"):
        require(subprocess.check_output(["git", "show", REGISTRATION_SHA + ":" + REL + name], cwd=ROOT)
                == (MODULE / name).read_bytes(), "Secondary preregistration changed")
    changed = subprocess.check_output(["git", "diff", "--name-only", REGISTRATION_SHA, head],
                                      cwd=ROOT, text=True).splitlines()
    require(all(name.startswith(REL) or name == WORKFLOW for name in changed), "Protected historical change")
    require(not subprocess.check_output(["git", "status", "--porcelain", "--untracked-files=no"],
                                       cwd=ROOT, text=True).strip(), "Dirty tracked checkout")
    validate_grant(read_json(MODULE / "authorization.json"))
    frozen = source_summary()
    result = {"protocol_id": PROTOCOL_ID, "registration_commit_sha": REGISTRATION_SHA,
              "implementation_commit_sha": head, "implementation_fingerprint": fingerprint(),
              "protocol_sha256": identity(MODULE / "protocol.json")["sha256"],
              "authorization_sha256": identity(MODULE / "authorization.json")["sha256"],
              "source_summary_sha256": identity(ROOT / read_json(MODULE / "protocol.json")["source"]["summary_path"])["sha256"],
              "run_id": int(os.environ["GITHUB_RUN_ID"]),
              "run_attempt": int(os.environ.get("GITHUB_RUN_ATTEMPT", "1"))}
    require(frozen["provenance"]["phase"] == "main", "Not an original main-series source")
    if runtime:
        require(platform.python_implementation() == "CPython" and platform.python_version() == "3.12.14", "Wrong Python")
        lock = read_json(ROOT / "studies/knapsack_parameters/ga_study/dependencies/environment.lock.json")
        versions = {r["name"]: importlib.metadata.version(r["name"]) for r in lock["packages"]}
        require(all(versions[r["name"]] == r["version"] for r in lock["packages"]), "Wrong environment")
        result["environment"] = {"python": platform.python_version(), "packages": versions}
    return result


def payload_bytes(directory):
    return sum(path.stat().st_size for path in Path(directory).rglob("*") if path.is_file())


def resource_usage():
    current = (int(os.environ["GITHUB_RUN_ID"]), int(os.environ.get("GITHUB_RUN_ATTEMPT", "1")))
    endpoint = "/actions/workflows/" + Path(WORKFLOW).name + "/runs?branch=" + urllib.parse.quote(old.BRANCH, safe="")
    jobs, artifacts, seen, seen_jobs, seen_artifacts = [], [], set(), set(), set()
    current_seen, prior_workers = False, 0
    for run in pages(endpoint, "workflow_runs"):
        require(type(run.get("id")) is int and run["id"] not in seen, "Duplicate workflow run")
        seen.add(run["id"])
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
                             "name": job.get("name"), "minutes": old.job_minutes(job),
                             "conclusion": job.get("conclusion")})
                prior_workers += int(not here and str(job.get("name", "")).startswith("worker ("))
        for artifact in pages(f"/actions/runs/{run['id']}/artifacts", "artifacts"):
            require(type(artifact.get("id")) is int and artifact["id"] not in seen_artifacts and
                    type(artifact.get("size_in_bytes")) is int and artifact["size_in_bytes"] >= 0,
                    "Unknown artifact usage")
            seen_artifacts.add(artifact["id"])
            kinds = [kind for kind in CAPS if artifact.get("name", "").startswith(PREFIX + kind + "-")]
            require(len(kinds) == 1, "Unregistered output artifact")
            artifacts.append({"artifact_id": artifact["id"], "zip_bytes": artifact["size_in_bytes"],
                              "payload_upper_bound_bytes": CAPS[kinds[0]], "expired": artifact.get("expired")})
    require(current_seen, "Current usage is not yet visible")
    return {"used_runner_minutes": sum(r["minutes"] for r in jobs), "jobs": jobs, "artifacts": artifacts,
            "previous_payload_upper_bound_bytes": sum(r["payload_upper_bound_bytes"] for r in artifacts),
            "previous_artifact_zip_bytes": sum(r["zip_bytes"] for r in artifacts),
            "previous_workers": prior_workers}


def check_allowance(usage, selected):
    require(selected in RESERVATIONS, "Unregistered phase")
    used = usage.get("used_runner_minutes")
    require(type(used) is int and used >= 0 and used + RESERVATIONS[selected] <= CEILING, "Insufficient runner allowance")
    reserve = CAPS["permit"] + (CAPS["tests"] if selected == "tests" else 10 * CAPS["worker"] + CAPS["summary"])
    payload, zipped = usage.get("previous_payload_upper_bound_bytes"), usage.get("previous_artifact_zip_bytes")
    require(type(payload) is int and payload >= 0 and payload + reserve <= BYTE_CEILING and
            type(zipped) is int and 0 <= zipped <= BYTE_CEILING, "Unknown or excessive output storage")
    if selected == "analyze":
        require(usage.get("previous_workers") == 0, "A partial secondary matrix must not be silently repeated")


def frozen_tests():
    frozen = read_json(MODULE / "frozen_tests.json")
    require(frozen.get("protocol_id") == PROTOCOL_ID and frozen.get("frozen") is True and
            frozen.get("implementation_fingerprint") == fingerprint(), "No exact green test freeze")
    receipt_path = safe_path(MODULE, frozen["receipt_path"])
    require(str(frozen["receipt_path"]).startswith("evidence/") and
            identity(receipt_path)["sha256"] == frozen.get("receipt_sha256"), "Frozen test receipt changed")
    run = api(f"/actions/runs/{frozen['run_id']}/attempts/{frozen['run_attempt']}")
    require(run.get("conclusion") == "success" and run.get("head_sha") == frozen["implementation_commit_sha"] and
            run.get("head_branch") == old.BRANCH and run.get("path") == WORKFLOW and
            run.get("event") == "push" and phase(run.get("head_commit", {}).get("message", "")) == "tests",
            "Wrong frozen test execution")
    subprocess.run(["git", "merge-base", "--is-ancestor", frozen["implementation_commit_sha"], os.environ["GITHUB_SHA"]],
                   cwd=ROOT, check=True)
    receipt = read_json(receipt_path)
    require(receipt.get("tests_passed") is True and type(receipt.get("tests_run")) is int and
            receipt["tests_run"] > 0 and all(receipt.get(key) == 0 for key in ("errors", "failures", "skipped")) and
            receipt.get("implementation_fingerprint") == fingerprint(), "Tests not green")
    require(receipt.get("protocol_id") == PROTOCOL_ID and
            receipt.get("run_id") == frozen["run_id"] and receipt.get("run_attempt") == frozen["run_attempt"] and
            receipt.get("implementation_commit_sha") == frozen["implementation_commit_sha"] and
            receipt.get("authorization_sha256") == identity(MODULE / "authorization.json")["sha256"] and
            receipt.get("protocol_sha256") == identity(MODULE / "protocol.json")["sha256"], "Wrong test provenance")
    metadata = api(f"/actions/artifacts/{frozen['artifact_id']}")
    require(metadata.get("workflow_run", {}).get("id") == frozen["run_id"] and
            metadata.get("workflow_run", {}).get("head_sha") == frozen["implementation_commit_sha"] and
            metadata.get("name") == f"{PREFIX}tests-{frozen['run_id']}-{frozen['run_attempt']}" and
            metadata.get("digest") == "sha256:" + frozen["zip_sha256"], "Foreign test artifact")
    with tempfile.TemporaryDirectory(prefix="secondary-frozen-tests-") as temporary:
        destination = Path(temporary) / "tests"
        transport = old._download_zip(metadata, destination)
        require(transport["file_manifest_sha256"] == frozen["file_manifest_sha256"] and
                (destination / "tests_receipt.json").read_bytes() == receipt_path.read_bytes(),
                "Frozen tests differ from the archived green test receipt")
    return receipt


def gate(output, selected):
    provenance = authenticate()
    require(phase(os.environ.get("COMMIT_MESSAGE", "")) == selected, "Wrong phase")
    usage = resource_usage()
    check_allowance(usage, selected)
    checked = frozen_tests() if selected == "analyze" else None
    write_json(Path(output) / "permit.json", {**provenance, **usage, "phase": selected,
               "reserved_runner_minutes": RESERVATIONS[selected], "runner_minutes_ceiling": CEILING,
               "new_search_authorized": False, "frozen_tests": checked})
    write_manifest(output)


def check_permit(directory, selected):
    provenance = authenticate(runtime=True)
    require(selected in RESERVATIONS and phase(os.environ.get("COMMIT_MESSAGE", "")) == selected, "Wrong phase")
    verify_manifest(directory)
    permit = read_json(Path(directory) / "permit.json")
    require(all(permit.get(k) == provenance[k] for k in PROVENANCE_KEYS) and permit.get("phase") == selected and
            permit.get("reserved_runner_minutes") == RESERVATIONS[selected] and
            permit.get("runner_minutes_ceiling") == CEILING and permit.get("new_search_authorized") is False,
            "Foreign secondary-analysis permit")
    check_allowance(permit, selected)
    return provenance


def download_source(ledger_row, destination):
    registered = read_json(MODULE / "protocol.json")["source"]
    require(ledger_row in source_summary()["transport_ledger"]["artifacts"], "Unregistered historical artifact")
    metadata = api(f"/actions/artifacts/{ledger_row['artifact_id']}")
    require(metadata.get("workflow_run", {}).get("id") == registered["run_id"] and
            metadata.get("workflow_run", {}).get("head_sha") == registered["head_sha"] and
            metadata.get("name") == ledger_row["name"] and
            metadata.get("digest") == "sha256:" + ledger_row["zip_sha256"] and
            metadata.get("size_in_bytes") == ledger_row["zip_bytes"], "Wrong historical source ZIP")
    transport = old._download_zip(metadata, destination)
    require(transport["file_manifest_sha256"] == ledger_row["file_manifest_sha256"] and
            payload_bytes(destination) == ledger_row["payload_bytes"], "Wrong historical source members")
    return transport


def download_current(destination, kind):
    provenance = authenticate()
    require(kind in ("permit", "workers"), "Unknown current artifact kind")
    suffix = f"-{provenance['run_id']}-{provenance['run_attempt']}"
    rows = pages(f"/actions/runs/{provenance['run_id']}/artifacts", "artifacts")
    selected = [row for row in rows if (row["name"] == PREFIX + "permit" + suffix if kind == "permit" else
                row["name"].startswith(PREFIX + "worker-") and row["name"].endswith(suffix))]
    require((kind != "permit" or len(selected) == 1) and
            len({r["name"] for r in selected}) == len(selected), "Missing or duplicate current transport")
    ledger = []
    destination = Path(destination)
    for row in sorted(selected, key=lambda x: x["name"]):
        require(re.fullmatch(r"[A-Za-z0-9_.-]+", row["name"]), "Unsafe current name")
        metadata = api(f"/actions/artifacts/{row['id']}")
        require(metadata.get("workflow_run", {}).get("id") == provenance["run_id"] and
                metadata.get("workflow_run", {}).get("head_sha") == provenance["implementation_commit_sha"] and
                metadata.get("name") == row["name"] and metadata.get("digest") == row.get("digest"),
                "Foreign current transport")
        target = destination if kind == "permit" else destination / row["name"]
        transport = old._download_zip(metadata, target)
        require(payload_bytes(target) <= CAPS["permit" if kind == "permit" else "worker"], "Payload cap exceeded")
        receipt = read_json(target / ("permit.json" if kind == "permit" else "worker_summary.json"))
        require(all(receipt.get(k) == provenance[k] for k in PROVENANCE_KEYS), "Mixed current provenance")
        ledger.append({"name": row["name"], **transport})
    if kind == "workers":
        write_json(destination / "transport_ledger.json", {**provenance, "artifacts": ledger})
    return ledger
