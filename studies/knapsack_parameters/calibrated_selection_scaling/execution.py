"""Execute missing frozen identities, independently replay and atomically retain.

Each worker commits its complete compressed journal, observations and receipt
before receiving another case. An orphan journal can be adopted only when its
full frozen identity and replay pass; a started case without a journal requires
a separate recovery audit. Existing evidence is never silently overwritten.
"""
from __future__ import annotations

import argparse
from concurrent.futures import FIRST_COMPLETED, ProcessPoolExecutor, wait
from copy import deepcopy
import multiprocessing
import os
from pathlib import Path
import re
from time import perf_counter_ns

from . import configuration as config
from .common import (ROOT, canonical_sha256, ci_only, guard_stage, read_json, read_log,
                     require, write_json, write_log)
from .observations import extract
from .preparation import identity, load_case, load_reference, problem_sha256
from .resources import MAX_WORKERS, require_enclosure


ENVELOPE_SCHEMA = "calibrated-selection-run-v1"
RECEIPT_SCHEMA = "calibrated-selection-run-receipt-v1"
REGISTRY_SCHEMA = "calibrated-selection-execution-registry-v1"
TECHNICAL_SHARD_BYTES = 256 * 1024 ** 2


def _files(output, case):
    identifier = case["case_id"]
    require(type(identifier) is str and re.fullmatch(r"[A-Za-z0-9_-]+", identifier), "Unsafe case identifier")
    root = Path(output)
    return {"log": root / (identifier + ".json.gz"),
            "candidate": root / (identifier + ".candidate.json.gz"),
            "observations": root / (identifier + ".observations.json"),
            "receipt": root / (identifier + ".receipt.json"),
            "started": root / (identifier + ".started.json")}


def _file_descriptor(root, path):
    return {"path": Path(path).relative_to(root).as_posix(), **identity(path)}


def _case_identity(case, problem, bank, inputs):
    return {"case": deepcopy(case), "problem_sha256": problem_sha256(problem),
            "bank_sha256": canonical_sha256(bank),
            "prepared_registry": identity(Path(inputs) / "registry.json"),
            "source_manifest_sha256": identity(ROOT / "source_manifest.json")["sha256"],
            "configuration_contract": config.CONTRACT}


def _bind(log, case, problem, bank):
    mu = case["initial_parameters"]["target_mu"]
    require(log.get("schema") == config.LOG_SCHEMA and log.get("configuration_contract") == config.CONTRACT and
            log.get("problem") == problem and log.get("profile") == case["profile"] and
            log.get("initial_parameters") == case["initial_parameters"] and
            log.get("initial_population_size") == mu and
            log.get("budget") == case["total_evaluations"] - mu and
            log.get("initial_masks") == bank["masks"][:mu] and
            log.get("initial_scores") == bank["scores"][:mu] and
            log.get("rng_initial") == bank["rng_states"], "Journal differs from its full frozen case identity")


def _compact_verification(verification):
    # The raw journal and reproducible observations retain detailed rows.
    return {key: deepcopy(value) for key, value in verification.items() if key != "derived_metrics"}


