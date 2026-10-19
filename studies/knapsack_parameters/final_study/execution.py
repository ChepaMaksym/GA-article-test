"""Ten one-profile resource probes; no held-out or full-series search entrypoint."""
from __future__ import annotations

import argparse
from copy import deepcopy
import gzip
import hashlib
import io
import json
import os
from pathlib import Path
import time
import unittest

from . import authority as a

BUDGET = 5000
SEED = 86001
_PROVENANCE = ("protocol_id", "registration_sha", "implementation_sha", "source_manifest", "run_id", "run_attempt")
_NONAPPLICABLE_HISTORICAL_CONTEXT_TESTS = {
    "studies.knapsack_parameters.adaptation_analysis.tests.test_authority.AuthorityTests.test_frozen_sources_and_runtime":
        "Historical adaptation authorization rejects paths outside its own registered module; the new final-study gate checks this execution context.",
    "studies.knapsack_parameters.adaptation_analysis.tests.test_pilot_authority.PilotAuthorityTests.test_exact_registered_identity_and_frozen_environment":
        "Historical pilot authorization delegates to its original module-only gate; it does not authorize the new final-study workflow.",
    "studies.knapsack_parameters.bntga_selection.tests.test_authority.AuthorityTests.test_frozen_contract_and_runtime":
        "Historical archive authorization rejects later modules by design; its unchanged rejection and protected bytes are checked by the new gate.",
}


def _same_provenance(found, expected):
    a.require(all(found.get(name) == expected[name] for name in _PROVENANCE), "Mixed execution provenance")


def _json_hash(value):
    digest = hashlib.sha256()
    encoder = json.JSONEncoder(sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)
    for piece in encoder.iterencode(value):
        digest.update(piece.encode("utf-8"))
    return digest.hexdigest()


def _progress(output, index):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    temporary = output.parent / ("." + output.name + "-progress.partial")
    a.write_json(temporary, index)
    os.replace(temporary, output / "worker_index.json")
    a.write_manifest(output)


class _CappedWriter:
    def __init__(self, stream, maximum):
        self.stream, self.maximum, self.written = stream, maximum, 0

    def write(self, data):
        a.require(self.written + len(data) <= self.maximum, "Compressed evidence exceeds job limit")
        count = self.stream.write(data)
        self.written += count
        return count

    def flush(self):
        return self.stream.flush()

    def tell(self):
        return self.stream.tell()


def write_raw_atomic(path, packet):
    """Persist raw data before any independent replay; incomplete writes stay outside artifacts."""
    path = Path(path)
    a.require(not path.exists(), "Refuse raw journal overwrite")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.parent.parent / ("." + path.name + ".partial")
    a.require(not temporary.exists(), "Refuse partial journal overwrite")
    with temporary.open("xb") as stream:
        bounded = _CappedWriter(stream, a.MAX_BYTES)
        with gzip.GzipFile(filename="", mode="wb", fileobj=bounded, mtime=0) as compressed:
            with io.TextIOWrapper(compressed, encoding="utf-8", newline="\n") as text:
                json.dump(packet, text, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)
                text.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)


def run_raw(bank, method):
    """Only a problem, known beginning, and search RNGs enter a raw search kernel."""
    a.require(method in a.METHODS, "Unknown or blocked profile")
    from studies.adaptive_parameters.mutation_only import engine
    rngs = engine.make_rngs(SEED, bank["task_index"], bank["start_index"])
    problem, masks, scores = bank["problem"], bank["initial_masks"], bank["initial_scores"]
    if method in ("classical", "adaptive_mutation"):
        return engine.run_search(problem, masks, scores, "fixed" if method == "classical" else method, rngs, BUDGET)
    if method == "adaptive_crossover":
        from studies.knapsack_parameters.adaptation_analysis.crossover import run_search
        return run_search(problem, masks, scores, method, rngs, BUDGET)
    from .fast_archive import run_archive_search
    return run_archive_search(problem, masks, scores, method == "balanced_gap", rngs, BUDGET)


def verify_raw(method, log):
    from studies.knapsack_parameters.adaptation_analysis.comparison import verify_profile_log
    result = verify_profile_log(method, log)
    a.require(result.get("verification_status") == "VERIFIED" and result.get("summary") == log.get("summary") and
              result.get("independent_score_checks") == BUDGET + 30,
              "Independent raw replay or counters differ")
    a.require(log.get("budget") == BUDGET and
              log["summary"].get("new_calls") == log["summary"].get("physical_evaluations") == BUDGET and
              log["summary"].get("known_score_validation_evaluations") == 30, "Wrong probe evaluation budget")
    return result


