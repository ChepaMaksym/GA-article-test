"""Bound uploads and record resource use; this module never starts search."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path

from .common import guard_main
from .dispatch import api_json, _token
from studies.knapsack_parameters.population_validation_100.common import require, read_json


def directory_bytes(path):
    root = Path(path)
    if not root.exists():
        return 0
    require(root.is_dir() and not root.is_symlink(), "Unsafe bounded artifact directory")
    total = 0
    for item in root.rglob("*"):
        require(not item.is_symlink() and item.resolve().is_relative_to(root.resolve()),
                "Artifact path aliases outside its root")
        if item.is_file():
            total += item.stat().st_size
    return total


def rounded_job_minutes(jobs, *, require_completed):
    """Retain per-job rounding; skipped jobs receive no elapsed runner time."""
    require(type(jobs) is list and len({row.get("id") for row in jobs}) == len(jobs),
            "Resource job inventory is incomplete or duplicated")
    total = 0
    for row in jobs:
        if row.get("conclusion") == "skipped":
            continue
        if require_completed:
            require(row.get("status") == "completed" and row.get("completed_at"),
                    "A prior main run is still executing")
        if row.get("completed_at") and row.get("started_at"):
            seconds = (datetime.fromisoformat(row["completed_at"])
                       - datetime.fromisoformat(row["started_at"])).total_seconds()
            require(seconds >= 0, "Negative runner duration")
            total += math.ceil(seconds / 60)
    return total


def resource_state(authorization, *, include_current=False):
    """Read only this stage's admitted history, never earlier study allowances."""
    prior = authorization.get("charged_prior_run_ids", [])
    require(type(prior) is list and all(type(value) is int and value > 0 for value in prior)
            and len(prior) == len(set(prior)), "Charged prior-run inventory differs")
    current = int(os.environ["GITHUB_RUN_ID"])
    require(current not in prior, "The current run must not be double charged")
    token = _token() if prior or include_current else None
    records, minutes, byte_count = [], 0, 0
    for run_id in [*prior, *([current] if include_current else [])]:
        require_completed = run_id != current
        run = api_json(f"/actions/runs/{run_id}", token)
        require(run.get("repository", {}).get("full_name") == authorization["repository"]
                and run.get("event") == "workflow_dispatch"
                and run.get("path") == ".github/workflows/iterative-validation-population13-main.yml"
                and run.get("head_branch") == authorization["ref"].removeprefix("refs/heads/"),
                "An unrelated workflow cannot enter this stage ledger")
        job_data = api_json(f"/actions/runs/{run_id}/jobs?per_page=100", token)
        artifact_data = api_json(f"/actions/runs/{run_id}/artifacts?per_page=100", token)
        jobs, artifacts = job_data.get("jobs"), artifact_data.get("artifacts")
        require(type(jobs) is list and job_data.get("total_count") == len(jobs) <= 100
                and type(artifacts) is list and artifact_data.get("total_count") == len(artifacts) <= 100,
                "Resource metadata requires a complete non-paginated inventory")
        count = rounded_job_minutes(jobs, require_completed=require_completed)
        size = sum(row["size_in_bytes"] for row in artifacts)
        require(all(type(row.get("size_in_bytes")) is int and row["size_in_bytes"] >= 0 for row in artifacts),
                "Invalid artifact metadata length")
        minutes += count
        byte_count += size
        records.append({"run_id": run_id, "rounded_completed_job_minutes": count,
                        "artifact_bytes": size,
                        "jobs": [{key: row.get(key) for key in
                                  ("id", "name", "status", "conclusion", "started_at", "completed_at")}
                                 for row in jobs],
                        "artifacts": [{key: row.get(key) for key in ("id", "name", "size_in_bytes", "digest")}
                                      for row in artifacts]})
    return {"runs": records, "rounded_completed_job_minutes": minutes, "uploaded_artifact_bytes": byte_count}


def admit(out, authorization_id):
    protocol, authorization = guard_main(authorization_id)
    state = resource_state(authorization)
    require(authorization["remaining_runner_minutes"]
            == authorization["runner_minutes"] - state["rounded_completed_job_minutes"],
            "The declared remaining runner allowance differs from the completed-run ledger")
    path = Path(out)
    require(not path.exists(), "Preserve an earlier resource admission receipt")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes((json.dumps({"schema": "population13-main-budget-admission-v1", **state,
                    "runner_minutes": authorization["runner_minutes"],
                    "remaining_runner_minutes": authorization["remaining_runner_minutes"],
                    "artifact_bytes": authorization["artifact_bytes"],
                    "source_manifest_sha256": authorization["source_manifest_sha256"],
                    "workflow_run_id": os.environ["GITHUB_RUN_ID"], "ga_runs_started": 0},
                    ensure_ascii=False, indent=2) + "\n").encode("utf-8"))


