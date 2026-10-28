"""Registered donor/recipient CI phases; no search is dispatched on import."""
from __future__ import annotations

import argparse
import gzip
import hashlib
import math
import os
from pathlib import Path
import shutil
import sys
from time import perf_counter_ns, sleep
import traceback
import unittest

from . import authority as a


def run_tests(output, permit):
    provenance = a.check_permit(permit, "tests")
    suite = unittest.defaultTestLoader.discover(str(a.MODULE / "tests"), pattern="test_*.py", top_level_dir=str(a.ROOT))
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    a.write_json(Path(output) / "tests_receipt.json", {**provenance, "tests_passed": result.wasSuccessful(),
                 "tests_run": result.testsRun, "failures": len(result.failures), "errors": len(result.errors),
                 "skipped": len(result.skipped), "scientific_search_performed": False, "scientific_bootstrap_performed": False,
                 "instructional_fixtures_only": True, "new_exact_solves": 0})
    a.write_manifest(output)
    a.require(result.wasSuccessful() and not result.skipped and result.testsRun > 0, "Checks not fully green")


def balanced_order(bank):
    offset = bank["condition_index"] % len(a.PROFILES)
    return a.PROFILES[offset:] + a.PROFILES[:offset]


def run_worker(selected, worker, output, permit):
    from . import analysis, banks, engine
    started_worker = perf_counter_ns()
    provenance = a.check_permit(permit, selected)
    stage, role = selected.split("-")
    started = perf_counter_ns()
    beginnings = banks.load_frozen_banks(stage, selected_worker=worker)
    bank_validation_ns = perf_counter_ns() - started
    expected = [row for row in banks.expected_conditions(stage) if row["worker"] == worker]
    a.require(beginnings and len(beginnings) == len(expected), "Wrong worker conditions")
    started_schedule = perf_counter_ns()
    schedule_map = banks.load_frozen_schedules(stage)[0] if role == "recipients" else {}
    bank_validation_ns += perf_counter_ns() - started_schedule
    count = len(beginnings) * (6 if role == "recipients" else 1)
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    records, schedules, errors, compressed_bytes = [], [], [], 0
    sources = {bank["task"]: banks.source_case(bank["task"], stage) for bank in beginnings}
    try:
        for bank in beginnings:
            source = sources[bank["task"]]
            condition_key = bank["task"], bank["start"], bank["seed"]
            frozen_schedule = schedule_map.get(condition_key)
            if frozen_schedule:
                a.require(frozen_schedule["bank_identity"] == bank["bank_identity"], "Donor and recipient beginnings differ")
            search_seed = bank["donor_seed"] if role == "donors" else bank["seed"]
            profiles = ("adaptive",) if role == "donors" else balanced_order(bank)
            for order_index, profile in enumerate(profiles):
                started = perf_counter_ns()
                log = engine.run_search(bank["problem"], bank["initial_masks"], bank["initial_scores"], profile,
                                        engine.make_rngs(search_seed, bank["task_index"], bank["start_index"]), budget=5000,
                                        schedule=frozen_schedule["values"] if profile == "replay" else None)
                search_ns = perf_counter_ns() - started
                # Bind replayable states to the registered seed identity as well
                # as reconstructing the operators from their persisted states.
                import numpy as np
                expected_states = {name: np.random.PCG64(np.random.SeedSequence(
                    [search_seed, bank["task_index"], bank["start_index"], channel])).state
                    for channel, name in enumerate(("initialization", "selection", "branch", "crossover", "mutation", "ties"))}
                a.require(log["rng_initial"] == expected_states and log["initial_masks"] == bank["initial_masks"] and
                          log["initial_scores"] == bank["initial_scores"] and log["problem"] == bank["problem"] and
                          log["profile"] == profile and log["budget"] == 5000, "Journal seed, beginning or profile identity differs")
                # The journal is retained before replay, including a failed replay.
                basename = f"{bank['task']}-{bank['start']}-{bank['seed']}-{profile}"
                relative = "logs/" + basename + ".json.gz"
                started = perf_counter_ns()
                raw = gzip.compress(a.canonical(log), mtime=0)
                # Never exceed a job's disjoint journal allocation by one log.
                # On exhaustion this phase remains incomplete; no replacement
                # seed or shortened search is dispatched. A repeated source
                # phase is separately blocked by the cumulative resource gate.
                a.require(compressed_bytes + len(raw) <= a.journal_allowance(selected),
                          "Compressed journal quota exhausted before writing the next journal; phase incomplete")
                path = output / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(raw)
                serialization_ns = perf_counter_ns() - started
                compressed_bytes += len(raw)
                metadata = {**provenance, "stage": stage, "role": role, "task": bank["task"], "start": bank["start"],
                            "seed": bank["seed"], "search_seed": search_seed, "profile": profile, "order_index": order_index,
                            "bank_identity": bank["bank_identity"], "source_identity": source["source_identity"],
                            "log_path": relative, "log_identity": a.identity(path), "verification_status": "PENDING_INDEPENDENT_REPLAY"}
                a.write_json(output / "metadata" / (basename + ".json"), metadata)
                envelope = {"task": bank["task"], "family": bank["family"], "start": bank["start"], "seed": bank["seed"],
                            "profile": profile, "stage": stage, "implementation_sha": provenance["implementation_sha"],
                            "optimum": source["optimum"], "log": log,
                            "timings": {"search_wall_ns": search_ns, "serialization_ns": serialization_ns,
                                        "verification_ns": None, "preparation_ns": bank["preparation_ns"]}}
                started = perf_counter_ns()
                row = analysis.extract_run(envelope)
                row["timings"]["verification_ns"] = perf_counter_ns() - started
                row.update({"role": "recipient" if role == "recipients" else "donor", "search_seed": search_seed, "order_index": order_index,
                            "bank_identity": bank["bank_identity"], "log_identity": metadata["log_identity"]})
                records.append(row)
                metadata.update({"verification_status": "VERIFIED", "timings": row["timings"]})
                a.write_json(output / "metadata" / (basename + ".json"), metadata)
                if role == "donors":
                    values = engine.extract_schedule(log)
                    schedule = {"task": bank["task"], "start": bank["start"], "seed": bank["seed"], "donor_seed": search_seed,
                                "bank_identity": bank["bank_identity"], "source_manifest": provenance["source_manifest"],
                                "implementation_sha": provenance["implementation_sha"], "donor_journal_sha256": hashlib.sha256(a.canonical(log)).hexdigest(), "values": values}
                    schedule_relative = f"schedules/{bank['task']}-{bank['start']}-{bank['seed']}.json"
                    a.write_json(output / schedule_relative, schedule)
                    schedules.append({"task": bank["task"], "start": bank["start"], "seed": bank["seed"], "path": schedule_relative,
                                      **a.identity(output / schedule_relative)})
                print(f"VERIFIED {role} {basename}: 5000 new calls", flush=True)
                del log, raw, envelope
    except Exception as exc:
        errors.append({"type": type(exc).__name__, "message": str(exc)})
        raise
    finally:
        a.write_json(output / "worker_summary.json", {**provenance, "schema": "tournament-feedback-worker-v1", "phase": selected,
                     "stage": stage, "role": role, "worker": worker, "expected_runs": count, "verified_runs": len(records),
                     "complete": len(records) == count and not errors, "records": records, "schedules": schedules, "errors": errors,
                     "compressed_journal_bytes": compressed_bytes, "worker_ns": perf_counter_ns() - started_worker,
                     "bank_validation_ns": bank_validation_ns, "bank_validation_initial_score_checks": 30 * len(beginnings)})
        a.write_manifest(output)


