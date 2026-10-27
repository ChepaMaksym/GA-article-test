"""Prospective bounded CI phases; no work is dispatched by import."""
from __future__ import annotations

import argparse
from copy import deepcopy
import gzip
import math
import os
from pathlib import Path
import sys
from time import perf_counter_ns
import traceback
import unittest

from . import authority as a


def expected_conditions():
    return [{"task": task, "family": task[3:], "task_index": task_index, "start": start,
             "start_index": start_index, "seed": 97999}
            for task_index, task in enumerate(a.PILOT_TASKS) for start_index, start in enumerate(a.STARTS)]


def _score(problem, mask):
    a.require(type(mask) is str and len(mask) == problem["n"] and set(mask) <= {"0", "1"}, "Invalid initial mask")
    weight = sum(w for w, bit in zip(problem["weights"], mask) if bit == "1")
    profit = sum(v for v, bit in zip(problem["profits"], mask) if bit == "1")
    return {"weight": weight, "profit": profit, "feasible": weight <= problem["capacity"]}


def _initial_masks(condition, center):
    import numpy as np
    generator = np.random.Generator(np.random.PCG64(np.random.SeedSequence(
        [97998, condition["task_index"], condition["start_index"], 97999])))
    before = deepcopy(generator.bit_generator.state)
    if condition["start"] == "cloned":
        masks = [center] * 30
    else:
        masks = ["0" * 100] + ["".join(map(str, generator.integers(0, 2, size=100).tolist())) for _ in range(29)]
    return masks, before, deepcopy(generator.bit_generator.state)


def prepare_pilot(output, permit):
    # Only the source reader is reused. Its historical authority/grant and its
    # preparation/RNG functions are never called.
    from ..two_signal_mutation.banks import source_case
    provenance = a.check_permit(permit, "prepare-pilot")
    a.validated_tests()
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    started = perf_counter_ns()
    sources = {task: source_case(task, "pilot") for task in a.PILOT_TASKS}
    source_validation_ns = perf_counter_ns() - started
    rows = []
    for condition in expected_conditions():
        started = perf_counter_ns()
        source = sources[condition["task"]]
        masks, before, after = _initial_masks(condition, source["center_mask"])
        unique_scores = {mask: _score(source["problem"], mask) for mask in dict.fromkeys(masks)}
        scores = [deepcopy(unique_scores[mask]) for mask in masks]
        bank = {**provenance, **condition, "schema": "mutation-refinement-bank-v1", "stage": "pilot",
                "preparation_seed": 97998, "problem": source["problem"], "source_identity": source["source_identity"],
                "registry_identity": source["registry_identity"], "initial_masks": masks, "initial_scores": scores,
                "initialization_before": before, "initialization_after": after,
                "physical_preparation_evaluations": len(unique_scores), "logical_initial_positions": 30,
                "new_search_calls": 0, "new_exact_solves": 0, "preparation_ns": perf_counter_ns() - started}
        relative = f"banks/{condition['task']}-{condition['start']}-97999.json"
        a.write_json(output / relative, bank)
        rows.append({**condition, "path": relative, **a.identity(output / relative),
                     "physical_preparation_evaluations": len(unique_scores), "preparation_ns": bank["preparation_ns"]})
    registry = {**provenance, "schema": "mutation-refinement-bank-registry-v1", "stage": "pilot",
                "conditions": 8, "pilot_runs": 40, "banks": rows, "preparation_seed": 97998,
                "physical_preparation_evaluations": sum(r["physical_preparation_evaluations"] for r in rows),
                "logical_initial_positions": 240, "existing_center_validation_score_checks": len(sources),
                "source_validation_ns": source_validation_ns, "new_search_calls": 0, "new_exact_solves": 0}
    a.write_json(output / "bank_registry.json", registry)
    a.write_manifest(output)
    return registry


