"""Execute registered population-thirteen cases and retain each verified result.

There is no evolution loop in this module. Search calls the immutable public
core through the already tested adapter. Exact optima enter observations only
after independent replay has completed.
"""
from __future__ import annotations

import argparse
import math
import os
from pathlib import Path
import shutil
import time
import traceback

from .common import (
    TOTAL, descriptor, guard_main, registered_cases, registered_shards,
    validate_case_origin,
)
from .preparation import load_case
from studies.knapsack_parameters.iterative_validation_population13.pilot import check_accounting
from studies.knapsack_parameters.iterative_validation_population13.search import make_log
from studies.knapsack_parameters.population_validation_100.common import (
    read_json, require, require_ci, sha,
)
from studies.knapsack_parameters.population_validation_100_main.runner import (
    _used_bytes, _write_bounded,
)


SCHEMA = "population13-main-case-v1"
PAYLOAD_FILES = frozenset(("journal.json.gz", "verification.json", "operator_bins.json",
                           "observations.json.gz"))
CASE_FILES = PAYLOAD_FILES | {"record.json"}
INPUT_FIELDS = ("problem", "certificate", "source", "bank")
PARAMETERS = {"p_m": .01, "p_c": .9, "target_mu": 13,
              "tournament_size": 2, "elite_count": 1}


def _registered_case(case_id):
    rows = registered_cases()
    matches = [row for row in rows if row["case_id"] == case_id]
    require(len(matches) == 1, "An exact registered main-case identity is required")
    return matches[0]


def _match_identity(actual, expected):
    require(type(actual) is dict and all(type(actual.get(key)) is type(value)
            and actual[key] == value for key, value in expected.items()),
            "The registered task, seed or fixed configuration differs")


def _current_inputs(inputs, case_id, authorization):
    case, problem, bank, certificate = load_case(inputs, case_id, authorization)
    _match_identity(case, _registered_case(case_id))
    require(case["mu"] == 13 and case["pc_percentage"] == 90
            and case["mutation_basis_points"] == 100 and case["preparation_seed"] == 150000,
            "Only the registered fixed population-thirteen configuration is admitted")
    paths = {name: descriptor(inputs, case[name]) for name in INPUT_FIELDS}
    require(bank.get("search_seed") == case["seed"]
            and bank.get("task_index") == case["task_index"]
            and bank.get("preparation_seed") == case["preparation_seed"],
            "The retained bank has a different seed or task index")
    return case, problem, bank, certificate, paths


def _check_payload_receipts(record, verification, operators, observations):
    """Check stored replay/accounting receipts without running the producer."""
    mu, new = record["mu"], TOTAL - record["mu"]
    full, partial = divmod(new, mu - 1)
    require(all(type(record.get(name)) is int for name in
                ("initial_evaluations", "new_evaluations", "total_evaluations",
                 "completed_generations", "terminal_partial_children",
                 "known_start_score_validation_checks", "replay_score_checks", "premutation_score_checks"))
            and all(type(verification.get(name)) is int for name in
                    ("new_calls", "initial_score_checks", "final_score_checks", "premutation_score_checks",
                     "independent_score_checks", "completed_generations")),
            "Evaluation and replay counters must be exact integers")
    require(record.get("initial_evaluations") == mu
            and record.get("new_evaluations") == new
            and record.get("total_evaluations") == TOTAL
            and record.get("completed_generations") == full
            and record.get("terminal_partial_children") == partial,
            "Saved total, initial, offspring or terminal-block accounting differs")
    require(verification.get("verification_status") == "VERIFIED"
            and verification.get("new_calls") == new
            and verification.get("initial_score_checks") == mu
            and verification.get("final_score_checks") == new
            and verification.get("premutation_score_checks") == new
            and verification.get("independent_score_checks") == mu + 2 * new
            and verification.get("completed_generations") == full
            and verification.get("summary", {}).get("partial_children") == partial
            and verification.get("final_parameters") == PARAMETERS,
            "Saved independent replay receipt is incomplete or inconsistent")
    require(record.get("known_start_score_validation_checks") == mu
            and record.get("replay_score_checks") == verification["independent_score_checks"]
            and record.get("premutation_score_checks") == new,
            "Saved physical validation counts differ from independent replay")
    bins = operators.get("operator_bins")
    require(operators.get("premutation_score_checks") == new
            and type(bins) is list and len(bins) == 101
            and [row.get("distance") for row in bins] == list(range(101))
            and all(type(row.get("total")) is int and row["total"] >= 0 for row in bins)
            and sum(row["total"] for row in bins) == new,
            "Saved operator observations do not cover every offspring")
    require(observations.get("schema") == "population-crossover-observations-v1"
            and observations.get("total_evaluations") == TOTAL
            and observations.get("initial_evaluations") == mu
            and observations.get("new_evaluations") == new
            and observations.get("completed_generations") == full
            and observations.get("terminal_partial_offspring") == partial
            and observations.get("final_best_profit") == verification.get("record_profit")
            and observations.get("search_evaluations_performed") == 0,
            "Saved postsearch observations differ from independently verified search")


