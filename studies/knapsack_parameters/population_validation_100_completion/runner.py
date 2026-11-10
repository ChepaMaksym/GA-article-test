"""Retain 886 verified cases and execute only fourteen explicitly missing identities."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import time
import traceback

from .common import (HERE, ORIGINAL_RUN, ORIGINAL_COMMIT, ORIGINAL_SEAL,
                     TECHNICAL_INPUT_SEAL, guard_completion, read_json, write_json, sha, require)
from studies.knapsack_parameters.population_validation_100_main.runner import (
    _safe_file, _verify_files, _used_bytes, _write_bounded,
)
from studies.knapsack_parameters.population_validation_100_main.analysis import validate_row

TYPES = ("UC", "WC", "SC")
POPS = (10, 20, 30)
FAMILIES = tuple(f"s{i:03d}" for i in range(50, 60))
SEEDS = tuple(range(150001, 150011))
TOTAL = 100000


def expected_missing():
    return {(f"n00100-SC-{family}", seed, 10) for family, first in
            (("s050", 150007), ("s055", 150007), ("s058", 150009), ("s059", 150007))
            for seed in range(first, 150011)}


def _identity(row):
    return row["task"], row["seed"], row["mu"]


def _check_bank_and_reference(row, prepared, manifest):
    tasks = {task["task"]: task for task in manifest["tasks"]}
    task = tasks[row["task"]]
    bank = next(item for item in task["banks"] if item["seed"] == row["seed"])
    require(row["bank_sha256"] == bank["sha256"] and row["certificate_sha256"] == task["certificate_sha256"],
            "Retained record uses different paired inputs")
    certificate = read_json(prepared / row["task"] / "certificate.json")
    require(row["optimum"] == certificate["optimum"], "Retained optimum differs from the certified reference")


def load_original(prepared, compacts):
    """Load authenticated original artifacts without weakening their recorded provenance."""
    protocol = guard_completion()
    prepared, compacts = Path(prepared), Path(compacts)
    manifest_path = prepared / "manifest.json"
    manifest = read_json(manifest_path)
    prepared_sha = sha(manifest_path)
    require(manifest.get("schema") == "population-validation-100-main-inputs-v1"
            and manifest.get("status") == "PAIRED_BANKS_PREPARED" and manifest.get("main_ga_runs") == 0
            and manifest.get("source_manifest_sha256") == TECHNICAL_INPUT_SEAL,
            "Original preparation identity differs")
    _verify_files(prepared, manifest["files"])
    expected = {(f"n00100-{kind}-{family}", seed, mu) for family in FAMILIES
                for kind in TYPES for seed in SEEDS for mu in POPS}
    artifacts = {row["name"]: row for row in protocol["original_artifacts"]}
    receipt = read_json(compacts.parent / "evidence_receipt.json")
    require(receipt.get("status") == "AUTHENTICATED_31_ORIGINAL_ARCHIVES",
            "Authenticated original archive receipt is absent")
    downloaded = {row["name"]: row for row in receipt["artifacts"]}
    require(len(downloaded) == len(receipt["artifacts"]) == 31, "Archive receipt inventory differs")
    for name, row in downloaded.items():
        pinned = artifacts.get(name)
        require(pinned is not None and row.get("archive_sha256_checked") is True
                and row.get("original_run_id") == ORIGINAL_RUN and row.get("original_commit") == ORIGINAL_COMMIT
                and all(row.get(key) == pinned[key] for key in ("id", "sha256", "bytes")),
                "Downloaded archive origin differs from the pinned GitHub metadata")
        archive = compacts.parent / "archives" / (name + ".zip")
        require(archive.is_file() and archive.stat().st_size == pinned["bytes"]
                and sha(archive) == pinned["sha256"], "Original archive bytes differ")
    records, provenance, seen = [], [], set()
    expected_dirs = {f"population100-main-compact-{family}-mu{mu}-{ORIGINAL_RUN}"
                     for family in FAMILIES for mu in POPS}
    require(compacts.is_dir() and {path.name for path in compacts.iterdir() if path.is_dir()} == expected_dirs,
            "Original compact artifact inventory differs")
    for family in FAMILIES:
        for mu in POPS:
            artifact_name = f"population100-main-compact-{family}-mu{mu}-{ORIGINAL_RUN}"
            root = compacts / artifact_name
            require(artifact_name in artifacts, "Original compact archive is not pinned")
            descriptors = sorted((root / "records").rglob("seed-*.json"))
            rows = []
            for path in descriptors:
                require(not path.is_symlink() and path.resolve().is_relative_to(root.resolve()), "Unsafe retained receipt")
                row = validate_row(read_json(path), family, mu)
                require(path.relative_to(root).as_posix() == f"records/{row['task']}/seed-{row['seed']}.json",
                        "Retained receipt identity/path differs")
                _check_bank_and_reference(row, prepared, manifest)
                identity = _identity(row)
                require(identity in expected and identity not in seen, "Duplicate or unregistered retained case")
                seen.add(identity)
                rows.append(row)
            compact_file = root / "compact.json"
            failures = sorted(root.glob("failure-*.json"))
            if compact_file.is_file():
                compact = read_json(compact_file)
                require(compact.get("schema") == "population-validation-100-main-shard-v1"
                        and compact.get("status") == "VERIFIED" and compact.get("family") == family
                        and compact.get("mu") == mu and len(rows) == 30,
                        "Original completed shard differs")
                require(compact.get("workflow_commit") == ORIGINAL_COMMIT
                        and str(compact.get("workflow_run_id")) == str(ORIGINAL_RUN)
                        and compact.get("code_manifest_sha256") == ORIGINAL_SEAL
                        and compact.get("source_manifest_sha256") == prepared_sha
                        and compact.get("technical_input_manifest_sha256") == TECHNICAL_INPUT_SEAL,
                        "Original completed shard source or run differs")
                require(compact.get("raw_artifact_name") == f"population100-main-raw-{family}-mu{mu}-{ORIGINAL_RUN}",
                        "Original raw archive identity differs")
                full = {_identity(row): row for row in compact["runs"]}
                require(len(full) == 30 and full == {_identity(row): row for row in rows} and not failures,
                        "Original per-case receipts differ from the completed shard")
                state = "VERIFIED_COMPLETE_ORIGINAL_SHARD"
            else:
                allowed = {item for item in expected_missing() if item[0].endswith(family) and item[2] == mu}
                require(allowed and len(rows) == 30 - len(allowed) and len(failures) == 1,
                        "Unexpected incomplete original shard")
                failure = read_json(failures[0])
                require(failure.get("status") == "FAILED_OR_INTERRUPTED" and failure.get("family") == family
                        and failure.get("mu") == mu and failure.get("completed_case_count") == len(rows)
                        and failure.get("error_type") == "ValueError"
                        and failure.get("message") == "Time reserve reached; preserve and resume only missing identities",
                        "Original partial shard did not stop for the recorded time reserve")
                require((failure["task"], failure["seed"], mu) in allowed,
                        "Interrupted identity differs from the missing-case ledger")
                state = "VERIFIED_ORIGINAL_RECEIPTS_FROM_TIME_LIMITED_SHARD"
            records.extend(rows)
            provenance.append({"family": family, "mu": mu, "retained_runs": len(rows), "status": state,
                               "artifact_name": artifact_name, "artifact_id": artifacts[artifact_name]["id"],
                               "archive_sha256": artifacts[artifact_name]["sha256"],
                               "original_run_id": ORIGINAL_RUN, "original_commit": ORIGINAL_COMMIT,
                               "original_code_manifest_sha256": ORIGINAL_SEAL,
                               "prepared_manifest_sha256": prepared_sha,
                               "receipt_sha256": {path.relative_to(root).as_posix(): sha(path) for path in descriptors}})
    missing = expected - seen
    require(len(records) == len(seen) == 886 and missing == expected_missing(),
            "Original records do not imply exactly the fourteen registered missing identities")
    missing_rows = [{"task": task, "family": task.rsplit("-", 1)[1], "seed": seed, "mu": mu}
                    for task, seed, mu in sorted(missing)]
    return records, provenance, missing_rows, prepared_sha


def prepare(prepared, compacts, out):
    records, provenance, missing, prepared_sha = load_original(prepared, compacts)
    out = Path(out)
    require(not out.exists(), "Retain the previous completed-case ledger")
    out.mkdir(parents=True, exist_ok=False)
    origin = {"original_run_id": ORIGINAL_RUN, "original_commit": ORIGINAL_COMMIT,
              "original_code_manifest_sha256": ORIGINAL_SEAL}
    write_json(out / "completed_records.json", {"schema": "population-validation-100-completion-original-v1",
               "status": "VERIFIED_886_RETAINED", "records": records, "provenance": provenance,
               "prepared_manifest_sha256": prepared_sha, **origin})
    write_json(out / "ledger.json", {"schema": "population-validation-100-completion-ledger-v1",
               "status": "MISSING_IDENTITIES_FROZEN", "completed": 886, "missing": missing,
               "prepared_manifest_sha256": prepared_sha, "original_compact_provenance": provenance,
               "completed_records_sha256": sha(out / "completed_records.json"), **origin})
    print("Retained 886 verified cases; froze fourteen missing identities; no new search.", flush=True)


def recover(prepared, ledger, family, out, compact_out):
    """Run missing cases with the unchanged, sealed search and independent verifier."""
    protocol = guard_completion()
    prepared, ledger, output, compact = Path(prepared), Path(ledger), Path(out), Path(compact_out)
    require(family in ("s050", "s055", "s058", "s059"), "Family is not in the missing-case ledger")
    require(not output.exists() and not compact.exists(), "Retain prior completion evidence")
    require(not output.resolve().is_relative_to(compact.resolve()) and not compact.resolve().is_relative_to(output.resolve()),
            "Raw and compact completion directories must be disjoint")
    ledger_file = ledger / "ledger.json" if ledger.is_dir() else ledger
    frozen = read_json(ledger_file)
    require(frozen.get("schema") == "population-validation-100-completion-ledger-v1"
            and frozen.get("status") == "MISSING_IDENTITIES_FROZEN" and frozen.get("completed") == 886
            and frozen.get("original_run_id") == ORIGINAL_RUN and frozen.get("original_commit") == ORIGINAL_COMMIT
            and frozen.get("original_code_manifest_sha256") == ORIGINAL_SEAL,
            "Completion ledger identity differs")
    require(sha(ledger_file.parent / "completed_records.json") == frozen["completed_records_sha256"],
            "Retained completed records differ")
    require({_identity(row) for row in frozen["missing"]} == expected_missing() and len(frozen["missing"]) == 14,
            "Completion ledger includes a completed or unknown identity")
    manifest_path = prepared / "manifest.json"
    manifest = read_json(manifest_path)
    require(sha(manifest_path) == frozen["prepared_manifest_sha256"]
            and manifest.get("source_manifest_sha256") == TECHNICAL_INPUT_SEAL,
            "Completion paired banks differ from the original run")
    _verify_files(prepared, manifest["files"])
    tasks = {row["task"]: row for row in manifest["tasks"]}
    missing = [row for row in frozen["missing"] if row["family"] == family]
    require(len(missing) == (2 if family == "s058" else 4), "Completion family count differs")
    output.mkdir(parents=True, exist_ok=False)
    compact.mkdir(parents=True, exist_ok=False)
    limits = protocol["shard_limits"]
    require(limits["seconds"] <= 420 and limits["bytes"] <= 60 * 1024 * 1024,
            "Completion shard allocation exceeds the registered sub-allocation")
    budget = {"limit": limits["bytes"], "used": 0}
    started, rows = time.monotonic(), []
    run_id, commit = os.environ["GITHUB_RUN_ID"], os.environ["GITHUB_SHA"]
    code_seal = sha(HERE / "source_manifest.json")
    raw_name = f"population100-completion-raw-{family}-{run_id}"
    from studies.knapsack_parameters.population_validation_100.pilot import make_log
    from studies.knapsack_parameters.crossover_population.verification import verify_log
    from studies.knapsack_parameters.crossover_population.observations import extract
    for identity in missing:
        task_name, seed, mu = identity["task"], identity["seed"], identity["mu"]
        try:
            require(time.monotonic() - started < limits["seconds"] - limits["reserve_seconds"],
                    "Completion time reserve reached; retain finished identities")
            require(budget["used"] < limits["bytes"] - limits["reserve_bytes"],
                    "Completion artifact reserve reached; retain finished identities")
            task = tasks[task_name]
            descriptor = next(row for row in task["banks"] if row["seed"] == seed)
            problem = read_json(prepared / task_name / "problem.json")
            bank_file = _safe_file(prepared, descriptor["path"])
            require(sha(bank_file) == descriptor["sha256"], "Completion initial bank differs")
            bank = read_json(bank_file)
            require(bank["task_index"] == task["task_index"] and bank["search_seed"] == seed
                    and bank["preparation_seed"] == 150000, "Completion bank identity differs")
            folder = output / task_name / f"seed-{seed}"
            folder.mkdir(parents=True, exist_ok=False)
            case_started = time.perf_counter()
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
                    "Completion replay or evaluation accounting differs")
            derived = checked.pop("derived_metrics")
            bins = derived["operator_bins"]
            del derived
            _write_bounded(folder / "verification.json", checked, budget)
            _write_bounded(folder / "operator_bins.json", {"operator_bins": bins,
                           "premutation_score_checks": checked["premutation_score_checks"]}, budget)
            certificate = read_json(prepared / task_name / "certificate.json")
            require(sha(prepared / task_name / "certificate.json") == task["certificate_sha256"], "Completion reference differs")
            mark = time.perf_counter()
            observed = extract(log, TOTAL, certificate["optimum"], checkpoints=(5000, 10000, 20000, 50000, 100000))
            observations_seconds = time.perf_counter() - mark
            require(observed["final_best_profit"] == checked["record_profit"], "Completion observation differs from replay")
            _write_bounded(folder / "observations.json.gz", observed, budget)
            names = ("journal.json.gz", "verification.json", "operator_bins.json", "observations.json.gz")
            artifact_hashes = {name: sha(folder / name) for name in names}
            record = {"status": "VERIFIED", "task": task_name, "task_index": task["task_index"],
                      "family": family, "class_label": "SC", "mu": mu, "seed": seed,
                      "total_evaluations": TOTAL, "initial_evaluations": mu, "new_evaluations": TOTAL - mu,
                      "known_start_score_validation_checks": mu, "replay_score_checks": checked["independent_score_checks"],
                      "premutation_score_checks": checked["premutation_score_checks"],
                      "bank_sha256": descriptor["sha256"], "certificate_sha256": task["certificate_sha256"],
                      "artifact_hashes": artifact_hashes, "source_manifest_sha256": sha(manifest_path),
                      "workflow_commit": commit, "workflow_run_id": run_id, "code_manifest_sha256": code_seal,
                      "original_run_id": ORIGINAL_RUN, "ledger_sha256": sha(ledger_file),
                      "search_seconds": search_seconds, "log_write_seconds": log_write_seconds,
                      "verification_seconds": verification_seconds, "observations_seconds": observations_seconds}
            _write_bounded(folder / "record.json", record, budget)
            artifact_hashes["record.json"] = sha(folder / "record.json")
            timing = {"search_seconds": search_seconds, "log_write_seconds": log_write_seconds,
                      "verification_seconds": verification_seconds, "observations_seconds": observations_seconds,
                      "case_seconds": time.perf_counter() - case_started,
                      "artifact_bytes": sum(path.stat().st_size for path in folder.iterdir() if path.is_file())}
            row = {"task": task_name, "task_index": task["task_index"], "family": family, "class_label": "SC",
                   "mu": mu, "seed": seed, "optimum": certificate["optimum"], "best": observed["final_best_profit"],
                   "events": [[event["q"], event["profit"]] for event in observed["record_events"]],
                   "checkpoints": [{"q": point["q"], "record_profit": point["record_profit"],
                                    "population_metrics": point["population_metrics"],
                                    "completed_generations": point["completed_generations"]} for point in observed["checkpoints"]],
                   "targets": observed["targets"], "completed_generations": observed["completed_generations"],
                   "duplicates": checked["duplicate_candidates"], "artifact_hashes": artifact_hashes,
                   "artifact_prefix": f"{task_name}/seed-{seed}", "bank_sha256": descriptor["sha256"],
                   "certificate_sha256": task["certificate_sha256"], "timing": timing}
            validate_row(row, family, mu)
            _write_bounded(compact / "records" / task_name / f"seed-{seed}.json", row, budget)
            rows.append(row)
            require(_used_bytes(output, compact) == budget["used"] <= limits["bytes"], "Completion output accounting differs")
            print(task_name, seed, "population", mu, "COMPLETION VERIFIED", flush=True)
            del log, checked, observed, bins
        except Exception as error:
            _write_bounded(compact / f"failure-{task_name}-seed-{seed}.json",
                           {"status": "FAILED_OR_INTERRUPTED", "task": task_name, "seed": seed, "mu": mu,
                            "completed_case_count": len(rows), "error_type": type(error).__name__,
                            "message": str(error)[:1000], "traceback": traceback.format_exc(limit=8)}, budget, emergency=True)
            raise
    require({_identity(row) for row in rows} == {_identity(row) for row in missing}, "Completion family is incomplete")
    _write_bounded(compact / "completion.json", {"schema": "population-validation-100-completion-shard-v1",
                   "status": "VERIFIED", "family": family, "mu": 10, "runs": rows,
                   "raw_artifact_name": raw_name, "source_manifest_sha256": sha(manifest_path),
                   "prepared_manifest_sha256": sha(manifest_path), "original_run_id": ORIGINAL_RUN,
                   "workflow_commit": commit, "workflow_run_id": run_id, "code_manifest_sha256": code_seal,
                   "ledger_sha256": sha(ledger_file), "elapsed_seconds": time.monotonic() - started}, budget)
    require(_used_bytes(output, compact) == budget["used"] <= limits["bytes"], "Final completion output accounting differs")
    print("Completion family verified:", family, len(rows), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    creation = commands.add_parser("prepare")
    creation.add_argument("--prepared", type=Path, required=True)
    creation.add_argument("--compacts", type=Path, required=True)
    creation.add_argument("--out", type=Path, required=True)
    execution = commands.add_parser("recover")
    execution.add_argument("--prepared", type=Path, required=True)
    execution.add_argument("--ledger", type=Path, required=True)
    execution.add_argument("--family", required=True)
    execution.add_argument("--out", type=Path, required=True)
    execution.add_argument("--compact-out", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "prepare":
        prepare(args.prepared, args.compacts, args.out)
    else:
        recover(args.prepared, args.ledger, args.family, args.out, args.compact_out)


if __name__ == "__main__":
    main()