def _verify_seed_binding(bank, log):
    import numpy as np
    channels = ("initialization", "selection", "branch", "crossover", "mutation", "ties")
    expected = {name: deepcopy(np.random.PCG64(np.random.SeedSequence(
        [SEED, bank["task_index"], bank["start_index"], channel])).state)
        for channel, name in enumerate(channels)}
    a.require(log.get("rng_initial") == expected, "Raw generator states differ from the registered seed")


def _archive_sizes(log):
    if "initial_archive" not in log:
        return {"maximum_archive_size": None, "final_archive_size": None}
    sizes = [len(log["initial_archive"])]
    for event in log["generations"]:
        sizes += [len(event[name]) for name in ("archive_before", "archive_after")]
    return {"maximum_archive_size": max(sizes), "final_archive_size": len(log["generations"][-1]["archive_after"])}


def selected_regression_suite():
    """Keep all scientific checks; only old execution-context checks are inapplicable.

    Those checks would correctly reject this later protocol. Their historical
    code is unchanged, and a new test checks that they still reject it.
    """
    discovered = unittest.TestSuite()
    for relative in ("studies/knapsack_parameters/final_study/tests",
                     "studies/knapsack_parameters/adaptation_analysis/tests",
                     "studies/knapsack_parameters/bntga_selection/tests"):
        discovered.addTests(unittest.defaultTestLoader.discover(str(a.ROOT / relative), pattern="test_*.py",
                                                               top_level_dir=str(a.ROOT)))
    def flatten(node):
        for child in node:
            if isinstance(child, unittest.TestSuite):
                yield from flatten(child)
            else:
                yield child
    tests = list(flatten(discovered))
    identities = [test.id() for test in tests]
    a.require(len(identities) == len(set(identities)), "Duplicate discovered regression test identity")
    a.require(set(_NONAPPLICABLE_HISTORICAL_CONTEXT_TESTS) <= set(identities),
              "Historical execution-context selection changed")
    selected = [test for test in tests if test.id() not in _NONAPPLICABLE_HISTORICAL_CONTEXT_TESTS]
    selection = {"schema": "ga-final-regression-selection-v1", "discovered_count": len(tests),
                 "selected_count": len(selected), "discovered_ids": identities,
                 "selected_ids": [test.id() for test in selected],
                 "excluded": [{"test_id": name, "reason": reason}
                              for name, reason in sorted(_NONAPPLICABLE_HISTORICAL_CONTEXT_TESTS.items())],
                 "scientific_or_operator_checks_excluded": False,
                 "historical_authorization_code_modified": False}
    return unittest.TestSuite(selected), selection


def run_tests(output, permit):
    provenance = a.check_permit(permit, "tests")
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    suite, selection = selected_regression_suite()
    with (output / "tests.txt").open("w", encoding="utf-8") as stream:
        result = unittest.TextTestRunner(stream=stream, verbosity=2).run(suite)
    from .inputs import probe_binding
    receipt = {**provenance, "tests_run": result.testsRun, "tests_passed": result.wasSuccessful(),
               "failures": len(result.failures), "errors": len(result.errors), "skipped": len(result.skipped),
               "scientific_KPLIB_search_performed": False, "scientific_statistics_performed": False,
               "lambda_search_performed": False,
               "input_binding": probe_binding(),
               "test_selection": selection,
               "scope": "Frozen historical checks, synthetic equivalence fixtures and execution guards only"}
    a.write_json(output / "tests_receipt.json", receipt)
    a.write_manifest(output)
    a.verify_manifest(output)
    print((output / "tests.txt").read_text(encoding="utf-8"))
    a.require(result.wasSuccessful() and result.testsRun == selection["selected_count"] > 0 and
              not result.skipped, "All selected unit checks must pass")
    return receipt