def verify_saved_case(folder, case, inputs_manifest_sha256, authorization):
    """Authenticate completed evidence before it can replace a new case call.

    Prior results must be explicitly admitted by the current authorization. Their
    original prepared-manifest hash is retained; the case's four input hashes
    must still equal the current authenticated input payloads.
    """
    require_ci()
    folder = Path(folder)
    require(folder.is_dir() and not folder.is_symlink(), "A retained case directory is required")
    files = list(folder.iterdir())
    require({path.name for path in files} == CASE_FILES
            and all(path.is_file() and not path.is_symlink()
                    and path.resolve().is_relative_to(folder.resolve()) for path in files),
            "A completed case must contain exactly its five canonical files")
    record = read_json(folder / "record.json")
    _match_identity(record, _registered_case(case["case_id"]))
    require(record.get("schema") == SCHEMA and record.get("status") == "VERIFIED"
            and type(record.get("tournament_size")) is int and record["tournament_size"] == 2
            and type(record.get("elite_count")) is int and record["elite_count"] == 1,
            "An independently verified fixed main-case receipt is required")
    origin = validate_case_origin(record, authorization)
    current = (record.get("workflow_run_id") == os.environ.get("GITHUB_RUN_ID")
               and record.get("workflow_commit") == os.environ.get("GITHUB_SHA"))
    expected_manifest = inputs_manifest_sha256 if current else origin.get("inputs_manifest_sha256")
    require(type(expected_manifest) is str
            and record.get("inputs_manifest_sha256") == expected_manifest,
            "The prepared-manifest identity is not admitted for this saved origin")
    for name in INPUT_FIELDS:
        require(record.get(name + "_sha256") == case[name]["sha256"],
                "Saved case uses a different authenticated input: " + name)
    hashes = record.get("artifact_hashes")
    require(type(hashes) is dict and set(hashes) == PAYLOAD_FILES,
            "Saved canonical payload inventory differs")
    for name in PAYLOAD_FILES:
        require(sha(folder / name) == hashes[name], "Saved case payload hash differs: " + name)
    require(record.get("artifact_bytes_before_receipt")
            == sum((folder / name).stat().st_size for name in PAYLOAD_FILES),
            "Saved payload-byte accounting differs")
    for name in ("input_validation_seconds", "search_seconds", "journal_write_seconds",
                 "verification_seconds", "observations_seconds", "case_seconds_before_receipt"):
        value = record.get(name)
        require(type(value) in (int, float) and math.isfinite(value) and value >= 0,
                "Saved measured duration is invalid: " + name)
    _check_payload_receipts(record, read_json(folder / "verification.json"),
                            read_json(folder / "operator_bins.json"),
                            read_json(folder / "observations.json.gz"))
    return record


