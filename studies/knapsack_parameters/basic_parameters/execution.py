"""CI task runner: unchanged search, independent replay, and complete journals."""
from __future__ import annotations

import gzip
from pathlib import Path
import time

import numpy as np

from ..ga_study.contract import REGISTRY_SHA
from .banks import load_bank
from .contract import PROTOCOL, canonical, identity, manifest, read_json, require, verify_manifest, write_json
from .core import (BUDGET, DEVELOPMENT_SEEDS, PILOT_SEED, PILOT_TASKS, ci_only,
                   grid, load_instance, pilot_grid, run_checked)

MAX_SECONDS = 20 * 60
MAX_BYTES = 1024 ** 3


class StudyResourceError(RuntimeError):
    """A fixed resource boundary; it never changes the scientific budget."""


def _json_gzip(path, value, *, lines=False):
    with Path(path).open("wb") as target:
        with gzip.GzipFile(fileobj=target, mode="wb", filename="", mtime=0) as stream:
            if lines:
                for item in value:
                    stream.write(canonical(item) + b"\n")
            else:
                stream.write(canonical(value) + b"\n")


def _optimum(root, task_id):
    """Outer after-search reporting only; no exact reference enters the kernel."""
    path = Path(root) / "studies/knapsack_parameters/evidence/run-37637475385/registry.json"
    require(identity(path)["sha256"] == REGISTRY_SHA, "Historical exact registry changed")
    cases = [row for row in read_json(path)["cases"] if row["instance_id"] == task_id]
    require(len(cases) == 1, "Exact reference missing or duplicated")
    exact = cases[0]["payload"]["exact"]
    value = exact["confirmed_optimum"]
    require(type(value) is int and value > 0 and exact["witness_verified"] is True and
            exact["capacity"]["optimum_profit"] == exact["profit"]["optimum_profit"] == value,
            "Independent exact methods do not agree")
    return value


def build_summary(instance, seed, phase, result, verdict, bank, bank_metadata, provenance, optimum):
    """Reporting fields are separate from the oracle's strictly frozen envelope."""
    summary = result["summary"]
    size = summary["N"]
    valid_initial = [int(v) for v, f in zip(bank["profit"][:size], bank["feasible"][:size], strict=True) if f]
    require(bool(valid_initial) and summary["best_profit"] is not None, "Empty-first bank must give a feasible record")
    require(type(optimum) is int and 0 < optimum >= summary["best_profit"], "Record exceeds exact optimum")
    return {**summary, "protocol_id": PROTOCOL, "phase": phase,
            "instance_id": instance.instance_id, "class_label": instance.class_label,
            "family": instance.family, "index": instance.index, "repeat_seed": seed, "seed": seed,
            "implementation_sha": provenance["implementation_sha"],
            "implementation_commit_sha": provenance["implementation_sha"],
            "source_manifest_sha256": provenance["source_manifest"]["sha256"],
            "run_id": provenance["run_id"], "run_attempt": provenance["run_attempt"],
            "verified": True, "verification_status": "PASS_REPLAY", "verification": verdict,
            "initial_best_profit": max(valid_initial), "exact_optimum": optimum,
            "relative_gap": (optimum - summary["best_profit"]) / optimum,
            "bank_mask_sha256": bank_metadata["mask_sha256"],
            "initial_identity": {"bank_seed": seed, "bank_size": 100, "prefix": size,
                                 "physical_shared_preparation_evaluations": 100,
                                 "physical_evaluations_in_current_search": 0},
            "run_directory": f"runs/{seed}/{summary['configuration_id']}"}


def write_run(directory, result, row):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=False)
    np.savez_compressed(directory / "requests.npz", **result["requests"])
    _json_gzip(directory / "generations.jsonl.gz", result["generations"], lines=True)
    write_json(directory / "search_summary.json", result["summary"])
    write_json(directory / "summary.json", row)
    files = [{"path": p.name, **identity(p)} for p in sorted(directory.iterdir()) if p.is_file()]
    write_json(directory / "manifest.json", {"protocol_id": PROTOCOL, "verified": True,
               "identity": {key: row[key] for key in ("instance_id", "repeat_seed", "configuration_id",
                                                       "implementation_sha", "run_id", "run_attempt")},
               "files": files})
    return sum(p.stat().st_size for p in directory.iterdir() if p.is_file())


def trajectory(instance, seed, result):
    rows, summary = result["requests"], result["summary"]
    best, seen_until, points = None, 0, []
    for event in result["generations"]:
        until = event["last_request"]
        for ref in range(seen_until, until):
            if rows["feasible"][ref] and (best is None or rows["profit"][ref] > best):
                best = int(rows["profit"][ref])
        seen_until = until
        metrics = event["metrics_after"]
        points.append({"request": until, "generation": event["generation"],
                       "complete": event["complete"], "record_profit": best,
                       "mean_feasible_profit": metrics["mean_feasible_profit"],
                       "unique_fraction": metrics["diversity"],
                       "feasible_fraction": metrics["feasible_fraction"]})
    return {"instance_id": instance.instance_id, "repeat_seed": seed,
            "configuration_id": summary["configuration_id"], "p_m": summary["p_m"],
            "p_c": summary["p_c"], "N": summary["N"], "points": points}


