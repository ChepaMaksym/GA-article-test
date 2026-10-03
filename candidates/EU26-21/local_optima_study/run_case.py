#!/usr/bin/env python3
"""Run four comparison methods and prepare one certified case, in CI only."""
from __future__ import annotations

import argparse
from pathlib import Path
import sys
from typing import Any, Mapping

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np

from common_bridge.model_evidence import evaluate_and_persist
from common_bridge.search import run_harmonized_chc
from hybrid_1.core import source_density_population
from local_optima_study.certification import prepare_case
from local_optima_study.contract import (
    ALL_ARMS, CASE_SCHEMA, SEARCH_ARMS, add_class_metrics, authenticate,
    canonical_sha256, mask_fitness, objective_for, pairing_for, prepare_data,
    require, write_json, write_manifest,
)
from local_optima_study.search import run_lambda_search


def _first_fifty(result: Mapping[str, Any]) -> list[dict[str, Any]]:
    return [{"mask": row["mask"], "fitness": row.get("fitness", [
        row.get("validation_weighted_balanced_accuracy"),
        row.get("negative_selected_feature_fraction"),
    ])} for row in result["evaluations"][:50]]


def _chc_dict(result: Any) -> dict[str, Any]:
    return {
        "schema": "eu26-21-local-optima-search-v1", "arm": "chc_harmonized",
        "objective_calls": result.objective_calls,
        "initial_population_calls": result.initial_population_calls,
        "terminal": result.terminal_payload(),
        "normalized_auc_best_so_far_validation_wba_1_400": result.normalized_auc_best_so_far_validation_wba_1_400,
        "normalized_auc_best_so_far_validation_wba_51_400": result.normalized_auc_best_so_far_validation_wba_51_400,
        "terminal_state": dict(result.terminal_state),
        "termination_phase": result.termination_phase,
        "reset": result.reset, "reset_events": result.reset_events,
        "evaluations": [record.to_dict() for record in result.evaluations],
        "generation_trace": [dict(record) for record in result.generation_trace],
    }


def _terminal_static(mask: list[int], fitness: tuple[float, float]) -> dict[str, Any]:
    return {"call": 1, "mask": mask, "fitness": list(fitness),
            "validation_weighted_balanced_accuracy": fitness[0],
            "negative_selected_feature_fraction": fitness[1],
            "selected_feature_count": sum(mask)}


