"""Forty real single-feature fits, completed before any new search."""
from __future__ import annotations

import argparse
from pathlib import Path

from chc_qx_alignment_study.data import objective_for, prepare_training
from lambda_response_study.contract import (
    authenticate, ensure_empty_output, file_sha256, require, validate_preparation,
    write_json, write_manifest,
)
from lambda_response_study.oracle import score

def prepare(*, train: Path, seed: int, expected_sha: str, output: Path) -> dict:
    protocol, provenance = authenticate(expected_sha)
    require(type(seed) is int and seed in protocol["rng"]["case_seeds"], "unregistered seed")
    require(file_sha256(train) == protocol["data"]["train_sha256"], "official train hash mismatch")
    ensure_empty_output(output)
    write_json(output / "execution-start.json", {"seed": seed, "provenance": provenance, "phase": "preparation"})
    prepared = prepare_training(train, seed=seed)
    objective = objective_for(prepared)
    rows = []
    for bit in range(40):
        mask = [int(index == bit) for index in range(40)]
        value = score(objective(mask))
        rows.append({"bit_index": bit, "mask": mask, "score": value})
    weakest = min(rows, key=lambda row: (row["score"], row["bit_index"]))
    initial = {**weakest, "feature_name": prepared.feature_names[weakest["bit_index"]]}
    value = {"schema": "eu26-21-lr-preparation-v1", "status": "PASS_PREPARATION",
             "seed": seed, "provenance": provenance, "training_data": prepared.metadata,
             "initial": initial, "evaluations": rows,
             "counts": {"physical_calls": 40, "actual_tree_fits": 40}}
    validate_preparation(value, seed=seed, expected_sha=expected_sha)
    write_json(output / "preparation.json", value)
    write_manifest(output, seed=seed, kind="preparation", provenance=provenance)
    return value

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--train", type=Path, required=True)
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--expected-sha", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        prepare(**vars(args))
    except Exception as error:
        if args.output.is_dir() and not args.output.is_symlink():
            write_json(args.output / "failure-status.json", {"seed": args.seed, "status": "FAIL_INFRASTRUCTURE_OR_SCHEMA",
                                                           "error_type": type(error).__name__, "error": str(error)})
        raise
    print("PASS_PREPARATION")

if __name__ == "__main__":
    main()
