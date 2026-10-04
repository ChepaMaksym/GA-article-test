#!/usr/bin/env python3
"""Six paired methods with shared initialization, run only in authenticated CI."""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import sys
from typing import Any, Mapping

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np

from common_bridge.model_evidence import evaluate_and_persist
from common_bridge.search import run_harmonized_chc
from hybrid_1.core import source_density_population
from local_optima_study.search import run_lambda_search
from lambda_initial_study.contract import (
    ALL_ARMS, CASE_SCHEMA, LAMBDA_INITIAL_VALUES, PROTOCOL_ID, PROTOCOL_SHA256,
    STATUS_SCHEMA, TRACE_SCHEMA, THIS_DIRECTORY, SharedInitialization,
    add_class_metrics, authenticate, mask_fitness, objective_for, pairing_for,
    prepare_data, require, write_json, write_manifest,
)


def _first_fifty(result: Mapping[str, Any]) -> list[dict[str, Any]]:
    return [{"mask": row["mask"], "fitness": row.get("fitness", [
        row.get("validation_weighted_balanced_accuracy"),
        row.get("negative_selected_feature_fraction"),
    ])} for row in result["evaluations"][:50]]


def _chc_dict(result: Any) -> dict[str, Any]:
    return {
        "schema": TRACE_SCHEMA, "arm": "chc_harmonized", "lambda_initial": None,
        "objective_calls": result.objective_calls,
        "initial_population_calls": result.initial_population_calls,
        "terminal": result.terminal_payload(),
        "normalized_auc_best_so_far_validation_wba_1_400": result.normalized_auc_best_so_far_validation_wba_1_400,
        "normalized_auc_best_so_far_validation_wba_51_400": result.normalized_auc_best_so_far_validation_wba_51_400,
        "terminal_state": dict(result.terminal_state), "termination_phase": result.termination_phase,
        "reset": result.reset, "reset_events": result.reset_events,
        "evaluations": [record.to_dict() for record in result.evaluations],
        "generation_trace": [dict(record) for record in result.generation_trace],
    }