def source_jobs_complete(provenance, selected, expected):
    wanted = {f"{selected} ({worker})" for worker in expected}
    # Actions API can briefly lag jobs which have already completed; retry only metadata.
    for attempt in range(7):
        jobs = [row for row in a.pages(f"/actions/runs/{provenance['run_id']}/attempts/{provenance['run_attempt']}/jobs", "jobs")
                if row["name"].startswith(selected + " (")]
        if {row["name"] for row in jobs} == wanted and len(jobs) == len(wanted) and all(row.get("conclusion") == "success" for row in jobs):
            a.require(all(row.get("head_sha") == provenance["implementation_sha"] for row in jobs), "Source job SHA differs")
            return jobs
        if attempt < 6:
            sleep(5)
    raise ValueError("Exact source jobs did not all complete successfully")


def cost_review(donor_registry, recipient_receipts, recipient_records):
    donors = donor_registry["records"]
    a.require(len(donors) == 8 and len(recipient_records) == 48, "Complete 56-run pilot required")
    # Frozen-registry validation is paid once per worker. Scaling that fixed
    # API/Git cost as if it occurred after every candidate run overstates work.
    donor_rate = max((row["worker_ns"] - row["bank_validation_ns"]) / row["verified_runs"] for row in donor_registry["workers"]) / 1e9
    recipient_rate = max((row["worker_ns"] - row["bank_validation_ns"]) / row["verified_runs"] for row in recipient_receipts) / 1e9
    donor_timeout = max(2, math.ceil(donor_rate * 90 * 1.25 / 60) + 1)
    recipient_timeout = max(2, math.ceil(recipient_rate * 540 * 1.25 / 60) + 1)
    compressed = donor_registry["compressed_journal_bytes"] + sum(row["compressed_journal_bytes"] for row in recipient_receipts)
    forecast_bytes = math.ceil((donor_registry["compressed_journal_bytes"] * 900 / 8 +
                                sum(row["compressed_journal_bytes"] for row in recipient_receipts) * 5400 / 48) * 1.25) + compressed
    # Reserve actual configured timeouts, including all service jobs/rounding,
    # rather than presenting concurrent wall time as cumulative runner time.
    reserve = a.RESERVATIONS["prepare-main"] + a.RESERVATIONS["main-donors"] + a.RESERVATIONS["main-recipients"] + a.RESERVATIONS["aggregate"]
    return {"pilot_physical_runs": 56, "future_runs": 6300, "future_new_search_calls": 31500000,
            "measured_donor_seconds_per_run_max_worker_mean": donor_rate,
            "measured_recipient_seconds_per_run_max_worker_mean": recipient_rate, "reserve_factor": 1.25,
            "measured_pilot_bank_validation_ns": sum(row["bank_validation_ns"] for row in donor_registry["workers"] + recipient_receipts),
            "fixed_worker_setup_reserve_minutes": 1,
            "forecast_main_donor_timeout": donor_timeout, "forecast_main_recipient_timeout": recipient_timeout,
            "configured_main_donor_timeout": a.TIMEOUTS["main-donors"], "configured_main_recipient_timeout": a.TIMEOUTS["main-recipients"],
            "forecast_main_runner_minutes": reserve, "forecast_total_journal_bytes": forecast_bytes,
            "pilot_compressed_journal_bytes": compressed, "fresh_exact_preparation_measured": False,
            "preparation_timeout_minutes_reserved": a.TIMEOUTS["prepare-main"], "automatic_sample_reduction_allowed": False}


