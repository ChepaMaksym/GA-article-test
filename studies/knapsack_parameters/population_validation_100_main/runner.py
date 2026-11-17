"""Prepare paired banks and execute explicitly authorized main-study shards.

Search, replay and numerical input preparation are CI-only.  Importing this
module performs no calculations or search.  Each shard covers one population
and one family; all scientific parameters come from the preregistered plan.
"""
from __future__ import annotations

import argparse
import gzip
import json
import os
from pathlib import Path
import re
import time
import traceback

from .common import guard_main
from studies.knapsack_parameters.population_validation_100.common import (
    read_json, require, sha, write_json,
)


TYPES = ("UC", "WC", "SC")
POPS = (10, 20, 30)
TOTAL = 100000


def _validate_protocol(protocol):
    require(protocol["item_count"] == 100 and tuple(protocol["populations"]) == POPS,
            "Study dimension or populations differ from the registered comparison")
    require(tuple(protocol["families"]) == tuple(range(50, 60)) and tuple(protocol["types"]) == TYPES,
            "Family/type plan differs")
    require(tuple(protocol["search_seeds"]) == tuple(range(150001, 150011))
            and protocol["preparation_seed"] == 150000 and protocol["total_evaluations"] == TOTAL,
            "Seed or evaluation plan differs")
    require(protocol["fixed_parameters"] == {"p_m": 0.01, "p_c": 0.9, "tournament_size": 2, "elite_count": 1},
            "Fixed operators differ")
    require(tuple(protocol["checkpoints"]) == (5000, 10000, 20000, 50000, 100000), "Checkpoints differ")
    limits = protocol["shard_limits"]
    require(all(type(limits[k]) is int and limits[k] > 0
                for k in ("seconds", "bytes", "reserve_seconds", "reserve_bytes")), "Missing registered shard limits")
    require(limits["reserve_seconds"] < limits["seconds"] and limits["reserve_bytes"] < limits["bytes"],
            "Invalid shard reserves")
    require(re.fullmatch(r"[0-9a-f]{64}", protocol["technical_input_manifest_sha256"]) is not None,
            "Technical input manifest digest is not pinned")


def _safe_file(root, relative):
    require(type(relative) is str and relative and "\\" not in relative and ":" not in relative,
            "Unsafe evidence path")
    require(not Path(relative).is_absolute() and ".." not in Path(relative).parts, "Unsafe evidence path")
    path = (root / relative).resolve()
    require(path.is_relative_to(root.resolve()) and path.is_file(), "Missing or unsafe evidence path")
    return path


def _verify_files(root, entries):
    require(type(entries) is list and entries, "Evidence file inventory is empty")
    seen = set()
    for row in entries:
        relative = row["path"]
        require(relative not in seen, "Duplicate evidence path")
        seen.add(relative)
        path = _safe_file(root, relative)
        require(path.stat().st_size == row["bytes"] and sha(path) == row["sha256"],
                "Evidence checksum differs: " + relative)


def _copy_bytes(source, destination):
    require(not destination.exists(), "Existing input evidence must be retained")
    destination.parent.mkdir(parents=True, exist_ok=True)
    with source.open("rb") as incoming, destination.open("xb") as outgoing:
        for chunk in iter(lambda: incoming.read(1024 * 1024), b""):
            outgoing.write(chunk)


def _verify_certificates(problem, certificate):
    """Recheck retained witnesses without invoking either exact solver."""
    from studies.knapsack_parameters.population_validation_100.preparation import score
    require(certificate["status"] == "CERTIFIED_TWO_INDEPENDENT_EXACT_ORACLES"
            and certificate["search_uses_optimum"] is False, "Exact references are not admitted")
    optimum = certificate["optimum"]
    require(type(optimum) is int and optimum > 0, "Invalid reference optimum")
    expected_methods = {"capacity_certificate": "capacity_max_profit_dp_packed_witness",
                        "profit_certificate": "profit_min_weight_dp_independent_packed_witness"}
    for name, method in expected_methods.items():
        witness = certificate[name]
        require(witness["method"] == method and witness["optimum_profit"] == optimum, "Two exact optima disagree")
        measured = score(problem, witness["witness_mask"])
        require(measured["feasible"] and measured["profit"] == witness["witness_profit"] == optimum
                and measured["weight"] == witness["witness_weight"], "Exact witness scores disagree")