def _validate_bank(bank, source):
    """Reconstruct seed and scores independently of search; account separately."""
    import numpy as np
    generator = np.random.Generator(np.random.PCG64(np.random.SeedSequence(
        [97998, bank["task_index"], bank["start_index"], bank["seed"]])))
    before = deepcopy(generator.bit_generator.state)
    if bank["start"] == "cloned":
        expected = [source["center_mask"] for _ in range(30)]
    else:
        expected = ["0" * 100]
        for _ in range(29):
            bits = generator.integers(low=0, high=2, size=100)
            expected.append("".join("1" if int(bit) else "0" for bit in bits))
    a.require(bank["initial_masks"] == expected and bank["initialization_before"] == before and
              bank["initialization_after"] == generator.bit_generator.state, "Frozen preparation RNG differs")
    actual = []
    for mask in expected:
        weight = profit = 0
        for index, bit in enumerate(mask):
            if bit == "1":
                weight += source["problem"]["weights"][index]
                profit += source["problem"]["profits"][index]
        actual.append({"weight": weight, "profit": profit, "feasible": weight <= source["problem"]["capacity"]})
    a.require(actual == bank["initial_scores"], "Frozen initial scores differ")
    a.require(type(bank.get("physical_preparation_evaluations")) is int and
              bank["physical_preparation_evaluations"] == len(set(expected)) and
              type(bank.get("preparation_ns")) is int and bank["preparation_ns"] >= 0,
              "Invalid preparation accounting")


def load_frozen_banks(check_scores=True, selected_worker=None):
    directory = a.MODULE / "inputs/pilot"
    manifest = a.verify_manifest(directory)
    descriptor_path = a.MODULE / "frozen_pilot_banks.json"
    frozen = a.read_json(descriptor_path)
    a.require(frozen.get("frozen") is True and frozen.get("stage") == "pilot" and
              frozen.get("registry_identity") == a.identity(directory / "bank_registry.json"), "Pilot banks not frozen")
    registry = a.read_json(directory / "bank_registry.json")
    a.require(registry.get("schema") == "mutation-refinement-bank-registry-v1" and registry.get("stage") == "pilot" and
              registry.get("preparation_seed") == 97998 and registry.get("conditions") == 8 and
              registry.get("pilot_runs") == 40 and registry.get("new_search_calls") == registry.get("new_exact_solves") == 0,
              "Foreign preparation registry")
    a.validate_source_receipt(registry, "prepare-pilot")
    a.frozen_artifact(frozen, "inputs", registry)
    a.require(a.seal_frozen_files(descriptor_path, directory, manifest) != registry["implementation_sha"],
              "Separate bank data freeze required")
    expected = {(r["task"], r["start"], r["seed"]): r for r in expected_conditions()}
    a.require(selected_worker is None or selected_worker in a.PILOT_TASKS, "Unregistered bank worker")
    sources = {}
    seen, result = set(), []
    for row in registry["banks"]:
        key = row["task"], row["start"], row["seed"]
        a.require(key in expected and key not in seen, "Foreign or duplicate bank condition")
        seen.add(key)
        relative = f"banks/{row['task']}-{row['start']}-97999.json"
        a.require(row["path"] == relative, "Noncanonical bank path")
        path = a.safe_child(directory, row["path"])
        a.require(a.identity(path) == {"bytes": row["bytes"], "sha256": row["sha256"]}, "Bank identity differs")
        bank = a.read_json(path)
        for name, value in expected[key].items():
            a.require(bank.get(name) == value, "Mixed initial condition")
        for name in ("implementation_sha", "source_manifest", "run_id", "run_attempt", "protocol_id", "registration_sha"):
            a.require(bank.get(name) == registry[name], "Mixed bank provenance")
        a.require(bank.get("schema") == "mutation-refinement-bank-v1" and bank.get("stage") == "pilot" and
                  bank.get("preparation_seed") == 97998 and len(bank["initial_masks"]) == len(bank["initial_scores"]) == 30 and
                  bank.get("logical_initial_positions") == 30 and bank.get("new_search_calls") == bank.get("new_exact_solves") == 0,
                  "Wrong initial population accounting")
        if selected_worker is not None and bank["task"] != selected_worker:
            continue
        if check_scores:
            from ..two_signal_mutation.banks import source_case
            if bank["task"] not in sources:
                sources[bank["task"]] = source_case(bank["task"], "pilot")
            source = sources[bank["task"]]
            a.require(bank["problem"] == source["problem"] and bank["source_identity"] == source["source_identity"] and
                      bank["registry_identity"] == source["registry_identity"], "Frozen bank source differs")
            _validate_bank(bank, source)
        result.append(bank)
    a.require(seen == set(expected) and len(registry["banks"]) == 8 and
              registry.get("physical_preparation_evaluations") == sum(r["physical_preparation_evaluations"] for r in registry["banks"]),
              "Incomplete bank rectangle or accounting")
    return result


