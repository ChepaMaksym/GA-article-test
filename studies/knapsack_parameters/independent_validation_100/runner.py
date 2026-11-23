"""Run and immediately replay paired holdout cases under the frozen GA contract."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import shutil
import time

from studies.knapsack_parameters.iterative_validation_population13.pilot import check_accounting
from studies.knapsack_parameters.mutation_grid_100.analysis import validate_row
from studies.knapsack_parameters.mutation_grid_100.observations import extract
from studies.knapsack_parameters.mutation_grid_100.validation.search import make_log
from studies.knapsack_parameters.mutation_grid_100.verification import verify_log
from studies.knapsack_parameters.population_validation_100.common import read_json, require, sha
from studies.knapsack_parameters.population_validation_100_main.runner import _used_bytes, _write_bounded

from .common import guard
from .preparation import input_descriptors, load_case


TOTAL = 100_000
CHECKPOINTS = (5000, 10000, 20000, 50000, TOTAL)
PROFILES = ((10, 90, 100), (15, 90, 100), (15, 100, 100), (20, 90, 100))
KINDS = ("UC", "WC", "SC")
SHARD_SIZE = 6
SHARD_BYTES = 96 * 1024**2
MAX_CASE_BYTES = 15 * 1024**2
PAYLOADS = ("journal.json.gz", "verification.json", "operator_bins.json", "observations.json.gz")
CASE_FILES = {*PAYLOADS, "record.json"}
SCHEMA = "independent-validation100-case-v1"


def identity(case):
    return (f"{case['task']}-seed-{case['seed']}-mu{case['mu']}"
            f"-pc{case['pc_percentage']}-pm{case['mutation_basis_points']}bp")


def raw_prefix(case):
    return (f"{case['task']}/seed-{case['seed']}/mu{case['mu']}"
            f"-pc{case['pc_percentage']}-pm{case['mutation_basis_points']}bp")


def _checked_cases(schedule):
    rows = schedule["cases"]
    require(type(rows) is list and len(rows) == 1200, "The independent schedule requires 1,200 cases")
    ids = set()
    for row in rows:
        family, kind = row["family"], row["class_label"]
        require(family in {f"s{i:03d}" for i in range(60, 70)} and kind in KINDS,
                "Task outside the registered holdout")
        require(all(type(row.get(key)) is int for key in
                    ("task_index", "seed", "mu", "pc_percentage", "mutation_basis_points"))
                and row["task"] == f"n00100-{kind}-{family}"
                and row["task_index"] == 33 + 3 * (int(family[1:]) - 60) + KINDS.index(kind)
                and row["seed"] in range(160001, 160011)
                and (row["mu"], row["pc_percentage"], row["mutation_basis_points"]) in PROFILES,
                "Unregistered task, seed or configuration")
        case_id = identity(row)
        require(case_id == row["case_id"] and case_id not in ids, "Duplicate or changed case identity")
        ids.add(case_id)
    return rows


def _binding(auth, inputs):
    return {"workflow_commit": os.environ["GITHUB_SHA"], "workflow_run_id": os.environ["GITHUB_RUN_ID"],
            "authorization_id": auth["authorization_id"], "source_manifest_sha256": auth["source_manifest_sha256"],
            "inputs_manifest_sha256": sha(inputs / "manifest.json")}


def _expected_parameters(case):
    return {"target_mu": case["mu"], "p_c": case["pc_percentage"] / 100,
            "p_m": case["mutation_basis_points"] / 10000, "elite_count": 1, "tournament_size": 2}


def _summary(case, verification, observed, optimum):
    return {**case, "schema": SCHEMA, "status": "VERIFIED", "optimum": optimum,
            "best": observed["final_best_profit"],
            "events": [[row["q"], row["profit"]] for row in observed["record_events"]],
            "targets": observed["targets"],
            "checkpoints": [{key: point[key] for key in
                             ("q", "record_profit", "population_metrics", "completed_generations")}
                            for point in observed["checkpoints"]],
            "duplicates": verification["duplicate_candidates"],
            "completed_generations": verification["completed_generations"],
            "artifact_prefix": raw_prefix(case)}


def execute_case(case, problem, bank, certificate, descriptors, origin, raw_root, compact_root,
                 writer_budget, *, search=make_log, phase="validation"):
    """Use only problem/bank in search; independently replay before extracting any outcome."""
    started = time.perf_counter()
    folder = raw_root / raw_prefix(case)
    row_path = compact_root / "records" / (case["case_id"] + ".json")
    require(not folder.exists() and not row_path.exists(), "Keep prior completed or interrupted evidence")
    folder.mkdir(parents=True, exist_ok=False)
    profile = (case["mu"], case["pc_percentage"], case["mutation_basis_points"])
    mark = time.perf_counter()
    log = search(problem, bank, profile, case["seed"], case["task_index"], TOTAL)
    search_seconds = time.perf_counter() - mark
    counts = check_accounting(log, case["mu"], TOTAL)
    expected = _expected_parameters(case)
    require(log["rng_initial"] == bank["rng_states"] and log["initial_masks"] == bank["masks"][:case["mu"]]
            and log["initial_scores"] == bank["scores"][:case["mu"]]
            and log["initial_parameters"] == expected
            and all(g["parameters_before"] == g["parameters_after"] == expected for g in log["generations"]),
            "Common prefix, random streams or fixed parameters differ")
    mark = time.perf_counter()
    _write_bounded(folder / "journal.json.gz", log, writer_budget)
    log_seconds = time.perf_counter() - mark
    mark = time.perf_counter()
    checked = verify_log(log)
    replay_seconds = time.perf_counter() - mark
    new = TOTAL - case["mu"]
    require(checked["verification_status"] == "VERIFIED" and checked["new_calls"] == new
            and checked["independent_score_checks"] == case["mu"] + 2 * new
            and checked["final_parameters"] == expected, "Independent case replay is incomplete")
    bins = checked.pop("derived_metrics")["operator_bins"]
    require(len(bins) == problem["n"] + 1 and sum(row["total"] for row in bins) == new,
            "Operator counts do not cover all candidates")
    _write_bounded(folder / "verification.json", checked, writer_budget)
    _write_bounded(folder / "operator_bins.json", {"operator_bins": bins, "premutation_score_checks": new},
                   writer_budget)
    mark = time.perf_counter()
    observed = extract(log, TOTAL, certificate["optimum"], checkpoints=CHECKPOINTS)
    observation_seconds = time.perf_counter() - mark
    require(observed["final_best_profit"] == checked["record_profit"], "Observation and replay differ")
    _write_bounded(folder / "observations.json.gz", observed, writer_budget)
    counts.update({key + "_sha256": descriptors[key]["sha256"] for key in
                   ("bank", "certificate", "source", "problem")})
    hashes = {name: sha(folder / name) for name in PAYLOADS}
    timing = {"search_seconds": search_seconds, "log_write_seconds": log_seconds,
              "verification_seconds": replay_seconds, "observations_seconds": observation_seconds}
    receipt = {**case, **origin, **counts, **timing, "schema": SCHEMA, "status": "VERIFIED",
               "artifact_hashes": hashes.copy(), "replay_score_checks": checked["independent_score_checks"]}
    _write_bounded(folder / "record.json", receipt, writer_budget)
    hashes["record.json"] = sha(folder / "record.json")
    timing.update(case_seconds=time.perf_counter() - started, artifact_bytes=_used_bytes(folder))
    row = {**_summary(case, checked, observed, certificate["optimum"]), **counts, **origin,
           "artifact_hashes": hashes, "timing": timing}
    validate_row(row, phase=phase)
    _write_bounded(row_path, row, writer_budget)
    return row


def authenticate_saved(case, descriptors, origin, retained, previous_run, previous_commit, optimum,
                       admitted_producers=()):
    """Validate an already independently replayed case against current inputs before reuse."""
    record_path = retained / "compact" / "records" / (case["case_id"] + ".json")
    folder = retained / "raw" / raw_prefix(case)
    failed = retained / "compact" / "failures" / (case["case_id"] + ".json")
    require(not failed.exists(), "An interrupted case cannot stand in for a successful case")
    require(record_path.is_file() and not record_path.is_symlink() and folder.is_dir() and not folder.is_symlink()
            and record_path.resolve().is_relative_to(retained.resolve())
            and folder.resolve().is_relative_to(retained.resolve()), "Invalid prior result locations")
    paths = list(folder.iterdir())
    require({p.name for p in paths} == CASE_FILES and all(p.is_file() and not p.is_symlink() for p in paths),
            "Prior raw case inventory differs")
    row, receipt = read_json(record_path), read_json(folder / "record.json")
    validate_row(row, phase="validation")
    producers = {previous_run, *(str(run_id) for run_id in admitted_producers)}
    require(row.get("workflow_run_id") == receipt.get("workflow_run_id") and
            row.get("workflow_run_id") in producers, "Unauthenticated prior case producer")
    for obj in (row, receipt):
        require(obj.get("status") == "VERIFIED" and obj.get("schema") == SCHEMA
                and all(obj.get(k) == case[k] for k in
                        ("case_id", "task", "family", "class_label", "task_index",
                         "seed", "mu", "pc_percentage", "mutation_basis_points"))
                and obj.get("workflow_commit") == previous_commit == origin["workflow_commit"]
                and obj.get("source_manifest_sha256") == origin["source_manifest_sha256"]
                and obj.get("authorization_id") == origin["authorization_id"]
                and all(obj.get(k + "_sha256") == descriptors[k]["sha256"]
                        for k in ("bank", "certificate", "source", "problem")),
                "Prior identity, immutable code, grant, or prepared input differs")
    require(row["inputs_manifest_sha256"] == receipt["inputs_manifest_sha256"] == origin["inputs_manifest_sha256"]
            and re.fullmatch("[a-f0-9]{64}", row["inputs_manifest_sha256"]) is not None
            and row["optimum"] == optimum and row["artifact_prefix"] == raw_prefix(case),
            "Incorrect prior prepared manifest, optimum, or case location")
    hashes = {p.name: sha(p) for p in paths}
    require(hashes == row["artifact_hashes"] and {k: hashes[k] for k in PAYLOADS} == receipt["artifact_hashes"],
            "Prior raw journal, receipt or replay checksum differs")
    checked, observed = read_json(folder / "verification.json"), read_json(folder / "observations.json.gz")
    expected = _summary(case, checked, observed, optimum)
    require(checked.get("verification_status") == "VERIFIED" and checked["new_calls"] == TOTAL - case["mu"]
            and checked["record_profit"] == observed["final_best_profit"]
            and checked["final_parameters"] == _expected_parameters(case)
            and all(row[k] == value for k, value in expected.items()),
            "Prior compact data do not match authenticated raw observations")
    return folder, record_path, row


def run_shard(inputs, shard_number, raw, compact, retained=None, retained_run_id=None, retained_commit=None):
    _, auth = guard("main")
    inputs, raw, compact = map(Path, (inputs, raw, compact))
    require(not raw.exists() and not compact.exists() and not raw.resolve().is_relative_to(compact.resolve())
            and not compact.resolve().is_relative_to(raw.resolve()), "Use fresh disjoint evidence roots")
    require(type(shard_number) is int and 0 <= shard_number < 200, "Unregistered shard")
    manifest = read_json(inputs / "manifest.json")
    schedule_path = inputs / "schedule.json"
    schedule_descriptor = manifest["schedule"]
    require(schedule_descriptor["path"] == "schedule.json"
            and schedule_path.stat().st_size == schedule_descriptor["bytes"]
            and sha(schedule_path) == schedule_descriptor["sha256"], "Schedule checksum differs")
    cases = _checked_cases(read_json(schedule_path))[shard_number * SHARD_SIZE:(shard_number + 1) * SHARD_SIZE]
    require(len(cases) == SHARD_SIZE, "Incomplete schedule slice")
    origin = _binding(auth, inputs)
    require((retained is None and retained_run_id is None and retained_commit is None)
            or (retained is not None and isinstance(retained_run_id, str) and retained_run_id.isdecimal()
                and retained_run_id != origin["workflow_run_id"] and retained_commit == origin["workflow_commit"]),
            "Explicit prior run and identical frozen commit required")
    raw.mkdir(parents=True)
    compact.mkdir(parents=True)
    completed, reused, failures = [], [], []
    budget = {"used": 0, "limit": SHARD_BYTES}
    for case in cases:
        case_id = case["case_id"]
        try:
            require(budget["used"] <= SHARD_BYTES - MAX_CASE_BYTES, "Insufficient remaining shard evidence space")
            problem, bank, certificate = load_case(inputs, case)
            descriptors = input_descriptors(manifest, case)
            if retained is not None:
                old = Path(retained)
                prior_row = old / "compact" / "records" / (case_id + ".json")
                failure_path = old / "compact" / "failures" / (case_id + ".json")
                if prior_row.exists() and not failure_path.exists():
                    folder, row_path, _ = authenticate_saved(case, descriptors, origin, old, retained_run_id,
                                                            retained_commit, certificate["optimum"],
                                                            auth["prior_run_ids"])
                    size = _used_bytes(folder) + row_path.stat().st_size
                    require(size <= MAX_CASE_BYTES, "Retained case exceeds its storage bound")
                    shutil.copytree(folder, raw / raw_prefix(case))
                    target = compact / "records" / row_path.name
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(row_path, target)
                    budget["used"] += size
                    reused.append(case_id)
                    continue
            execute_case(case, problem, bank, certificate, descriptors, origin, raw, compact, budget)
            completed.append(case_id)
        except Exception as error:
            failure = {"case_id": case_id, "status": "FAILED_OR_INTERRUPTED",
                       "error_type": type(error).__name__, "message": str(error)[:1000], **origin}
            _write_bounded(compact / "failures" / (case_id + ".json"), failure, budget, emergency=True)
            failures.append(case_id)
    result = {"schema": "independent-validation100-shard-v1",
              "status": "VERIFIED" if not failures else "INCOMPLETE", "shard_id": f"{shard_number:03d}",
              "requested": [c["case_id"] for c in cases], "new": completed, "reused": reused,
              "failures": failures, **origin}
    _write_bounded(compact / "shard.json", result, budget, emergency=True)
    require(_used_bytes(raw, compact) == budget["used"], "Shard storage accounting differs")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("inputs", "raw", "compact"):
        parser.add_argument("--" + name, required=True, type=Path)
    parser.add_argument("--shard", type=int, required=True)
    parser.add_argument("--retained", type=Path)
    parser.add_argument("--retained-run-id")
    parser.add_argument("--retained-commit")
    args = parser.parse_args()
    result = run_shard(args.inputs, args.shard, args.raw, args.compact, args.retained,
                       args.retained_run_id, args.retained_commit)
    print(json.dumps(result))
    return 0 if result["status"] == "VERIFIED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