def run_case(*, protocol_path: Path, upstream: Path, official_train: Path,
             official_test: Path, seed: int, expected_sha: str,
             expected_protocol_sha256: str, output_dir: Path,
             artifact_name: str) -> dict[str, Any]:
    protocol, provenance = authenticate(protocol_path=protocol_path, expected_sha=expected_sha,
                                        expected_protocol_sha256=expected_protocol_sha256, upstream=upstream)
    prepared = prepare_data(protocol, official_train, official_test, seed)
    objective = objective_for(prepared)
    initial_masks = tuple(source_density_population(50, 40, np.random.default_rng(seed + 1000102)))
    results = {"chc_harmonized": _chc_dict(run_harmonized_chc(
        objective, initial_masks, seed=seed + 1000003, budget=400,
        initial_distance=10, cataclysmic_mutation_probability=1 / 3,
    ))}
    for arm, mode in (("lambda_adaptive", "adaptive"), ("lambda_fixed1", "fixed1")):
        results[arm] = run_lambda_search(objective, seed=seed + 1000003,
                                        mode=mode, budget=400, initial_masks=initial_masks)
    first = _first_fifty(results["chc_harmonized"])
    for arm in SEARCH_ARMS:
        require(results[arm]["objective_calls"] == 400, f"{arm} did not consume 400 calls")
        require(results[arm]["initial_population_calls"] == 50, "initial call count mismatch")
        require(_first_fifty(results[arm]) == first, "initial ordered evaluations differ between arms")
        require(results[arm]["reset"] is False and results[arm]["reset_events"] == 0, "reset occurred")
    pairing = pairing_for(prepared, initial_masks, first, seed)

    full_mask = [1] * 40
    full_fitness = tuple(objective(tuple(full_mask)))
    ablations: dict[str, Any] = {}
    for config in protocol["comparison"]["feature_ablations"]:
        mask = [int(name not in config["remove"]) for name in prepared.feature_names]
        require(set(config["remove"]) <= set(prepared.feature_names), "unknown ablation feature")
        fitness = tuple(objective(tuple(mask)))
        mask_fitness(mask, fitness)
        ablations[config["arm"]] = {"mask": mask, "removed_feature_names": config["remove"],
                                     "fitness": list(fitness), "objective_calls": 1,
                                     "test_evaluations": 0}
    results["full40"] = {"arm": "full40", "objective_calls": 1,
                          "initial_population_calls": 0, "reset": False, "reset_events": 0,
                          "terminal": _terminal_static(full_mask, full_fitness),
                          "normalized_auc_best_so_far_validation_wba_1_400": None,
                          "normalized_auc_best_so_far_validation_wba_51_400": None}
    preparation = prepare_case(objective, results["chc_harmonized"]["terminal"]["mask"],
                                results["chc_harmonized"]["terminal"]["fitness"], max_passes=20)
    require(preparation["diagnostic_calls"] <= 1622, "preparation exceeds registered call cap")

    output_dir.mkdir(parents=True, exist_ok=True)
    require(not any(output_dir.iterdir()), "output artifact directory is not empty")
    traces: dict[str, Any] = {}
    for arm in SEARCH_ARMS:
        name = f"trace-{arm}.json"
        traces[arm] = {"file": name, **write_json(output_dir / name, {
            **results[arm], "seed": seed, "pairing": pairing,
            "protocol_id": protocol["protocol_id"], "implementation_sha": expected_sha,
        })}
    preparation_identity = {"file": "preparation.json", **write_json(output_dir / "preparation.json", preparation)}
    terminal_masks = {arm: results[arm]["terminal"] for arm in ALL_ARMS}
    # All four masks and validation/preparation results are persisted BEFORE
    # the first terminal fit or official-test metric is requested.
    freeze = {"schema": "eu26-21-local-optima-terminal-mask-freeze-v1", "seed": seed,
              "provenance": provenance, "pairing": pairing, "arms": terminal_masks,
              "selected_by": "validation_only", "test_evaluations_so_far": 0}
    freeze_identity = {"file": "terminal-masks.json", **write_json(output_dir / "terminal-masks.json", freeze)}
    models: dict[str, Any] = {}
    arm_rows: dict[str, Any] = {}
    for arm in ALL_ARMS:
        terminal = terminal_masks[arm]
        mask_fitness(terminal["mask"], terminal["fitness"])
        metrics, model = evaluate_and_persist(
            prepared, terminal["mask"], path=output_dir / f"model-{arm}.joblib",
            seed=seed, arm=arm, provenance=provenance,
        )
        models[arm] = model
        arm_rows[arm] = {key: value for key, value in results[arm].items()
                         if key not in ("evaluations", "generation_trace")}
        arm_rows[arm].update({"test_metrics": add_class_metrics(metrics), "test_evaluations": 1})
        if arm in traces:
            arm_rows[arm]["trace"] = traces[arm]
    row = {"schema": CASE_SCHEMA, "seed": seed, "provenance": provenance,
           "artifact_name": artifact_name, "pairing": pairing,
           "feature_names": list(prepared.feature_names),
           "initial_masks": [list(mask) for mask in initial_masks], "initial_evaluations": first,
           "arms": arm_rows, "ablations": ablations, "models": models,
           "terminal_masks_freeze": freeze_identity,
           "preparation": {**preparation_identity, "eligible": preparation["eligible"],
                           "status": preparation["status"], "diagnostic_calls": preparation["diagnostic_calls"],
                           "center_sha256": canonical_sha256({"mask": preparation["center_mask"],
                                                               "fitness": preparation["center_fitness"]})},
           "counts": {"comparison_search_calls": 1200, "static_validation_calls": 3,
                      "diagnostic_calls": preparation["diagnostic_calls"], "test_evaluations": 4}}
    write_json(output_dir / "case.json", row)
    write_json(output_dir / "status.json", {"schema": "eu26-21-local-optima-status-v1",
               "seed": seed, "status": "PASS_INFRASTRUCTURE_AND_SCHEMA", "scientific_status": preparation["status"],
               "run_id": provenance["run_id"], "run_attempt": provenance["run_attempt"]})
    write_manifest(output_dir, seed=seed, artifact_name=artifact_name, provenance=provenance, row_file="case.json")
    return row


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--protocol", type=Path, required=True)
    parser.add_argument("--upstream", type=Path, required=True)
    parser.add_argument("--official-train", type=Path, required=True)
    parser.add_argument("--official-test", type=Path, required=True)
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--expected-sha", required=True)
    parser.add_argument("--expected-protocol-sha256", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--artifact-name", required=True)
    args = parser.parse_args()
    try:
        row = run_case(protocol_path=args.protocol, upstream=args.upstream,
                       official_train=args.official_train, official_test=args.official_test,
                       seed=args.seed, expected_sha=args.expected_sha,
                       expected_protocol_sha256=args.expected_protocol_sha256,
                       output_dir=args.output_dir, artifact_name=args.artifact_name)
    except Exception as error:
        args.output_dir.mkdir(parents=True, exist_ok=True)
        write_json(args.output_dir / "failure-status.json", {
            "schema": "eu26-21-local-optima-status-v1", "seed": args.seed,
            "status": "FAIL_INFRASTRUCTURE_OR_SCHEMA", "error_type": type(error).__name__, "error": str(error),
        })
        raise
    print(f"seed={row['seed']} PASS_INFRASTRUCTURE_AND_SCHEMA")


if __name__ == "__main__":
    main()
