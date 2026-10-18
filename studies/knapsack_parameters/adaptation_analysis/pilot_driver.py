"""Resource-gated 40-run pilot; journals are processed one profile at a time.

No work occurs at import time.  The separately registered execution authority
admits only preparation and the one-seed pilot, never main or lambda search.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
import gzip
import hashlib
import io
import json
import os
from pathlib import Path

from . import authority as a
from . import pilot_authority as p


TASKS = ("UC-s000", "WC-s001", "SC-s005", "SC-s000")
STARTS = ("cloned", "bank")
METHODS = ("classical", "adaptive_mutation", "adaptive_crossover", "unbalanced_gap", "balanced_gap")
SEED = 86001
PREPARATION_SEED = 86000
BUDGET = 5000
MAX_COMPRESSED_BYTES = 512 * 1024 * 1024
PILOT_PROTOCOL = "GA-KNAPSACK-ADAPTATION-ANALYSIS-PILOT-V1"
_PROVENANCE = ("protocol_id", "pilot_protocol_id", "pilot_registration_sha", "implementation_sha",
               "source_manifest", "run_id", "run_attempt")


def _require(condition, message):
    if not condition:
        raise ValueError("Adaptation pilot: " + message)


def _conditions():
    return {(task, start) for task in TASKS for start in STARTS}


def _json_hash(value):
    digest = hashlib.sha256()
    encoder = json.JSONEncoder(sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)
    for piece in encoder.iterencode(value):
        digest.update(piece.encode("utf-8"))
    return digest.hexdigest()


def _provenance_matches(found, expected):
    _require(all(name in found and found[name] == expected[name] for name in _PROVENANCE),
             "Foreign or mixed implementation/run provenance")


def _write_progress(output, index):
    # A new file is atomically installed; an interrupted profile does not
    # overwrite the last successfully recorded condition progress.
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    temporary = output.parent / ("." + output.name + "-condition-index.partial")
    a.write_json(temporary, index)
    os.replace(temporary, output / "condition_index.json")
    a.write_manifest(output)


class _CappedWriter:
    def __init__(self, stream, limit):
        self.stream, self.limit, self.written = stream, limit, 0

    def write(self, data):
        _require(self.written + len(data) <= self.limit, "Compressed journal resource limit exceeded")
        count = self.stream.write(data)
        self.written += count
        return count

    def flush(self):
        return self.stream.flush()

    def tell(self):
        return self.stream.tell()


def _write_gzip(path, packet, output):
    """Stream JSON/gzip, bounding all completed compressed journals per job."""
    path, output = Path(path), Path(output)
    _require(not path.exists(), "Refusing to overwrite an existing scientific journal")
    path.parent.mkdir(parents=True, exist_ok=True)
    used = sum(item.stat().st_size for item in (output / "journals").glob("*.json.gz"))
    remaining = MAX_COMPRESSED_BYTES - used
    _require(remaining > 0, "Compressed journal resource limit exceeded")
    temporary = output.parent / ("." + output.name + "-" + path.name + ".partial")
    _require(not temporary.exists(), "Pre-existing temporary journal would be overwritten")
    with temporary.open("xb") as raw:
        bounded = _CappedWriter(raw, remaining)
        with gzip.GzipFile(filename="", mode="wb", fileobj=bounded, mtime=0) as compressed:
            with io.TextIOWrapper(compressed, encoding="utf-8", newline="\n") as text_stream:
                json.dump(packet, text_stream, sort_keys=True, separators=(",", ":"),
                          ensure_ascii=False, allow_nan=False)
                text_stream.write("\n")
    os.replace(temporary, path)


def _bank_map(banks):
    _require(type(banks) is list and len(banks) == 8, "Exactly eight frozen banks required")
    result = {}
    for bank in banks:
        key = (bank.get("task"), bank.get("start"))
        _require(key in _conditions() and key not in result and bank.get("search_seed") == SEED and
                 bank.get("preparation_seed") == PREPARATION_SEED, "Unknown, duplicate or stale bank")
        result[key] = bank
    _require(set(result) == _conditions(), "Incomplete frozen bank rectangle")
    return result


def prepare(output, permit=None):
    output = Path(output)
    provenance = p.check_permit(Path(permit) if permit is not None else output, "prepare")
    tests = p.validated_tests()
    from studies.knapsack_parameters.mutation_population.driver import initial_bank, source_task

    _require(not (output / "bank_registry.json").exists(), "Refusing to overwrite prepared banks")
    registration = a.read_json(a.MODULE / "registration.json")
    historical = a.read_json(a.ROOT / "studies/knapsack_parameters/evidence/run-37637475385/registry.json")
    _require(registration["pilot"]["tasks"] == list(TASKS) and
             registration["pilot"]["starts"] == list(STARTS) and
             registration["pilot"]["seed"] == SEED and
             registration["pilot"]["preparation_seed"] == PREPARATION_SEED,
             "Frozen pilot configuration changed")
    entries, physical, independent = [], 0, 0
    for task in TASKS:
        task_index = historical["case_order"].index(task)
        problem, case, source = source_task(task)
        for start_index, start in enumerate(STARTS):
            beginning = initial_bank(problem, case, task_index, start, SEED, PREPARATION_SEED)
            bank = {**provenance, "schema": "ga-adaptation-pilot-bank-v1",
                    "task": task, "task_index": task_index, "start": start,
                    "start_index": start_index, "search_seed": SEED,
                    "preparation_seed": PREPARATION_SEED, "problem": problem,
                    "source_identity": source, **beginning}
            relative = f"banks/{task}-{start}-{SEED}.json"
            a.write_json(output / relative, bank)
            entries.append({"task": task, "start": start, "seed": SEED,
                            "path": relative, **a.identity(output / relative)})
            physical += beginning["physical_preparation_evaluations"]
            independent += beginning["independent_preparation_checks"]
    registry = {**provenance, "schema": "ga-adaptation-pilot-banks-v1", "scope": "pilot",
                "banks": entries, "initial_conditions": len(entries),
                "scientific_search_calls": 0, "physical_preparation_evaluations": physical,
                "independent_preparation_checks": independent,
                "tests_receipt_identity": {"implementation_sha": tests.get("implementation_sha"),
                                           "source_manifest": tests.get("source_manifest")}}
    _require(independent == 240 and len(entries) == 8, "Initial preparation accounting differs")
    a.write_json(output / "bank_registry.json", registry)
    a.write_manifest(output)
    a.verify_manifest(output)
    return registry


def run_one_condition(output, task, start, permit=None):
    output = Path(output)
    provenance = p.check_permit(Path(permit) if permit is not None else output, "pilot")
    p.validated_tests()
    _require((task, start) in _conditions(), "Unregistered task/start condition")
    banks = p.load_banks()
    bank = _bank_map(banks)[(task, start)]
    from .comparison import run_profile

    _require(not (output / "condition_index.json").exists(), "Refusing to overwrite condition progress")
    index = {**provenance, "schema": "ga-adaptation-pilot-condition-v1",
             "task": task, "start": start, "seed": SEED,
             "bank_sha256": _json_hash(bank), "source_identity": bank["source_identity"],
             "expected_methods": list(METHODS), "results": [], "failures": [],
             "active_method": None, "status": "INCOMPLETE",
             "bank_validation_independent_score_checks": 30 * len(banks)}
    _write_progress(output, index)
    for method in METHODS:
        index["active_method"] = method
        _write_progress(output, index)
        try:
            result = run_profile(bank["problem"], bank["initial_masks"], bank["initial_scores"],
                                 method, SEED, bank["task_index"], bank["start_index"], budget=BUDGET)
            log, verification = result["log"], result["verification"]
            _require(verification.get("verification_status") == "VERIFIED" and
                     verification.get("summary") == log.get("summary"), "Worker independent reconstruction failed")
            _require(log.get("budget") == BUDGET and
                     log["summary"]["new_calls"] == log["summary"]["physical_evaluations"] == BUDGET and
                     log["summary"]["known_score_validation_evaluations"] == 30 and
                     verification.get("independent_score_checks") == BUDGET + 30,
                     "Worker budget or evaluation accounting differs")
            packet = {**provenance, "schema": "ga-adaptation-pilot-journal-v1",
                      "task": task, "start": start, "seed": SEED, "method": method,
                      "bank_sha256": index["bank_sha256"], "source_identity": bank["source_identity"],
                      "log": log, "verification": verification}
            relative = f"journals/{task}-{start}-{SEED}-{method}.json.gz"
            path = output / relative
            _write_gzip(path, packet, output)
            index["results"].append({"method": method, "path": relative, **a.identity(path),
                                     "log_sha256": _json_hash(log), "summary": deepcopy(log["summary"]),
                                     "worker_independent_score_checks": BUDGET + 30})
            # Release this profile before allocating the next archive log.
            del packet, log, verification, result
            index["active_method"] = None
            _write_progress(output, index)
        except Exception as error:
            index["failures"].append({"method": method, "error_type": type(error).__name__,
                                      "message": str(error)})
            _write_progress(output, index)
            return index
    index["status"] = "COMPLETE_CONDITION"
    _write_progress(output, index)
    return index


def _first_generation(log):
    keys = ("method", "problem", "initial_masks", "initial_scores", "rng_initial", "budget")
    result = {name: deepcopy(log[name]) for name in keys}
    result["candidates"] = deepcopy([row for row in log["candidates"] if row["generation"] == 1])
    result["generations"] = deepcopy(log["generations"][:1])
    if "initial_archive" in log:
        result["initial_archive"] = deepcopy(log["initial_archive"])
    return result


def _trajectory(envelope):
    from .analysis import _population

    log = envelope["log"]
    masks = list(log["initial_masks"]) + [row["mask"] for row in log["candidates"]]
    scores = list(log["initial_scores"]) + [
        {key: row[key] for key in ("weight", "profit", "feasible")} for row in log["candidates"]
    ]
    best = max(score["profit"] for score in log["initial_scores"] if score["feasible"])
    records = [{"query": 0, "profit": best}]
    for row in log["candidates"]:
        if row["record_profit"] > best:
            best = row["record_profit"]
            records.append({"query": row["call"], "profit": best})
    population = [_population(list(range(30)), masks, scores, log["problem"]["n"], 0)]
    for event in log["generations"]:
        if event["complete"]:
            population.append(_population(event["population_after"], masks, scores,
                                          log["problem"]["n"], event["end_call"]))
    return {"method": envelope["method"], "start": envelope["start"],
            "budget": log["budget"], "optimum": envelope["optimum"],
            "final_best_profit": best, "record_events": records, "population_trace": population}


def _render_trajectory(rows, output):
    if len(rows) != 10:
        return None
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from .plots import COLORS, LABELS

    destination = Path(output) / "04_pilot_uc_s000_86001.png"
    _require(not destination.exists(), "Refusing to overwrite the pilot trajectory")
    fig, axes = plt.subplots(2, 3, figsize=(17, 9), constrained_layout=True, sharex="col", sharey="col")
    for row_index, start in enumerate(("bank", "cloned")):
        for run in rows:
            if run["start"] != start:
                continue
            record, population = run["record_events"], run["population_trace"]
            method, optimum = run["method"], run["optimum"]
            axes[row_index, 0].step([r["query"] for r in record] + [BUDGET],
                                    [100 * r["profit"] / optimum for r in record] +
                                    [100 * run["final_best_profit"] / optimum], where="post",
                                    label=LABELS[method], color=COLORS[method])
            axes[row_index, 1].plot([r["query"] for r in population],
                                    [100 * r["mean_feasible_profit"] / optimum
                                     if r["mean_feasible_profit"] is not None else float("nan")
                                     for r in population], color=COLORS[method])
            axes[row_index, 2].plot([r["query"] for r in population],
                                    [r["normalized_hamming"] for r in population], color=COLORS[method])
        for column, title in enumerate(("Рекорд, % OPT", "Середня допустима цінність, % OPT", "Різноманітність")):
            axes[row_index, column].set_title(f"{start}: {title}")
            axes[row_index, column].set_xlabel("Нові оцінювання")
            axes[row_index, column].grid(alpha=0.25)
    axes[0, 0].legend(fontsize=8)
    fig.suptitle("UC-s000, seed 86001: один технічний пілот; не доказ переваги")
    fig.savefig(destination, dpi=170)
    plt.close(fig)
    return destination.name


def aggregate(output, artifacts_root, permit=None):
    output, artifacts_root = Path(output), Path(artifacts_root).resolve()
    provenance = p.check_permit(Path(permit) if permit is not None else output, "aggregate")
    p.validated_tests()
    banks = p.load_banks()
    bank_map = _bank_map(banks)
    _require(not (output / "pilot_summary.json").exists(), "Refusing to overwrite pilot aggregation")
    output.mkdir(parents=True, exist_ok=True)
    from . import analysis
    from studies.knapsack_parameters.mutation_population.driver import source_task

    indices, available, errors, seen_conditions, seen_runs = [], [], [], set(), set()
    for index_path in sorted(artifacts_root.rglob("condition_index.json")):
        try:
            root = index_path.parent.resolve()
            _require(root.is_relative_to(artifacts_root), "Artifact path escaped its root")
            a.verify_manifest(root)
            index = a.read_json(index_path)
            _provenance_matches(index, provenance)
            condition = (index.get("task"), index.get("start"))
            _require(index.get("schema") == "ga-adaptation-pilot-condition-v1" and
                     condition in _conditions() and condition not in seen_conditions and
                     index.get("seed") == SEED and index.get("expected_methods") == list(METHODS),
                     "Unexpected, duplicate or foreign condition artifact")
            seen_conditions.add(condition)
            bank = bank_map[condition]
            _require(index.get("bank_sha256") == _json_hash(bank) and
                     index.get("source_identity") == bank["source_identity"], "Worker frozen bank identity differs")
            _require(type(index.get("results")) is list and type(index.get("failures")) is list,
                     "Condition progress schema differs")
            _require(type(index.get("bank_validation_independent_score_checks")) is int and
                     index["bank_validation_independent_score_checks"] == 240,
                     "Worker bank-validation accounting differs")
            indices.append(index)
            if index.get("status") != "COMPLETE_CONDITION" or index["failures"]:
                errors.append({"condition": list(condition), "reason": "Worker incomplete", "failures": index["failures"]})
            for row in index["results"]:
                method = row.get("method")
                key = (*condition, method)
                _require(method in METHODS and key not in seen_runs, "Duplicate or unsupported profile result")
                relative = f"journals/{condition[0]}-{condition[1]}-{SEED}-{method}.json.gz"
                _require(row.get("path") == relative, "Unsafe or mismatched journal path")
                path = root / relative
                _require(a.identity(path) == {"bytes": row.get("bytes"), "sha256": row.get("sha256")},
                         "Journal checksum differs from worker index")
                seen_runs.add(key)
                available.append((condition, method, path, row, index))
        except Exception as error:
            errors.append({"artifact": str(index_path.relative_to(artifacts_root)),
                           "reason": str(error), "error_type": type(error).__name__})

    projections, trajectories, run_rows = {}, [], []
    replayed = 0

    def envelopes():
        nonlocal replayed
        for condition, method, path, worker_row, index in available:
            with gzip.open(path, "rt", encoding="utf-8") as stream:
                packet = json.load(stream)
            _provenance_matches(packet, provenance)
            bank = bank_map[condition]
            _require(packet.get("schema") == "ga-adaptation-pilot-journal-v1" and
                     (packet.get("task"), packet.get("start")) == condition and
                     packet.get("seed") == SEED and packet.get("method") == method and
                     packet.get("bank_sha256") == index["bank_sha256"] and
                     packet.get("source_identity") == bank["source_identity"], "Raw journal identity differs")
            log = packet["log"]
            _require(log.get("problem") == bank["problem"] and
                     log.get("initial_masks") == bank["initial_masks"] and
                     log.get("initial_scores") == bank["initial_scores"] and
                     log.get("budget") == BUDGET and _json_hash(log) == worker_row.get("log_sha256"),
                     "Raw journal differs from frozen input or worker identity")
            verification = packet.get("verification", {})
            _require(verification.get("verification_status") == "VERIFIED" and
                     verification.get("summary") == log.get("summary") == worker_row.get("summary") and
                     verification.get("independent_score_checks") == BUDGET + 30,
                     "Worker reconstruction receipt disagrees with raw log")
            _, case, _ = source_task(condition[0])
            envelope = {"task": condition[0], "family": condition[0].split("-", 1)[1],
                        "start": condition[1], "seed": SEED, "method": method,
                        "implementation_sha": provenance["implementation_sha"], "log": log,
                        "optimum": case["exact"]["confirmed_optimum"],
                        "center_profit": case["certificate"]["center"]["profit"]
                        if condition[1] == "cloned" else None}
            projection = _first_generation(log)
            trajectory = _trajectory(envelope) if condition[0] == "UC-s000" else None
            yield envelope
            # The consumer has now independently reconstructed this raw log.
            replayed += 1
            projections.setdefault(condition, {})[method] = projection
            if trajectory is not None:
                trajectories.append(trajectory)
            run_rows.append({"task": condition[0], "start": condition[1], "method": method,
                             "seed": SEED, "center_status": case["status"],
                             "summary": deepcopy(log["summary"]),
                             "worker_journal_identity": {"bytes": worker_row["bytes"], "sha256": worker_row["sha256"]},
                             "worker_independent_score_checks": BUDGET + 30,
                             "aggregation_operator_score_checks": BUDGET + 30,
                             "aggregation_metric_score_checks": BUDGET + 30})
            del envelope, packet, log

    try:
        summary = analysis.summarize_verified_envelopes(envelopes(), scope="pilot")
    except Exception as error:
        errors.append({"reason": str(error), "error_type": type(error).__name__, "phase": "raw_replay"})
        summary = {"schema": "ga-adaptation-series-summary-v1", "scope": "pilot", "status": "INCOMPLETE",
                   "expected_runs": 40, "received_runs": replayed, "statistics": None, "correlations": []}
    pairs = []
    from . import comparison
    from studies.knapsack_parameters.mutation_population.search import verify_paired_first_generation
    from studies.knapsack_parameters.bntga_selection.knapsack_comparison import verify_first_generation
    for condition, logs in projections.items():
        if set(logs) != set(METHODS):
            continue
        try:
            pairs.append({"task": condition[0], "start": condition[1], "seed": SEED,
                          "mutation": verify_paired_first_generation(logs["classical"], logs["adaptive_mutation"]),
                          "crossover": comparison.verify_crossover_first_generation(logs["classical"], logs["adaptive_crossover"]),
                          "archive": verify_first_generation(logs["unbalanced_gap"], logs["balanced_gap"])})
        except Exception as error:
            errors.append({"condition": list(condition), "phase": "pairing", "reason": str(error)})
    complete = (not errors and seen_conditions == _conditions() and len(available) == replayed == 40 and
                len(pairs) == 8 and summary.get("status") == "COMPLETE_VERIFIED_PILOT")
    rendering = {"status": "NOT_RENDERED", "reason": "INCOMPLETE", "files": []}
    if complete:
        from .plots import render_report
        rendering = render_report(summary, output / "figures")
        trajectory = _render_trajectory(trajectories, output / "figures")
        if trajectory:
            rendering["files"].append(trajectory)
    # Source artifacts remain the evidence for partial or corrupt cases too.
    result = {**provenance, "schema": "ga-adaptation-pilot-result-v1",
              "status": "COMPLETE_TECHNICAL_PILOT" if complete else "INCOMPLETE",
              "expected_conditions": 8, "received_condition_artifacts": len(indices),
              "expected_runs": 40, "available_raw_journals": len(available),
              "independently_replayed_runs": replayed, "new_search_evaluations_verified": replayed * BUDGET,
              "runs": run_rows, "paired_checks": pairs, "errors": errors,
              "analysis": summary, "rendering": rendering,
              "cost_accounting": {
                  "verified_new_search_evaluations": replayed * BUDGET,
                  "kernel_known_initial_score_checks_completed": 30 * len(available),
                  "worker_independent_operator_score_checks_completed": (BUDGET + 30) * len(available),
                  "aggregation_independent_operator_score_checks_completed": (BUDGET + 30) * replayed,
                  "aggregation_independent_metric_score_checks_completed": (BUDGET + 30) * replayed,
                  "worker_bank_validation_independent_score_checks": sum(
                      index["bank_validation_independent_score_checks"] for index in indices),
                  "aggregation_bank_validation_independent_score_checks": 30 * len(banks),
                  "previous_initial_preparation_physical_evaluations": sum(
                      bank["physical_preparation_evaluations"] for bank in banks),
                  "previous_initial_preparation_independent_score_checks": sum(
                      bank["independent_preparation_checks"] for bank in banks),
                  "diagnostic_neighborhood_evaluations": 0,
                  "failed_in_progress_evaluations": "UNKNOWN_IF_WORKER_INTERRUPTED",
                  "final_runner_minutes": "PENDING_FINAL_GITHUB_JOB_TIMINGS"},
              "lambda": {"status": "BLOCKED_LAMBDA_REPLICATION", "runs": None},
              "bootstrap_performed": False, "correlations_performed": False,
              "superiority_claim_authorized": False, "main_search_performed": False}
    a.write_json(output / "pilot_summary.json", result)
    lines = ["# Пілот адаптації ГА", "", f"Статус: {result['status']}.", "",
             f"Незалежно відтворено {replayed}/40 журналів; перевірено {replayed * BUDGET} нових пошукових запитів.", "",
             "Один технічний seed 86001; без BCa, кореляційної переваги або добору коефіцієнтів. λ заблокований.", "",
             "Cloned включає SC-s000 із глобальним центром як негативний контроль. Це не частота виходу лише з 14 допущених неглобальних центрів.", "",
             "| Початок | Метод | Запуски | Кінцеве відставання, % | Виходи |",
             "|---|---|---:|---:|---:|"]
    for row in summary.get("method_summaries", []):
        escapes = "—" if row["absolute_escapes"] is None else str(row["absolute_escapes"])
        lines.append(f"| {row['start']} | {row['method']} | {row['runs']} | {row['mean_final_gap_percent']:.4f} | {escapes} |")
    lines += ["", "| Задача | Початок | Тип початкового центра | Метод | Фінальна цінність |", "|---|---|---|---|---:|"]
    for row in run_rows:
        lines.append(f"| {row['task']} | {row['start']} | {row['center_status']} | {row['method']} | {row['summary']['best_profit']} |")
    lines += ["", "*Невихід не доводить глобальності. Невиконані або пошкоджені записи не замінюються нулями; остаточні runner-хвилини встановлюються після завершення jobs.*", ""]
    (output / "RESULTS_UK.md").write_text("\n".join(lines), encoding="utf-8")
    a.write_manifest(output)
    a.verify_manifest(output)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("gate", "prepare", "worker", "aggregate"))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--permit", type=Path)
    parser.add_argument("--phase", choices=("prepare", "pilot"))
    parser.add_argument("--artifacts", type=Path)
    parser.add_argument("--task", choices=TASKS)
    parser.add_argument("--start", choices=STARTS)
    args = parser.parse_args()
    if args.command == "gate":
        _require(args.phase is not None, "gate requires --phase")
        p.gate(args.output, args.phase)
    elif args.command == "prepare":
        prepare(args.output, args.permit)
    elif args.command == "worker":
        _require(args.task is not None and args.start is not None, "worker requires task and start")
        result = run_one_condition(args.output, args.task, args.start, args.permit)
        _require(result["status"] == "COMPLETE_CONDITION", "Worker incomplete; progress evidence retained")
    else:
        _require(args.artifacts is not None, "aggregate requires --artifacts")
        result = aggregate(args.output, args.artifacts, args.permit)
        _require(result["status"] == "COMPLETE_TECHNICAL_PILOT", "Pilot incomplete; aggregate evidence retained")


if __name__ == "__main__":
    main()
