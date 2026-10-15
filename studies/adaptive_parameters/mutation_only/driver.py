"""CI entry points. No work is executed by importing the module."""
from __future__ import annotations

import argparse
import copy
import gzip
import io
from pathlib import Path
import unittest

from . import contract as c


def require_phase(expected):
    c.require(c.phase(c.os.environ.get("COMMIT_MESSAGE", "")) == expected, "Wrong execution phase")


def validated_tests():
    from .provenance import fetch_artifact
    transport = c.read_json(c.MODULE / "validated_tests.json")
    run_id, attempt = transport["run_id"], transport["run_attempt"]
    members, run = fetch_artifact(transport, "tests")
    receipt = c.json.loads(members["tests_receipt.json"])
    c.require(receipt.get("tests_passed") is True and receipt.get("tests_run", 0) > 0 and
              receipt.get("phase") == "tests" and receipt.get("protocol_id") == c.PROTOCOL and
              receipt.get("run_id") == run_id and receipt.get("run_attempt") == attempt and
              receipt.get("implementation_sha") == run["head_sha"] and
              receipt.get("source_manifest") == c.source_manifest(), "Missing or stale green checks")
    return receipt


def run_tests(output):
    require_phase("tests")
    provenance = c.authenticate(runtime=True)
    suite = unittest.TestSuite(unittest.defaultTestLoader.loadTestsFromName(name) for name in (
        "studies.adaptive_parameters.mutation_only.test_mutation_only",
        "studies.adaptive_parameters.mutation_only.test_contract",
        "studies.adaptive_parameters.mutation_only.test_provenance"))
    stream = io.StringIO()
    result = unittest.TextTestRunner(stream=stream, verbosity=2).run(suite)
    report = stream.getvalue()
    print(report)
    (output / "tests.txt").write_text(report, encoding="utf-8")
    c.write_json(output / "tests_receipt.json", {**provenance,
        "phase": "tests", "tests_run": result.testsRun, "tests_passed": result.wasSuccessful(),
        "failures": len(result.failures), "errors": len(result.errors),
        "scientific_pilot_runs": 0})
    c.write_manifest(output)
    c.require(result.wasSuccessful(), "Independent CI checks failed")


def source_task(task):
    registration = c.read_json(c.MODULE / "registration.json")
    suffix = {"UC-s000": "00Uncorrelated/n00100/R01000/s000.kp",
              "WC-s001": "01WeaklyCorrelated/n00100/R01000/s001.kp",
              "SC-s005": "02StronglyCorrelated/n00100/R01000/s005.kp",
              "SC-s000": "02StronglyCorrelated/n00100/R01000/s000.kp"}[task]
    relative = "studies/knapsack_parameters/inputs/source/" + suffix
    c.require(c.identity(c.ROOT / relative)["sha256"] == registration["input_sha256"][relative], "Wrong data")
    raw = [int(v) for v in (c.ROOT / relative).read_text(encoding="utf-8").split()]
    n, capacity = raw[:2]
    c.require(n == 100 and len(raw) == 2 + 2*n and capacity > 0 and
              all(v > 0 for v in raw[2:]), "Malformed source data")
    problem = {"n": n, "capacity": capacity, "profits": raw[2::2], "weights": raw[3::2]}
    case = c.read_json(c.ROOT / f"studies/knapsack_parameters/evidence/run-37637475385/cases/{task}/case.json")
    return problem, case, relative


def initial_independent_score(problem, mask):
    c.require(len(mask) == problem["n"] and set(mask) <= {"0", "1"}, "Bad initial mask")
    weight = sum(problem["weights"][i] for i in range(problem["n"]) if mask[i] == "1")
    profit = sum(problem["profits"][i] for i in range(problem["n"]) if mask[i] == "1")
    return {"weight": weight, "profit": profit, "feasible": weight <= problem["capacity"]}


