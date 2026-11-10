"""Technical runs only; the independent 900-run series is not enabled here."""
import argparse
from copy import deepcopy
from pathlib import Path
import time

from .common import guard_technical, read_json, require, require_ci, sha, write_json


def make_log(problem, bank, mu, seed, task_index, total=100000):
    """Call the retained single evolution loop without giving it OPT."""
    require_ci()
    require(problem["n"] == 100 and mu in (10, 20, 30), "Configuration outside the 100-item comparison")
    require(type(total) is int and total > mu, "Total evaluations must include a nonempty search")
    require(len(bank["masks"]) == len(bank["scores"]) == 30 and bank["masks"][0] == "0" * 100,
            "The common bank must contain 30 masks with an empty first mask")
    from studies.knapsack_parameters.crossover_population.program.ga_core import (
        create_random_generators, parameter_controller, run_ga,
    )
    generators = create_random_generators(seed, task_index, 0)
    require({name: deepcopy(rng.bit_generator.state) for name, rng in generators.items()} == bank["rng_states"],
            "Initial search streams differ from the shared bank")
    return run_ga(problem, {"masks": bank["masks"][:mu], "scores": bank["scores"][:mu]},
                  parameter_controller(0), generators, budget=total - mu,
                  initial_parameters={"p_m": 0.01, "p_c": 0.9, "target_mu": mu,
                                      "tournament_size": 2, "elite_count": 1},
                  configuration_contract="population-crossover-v1")


def run_pilot(inputs, mu, out):
    protocol = guard_technical()
    require(mu in protocol["populations"], "Unregistered technical population")
    inputs, output = Path(inputs), Path(out)
    require(not output.exists(), "Preserve completed/failed identities instead of repeating them")
    output.mkdir(parents=True)
    manifest = read_json(inputs / "manifest.json")
    require(manifest["status"] == "INPUTS_AUDITED_AND_CERTIFIED" and manifest["holdout_tasks"] == 30,
            "Source and exact-reference audit must pass first")
    for entry in manifest["files"]:
        path = (inputs / entry["path"]).resolve()
        require(path.is_relative_to(inputs.resolve()) and path.is_file(), "Unsafe prepared input")
        require(path.stat().st_size == entry["bytes"] and sha(path) == entry["sha256"], "Prepared input checksum differs")
    tasks = [r for r in manifest["tasks"] if r["phase"] == "technical"]
    require(len(tasks) == 3 and {r["task"] for r in tasks} == set(protocol["pilot"]["cases"]),
            "Pilot must use only the three old tasks")
    from studies.knapsack_parameters.crossover_population.verification import verify_log
    from studies.knapsack_parameters.crossover_population.observations import extract
    records = []
    for task in tasks:
        case_started = time.perf_counter()
        folder = output / task["task"]
        folder.mkdir()
        problem = read_json(inputs / task["task"] / "problem.json")
        bank = read_json(inputs / task["task"] / "bank.json")
        # The search call receives only problem/bank/configuration and six streams.
        started = time.perf_counter()
        log = make_log(problem, bank, mu, protocol["pilot"]["seed"], task["task_index"])
        search_seconds = time.perf_counter() - started
        started = time.perf_counter()
        write_json(folder / "journal.json.gz", log)
        log_write_seconds = time.perf_counter() - started
        started = time.perf_counter()
        checked = verify_log(log)
        verification_seconds = time.perf_counter() - started
        require(checked["verification_status"] == "VERIFIED" and checked["new_calls"] == 100000 - mu,
                "Independent replay or evaluation accounting differs")
        derived = checked.pop("derived_metrics")
        bins = derived["operator_bins"]
        del derived
        write_json(folder / "verification.json", checked)
        write_json(folder / "operator_bins.json", {"operator_bins": bins})
        # Only after the search and independent replay is the exact reference read.
        reference = read_json(inputs / task["task"] / "certificate.json")
        started = time.perf_counter()
        observed = extract(log, 100000, reference["optimum"], checkpoints=tuple(protocol["checkpoints"]))
        observations_seconds = time.perf_counter() - started
        require(observed["final_best_profit"] == checked["record_profit"], "Observation record differs")
        write_json(folder / "observations.json.gz", observed)
        files = {name: sha(folder / name) for name in ("journal.json.gz", "verification.json", "operator_bins.json", "observations.json.gz")}
        byte_count = sum(path.stat().st_size for path in folder.iterdir() if path.is_file())
        require(sum(path.stat().st_size for path in output.rglob("*") if path.is_file()) < 300 * 1024**2,
                "Technical job is approaching the shared artifact ceiling")
        row = {"task": task["task"], "mu": mu, "seed": protocol["pilot"]["seed"], "status": "VERIFIED",
               "total_evaluations": 100000, "initial_evaluations": mu, "new_evaluations": 100000 - mu,
               "search_seconds": search_seconds, "log_write_seconds": log_write_seconds,
               "verification_seconds": verification_seconds, "observations_seconds": observations_seconds,
               "artifact_bytes": byte_count, "sha256": files}
        write_json(folder / "record.json", row)
        row["artifact_bytes"] = sum(path.stat().st_size for path in folder.iterdir() if path.is_file())
        row["case_seconds"] = time.perf_counter() - case_started
        records.append(row)
        print(task["task"], "population", mu, "VERIFIED", flush=True)
        del log, observed, checked, bins
    write_json(output / "pilot.json", {"status": "VERIFIED_TECHNICAL_ONLY", "population": mu, "runs": records,
               "main_runs": 0, "input_manifest_sha256": sha(inputs / "manifest.json")})