def run_tests(output, permit):
    provenance = a.check_permit(permit, "tests")
    suite = unittest.defaultTestLoader.discover(str(a.MODULE / "tests"), pattern="test_*.py", top_level_dir=str(a.ROOT))
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    a.write_json(Path(output) / "tests_receipt.json", {**provenance, "tests_passed": result.wasSuccessful(),
                 "tests_run": result.testsRun, "failures": len(result.failures), "errors": len(result.errors),
                 "skipped": len(result.skipped), "scientific_search_performed": False,
                 "instructional_fixtures_only": True, "new_exact_solves": 0})
    a.write_manifest(output)
    a.require(result.wasSuccessful() and not result.skipped and result.testsRun > 0, "Tests not fully green")


def balanced_order(condition):
    index = 2 * condition["task_index"] + condition["start_index"]
    return tuple(a.METHODS[(index + i) % len(a.METHODS)] for i in range(len(a.METHODS)))


def _condition_key(task, start, method):
    return task, start, 97999, method


def evaluation_accounting(verification):
    """Classify actual scorer calls; replay subtotals are part of its total.

    Search evaluates final children, not their pre-mutation intermediates.
    Initial-score validation and all independent replay calls are separate
    from the new-search budget. No scorer is invoked by this helper.
    """
    calls = verification.get("new_calls")
    a.require(verification.get("verification_status") == "VERIFIED" and
              type(calls) is int and 1 <= calls <= 5000, "Invalid replay query accounting")
    summary = verification.get("summary", {})
    a.require(type(summary) is dict and
              all(type(summary.get(name)) is int for name in
                  ("physical_evaluations", "new_calls", "known_score_validation_evaluations")) and
              summary.get("physical_evaluations") == summary.get("new_calls") == calls and
              summary.get("known_score_validation_evaluations") == 30,
              "Invalid search/initial validation accounting")
    initial = verification.get("initial_score_checks")
    final = verification.get("final_score_checks")
    premutation = verification.get("premutation_score_checks")
    total = verification.get("independent_score_checks")
    a.require(all(type(value) is int for value in (initial, final, premutation, total)) and
              initial == 30 and final == premutation == calls and
              total == initial + final + premutation, "Invalid independent replay accounting split")
    return {"new_search_evaluations": calls,
            "engine_initial_score_validation_evaluations": 30,
            "engine_premutation_observational_evaluations": 0,
            "independent_replay_score_checks": total,
            "independent_replay_initial_score_checks": initial,
            "independent_replay_final_score_checks": final,
            "independent_replay_premutation_score_checks": premutation}


def validate_record_accounting(record):
    """Reject absent, falsely attributed or double-counted compact counters."""
    expected = evaluation_accounting({
        "verification_status": "VERIFIED", "summary": record.get("summary"),
        "new_calls": record.get("new_search_evaluations"),
        "independent_score_checks": record.get("independent_replay_score_checks"),
        "initial_score_checks": record.get("independent_replay_initial_score_checks"),
        "final_score_checks": record.get("independent_replay_final_score_checks"),
        "premutation_score_checks": record.get("independent_replay_premutation_score_checks")})
    a.require(all(type(record.get(name)) is int and record[name] == value
                  for name, value in expected.items()), "Compact evaluation accounting differs from replay")


