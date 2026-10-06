#!/usr/bin/env python3
"""Run one escape pair from the authenticated frozen registry, in CI only."""
from __future__ import annotations

import argparse
from pathlib import Path
import sys
from typing import Any

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from local_optima_study.contract import (
    ESCAPE_ARMS, ESCAPE_SCHEMA, REGISTRY_SCHEMA, authenticate,
    canonical_sha256, file_sha256, objective_for, pairing_for, prepare_data,
    read_json, require, verify_manifest, write_json, write_manifest,
)
from local_optima_study.search import run_lambda_search


def locate_frozen_case(cases_dir: Path, registry: dict[str, Any], seed: int,
                       expected_sha: str) -> tuple[dict[str, Any], dict[str, Any]]:
    entries = [entry for entry in registry["cases"] if entry["seed"] == seed]
    require(len(entries) == 1 and entries[0]["eligible"] is True, "case not uniquely eligible in registry")
    entry = entries[0]
    matches = []
    for path in cases_dir.rglob("manifest.json"):
        candidate = read_json(path)
        if candidate.get("seed") == seed and candidate.get("repeat") is None:
            matches.append(path)
    require(len(matches) == 1, "missing or duplicate source case manifest")
    path = matches[0]
    require(file_sha256(path) == entry["manifest_sha256"], "source manifest differs from frozen registry")
    manifest = verify_manifest(path, expected_sha=expected_sha)
    require(manifest["artifact_name"] == entry["source_artifact_name"], "source artifact name mismatch")
    case_path = path.parent / manifest["row_file"]
    require(file_sha256(case_path) == entry["row_sha256"], "source row differs from frozen registry")
    case = read_json(case_path)
    preparation_path = path.parent / case["preparation"]["file"]
    require(file_sha256(preparation_path) == entry["preparation_sha256"], "prepared case digest mismatch")
    preparation = read_json(preparation_path)
    require(preparation["eligible"] is True, "frozen preparation is ineligible")
    require(canonical_sha256({"mask": preparation["center_mask"], "fitness": preparation["center_fitness"]})
            == entry["center_sha256"], "frozen center changed")
    return case, preparation


