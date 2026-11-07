"""Prospective resource quotes from the registered technical pilot.

These estimates do not select a population or authorize another execution phase.
Boundary measurements are an empirical basis, not a bound on unseen inputs,
intermediate populations, network throughput, or irace itself.
"""
from __future__ import annotations

import os


SIZES = (100, 200, 500)
TYPES = ("UC", "WC", "SC")
NANOSECONDS_PER_MINUTE = 60 * 1_000_000_000
MEBIBYTE = 1024**2
TIME_RESERVE_FACTOR = 2
BYTE_RESERVE_NUMERATOR = 3
BYTE_RESERVE_DENOMINATOR = 2


def _require(condition, message):
    if not condition:
        raise ValueError("Invalid resource-quote evidence: " + message)


def _integer(value, label, minimum=0):
    _require(type(value) is int and value >= minimum, label + " must be a non-boolean integer")
    return value


def _ceil_div(numerator, denominator):
    return (numerator + denominator - 1) // denominator


def _case_key(case):
    return case.get("n"), case.get("class_label")


def _measurement_bases(prepared_registry, worker_receipts):
    _require(type(prepared_registry) is dict
             and prepared_registry.get("schema") == "population-size-pilot-preparation-v1"
             and prepared_registry.get("status") == "PREPARED_CERTIFIED_PILOT_INPUTS",
             "a complete prepared pilot registry is required")
    cases = prepared_registry.get("cases")
    _require(type(cases) is list and len(cases) == 9, "exactly nine prepared cases are required")
    expected = {(n, kind) for n in SIZES for kind in TYPES}
    indexed_cases = {}
    for case in cases:
        _require(type(case) is dict and _case_key(case) in expected
                 and _case_key(case) not in indexed_cases, "duplicate or unexpected prepared case")
        _require(type(case.get("task_id")) is str and bool(case["task_id"]), "missing prepared task identity")
        timing = case.get("timing_ns", {})
        for name in ("certification", "bank_preparation", "bank_verification", "bank_serialization"):
            _integer(timing.get(name), "prepared " + name)
        files = case.get("files", {})
        for name in ("problem", "certificate", "bank", "bank_metadata"):
            _require(type(files.get(name)) is dict, "missing prepared file descriptor")
            _integer(files[name].get("bytes"), "prepared " + name + " bytes", 1)
        _require(case.get("physical_preparation_evaluations") == 25000
                 and case.get("independent_verification_evaluations") == 25000,
                 "prepared bank accounting differs")
        indexed_cases[_case_key(case)] = case
    _require(set(indexed_cases) == expected
             and len({case["task_id"] for case in cases}) == 9, "prepared pilot coverage differs")
    _require(type(worker_receipts) is list and len(worker_receipts) == 9,
             "exactly nine verified worker receipts are required")
    by_size = {n: [] for n in SIZES}
    used_tasks = set()
    for worker in worker_receipts:
        _require(type(worker) is dict and worker.get("schema") == "population-size-pilot-worker-v1"
                 and worker.get("status") == "VERIFIED_TECHNICAL_WORKER", "an unverified worker cannot support a quote")
        task = worker.get("task_id")
        _require(task not in used_tasks, "duplicate worker task")
        used_tasks.add(task)
        _integer(worker.get("input_validation_ns"), "shared input verification time")
        _integer(worker.get("peak_rss_bytes"), "worker peak memory", 1)
        records = worker.get("records")
        _require(type(records) is list and len(records) == 2, "each worker needs two boundary runs")
        populations = set()
        key = None
        for record in records:
            _require(type(record) is dict and record.get("verification_status") == "VERIFIED",
                     "an unverified run cannot support a quote")
            run = record.get("identity", {})
            candidate_key = _case_key(run)
            _require(candidate_key in indexed_cases and run.get("task_id") == task
                     and indexed_cases[candidate_key]["task_id"] == task,
                     "worker and prepared task identities differ")
            _require(key is None or key == candidate_key, "worker mixes different tasks")
            key = candidate_key
            mu = run.get("mu")
            _require(type(mu) is int and mu in (2, 25000) and mu not in populations
                     and run.get("total_evaluations") == 50000, "boundary run identity differs")
            populations.add(mu)
            timing = record.get("timing_ns", {})
            core = timing.get("core", {})
            total_ns = _integer(core.get("total"), "core total time")
            for component in ("verification", "observations", "serialization"):
                total_ns += _integer(timing.get(component), component + " time")
            # Each technical worker validates its shared inputs once for two runs.
            attributed_ns = total_ns + _ceil_div(worker["input_validation_ns"], 2)
            size = _integer(record.get("file", {}).get("bytes"), "compressed run bytes", 1)
            _integer(record.get("peak_rss_bytes"), "run peak memory", 1)
            by_size[key[0]].append({"task_id": task, "mu": mu, "measured_run_ns": total_ns,
                                   "attributed_run_ns": attributed_ns, "compressed_bytes": size,
                                   "peak_rss_bytes": max(record["peak_rss_bytes"], worker["peak_rss_bytes"])})
        _require(populations == {2, 25000}, "both boundary populations are required")
    _require(used_tasks == {case["task_id"] for case in cases}, "pilot task coverage is incomplete")
    bases = []
    for n in SIZES:
        group = [case for key, case in indexed_cases.items() if key[0] == n]
        rows = by_size[n]
        _require(len(rows) == 6, "each dimension needs six measured runs")
        bases.append({
            "n": n, "measured_runs": rows,
            "max_attributed_run_ns": max(row["attributed_run_ns"] for row in rows),
            "max_compressed_run_bytes": max(row["compressed_bytes"] for row in rows),
            "max_observed_peak_rss_bytes": max(row["peak_rss_bytes"] for row in rows),
            "max_certification_ns_per_task": max(case["timing_ns"]["certification"] for case in group),
            "max_prepared_bank_ns": max(sum(case["timing_ns"][name] for name in
                ("bank_preparation", "bank_verification", "bank_serialization")) for case in group),
            "max_prepared_bank_bytes": max(sum(case["files"][name]["bytes"] for name in
                ("bank", "bank_metadata")) for case in group),
            "max_problem_and_certificate_bytes": max(sum(case["files"][name]["bytes"] for name in
                ("problem", "certificate")) for case in group),
        })
    return bases