def run_case(*, protocol_path: Path, upstream: Path, official_train: Path,
             official_test: Path, seed: int, expected_sha: str,
             expected_protocol_sha256: str, output_dir: Path,
             artifact_name: str) -> dict[str, Any]:
    protocol, provenance = authenticate(
        protocol_path=protocol_path, expected_sha=expected_sha,
        expected_protocol_sha256=expected_protocol_sha256, upstream=upstream,
    )
    require(not output_dir.is_symlink(), "output directory may not be a symlink")
    require(not output_dir.exists() or (output_dir.is_dir() and not any(output_dir.iterdir())),
            "output artifact directory is not empty")
    prepared = prepare_data(protocol, official_train, official_test, seed)
    objective = objective_for(prepared)
    initial_masks = tuple(source_density_population(50, 40, np.random.default_rng(seed + 1000102)))
    shared = SharedInitialization(objective, initial_masks)
    results, ledgers = {}, {}
    replay = shared.replay(objective)
    results["chc_harmonized"] = _chc_dict(run_harmonized_chc(
        replay, initial_masks, seed=seed + 1000003, budget=400,
        initial_distance=10, cataclysmic_mutation_probability=1 / 3,
    ))
    ledgers["chc_harmonized"] = replay.complete()
    for value in LAMBDA_INITIAL_VALUES:
        arm = f"lambda_initial_{value}"
        replay = shared.replay(objective)
        result = run_lambda_search(
            replay, seed=seed + 1000003, mode="adaptive", budget=400,
            initial_masks=initial_masks, lambda_initial=value, update_factor=1.5,
        )
        result.update({"schema": TRACE_SCHEMA, "arm": arm, "lambda_initial": value})
        results[arm], ledgers[arm] = result, replay.complete()
    first = list(shared.records)
    for arm in ALL_ARMS:
        require(results[arm]["objective_calls"] == 400
                and results[arm]["initial_population_calls"] == 50,
                "logical search-call count mismatch")
        require(_first_fifty(results[arm]) == first, "shared ordered initialization differs between arms")
        require(results[arm]["reset"] is False and results[arm]["reset_events"] == 0,
                "reset occurred")
        results[arm]["evaluation_ledger"] = ledgers[arm]
    pairing = pairing_for(prepared, initial_masks, first, seed)
    output_dir.mkdir(parents=True, exist_ok=True)
    traces = {}
    for arm in ALL_ARMS:
        name = f"trace-{arm}.json"
        traces[arm] = {"file": name, **write_json(output_dir / name, {
            **results[arm], "seed": seed, "pairing": pairing,
            "protocol_id": PROTOCOL_ID, "implementation_sha": expected_sha,
        })}
    terminals = {arm: results[arm]["terminal"] for arm in ALL_ARMS}
    for terminal in terminals.values():
        mask_fitness(terminal["mask"], terminal["fitness"])
    freeze = {
        "schema": "eu26-21-lambda-initial-terminal-mask-freeze-v1", "seed": seed,
        "provenance": provenance, "pairing": pairing, "arms": terminals,
        "selected_by": "validation_only", "test_evaluations_so_far": 0,
        "lambda_initial_values": list(LAMBDA_INITIAL_VALUES),
    }
    freeze_identity = {"file": "terminal-masks.json",
                       **write_json(output_dir / "terminal-masks.json", freeze)}
    # The immutable six-arm freeze and all validation traces exist before any
    # full-training fit or official holdout prediction is requested.
    models, arm_rows = {}, {}
    for arm in ALL_ARMS:
        metrics, model = evaluate_and_persist(
            prepared, terminals[arm]["mask"], path=output_dir / f"model-{arm}.joblib",
            seed=seed, arm=arm, provenance=provenance,
        )
        models[arm] = model
        arm_rows[arm] = {key: value for key, value in results[arm].items()
                         if key not in ("evaluations", "generation_trace")}
        arm_rows[arm].update({"test_metrics": add_class_metrics(metrics),
                              "test_evaluations": 1, "trace": traces[arm]})
    counts = {
        "shared_initial_validation_calls": 50,
        "postinitial_validation_calls": sum(row["post_initial_physical_calls"] for row in ledgers.values()),
        "logical_validation_calls": sum(row["logical_calls"] for row in ledgers.values()),
        "physical_validation_calls": shared.physical_validation_calls
        + sum(row["post_initial_physical_calls"] for row in ledgers.values()),
        "test_evaluations": len(ALL_ARMS),
    }
    require(counts == {"shared_initial_validation_calls": 50, "postinitial_validation_calls": 2100,
                       "logical_validation_calls": 2400, "physical_validation_calls": 2150,
                       "test_evaluations": 6}, "case accounting differs from registered limits")
    row = {
        "schema": CASE_SCHEMA, "seed": seed, "provenance": provenance,
        "artifact_name": artifact_name, "pairing": pairing,
        "feature_names": list(prepared.feature_names),
        "initial_masks": [list(mask) for mask in initial_masks], "initial_evaluations": first,
        "shared_initialization": {
            "physical_validation_calls": shared.physical_validation_calls,
            "actual_tree_fits": shared.actual_tree_fits,
            "unique_masks": shared.unique_mask_count, "duplicate_queries": 50 - shared.unique_mask_count,
            "deduplication": False, "replay_is_position_checked": True,
        },
        "actual_validation_tree_fits": shared.actual_tree_fits
        + sum(item["post_initial_actual_tree_fits"] for item in ledgers.values()),
        "arms": arm_rows, "models": models, "terminal_masks_freeze": freeze_identity,
        "counts": counts,
    }
    write_json(output_dir / "case.json", row)
    write_json(output_dir / "status.json", {
        "schema": STATUS_SCHEMA, "seed": seed, "status": "PASS_INFRASTRUCTURE_AND_SCHEMA",
        "scientific_status": "PENDING_ALL_30_CASE_AGGREGATION",
        "run_id": provenance["run_id"], "run_attempt": provenance["run_attempt"],
    })
    write_manifest(output_dir, seed=seed, artifact_name=artifact_name, provenance=provenance)
    return row


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--protocol", type=Path, default=THIS_DIRECTORY / "protocol.json")
    parser.add_argument("--upstream", type=Path, required=True)
    parser.add_argument("--train", "--official-train", dest="official_train", type=Path, required=True)
    parser.add_argument("--test", "--official-test", dest="official_test", type=Path, required=True)
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--expected-sha", required=True)
    parser.add_argument("--expected-protocol-sha256", default=PROTOCOL_SHA256)
    parser.add_argument("--output", "--output-dir", dest="output_dir", type=Path, required=True)
    parser.add_argument("--artifact-name")
    args = parser.parse_args()
    artifact_name = args.artifact_name or (
        f"eu26-21-lambda-case-{args.seed}-{os.environ.get('GITHUB_RUN_ID', '')}"
        f"-{os.environ.get('GITHUB_RUN_ATTEMPT', '')}"
    )
    try:
        row = run_case(
            protocol_path=args.protocol, upstream=args.upstream,
            official_train=args.official_train, official_test=args.official_test,
            seed=args.seed, expected_sha=args.expected_sha,
            expected_protocol_sha256=args.expected_protocol_sha256,
            output_dir=args.output_dir, artifact_name=artifact_name,
        )
    except Exception as error:
        # Never replace prior successful evidence or follow a symlink on failure.
        if not args.output_dir.exists():
            args.output_dir.mkdir(parents=True)
        if args.output_dir.is_dir() and not args.output_dir.is_symlink() and not any(args.output_dir.iterdir()):
            write_json(args.output_dir / "failure-status.json", {
                "schema": STATUS_SCHEMA, "seed": args.seed,
                "status": "FAIL_INFRASTRUCTURE_OR_SCHEMA", "error_type": type(error).__name__,
                "error": str(error),
            })
        raise
    print(f"seed={row['seed']} PASS_INFRASTRUCTURE_AND_SCHEMA")


if __name__ == "__main__":
    main()
