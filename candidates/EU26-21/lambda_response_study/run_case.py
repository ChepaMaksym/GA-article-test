"""Two independent problem pairs, frozen real parents, then one-time test."""
from __future__ import annotations

import argparse
from pathlib import Path

from common_bridge.model_evidence import evaluate_and_persist
from chc_qx_alignment_study.data import load_terminal_holdout, objective_for, prepare_training
from chc_qx_alignment_study.run_case import normalize_terminal_metrics
from lambda_response_study.contract import (
    ARMS, CASE_SEEDS, PROBLEMS, authenticate, ensure_empty_output, file_sha256,
    load_preparation, require, write_json, write_manifest,
)
from lambda_response_study.search import run_search

def run_case(*, train: Path, test: Path, seed: int, expected_sha: str,
             preparation: Path, registry: Path, output: Path) -> dict:
    protocol, provenance = authenticate(expected_sha)
    require(type(seed) is int and seed in CASE_SEEDS, "unregistered seed")
    frozen, source = load_preparation(preparation, registry, seed=seed, expected_sha=expected_sha)
    require(file_sha256(train) == protocol["data"]["train_sha256"], "official train hash mismatch")
    ensure_empty_output(output)
    write_json(output / "execution-start.json", {"seed": seed, "provenance": provenance,
               "preparation": source, "test_evaluations": 0})
    prepared = prepare_training(train, seed=seed)
    require(prepared.metadata == frozen["training_data"], "reconstructed split/preprocessor identity changed")
    real_objective = objective_for(prepared)
    problems, traces = {}, {}
    for problem in PROBLEMS:
        initial = [0] * 40 if problem == "onemax" else frozen["initial"]["mask"]
        value = 0.0 if problem == "onemax" else frozen["initial"]["score"]
        objective = (lambda mask: sum(mask) / 40) if problem == "onemax" else real_objective
        search_seed = seed + (1000003 if problem == "onemax" else 2000003)
        arms, identities = {}, {}
        for arm in ARMS:
            def progress(event, current_problem=problem, current_arm=arm):
                pending = output / f"progress-{current_problem}-{current_arm}.pending.json"
                write_json(pending, {**event, "provenance": provenance, "complete_case": False})
                pending.replace(output / f"progress-{current_problem}-{current_arm}.json")
            trace = run_search(objective, problem=problem, arm=arm, initial_mask=initial,
                               initial_score=value, search_seed=search_seed,
                               on_generation_completed=progress)
            name = f"trace-{problem}-{arm}.json"
            identities[arm] = {"file": name, **write_json(output / name, trace)}
            arms[arm] = trace
        # Same randomness and operators before the first update: exact paired first-generation proof.
        first = [arms[arm]["generation_trace"][0] for arm in ARMS]
        for field in ("parent_before", "parent_score_before", "candidate_mask", "candidate_score",
                      "parent_after", "parent_score_after", "mutation_strength", "selected_mutant_index",
                      "RNG_state_before", "RNG_state_after"):
            require(first[0][field] == first[1][field], "paired first generation differs: " + field)
        require(arms["adaptive"]["evaluations"][:20] == arms["fixed10"]["evaluations"][:20],
                "first generation raw candidates differ")
        problems[problem] = {"arms": arms}
        traces[problem] = identities
    final = {arm: problems["census"]["arms"][arm]["final"] for arm in ARMS}
    require(all(sum(row["mask"]) > 0 for row in final.values()), "accepted final real parent cannot be empty")
    freeze = {"schema": "eu26-21-lr-terminal-freeze-v1", "seed": seed, "provenance": provenance,
              "preparation": source, "parents": final, "selected_by": "accepted_parent_after_generation_20",
              "test_evaluations_so_far": 0}
    identity = {"file": "terminal-masks.json", **write_json(output / "terminal-masks.json", freeze)}
    # Only now can any official test array be loaded. Search had training-only objects.
    terminal = load_terminal_holdout(prepared, test, expected_test_sha256=protocol["data"]["test_sha256"])
    models, metrics = {}, {}
    for arm in ARMS:
        result, model = evaluate_and_persist(terminal, final[arm]["mask"],
            path=output / f"model-{arm}.joblib", seed=seed, arm=arm, provenance=provenance)
        metrics[arm] = normalize_terminal_metrics(result)
        models[arm] = model
    value = {"schema": "eu26-21-lr-case-v1", "status": "PASS_CASE", "seed": seed,
             "provenance": provenance, "preparation": source, "training_data": prepared.metadata,
             "initial": frozen["initial"], "problems": problems, "traces": traces,
             "final_masks_freeze": identity, "models": models, "test_metrics": metrics,
             "test_evaluations": {arm: 1 for arm in ARMS},
             "counts": {"preparation_calls": 40,
                        "search_calls": sum(trace["counts"]["physical_calls"]
                            for problem in problems.values() for trace in problem["arms"].values()),
                        "search_tree_fits": sum(trace["counts"]["actual_tree_fits"]
                            for trace in problems["census"]["arms"].values()), "test_evaluations": 2}}
    write_json(output / "case.json", value)
    write_json(output / "status.json", {"seed": seed, "status": "PASS_CASE", "provenance": provenance,
                                      "scientific_status": "PENDING_ALL_30_AGGREGATION"})
    write_manifest(output, seed=seed, kind="case", provenance=provenance)
    return value

def main():
    parser = argparse.ArgumentParser()
    for field in ("train", "test", "preparation", "registry", "output"):
        parser.add_argument("--" + field, type=Path, required=True)
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--expected-sha", required=True)
    args = parser.parse_args()
    try:
        run_case(**vars(args))
    except Exception as error:
        if args.output.is_dir() and not args.output.is_symlink():
            write_json(args.output / "failure-status.json", {"seed": args.seed, "status": "FAIL_INFRASTRUCTURE_OR_SCHEMA",
                                                           "error_type": type(error).__name__, "error": str(error)})
        raise
    print("PASS_CASE")

if __name__ == "__main__":
    main()
