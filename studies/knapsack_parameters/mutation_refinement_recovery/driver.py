"""Bounded retained-artifact aggregation. No search entry point exists."""
from __future__ import annotations

import argparse
from datetime import datetime
import hashlib
import math
import os
from pathlib import Path
import re
import subprocess
import sys
import traceback
import unittest

from ..mutation_refinement import authority as a

MODULE = Path(__file__).resolve().parent
REGISTRATION = "eb86131001e68a359f9996a5ec24fcfa1ccb4cef"
PROTOCOL = "GA-KNAPSACK-MUTATION-REFINEMENT-AGGREGATION-RECOVERY-V1"
WORKFLOW = ".github/workflows/knapsack-mutation-refinement-recovery.yml"
SOURCE_RUN = 40516606272
SOURCE_ATTEMPT = 1
SOURCE_SHA = "a1435603e38911a06fa0f6611d1b066337d0aad2"
RESERVE = 10


def authenticate(runtime=False):
    provenance = a.authenticate(runtime=runtime)
    a.require(re.findall(r"\[([^\[\]\r\n]+)\]", os.environ.get("COMMIT_MESSAGE", "")) ==
              ["mutation-refinement-recovery:aggregate"], "Exactly one registered recovery marker required")
    subprocess.run(["git", "merge-base", "--is-ancestor", REGISTRATION, os.environ["GITHUB_SHA"]], cwd=a.ROOT, check=True)
    for filename in ("PROTOCOL_UK.md", "source_artifacts.json"):
        path = MODULE / filename
        raw = subprocess.check_output(["git", "show", REGISTRATION + ":" + path.relative_to(a.ROOT).as_posix()], cwd=a.ROOT)
        a.require(raw == path.read_bytes(), "Registered recovery contract changed")
    inventory = []
    for path in sorted([*MODULE.glob("*.py"), *MODULE.glob("*.md"), *MODULE.glob("tests/*.py"),
                        MODULE / "source_artifacts.json", a.ROOT / WORKFLOW]):
        relative = path.relative_to(a.ROOT).as_posix()
        raw = subprocess.check_output(["git", "show", os.environ["GITHUB_SHA"] + ":" + relative], cwd=a.ROOT)
        a.require(hashlib.sha256(raw).hexdigest() == a.identity(path)["sha256"], "Uncommitted recovery source")
        inventory.append({"path": relative, **a.identity(path)})
    return {**provenance, "protocol_id": PROTOCOL, "recovery_registration_sha": REGISTRATION,
            "recovery_source_files": inventory, "source_run_id": SOURCE_RUN, "source_run_attempt": SOURCE_ATTEMPT,
            "source_sha": SOURCE_SHA, "new_search_authorized": False}


def usage():
    original = a.runner_usage()
    rows = list(original["jobs"])
    current = int(os.environ["GITHUB_RUN_ID"]), int(os.environ["GITHUB_RUN_ATTEMPT"])
    endpoint = "/actions/workflows/" + Path(WORKFLOW).name + "/runs?branch=research%2Fmasters-ga-diversity-crossover"
    seen = {row["job_id"] for row in rows}
    for run in a.pages(endpoint, "workflow_runs"):
        for attempt in range(1, run["run_attempt"] + 1):
            if (run["id"], attempt) == current:
                continue
            allocated = [job for job in a.pages(f"/actions/runs/{run['id']}/attempts/{attempt}/jobs", "jobs")
                         if job.get("conclusion") != "skipped"]
            if not allocated:
                continue
            a.require(run.get("status") == "completed", "Concurrent recovery usage unknown")
            for job in allocated:
                a.require(job["id"] not in seen and job.get("status") == "completed" and
                          job.get("started_at") and job.get("completed_at"), "Unknown recovery job duration")
                seen.add(job["id"])
                seconds = (datetime.fromisoformat(job["completed_at"].replace("Z", "+00:00")) -
                           datetime.fromisoformat(job["started_at"].replace("Z", "+00:00"))).total_seconds()
                a.require(seconds >= 0, "Negative recovery duration")
                rows.append({"run_id": run["id"], "run_attempt": attempt, "job_id": job["id"],
                             "name": job["name"], "conclusion": job.get("conclusion"),
                             "runner_minutes": max(1, math.ceil(seconds / 60))})
    return {"used_runner_minutes": sum(row["runner_minutes"] for row in rows), "jobs": rows}