def run_case(inputs, case_id, out, authorization_id=None):
    """Search one missing registered identity, then replay and save its receipt."""
    protocol, authorization = guard_main(authorization_id)
    _registered_case(case_id)
    inputs, output = Path(inputs), Path(out)
    require(not output.exists(), "Preserve completed or interrupted case evidence")
    started = time.perf_counter()
    case, problem, bank, certificate, paths = _current_inputs(inputs, case_id, authorization)
    input_seconds = time.perf_counter() - started
    output.mkdir(parents=True, exist_ok=False)
    budget = {"limit": protocol["limits"]["per_case_artifact_bytes"], "used": 0}
    search_started = search_completed = False
    try:
        from studies.knapsack_parameters.crossover_population.verification import verify_log
        from studies.knapsack_parameters.crossover_population.observations import extract

        # Search receives only the problem and original bank, never the optimum.
        mark = time.perf_counter()
        search_started = True
        log = make_log(problem, bank, case["mu"], case["seed"], case["task_index"], TOTAL)
        search_completed = True
        search_seconds = time.perf_counter() - mark
        accounting = check_accounting(log, case["mu"], TOTAL)
        require(log.get("initial_parameters") == PARAMETERS
                and all(event.get("parameters_before") == PARAMETERS
                        and event.get("parameters_after") == PARAMETERS for event in log["generations"]),
                "A main case changed its registered fixed parameters")
        mark = time.perf_counter()
        _write_bounded(output / "journal.json.gz", log, budget)
        journal_seconds = time.perf_counter() - mark

        # Monitoring and independent checks occur after search has finished.
        mark = time.perf_counter()
        verification = verify_log(log)
        verification_seconds = time.perf_counter() - mark
        require(verification.get("verification_status") == "VERIFIED"
                and verification.get("new_calls") == TOTAL - case["mu"], "Independent replay failed")
        bins = verification.pop("derived_metrics")["operator_bins"]
        _write_bounded(output / "verification.json", verification, budget)
        _write_bounded(output / "operator_bins.json", {"operator_bins": bins,
                       "premutation_score_checks": verification["premutation_score_checks"]}, budget)
        mark = time.perf_counter()
        observations = extract(log, TOTAL, certificate["optimum"],
                               checkpoints=tuple(protocol["checkpoints"]))
        observation_seconds = time.perf_counter() - mark
        require(observations["final_best_profit"] == verification["record_profit"],
                "Postsearch observations differ from independent replay")
        _write_bounded(output / "observations.json.gz", observations, budget)
        record = {"schema": SCHEMA, "status": "VERIFIED", **_registered_case(case_id),
                  **accounting, "tournament_size": 2, "elite_count": 1,
                  "known_start_score_validation_checks": case["mu"],
                  "replay_score_checks": verification["independent_score_checks"],
                  "premutation_score_checks": verification["premutation_score_checks"],
                  **{name + "_sha256": sha(path) for name, path in paths.items()},
                  "inputs_manifest_sha256": sha(inputs / "manifest.json"),
                  "source_manifest_sha256": authorization["source_manifest_sha256"],
                  "artifact_hashes": {name: sha(output / name) for name in sorted(PAYLOAD_FILES)},
                  "input_validation_seconds": input_seconds, "search_seconds": search_seconds,
                  "journal_write_seconds": journal_seconds, "verification_seconds": verification_seconds,
                  "observations_seconds": observation_seconds,
                  "case_seconds_before_receipt": time.perf_counter() - started,
                  "artifact_bytes_before_receipt": _used_bytes(output),
                  "workflow_run_id": os.environ["GITHUB_RUN_ID"],
                  "workflow_commit": os.environ["GITHUB_SHA"],
                  "authorization_id": authorization["authorization_id"]}
        _check_payload_receipts(record, verification,
                                {"operator_bins": bins, "premutation_score_checks": verification["premutation_score_checks"]},
                                observations)
        _write_bounded(output / "record.json", record, budget)
        require(_used_bytes(output) == budget["used"] <= budget["limit"], "Case artifact-byte accounting differs")
        return record
    except Exception as error:
        _write_bounded(output / "failure.json", {"status": "FAILED_OR_INTERRUPTED", "case_id": case_id,
                       "error_type": type(error).__name__, "message": str(error)[:1000],
                       "traceback": traceback.format_exc(limit=8),
                       "search_call_started": search_started,
                       "search_call_completed": search_completed,
                       "requested_total_evaluations": TOTAL,
                       "completed_search_evaluations_if_returned": TOTAL if search_completed else None,
                       "elapsed_seconds": time.perf_counter() - started}, budget, emergency=True)
        raise


def _retained_index(root):
    require(root.is_dir() and not root.is_symlink(), "An authenticated retained-result directory is required")
    allowed = {row["case_id"] for row in registered_cases()}
    found = {}
    for path in sorted(root.rglob("record.json")):
        require(path.is_file() and not path.is_symlink() and path.resolve().is_relative_to(root.resolve()),
                "Unsafe retained result receipt")
        record = read_json(path)
        case_id = record.get("case_id")
        require(case_id in allowed and case_id not in found,
                "Unknown or duplicated retained main-case identity")
        failure = path.parent / "failure.json"
        if failure.exists():
            require(failure.is_file() and not failure.is_symlink()
                    and failure.resolve().is_relative_to(root.resolve()), "Unsafe prior failure receipt")
            failed = read_json(failure)
            require(failed.get("status") == "FAILED_OR_INTERRUPTED"
                    and failed.get("case_id") == case_id, "Prior failure identity differs")
            # A late retention failure disqualifies even an earlier VERIFIED receipt.
            # Preserve the old archive and execute the same missing identity afresh.
            continue
        found[case_id] = path.parent
    return found


def _copy_saved_case(source, destination, case, manifest_sha, authorization, byte_cap):
    record = verify_saved_case(source, case, manifest_sha, authorization)
    require(_used_bytes(source) <= byte_cap, "Retained case exceeds the current artifact cap")
    require(not destination.exists(), "Never overwrite partial or completed output")
    destination.mkdir(parents=True, exist_ok=False)
    for name in sorted(CASE_FILES):
        # Copy the original receipt as well; never relabel an old run as new.
        with (source / name).open("rb") as incoming, (destination / name).open("xb") as outgoing:
            shutil.copyfileobj(incoming, outgoing, length=1024 * 1024)
    verify_saved_case(destination, case, manifest_sha, authorization)
    return record