def check_upload(kind, root, authorization_id):
    protocol, _ = guard_main(authorization_id)
    keys = {"inputs": "preparation_artifact_bytes", "metadata": "preparation_metadata_artifact_bytes",
            "raw": "shard_artifact_bytes", "index": "index_artifact_bytes", "analysis": "analysis_artifact_bytes"}
    require(kind in keys, "Unknown upload role")
    size = directory_bytes(root)
    require(size <= protocol["limits"][keys[kind]], "Artifact upload role exceeded its fixed byte cap")
    return size


def plan_budget(plan, receipt, authorization_id):
    _, authorization = guard_main(authorization_id)
    planned, admitted = read_json(plan), read_json(receipt)
    require(admitted["workflow_run_id"] == os.environ["GITHUB_RUN_ID"]
            and planned["workflow_run_id"] == os.environ["GITHUB_RUN_ID"]
            and planned["source_manifest_sha256"] == authorization["source_manifest_sha256"],
            "Budget and dispatch plan origins differ")
    count = len(planned["active_shards"])
    require(5 + 10 + 4 * count + 2 <= admitted["remaining_runner_minutes"],
            "Remaining runner time does not cover the planned dispatch")
    # Bound raw+index uploads before allowing any case job. The remaining roles
    # reserve 16MiB inputs, 4MiB metadata and 48MiB analysis.
    maximum_upload = count * 50 * 1024**2 + (16 + 4 + 48) * 1024**2
    require(admitted["uploaded_artifact_bytes"] + maximum_upload <= authorization["artifact_bytes"],
            "Remaining storage cannot cover all admitted uploads")


def final_receipt(root, authorization_id):
    protocol, authorization = guard_main(authorization_id)
    output = Path(root)
    output.mkdir(parents=True, exist_ok=True)
    state = resource_state(authorization, include_current=True)
    require(state["uploaded_artifact_bytes"] + protocol["limits"]["analysis_artifact_bytes"]
            <= authorization["artifact_bytes"], "Aggregate main-stage upload cap exceeded")
    require(state["rounded_completed_job_minutes"] <= authorization["runner_minutes"],
            "Recorded main-stage runner ceiling exceeded")
    summary = output / "summary.json"
    status = read_json(summary).get("status") if summary.is_file() else "ANALYSIS_INCOMPLETE_OR_FAILED"
    record = {"schema": "population13-main-provisional-resource-receipt-v1", **state,
              "analysis_status": status, "source_manifest_sha256": authorization["source_manifest_sha256"],
              "workflow_run_id": os.environ["GITHUB_RUN_ID"], "workflow_commit": os.environ["GITHUB_SHA"],
              "authorization_id": authorization["authorization_id"], "analysis_job_times_final": False,
              "final_runner_receipt_required_after_completion": True,
              "recorded_at_utc": datetime.now(timezone.utc).isoformat(), "future_stage_started": False}
    (output / "resource_receipt.json").write_bytes((json.dumps(record, ensure_ascii=False, indent=2)
                                                  + "\n").encode("utf-8"))
    check_upload("analysis", output, authorization_id)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("admit", "cap", "plan", "final"))
    parser.add_argument("--authorization-id", required=True)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--root", type=Path)
    parser.add_argument("--kind")
    parser.add_argument("--plan", type=Path)
    parser.add_argument("--receipt", type=Path)
    args = parser.parse_args()
    if args.command == "admit":
        require(args.out is not None, "Admission receipt output is required")
        admit(args.out, args.authorization_id)
    elif args.command == "cap":
        require(args.root is not None, "Upload root is required")
        print(json.dumps({"role": args.kind, "bytes": check_upload(args.kind, args.root, args.authorization_id)}))
    elif args.command == "plan":
        require(args.plan is not None and args.receipt is not None, "Plan and resource receipt are required")
        plan_budget(args.plan, args.receipt, args.authorization_id)
    else:
        require(args.root is not None, "Final resource output root is required")
        final_receipt(args.root, args.authorization_id)


if __name__ == "__main__":
    main()