def prepare(inputs, out):
    """Validate the prior certified source and generate 300 shared initial banks."""
    protocol = guard_main()
    _validate_protocol(protocol)
    inputs, output = Path(inputs), Path(out)
    require(not output.exists(), "Preserve prior/incomplete bank preparation")
    source_manifest = inputs / "manifest.json"
    require(sha(source_manifest) == protocol["technical_input_manifest_sha256"], "Technical input manifest differs")
    source = read_json(source_manifest)
    require(source["status"] == "INPUTS_AUDITED_AND_CERTIFIED" and source["holdout_tasks"] == 30
            and source["historical_duplicate_inputs_checked"] == 150
            and source["main_ga_runs"] == 0 and source["main_banks_prepared"] is False,
            "Independent input preparation is incomplete or already includes main search")
    require(source["source_commit"] == protocol["source_commit"], "KPLIB source revision differs")
    _verify_files(inputs, source["files"])
    main_tasks = [row for row in source["tasks"] if row["phase"] == "main"]
    expected_ids = {f"n00100-{kind}-s{family:03d}" for family in range(50, 60) for kind in TYPES}
    require(len(main_tasks) == 30 and {row["task"] for row in main_tasks} == expected_ids,
            "Holdout corpus is incomplete or contains duplicates")
    require(len({row["task_index"] for row in main_tasks}) == 30, "Task indices are duplicated")
    registry_path = Path(__file__).resolve().parents[1] / "population_validation_100/data/source_registry.json"
    registry = read_json(registry_path)
    original = {row["task_id"]: row for row in registry["main_cases"]}
    require(set(original) == expected_ids and registry["source_commit"] == protocol["source_commit"],
            "Pinned source registry differs")
    from studies.knapsack_parameters.population_validation_100.preparation import (
        make_bank, validate_source,
    )
    from studies.knapsack_parameters.population_size_study.inputs import problem_sha256, unordered_problem_sha256
    started = time.perf_counter()
    output.mkdir(parents=True, exist_ok=False)
    files, tasks, banks = [], [], []
    for row in sorted(main_tasks, key=lambda x: x["task"]):
        task, index = row["task"], row["task_index"]
        require(index == original[task]["task_index"] and row["git_blob_sha1"] == original[task]["git_blob_sha1"],
                "Source identity or task index differs")
        source_dir = inputs / task
        problem = read_json(source_dir / "problem.json")
        certificate = read_json(source_dir / "certificate.json")
        raw = (source_dir / "source.kp").read_bytes()
        require(validate_source(raw, original[task]) == problem and sha(source_dir / "source.kp") == row["source_sha256"]
                and problem_sha256(problem) == row["problem_sha256"]
                and unordered_problem_sha256(problem) == row["unordered_problem_sha256"], "Source/problem identity differs")
        _verify_certificates(problem, certificate)
        for name in ("problem.json", "certificate.json", "source.kp"):
            _copy_bytes(source_dir / name, output / task / name)
        task_banks = []
        for seed in protocol["search_seeds"]:
            bank = make_bank(problem, index, seed, protocol["preparation_seed"])
            relative = f"{task}/banks/seed-{seed}.json"
            bank_path = output / relative
            write_json(bank_path, bank)
            task_banks.append({"seed": seed, "path": relative, "sha256": sha(bank_path), "bytes": bank_path.stat().st_size})
        match = re.fullmatch(r"n00100-(UC|WC|SC)-(s0(?:5[0-9]))", task)
        require(match is not None, "Unexpected task identity")
        tasks.append({"task": task, "task_index": index, "class_label": match.group(1),
                      "family": match.group(2), "problem_sha256": row["problem_sha256"],
                      "certificate_sha256": sha(output / task / "certificate.json"), "banks": task_banks})
        banks.extend(task_banks)
    require(len(tasks) == 30 and len(banks) == 300, "Prepared bank inventory differs")
    for path in sorted(output.rglob("*")):
        if path.is_file():
            files.append({"path": path.relative_to(output).as_posix(), "bytes": path.stat().st_size, "sha256": sha(path)})
    write_json(output / "manifest.json", {"schema": "population-validation-100-main-inputs-v1",
               "status": "PAIRED_BANKS_PREPARED", "source_manifest_sha256": sha(source_manifest),
               "source_commit": source["source_commit"], "tasks": tasks, "files": files,
               "bank_count": 300, "bank_size": 30, "physical_start_score_checks": 9000,
               "main_ga_runs": 0, "preparation_seconds": time.perf_counter() - started})
    print("Prepared and validated 300 paired banks for 30 certified tasks; no main search.", flush=True)