def worker(output, task, start, method, permit):
    provenance = a.check_permit(permit, "worker")
    a.require((task, start) in a.CONDITIONS and method in a.METHODS, "Unregistered resource probe")
    a.validated_tests()
    from .inputs import load_probe_bank, validate_probe_freeze
    validate_probe_freeze(provenance)
    bank = load_probe_bank(task, start)
    output = Path(output)
    a.require(not (output / "worker_index.json").exists(), "Refuse worker overwrite")
    index = {**provenance, "schema": "ga-final-probe-worker-v1", "status": "SEARCH_NOT_STARTED",
             "task": task, "start": start, "seed": SEED, "method": method,
             "bank_sha256": _json_hash(bank), "source_identity": bank["source_identity"],
             "new_evaluations_requested": BUDGET, "raw": None, "verification": None,
             "timing_seconds": {}, "errors": []}
    _progress(output, index)
    stage = "search"
    try:
        started = time.perf_counter()
        log = run_raw(bank, method)
        _verify_seed_binding(bank, log)
        index["timing_seconds"]["search"] = time.perf_counter() - started
        index["summary"] = deepcopy(log["summary"])
        index["archive_sizes"] = _archive_sizes(log)
        index["initial_score_validation_evaluations"] = 30
        index["independent_frozen_bank_score_checks"] = 30
        stage = "raw_persistence"
        packet = {**provenance, "schema": "ga-final-probe-raw-v1", "task": task, "start": start,
                  "seed": SEED, "method": method, "bank_sha256": index["bank_sha256"],
                  "source_identity": bank["source_identity"], "log": log}
        path = output / "journal.json.gz"
        started = time.perf_counter()
        write_raw_atomic(path, packet)
        index["timing_seconds"]["raw_persistence"] = time.perf_counter() - started
        index["raw"] = {"path": path.name, **a.identity(path), "log_sha256": _json_hash(log)}
        index["status"] = "RAW_SAVED_UNVERIFIED"
        # This manifest and index are uploadable even if replay subsequently times out.
        _progress(output, index)
        stage = "independent_replay"
        started = time.perf_counter()
        verification = verify_raw(method, log)
        index["timing_seconds"]["independent_replay"] = time.perf_counter() - started
        a.write_json(output / "verification.json", verification)
        index["verification"] = {"path": "verification.json", **a.identity(output / "verification.json")}
        index["status"] = "COMPLETE_VERIFIED_PROBE"
        _progress(output, index)
    except Exception as error:
        index["errors"].append({"stage": stage, "type": type(error).__name__, "message": str(error)})
        index["status"] = "INCOMPLETE"
        _progress(output, index)
    return index


def _first_generation(log):
    result = {name: deepcopy(log[name]) for name in
              ("method", "problem", "initial_masks", "initial_scores", "rng_initial", "budget")}
    result["candidates"] = deepcopy([row for row in log["candidates"] if row["generation"] == 1])
    result["generations"] = deepcopy(log["generations"][:1])
    if "initial_archive" in log:
        result["initial_archive"] = deepcopy(log["initial_archive"])
    return result


def _pair_checks(projections):
    from studies.knapsack_parameters.mutation_population.search import verify_paired_first_generation
    from studies.knapsack_parameters.adaptation_analysis.comparison import verify_crossover_first_generation
    from studies.knapsack_parameters.bntga_selection.knapsack_comparison import verify_first_generation
    return {"mutation": verify_paired_first_generation(projections["classical"], projections["adaptive_mutation"]),
            "crossover": verify_crossover_first_generation(projections["classical"], projections["adaptive_crossover"]),
            "archive": verify_first_generation(projections["unbalanced_gap"], projections["balanced_gap"])}


