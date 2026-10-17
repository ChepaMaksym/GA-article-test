"""Phase-gated CI entry points; no scientific work at import time.

The implemented scientific execution stage is a resource pilot, not the main
series. Preparation can freeze the planned main banks, but cannot release GA
search on them. A main matrix and statistical release require a later contract.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
import gzip
import io
from pathlib import Path
import unittest

from . import contract as c

REGISTRY = "studies/knapsack_parameters/evidence/run-37637475385/registry.json"
DATA_MANIFEST = "studies/knapsack_parameters/inputs/data_manifest.json"


def source_task(task):
    """Load immutable bytes and an external case; never pass the case to search."""
    registration = c.read_json(c.MODULE / "registration.json")
    for name in (REGISTRY, DATA_MANIFEST):
        c.require(c.identity(c.ROOT / name)["sha256"] == registration["protected_sha256"][name],
                  "Changed historical registry or data manifest")
    registry = c.read_json(c.ROOT / REGISTRY)
    c.require(len(registry["cases"]) == 30 and registry["case_order"].count(task) == 1,
              "Unknown or duplicated task")
    entries = [row for row in registry["cases"] if row["instance_id"] == task]
    c.require(len(entries) == 1 and entries[0]["technically_complete"] is True and
              entries[0]["scientific_proofs_verified"] is True, "Unverified historical task")
    case = entries[0]["payload"]
    relative = "studies/knapsack_parameters/inputs/source/" + case["source_identity"]["source_path"]
    manifest = c.read_json(c.ROOT / DATA_MANIFEST)
    source_rows = [row for row in manifest["source_files"]
                   if row["source_path"] == case["source_identity"]["source_path"]]
    c.require(len(source_rows) == 1 and source_rows[0]["status"] == "PASS_SOURCE", "Missing source identity")
    expected = {field: source_rows[0][field] for field in ("bytes", "sha256")}
    c.require(c.identity(c.ROOT / relative) == expected, "Source byte identity mismatch")
    raw = [int(value) for value in (c.ROOT / relative).read_text(encoding="utf-8").split()]
    n, capacity = raw[:2]
    c.require(n == 100 and len(raw) == 2 + 2*n and capacity > 0 and
              all(value > 0 for value in raw[2:]), "Malformed KPLIB data")
    problem = {"n": n, "capacity": capacity, "profits": raw[2::2], "weights": raw[3::2]}
    c.require(capacity == case["capacity"] and n == case["n"] and
              case["exact"]["confirmed_optimum"] > 0, "Case and input disagree")
    return problem, case, {"path": relative, **expected}


def independent_score(problem, mask):
    c.require(type(mask) is str and len(mask) == problem["n"] and set(mask) <= {"0", "1"},
              "Invalid initial mask")
    weight = sum(problem["weights"][i] for i in range(problem["n"]) if mask[i] == "1")
    profit = sum(problem["profits"][i] for i in range(problem["n"]) if mask[i] == "1")
    return {"weight": weight, "profit": profit, "feasible": weight <= problem["capacity"]}


def planned_conditions(scope):
    registration = c.read_json(c.MODULE / "registration.json")
    registry = c.read_json(c.ROOT / REGISTRY)
    if scope == "pilot":
        config = registration["pilot"]
        return [(task, start, seed) for task in config["tasks"]
                for start in config["starts"] for seed in config["search_seeds"]]
    c.require(scope == "main", "Unknown preparation scope")
    admitted = {row["instance_id"] for row in registry["cases"]
                if row["status"] in ("ADMITTED_STRICT_LOCAL", "ADMITTED_PLATEAU_LOCAL")}
    c.require(len(admitted) == 14, "Historical admission set changed")
    config = registration["main"]
    return [(task, start, seed) for task in registry["case_order"]
            for start in ("cloned", "bank") if start == "bank" or task in admitted
            for seed in range(config["search_seed_first"], config["search_seed_last"] + 1)]


def initial_bank(problem, case, task_index, start, seed, preparation_seed):
    import numpy as np
    c.require(start in ("cloned", "bank"), "Unknown start")
    start_index = ("cloned", "bank").index(start)
    rng = np.random.Generator(np.random.PCG64(np.random.SeedSequence(
        [preparation_seed, seed, task_index, start_index, 0])))
    before = deepcopy(rng.bit_generator.state)
    masks = ([case["certificate"]["center"]["mask"]] * 30 if start == "cloned" else
             ["0" * problem["n"]] + ["".join("1" if bit else "0"
                for bit in rng.random(problem["n"]) < 0.5) for _ in range(29)])
    # Deduplication is confined to preparation. Search never uses this cache.
    from studies.adaptive_parameters.mutation_only.engine import evaluate
    known = {mask: evaluate(problem, mask) for mask in sorted(set(masks))}
    scores = [known[mask] for mask in masks]
    c.require(scores == [independent_score(problem, mask) for mask in masks], "Independent initial mismatch")
    return {"initial_masks": masks, "initial_scores": scores,
        "initialization_before": before, "initialization_after": deepcopy(rng.bit_generator.state),
        "logical_initial_positions": 30, "physical_preparation_evaluations": len(known),
        "independent_preparation_checks": 30}


def prepare(output, scope):
    provenance = c.check_preflight(output, "prepare")
    c.validated_tests()
    registration = c.read_json(c.MODULE / "registration.json")
    registry = c.read_json(c.ROOT / REGISTRY)
    prep_seed = registration[scope]["preparation_seed"]
    entries, physical = [], 0
    for task, start, seed in planned_conditions(scope):
        task_index = registry["case_order"].index(task)
        problem, case, source = source_task(task)
        bank = {**provenance, "schema": "mutation-population-bank-v1", "task": task,
            "task_index": task_index, "start": start, "start_index": ("cloned", "bank").index(start),
            "search_seed": seed, "preparation_seed": prep_seed, "problem": problem,
            "source_identity": source, **initial_bank(problem, case, task_index, start, seed, prep_seed)}
        physical += bank["physical_preparation_evaluations"]
        name = f"banks/{task}-{start}-{seed}.json"
        c.write_json(output / name, bank)
        entries.append({"task": task, "start": start, "seed": seed, "path": name,
                        **c.identity(output / name)})
    c.write_json(output / "bank_registry.json", {**provenance, "schema": "mutation-population-banks-v1",
        "scope": scope, "banks": entries, "initial_conditions": len(entries),
        "physical_preparation_evaluations": physical,
        "independent_preparation_checks": 30 * len(entries), "scientific_search_calls": 0})
    c.write_manifest(output)


def load_banks(scope):
    root = c.MODULE / "inputs" / scope
    c.verify_manifest(root)
    registry = c.read_json(root / "bank_registry.json")
    frozen = c.read_json(c.MODULE / "frozen_banks.json")
    c.require(frozen.get("protocol_id") == c.PROTOCOL and frozen.get("frozen") is True and
              frozen.get("scope") == scope and c.identity(root / "bank_registry.json") ==
              frozen.get("registry_identity"), "Beginnings have not been frozen")
    c.require(registry.get("protocol_id") == c.PROTOCOL and registry.get("scope") == scope and
              registry.get("source_manifest") == c.source_manifest(), "Stale or mixed preparation")
    run = c.api(f"/actions/runs/{registry['run_id']}/attempts/{registry['run_attempt']}")
    c.require(run.get("head_sha") == registry.get("implementation_sha") and
              run.get("conclusion") == "success" and run.get("path") == c.WORKFLOW and
              run.get("head_branch") == c.BRANCH, "Unsuccessful or foreign preparation")
    artifact = c.api(f"/actions/artifacts/{frozen['artifact_id']}")
    c.require(artifact.get("workflow_run", {}).get("id") == registry["run_id"] and
              artifact.get("digest") == "sha256:" + frozen.get("zip_sha256", "") and
              not artifact.get("expired"), "Preparation artifact identity mismatch")
    expected = set(planned_conditions(scope))
    seen, result = set(), []
    historical = c.read_json(c.ROOT / REGISTRY)
    for row in registry["banks"]:
        key = (row["task"], row["start"], row["seed"])
        c.require(key in expected - seen, "Duplicate or unknown initial condition")
        seen.add(key)
        c.require(row["path"] == f"banks/{key[0]}-{key[1]}-{key[2]}.json", "Unsafe bank path")
        path = root / row["path"]
        c.require(c.identity(path) == {"bytes": row["bytes"], "sha256": row["sha256"]}, "Corrupted bank")
        bank = c.read_json(path)
        problem, case, source = source_task(key[0])
        ti, si = historical["case_order"].index(key[0]), ("cloned", "bank").index(key[1])
        prep_seed = c.read_json(c.MODULE / "registration.json")[scope]["preparation_seed"]
        replay = initial_bank(problem, case, ti, key[1], key[2], prep_seed)
        c.require(bank.get("problem") == problem and bank.get("source_identity") == source and
                  bank.get("task") == key[0] and bank.get("start") == key[1] and
                  bank.get("search_seed") == key[2] and bank.get("preparation_seed") == prep_seed and
                  bank.get("task_index") == ti and bank.get("start_index") == si and
                  all(bank.get(field) == registry.get(field) for field in
                      ("protocol_id", "implementation_sha", "run_id", "run_attempt", "source_manifest")) and
                  all(bank.get(field) == value for field, value in replay.items()), "Bank replay mismatch")
        result.append(bank)
    c.require(seen == expected and registry.get("initial_conditions") == len(expected) and
              registry.get("scientific_search_calls") == 0, "Incomplete preparation")
    return result


def run_tests(output):
    provenance = c.check_preflight(output, "tests")
    # No discovery outside this new module and the frozen mutation implementation.
    suite = unittest.TestSuite(unittest.defaultTestLoader.loadTestsFromName(name) for name in (
        "studies.adaptive_parameters.mutation_only.test_mutation_only",
        "studies.knapsack_parameters.mutation_population.tests.test_core",
        "studies.knapsack_parameters.mutation_population.tests.test_contract"))
    stream = io.StringIO()
    result = unittest.TextTestRunner(stream=stream, verbosity=2).run(suite)
    report = stream.getvalue()
    print(report)
    (output / "tests.txt").write_text(report, encoding="utf-8")
    c.write_json(output / "tests_receipt.json", {**provenance,
        "phase": "tests", "tests_run": result.testsRun, "tests_passed": result.wasSuccessful(),
        "failures": len(result.failures), "errors": len(result.errors),
        "scientific_runs": 0, "pilot_performed": False, "main_performed": False})
    c.write_manifest(output)
    c.require(result.wasSuccessful(), "CI tests failed")


def pilot(output):
    provenance = c.check_preflight(output, "pilot")
    c.validated_tests()
    from .search import run_profile, verify_paired_first_generation
    from .observations import summarize_log, certify_n2
    logs, results, pairs, diagnostic_requests = {}, [], [], {}
    banks = load_banks("pilot")
    for bank in banks:
        task, start, seed = bank["task"], bank["start"], bank["search_seed"]
        # Oracle metadata is deliberately not loaded in this loop until search returns.
        paired = {}
        for method in ("fixed", "adaptive_mutation"):
            run = run_profile(bank["problem"], bank["initial_masks"], bank["initial_scores"],
                              method, seed, bank["task_index"], bank["start_index"], budget=5000)
            log, verification = run["log"], run["verification"]
            c.require(log["budget"] == log["summary"]["physical_evaluations"] == 5000,
                      "Wrong scientific search budget")
            paired[method] = log
            _, case, _ = source_task(task)
            optimum = case["exact"]["confirmed_optimum"]
            observed = summarize_log(log, optimum)
            name = f"{task}-{start}-{seed}-{method}"
            journal = output / "journals" / (name + ".json.gz")
            journal.parent.mkdir(parents=True, exist_ok=True)
            journal.write_bytes(gzip.compress(c.canonical({**provenance, "task": task, "start": start,
                "seed": seed, "log": log, "verification": verification, "observations": observed}), mtime=0))
            c.require(journal.stat().st_size <= 64 * 1024 * 1024, "Journal resource limit exceeded")
            logs[(task, start, method)] = log
            results.append({"task": task, "start": start, "method": method, "seed": seed,
                "summary": log["summary"], "observations": observed, "external_optimum": optimum,
                "center_type": case["status"], "verification": verification,
                "journal": journal.relative_to(output).as_posix(), "journal_identity": c.identity(journal)})
            if task == "UC-s000":
                for mask in {observed["initial_record"]["mask"], observed["final_record"]["mask"]}:
                    key = (task, mask)
                    if mask is not None:
                        diagnostic_requests[key] = (bank["problem"], optimum)
        pairs.append({"task": task, "start": start, "seed": seed,
                      **verify_paired_first_generation(paired["fixed"], paired["adaptive_mutation"])})
    expected = {(task, start, seed, method) for task, start, seed in planned_conditions("pilot")
                for method in ("fixed", "adaptive_mutation")}
    actual = [(r["task"], r["start"], r["seed"], r["method"]) for r in results]
    c.require(len(actual) == len(set(actual)) == 16 and set(actual) == expected, "Incomplete or duplicate pilot")
    diagnostics = []
    # Only now, after every search has returned, enumerate any diagnostic neighbor.
    for index, ((task, mask), (problem, optimum)) in enumerate(sorted(diagnostic_requests.items())):
        certificate = certify_n2(problem, mask, optimum)
        path = output / "diagnostics" / f"{task}-{index}.json.gz"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(gzip.compress(c.canonical(certificate), mtime=0))
        diagnostics.append({"task": task, "mask": mask, "path": path.relative_to(output).as_posix(),
            "locality": certificate["locality"], "global_status": certificate["global_status"],
            "independent_evaluations": certificate["independent_evaluations"], **c.identity(path)})
    summary = {**provenance, "status": "COMPLETE_TECHNICAL_PILOT", "scope": "pilot",
        "runs": 16, "new_calls": 80000, "results": results, "paired_checks": pairs,
        "diagnostics": diagnostics, "diagnostic_evaluations": sum(r["independent_evaluations"] for r in diagnostics),
        "cost_accounting": {
            "new_search_evaluations": sum(row["summary"]["physical_evaluations"] for row in results),
            "kernel_known_initial_score_checks": sum(row["summary"]["known_score_validation_evaluations"] for row in results),
            "independent_operator_replay_score_checks": sum(row["verification"]["independent_score_checks"] for row in results),
            "independent_observer_score_checks": sum(row["observations"]["accounting"]["independent_candidate_and_initial_scores"] for row in results),
            "bank_validation_evaluations": sum(bank["physical_preparation_evaluations"] for bank in banks),
            "independent_bank_validation_checks": sum(bank["independent_preparation_checks"] for bank in banks),
            "previous_separate_initial_preparation_evaluations": sum(bank["physical_preparation_evaluations"] for bank in banks),
            "previous_separate_independent_preparation_checks": sum(bank["independent_preparation_checks"] for bank in banks),
            "n2_diagnostic_evaluations": sum(row["independent_evaluations"] for row in diagnostics)},
        "superiority_tested": False, "bootstrap_performed": False,
        "adaptive_population_implemented": False}
    from .reporting import build_report
    build_report(output, summary, logs)
    trace_names = ("candidate_trace", "record_trace", "population_trace", "full_generation_metrics",
                   "mutation_trace", "checkpoints", "snapshots", "strict_success_calls")
    for row in results:
        for field in trace_names:
            row["observations"].pop(field, None)
    c.write_json(output / "pilot_summary.json", summary)
    c.write_manifest(output)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=("preflight", "tests", "prepare", "pilot"))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--scope", choices=("pilot", "main"), default="pilot")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    if args.phase == "preflight":
        c.preflight(args.output)
    elif args.phase == "tests":
        run_tests(args.output)
    elif args.phase == "prepare":
        prepare(args.output, args.scope)
    else:
        c.require(args.scope == "pilot", "Main search is not activated or implemented by this pilot entry point")
        pilot(args.output)


if __name__ == "__main__":
    main()
