"""Execute one frozen six-case tuning block using the unchanged GA core."""
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
TIME_RESERVE = 60
CASE_START_LIMIT = 390 - TIME_RESERVE
CHECKPOINTS = (5000, 10000, 20000, 50000, 100000)


def execute(inputs, shard_id, raw_root, compact_root):
    protocol = guard_stage("tuning")
    inputs, raw_root, compact_root = map(Path, (inputs, raw_root, compact_root))
    require(not raw_root.exists() and not compact_root.exists(), "Preserve previously started block evidence")
    require(not raw_root.resolve().is_relative_to(compact_root.resolve())
            and not compact_root.resolve().is_relative_to(raw_root.resolve()), "Evidence roots must be disjoint")
    stage = read_json(inputs / "stage_manifest.json")
    require(stage.get("schema") == "initial-grid-100-stage-inputs-v1" and stage.get("stage") == "tuning"
            and stage.get("status") == "STAGE_INPUTS_PREPARED" and stage.get("retained_count") == 180
            and stage.get("new_case_count") == 1260, "Tuning inputs are incomplete")
    require(sha(inputs / "schedule.json") == stage["schedule_sha256"]
            and sha(inputs / "reused.json") == stage["reused_sha256"]
            and sha(inputs / "prepared/manifest.json") == stage["prepared_manifest_sha256"],
            "Frozen input or retained-case checksum differs")
    schedule = read_json(inputs / "schedule.json")
    blocks = [block for block in schedule["shards"] if block["shard_id"] == shard_id]
    require(len(blocks) == 1 and len(blocks[0]["cases"]) == 6, "Unknown or incomplete tuning block")
    old = read_json(inputs / "prepared/manifest.json")
    _verify_files(inputs / "prepared", old["files"])
    tasks = {task["task"]: task for task in old["tasks"]}
    raw_root.mkdir(parents=True)
    compact_root.mkdir(parents=True)
    from studies.knapsack_parameters.crossover_population.verification import verify_log
    from studies.knapsack_parameters.crossover_population.observations import extract
    budget, rows, started = {"limit": LIMIT, "used": 0}, [], time.monotonic()
    for case in blocks[0]["cases"]:
        try:
            require(time.monotonic() - started < CASE_START_LIMIT, "Time reserve reached; retain completed cases")
            require(budget["used"] < LIMIT - 12 * 1024**2, "Byte reserve reached; retain completed cases")
            require(case["seed"] in protocol["tuning"]["seeds"] and case["mu"] in (10, 15, 20, 25)
                    and case["pc_percentage"] in (70, 80, 90, 100)
                    and (case["mu"], case["pc_percentage"]) not in ((10, 90), (20, 90)),
                    "Case would repeat a retained configuration or is outside the grid")
            task = tasks[case["task"]]
            require(task["task_index"] == case["task_index"] and task["family"] == case["family"]
                    and task["class_label"] == case["class_label"], "Case identity differs from the paired inputs")
            descriptor = next(item for item in task["banks"] if item["seed"] == case["seed"])
            bank_path = _safe_file(inputs / "prepared", descriptor["path"])
            require(sha(bank_path) == descriptor["sha256"], "Initial bank differs")
            problem = read_json(inputs / "prepared" / case["task"] / "problem.json")
            bank = read_json(bank_path)
            case_path = f'{case["task"]}/seed-{case["seed"]}/mu{case["mu"]}-pc{case["pc_percentage"]}'
            folder = raw_root / case_path
            folder.mkdir(parents=True, exist_ok=False)
            case_started, mark = time.perf_counter(), time.perf_counter()
            log = make_log(problem, bank, case["mu"], case["pc_percentage"], case["seed"], case["task_index"])
            search_seconds = time.perf_counter() - mark
            mark = time.perf_counter()
            _write_bounded(folder / "journal.json.gz", log, budget)
            write_seconds = time.perf_counter() - mark
            mark = time.perf_counter()
            checked = verify_log(log)
            verification_seconds = time.perf_counter() - mark
            require(checked["verification_status"] == "VERIFIED"
                    and checked["new_calls"] == 100000 - case["mu"], "Independent replay differs")
            bins = checked.pop("derived_metrics")["operator_bins"]
            _write_bounded(folder / "verification.json", checked, budget)
            _write_bounded(folder / "operator_bins.json", {"operator_bins": bins,
                           "premutation_score_checks": checked["premutation_score_checks"]}, budget)
            # Exact references are used only after search and independent replay.
            certificate_path = inputs / "prepared" / case["task"] / "certificate.json"
            require(sha(certificate_path) == task["certificate_sha256"], "Exact reference differs")
            optimum = read_json(certificate_path)["optimum"]
            mark = time.perf_counter()
            observed = extract(log, 100000, optimum, checkpoints=CHECKPOINTS)
            observations_seconds = time.perf_counter() - mark
            require(observed["final_best_profit"] == checked["record_profit"], "Observed record differs")
            _write_bounded(folder / "observations.json.gz", observed, budget)
            names = ("journal.json.gz", "verification.json", "operator_bins.json", "observations.json.gz")
            hashes = {name: sha(folder / name) for name in names}
            record = {**case, "status": "VERIFIED", "total_evaluations": 100000,
                      "initial_evaluations": case["mu"], "new_evaluations": 100000 - case["mu"],
                      "bank_sha256": descriptor["sha256"], "certificate_sha256": task["certificate_sha256"],
                      "artifact_hashes": hashes, "workflow_run_id": os.environ["GITHUB_RUN_ID"],
                      "workflow_commit": os.environ["GITHUB_SHA"], "code_manifest_sha256": sha(HERE / "source_manifest.json"),
                      "stage_manifest_sha256": sha(inputs / "stage_manifest.json"),
                      "search_seconds": search_seconds, "log_write_seconds": write_seconds,
                      "verification_seconds": verification_seconds, "observations_seconds": observations_seconds}
            _write_bounded(folder / "record.json", record, budget)
            hashes["record.json"] = sha(folder / "record.json")
            elapsed = time.perf_counter() - case_started
            require(elapsed >= search_seconds + write_seconds + verification_seconds + observations_seconds,
                    "Measured case time omits a component")
            row = {**case, "optimum": optimum, "best": observed["final_best_profit"],
                   "events": [[e["q"], e["profit"]] for e in observed["record_events"]],
                   "checkpoints": [{"q": p["q"], "record_profit": p["record_profit"],
                                    "population_metrics": p["population_metrics"],
                                    "completed_generations": p["completed_generations"]} for p in observed["checkpoints"]],
                   "targets": observed["targets"], "completed_generations": observed["completed_generations"],
                   "duplicates": checked["duplicate_candidates"], "artifact_hashes": hashes,
                   "artifact_prefix": case_path, "bank_sha256": descriptor["sha256"],
                   "certificate_sha256": task["certificate_sha256"],
                   "timing": {"search_seconds": search_seconds, "log_write_seconds": write_seconds,
                              "verification_seconds": verification_seconds, "observations_seconds": observations_seconds,
                              "case_seconds": elapsed, "artifact_bytes": _used_bytes(folder)}}
            receipt = compact_root / "records" / f'{case["task"]}-seed{case["seed"]}-mu{case["mu"]}-pc{case["pc_percentage"]}.json'
            _write_bounded(receipt, row, budget)
            rows.append(row)
            require(_used_bytes(raw_root, compact_root) == budget["used"] <= LIMIT, "Block resource accounting differs")
            print(case["task"], case["seed"], case["mu"], case["pc_percentage"], "VERIFIED", flush=True)
            del log, checked, observed, bins
        except Exception as error:
            _write_bounded(compact_root / f"failure-{len(rows):02d}.json",
                           {"status": "FAILED_OR_INTERRUPTED", "case": case, "completed_case_count": len(rows),
                            "type": type(error).__name__, "message": str(error)[:1000],
                            "traceback": traceback.format_exc(limit=8)}, budget, emergency=True)
            raise
    require(len(rows) == 6, "A completed block must contain six verified cases")
    _write_bounded(compact_root / "shard.json", {"schema": "initial-grid-100-tuning-shard-v1", "status": "VERIFIED",
                   "shard_id": shard_id, "runs": rows, "stage_manifest_sha256": sha(inputs / "stage_manifest.json"),
                   "workflow_run_id": os.environ["GITHUB_RUN_ID"], "workflow_commit": os.environ["GITHUB_SHA"],
                   "source_manifest_sha256": sha(HERE / "source_manifest.json"),
                   "raw_artifact_name": f'initial-grid100-tuning-raw-{shard_id}-{os.environ["GITHUB_RUN_ID"]}'}, budget)
    require(_used_bytes(raw_root, compact_root) == budget["used"] <= LIMIT, "Final block accounting differs")


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