def aggregate(output, artifacts, permit):
    provenance = a.check_permit(permit, "aggregate")
    a.validated_tests()
    from .inputs import load_probe_bank, validate_probe_freeze
    validate_probe_freeze(provenance)
    banks = {condition: load_probe_bank(*condition) for condition in a.CONDITIONS}
    output, artifacts = Path(output), Path(artifacts).resolve()
    a.require(not (output / "probe_summary.json").exists(), "Refuse aggregate overwrite")
    results, errors, seen, projections, plot_sources = [], [], set(), {}, []
    transport_path = artifacts / "transport_errors.json"
    if transport_path.is_file():
        transport = a.read_json(transport_path)
        _same_provenance(transport, provenance)
        a.require(transport.get("schema") == "ga-final-worker-transport-errors-v1" and
                  type(transport.get("errors")) is list and transport["errors"],
                  "Malformed transport failure record")
        errors.extend({"stage": "worker_artifact_transport", "detail": row} for row in transport["errors"])
    for path in sorted(artifacts.rglob("worker_index.json")):
        try:
            root = path.parent.resolve()
            a.require(root.is_relative_to(artifacts), "Artifact path escaped")
            a.verify_manifest(root)
            index = a.read_json(path)
            _same_provenance(index, provenance)
            condition = (index.get("task"), index.get("start"))
            key = (*condition, index.get("method"))
            a.require(condition in a.CONDITIONS and key[2] in a.METHODS and key not in seen and
                      index.get("schema") == "ga-final-probe-worker-v1" and index.get("seed") == SEED,
                      "Duplicate, foreign or unregistered profile")
            seen.add(key)
            bank = banks[condition]
            a.require(index.get("bank_sha256") == _json_hash(bank) and
                      index.get("source_identity") == bank["source_identity"], "Frozen bank identity differs")
            row = index.get("raw")
            a.require(type(row) is dict and row.get("path") == "journal.json.gz" and
                      a.identity(root / row["path"]) == {"bytes": row.get("bytes"), "sha256": row.get("sha256")},
                      "Missing or corrupt saved raw journal")
            with gzip.open(root / row["path"], "rt", encoding="utf-8") as stream:
                packet = json.load(stream)
            _same_provenance(packet, provenance)
            a.require(packet.get("schema") == "ga-final-probe-raw-v1" and
                      (packet.get("task"), packet.get("start"), packet.get("method")) == key and
                      packet.get("seed") == SEED and packet.get("bank_sha256") == index["bank_sha256"] and
                      packet.get("source_identity") == bank["source_identity"], "Raw provenance differs")
            log = packet["log"]
            a.require(log.get("problem") == bank["problem"] and log.get("initial_masks") == bank["initial_masks"] and
                      log.get("initial_scores") == bank["initial_scores"] and
                      row.get("log_sha256") == _json_hash(log), "Raw journal differs from fixed beginning")
            _verify_seed_binding(bank, log)
            started = time.perf_counter()
            verification = verify_raw(key[2], log)
            elapsed = time.perf_counter() - started
            a.require(index.get("summary") == log["summary"], "Worker summary differs")
            projections.setdefault(condition, {})[key[2]] = _first_generation(log)
            results.append({"task": key[0], "start": key[1], "method": key[2], "seed": SEED,
                            "summary": deepcopy(log["summary"]), "worker_status": index.get("status"),
                            "worker_errors": index.get("errors"), "timing_seconds": index.get("timing_seconds"),
                            "aggregation_replay_seconds": elapsed, "raw_identity": row,
                            "archive_sizes": _archive_sizes(log),
                            "independent_score_checks": verification["independent_score_checks"]})
            plot_sources.append((key, root / row["path"], deepcopy(row)))
            if index.get("status") != "COMPLETE_VERIFIED_PROBE" or index.get("errors"):
                errors.append({"profile": list(key), "reason": "Worker incomplete; saved raw independently replayed"})
            del packet, log, verification
        except Exception as error:
            errors.append({"artifact": path.relative_to(artifacts).as_posix(),
                           "type": type(error).__name__, "message": str(error)})
    pairs = []
    for condition, logs in projections.items():
        if set(logs) != set(a.METHODS):
            continue
        try:
            pairs.append({"task": condition[0], "start": condition[1], "checks": _pair_checks(logs)})
        except Exception as error:
            errors.append({"condition": list(condition), "stage": "pairing", "message": str(error)})
    complete = len(results) == 10 and len(pairs) == 2 and not errors
    rendering = {"status": "NOT_RENDERED", "reason": "INCOMPLETE", "files": []}
    if complete:
        # A sequential second read avoids retaining ten large raw archive logs.
        historical = a.read_json(a.ROOT / "studies/knapsack_parameters/evidence/run-37637475385/registry.json")
        optima = {row["instance_id"]: row["payload"]["exact"]["confirmed_optimum"]
                  for row in historical["cases"]}
        def plot_rows():
            for key, path, row in plot_sources:
                a.require(a.identity(path) == {"bytes": row["bytes"], "sha256": row["sha256"]},
                          "Raw journal changed before rendering")
                with gzip.open(path, "rt", encoding="utf-8") as stream:
                    packet = json.load(stream)
                yield {"task": key[0], "start": key[1], "method": key[2],
                       "log": packet["log"], "optimum": optima[key[0]], "verification_status": "VERIFIED"}
                del packet
        from .figures import render_probe, render_historical_fixed
        files = list(render_probe(plot_rows(), output / "figures"))
        files += list(render_historical_fixed(output / "figures"))
        rendering = {"status": "RENDERED_VERIFIED_TECHNICAL_PROBE", "files": [str(path) for path in files],
                     "inferential_claim": False}
    summary = {**provenance, "schema": "ga-final-resource-probe-v1",
               "status": "COMPLETE_TECHNICAL_PROBE" if complete else "INCOMPLETE",
               "expected_runs": 10, "verified_saved_runs": len(results), "missing_or_unverified_runs": 10 - len(results),
               "verified_new_search_evaluations": len(results) * BUDGET,
               "failed_in_progress_evaluations": "UNKNOWN_IF_INTERRUPTED", "results": results,
               "paired_checks": pairs, "errors": errors, "one_technical_seed": SEED,
               "rendering": rendering,
               "cost_accounting": {"new_initial_preparation_evaluations": 0,
                   "reused_frozen_initial_conditions": 2,
                   "worker_frozen_bank_score_checks_completed": 30 * len(results),
                   "aggregation_frozen_bank_score_checks": 60,
                   "kernel_known_initial_score_checks_completed": 30 * len(results),
                   "worker_operator_score_checks_completed": sum(
                       BUDGET + 30 for row in results if row["worker_status"] == "COMPLETE_VERIFIED_PROBE"),
                   "aggregation_operator_score_checks": (BUDGET + 30) * len(results)},
               "confirmatory_statistics_performed": False, "correlations_performed": False,
               "holdout_search_performed": False, "main_search_performed": False, "lambda_search_performed": False,
               "superiority_claim_authorized": False,
               "runner_minutes": "PENDING_FINAL_GITHUB_JOB_TIMINGS"}
    a.write_json(output / "probe_summary.json", summary)
    lines = ["# Ресурсна перевірка незмінних методів", "", f"Статус: {summary['status']}.", "",
             f"Перевірено {len(results)}/10 збережених журналів і {len(results) * BUDGET} нових запитів.", "",
             "Один технічний seed; нові задачі, підтверджувальна статистика та lambda не запускалися.", "",
             "| Задача | Початок | Метод | Кінцева цінність | Пошук, с | Перевірка, с |",
             "|---|---|---|---:|---:|---:|"]
    for row in results:
        timing = row["timing_seconds"]
        replay = timing.get("independent_replay")
        lines.append(f"| {row['task']} | {row['start']} | {row['method']} | {row['summary']['best_profit']} | "
                     f"{timing.get('search', 0):.3f} | {'не завершено' if replay is None else format(replay, '.3f')} |")
    lines += ["", "Неповні випадки не замінюються нулями. Результати не доводять переваги або практичної важливості.", ""]
    (output / "RESULTS_UK.md").write_text("\n".join(lines), encoding="utf-8")
    a.write_manifest(output)
    a.verify_manifest(output)
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("gate", "tests", "worker", "aggregate", "download"))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--phase", choices=("tests", "probe"))
    parser.add_argument("--permit", type=Path)
    parser.add_argument("--task")
    parser.add_argument("--start")
    parser.add_argument("--method")
    parser.add_argument("--artifacts", type=Path)
    parser.add_argument("--kind", choices=("permit", "workers"))
    args = parser.parse_args()
    if args.command == "gate":
        a.require(args.phase is not None, "Gate phase required")
        a.gate(args.output, args.phase)
    elif args.command == "download":
        a.require(args.kind is not None, "Download kind required")
        try:
            a.download_artifacts(args.output, args.kind)
        except Exception as error:
            if args.kind == "workers":
                # Already downloaded valid workers remain usable. Aggregation
                # still runs and cannot label a transport failure complete.
                provenance = a.authenticate()
                a.write_json(args.output / "transport_errors.json", {**provenance,
                    "schema": "ga-final-worker-transport-errors-v1",
                    "errors": [{"type": type(error).__name__, "message": str(error)}]})
            raise
    else:
        a.require(args.permit is not None, "Central permit required")
        if args.command == "tests":
            run_tests(args.output, args.permit)
        elif args.command == "worker":
            result = worker(args.output, args.task, args.start, args.method, args.permit)
            a.require(result["status"] == "COMPLETE_VERIFIED_PROBE", "Worker incomplete; raw evidence retained")
        else:
            a.require(args.artifacts is not None, "Source artifacts required")
            result = aggregate(args.output, args.artifacts, args.permit)
            a.require(result["status"] == "COMPLETE_TECHNICAL_PROBE", "Resource probe incomplete; evidence retained")


if __name__ == "__main__":
    main()