def prepare(output):
    require_phase("prepare")
    provenance = c.authenticate(runtime=True)
    validated_tests()
    from .engine import evaluate, make_rngs
    registration = c.read_json(c.MODULE / "registration.json")
    banks = []
    for ti, task in enumerate(registration["tasks"]):
        problem, case, source = source_task(task)
        for si, start in enumerate(registration["starts"]):
            rngs = make_rngs(76000, ti, si)
            before = copy.deepcopy(rngs["initialization"].bit_generator.state)
            if start == "cloned":
                masks = [case["certificate"]["center"]["mask"]] * 30
            else:
                masks = ["0" * 100] + ["".join("1" if v < 0.5 else "0"
                    for v in rngs["initialization"].random(100)) for _ in range(29)]
            cache = {mask: evaluate(problem, mask) for mask in sorted(set(masks))}
            scores = [cache[mask] for mask in masks]
            c.require(scores == [initial_independent_score(problem, mask) for mask in masks], "Initial score mismatch")
            bank = {"schema": "mutation-only-bank-v1", "protocol_id": c.PROTOCOL,
                "task": task, "task_index": ti, "start": start, "start_index": si,
                "preparation_seed": 76000, "problem": problem, "initial_masks": masks,
                "initial_scores": scores, "initialization_before": before,
                "initialization_after": copy.deepcopy(rngs["initialization"].bit_generator.state),
                "logical_initial_positions": 30, "physical_preparation_evaluations": len(cache),
                "independent_preparation_checks": 30, "source_path": source,
                "source_identity": c.identity(c.ROOT / source), "provenance": provenance}
            name = f"banks/{task}-{start}.json"
            c.write_json(output / name, bank)
            banks.append({"task": task, "start": start, "path": name, **c.identity(output / name)})
    c.require(len(banks) == 8, "Incomplete preparation")
    c.write_json(output / "bank_registry.json", {**provenance, "schema": "mutation-only-registry-v1",
        "banks": banks, "initial_conditions": 8, "pilot_search_seed": 76001,
        "physical_preparation_evaluations": sum(c.read_json(output / b["path"])["physical_preparation_evaluations"] for b in banks),
        "independent_preparation_checks": 240, "scientific_search_calls": 0})
    c.write_manifest(output)


def load_banks():
    from .provenance import fetch_artifact
    root = c.MODULE / "inputs"
    c.verify_manifest(root)
    registry = c.read_json(root / "bank_registry.json")
    c.require(registry.get("protocol_id") == c.PROTOCOL and
              registry.get("source_manifest") == c.source_manifest() and
              registry.get("schema") == "mutation-only-registry-v1" and
              registry.get("initial_conditions") == 8 and registry.get("pilot_search_seed") == 76001,
              "Wrong preparation identity")
    transport = c.read_json(c.MODULE / "prepared_inputs.json")
    original, preparation = fetch_artifact(transport, "prepare")
    c.require(registry["implementation_sha"] == preparation["head_sha"] and
              registry["run_id"] == preparation["id"] and registry["run_attempt"] == preparation["run_attempt"],
              "Preparation registry provenance mismatch")
    actual_files = {p.relative_to(root).as_posix(): p.read_bytes() for p in root.rglob("*") if p.is_file()}
    c.require(actual_files == original, "Local banks differ from exact preparation artifact")
    registration = c.read_json(c.MODULE / "registration.json")
    expected = {(task, start) for task in registration["tasks"] for start in registration["starts"]}
    seen, result = set(), []
    for row in registry["banks"]:
        task, start = row["task"], row["start"]
        c.require((task, start) in expected - seen and row["path"] == f"banks/{task}-{start}.json", "Duplicate or unsafe bank")
        seen.add((task, start))
        path = root / row["path"]
        c.require(c.identity(path) == {"sha256": row["sha256"], "bytes": row["bytes"]}, "Corrupted bank")
        bank = c.read_json(path)
        ti, si = registration["tasks"].index(task), registration["starts"].index(start)
        problem, case, source = source_task(task)
        c.require(bank.get("protocol_id") == c.PROTOCOL and bank.get("schema") == "mutation-only-bank-v1" and
                  bank.get("task") == task and bank.get("start") == start and bank.get("preparation_seed") == 76000 and
                  bank.get("source_path") == source and
                  all(bank["provenance"].get(k) == registry.get(k) for k in
                      ("protocol_id", "implementation_sha", "run_id", "run_attempt", "source_manifest")) and
                  bank["problem"] == problem and bank["task_index"] == ti and bank["start_index"] == si and
                  bank["source_identity"] == c.identity(c.ROOT / source) and
                  len(bank["initial_masks"]) == len(bank["initial_scores"]) == 30, "Wrong bank identity")
        import numpy as np
        rng = np.random.Generator(np.random.PCG64(np.random.SeedSequence([76000, ti, si, 0])))
        before = copy.deepcopy(rng.bit_generator.state)
        replay = ([case["certificate"]["center"]["mask"]] * 30 if start == "cloned" else
                  ["0" * 100] + ["".join("1" if v < 0.5 else "0" for v in rng.random(100)) for _ in range(29)])
        c.require(bank["initial_masks"] == replay and bank["initial_scores"] ==
                  [initial_independent_score(problem, m) for m in replay], "Initial reconstruction mismatch")
        c.require(bank["initialization_before"] == before and bank["initialization_after"] == rng.bit_generator.state and
                  bank["logical_initial_positions"] == bank["independent_preparation_checks"] == 30 and
                  bank["physical_preparation_evaluations"] == len(set(replay)), "Initial accounting or RNG mismatch")
        result.append(bank)
    c.require(seen == expected, "Missing initial condition")
    c.require(registry["physical_preparation_evaluations"] == sum(b["physical_preparation_evaluations"] for b in result) and
              registry["independent_preparation_checks"] == 240 and registry["scientific_search_calls"] == 0,
              "Initial registry totals mismatch")
    return result