def _sync_directory(directory):
    descriptor = os.open(directory, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _read_envelope(path, expected):
    envelope = read_log(path)
    require(type(envelope) is dict and set(envelope) == {"schema", "case", "identity", "log"} and
            envelope["schema"] == ENVELOPE_SCHEMA and envelope["case"] == expected["case"] and
            envelope["identity"] == expected, "Compressed journal has a foreign frozen identity")
    return envelope["log"]


def _validate_receipt(receipt, expected, files, output):
    require(receipt.get("schema") == RECEIPT_SCHEMA and receipt.get("status") == "VERIFIED_ATOMICALLY_RETAINED" and
            receipt.get("identity") == expected and receipt.get("identity_sha256") == canonical_sha256(expected) and
            receipt.get("case") == expected["case"], "Foreign, incomplete or stale retained receipt")
    for key in ("log", "observations"):
        require(files[key].is_file() and receipt[key] == _file_descriptor(output, files[key]),
                "Retained " + key + " checksum changed")


def _case_bytes(files):
    return sum(path.stat().st_size for path in files.values() if path.is_file())


def _retain_observations(log, verification, case, expected, files, inputs, output, timings, enclosure,
                         recovered, byte_ceiling, case_started):
    observation_started = perf_counter_ns()
    optimum = load_reference(inputs, case["task_id"])
    observations = extract(log, case["total_evaluations"], optimum)
    observation_ns = perf_counter_ns() - observation_started
    if files["observations"].exists():
        require(read_json(files["observations"]) == observations, "Orphan observation differs from verified journal")
    else:
        write_json(files["observations"], observations,
                   max_bytes=max(0, byte_ceiling - _case_bytes(files) - 64 * 1024))
    timings["observation"] = observation_ns
    timings["total"] = perf_counter_ns() - case_started
    receipt = {"schema": RECEIPT_SCHEMA, "status": "VERIFIED_ATOMICALLY_RETAINED", "case": deepcopy(case),
               "identity": expected, "identity_sha256": canonical_sha256(expected),
               "source_manifest_sha256": expected["source_manifest_sha256"],
               "log": _file_descriptor(output, files["log"]),
               "observations": _file_descriptor(output, files["observations"]),
               "verification": _compact_verification(verification), "resource_enclosure": enclosure,
               "timing_ns": timings, "recovered_without_search": recovered,
               "total_timing_scope": "case_load_through_observation_persistence_before_receipt_commit",
               "new_search_runs": 0 if recovered else 1,
               "logical_initial_evaluations": case["initial_parameters"]["target_mu"],
               "logical_total_evaluations": case["total_evaluations"],
               "logical_offspring_evaluations": log["budget"],
               "compressed_journal_bytes": files["log"].stat().st_size,
               "best_profit": observations["final_best_profit"], "targets": observations["targets"]}
    write_json(files["receipt"], receipt, max_bytes=max(0, byte_ceiling - _case_bytes(files)))
    _sync_directory(output)
    _validate_receipt(read_json(files["receipt"]), expected, files, output)
    return receipt


def _run_one(case, inputs, output, byte_ceiling):
    """One process owns one case and all its commits; no shared worker files."""
    ci_only()
    guard_stage(case["stage"])
    enclosure = require_enclosure()
    from .search import execute_case
    from .verification import verify_log
    started = perf_counter_ns()
    output = Path(output)
    files = _files(output, case)
    problem, bank = load_case(inputs, case)
    expected = _case_identity(case, problem, bank, inputs)
    if files["receipt"].exists():
        receipt = read_json(files["receipt"])
        _validate_receipt(receipt, expected, files, output)
        log = _read_envelope(files["log"], expected)
        _bind(log, case, problem, bank)
        verification = verify_log(log)
        require(receipt["verification"] == _compact_verification(verification), "Retained verification differs on replay")
        require(read_json(files["observations"]) == extract(log, case["total_evaluations"], load_reference(inputs, case["task_id"])),
                "Retained observations differ on reconstruction")
        return receipt
    if files["log"].exists() or files["candidate"].exists():
        replay_started = perf_counter_ns()
        retained = files["log"] if files["log"].exists() else files["candidate"]
        log = _read_envelope(retained, expected)
        _bind(log, case, problem, bank)
        verification = verify_log(log)
        require(verification.get("verification_status") == "VERIFIED", "Independent orphan replay did not pass")
        if retained == files["candidate"]:
            require(not files["log"].exists(), "Retained journal overwrite refused")
            os.replace(retained, files["log"])
            _sync_directory(output)
        timings = {"search": 0, "replay": perf_counter_ns() - replay_started, "compression": 0,
                   "total": perf_counter_ns() - started}
        return _retain_observations(log, verification, case, expected, files, inputs, output,
                                    timings, enclosure, recovered=True, byte_ceiling=byte_ceiling,
                                    case_started=started)
    require(not files["started"].exists() and not files["observations"].exists(),
            "Started identity lacks a retained journal; a separate recovery resource audit is required")
    write_json(files["started"], {"schema": RECEIPT_SCHEMA, "status": "SEARCH_STARTED", "identity": expected,
                                  "identity_sha256": canonical_sha256(expected)})
    search_started = perf_counter_ns()
    log = execute_case(case, problem, bank)
    search_ns = perf_counter_ns() - search_started
    _bind(log, case, problem, bank)
    envelope = {"schema": ENVELOPE_SCHEMA, "case": deepcopy(case), "identity": expected, "log": log}
    pending = files["candidate"]
    require(not pending.exists(), "A previous unfinished serialization requires a recovery audit")
    compression_started = perf_counter_ns()
    # Raw candidate evidence survives independent replay failure or timeout.
    write_log(pending, envelope, max_bytes=max(0, byte_ceiling - _case_bytes(files) - 64 * 1024))
    log = _read_envelope(pending, expected)
    _bind(log, case, problem, bank)
    compression_ns = perf_counter_ns() - compression_started
    replay_started = perf_counter_ns()
    verification = verify_log(log)
    replay_ns = perf_counter_ns() - replay_started
    require(verification.get("verification_status") == "VERIFIED", "Independent journal replay did not pass")
    require(not files["log"].exists(), "Retained journal overwrite refused")
    os.replace(pending, files["log"])
    _sync_directory(output)
    timings = {"search": search_ns, "replay": replay_ns, "compression": compression_ns,
               "total": perf_counter_ns() - started}
    return _retain_observations(log, verification, case, expected, files, inputs, output,
                                timings, enclosure, recovered=False, byte_ceiling=byte_ceiling,
                                case_started=started)


def _registry(output, stage, selected, receipts, *, status, error=None):
    rows = sorted(receipts, key=lambda row: row["case"]["case_id"])
    registry = {"schema": REGISTRY_SCHEMA, "status": status, "stage": stage,
                "expected_cases": [case["case_id"] for case in selected], "receipts": rows,
                "completed_cases": len(rows), "expected_count": len(selected),
                "source_manifest_sha256": identity(ROOT / "source_manifest.json")["sha256"],
                "compressed_journal_bytes": sum(row["compressed_journal_bytes"] for row in rows),
                "timing_ns": {name: sum(row["timing_ns"].get(name, 0) for row in rows)
                              for name in ("search", "replay", "compression", "observation", "total")}}
    if error is not None:
        registry["error"] = {"type": type(error).__name__, "message": str(error)}
    write_json(Path(output) / "execution_registry.json", registry)
    return registry


def run_cases(stage, inputs, output, *, workers=2, n=None, class_label=None, case_ids=None, source_identity=None):
    """Validate caches and run only missing exact identities, with two workers max."""
    ci_only()
    guard_stage(stage)
    require_enclosure(workers=workers)
    require(type(workers) is int and 1 <= workers <= MAX_WORKERS, "At most two workers are permitted")
    require(stage in ("technical", "main"), "Unknown execution stage")
    selected = config.technical_cases() if stage == "technical" else config.main_cases()
    if n is not None:
        require(n in (100, 500), "Unknown dimension filter")
        selected = [case for case in selected if case["n"] == n]
    if class_label is not None:
        require(class_label in ("UC", "WC", "SC"), "Unknown class filter")
        selected = [case for case in selected if case["class_label"] == class_label]
    if case_ids is not None:
        require(type(case_ids) is list and len(case_ids) == len(set(case_ids)) and
                set(case_ids) <= {case["case_id"] for case in selected}, "Foreign or repeated recovery identity")
        selected = [case for case in selected if case["case_id"] in case_ids]
    require(selected, "No registered case selected")
    source = identity(ROOT / "source_manifest.json")
    require(source_identity is None or source_identity in (source, source["sha256"]), "Requested source seal differs")
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=True)
    lock = output / "execution.lock"
    require(not lock.exists(), "An execution lock needs recovery review before reuse")
    with lock.open("x", encoding="ascii") as stream:
        stream.write(str(os.getpid()))
    receipts = []
    authority = read_json(ROOT / f"{stage}_authorization.json")
    byte_ceiling = min(authority["artifact_bytes"], TECHNICAL_SHARD_BYTES) if stage == "technical" else authority["artifact_bytes"]
    # Disjoint reservations make concurrent worker writes safe without a shared
    # mutable byte counter. Leave space for the duplicated aggregate receipts.
    per_case_ceiling = (byte_ceiling - 2 * 1024 ** 2) // len(selected)
    try:
        _registry(output, stage, selected, receipts, status="INCOMPLETE")
        if workers == 1:
            for case in selected:
                receipts.append(_run_one(case, str(inputs), str(output), per_case_ceiling))
                _registry(output, stage, selected, receipts, status="INCOMPLETE")
        else:
            with ProcessPoolExecutor(max_workers=workers, mp_context=multiprocessing.get_context("spawn"),
                                     max_tasks_per_child=1) as pool:
                remaining = iter(selected)
                active = {}
                for _ in range(workers):
                    case = next(remaining, None)
                    if case is not None:
                        active[pool.submit(_run_one, case, str(inputs), str(output), per_case_ceiling)] = case
                while active:
                    completed, _ = wait(active, return_when=FIRST_COMPLETED)
                    for future in completed:
                        active.pop(future)
                        receipts.append(future.result())
                        _registry(output, stage, selected, receipts, status="INCOMPLETE")
                        case = next(remaining, None)
                        if case is not None:
                            active[pool.submit(_run_one, case, str(inputs), str(output), per_case_ceiling)] = case
        require(len(receipts) == len(selected), "Execution rectangle is incomplete")
        retained_bytes = sum(path.stat().st_size for path in output.rglob("*") if path.is_file())
        require(retained_bytes <= byte_ceiling, "Retained output exceeds the registered artifact ceiling")
        return _registry(output, stage, selected, receipts, status="COMPLETE_VERIFIED")
    except Exception as error:
        _registry(output, stage, selected, receipts, status="FAILED_RETAINED_PARTIAL_EVIDENCE", error=error)
        raise
    finally:
        lock.unlink()