def run_escape(*, protocol_path: Path, registry_path: Path, registry_sha256: str,
               cases_dir: Path, official_train: Path, official_test: Path,
               seed: int, repeat: int, expected_sha: str,
               expected_protocol_sha256: str, output_dir: Path,
               artifact_name: str) -> dict[str, Any]:
    protocol, provenance = authenticate(protocol_path=protocol_path, expected_sha=expected_sha,
                                        expected_protocol_sha256=expected_protocol_sha256)
    require(file_sha256(registry_path) == registry_sha256, "frozen registry digest mismatch")
    registry = read_json(registry_path)
    require(registry["schema"] == REGISTRY_SCHEMA, "registry schema mismatch")
    require(registry["implementation_sha"] == expected_sha, "registry implementation SHA mismatch")
    require(registry["protocol_sha256"] == expected_protocol_sha256, "registry protocol hash mismatch")
    require(registry["all_case_records_frozen"] == 30 and len(registry["cases"]) == 30
            and [entry["seed"] for entry in registry["cases"]] == protocol["rng"]["case_seeds"],
            "registry does not freeze all 30 ordered cases")
    require(registry["escape_outcomes_inspected"] is False, "registry was not frozen before escape inspection")
    require(repeat in protocol["rng"]["escape_repeats"] and type(repeat) is int, "repeat outside frozen ledger")
    case, preparation = locate_frozen_case(cases_dir, registry, seed, expected_sha)
    require(provenance["environment_sha256"] == case["provenance"]["environment_sha256"],
            "escape runtime differs from prepared-case runtime")
    prepared = prepare_data(protocol, official_train, official_test, seed)
    pairing = pairing_for(prepared, case["initial_masks"], case["initial_evaluations"], seed)
    require(pairing == case["pairing"], "reconstructed split/evaluator identity differs from frozen case")
    objective = objective_for(prepared)
    search_seed = 10000000 + 100 * (seed - 42001) + repeat
    results: dict[str, Any] = {}
    # Only the certified center and its known fitness enter the kernel. The
    # two-bit witness and its mask are never passed as search information.
    for arm, mode in (("lambda_adaptive", "adaptive"), ("lambda_fixed1", "fixed1")):
        results[arm] = run_lambda_search(
            objective, seed=search_seed, mode=mode, budget=400,
            initial_parent=preparation["center_mask"], initial_fitness=preparation["center_fitness"],
        )
        require(results[arm]["objective_calls"] == 400, "escape call count differs from 400")
        require(results[arm]["initial_population_calls"] == 0, "escape performed a warmup population")
        require(results[arm]["initial"]["call"] == 0, "known parent not retained at q0")
        require(results[arm]["reset"] is False and results[arm]["reset_events"] == 0, "reset occurred")
    output_dir.mkdir(parents=True, exist_ok=True)
    require(not any(output_dir.iterdir()), "output artifact directory is not empty")
    traces = {}
    for arm in ESCAPE_ARMS:
        name = f"trace-{arm}.json"
        traces[arm] = {"file": name, **write_json(output_dir / name, results[arm])}
    row = {"schema": ESCAPE_SCHEMA, "seed": seed, "repeat": repeat,
           "search_seed": search_seed, "artifact_name": artifact_name, "provenance": provenance,
           "source_registry_sha256": registry_sha256, "source_run_id": registry["source_run_id"],
           "source_case": next(entry for entry in registry["cases"] if entry["seed"] == seed),
           "pairing": pairing, "test_evaluations": 0,
           "arms": {arm: {key: value for key, value in results[arm].items()
                           if key not in ("evaluations", "generation_trace")}
                    for arm in ESCAPE_ARMS}}
    for arm in ESCAPE_ARMS:
        row["arms"][arm]["trace"] = traces[arm]
    write_json(output_dir / "escape.json", row)
    write_json(output_dir / "status.json", {"schema": "eu26-21-local-optima-status-v1",
               "seed": seed, "repeat": repeat, "status": "PASS_INFRASTRUCTURE_AND_SCHEMA",
               "scientific_status": "OBSERVED_EXIT_OR_RETAINED_NONEXIT",
               "run_id": provenance["run_id"], "run_attempt": provenance["run_attempt"]})
    write_manifest(output_dir, seed=seed, repeat=repeat, artifact_name=artifact_name,
                   provenance=provenance, row_file="escape.json")
    return row


def main() -> None:
    parser = argparse.ArgumentParser()
    for name in ("protocol", "registry", "cases-dir", "official-train", "official-test", "output-dir"):
        parser.add_argument(f"--{name}", type=Path, required=True)
    for name in ("registry-sha256", "expected-sha", "expected-protocol-sha256", "artifact-name"):
        parser.add_argument(f"--{name}", required=True)
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--repeat", type=int, required=True)
    args = parser.parse_args()
    try:
        row = run_escape(protocol_path=args.protocol, registry_path=args.registry,
                         registry_sha256=args.registry_sha256, cases_dir=args.cases_dir,
                         official_train=args.official_train, official_test=args.official_test,
                         seed=args.seed, repeat=args.repeat, expected_sha=args.expected_sha,
                         expected_protocol_sha256=args.expected_protocol_sha256,
                         output_dir=args.output_dir, artifact_name=args.artifact_name)
    except Exception as error:
        args.output_dir.mkdir(parents=True, exist_ok=True)
        write_json(args.output_dir / "failure-status.json", {
            "schema": "eu26-21-local-optima-status-v1", "seed": args.seed, "repeat": args.repeat,
            "status": "FAIL_INFRASTRUCTURE_OR_SCHEMA", "error_type": type(error).__name__, "error": str(error),
        })
        raise
    print(f"seed={row['seed']} repeat={row['repeat']} PASS_INFRASTRUCTURE_AND_SCHEMA")


if __name__ == "__main__":
    main()