def aggregate_phase(selected, workers, output, permit):
    from . import analysis, banks
    provenance = a.check_permit(permit, selected)
    stage, role = selected.split("-")
    expected = set(a.PILOT_TASKS if stage == "pilot" else a.MAIN_WORKERS)
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    seen, records, receipts, schedules, errors = set(), [], [], [], []
    for path in sorted(Path(workers).rglob("worker_summary.json")):
        try:
            a.verify_manifest(path.parent)
            row = a.read_json(path)
            a.require(row.get("worker") in expected - seen and row.get("phase") == selected and row.get("schema") == "tournament-feedback-worker-v1", "Duplicate or foreign worker")
            seen.add(row["worker"])
            for key in ("protocol_id", "source_manifest", "implementation_sha", "run_id", "run_attempt"):
                a.require(row.get(key) == provenance[key], "Mixed producer provenance: " + key)
            count = (2 if stage == "pilot" else 90) * (6 if role == "recipients" else 1)
            a.require(row.get("complete") is True and not row.get("errors") and row.get("expected_runs") == row.get("verified_runs") == len(row["records"]) == count, "Incomplete producer retained")
            records.extend(row["records"])
            receipts.append({key: row[key] for key in ("worker", "verified_runs", "compressed_journal_bytes", "worker_ns", "bank_validation_ns")})
            for schedule in row["schedules"]:
                original = a.safe_child(path.parent, schedule["path"])
                a.require(a.identity(original) == {"bytes": schedule["bytes"], "sha256": schedule["sha256"]}, "Schedule manifest differs")
                target = a.safe_child(output, schedule["path"])
                a.require(not target.exists(), "Duplicate donor schedule")
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(original, target)
                schedules.append(schedule)
        except Exception as exc:
            errors.append({"producer": path.parent.name, "error": str(exc)})
    try:
        source_jobs_complete(provenance, selected, expected)
    except Exception as exc:
        errors.append({"error": str(exc)})
    count = (8 if stage == "pilot" else 900) * (6 if role == "recipients" else 1)
    audit = {**provenance, "phase": selected, "stage": stage, "role": role, "expected_runs": count, "verified_runs": len(records),
             "complete": seen == expected and len(records) == count and not errors, "errors": errors, "workers": receipts,
             "compressed_journal_bytes": sum(row["compressed_journal_bytes"] for row in receipts), "new_search_performed_during_aggregation": False}
    a.write_json(output / "audit_status.json", audit)
    a.write_manifest(output)
    a.require(audit["complete"], "Incomplete phase retained; analysis blocked")
    expected_identities = {(row["task"], row["start"], row["seed"], profile) for row in banks.expected_conditions(stage)
                           for profile in (("adaptive",) if role == "donors" else a.PROFILES)}
    identities = [(row["task"], row["start"], row["seed"], row["profile"]) for row in records]
    a.require(len(set(identities)) == len(identities) and set(identities) == expected_identities, "Incomplete or duplicate result rectangle")
    a.require(all(row.get("verification_status") == "VERIFIED" and row["implementation_sha"] == provenance["implementation_sha"] for row in records), "Unverified/mixed compact results")
    if role == "donors":
        registry = {**provenance, "schema": "tournament-feedback-schedules-v1", "phase": selected, "stage": stage,
                    "complete": True, "schedules": schedules, "records": records, "workers": receipts,
                    "compressed_journal_bytes": audit["compressed_journal_bytes"], "donor_runs": count,
                    "new_search_calls": 5000 * count, "selection_of_best_donor": False}
        a.require(len(schedules) == count, "Incomplete applied schedule collection")
        a.write_json(output / "schedule_registry.json", registry)
    else:
        _, donor_registry = banks.load_frozen_schedules(stage)
        summary = analysis.aggregate(records, scope=stage, expected_sha=provenance["implementation_sha"])
        a.write_json(output / "series_summary.json", summary)
        (output / "compact_records.json.gz").write_bytes(gzip.compress(a.canonical(records), mtime=0))
        rendering = analysis.render_report(summary, output / "figures")
        a.write_json(output / "rendering_receipt.json", rendering)
        audit["physical_runs_including_donors"] = count + donor_registry["donor_runs"]
        audit["new_search_calls_including_donors"] = 5000 * audit["physical_runs_including_donors"]
        audit["donor_compressed_journal_bytes"] = donor_registry["compressed_journal_bytes"]
        audit["total_compressed_journal_bytes"] = audit["compressed_journal_bytes"] + donor_registry["compressed_journal_bytes"]
        if stage == "pilot":
            audit["cost_review"] = cost_review(donor_registry, receipts, records)
            a.write_json(output / "cost_review.json", audit["cost_review"])
        else:
            pilot, _ = a.frozen_receipt("pilot", "pilot-recipients")
            a.require(audit["total_compressed_journal_bytes"] + pilot["total_compressed_journal_bytes"] <= 6 * 2 ** 30, "Cumulative compressed evidence ceiling exceeded")
        a.write_json(output / "audit_status.json", audit)
    a.write_manifest(output)