def forecast(artifacts, out):
    protocol = guard_technical()
    artifacts = Path(artifacts)
    manifests = list(artifacts.rglob("pilot.json"))
    require(len(manifests) == 3, "Three population pilot artifacts are required")
    rows = []
    for path in manifests:
        item = read_json(path)
        require(item["status"] == "VERIFIED_TECHNICAL_ONLY" and item["main_runs"] == 0, "Invalid pilot stage")
        for row in item["runs"]:
            folder = path.parent / row["task"]
            for name, expected in row["sha256"].items():
                require(sha(folder / name) == expected, "Pilot artifact bytes differ")
            require(row["status"] == "VERIFIED" and row["total_evaluations"] == 100000, "Incomplete pilot")
            rows.append(row)
    require(len(rows) == 9 and {(r["task"], r["mu"]) for r in rows} ==
            {(task, mu) for task in protocol["pilot"]["cases"] for mu in (10, 20, 30)}, "Pilot inventory differs")
    per_mu = {}
    time_seconds = storage_bytes = 0
    fields = ("search_seconds", "log_write_seconds", "verification_seconds", "observations_seconds")
    for mu in (10, 20, 30):
        own = [r for r in rows if r["mu"] == mu]
        require(all(r["case_seconds"] >= sum(r[k] for k in fields) for r in own), "Measured total omits a timed component")
        maximum_time = max(r["case_seconds"] for r in own)
        maximum_bytes = max(r["artifact_bytes"] for r in own)
        per_mu[str(mu)] = {"pilot_runs": 3, "maximum_seconds": maximum_time, "maximum_artifact_bytes": maximum_bytes,
                           "planned_main_runs": 300}
        time_seconds += 300 * maximum_time
        storage_bytes += 300 * maximum_bytes
    # This conservative scenario uses each population's slowest measured old task,
    # a 35% reserve, plus an explicit allowance for 30 worker setups and analysis.
    estimate = {"status": "MEASURED_FORECAST_NOT_MAIN_AUTHORIZATION", "technical_runs_verified": 9,
                "main_runs": 900, "main_total_evaluations": 90000000, "per_population": per_mu,
                "reserve_factor": 1.35, "setup_and_analysis_runner_minutes_allowance": 50,
                "forecast_runner_minutes": 1.35 * time_seconds / 60 + 50,
                "forecast_artifact_bytes": int(1.35 * storage_bytes + 100 * 1024**2),
                "main_authorized": False,
                "limitations": "Three old tasks with one pilot seed estimate resources only; they cannot guarantee future runtime or statistical precision."}
    write_json(Path(out) / "forecast.json", estimate)
    print("Technical pilot 9/9 verified; main series is NOT authorized.", flush=True)
    print("Forecast runner-minutes:", round(estimate["forecast_runner_minutes"], 1), flush=True)
    print("Forecast GiB:", round(estimate["forecast_artifact_bytes"] / 1024**3, 3), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    execute = commands.add_parser("run")
    execute.add_argument("--inputs", type=Path, required=True)
    execute.add_argument("--mu", type=int, choices=(10, 20, 30), required=True)
    execute.add_argument("--out", type=Path, required=True)
    estimate = commands.add_parser("forecast")
    estimate.add_argument("--artifacts", type=Path, required=True)
    estimate.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "run":
        run_pilot(args.inputs, args.mu, args.out)
    else:
        forecast(args.artifacts, args.out)


if __name__ == "__main__":
    main()
