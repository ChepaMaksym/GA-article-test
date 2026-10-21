"""Fail-closed recovery authority sharing the original 90-minute grant."""
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

from ..stagnation_mechanisms import contract as base

ROOT, MODULE = base.ROOT, Path(__file__).resolve().parent
REL = "studies/knapsack_parameters/stagnation_mechanisms_recovery/"
WORKFLOW = ".github/workflows/knapsack-stagnation-recovery.yml"
REGISTRATION_SHA = "b6ae1716f519719d05b5ffdf5957826aca700645"
PROTOCOL_ID = "GA-KNAPSACK-STAGNATION-MECHANISMS-RECOVERY-V1"
PREFIX = "knapsack-stagnation-recovery-"
RECOVER_FAMILIES = ("s004", "s005", "s006")
REUSED_FAMILIES = ("s000", "s001", "s002", "s003", "s007", "s008", "s009")
RESERVATIONS = {"tests": 4, "recover": 34, "present": 4}
CAPS, CEILING, BYTE_CEILING = base.CAPS, 90, 1024 ** 3
require, canonical, identity = base.require, base.canonical, base.identity
read_json, write_json, safe_path = base.read_json, base.write_json, base.safe_path
write_manifest, verify_manifest = base.write_manifest, base.verify_manifest
api, pages, payload_bytes = base.api, base.pages, base.payload_bytes
PROVENANCE_KEYS = ("protocol_id", "registration_commit_sha", "implementation_commit_sha",
                   "implementation_fingerprint", "protocol_sha256", "scientific_implementation_fingerprint",
                   "run_id", "run_attempt")


def phase(message):
    markers = re.findall(r"\[([^\[\]\r\n]+)\]", message)
    require(len(markers) == 1 and markers[0] in tuple("knapsack-stagnation-recovery:" + p for p in RESERVATIONS),
            "One exact recovery phase required")
    return markers[0].split(":", 1)[1]


def prior_audit():
    protocol = read_json(MODULE / "protocol.json")
    prior = protocol["prior"]
    for key in ("audit", "resource_receipt"):
        require(identity(ROOT / prior[key + "_path"])["sha256"] == prior[key + "_sha256"], "Frozen prior receipt changed")
    require(base.fingerprint() == prior["implementation_fingerprint"], "Scientific code or prior authority changed")
    audit = read_json(ROOT / prior["audit_path"])
    require(audit["complete"] is False and audit["verified_rows"] == 630 and
            audit["run_id"] == prior["run_id"] and audit["run_attempt"] == 1 and
            audit["implementation_commit_sha"] == prior["implementation_commit_sha"] and
            audit["implementation_fingerprint"] == prior["implementation_fingerprint"] and
            audit["source_identity"] == base.source_summary()["provenance"], "Foreign prior audit")
    ledger = audit["transport_ledger"]["artifacts"]
    expected = {f"{base.PREFIX}worker-{f}-{prior['run_id']}-1" for f in REUSED_FAMILIES}
    require(len(ledger) == 7 and {r["name"] for r in ledger} == expected and
            len({r["artifact_id"] for r in ledger}) == 7, "Missing or duplicated retained family")
    receipt = read_json(ROOT / prior["resource_receipt_path"])
    require(receipt["used_runner_minutes"] == prior["used_runner_minutes"] == 51 and
            receipt["runner_minutes_ceiling"] == 90, "Prior budget cannot be reset")
    return audit


def source_manifest():
    files = {r["path"]: r for r in base.source_manifest()["files"]}
    protocol = read_json(MODULE / "protocol.json")
    paths = list(MODULE.rglob("*.py")) + [MODULE / "protocol.json", MODULE / "PROTOCOL_UK.md",
            MODULE / "presentation_amendment.json", ROOT / WORKFLOW]
    paths += [ROOT / protocol["prior"][key + "_path"] for key in ("audit", "resource_receipt")]
    for path in paths:
        name = path.relative_to(ROOT).as_posix()
        files[name] = {"path": name, **identity(path)}
    rows = [files[name] for name in sorted(files)]
    return {"files": rows, "sha256": hashlib.sha256(canonical(rows)).hexdigest()}


def fingerprint():
    return source_manifest()["sha256"]


