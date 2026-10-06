#!/usr/bin/env python3
"""Freeze one training-only sampler and initialization before any main search."""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import sys
from typing import Any

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from chc_qx_alignment_study.contract import (  # noqa: E402
    CASE_SEEDS, PREPARATION_SCHEMA, PROTOCOL_ID, PROTOCOL_SHA256, THIS_DIRECTORY,
    authenticate, canonical_sha256, ensure_empty_output, file_sha256, require, write_json, write_manifest,
)
from chc_qx_alignment_study.data import (  # noqa: E402
    objective_for, prepare_training, select_active_rows, source_density_masks,
)


def prepare_case(*, train: Path, seed: int, expected_sha: str, output: Path,
                 protocol_path: Path = THIS_DIRECTORY / "protocol.json",
                 artifact_name: str | None = None) -> dict[str, Any]:
    ensure_empty_output(output)
    protocol, provenance = authenticate(protocol_path=protocol_path, expected_sha=expected_sha)
    require(type(seed) is int and seed in CASE_SEEDS, "preparation seed outside registered ledger")
    require(file_sha256(train) == protocol["data"]["train_sha256"], "train data hash mismatch")
    write_json(output / "execution-start.json", {
        "schema": "eu26-21-qx-execution-start-v1", "seed": seed, "provenance": provenance,
        "event": "authenticated_training_only_preparation_started",
        "terminal_result_file": "preparation.json", "scientific_result": False,
    })
    prepared = prepare_training(train, seed=seed)
    require(prepared.metadata["train_file_rows"] == protocol["data"]["train_rows"], "train row count mismatch")
    initial_masks = source_density_masks(50, seed=seed + 3000003, nonempty=False)
    sampling = select_active_rows(prepared, seed=seed)
    initial_scores = None
    if sampling["status"] == "PASS_PREPARATION":
        active = objective_for(prepared, sampling["selected_rows"])
        initial_scores = [active(mask) for mask in initial_masks]
    row = {"schema": PREPARATION_SCHEMA, "seed": seed, "status": sampling["status"],
           "protocol_id": PROTOCOL_ID, "protocol_sha256": PROTOCOL_SHA256,
           "provenance": provenance, "training_data": prepared.metadata, "sampling": sampling,
           "initial_masks": [list(mask) for mask in initial_masks], "initial_scores": initial_scores,
           "initial_masks_sha256": canonical_sha256([list(mask) for mask in initial_masks]),
           "initial_scores_sha256": canonical_sha256(initial_scores),
           "initial_mask_seed": seed + 3000003,
           "counts": {"sampler_validation_calls": sampling["sampler_validation_calls"],
                      "sampler_actual_tree_fits": sampling["sampler_validation_calls"],
                      "shared_initial_physical_calls": 50 if initial_scores is not None else 0,
                      "shared_initial_actual_tree_fits": sum(bool(sum(mask)) for mask in initial_masks)
                      if initial_scores is not None else 0, "test_evaluations": 0},
           "frozen_before_search": True, "test_arrays_loaded": False}
    write_json(output / "preparation.json", row)
    name = artifact_name or f"eu26-21-qx-preparation-{seed}-{provenance['run_id']}-{provenance['run_attempt']}"
    write_manifest(output, seed=seed, artifact_name=name, provenance=provenance, row_file="preparation.json")
    return row


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--train", type=Path, required=True)
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--expected-sha", required=True)
    parser.add_argument("--expected-protocol-sha256", default=PROTOCOL_SHA256)
    parser.add_argument("--protocol", type=Path, default=THIS_DIRECTORY / "protocol.json")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--artifact-name")
    args = parser.parse_args()
    require(args.expected_protocol_sha256 == PROTOCOL_SHA256, "unregistered protocol requested")
    # This check is outside the failure handler: an old package is never changed.
    ensure_empty_output(args.output)
    try:
        row = prepare_case(train=args.train, seed=args.seed, expected_sha=args.expected_sha,
                           output=args.output, protocol_path=args.protocol, artifact_name=args.artifact_name)
    except Exception as error:
        write_json(args.output / "failure-status.json", {
            "schema": "eu26-21-qx-status-v1", "seed": args.seed,
            "status": "FAIL_INFRASTRUCTURE_OR_SCHEMA", "error_type": type(error).__name__,
            "error": str(error), "run_id": os.environ.get("GITHUB_RUN_ID"),
        })
        raise
    print(f"seed={row['seed']} {row['status']}")


if __name__ == "__main__":
    main()
