"""CI-only pilot/main controller, isolated from the reference search kernel."""

from __future__ import annotations

import argparse
from copy import deepcopy
from pathlib import Path
import time

import numpy as np

from .banks import create_bank, load_bank, validate_bank
from .contract import (CLASS_CODES, MODULE_ROOT, STUDY_ROOT, canonical_bytes, file_identity,
                       load_context, output_directory, read_json, require, sha256_bytes,
                       write_file_manifest, write_json, write_jsonl_gz)
from .engine import configurations, make_rngs, run_search
from .oracle import verify_search

LIMIT_BYTES = 8 * 1024 ** 3
LIMIT_SECONDS = 120 * 60
PILOT_CASES = ("UC-s000", "WC-s001", "SC-s005")


def validate_main_gates(identity, *, require_pilot):
    banks = read_json(MODULE_ROOT / "frozen_banks.json")
    require(banks["schema_version"] == "ga-knapsack-frozen-banks-v1" and
            banks["protocol_id"] == identity["protocol_id"] and banks["bank_count"] == 900,
            "initial banks must be frozen before any pilot/main search")
    require(banks["implementation_fingerprint"] == identity["implementation_fingerprint"] and
            banks["runtime_lock_sha256"] == identity["runtime_lock_sha256"], "bank preparation used different scientific code/runtime")
    if require_pilot:
        pilot = read_json(MODULE_ROOT / "frozen_pilot.json")
        require(pilot["schema_version"] == "ga-knapsack-frozen-pilot-v1" and
                pilot["protocol_id"] == identity["protocol_id"] and pilot["technical_status"] == "PASS_TECHNICAL",
                "successful frozen technical pilot required")
        require(pilot["implementation_fingerprint"] == identity["implementation_fingerprint"] and
                pilot["runtime_lock_sha256"] == identity["runtime_lock_sha256"] and
                pilot["banks_manifest_sha256"] == banks["banks_manifest_sha256"], "pilot does not certify current implementation/banks/runtime")
        require(pilot["run_count"] == 162 and pilot["projected_job_seconds"] <= LIMIT_SECONDS and
                pilot["projected_job_bytes"] <= LIMIT_BYTES, "pilot exceeds scientific resource limits")
    return banks


def _initial_local(instance, row):
    center = row["payload"]["certificate"]["center"]
    mask = np.fromiter((int(bit) for bit in center["mask"]), dtype=np.uint8, count=instance.n)
    weight = sum(int(bit) * int(value) for bit, value in zip(mask, instance.weights, strict=True))
    profit = sum(int(bit) * int(value) for bit, value in zip(mask, instance.profits, strict=True))
    require(weight == center["weight"] and profit == center["profit"] and weight <= instance.capacity, "frozen center score mismatch")
    return mask, {"weight": weight, "profit": profit, "feasible": True}


def write_run(directory, result, row):
    directory.mkdir(parents=True, exist_ok=False)
    np.savez_compressed(directory / "requests.npz", **result["requests"])
    write_jsonl_gz(directory / "generations.jsonl.gz", result["generations"])
    # Kernel result remains immutable until independent replay has completed.
    write_json(directory / "search_summary.json", result["summary"])
    write_json(directory / "summary.json", row)
    payload_files = [{"path": path.name, **file_identity(path)} for path in sorted(directory.iterdir()) if path.is_file()]
    write_json(directory / "manifest.json", {"schema_version": "ga-knapsack-run-manifest-v1",
              "verified": row["verified"], "identity": {key: row[key] for key in ("instance_id", "start_profile", "repeat_seed", "configuration_id", "implementation_commit_sha")},
              "files": payload_files})