def _used_bytes(*roots):
    return sum(path.stat().st_size for root in roots for path in root.rglob("*") if path.is_file())


class _BoundedSink:
    """Reject a physical write before the combined shard cap can be exceeded."""

    def __init__(self, stream, budget, ceiling):
        self.stream, self.budget, self.ceiling = stream, budget, ceiling

    def write(self, value):
        if not value:
            return 0
        require(self.budget["used"] + len(value) <= self.ceiling,
                "Shard byte ceiling reached while writing; preserve partial evidence")
        written = self.stream.write(value)
        require(type(written) is int and 0 <= written <= len(value), "Invalid physical write count")
        self.budget["used"] += written
        require(written == len(value), "Incomplete physical write")
        return written

    def flush(self):
        self.stream.flush()

    def tell(self):
        return self.stream.tell()


def _write_bounded(path, value, budget, *, emergency=False):
    """Stream JSON/gzip through a strict cap; retain a failed pending file."""
    path = Path(path)
    require(not path.exists(), "Existing evidence must not be overwritten: " + str(path))
    path.parent.mkdir(parents=True, exist_ok=True)
    pending = path.with_name(path.name + ".pending")
    require(not pending.exists(), "Existing incomplete evidence must not be overwritten")
    # Reserve 128 KiB for a failure receipt even if one unexpectedly huge case
    # consumes all remaining regular-output space.
    ceiling = budget["limit"] if emergency else budget["limit"] - 128 * 1024
    require(ceiling >= budget["used"], "No bounded output space remains")
    encoder = json.JSONEncoder(sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)
    with pending.open("xb", buffering=0) as raw:
        sink = _BoundedSink(raw, budget, ceiling)
        if path.suffix == ".gz":
            with gzip.GzipFile(fileobj=sink, mode="wb", filename="", mtime=0, compresslevel=3) as stream:
                for chunk in encoder.iterencode(value):
                    stream.write(chunk.encode("utf-8"))
        else:
            for chunk in encoder.iterencode(value):
                sink.write(chunk.encode("utf-8"))
    # A hard link in the same directory fails atomically if the destination
    # already exists, unlike os.replace() which could silently overwrite it.
    os.link(pending, path)
    pending.unlink()


