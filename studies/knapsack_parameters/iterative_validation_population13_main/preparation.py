"""Retain the original paired inputs for the ninety-case population-13 study.

Only an admitted CI job can download, validate, or prepare inputs.  No bank is
generated, no exact solver is called, and this module never invokes the GA.
The old preparation manifest is historical provenance, not a new holdout audit.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
from hashlib import sha256
import json
import os
from pathlib import Path
import tempfile
import time
from zipfile import ZipFile

from .common import ROOT, descriptor, guard_main, registered_cases
from studies.knapsack_parameters.population_validation_100.common import read_json, require, require_ci, sha
from studies.knapsack_parameters.population_validation_100_main.runner import _used_bytes, _write_bounded
from studies.knapsack_parameters.iterative_validation_population13.transport import (
    download_archive, safe_relative, validate_members,
)


SOURCE_COMMIT = "c5bea0df8169749caaba5ce7dfcf21437aa1ca5c"
ORIGINAL_MANIFEST_SHA256 = "f29b9c33def8e74adbf13aeabda1d6851ca3d64258468640ceba6968f3e4d96d"
SOURCE_REGISTRY = "studies/knapsack_parameters/population_validation_100/data/source_registry.json"
CHANNELS = ("initialization", "selection", "branch", "crossover", "mutation", "ties")
ORIGIN_ARTIFACT = {
    "id": 13762967913,
    "name": "population100-main-prepared-42813784277",
    "bytes": 574487,
    "sha256": "ff19ca444ea38399bd30d913f18e6e56affa358f5a293bb84ddfb906092e75e7",
    "run_id": 42813784277,
    "commit": "653b7a3f9c5e66d31ec8ca93fb4e710bd0078ff8",
}


def original_inventory(manifest, member_names=None):
    """Bind the retained 30-task/300-bank inventory before selecting 90 banks."""
    expected = {row["task"]: row for row in registered_cases()}
    require(type(manifest) is dict
            and manifest.get("schema") == "population-validation-100-main-inputs-v1"
            and manifest.get("status") == "PAIRED_BANKS_PREPARED"
            and manifest.get("source_commit") == SOURCE_COMMIT
            and manifest.get("main_ga_runs") == 0
            and manifest.get("bank_count") == 300 and manifest.get("bank_size") == 30,
            "Original paired preparation identity differs")
    entries, tasks = manifest.get("files"), manifest.get("tasks")
    require(type(entries) is list and len(entries) == 390
            and type(tasks) is list and len(tasks) == 30,
            "Original preparation inventory is incomplete")
    files = {}
    for row in entries:
        require(type(row) is dict, "Original file descriptor is malformed")
        name = row.get("path")
        safe_relative(name)
        require(name not in files and type(row.get("bytes")) is int and row["bytes"] > 0
                and type(row.get("sha256")) is str and len(row["sha256"]) == 64
                and all(c in "0123456789abcdef" for c in row["sha256"]),
                "Duplicate or malformed original file descriptor")
        files[name] = row
    if member_names is not None:
        require(set(member_names) == set(files) | {"manifest.json"},
                "Original ZIP and manifest inventories differ")
    by_task = {}
    required_paths = set()
    for row in tasks:
        require(type(row) is dict and row.get("task") in expected
                and row["task"] not in by_task, "Unknown or duplicate original task")
        task, fixed = row["task"], expected[row["task"]]
        require(all(type(row.get(k)) is type(fixed[k]) and row[k] == fixed[k]
                    for k in ("task_index", "family", "class_label")),
                "Original task index or family differs")
        banks = row.get("banks")
        require(type(banks) is list and len(banks) == 10
                and {b.get("seed") for b in banks if type(b) is dict} == set(range(150001, 150011)),
                "Original task must retain ten uniquely identified banks")
        for name in ("problem.json", "certificate.json", "source.kp"):
            required_paths.add(task + "/" + name)
        require(task + "/certificate.json" in files
                and files[task + "/certificate.json"]["sha256"] == row.get("certificate_sha256"),
                "Original certificate descriptor differs")
        for bank in banks:
            path = task + "/banks/seed-" + str(bank["seed"]) + ".json"
            require(bank.get("path") == path and path in files
                    and all(bank.get(k) == files[path][k] for k in ("bytes", "sha256")),
                    "Original bank descriptor differs")
            required_paths.add(path)
        by_task[task] = row
    require(set(by_task) == set(expected) and set(files) == required_paths,
            "Original task/file inventory differs from the registered corpus")
    return files, by_task


def selected_paths():
    """Select shared source files and exactly the registered bank prefixes."""
    return {case["task"] + "/" + name for case in registered_cases()
            for name in ("problem.json", "certificate.json", "source.kp")}


def selected_members():
    paths = selected_paths()
    paths.update(case["task"] + "/banks/seed-" + str(case["seed"]) + ".json"
                 for case in registered_cases())
    require(len(paths) == 180, "Exactly 180 original files are required")
    return paths


def validate_bank(problem, bank, case):
    """Recheck retained scores and six initial RNG states without generation."""
    require_ci()
    require(type(bank) is dict
            and all(type(bank.get(key)) is int for key in ("task_index", "search_seed", "preparation_seed"))
            and bank.get("task_index") == case["task_index"]
            and bank.get("search_seed") == case["seed"]
            and bank.get("preparation_seed") == 150000
            and bank.get("physical_initial_score_checks") == 30,
            "Original bank identity differs")
    masks, scores = bank.get("masks"), bank.get("scores")
    require(type(masks) is list and type(scores) is list and len(masks) == len(scores) == 30
            and masks[0] == "0" * 100, "Original thirty-mask bank is required")
    from studies.knapsack_parameters.population_validation_100.preparation import score
    for mask, value in zip(masks, scores, strict=True):
        require(type(value) is dict and set(value) == {"weight", "profit", "feasible"}
                and type(value["weight"]) is int and type(value["profit"]) is int
                and type(value["feasible"]) is bool and score(problem, mask) == value,
                "Retained bank mask or score differs")
    from studies.knapsack_parameters.crossover_population.program.ga_core import create_random_generators
    states = {name: deepcopy(generator.bit_generator.state)
              for name, generator in create_random_generators(case["seed"], case["task_index"], 0).items()}
    require(type(bank.get("rng_states")) is dict and set(bank["rng_states"]) == set(CHANNELS)
            and bank["rng_states"] == states, "Original six initial generator states differ")
    return {"bank_score_checks": 30, "rng_state_checks": 6}


def _validate_task(problem, certificate, raw, source_entry, original):
    from studies.knapsack_parameters.population_validation_100.preparation import validate_source
    from studies.knapsack_parameters.population_size_study.inputs import problem_sha256
    from studies.knapsack_parameters.iterative_validation_population13.preparation import validate_retained_certificate
    require(type(problem) is dict and set(problem) == {"n", "weights", "profits", "capacity"}
            and problem.get("n") == 100 and validate_source(raw, source_entry) == problem
            and problem_sha256(problem) == original["problem_sha256"],
            "Retained raw source and problem identity differ")
    validate_retained_certificate(problem, certificate, raw)


def prepare(out, authorization_id=None):
    """Authenticate the pinned source ZIP and copy 90 existing paired banks."""
    protocol, authorization = guard_main(authorization_id)
    output = Path(out)
    require(not output.exists(), "Preserve completed or interrupted preparation")
    started = time.perf_counter()
    budget = {"limit": protocol["limits"]["preparation_artifact_bytes"], "used": 0}
    try:
        token = os.environ.get("GITHUB_TOKEN", "")
        require(bool(token), "Read-only GitHub artifact token is absent")
        registry_path = ROOT / SOURCE_REGISTRY
        registry = read_json(registry_path)
        sources = {row["task_id"]: row for row in registry["main_cases"]}
        require(registry.get("source_commit") == SOURCE_COMMIT
                and len(sources) == 30 and set(sources) == {r["task"] for r in registered_cases()},
                "Pinned source registry differs")
        with tempfile.TemporaryDirectory(prefix="population13-main-original-") as temporary:
            archive_path = Path(temporary) / "prepared.zip"
            origin = download_archive(ORIGIN_ARTIFACT, token, archive_path)
            with ZipFile(archive_path) as archive:
                members = validate_members(archive)
                require("manifest.json" in members and members["manifest.json"].file_size <= 256 * 1024,
                        "Original preparation manifest is missing or oversized")
                original_raw = archive.read("manifest.json")
                require(sha256(original_raw).hexdigest() == ORIGINAL_MANIFEST_SHA256,
                        "Original paired preparation manifest bytes differ")
                original = json.loads(original_raw)
                files, tasks = original_inventory(original, members)
                retained = {}
                for name in sorted(selected_members()):
                    entry = files[name]
                    require(members[name].file_size == entry["bytes"] <= 256 * 1024,
                            "Selected original member length differs")
                    raw = archive.read(name)
                    require(len(raw) == entry["bytes"] and sha256(raw).hexdigest() == entry["sha256"],
                            "Selected original member SHA256 differs")
                    retained[name] = raw
            # Resolve and validate the entire corpus before creating an input tree.
            problem_by_task = {}
            for task in tasks:
                problem = json.loads(retained[task + "/problem.json"])
                certificate = json.loads(retained[task + "/certificate.json"])
                _validate_task(problem, certificate, retained[task + "/source.kp"], sources[task], tasks[task])
                problem_by_task[task] = problem
            checks = {"bank_score_checks": 0, "rng_state_checks": 0}
            for case in registered_cases():
                bank = json.loads(retained[case["task"] + "/banks/seed-" + str(case["seed"]) + ".json"])
                current = validate_bank(problem_by_task[case["task"]], bank, case)
                for key in checks:
                    checks[key] += current[key]
            output.mkdir(parents=True, exist_ok=False)
            for name, raw in retained.items():
                target = output.joinpath(*safe_relative(name).parts)
                target.parent.mkdir(parents=True, exist_ok=True)
                require(budget["used"] + len(raw) <= budget["limit"] - 128 * 1024,
                        "Prepared input byte cap reached")
                with target.open("xb") as stream:
                    stream.write(raw)
                budget["used"] += len(raw)
            require(budget["used"] + len(original_raw) <= budget["limit"] - 128 * 1024,
                    "Original manifest exceeds the prepared input byte cap")
            with (output / "original_manifest.json").open("xb") as stream:
                stream.write(original_raw)
            budget["used"] += len(original_raw)
            _write_bounded(output / "origin_receipt.json", {
                "schema": "population13-main-retained-origin-v1", "archive": origin,
                "original_manifest_sha256": ORIGINAL_MANIFEST_SHA256,
                "source_registry_sha256": sha(registry_path), "retained_original_files": 180,
                "new_banks_generated": 0, "exact_solver_calls": 0, "ga_runs": 0,
                "source_archive_uploaded": False,
            }, budget)
        inventory = [{"path": p.relative_to(output).as_posix(), "bytes": p.stat().st_size, "sha256": sha(p)}
                     for p in sorted(output.rglob("*")) if p.is_file()]
        by_path = {row["path"]: row for row in inventory}
        cases = []
        for case in registered_cases():
            paths = {"problem": case["task"] + "/problem.json",
                     "certificate": case["task"] + "/certificate.json",
                     "source": case["task"] + "/source.kp",
                     "bank": case["task"] + "/banks/seed-" + str(case["seed"]) + ".json"}
            cases.append({**case, **{key: dict(by_path[path]) for key, path in paths.items()}})
        manifest = {
            "schema": "population13-main-inputs-v1", "status": "NINETY_PAIRED_CASES_READY",
            "cases": cases, "files": inventory,
            "source_manifest_sha256": authorization["source_manifest_sha256"],
            "authorization_id": authorization["authorization_id"],
            "workflow_run_id": os.environ["GITHUB_RUN_ID"], "workflow_commit": os.environ["GITHUB_SHA"],
            "new_bank_count": 0, "retained_bank_count": 90, "bank_size": 30,
            "ga_runs": 0, "exact_solver_calls": 0,
            "physical_initial_score_checks": checks["bank_score_checks"],
            "initial_rng_state_checks": checks["rng_state_checks"],
            "certificate_witness_score_checks": 60, "preparation_seconds": time.perf_counter() - started,
            "source_archive": dict(ORIGIN_ARTIFACT), "original_manifest_sha256": ORIGINAL_MANIFEST_SHA256,
        }
        _write_bounded(output / "manifest.json", manifest, budget)
        require(_used_bytes(output) == budget["used"] <= budget["limit"], "Prepared artifact accounting differs")
        return manifest
    except Exception as error:
        output.mkdir(parents=True, exist_ok=True)
        failure = output / "preparation_failure.json"
        if not failure.exists():
            _write_bounded(failure, {"status": "PREPARATION_INCOMPLETE", "error_type": type(error).__name__,
                           "ga_runs": 0, "new_banks_generated": 0, "exact_solver_calls": 0},
                           budget, emergency=True)
        raise


def load_case(inputs, case_id, authorization):
    """Verify prepared bytes and return only one registered original bank."""
    require_ci()
    root = Path(inputs)
    manifest = read_json(root / "manifest.json")
    require(manifest.get("schema") == "population13-main-inputs-v1"
            and manifest.get("status") == "NINETY_PAIRED_CASES_READY"
            and manifest.get("source_manifest_sha256") == authorization["source_manifest_sha256"]
            and manifest.get("authorization_id") == authorization["authorization_id"]
            and manifest.get("workflow_run_id") == os.environ.get("GITHUB_RUN_ID")
            and manifest.get("workflow_commit") == os.environ.get("GITHUB_SHA")
            and manifest.get("new_bank_count") == 0 and manifest.get("retained_bank_count") == 90
            and manifest.get("ga_runs") == 0 and manifest.get("exact_solver_calls") == 0,
            "Prepared population-13 provenance differs")
    expected = {row["case_id"]: row for row in registered_cases()}
    rows = manifest.get("cases")
    require(case_id in expected and type(rows) is list and len(rows) == 90
            and all(type(row) is dict for row in rows)
            and {row.get("case_id") for row in rows} == set(expected),
            "Prepared case inventory is incomplete or duplicated")
    entries = manifest.get("files")
    require(type(entries) is list and len(entries) == 182, "Prepared file inventory differs")
    by_path = {}
    for row in entries:
        require(type(row) is dict and row.get("path") not in by_path, "Duplicate prepared file descriptor")
        path = descriptor(root, row)
        by_path[row["path"]] = row
        require(path.relative_to(root.resolve()).as_posix() == row["path"], "Prepared path aliases another file")
    require(set(by_path) == selected_members() | {"original_manifest.json", "origin_receipt.json"},
            "Prepared selected-member inventory differs")
    actual_files = {p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file()}
    require(actual_files == set(by_path) | {"manifest.json"}, "Prepared directory contains unregistered files")
    for row in rows:
        fixed = expected[row["case_id"]]
        require(all(type(row.get(key)) is type(value) and row[key] == value for key, value in fixed.items()),
                "Prepared case identity differs")
        names = {"problem": row["task"] + "/problem.json", "certificate": row["task"] + "/certificate.json",
                 "source": row["task"] + "/source.kp",
                 "bank": row["task"] + "/banks/seed-" + str(row["seed"]) + ".json"}
        require(all(row.get(key) == by_path.get(name) for key, name in names.items()),
                "Prepared case descriptor substitutes an original input")
    origin = read_json(root / "origin_receipt.json")
    require(origin.get("schema") == "population13-main-retained-origin-v1"
            and all(origin.get("archive", {}).get(key) == value for key, value in ORIGIN_ARTIFACT.items())
            and origin.get("original_manifest_sha256") == ORIGINAL_MANIFEST_SHA256
            and sha(root / "original_manifest.json") == ORIGINAL_MANIFEST_SHA256
            and origin.get("source_registry_sha256") == sha(ROOT / SOURCE_REGISTRY),
            "Prepared original archive provenance differs")
    original_files, original_tasks = original_inventory(read_json(root / "original_manifest.json"))
    for name in selected_members():
        require(all(by_path[name][key] == original_files[name][key] for key in ("path", "bytes", "sha256")),
                "Prepared file no longer matches the original retained member")
    row = next(row for row in rows if row["case_id"] == case_id)
    problem = read_json(descriptor(root, row["problem"]))
    certificate = read_json(descriptor(root, row["certificate"]))
    bank = read_json(descriptor(root, row["bank"]))
    sources = {entry["task_id"]: entry for entry in read_json(ROOT / SOURCE_REGISTRY)["main_cases"]}
    _validate_task(problem, certificate, descriptor(root, row["source"]).read_bytes(),
                   sources[row["task"]], original_tasks[row["task"]])
    validate_bank(problem, bank, row)
    return row, problem, bank, certificate


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--authorization-id", required=True)
    args = parser.parse_args()
    result = prepare(args.out, args.authorization_id)
    print(json.dumps({"status": result["status"], "cases": len(result["cases"]),
                      "retained_bank_count": result["retained_bank_count"], "new_bank_count": 0, "ga_runs": 0}))


if __name__ == "__main__":
    main()
