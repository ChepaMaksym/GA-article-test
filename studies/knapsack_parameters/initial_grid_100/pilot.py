"""Run only the separately authorized technical and compatibility cases in CI."""
import argparse
from copy import deepcopy
import os
from pathlib import Path
import time
import traceback

from .common import HERE, guard_stage
from .search import make_log
from studies.knapsack_parameters.population_validation_100.common import read_json, require, sha
from studies.knapsack_parameters.population_validation_100_main.runner import (
    _safe_file, _verify_files, _used_bytes, _write_bounded,
)

PER_RUN_BYTES = 32 * 1024**2
TOTAL = 100000
CHECKPOINTS = (5000, 10000, 20000, 50000, 100000)


def comparable_log(log):
    """Ignore only measured execution time when comparing complete GA evidence."""
    copied = deepcopy(log)
    copied.pop("timing_ns", None)
    return copied


def run_pilot(inputs, case, mu, out, *, compatibility=False, references=None):
    protocol = guard_stage("technical")
    technical = protocol["technical"]
    require(case in technical["cases"], "Technical task is outside the registered plan")
    require(type(compatibility) is bool, "Invalid technical mode")
    require(mu in ((10, 20) if compatibility else (15, 25)), "Unregistered technical population")
    require((references is not None) == compatibility, "Compatibility needs the retained reference directory")
    inputs, output = Path(inputs), Path(out)
    require(not output.exists(), "Retain completed or interrupted technical evidence")
    manifest_path = inputs / "manifest.json"
    manifest = read_json(manifest_path)
    _verify_files(inputs, manifest["files"])
    tasks = [row for row in manifest["tasks"] if row.get("task", row.get("task_id")) == case]
    require(len(tasks) == 1, "Technical task inventory is incomplete or duplicated")
    task_index = tasks[0]["task_index"]
    task_directory = inputs / case
    problem = read_json(task_directory / "problem.json")
    bank_name = "compatibility_bank.json" if compatibility else "bank.json"
    bank_path = task_directory / bank_name
    bank = read_json(bank_path)
    seed = 149999 if compatibility else 159999
    preparation_seed = 149998 if compatibility else 159998
    require(bank.get("preparation_seed") == preparation_seed, "Technical preparation seed differs")
    percentages = (90,) if compatibility else (70, 100)
    output.mkdir(parents=True, exist_ok=False)
    all_started, rows = time.perf_counter(), []
    from studies.knapsack_parameters.crossover_population.verification import verify_log
    from studies.knapsack_parameters.crossover_population.observations import extract
    for pc_percentage in percentages:
        folder = output / f"pc{pc_percentage}"
        folder.mkdir()
        budget = {"limit": PER_RUN_BYTES, "used": 0}
        case_started = time.perf_counter()
        try:
            mark = time.perf_counter()
            log = make_log(problem, bank, mu, pc_percentage, seed, task_index, total=TOTAL)
            search_seconds = time.perf_counter() - mark
            mark = time.perf_counter()
            _write_bounded(folder / "journal.json.gz", log, budget)
            log_write_seconds = time.perf_counter() - mark
            mark = time.perf_counter()
            checked = verify_log(log)
            verification_seconds = time.perf_counter() - mark
            require(checked["verification_status"] == "VERIFIED" and checked["new_calls"] == TOTAL - mu,
                    "Technical replay or evaluation count differs")
            derived = checked.pop("derived_metrics")
            bins = derived["operator_bins"]
            del derived
            _write_bounded(folder / "verification.json", checked, budget)
            _write_bounded(folder / "operator_bins.json", {"operator_bins": bins,
                           "premutation_score_checks": checked["premutation_score_checks"]}, budget)
            compatibility_seconds = 0.0
            reference_sha256 = None
            if compatibility:
                mark = time.perf_counter()
                reference_path = _safe_file(Path(references), case + "/journal.json.gz")
                reference = read_json(reference_path)
                require(comparable_log(log) == comparable_log(reference),
                        "Exact historical compatibility failed outside execution timing")
                reference_sha256 = sha(reference_path)
                compatibility_seconds = time.perf_counter() - mark
                del reference
            # The reference optimum is read only after the search and replay.
            certificate = read_json(task_directory / "certificate.json")
            mark = time.perf_counter()
            observed = extract(log, TOTAL, certificate["optimum"], checkpoints=CHECKPOINTS)
            observations_seconds = time.perf_counter() - mark
            require(observed["final_best_profit"] == checked["record_profit"], "Observed record differs from replay")
            _write_bounded(folder / "observations.json.gz", observed, budget)
            names = ("journal.json.gz", "verification.json", "operator_bins.json", "observations.json.gz")
            row = {"status": "VERIFIED", "mode": "compatibility" if compatibility else "pilot",
                   "task": case, "task_index": task_index, "mu": mu, "pc_percentage": pc_percentage,
                   "seed": seed, "preparation_seed": preparation_seed,
                   "total_evaluations": TOTAL, "initial_evaluations": mu, "new_evaluations": TOTAL - mu,
                   "known_start_score_validation_checks": mu,
                   "replay_score_checks": checked["independent_score_checks"],
                   "premutation_score_checks": checked["premutation_score_checks"],
                   "bank_sha256": sha(bank_path), "certificate_sha256": sha(task_directory / "certificate.json"),
                   "artifact_hashes": {name: sha(folder / name) for name in names},
                   "reference_sha256": reference_sha256,
                   "search_seconds": search_seconds, "log_write_seconds": log_write_seconds,
                   "verification_seconds": verification_seconds, "compatibility_seconds": compatibility_seconds,
                   "observations_seconds": observations_seconds,
                   "workflow_run_id": os.environ["GITHUB_RUN_ID"], "workflow_commit": os.environ["GITHUB_SHA"],
                   "source_manifest_sha256": sha(HERE / "source_manifest.json")}
            _write_bounded(folder / "record.json", row, budget)
            row["case_seconds"] = time.perf_counter() - case_started
            row["artifact_bytes"] = _used_bytes(folder)
            require(row["case_seconds"] >= sum(row[key] for key in
                    ("search_seconds", "log_write_seconds", "verification_seconds", "compatibility_seconds", "observations_seconds")),
                    "Technical case timer omits a component")
            rows.append(row)
            require(_used_bytes(folder) == budget["used"] <= PER_RUN_BYTES, "Technical per-run byte count differs")
            print(case, "population", mu, "crossover", pc_percentage, row["mode"], "VERIFIED", flush=True)
            del log, checked, observed, bins
        except Exception as error:
            _write_bounded(folder / "failure.json", {"status": "FAILED_OR_INTERRUPTED", "task": case,
                           "mu": mu, "pc_percentage": pc_percentage, "seed": seed,
                           "error_type": type(error).__name__, "message": str(error)[:1000],
                           "traceback": traceback.format_exc(limit=8)}, budget, emergency=True)
            raise
    summary_budget = {"limit": len(percentages) * PER_RUN_BYTES, "used": _used_bytes(output)}
    _write_bounded(output / "technical.json", {"schema": "initial-grid-100-technical-shard-v1",
                   "status": "VERIFIED", "mode": "compatibility" if compatibility else "pilot",
                   "task": case, "mu": mu, "runs": rows,
                   "inputs_manifest_sha256": sha(manifest_path),
                   "source_manifest_sha256": sha(HERE / "source_manifest.json"),
                   "workflow_run_id": os.environ["GITHUB_RUN_ID"], "workflow_commit": os.environ["GITHUB_SHA"],
                   "elapsed_seconds": time.perf_counter() - all_started,
                   "artifact_bytes_before_manifest": summary_budget["used"],
                   "new_tuning_runs": 0, "new_validation_runs": 0}, summary_budget)
    require(_used_bytes(output) == summary_budget["used"] <= summary_budget["limit"], "Technical shard byte count differs")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inputs", type=Path, required=True)
    parser.add_argument("--case", required=True)
    parser.add_argument("--mu", type=int, choices=(10, 15, 20, 25), required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--compatibility", action="store_true")
    parser.add_argument("--references", type=Path)
    args = parser.parse_args()
    run_pilot(args.inputs, args.case, args.mu, args.out,
              compatibility=args.compatibility, references=args.references)


if __name__ == "__main__":
    main()