def run_task(root, task_id, phase, output, provenance):
    started = time.monotonic()
    ci_only()
    require(phase in ("pilot", "main"), "Only registered development phases are executable")
    require(provenance["protocol_id"] == PROTOCOL, "Wrong run protocol")
    root, output = Path(root).resolve(), Path(output).resolve()
    require(not output.is_relative_to(root), "Scientific output must be outside checkout")
    require(not output.exists() or not any(output.iterdir()), "Existing run evidence is not overwritten")
    instance = load_instance(root, task_id)  # Deliberately rejects all holdout identities.
    if phase == "pilot":
        require(task_id in PILOT_TASKS, "Unregistered pilot task")
        seeds, configs = (PILOT_SEED,), pilot_grid()
    else:
        seeds, configs = DEVELOPMENT_SEEDS, grid()
    module = root / "studies/knapsack_parameters/basic_parameters"
    frozen = read_json(module / "inputs/frozen_banks.json")
    require(frozen["protocol_id"] == PROTOCOL and
            frozen["source_manifest_sha256"] == provenance["source_manifest"]["sha256"],
            "Bank receipt does not certify current scientific sources")
    bundle = module / "inputs/banks"
    verify_manifest(bundle)
    bank_manifest = read_json(bundle / "banks_manifest.json")
    require(bank_manifest["provenance"]["source_manifest"] == provenance["source_manifest"],
            "Bank preparation used different code")
    output.mkdir(parents=True, exist_ok=True)
    summaries, traces, loaded_seeds = [], [], []
    payload_bytes, reference = 0, None
    status, failure = "INCOMPLETE", None
    try:
        for seed in seeds:
            arrays, metadata = load_bank(bundle, instance, seed,
                expected_manifest_sha256=frozen["banks_manifest_sha256"])
            loaded_seeds.append(seed)
            for config in configs:
                if time.monotonic() - started >= MAX_SECONDS:
                    raise StudyResourceError("Registered 20-minute job boundary reached")
                result, verdict = run_checked(instance, config, arrays, metadata, seed, budget=BUDGET)
                if reference is None:
                    reference = _optimum(root, task_id)
                row = build_summary(instance, seed, phase, result, verdict, arrays, metadata, provenance, reference)
                payload_bytes += write_run(output / row["run_directory"], result, row)
                summaries.append(row)
                if phase == "main" and task_id == "UC-s000" and seed == 81001:
                    traces.append(trajectory(instance, seed, result))
                write_json(output / "progress.json", {"instance_id": task_id, "phase": phase,
                           "completed_runs": len(summaries), "expected_runs": len(seeds) * len(configs),
                           "elapsed_seconds": time.monotonic() - started, "journal_bytes": payload_bytes})
                if payload_bytes > MAX_BYTES:
                    raise StudyResourceError("Registered 1-GiB job output boundary reached")
        require(len(summaries) == len(seeds) * len(configs), "Incomplete configuration/seed rectangle")
        if time.monotonic() - started >= MAX_SECONDS:
            raise StudyResourceError("Registered 20-minute job boundary reached")
        status = "COMPLETE"
    except Exception as error:
        failure = {"type": type(error).__name__, "message": str(error)}
        status = "STOP_RESOURCE" if isinstance(error, StudyResourceError) else "INCOMPLETE"
        raise
    finally:
        write_json(output / "summaries.json", summaries)
        if traces:
            write_json(output / "example_trajectories.json", traces)
        output_bytes = sum(p.stat().st_size for p in output.rglob("*") if p.is_file())
        post_resource_error = status == "COMPLETE" and output_bytes > MAX_BYTES
        if post_resource_error:
            status = "STOP_RESOURCE"
            failure = {"type": "StudyResourceError", "message": "Registered 1-GiB total output boundary reached"}
        report = {"schema_version": "knapsack-basic-task-v1", "protocol_id": PROTOCOL,
                  "instance_id": task_id, "phase": phase, "status": status,
                  "failure": failure, "provenance": provenance,
                  "source_manifest_sha256": provenance["source_manifest"]["sha256"],
                  "implementation_sha": provenance["implementation_sha"],
                  "completed_runs": len(summaries), "expected_runs": len(seeds) * len(configs),
                  "independent_mismatches": 0 if status == "COMPLETE" else None,
                  "logical_requests": sum(row["logical_requests"] for row in summaries),
                  "new_physical_search_evaluations": sum(row["physical_evaluations"] for row in summaries),
                  "known_initial_logical_requests": sum(row["known_initial_requests"] for row in summaries),
                  "physical_initial_preparation_in_this_job": 0,
                  "referenced_prior_bank_evaluations": 100 * len(loaded_seeds),
                  "independent_bank_validation_evaluations": 100 * len(loaded_seeds),
                  "independent_search_verification_evaluations": sum(row["logical_requests"] for row in summaries),
                  "banks_manifest_sha256": frozen["banks_manifest_sha256"],
                  "elapsed_seconds": time.monotonic() - started,
                  "journal_bytes": payload_bytes, "output_bytes": output_bytes}
        write_json(output / "manifest.json", report)
        manifest(output)
        actual_bytes = sum(p.stat().st_size for p in output.rglob("*") if p.is_file())
        if actual_bytes > MAX_BYTES and status == "COMPLETE":
            report.update(status="STOP_RESOURCE", independent_mismatches=None,
                          failure={"type": "StudyResourceError", "message": "Final inventory exceeds registered 1-GiB boundary"})
            write_json(output / "manifest.json", report)
            manifest(output)
            raise StudyResourceError(report["failure"]["message"])
        if post_resource_error:
            raise StudyResourceError(failure["message"])
    return report