def shard(prepared, family, mu, out, compact_out):
    """Execute 30 registered cases, retaining completed-case receipts immediately."""
    protocol = guard_main()
    _validate_protocol(protocol)
    require(re.fullmatch(r"s0(?:5[0-9])", family) is not None and mu in POPS, "Unregistered shard")
    require(re.fullmatch(r"[0-9]+", os.environ.get("GITHUB_RUN_ID", "")) is not None, "Missing workflow identity")
    require(re.fullmatch(r"[0-9a-f]{40}", os.environ.get("GITHUB_SHA", "")) is not None, "Missing frozen workflow commit")
    code_manifest_sha256 = sha(Path(__file__).resolve().parent / "source_manifest.json")
    prepared, output, compact = Path(prepared), Path(out), Path(compact_out)
    require(not output.exists() and not compact.exists(), "Preserve previous or partial shard evidence")
    require(not output.resolve().is_relative_to(compact.resolve()) and not compact.resolve().is_relative_to(output.resolve()),
            "Raw and compact output roots must be disjoint")
    manifest_path = prepared / "manifest.json"
    manifest = read_json(manifest_path)
    require(manifest["schema"] == "population-validation-100-main-inputs-v1"
            and manifest["status"] == "PAIRED_BANKS_PREPARED" and manifest["main_ga_runs"] == 0
            and manifest["source_manifest_sha256"] == protocol["technical_input_manifest_sha256"],
            "Prepared bank provenance differs")
    _verify_files(prepared, manifest["files"])
    tasks = [row for row in manifest["tasks"] if row["family"] == family]
    require(len(tasks) == 3 and {r["class_label"] for r in tasks} == set(TYPES), "Family tasks differ")
    require(all(len(row["banks"]) == 10 and {bank["seed"] for bank in row["banks"]} == set(protocol["search_seeds"])
                for row in tasks), "Family bank inventory differs")
    output.mkdir(parents=True, exist_ok=False)
    compact.mkdir(parents=True, exist_ok=False)
    raw_name = f"population100-main-raw-{family}-mu{mu}-{os.environ['GITHUB_RUN_ID']}"
    limits = protocol["shard_limits"]
    budget = {"limit": limits["bytes"], "used": _used_bytes(output, compact)}
    started = time.monotonic()
    rows = []
    from studies.knapsack_parameters.population_validation_100.pilot import make_log
    from studies.knapsack_parameters.crossover_population.verification import verify_log
    from studies.knapsack_parameters.crossover_population.observations import extract
    for task in sorted(tasks, key=lambda r: TYPES.index(r["class_label"])):
        require(task["task"] == f"n00100-{task['class_label']}-{family}", "Task family identity differs")
        for descriptor in sorted(task["banks"], key=lambda r: r["seed"]):
            seed = descriptor["seed"]
            prefix = f"{task['task']}/seed-{seed}"
            folder = output / task["task"] / f"seed-{seed}"
            try:
                require(time.monotonic() - started < limits["seconds"] - limits["reserve_seconds"],
                        "Time reserve reached; preserve and resume only missing identities")
                require(budget["used"] < limits["bytes"] - limits["reserve_bytes"],
                        "Artifact reserve reached; preserve and resume only missing identities")
                case_started = time.perf_counter()
                folder.mkdir(parents=True, exist_ok=False)
                problem = read_json(prepared / task["task"] / "problem.json")
                bank_file = _safe_file(prepared, descriptor["path"])
                require(sha(bank_file) == descriptor["sha256"] and bank_file.stat().st_size == descriptor["bytes"],
                        "The shared bank changed")
                bank = read_json(bank_file)
                require(bank["task_index"] == task["task_index"] and bank["search_seed"] == seed
                        and bank["preparation_seed"] == protocol["preparation_seed"], "Bank identity differs")
                mark = time.perf_counter()
                log = make_log(problem, bank, mu, seed, task["task_index"], total=TOTAL)
                search_seconds = time.perf_counter() - mark
                mark = time.perf_counter()
                _write_bounded(folder / "journal.json.gz", log, budget)
                log_write_seconds = time.perf_counter() - mark
                mark = time.perf_counter()
                checked = verify_log(log)
                verification_seconds = time.perf_counter() - mark
                require(checked["verification_status"] == "VERIFIED" and checked["new_calls"] == TOTAL - mu,
                        "Independent replay or evaluation accounting failed")
                derived = checked.pop("derived_metrics")
                bins = derived["operator_bins"]
                del derived
                _write_bounded(folder / "verification.json", checked, budget)
                _write_bounded(folder / "operator_bins.json", {"operator_bins": bins,
                               "premutation_score_checks": checked["premutation_score_checks"]}, budget)
                # The optimum enters only after the search and independent replay.
                certificate = read_json(prepared / task["task"] / "certificate.json")
                require(sha(prepared / task["task"] / "certificate.json") == task["certificate_sha256"],
                        "Exact-reference bytes differ")
                mark = time.perf_counter()
                observed = extract(log, TOTAL, certificate["optimum"], checkpoints=tuple(protocol["checkpoints"]))
                observations_seconds = time.perf_counter() - mark
                require(observed["final_best_profit"] == checked["record_profit"], "Observed record differs from replay")
                _write_bounded(folder / "observations.json.gz", observed, budget)
                names = ("journal.json.gz", "verification.json", "operator_bins.json", "observations.json.gz")
                artifact_hashes = {name: sha(folder / name) for name in names}
                record = {"status": "VERIFIED", "task": task["task"], "task_index": task["task_index"],
                          "family": family, "class_label": task["class_label"], "mu": mu, "seed": seed,
                          "total_evaluations": TOTAL, "initial_evaluations": mu, "new_evaluations": TOTAL - mu,
                          "known_start_score_validation_checks": mu,
                          "replay_score_checks": checked["independent_score_checks"],
                          "premutation_score_checks": checked["premutation_score_checks"],
                          "bank_sha256": descriptor["sha256"], "certificate_sha256": task["certificate_sha256"],
                          "artifact_hashes": artifact_hashes, "source_manifest_sha256": sha(manifest_path),
                          "workflow_commit": os.environ["GITHUB_SHA"], "workflow_run_id": os.environ["GITHUB_RUN_ID"],
                          "code_manifest_sha256": code_manifest_sha256,
                          "search_seconds": search_seconds, "log_write_seconds": log_write_seconds,
                          "verification_seconds": verification_seconds, "observations_seconds": observations_seconds}
                _write_bounded(folder / "record.json", record, budget)
                artifact_hashes["record.json"] = sha(folder / "record.json")
                timing = {"search_seconds": search_seconds, "log_write_seconds": log_write_seconds,
                          "verification_seconds": verification_seconds, "observations_seconds": observations_seconds,
                          "case_seconds": time.perf_counter() - case_started,
                          "artifact_bytes": sum(p.stat().st_size for p in folder.iterdir() if p.is_file())}
                require(timing["case_seconds"] >= sum(timing[k] for k in
                        ("search_seconds", "log_write_seconds", "verification_seconds", "observations_seconds")),
                        "Case timer omitted a component")
                row = {"task": task["task"], "task_index": task["task_index"], "family": family,
                       "class_label": task["class_label"], "mu": mu, "seed": seed,
                       "optimum": certificate["optimum"], "best": observed["final_best_profit"],
                       "events": [[event["q"], event["profit"]] for event in observed["record_events"]],
                       "checkpoints": [{"q": point["q"], "record_profit": point["record_profit"],
                                        "population_metrics": point["population_metrics"],
                                        "completed_generations": point["completed_generations"]}
                                       for point in observed["checkpoints"]],
                       "targets": observed["targets"], "completed_generations": observed["completed_generations"],
                       "duplicates": checked["duplicate_candidates"], "artifact_hashes": artifact_hashes,
                       "artifact_prefix": prefix, "bank_sha256": descriptor["sha256"],
                       "certificate_sha256": task["certificate_sha256"], "timing": timing}
                receipt = compact / "records" / task["task"] / f"seed-{seed}.json"
                _write_bounded(receipt, row, budget)
                rows.append(row)
                require(_used_bytes(output, compact) == budget["used"] <= limits["bytes"], "Shard material accounting differs")
                print(task["task"], seed, "population", mu, "VERIFIED", flush=True)
                del log, checked, observed, bins
            except Exception as error:
                failure = {"status": "FAILED_OR_INTERRUPTED", "task": task["task"], "family": family,
                           "mu": mu, "seed": seed, "completed_case_count": len(rows),
                           "error_type": type(error).__name__, "message": str(error)[:1000],
                           "traceback": traceback.format_exc(limit=8)}
                failure_path = compact / f"failure-{task['task']}-seed-{seed}.json"
                if not failure_path.exists():
                    _write_bounded(failure_path, failure, budget, emergency=True)
                raise
    require(len(rows) == 30 and len({(r["task"], r["seed"], r["mu"]) for r in rows}) == 30,
            "Verified shard is incomplete or duplicated")
    try:
        _write_bounded(compact / "compact.json", {"schema": "population-validation-100-main-shard-v1", "status": "VERIFIED",
                       "family": family, "mu": mu, "runs": rows, "raw_artifact_name": raw_name,
                       "source_manifest_sha256": sha(manifest_path), "technical_input_manifest_sha256": manifest["source_manifest_sha256"],
                       "workflow_commit": os.environ["GITHUB_SHA"], "code_manifest_sha256": code_manifest_sha256,
                       "elapsed_seconds": time.monotonic() - started, "artifact_bytes_before_manifest": budget["used"],
                       "workflow_run_id": os.environ["GITHUB_RUN_ID"]}, budget)
    except Exception as error:
        _write_bounded(compact / "failure-finalization.json", {"status": "FAILED_FINALIZATION", "family": family,
                       "mu": mu, "completed_case_count": len(rows), "error_type": type(error).__name__,
                       "message": str(error)[:1000]}, budget, emergency=True)
        raise
    require(_used_bytes(output, compact) == budget["used"] <= limits["bytes"], "Final shard material accounting differs")
    print("Shard complete:", family, "population", mu, "30/30 verified", flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    inputs = commands.add_parser("prepare")
    inputs.add_argument("--inputs", type=Path, required=True)
    inputs.add_argument("--out", type=Path, required=True)
    execution = commands.add_parser("shard")
    execution.add_argument("--prepared", type=Path, required=True)
    execution.add_argument("--family", required=True)
    execution.add_argument("--mu", type=int, choices=POPS, required=True)
    execution.add_argument("--out", type=Path, required=True)
    execution.add_argument("--compact-out", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "prepare":
        prepare(args.inputs, args.out)
    else:
        shard(args.prepared, args.family, args.mu, args.out, args.compact_out)


if __name__ == "__main__":
    main()