def authenticate(runtime=False):
    require(os.environ.get("GITHUB_ACTIONS") == "true" and
            os.environ.get("GITHUB_REPOSITORY") == base.old.REPOSITORY and
            os.environ.get("GITHUB_REF") == "refs/heads/" + base.old.BRANCH, "Wrong CI context")
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    require(re.fullmatch(r"[0-9a-f]{40}", head) and
            head == os.environ.get("GITHUB_SHA") == os.environ.get("EXPECTED_SHA"), "Wrong exact SHA")
    subprocess.run(["git", "merge-base", "--is-ancestor", REGISTRATION_SHA, head], cwd=ROOT, check=True)
    for name in ("protocol.json", "PROTOCOL_UK.md"):
        require(subprocess.check_output(["git", "show", REGISTRATION_SHA + ":" + REL + name], cwd=ROOT)
                == (MODULE / name).read_bytes(), "Recovery registration changed")
    require(subprocess.check_output(["git", "show", "b991933e482b8ba5bfccf7c476de69b797ee80a1:" + REL +
            "presentation_amendment.json"], cwd=ROOT) == (MODULE / "presentation_amendment.json").read_bytes(),
            "Presentation correction registration changed")
    changed = subprocess.check_output(["git", "diff", "--name-only", REGISTRATION_SHA, head], cwd=ROOT, text=True).splitlines()
    require(all(name.startswith(REL) or name == WORKFLOW for name in changed), "Protected historical change")
    require(not subprocess.check_output(["git", "status", "--porcelain", "--untracked-files=no"],
                                       cwd=ROOT, text=True).strip(), "Dirty checkout")
    prior_audit()
    grant = read_json(MODULE / "protocol.json")["authorization"]
    require(grant["authorized"] is True and grant["user_answer"] == "Так, завершити в межах 90 хвилин" and
            grant["shared_runner_minutes_ceiling"] == 90 and grant["new_search_authorized"] is False,
            "No explicit technical recovery permission")
    result = {"protocol_id": PROTOCOL_ID, "registration_commit_sha": REGISTRATION_SHA,
              "implementation_commit_sha": head, "implementation_fingerprint": fingerprint(),
              "protocol_sha256": identity(MODULE / "protocol.json")["sha256"],
              "scientific_implementation_fingerprint": base.fingerprint(),
              "run_id": int(os.environ["GITHUB_RUN_ID"]), "run_attempt": int(os.environ.get("GITHUB_RUN_ATTEMPT", "1"))}
    if runtime:
        require(platform.python_implementation() == "CPython" and platform.python_version() == "3.12.14", "Wrong Python")
        lock = read_json(ROOT / "studies/knapsack_parameters/ga_study/dependencies/environment.lock.json")
        versions = {r["name"]: importlib.metadata.version(r["name"]) for r in lock["packages"]}
        require(all(versions[r["name"]] == r["version"] for r in lock["packages"]), "Wrong environment")
        result["environment"] = {"python": platform.python_version(), "packages": versions}
    return result


def resource_usage():
    current = (int(os.environ["GITHUB_RUN_ID"]), int(os.environ.get("GITHUB_RUN_ATTEMPT", "1")))
    jobs, artifacts, seen_runs, seen_jobs, seen_artifacts = [], [], set(), set(), set()
    current_seen, recovery_workers = False, 0
    for workflow in (base.WORKFLOW, WORKFLOW):
        endpoint = "/actions/workflows/" + Path(workflow).name + "/runs?branch=" + urllib.parse.quote(base.old.BRANCH, safe="")
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
                    require(type(job.get("id")) is int and job["id"] not in seen_jobs, "Duplicate job")
                    seen_jobs.add(job["id"])
                    if here and job.get("name") == "gate" and job.get("status") == "in_progress":
                        continue
                    if here and job.get("status") == "queued" and not job.get("started_at"):
                        continue
                    jobs.append({"workflow": workflow, "run_id": run["id"], "run_attempt": attempt,
                                 "job_id": job["id"], "name": job.get("name"),
                                 "minutes": base.old.job_minutes(job), "conclusion": job.get("conclusion")})
                    recovery_workers += int(workflow == WORKFLOW and not here and str(job.get("name", "")).startswith("worker ("))
            for artifact in pages(f"/actions/runs/{run['id']}/artifacts", "artifacts"):
                require(type(artifact.get("id")) is int and artifact["id"] not in seen_artifacts and
                        type(artifact.get("size_in_bytes")) is int and artifact["size_in_bytes"] >= 0, "Unknown storage")
                seen_artifacts.add(artifact["id"])
                prefix = base.PREFIX if workflow == base.WORKFLOW else PREFIX
                kinds = [kind for kind in CAPS if artifact.get("name", "").startswith(prefix + kind + "-")]
                require(len(kinds) == 1, "Unregistered artifact")
                artifacts.append({"artifact_id": artifact["id"], "zip_bytes": artifact["size_in_bytes"],
                                  "payload_upper_bound_bytes": CAPS[kinds[0]], "expired": artifact.get("expired")})
    require(current_seen, "Current accounting not yet visible")
    return {"used_runner_minutes": sum(r["minutes"] for r in jobs), "jobs": jobs, "artifacts": artifacts,
            "previous_payload_upper_bound_bytes": sum(r["payload_upper_bound_bytes"] for r in artifacts),
            "previous_artifact_zip_bytes": sum(r["zip_bytes"] for r in artifacts),
            "recovery_workers": recovery_workers, "both_workflows_included": True}