def _quote(bases, *, kind, runs_per_dimension, banks_per_dimension, racing_runs=None):
    rows = []
    for base in bases:
        run_ns = runs_per_dimension * base["max_attributed_run_ns"]
        bank_ns = banks_per_dimension * base["max_prepared_bank_ns"]
        certification_ns = 30 * base["max_certification_ns_per_task"]
        # Batching is a proposed execution layout, not measured workflow overhead.
        run_jobs = _ceil_div(runs_per_dimension, 30)
        bank_jobs = _ceil_div(banks_per_dimension, 30)
        exact_jobs = 3
        setup_allowance_minutes = 2 * (run_jobs + bank_jobs + exact_jobs)
        logs = runs_per_dimension * base["max_compressed_run_bytes"]
        inputs = banks_per_dimension * base["max_prepared_bank_bytes"]
        inputs += 30 * base["max_problem_and_certificate_bytes"]
        metadata_allowance = max(16 * MEBIBYTE, 4096 * runs_per_dimension)
        scaled_ns = run_ns + bank_ns + certification_ns
        rows.append({"n": base["n"], "physical_runs": runs_per_dimension,
            "logical_total_evaluations": runs_per_dimension * 50000,
            "distinct_initial_banks_upper": banks_per_dimension, "exactly_certified_tasks": 30,
            "physical_bank_preparation_evaluations_upper": banks_per_dimension * 25000,
            "independent_bank_verification_evaluations_upper": banks_per_dimension * 25000,
            "scaled_search_and_check_ns": run_ns, "scaled_bank_preparation_and_check_ns": bank_ns,
            "scaled_exact_certification_ns": certification_ns,
            "scaled_measured_minutes_ceil": _ceil_div(scaled_ns, NANOSECONDS_PER_MINUTE),
            "reserved_measured_minutes_ceil": _ceil_div(TIME_RESERVE_FACTOR * scaled_ns, NANOSECONDS_PER_MINUTE),
            "proposed_run_jobs": run_jobs, "proposed_bank_jobs": bank_jobs,
            "proposed_exact_jobs": exact_jobs, "unmeasured_setup_allowance_minutes": setup_allowance_minutes,
            "compressed_logs_scaled_bytes": logs, "prepared_inputs_scaled_bytes": inputs,
            "metadata_allowance_bytes": metadata_allowance,
            "reserved_compressed_bytes": _ceil_div(BYTE_RESERVE_NUMERATOR * (logs + inputs),
                                                   BYTE_RESERVE_DENOMINATOR) + metadata_allowance,
            "max_observed_pilot_peak_rss_bytes": base["max_observed_peak_rss_bytes"]})
    extra_allowances = {"tests_statistics_and_reporting_minutes": 20,
                        "irace_R_environment_minutes": 30 if kind == "tuning" else 0}
    minutes = sum(row["reserved_measured_minutes_ceil"] + row["unmeasured_setup_allowance_minutes"] for row in rows)
    minutes += sum(extra_allowances.values())
    result = {"kind": kind, "status": "PROPOSED_NOT_AUTHORIZED", "per_dimension": rows,
        "physical_runs_upper": 3 * runs_per_dimension, "logical_total_evaluations_upper": 3 * runs_per_dimension * 50000,
        "distinct_initial_banks_upper": 3 * banks_per_dimension,
        "runner_minutes_proposed_ceiling": minutes,
        "compressed_bytes_proposed_ceiling": sum(row["reserved_compressed_bytes"] for row in rows),
        "unmeasured_study_allowances": extra_allowances}
    if racing_runs is not None:
        result["design_proposal"] = {"racing_runs_per_dimension": racing_runs,
            "finalists_upper": 3, "common_finalist_tasks": 30, "common_finalist_repetitions": 10,
            "common_finalist_runs_per_dimension": 900, "common_finalist_banks_per_dimension": 300,
            "rule": "Only proposed counts; freeze an approved irace scenario before tuning"}
    return result


