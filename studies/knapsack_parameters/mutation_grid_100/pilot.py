"""Run only the registered technical cases after separate resource permission."""
import argparse
from copy import deepcopy
import os
from pathlib import Path
import time
import traceback

from .common import HERE, guard_stage, read_json, require, sha
from .search import make_log
from studies.knapsack_parameters.population_validation_100_main.runner import (
    _safe_file, _verify_files, _used_bytes, _write_bounded,
)

PER_RUN_BYTES = 20 * 1024**2
TOTAL = 100000
CHECKPOINTS = (5000, 10000, 20000, 50000, 100000)


def comparable_log(log):
    """Exclude only timings and the two intentionally versioned contract fields."""
    result = deepcopy(log)
    for key in ("timing_ns", "schema", "configuration_contract"):
        result.pop(key, None)
    return result


def execute(inputs, case, mu, out, compatibility=False):
    protocol = guard_stage("technical")
    technical = protocol["technical"]
    require(type(mu) is int and mu in technical["populations"], "Unregistered technical population")
    cases = technical["compatibility_tasks"] if compatibility else technical["tasks"]
    require(case in cases, "Unregistered technical task")
    inputs, output = Path(inputs), Path(out)
    require(not output.exists(), "Preserve completed and partial technical evidence")
    manifest_path = inputs / "manifest.json"
    manifest = read_json(manifest_path)
    _verify_files(inputs, manifest["files"])
    tasks = [task for task in manifest["tasks"] if task["task"] == case]
    require(len(tasks) == 1, "Missing or duplicate technical task")
    task = tasks[0]
    task_directory = inputs / case
    problem = read_json(task_directory / "problem.json")
    bank_path = task_directory / ("compatibility_bank.json" if compatibility else "bank.json")
    bank = read_json(bank_path)
    seed = technical["compatibility_seed"] if compatibility else technical["seed"]
    expected_preparation = 150000 if compatibility else technical["preparation_seed"]
    require(bank.get("preparation_seed") == expected_preparation, "Preparation seed differs")
    rates = (100,) if compatibility else tuple(technical["mutation_basis_points"])
    output.mkdir(parents=True)
    rows, started = [], time.perf_counter()
    from .verification import verify_log
    from .observations import extract
    for rate in rates:
        folder = output / f"pm{rate}bp"
        folder.mkdir()
        budget = {"limit": PER_RUN_BYTES, "used": 0}
        case_started = time.perf_counter()
        try:
            mark = time.perf_counter()
            log = make_log(problem, bank, mu, rate, seed, task["task_index"], total=TOTAL)
            search_seconds = time.perf_counter() - mark
            mark = time.perf_counter()
            _write_bounded(folder / "journal.json.gz", log, budget)
            write_seconds = time.perf_counter() - mark
            mark = time.perf_counter()
            checked = verify_log(log)
            verification_seconds = time.perf_counter() - mark
            require(checked["verification_status"] == "VERIFIED" and checked["new_calls"] == TOTAL - mu,
                    "Independent replay or evaluation count differs")
            bins = checked.pop("derived_metrics")["operator_bins"]
            _write_bounded(folder / "verification.json", checked, budget)
            _write_bounded(folder / "operator_bins.json", {"operator_bins": bins,
                           "premutation_score_checks": checked["premutation_score_checks"]}, budget)
            reference_sha256 = None
            compatibility_seconds = 0.0
            if compatibility:
                mark = time.perf_counter()
                reference_path = _safe_file(inputs, f"references/{case}/mu{mu}/journal.json.gz")
                reference = read_json(reference_path)
                require(reference.get("schema") == "ga-knapsack-population-crossover-log-v1"
                        and reference.get("configuration_contract") == "population-crossover-v1"
                        and log.get("schema") == "ga-knapsack-fixed-mutation-grid-log-v1"
                        and log.get("configuration_contract") == "fixed-mutation-grid-v1",
                        "Compatibility schemas or contracts differ from the declared migration")
                require(comparable_log(log) == comparable_log(reference),
                        "Full historical replay differs outside timings and intentional version fields")
                from studies.knapsack_parameters.crossover_population.observations import extract as old_extract
                reference_sha256 = sha(reference_path)
                compatibility_seconds = time.perf_counter() - mark
            # Reference optima are read only after search and independent replay.
            certificate_path = task_directory / "certificate.json"
            optimum = read_json(certificate_path)["optimum"]
            mark = time.perf_counter()
            observed = extract(log, TOTAL, optimum, checkpoints=CHECKPOINTS)
            require(observed["final_best_profit"] == checked["record_profit"], "Observed record differs")
            if compatibility:
                previous = old_extract(reference, TOTAL, optimum, checkpoints=CHECKPOINTS)
                current = deepcopy(observed)
                previous.pop("schema", None)
                current.pop("schema", None)
                require(current == previous, "All retained observations must remain identical at one-percent mutation")
                del previous, current, reference
            observations_seconds = time.perf_counter() - mark
            _write_bounded(folder / "observations.json.gz", observed, budget)
            names = ("journal.json.gz", "verification.json", "operator_bins.json", "observations.json.gz")
            row = {"status": "VERIFIED", "mode": "compatibility" if compatibility else "pilot",
                   "task": case, "task_index": task["task_index"], "mu": mu,
                   "pc_percentage": 100, "mutation_basis_points": rate, "seed": seed,
                   "preparation_seed": expected_preparation, "total_evaluations": TOTAL,
                   "initial_evaluations": mu, "new_evaluations": TOTAL - mu,
                   "known_start_score_validation_checks": mu,
                   "replay_score_checks": checked["independent_score_checks"],
                   "premutation_score_checks": checked["premutation_score_checks"],
                   "bank_sha256": sha(bank_path), "certificate_sha256": sha(certificate_path),
                   "artifact_hashes": {name: sha(folder / name) for name in names},
                   "reference_sha256": reference_sha256, "search_seconds": search_seconds,
                   "log_write_seconds": write_seconds, "verification_seconds": verification_seconds,
                   "compatibility_seconds": compatibility_seconds,
                   "observations_seconds": observations_seconds,
                   "workflow_run_id": os.environ["GITHUB_RUN_ID"], "workflow_commit": os.environ["GITHUB_SHA"],
                   "source_manifest_sha256": sha(HERE / "source_manifest.json")}
            _write_bounded(folder / "record.json", row, budget)
            row["case_seconds"] = time.perf_counter() - case_started
            row["artifact_bytes"] = _used_bytes(folder)
            require(_used_bytes(folder) == budget["used"] <= PER_RUN_BYTES, "Per-case byte accounting differs")
            rows.append(row)
            print(case, mu, rate, row["mode"], "VERIFIED", flush=True)
            del log, checked, observed, bins
        except Exception as error:
            _write_bounded(folder / "failure.json", {"status": "FAILED_OR_INTERRUPTED", "task": case,
                           "mu": mu, "mutation_basis_points": rate, "seed": seed,
                           "error_type": type(error).__name__, "message": str(error)[:1000],
                           "traceback": traceback.format_exc(limit=8)}, budget, emergency=True)
            raise
    budget = {"limit": len(rates) * PER_RUN_BYTES + 1024**2, "used": _used_bytes(output)}
    _write_bounded(output / "technical.json", {"schema": "mutation-grid-100-technical-shard-v1",
                   "status": "VERIFIED", "runs": rows,
                   "inputs_manifest_sha256": sha(manifest_path),
                   "source_manifest_sha256": sha(HERE / "source_manifest.json"),
                   "workflow_run_id": os.environ["GITHUB_RUN_ID"], "workflow_commit": os.environ["GITHUB_SHA"],
                   "elapsed_seconds": time.perf_counter() - started,
                   "new_tuning_runs": 0, "new_validation_runs": 0}, budget)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inputs", type=Path, required=True)
    parser.add_argument("--case", required=True)
    parser.add_argument("--mu", type=int, choices=(10, 15, 20), required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--compatibility", action="store_true")
    args = parser.parse_args()
    execute(args.inputs, args.case, args.mu, args.out, args.compatibility)


if __name__ == "__main__":
    main()