def execute_job(expected_sha, output, *, stage, instance_id, batch=0, banks_bundle=None):
    started = time.monotonic()
    instances, cases, _, identity = load_context(expected_sha)
    frozen = validate_main_gates(identity, require_pilot=stage == "main")
    require(stage in ("main", "pilot"), "unknown search stage")
    selected = [instance for instance in instances if instance.instance_id == instance_id]
    require(len(selected) == 1, "unknown case; substitutions forbidden")
    instance = selected[0]
    row = cases[instance_id]
    admitted = row["status"].startswith("ADMITTED_")
    if stage == "pilot":
        require(instance_id in PILOT_CASES and admitted, "pilot must use the three prespecified admitted cases")
        seeds = [52001]
        job_key = f"{instance_id}-52001-52001"
    else:
        require(batch in (0, 1, 2) and banks_bundle is not None, "invalid main seed batch or missing frozen bank bundle")
        seeds = list(range(51001 + batch * 10, 51011 + batch * 10))
        job_key = f"{instance_id}-{seeds[0]}-{seeds[-1]}"
    output = output_directory(output)
    base = {**identity, "phase": stage, "instance_id": instance_id,
            "class_label": instance.class_label, "family": instance.family,
            "seed_first": seeds[0], "seed_last": seeds[-1], "job_key": job_key,
            "banks_manifest_sha256": frozen["banks_manifest_sha256"],
            "frozen_banks_descriptor_sha256": file_identity(MODULE_ROOT / "frozen_banks.json")["sha256"],
            "source_sha256": file_identity(STUDY_ROOT / "inputs/source" / instance.source_path)["sha256"],
            "source_commit_sha": "c5bea0df8169749caaba5ce7dfcf21437aa1ca5c",
            "source_path": instance.source_path, "capacity": instance.capacity,
            "bit_item_map": list(range(1, instance.n + 1))}
    center_mask, center_score = _initial_local(instance, row) if admitted else (None, None)
    summaries = []
    status = "INCOMPLETE"
    failure = None
    payload_bytes = 0
    try:
        for seed in seeds:
            if stage == "pilot":
                bank, bank_metadata = create_bank(instance, seed)
                validate_bank(instance, bank, bank_metadata, seed)
                directory = output / "pilot_bank"
                directory.mkdir()
                np.savez_compressed(directory / "bank.npz", **bank)
                write_json(directory / "bank.json", bank_metadata)
            else:
                bank, bank_metadata = load_bank(banks_bundle, instance, seed, descriptor=frozen)
            for profile in (["random", "local"] if admitted else ["random"]):
                for config in configurations():
                    require(time.monotonic() - started < LIMIT_SECONDS, "job preparation/search/replay exceeded 120 minutes")
                    rngs = make_rngs(CLASS_CODES[instance.class_label], instance.index, seed)
                    if profile == "random":
                        initial_masks = bank["masks"][:config.population_size].copy()
                        initial_scores = {name: bank[name][:config.population_size].copy() for name in ("weight", "profit", "feasible")}
                        rngs["initialization"].bit_generator.state = deepcopy(bank_metadata["rng_after"])
                        initial_identity = {"bank_seed": seed, "prefix": config.population_size,
                                            "bank_arrays_sha256": sha256_bytes(bank["masks"].tobytes()),
                                            "physical_shared_preparation_evaluations": 50,
                                            "physical_evaluations_in_current_search": 0}
                    else:
                        initial_masks = np.repeat(center_mask[None, :], config.population_size, axis=0)
                        initial_scores = {"weight": np.full(config.population_size, center_score["weight"], dtype=np.int64),
                                          "profit": np.full(config.population_size, center_score["profit"], dtype=np.int64),
                                          "feasible": np.ones(config.population_size, dtype=np.bool_)}
                        initial_identity = {"center_mask": "".join(map(str, center_mask.tolist())), "center_profit": center_score["profit"],
                                            "center_weight": center_score["weight"], "physical_shared_preparation_evaluations": 0,
                                            "physical_evaluations_in_current_search": 0,
                                            "score_source": "frozen independently certified preparation"}
                    result = run_search(instance, config, initial_masks, initial_scores, rngs, budget=5000)
                    verdict = verify_search(instance, config, result,
                                            initial_center_profit=center_score["profit"] if profile == "local" else None,
                                            initial_masks=initial_masks, initial_scores=initial_scores)
                    require(verdict["status"] == "PASS_REPLAY", "independent search replay rejected")
                    run_directory = f"runs/{seed}/{profile}/{config.configuration_id}"
                    summary = {**base, **result["summary"], "start_profile": profile,
                               "repeat_seed": seed, "initial_identity": initial_identity,
                               "run_directory": run_directory, "verified": True, "verification": verdict,
                               "escape_event": verdict["escape_event"], "first_escape_request": verdict["first_escape_request"],
                               "escape_time": verdict["escape_time"], "censored": verdict["censored"],
                               "initial_center_profit": center_score["profit"] if profile == "local" else None}
                    directory = output / run_directory
                    write_run(directory, result, summary)
                    payload_bytes += sum(path.stat().st_size for path in directory.iterdir() if path.is_file())
                    require(payload_bytes <= LIMIT_BYTES, "job output exceeded 8 GiB")
                    summaries.append(summary)
                    write_json(output / "progress.json", {"job_key": job_key, "completed_runs": len(summaries),
                               "elapsed_seconds": time.monotonic() - started, "payload_bytes": payload_bytes})
        expected_count = len(seeds) * 27 * (2 if admitted else 1)
        require(len(summaries) == expected_count, "incomplete scientific job")
        status = "COMPLETE"
    except Exception as error:
        failure = {"type": type(error).__name__, "message": str(error)}
        status = "RESOURCE_NOT_EVALUATED" if "120 minutes" in str(error) or "8 GiB" in str(error) else "INCOMPLETE"
        raise
    finally:
        write_json(output / "summaries.json", summaries)
        elapsed = time.monotonic() - started
        files = [{"path": path.relative_to(output).as_posix(), **file_identity(path)} for path in sorted(output.rglob("*"))
                 if path.is_file() and path.relative_to(output).as_posix() not in ("manifest.json", "file_manifest.json")]
        write_json(output / "manifest.json", {"schema_version": "ga-knapsack-job-v1", **base,
                   "status": status, "verified": status == "COMPLETE", "failure": failure,
                   "run_count": len(summaries), "logical_requests": sum(item["logical_requests"] for item in summaries),
                   "elapsed_seconds": elapsed, "output_bytes": sum(item["bytes"] for item in files),
                   "projected_main_job_seconds": elapsed * (10 if stage == "pilot" else 1),
                   "projected_main_job_bytes": sum(item["bytes"] for item in files) * (10 if stage == "pilot" else 1),
                   "physical_shared_bank_evaluations": 50 * len(seeds) if stage == "pilot" else 0,
                   "referenced_prior_bank_evaluations": 50 * len(seeds) if stage == "main" else 0,
                   "physical_shared_center_evaluations": 0,
                   "files": files})
        write_file_manifest(output)
    return summaries


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--expected-sha", required=True)
    parser.add_argument("--stage", choices=("pilot", "main"), required=True)
    parser.add_argument("--instance")
    parser.add_argument("--class", dest="class_label", choices=tuple(CLASS_CODES))
    parser.add_argument("--index", type=int)
    parser.add_argument("--batch", type=int, default=0)
    parser.add_argument("--banks", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    instance_id = args.instance or f"{args.class_label}-s{args.index:03d}"
    result = execute_job(args.expected_sha, args.output, stage=args.stage, instance_id=instance_id,
                         batch=args.batch, banks_bundle=args.banks)
    print(f"Completed {len(result)} runs with full independent controller/RNG replay")


if __name__ == "__main__":
    main()