def final_resource_review(output, permit):
    provenance = a.check_permit(permit, "aggregate")
    main, _ = a.frozen_receipt("main", "main-recipients")
    usage = a.runner_usage("aggregate")
    a.require(main.get("complete") is True and main.get("physical_runs_including_donors") == 6300, "Complete main series required")
    a.write_json(Path(output) / "final_resource_receipt.json", {**provenance, "main_receipt": main, "usage_before_current_service_job": usage,
                 "current_service_reservation": a.RESERVATIONS["aggregate"], "budget_ceiling": a.grant_for("aggregate")["runner_minutes_ceiling"],
                 "cumulative_bound_minutes": usage["used_runner_minutes"] + a.RESERVATIONS["aggregate"]})
    a.write_manifest(output)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("preflight", "tests", "prepare", "worker", "aggregate", "final"))
    parser.add_argument("--output", required=True)
    parser.add_argument("--permit")
    parser.add_argument("--stage", choices=("pilot", "main"))
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
            from . import banks
            a.require(selected == "prepare-" + str(args.stage) and args.permit, "Wrong preparation phase")
            banks.prepare(args.stage, args.output, a.check_permit(args.permit, selected))
        elif args.command == "worker":
            a.require(selected.endswith(("-donors", "-recipients")) and args.worker and args.permit, "Wrong worker phase")
            run_worker(selected, args.worker, args.output, args.permit)
        elif args.command == "aggregate":
            a.require(selected.endswith(("-donors", "-recipients")) and args.workers and args.permit, "Wrong aggregation phase")
            aggregate_phase(selected, args.workers, args.output, args.permit)
        else:
            a.require(selected == "aggregate" and args.permit, "Wrong final resource phase")
            final_resource_review(args.output, args.permit)
    except Exception as exc:
        a.write_json(Path(args.output) / "failure.json", {"type": type(exc).__name__, "message": str(exc), "command": args.command})
        a.write_manifest(args.output)
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