def run_worker(worker, output, permit):
    from . import engine, verifier
    from ..two_signal_mutation.banks import source_case
    started_worker = perf_counter_ns()
    provenance = a.check_permit(permit, "pilot")
    a.require(worker in a.PILOT_TASKS and tuple(engine.METHODS) == a.METHODS, "Unregistered pilot worker/methods")
    started = perf_counter_ns()
    banks = load_frozen_banks(check_scores=True, selected_worker=worker)
    source = source_case(worker, "pilot")  # External reference; never passed into search.
    validation_ns = perf_counter_ns() - started
    a.require(len(banks) == 2, "Expected exactly two shared beginnings")
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    records, errors, compressed_bytes = [], [], 0
    grant = a.grant_for("pilot")
    try:
        for bank in banks:
            for order_index, method in enumerate(balanced_order(bank)):
                started = perf_counter_ns()
                log = engine.run_search(bank["problem"], bank["initial_masks"], bank["initial_scores"], method,
                    engine.make_rngs(97999, bank["task_index"], bank["start_index"]), budget=5000)
                search_ns = perf_counter_ns() - started
                basename = f"{worker}-{bank['start']}-97999-{method}"
                relative = f"logs/{basename}.json.gz"
                started = perf_counter_ns()
                raw = gzip.compress(a.canonical(log), mtime=0)
                path = output / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(raw)
                serialization_ns = perf_counter_ns() - started
                compressed_bytes += len(raw)
                metadata = {**provenance, "stage": "pilot", "task": worker, "family": bank["family"],
                    "task_index": bank["task_index"], "start": bank["start"], "start_index": bank["start_index"],
                    "seed": 97999, "method": method, "order_index": order_index, "log_path": relative,
                    "log_identity": a.identity(path), "verification_status": "PENDING_INDEPENDENT_REPLAY",
                    "bank_identity": a.identity(a.MODULE / "inputs/pilot/banks" / f"{worker}-{bank['start']}-97999.json"),
                    "source_identity": source["source_identity"]}
                metadata_path = output / "metadata" / (basename + ".json")
                a.write_json(metadata_path, metadata)  # Retain full failed journal before replay.
                a.require(compressed_bytes <= grant["maximum_compressed_bytes_per_worker"], "Worker journal quota exceeded")
                started = perf_counter_ns()
                verification = verifier.verify_log(log)
                verification_ns = perf_counter_ns() - started
                a.require(verification.get("verification_status") == "VERIFIED" and verification["new_calls"] == 5000,
                          "Independent replay not complete")
                summary = verification["summary"]
                record = {"task": worker, "family": bank["family"], "start": bank["start"], "seed": 97999,
                    "method": method, "order_index": order_index, "log_path": relative, "log_identity": metadata["log_identity"],
                    "bank_identity": metadata["bank_identity"], "source_identity": source["source_identity"],
                    "summary": summary, "optimum_external_to_search": source["optimum"],
                    "final_gap_percent": 100 * (source["optimum"] - summary["best_profit"]) / source["optimum"],
                    **evaluation_accounting(verification),
                    "timings": {"search_wall_ns": search_ns, "serialization_ns": serialization_ns,
                                "verification_ns": verification_ns, "engine_timing_ns": verification["timing_ns"]}}
                records.append(record)
                metadata.update({"verification_status": "VERIFIED", "record": record})
                a.write_json(metadata_path, metadata)
                print(f"VERIFIED {basename}: 5000 new search evaluations", flush=True)
                del log, raw, verification
    except Exception as exc:
        errors.append({"type": type(exc).__name__, "message": str(exc)})
        raise
    finally:
        a.write_json(output / "worker_summary.json", {**provenance, "schema": "mutation-refinement-worker-v1",
            "stage": "pilot", "worker": worker, "expected_runs": 10, "verified_runs": len(records),
            "complete": len(records) == 10 and not errors, "records": records, "errors": errors,
            "compressed_journal_bytes": compressed_bytes, "worker_ns": perf_counter_ns() - started_worker,
            "bank_validation_ns": validation_ns, "bank_validation_initial_score_checks": 60,
            "existing_center_validation_score_checks": 2, "new_exact_solves": 0})
        a.write_manifest(output)