def verify_directory(stage, inputs, output):
    """Independent later job: require a complete registry and replay every log."""
    ci_only()
    guard_stage(stage)
    require_enclosure()
    root = Path(output)
    registry = read_json(root / "execution_registry.json")
    require(registry.get("schema") == REGISTRY_SCHEMA and registry.get("status") == "COMPLETE_VERIFIED" and
            registry.get("stage") == stage and registry.get("completed_cases") == registry.get("expected_count"),
            "Execution registry is incomplete")
    known = config.technical_cases() if stage == "technical" else config.main_cases()
    expected = registry["expected_cases"]
    require(len(expected) == len(set(expected)) and set(expected) <= {case["case_id"] for case in known},
            "Registry contains foreign or repeated identities")
    receipts = []
    for case in known:
        if case["case_id"] in expected:
            require(_files(root, case)["receipt"].is_file(), "Missing retained receipt")
            receipts.append(_run_one(case, str(inputs), str(root), 0))
    require(receipts == sorted(registry["receipts"], key=lambda row: known.index(row["case"])),
            "Registry receipts differ from retained identities")
    return {"schema": REGISTRY_SCHEMA, "status": "INDEPENDENT_REPLAY_VERIFIED", "stage": stage,
            "verified_cases": len(receipts), "source_manifest_sha256": registry["source_manifest_sha256"],
            "search_runs_performed": 0, "registry_identity": identity(root / "execution_registry.json")}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage", choices=("technical", "main"), required=True)
    parser.add_argument("--inputs", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--workers", type=int, default=2)
    parser.add_argument("--n", type=int, choices=(100, 500))
    parser.add_argument("--class-label", choices=("UC", "WC", "SC"))
    parser.add_argument("--case-id", action="append")
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args()
    if args.verify_only:
        receipt = verify_directory(args.stage, args.inputs, args.output)
        write_json(Path(args.output) / "independent_replay_receipt.json", receipt)
    else:
        run_cases(args.stage, args.inputs, args.output, workers=args.workers, n=args.n,
                  class_label=args.class_label, case_ids=args.case_id)


if __name__ == "__main__":
    main()