def run_shard(inputs, shard_id, out, authorization_id=None, retained_root=None):
    """Execute three seeds sequentially, preserving failures and verified reuse."""
    protocol, authorization = guard_main(authorization_id)
    rows = [row for row in registered_shards() if row["shard_id"] == shard_id]
    require(len(rows) == 1 and len(rows[0]["case_ids"]) == 3,
            "A registered three-case shard is required")
    inputs, output = Path(inputs), Path(out)
    require(not output.is_symlink(), "Unsafe shard output")
    output.mkdir(parents=True, exist_ok=True)
    require(not (output / "shard_receipt.json").exists(), "Preserve a completed shard receipt")
    require(_used_bytes(output) <= protocol["limits"]["shard_artifact_bytes"],
            "Existing shard output exceeds its artifact bound")
    retained = _retained_index(Path(retained_root)) if retained_root is not None else {}
    started = time.perf_counter()
    completed, reused, failed, deferred = [], [], [], []
    attempted, searches_started, searches_completed = [], [], []
    case_ids = rows[0]["case_ids"]
    for position, case_id in enumerate(case_ids):
        elapsed = time.perf_counter() - started
        if elapsed >= protocol["limits"]["shard_seconds"] - protocol["limits"]["shard_reserve_seconds"]:
            deferred.extend(case_ids[position:])
            break
        try:
            case, _, _, _, _ = _current_inputs(inputs, case_id, authorization)
            manifest_sha = sha(inputs / "manifest.json")
            destination = output / case_id
            require(not (destination.exists() and case_id in retained),
                    "Duplicate case identity across current and retained outputs")
            if destination.exists():
                verify_saved_case(destination, case, manifest_sha, authorization)
                reused.append(case_id)
            elif case_id in retained:
                _copy_saved_case(retained[case_id], destination, case, manifest_sha, authorization,
                                 protocol["limits"]["per_case_artifact_bytes"])
                reused.append(case_id)
            else:
                attempted.append(case_id)
                run_case(inputs, case_id, destination, authorization_id)
                searches_started.append(case_id)
                searches_completed.append(case_id)
                completed.append(case_id)
        except Exception as error:
            search_failure = output / case_id / "failure.json"
            failure_receipt = (read_json(search_failure)
                               if case_id in attempted and search_failure.is_file() else {})
            if case_id in attempted and failure_receipt.get("search_call_started") is True:
                searches_started.append(case_id)
            if case_id in attempted and failure_receipt.get("search_call_completed") is True:
                searches_completed.append(case_id)
            failed.append({"case_id": case_id, "error_type": type(error).__name__, "message": str(error)[:1000],
                           "search_call_started": case_id in searches_started,
                           "search_call_completed": case_id in searches_completed})
            # Input/corrupt-reuse failures may precede creation of a case folder.
            failure_path = output / "shard_failures" / (case_id + ".json")
            budget = {"used": _used_bytes(output), "limit": protocol["limits"]["shard_artifact_bytes"]}
            _write_bounded(failure_path, failed[-1], budget, emergency=True)
    record = {"schema": "population13-main-shard-v1",
              "status": "SHARD_VERIFIED" if not failed and not deferred else "SHARD_INCOMPLETE",
              "shard_id": shard_id, "requested_case_ids": list(case_ids),
              "newly_completed_case_ids": completed, "reused_case_ids": reused,
              "failed_cases": failed, "deferred_case_ids": deferred,
              "attempted_missing_case_ids": attempted,
              "new_search_call_ids_started": searches_started,
              "new_search_call_ids_completed": searches_completed,
              "new_search_runs": len(searches_completed), "retained_verified_runs": len(reused),
              "source_manifest_sha256": authorization["source_manifest_sha256"],
              "workflow_run_id": os.environ["GITHUB_RUN_ID"], "workflow_commit": os.environ["GITHUB_SHA"],
              "authorization_id": authorization["authorization_id"],
              "elapsed_seconds_before_receipt": time.perf_counter() - started}
    budget = {"used": _used_bytes(output), "limit": protocol["limits"]["shard_artifact_bytes"]}
    _write_bounded(output / "shard_receipt.json", record, budget, emergency=True)
    require(_used_bytes(output) == budget["used"] <= budget["limit"], "Shard artifact-byte accounting differs")
    return record


def main():
    import json

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inputs", type=Path, required=True)
    parser.add_argument("--shard-id", required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--authorization-id", required=True)
    parser.add_argument("--retained-root", type=Path)
    args = parser.parse_args()
    result = run_shard(args.inputs, args.shard_id, args.out, args.authorization_id, args.retained_root)
    print(json.dumps({"status": result["status"], "shard_id": result["shard_id"],
                      "new_search_runs": result["new_search_runs"],
                      "retained_verified_runs": result["retained_verified_runs"],
                      "failed_cases": len(result["failed_cases"]),
                      "deferred_cases": len(result["deferred_case_ids"])}))
    return 0 if result["status"] == "SHARD_VERIFIED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