def cost_review(records, workers):
    a.require(len(records) == 40 and len(workers) == 4, "A complete technical pilot is required for cost forecasting")
    seconds = [sum(r["timings"][k] for k in ("search_wall_ns", "serialization_ns", "verification_ns")) / 1e9 for r in records]
    maximum = max(max(seconds), max(w["worker_ns"] / 10 / 1e9 for w in workers))
    compressed = sum(w["compressed_journal_bytes"] for w in workers)
    return {"forecast_only": True, "calibration_authorized": False, "main_authorized": False,
            "pilot_runs": 40, "pilot_maximum_seconds_per_run": maximum, "pilot_mean_seconds_per_run": sum(seconds) / 40,
            "future_calibration_runs": 900, "future_main_maximum_physical_runs": 3600,
            "future_main_runs_if_fixed_labels_coincide": 2700,
            "forecast_calibration_compute_runner_minutes_with_50pct_reserve": math.ceil(1.5 * maximum * 900 / 60),
            "forecast_main_compute_runner_minutes_with_50pct_reserve": math.ceil(1.5 * maximum * 3600 / 60),
            "pilot_compressed_journal_bytes": compressed,
            "forecast_calibration_journal_bytes_with_50pct_reserve": math.ceil(1.5 * compressed * 900 / 40),
            "forecast_main_journal_bytes_with_50pct_reserve": math.ceil(1.5 * compressed * 3600 / 40),
            "new_source_preparation_measured": False, "new_exact_reference_cost_measured": False,
            "full_future_ci_cost_known": False,
            "limits": "Compute/journal extrapolation only; fresh-source auditing, exact references, future tests, setup, aggregation, bootstrap and retries need separate estimates and approval."}