def build_quotes(prepared_registry, worker_receipts):
    """Produce measured bases and unapproved tuning/validation cost scenarios."""
    _require(os.environ.get("GITHUB_ACTIONS") == "true", "cost calculations run only in GitHub Actions")
    bases = _measurement_bases(prepared_registry, worker_receipts)
    return {"schema": "population-size-prospective-quotes-v1", "status": "MEASURED_PILOT_FORECASTS",
        "population_selected": False, "execution_authorized": False, "measurement_bases": bases,
        "assumptions": {
            "time_reserve_factor": TIME_RESERVE_FACTOR, "compressed_bytes_reserve_factor": "3/2",
            "basis": "Maximum measured boundary-run cost within each dimension, over three task types",
            "shared_input_validation": "One technical worker input check is attributed equally to its two runs",
            "all_30_tasks_certified_again": "Conservative quote; reused valid exact references may reduce the cost",
            "initial_banks": "One bank is prepared per task and seed and shared between compared profiles",
            "batching_proposal": "At most30 runs or30 banks per job;10 exact tasks per job; maximum4 parallel jobs",
            "setup_allowance": "Two minutes per proposed job, not measured provisioning or transfer time",
            "irace_environment_allowance": "Thirty unmeasured minutes for R/irace setup only in each tuning proposal",
            "limits": ["Boundary timings do not bound intermediate populations or unseen inputs",
                       "Network, R startup, and statistical analysis were not benchmarked by this pilot",
                       "Observed peak memory is a measurement, not a future memory guarantee",
                       "Proposed ceilings require a separate resource approval and execution-layout review",
                       "No automatic reduction of repetitions or selection of a favorable population"]},
        "validation": _quote(bases, kind="validation", runs_per_dimension=2700, banks_per_dimension=900),
        "tuning_options": [_quote(bases, kind="tuning", runs_per_dimension=races + 900,
                                  banks_per_dimension=races + 300, racing_runs=races)
                           for races in (300, 600, 1200)]}