def validate_source():
    a.grant_for("pilot")  # Same separate sixty-minute technical grant; no inherited budget.
    a.validated_tests()
    from ..mutation_refinement.driver import load_frozen_banks
    load_frozen_banks(check_scores=False)
    registry = a.read_json(MODULE / "source_artifacts.json")
    a.require(registry["source_run_id"] == SOURCE_RUN and registry["source_run_attempt"] == SOURCE_ATTEMPT and
              registry["source_sha"] == SOURCE_SHA and registry["new_search_authorized"] is False,
              "Foreign source registry")
    for row in a.source_manifest()["files"]:
        raw = subprocess.check_output(["git", "show", SOURCE_SHA + ":" + row["path"]], cwd=a.ROOT)
        a.require(hashlib.sha256(raw).hexdigest() == row["sha256"], "Original tested implementation changed")
    run = a.api(f"/actions/runs/{SOURCE_RUN}/attempts/{SOURCE_ATTEMPT}")
    a.require(run.get("status") == "completed" and run.get("head_sha") == SOURCE_SHA and
              run.get("head_branch") == a.BRANCH and run.get("path") == a.WORKFLOW and
              a.phase(run.get("head_commit", {}).get("message", "")) == "pilot",
              "Source run not completed at exact registered SHA")
    jobs = [job for job in a.pages(f"/actions/runs/{SOURCE_RUN}/attempts/{SOURCE_ATTEMPT}/jobs", "jobs")
            if job["name"].startswith("pilot (")]
    a.require(len(jobs) == 4 and {job["name"] for job in jobs} == {f"pilot ({task})" for task in a.PILOT_TASKS} and
              all(job.get("status") == "completed" and job.get("conclusion") == "success" for job in jobs),
              "All four original source worker jobs must be completed successfully")
    a.require(len(registry["artifacts"]) == 6 and len({r["artifact_id"] for r in registry["artifacts"]}) == 6,
              "Wrong original artifact inventory")
    for row in registry["artifacts"]:
        artifact = a.api(f"/actions/artifacts/{row['artifact_id']}")
        a.require(artifact.get("expired") is False and artifact.get("workflow_run", {}).get("id") == SOURCE_RUN and
                  artifact.get("name") == row["name"] and artifact.get("size_in_bytes") == row["zip_bytes"] and
                  artifact.get("digest") == "sha256:" + row["zip_sha256"], "Retained source artifact unavailable or changed")
    return registry


def preflight(output):
    provenance = authenticate()
    registry = validate_source()
    prior = usage()
    a.require(prior["used_runner_minutes"] + RESERVE <= 60, "Insufficient shared sixty-minute balance")
    permit = {**provenance, "usage": prior, "reserved_runner_minutes": RESERVE,
              "grant_identity": a.identity(a.MODULE / "resource_authorization.json"),
              "source_artifact_registry": registry}
    a.write_json(Path(output) / "permit.json", permit)
    a.write_manifest(output)


def recover(workers, permit_directory, output):
    provenance = authenticate(runtime=True)
    a.verify_manifest(permit_directory)
    permit = a.read_json(Path(permit_directory) / "permit.json")
    for field in ("protocol_id", "implementation_sha", "run_id", "run_attempt", "recovery_source_files",
                  "source_manifest", "source_run_id", "source_run_attempt", "source_sha"):
        a.require(permit.get(field) == provenance[field], "Stale or mixed recovery permit: " + field)
    a.require(permit.get("grant_identity") == a.identity(a.MODULE / "resource_authorization.json") and
              permit.get("reserved_runner_minutes") == RESERVE and
              permit["usage"]["used_runner_minutes"] + RESERVE <= 60, "Changed recovery resource authority")
    a.require(validate_source() == permit["source_artifact_registry"], "Changed original source inventory")
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    suite = unittest.defaultTestLoader.discover(str(MODULE / "tests"), pattern="test_*.py", top_level_dir=str(a.ROOT))
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    a.write_json(output / "tests_receipt.json", {**provenance, "tests_run": result.testsRun,
        "tests_passed": result.wasSuccessful(), "failures": len(result.failures), "errors": len(result.errors),
        "skipped": len(result.skipped), "new_ga_runs": 0})
    a.require(result.wasSuccessful() and not result.skipped and result.testsRun > 0, "Recovery fixtures not fully green")
    registry = permit["source_artifact_registry"]
    for artifact in registry["artifacts"]:
        directory = Path(workers) / artifact["name"]
        a.verify_manifest(directory)
        a.require(a.identity(directory / "file_manifest.json")["sha256"] == artifact["file_manifest_sha256"],
                  "Downloaded retained artifact manifest differs")
    original_permit = a.read_json(Path(workers) / f"mutation-refinement-permit-{SOURCE_RUN}-{SOURCE_ATTEMPT}" / "permit.json")
    a.require(original_permit.get("implementation_sha") == SOURCE_SHA and original_permit.get("run_id") == SOURCE_RUN and
              original_permit.get("run_attempt") == SOURCE_ATTEMPT and original_permit.get("phase") == "pilot" and
              original_permit.get("source_manifest") == a.source_manifest(), "Foreign original search permit")
    fields = ("protocol_id", "registration_sha", "implementation_sha", "source_manifest", "run_id", "run_attempt")
    source = {key: original_permit[key] for key in fields}
    from .aggregate import aggregate_saved
    aggregate_saved(workers, output, source, provenance)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("preflight", "recover"))
    parser.add_argument("--output", required=True)
    parser.add_argument("--permit")
    parser.add_argument("--workers")
    args = parser.parse_args()
    try:
        if args.command == "preflight":
            preflight(args.output)
        else:
            a.require(args.permit and args.workers, "Retained artifacts and permit required")
            recover(args.workers, args.permit, args.output)
        return 0
    except Exception as exc:
        a.write_json(Path(args.output) / "failure.json", {"type": type(exc).__name__, "message": str(exc), "new_ga_runs": 0})
        traceback.print_exc()
        return 1
    finally:
        a.write_manifest(args.output)


if __name__ == "__main__":
    sys.exit(main())