def check_allowance(usage, selected):
    require(selected in RESERVATIONS and usage.get("both_workflows_included") is True, "Shared accounting required")
    used = usage.get("used_runner_minutes")
    require(type(used) is int and used >= 51 and used + RESERVATIONS[selected] <= CEILING,
            "Unknown or insufficient shared runner remainder")
    payload, zipped = usage.get("previous_payload_upper_bound_bytes"), usage.get("previous_artifact_zip_bytes")
    reserve = CAPS["permit"] + (CAPS["tests"] if selected == "tests" else CAPS["summary"] if selected == "present"
                               else 3 * CAPS["worker"] + CAPS["summary"])
    require(type(payload) is int and payload >= 0 and payload + reserve <= BYTE_CEILING and
            type(zipped) is int and 0 <= zipped <= BYTE_CEILING, "Insufficient shared storage allowance")
    require(type(usage.get("recovery_workers")) is int and usage["recovery_workers"] >= 0,
            "Unknown prior recovery worker allocation")
    if selected == "recover":
        require(usage.get("recovery_workers") == 0, "Do not silently repeat recovery workers")


def frozen_tests():
    frozen = read_json(MODULE / "frozen_tests.json")
    require(frozen.get("protocol_id") == PROTOCOL_ID and frozen.get("frozen") is True and
            frozen.get("implementation_fingerprint") == fingerprint(), "No exact green recovery tests")
    path = safe_path(MODULE, frozen["receipt_path"])
    require(frozen["receipt_path"].startswith("evidence/") and identity(path)["sha256"] == frozen["receipt_sha256"],
            "Frozen receipt changed")
    run = api(f"/actions/runs/{frozen['run_id']}/attempts/{frozen['run_attempt']}")
    require(run.get("conclusion") == "success" and run.get("head_sha") == frozen["implementation_commit_sha"] and
            run.get("head_branch") == base.old.BRANCH and run.get("path") == WORKFLOW and
            run.get("event") == "push" and phase(run.get("head_commit", {}).get("message", "")) == "tests", "Wrong green tests")
    subprocess.run(["git", "merge-base", "--is-ancestor", frozen["implementation_commit_sha"], os.environ["GITHUB_SHA"]],
                   cwd=ROOT, check=True)
    receipt = read_json(path)
    require(receipt.get("protocol_id") == PROTOCOL_ID and receipt.get("tests_passed") is True and
            receipt.get("tests_run", 0) > 0 and all(receipt.get(k) == 0 for k in ("errors", "failures", "skipped")) and
            receipt.get("run_id") == frozen["run_id"] and receipt.get("run_attempt") == frozen["run_attempt"] and
            receipt.get("implementation_commit_sha") == frozen["implementation_commit_sha"] and
            receipt.get("implementation_fingerprint") == fingerprint(), "Wrong test receipt identity")
    metadata = api(f"/actions/artifacts/{frozen['artifact_id']}")
    require(metadata.get("name") == f"{PREFIX}tests-{frozen['run_id']}-{frozen['run_attempt']}" and
            metadata.get("workflow_run", {}).get("id") == frozen["run_id"] and
            metadata.get("workflow_run", {}).get("head_sha") == frozen["implementation_commit_sha"] and
            metadata.get("digest") == "sha256:" + frozen["zip_sha256"], "Foreign recovery test artifact")
    with tempfile.TemporaryDirectory(prefix="recovery-test-gate-") as temporary:
        directory = Path(temporary) / "tests"
        transport = base.old._download_zip(metadata, directory)
        require(transport["file_manifest_sha256"] == frozen["file_manifest_sha256"] and
                (directory / "tests_receipt.json").read_bytes() == path.read_bytes(), "Wrong frozen test members")
    return receipt


def gate(output, selected):
    provenance = authenticate()
    require(phase(os.environ.get("COMMIT_MESSAGE", "")) == selected, "Wrong phase")
    usage = resource_usage()
    check_allowance(usage, selected)
    tests = frozen_tests() if selected in ("recover", "present") else None
    write_json(Path(output) / "permit.json", {**provenance, **usage, "phase": selected,
        "reserved_runner_minutes": RESERVATIONS[selected], "runner_minutes_ceiling": 90,
        "new_search_authorized": False, "frozen_tests": tests})
    write_manifest(output)