def aggregate(workers, output, permit):
    provenance = a.check_permit(permit, "pilot")
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    seen, records, errors, receipts = set(), [], [], []
    expected_keys = {_condition_key(task, start, method) for task in a.PILOT_TASKS for start in a.STARTS for method in a.METHODS}
    seen_keys = set()
    for path in sorted(Path(workers).rglob("worker_summary.json")):
        try:
            a.verify_manifest(path.parent)
            row = a.read_json(path)
            a.require(row.get("schema") == "mutation-refinement-worker-v1" and row.get("stage") == "pilot" and
                      row.get("worker") in set(a.PILOT_TASKS) - seen, "Foreign or duplicate producer")
            seen.add(row["worker"])
            for field in ("protocol_id", "registration_sha", "implementation_sha", "source_manifest", "run_id", "run_attempt"):
                a.require(row.get(field) == provenance[field], "Mixed producer provenance: " + field)
            a.require(row.get("complete") is True and not row.get("errors") and
                      row.get("expected_runs") == row.get("verified_runs") == len(row["records"]) == 10,
                      "Incomplete producer")
            checked_bytes = 0
            for record in row["records"]:
                key = record["task"], record["start"], record["seed"], record["method"]
                a.require(key in expected_keys - seen_keys and key[0] == row["worker"], "Foreign/duplicate search condition")
                seen_keys.add(key)
                log_path = a.safe_child(path.parent, record["log_path"])
                a.require(a.identity(log_path) == record["log_identity"], "Full gzip journal identity differs")
                basename = log_path.name.removesuffix(".json.gz")
                metadata = a.read_json(path.parent / "metadata" / (basename + ".json"))
                a.require(metadata.get("verification_status") == "VERIFIED" and metadata.get("record") == record,
                          "Compact record does not match replay receipt")
                for field in ("implementation_sha", "source_manifest", "run_id", "run_attempt", "protocol_id"):
                    a.require(metadata.get(field) == provenance[field], "Mixed replay receipt")
                a.require(record["new_search_evaluations"] == record["summary"]["physical_evaluations"] == 5000 and
                          record["independent_replay_score_checks"] == 10030, "Wrong independent evaluation accounting")
                validate_record_accounting(record)
                checked_bytes += record["log_identity"]["bytes"]
                records.append(record)
            a.require(checked_bytes == row["compressed_journal_bytes"], "Wrong worker log byte accounting")
            receipts.append({k: row[k] for k in ("worker", "verified_runs", "compressed_journal_bytes", "worker_ns",
                              "bank_validation_ns", "bank_validation_initial_score_checks", "existing_center_validation_score_checks")})
        except Exception as exc:
            errors.append({"path": path.relative_to(Path(workers)).as_posix(), "error": str(exc)})
    jobs = [job for job in a.pages(f"/actions/runs/{provenance['run_id']}/attempts/{provenance['run_attempt']}/jobs", "jobs")
            if job["name"].startswith("pilot (")]
    if len(jobs) != 4 or {j["name"] for j in jobs} != {f"pilot ({w})" for w in a.PILOT_TASKS} or any(j.get("conclusion") != "success" for j in jobs):
        errors.append({"error": "All four exact source worker jobs must succeed"})
    complete = seen == set(a.PILOT_TASKS) and seen_keys == expected_keys and len(records) == 40 and not errors
    status = {**provenance, "stage": "pilot", "complete": complete, "expected_runs": 40, "verified_runs": len(records),
              "workers": receipts, "errors": errors, "new_search_performed_during_aggregation": False}
    a.write_json(output / "audit_status.json", status)
    a.write_manifest(output)
    a.require(complete, "Incomplete pilot retained; cost forecast blocked")
    registry = a.read_json(a.MODULE / "inputs/pilot/bank_registry.json")
    costs = {"new_search_evaluations": sum(r["new_search_evaluations"] for r in records),
             "initial_preparation_physical_evaluations": registry["physical_preparation_evaluations"],
             "initial_preparation_logical_positions": registry["logical_initial_positions"],
             "preparation_existing_center_score_checks": registry["existing_center_validation_score_checks"],
             "worker_existing_center_score_checks": sum(w["existing_center_validation_score_checks"] for w in receipts),
             "bank_validation_initial_score_checks": sum(w["bank_validation_initial_score_checks"] for w in receipts),
             "engine_initial_validation_evaluations": sum(r["engine_initial_score_validation_evaluations"] for r in records),
             "engine_premutation_observational_evaluations": sum(r["engine_premutation_observational_evaluations"] for r in records),
             "independent_replay_score_checks": sum(r["independent_replay_score_checks"] for r in records),
             "independent_replay_initial_score_checks": sum(r["independent_replay_initial_score_checks"] for r in records),
             "independent_replay_final_score_checks": sum(r["independent_replay_final_score_checks"] for r in records),
             "independent_replay_premutation_score_checks": sum(r["independent_replay_premutation_score_checks"] for r in records),
             "independent_replay_split_is_breakdown_of_total": True,
             "compressed_journal_bytes": sum(w["compressed_journal_bytes"] for w in receipts), "new_exact_solves": 0}
    summary = {**status, "costs": costs, "records": records, "statistical_bootstrap_performed": False,
               "scientific_superiority_established": False, "calibration_authorized": False, "main_authorized": False}
    a.write_json(output / "pilot_summary.json", summary)
    a.write_json(output / "cost_review.json", cost_review(records, receipts))
    (output / "REPORT_UK.md").write_text(
        "# Технічний пілот уточнення мутації\n\n"
        "Перевірено 40/40 запусків на чотирьох старих задачах із двома початками й п'ятьма правилами. "
        "На кожний запуск припадає 5000 нових пошукових оцінювань; повні журнали залишаються у worker-артефактах.\n\n"
        "Підготовчі оцінювання, перевірки початків, спостереження до мутації й незалежне відновлення обліковано окремо. "
        "Зовнішній час пошуку вже включає внутрішні складові; повторно їх не додають.\n\n"
        "Це технічна перевірка й вимірювання ресурсів. Наукову перевагу або новизну не встановлено; "
        "калібрування, нові точні еталони та основну серію не дозволено. Прогноз не є повним кошторисом або дозволом.\n",
        encoding="utf-8")
    a.write_manifest(output)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("preflight", "tests", "prepare", "worker", "aggregate"))
    parser.add_argument("--output", required=True)
    parser.add_argument("--permit")
    parser.add_argument("--worker")
    parser.add_argument("--workers")
    args = parser.parse_args()
    try:
        selected = a.phase(os.environ.get("COMMIT_MESSAGE", ""))
        if args.command == "preflight":
            a.preflight(selected, args.output)
        elif args.command == "tests":
            a.require(selected == "tests" and args.permit, "Wrong tests phase")
            run_tests(args.output, args.permit)
        elif args.command == "prepare":
            a.require(selected == "prepare-pilot" and args.permit, "Wrong preparation phase")
            prepare_pilot(args.output, args.permit)
        elif args.command == "worker":
            a.require(selected == "pilot" and args.permit and args.worker, "Wrong pilot worker phase")
            run_worker(args.worker, args.output, args.permit)
        else:
            a.require(selected == "pilot" and args.permit and args.workers, "Wrong aggregation phase")
            aggregate(args.workers, args.output, args.permit)
    except Exception as exc:
        output = Path(args.output)
        output.mkdir(parents=True, exist_ok=True)
        a.write_json(output / "failure.json", {"command": args.command, "type": type(exc).__name__, "message": str(exc)})
        a.write_manifest(output)
        traceback.print_exc()
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