def pilot(output):
    require_phase("pilot")
    provenance = c.authenticate(runtime=True)
    validated_tests()
    from .engine import make_rngs, run_search
    from .verifier import verify_log
    from .provenance import validate_log_identity, validate_complete_results
    results = []
    for bank in load_banks():
        first = None
        for method in ("fixed", "adaptive_mutation"):
            log = run_search(bank["problem"], bank["initial_masks"], bank["initial_scores"], method,
                make_rngs(76001, bank["task_index"], bank["start_index"]), budget=5000)
            validate_log_identity(log, bank, method)
            verification = verify_log(log)
            c.require(verification["verification_status"] == "VERIFIED", "Log replay failed")
            candidates = [row for row in log["candidates"] if row["generation"] == 1]
            if first is None:
                first = candidates
            else:
                c.require(first == candidates, "First paired generation differs")
            name = f"{bank['task']}-{bank['start']}-{method}"
            journal = output / "journals" / (name + ".json.gz")
            journal.parent.mkdir(parents=True, exist_ok=True)
            raw = c.canonical({"provenance": provenance, "task": bank["task"], "start": bank["start"],
                               "seed": 76001, "log": log, "verification": verification})
            journal.write_bytes(gzip.compress(raw, mtime=0))
            c.require(journal.stat().st_size <= 64*1024*1024, "Oversized journal")
            initial = max(s["profit"] for s in bank["initial_scores"] if s["feasible"])
            exits = [r["call"] for r in log["candidates"] if r["feasible"] and r["profit"] > initial]
            # External oracle is read only after the search; never supplied to the kernel.
            _, case, _ = source_task(bank["task"])
            optimum = case["exact"]["confirmed_optimum"]
            c.require(log["summary"]["best_profit"] <= optimum, "Record exceeds exact external optimum")
            results.append({"task": bank["task"], "start": bank["start"], "method": method,
                "seed": 76001, "summary": log["summary"], "verification": verification,
                "initial_record": initial, "first_improvement_call": min(exits) if exits else None,
                "calls_to_improvement_capped": min(exits) if exits else 5000,
                "external_optimum": optimum, "center_type": case["status"],
                "journal": journal.relative_to(output).as_posix(), "journal_identity": c.identity(journal)})
    validate_complete_results(results)
    c.write_json(output / "pilot_summary.json", {**provenance, "status": "COMPLETE_TECHNICAL_PILOT",
        "runs": 16, "new_calls": 80000, "results": results, "technical_seed": 76001,
        "superiority_tested": False, "bootstrap_performed": False})
    from .reporting import build_report
    build_report(output)
    c.write_manifest(output)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=("preflight", "tests", "prepare", "pilot"))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    if args.phase == "preflight":
        c.preflight(args.output)
    else:
        # Work must have a same-SHA preflight from this very job, not a copied permit.
        previous = c.read_json(args.output / "preflight.json")
        c.require(previous["implementation_sha"] == c.os.environ.get("GITHUB_SHA") and
                  previous["run_id"] == int(c.os.environ["GITHUB_RUN_ID"]) and
                  previous["run_attempt"] == int(c.os.environ.get("GITHUB_RUN_ATTEMPT", "1")) and
                  previous["phase"] == args.phase, "No matching phase preflight")
        {"tests": run_tests, "prepare": prepare, "pilot": pilot}[args.phase](args.output)


if __name__ == "__main__":
    main()