def check_permit(directory, selected):
    provenance = authenticate(runtime=True)
    require(phase(os.environ.get("COMMIT_MESSAGE", "")) == selected, "Wrong execution phase")
    verify_manifest(directory)
    permit = read_json(Path(directory) / "permit.json")
    require(all(permit.get(k) == provenance[k] for k in PROVENANCE_KEYS) and permit.get("phase") == selected and
            permit.get("reserved_runner_minutes") == RESERVATIONS[selected] and
            permit.get("runner_minutes_ceiling") == 90 and permit.get("new_search_authorized") is False, "Foreign permit")
    check_allowance(permit, selected)
    return provenance


def validate_producer(receipt, family, current_identity):
    require(family in REUSED_FAMILIES + RECOVER_FAMILIES and receipt.get("family") == family,
            "Unregistered producer family")
    if family in REUSED_FAMILIES:
        expected, keys = prior_audit(), base.PROVENANCE_KEYS
    else:
        expected, keys = current_identity, PROVENANCE_KEYS
    require(all(receipt.get(k) == expected[k] for k in keys), "Family assigned to a foreign execution producer")
    require(receipt.get("source_identity") == base.source_summary()["provenance"] and
            receipt.get("status") == "COMPLETE" and receipt.get("completed_count") == 90 and
            receipt.get("errors") == [] and len(receipt.get("rows", [])) == 90, "Incomplete or foreign family")
    expected_runs = {(f"{label}-{family}", seed) for label in ("UC", "WC", "SC") for seed in range(93001, 93031)}
    found = [(r.get("instance_id"), r.get("repeat_seed")) for r in receipt["rows"]]
    require(len(set(found)) == len(found) and set(found) == expected_runs and
            all(r.get("family") == family and r.get("source_identity") == receipt["source_identity"] and
                r.get("status") == "PASS" and r.get("verified") is True for r in receipt["rows"]), "Mixed family run identities")
    return receipt["rows"]


def download_reused(family, destination):
    require(family in REUSED_FAMILIES, "Only seven frozen completed families may be reused")
    prior = prior_audit()
    name = f"{base.PREFIX}worker-{family}-39551196713-1"
    rows = [r for r in prior["transport_ledger"]["artifacts"] if r["name"] == name]
    require(len(rows) == 1, "Missing frozen family transport")
    row = rows[0]
    metadata = api(f"/actions/artifacts/{row['artifact_id']}")
    require(metadata.get("name") == name and metadata.get("workflow_run", {}).get("id") == 39551196713 and
            metadata.get("workflow_run", {}).get("head_sha") == prior["implementation_commit_sha"] and
            metadata.get("digest") == "sha256:" + row["zip_sha256"] and
            metadata.get("size_in_bytes") == row["zip_bytes"], "Foreign retained artifact")
    transport = base.old._download_zip(metadata, destination)
    require(transport["file_manifest_sha256"] == row["file_manifest_sha256"] and
            payload_bytes(destination) <= CAPS["worker"], "Changed retained members")
    return {"name": name, "kind": "reused", "family": family, **transport}


def download_current(destination, kind):
    provenance = authenticate()
    require(kind in ("permit", "workers"), "Unknown artifact kind")
    suffix = f"-{provenance['run_id']}-{provenance['run_attempt']}"
    rows = pages(f"/actions/runs/{provenance['run_id']}/artifacts", "artifacts")
    selected = [r for r in rows if (r["name"] == PREFIX + "permit" + suffix if kind == "permit" else
                r["name"].startswith(PREFIX + "worker-") and r["name"].endswith(suffix))]
    require((kind != "permit" or len(selected) == 1) and len({r["name"] for r in selected}) == len(selected),
            "Missing or duplicate current artifacts")
    ledger, destination = [], Path(destination)
    if kind == "workers":
        write_json(destination / "transport_ledger.json", {**provenance, "artifacts": ledger})
    for row in selected:
        require(re.fullmatch(r"[A-Za-z0-9_.-]+", row["name"]), "Unsafe artifact name")
        metadata = api(f"/actions/artifacts/{row['id']}")
        require(metadata.get("workflow_run", {}).get("id") == provenance["run_id"] and
                metadata.get("workflow_run", {}).get("head_sha") == provenance["implementation_commit_sha"] and
                metadata.get("name") == row["name"] and metadata.get("digest") == row.get("digest"), "Foreign current artifact")
        target = destination if kind == "permit" else destination / row["name"]
        transport = base.old._download_zip(metadata, target)
        require(payload_bytes(target) <= CAPS["permit" if kind == "permit" else "worker"], "Output cap exceeded")
        receipt = read_json(target / ("permit.json" if kind == "permit" else "worker_summary.json"))
        require(all(receipt.get(k) == provenance[k] for k in PROVENANCE_KEYS), "Mixed current receipt")
        ledger.append({"name": row["name"], "kind": "current", **transport})
        if kind == "workers":
            write_json(destination / "transport_ledger.json", {**provenance, "artifacts": ledger})
    return ledger
