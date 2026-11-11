"""Run one authorized six-case block and persist independently verified receipts."""
import argparse
import os
from pathlib import Path
import time
import traceback

from .common import HERE, guard_stage, read_json, require, sha
from .search import make_log
from studies.knapsack_parameters.population_validation_100_main.runner import (
    _safe_file, _verify_files, _used_bytes, _write_bounded,
)

LIMIT = 64 * 1024**2
CASE_START_LIMIT = 350
CHECKPOINTS = (5000, 10000, 20000, 50000, 100000)


def execute(inputs, shard_id, raw_root, compact_root):
    guard_stage("tuning")
    inputs, raw_root, compact_root = map(Path, (inputs, raw_root, compact_root))
    require(not raw_root.exists() and not compact_root.exists(), "Retain already started block evidence")
    require(not raw_root.resolve().is_relative_to(compact_root.resolve())
            and not compact_root.resolve().is_relative_to(raw_root.resolve()), "Evidence roots must be disjoint")
    stage = read_json(inputs / "stage_manifest.json")
    require(stage.get("schema") == "mutation-grid-100-tuning-inputs-v1"
            and stage.get("status") == "STAGE_INPUTS_PREPARED" and stage.get("new_case_count") == 1350
            and stage.get("retained_count") == 1440 and stage.get("overlap_count") == 270,
            "Tuning inputs differ")
    require(sha(inputs / "schedule.json") == stage["schedule_sha256"]
            and sha(inputs / "retained_grid.json.gz") == stage["retained_grid_sha256"]
            and sha(inputs / "prepared/manifest.json") == stage["prepared_manifest_sha256"]
            and sha(HERE / "source_manifest.json") == stage["source_manifest_sha256"],
            "Prepared inputs or sealed source differ")
    schedule = read_json(inputs / "schedule.json")
    blocks = [block for block in schedule["shards"] if block["shard_id"] == shard_id]
    require(len(blocks) == 1 and len(blocks[0]["cases"]) == 6, "Unknown or incomplete block")
    prepared = read_json(inputs / "prepared/manifest.json")
    _verify_files(inputs / "prepared", prepared["files"])
    tasks = {task["task"]: task for task in prepared["tasks"]}
    raw_root.mkdir(parents=True)
    compact_root.mkdir(parents=True)
    from .verification import verify_log
    from .observations import extract
    limit, rows, started = {"limit": LIMIT, "used": 0}, [], time.monotonic()
    for case in blocks[0]["cases"]:
        try:
            require(time.monotonic() - started < CASE_START_LIMIT, "Time reserve reached; preserve completed cases")
            require(limit["used"] < LIMIT - 12 * 1024**2, "Byte reserve reached; preserve completed cases")
            require(case["seed"] in (150001, 150002, 150003) and case["mu"] in (10, 15, 20)
                    and case["pc_percentage"] == 100 and case["mutation_basis_points"] in (25, 50, 75, 150, 200),
                    "Case is outside the registered missing identities")
            task = tasks[case["task"]]
            require(all(task[k] == case[k] for k in ("task_index", "family", "class_label")),
                    "Task identity differs from paired inputs")
            descriptor = next(item for item in task["banks"] if item["seed"] == case["seed"])
            bank_path = _safe_file(inputs / "prepared", descriptor["path"])
            require(sha(bank_path) == descriptor["sha256"], "Initial bank differs")
            problem = read_json(inputs / "prepared" / case["task"] / "problem.json")
            bank = read_json(bank_path)
            prefix = f'{case["task"]}/seed-{case["seed"]}/mu{case["mu"]}-pc100-pm{case["mutation_basis_points"]}bp'
            folder = raw_root / prefix
            folder.mkdir(parents=True, exist_ok=False)
            case_started = mark = time.perf_counter()
            log = make_log(problem, bank, case["mu"], case["mutation_basis_points"], case["seed"], case["task_index"])
            search_seconds = time.perf_counter() - mark
            mark = time.perf_counter()
            _write_bounded(folder / "journal.json.gz", log, limit)
            write_seconds = time.perf_counter() - mark
            mark = time.perf_counter()
            checked = verify_log(log)
            verify_seconds = time.perf_counter() - mark
            require(checked["verification_status"] == "VERIFIED" and checked["new_calls"] == 100000 - case["mu"],
                    "Independent replay or evaluation counter differs")
            bins = checked.pop("derived_metrics")["operator_bins"]
            _write_bounded(folder / "verification.json", checked, limit)
            _write_bounded(folder / "operator_bins.json", {"operator_bins": bins,
                           "premutation_score_checks": checked["premutation_score_checks"]}, limit)
            certificate_path = inputs / "prepared" / case["task"] / "certificate.json"
            require(sha(certificate_path) == task["certificate_sha256"], "Reference checksum differs")
            optimum = read_json(certificate_path)["optimum"]
            mark = time.perf_counter()
            observed = extract(log, 100000, optimum, checkpoints=CHECKPOINTS)
            observations_seconds = time.perf_counter() - mark
            require(observed["final_best_profit"] == checked["record_profit"], "Observed record differs")
            _write_bounded(folder / "observations.json.gz", observed, limit)
            names = ("journal.json.gz", "verification.json", "operator_bins.json", "observations.json.gz")
            hashes = {name: sha(folder / name) for name in names}
            record = {**case, "status": "VERIFIED", "total_evaluations": 100000,
                      "initial_evaluations": case["mu"], "new_evaluations": 100000 - case["mu"],
                      "bank_sha256": descriptor["sha256"], "certificate_sha256": task["certificate_sha256"],
                      "artifact_hashes": dict(hashes), "workflow_run_id": os.environ["GITHUB_RUN_ID"],
                      "workflow_commit": os.environ["GITHUB_SHA"], "code_manifest_sha256": sha(HERE / "source_manifest.json"),
                      "stage_manifest_sha256": sha(inputs / "stage_manifest.json"),
                      "search_seconds": search_seconds, "log_write_seconds": write_seconds,
                      "verification_seconds": verify_seconds, "observations_seconds": observations_seconds}
            _write_bounded(folder / "record.json", record, limit)
            hashes["record.json"] = sha(folder / "record.json")
            elapsed = time.perf_counter() - case_started
            require(elapsed >= search_seconds + write_seconds + verify_seconds + observations_seconds,
                    "Measured case time omits a component")
            row = {**case, "optimum": optimum, "best": observed["final_best_profit"],
                   "events": [[event["q"], event["profit"]] for event in observed["record_events"]],
                   "checkpoints": [{"q": p["q"], "record_profit": p["record_profit"],
                                    "population_metrics": p["population_metrics"],
                                    "completed_generations": p["completed_generations"]} for p in observed["checkpoints"]],
                   "targets": observed["targets"], "completed_generations": observed["completed_generations"],
                   "duplicates": checked["duplicate_candidates"], "artifact_hashes": hashes,
                   "artifact_prefix": prefix, "bank_sha256": descriptor["sha256"],
                   "certificate_sha256": task["certificate_sha256"],
                   "timing": {"search_seconds": search_seconds, "log_write_seconds": write_seconds,
                              "verification_seconds": verify_seconds, "observations_seconds": observations_seconds,
                              "case_seconds": elapsed, "artifact_bytes": _used_bytes(folder)}}
            receipt = compact_root / "records" / f'{case["task"]}-seed{case["seed"]}-mu{case["mu"]}-pm{case["mutation_basis_points"]}bp.json'
            _write_bounded(receipt, row, limit)
            rows.append(row)
            require(_used_bytes(raw_root, compact_root) == limit["used"] <= LIMIT, "Block byte accounting differs")
            print(case["task"], case["seed"], case["mu"], case["mutation_basis_points"], "VERIFIED", flush=True)
            del log, checked, observed, bins
        except Exception as error:
            _write_bounded(compact_root / f"failure-{len(rows):02d}.json",
                           {"status": "FAILED_OR_INTERRUPTED", "case": case, "completed_case_count": len(rows),
                            "type": type(error).__name__, "message": str(error)[:1000],
                            "traceback": traceback.format_exc(limit=8)}, limit, emergency=True)
            raise
    require(len(rows) == 6, "A completed block must contain six verified cases")
    _write_bounded(compact_root / "shard.json", {"schema": "mutation-grid-100-tuning-shard-v1", "status": "VERIFIED",
                   "shard_id": shard_id, "runs": rows, "stage_manifest_sha256": sha(inputs / "stage_manifest.json"),
                   "workflow_run_id": os.environ["GITHUB_RUN_ID"], "workflow_commit": os.environ["GITHUB_SHA"],
                   "source_manifest_sha256": sha(HERE / "source_manifest.json"),
                   "raw_artifact_name": f'mutation-grid100-tuning-raw-{shard_id}-{os.environ["GITHUB_RUN_ID"]}'}, limit)
    require(_used_bytes(raw_root, compact_root) == limit["used"] <= LIMIT, "Final block byte accounting differs")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inputs", type=Path, required=True)
    parser.add_argument("--shard", required=True)
    parser.add_argument("--raw", type=Path, required=True)
    parser.add_argument("--compact", type=Path, required=True)
    args = parser.parse_args()
    execute(args.inputs, args.shard, args.raw, args.compact)


if __name__ == "__main__":
    main()
