"""Authenticate held-out tasks and build paired input banks before GA search."""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import tempfile
from zipfile import ZipFile

from studies.knapsack_parameters.initial_grid_100.preparation import verify_certificate
from studies.knapsack_parameters.iterative_validation_population13.transport import (
    download_archive, safe_relative, validate_members,
)
from studies.knapsack_parameters.population_size_study.inputs import problem_sha256, unordered_problem_sha256
from studies.knapsack_parameters.population_validation_100.common import read_json, require, sha, write_json
from studies.knapsack_parameters.population_validation_100.preparation import make_bank, validate_source

from .common import guard, require_ci


HERE = Path(__file__).resolve().parent
REGISTRY = HERE.parent / "initial_grid_100/data/source_registry.json"
SELECTION = HERE.parent / "iterative_validation/data/selection.json"
RECORDS = SELECTION.parent / "validated_records.json.gz"
REGISTRY_SHA = "bd7f03776abc33e63ca03b388c8f7f660124f199bbcf01d0ca791a462d212e8d"
SELECTION_SHA = "d913102c6eb6aaf1f3897b079526c148aef9d846f13f97d55c9d9863ea486f1a"
RECORDS_SHA = "70adbcca7b27e645f8a01b7f8662358d62c347bf02a4edb825996ebf62a1af32"
SOURCE_COMMIT = "c5bea0df8169749caaba5ce7dfcf21437aa1ca5c"
TECHNICAL_MANIFEST = "b2bba8dfc6715a4e94c0ba60f6f448ec8f1897f2b77ecd496fbd07facfe6322d"
ORIGIN = {"id": 13792676347, "run_id": 42876556319,
          "name": "initial-grid100-inputs-42876556319", "bytes": 186693,
          "sha256": "a823648ea34cc4d8b84876f1fd5f12473341176984d02ee243428b5e34bac940",
          "commit": "e84a90b670cecbe3cc151a5771ac62d1a0151ddb"}
KINDS = ("UC", "WC", "SC")
SEEDS = tuple(range(160001, 160011))
PROFILES = ((10, 90, 100), (15, 90, 100), (15, 100, 100), (20, 90, 100))
TASKS = {f"n00100-{kind}-s{family:03d}": (33 + (family-60)*3 + k, f"s{family:03d}", kind)
         for family in range(60, 70) for k, kind in enumerate(KINDS)}
FILE_NAMES = {"source": "source.kp", "problem": "problem.json", "certificate": "certificate.json"}


def checked_audit(audit):
    require(isinstance(audit, dict) and audit.get("schema") == "independent-validation100-history-v1"
            and audit.get("status") == "ELIGIBLE_WITHIN_PROJECT_EVIDENCE"
            and audit.get("cohort") == "s060-s069"
            and type(audit.get("previous_holdout_search_runs")) is int
            and audit["previous_holdout_search_runs"] == 0
            and audit.get("original_input_audit") == ORIGIN["run_id"]
            and isinstance(audit.get("registered_history_sha256"), str)
            and re.fullmatch(r"[0-9a-f]{64}", audit["registered_history_sha256"]),
            "A completed clean project history audit of s060–s069 is required")
    return audit


def verify_frozen_roles():
    require(sha(SELECTION) == SELECTION_SHA and sha(RECORDS) == RECORDS_SHA,
            "Historical selection or 2790 compact records changed")
    selection = read_json(SELECTION)
    require(selection["source_records_sha256"] == RECORDS_SHA
            and selection["status"] == "SELECTED_BEFORE_VALIDATION"
            and selection["independent_validation_started"] is False, "Selection origin differs")
    for role, expected in (("quality", (15, 100, 100)), ("speed", (10, 90, 100))):
        row = selection["selections"][role]
        require(tuple(row[k] for k in ("mu", "pc_percentage", "mutation_basis_points")) == expected,
                "Historical recommendation differs")


def schedule_cases():
    cases = []
    for task, (index, family, kind) in TASKS.items():
        for seed in SEEDS:
            for mu, pc, mutation in PROFILES:
                cases.append({"case_id": f"{task}-seed-{seed}-mu{mu}-pc{pc}-pm{mutation}bp",
                              "task": task, "task_index": index, "family": family, "class_label": kind,
                              "seed": seed, "mu": mu, "pc_percentage": pc, "mutation_basis_points": mutation})
    return cases


def descriptor(root, path):
    return {"path": path.relative_to(root).as_posix(), "bytes": path.stat().st_size, "sha256": sha(path)}


def checked_path(root, row, expected_path):
    require(type(row) is dict and row.get("path") == expected_path, "Unexpected input path")
    relative = safe_relative(expected_path)
    path = root.joinpath(*relative.parts)
    require(path.resolve().is_relative_to(root.resolve()) and path.is_file()
            and not path.is_symlink() and type(row.get("bytes")) is int
            and 0 < row["bytes"] == path.stat().st_size and sha(path) == row.get("sha256"),
            "Input digest or length differs")
    return path


def input_descriptors(manifest, case):
    task, seed = case["task"], case["seed"]
    require(task in TASKS and type(seed) is int and seed in SEEDS, "Unregistered holdout pair")
    require(manifest.get("schema") == "independent-validation100-inputs-v1"
            and manifest.get("status") == "PAIRED_HOLDOUT_BANKS_PREPARED"
            and manifest.get("source_archive_sha256") == ORIGIN["sha256"]
            and manifest.get("technical_manifest_sha256") == TECHNICAL_MANIFEST
            and manifest.get("selection_sha256") == SELECTION_SHA
            and manifest.get("source_records_sha256") == RECORDS_SHA, "Unexpected input manifest")
    item = manifest["tasks"][task]
    require(tuple(item.get(k) for k in ("task_index", "family", "class_label")) == TASKS[task]
            and all(case[k] == item[k] for k in ("task_index", "family", "class_label")),
            "Prepared task identity differs")
    values = {role: item[role] for role in FILE_NAMES}
    values["bank"] = item["banks"][str(seed)]
    for key, filename in {**FILE_NAMES, "bank": f"banks/seed-{seed}.json"}.items():
        require(values[key]["path"] == task + "/" + filename and type(values[key]["bytes"]) is int
                and values[key]["bytes"] > 0 and re.fullmatch(r"[0-9a-f]{64}", values[key]["sha256"]),
                "Bank, certificate or source descriptor is not bound to its identity")
    return values


def load_case(inputs, case):
    require_ci()
    root = Path(inputs)
    manifest = read_json(root / "manifest.json")
    desc = input_descriptors(manifest, case)
    paths = {kind: checked_path(root, row, row["path"]) for kind, row in desc.items()}
    problem, bank, certificate = (read_json(paths[key]) for key in ("problem", "bank", "certificate"))
    require(bank["task_index"] == case["task_index"] and bank["search_seed"] == case["seed"]
            and bank["preparation_seed"] == 160000 and set(problem) == {"n", "weights", "profits", "capacity"}
            and certificate["problem_sha256"] == problem_sha256(problem),
            "Loaded material differs from the registered task/seed")
    return problem, bank, certificate


def read_certified_archive(path):
    require(path.stat().st_size == ORIGIN["bytes"] and sha(path) == ORIGIN["sha256"],
            "Historical CI archive changed")
    with ZipFile(path) as zipped:
        members = validate_members(zipped)
        require(len(members) == 209 and sum(i.file_size for i in members.values()) <= 1024**2,
                "Unexpected certified input archive size or inventory")
        raw_manifest = zipped.read("manifest.json")
        require(sha256(raw_manifest).hexdigest() == TECHNICAL_MANIFEST, "Historical manifest differs")
        source = json.loads(raw_manifest)
        require(source["schema"] == "initial-grid-100-inputs-v1"
                and source["status"] == "INPUTS_AUDITED_AND_CERTIFIED" and source["source_commit"] == SOURCE_COMMIT
                and source["validation_tasks"] == 30 and source["validation_ga_runs"] == 0
                and source["validation_banks_prepared"] is False, "Invalid original holdout preparation")
        files = {r["path"]: r for r in source["files"]}
        require(len(files) == len(source["files"]) == 208 and set(members) == {"manifest.json", *files},
                "Unlisted or duplicated archive entry")
        # The signed archive is under 1 MiB uncompressed, including the 180-task cross-check.
        payload = {}
        for name, item in files.items():
            raw = zipped.read(name)
            require(len(raw) == item["bytes"] and sha256(raw).hexdigest() == item["sha256"],
                    "Certified source member differs: " + name)
            payload[name] = raw
    return source, payload


def verify_tasks(registry, source, payload, audit):
    history = json.loads(payload["historical_source_audit.json"])
    require(history["checked_tasks"] == len(history["sources"]) == 180 == source["historical_duplicate_inputs_checked"],
            "Original 180-task duplicate check is incomplete")
    checked_keys = {r["unordered_problem_sha256"] for r in history["sources"]}
    additional = audit.get("additional_searched_problem_keys", [])
    require(type(additional) is list and all(isinstance(k, str) and re.fullmatch(r"[0-9a-f]{64}", k)
                                            for k in additional), "Invalid later search hashes")
    checked_keys.update(additional)
    original_rows = [r for r in source["tasks"] if r["phase"] == "validation"]
    original = {r["task"]: r for r in original_rows}
    entries = {r["task_id"]: r for r in registry["validation_cases"]}
    require(registry["source_commit"] == SOURCE_COMMIT and registry["holdout_audit"]["ga_results_found"] is False
            and len(original_rows) == len(registry["validation_cases"]) == 30
            and set(entries) == set(original) == set(TASKS), "Holdout source inventory differs")
    problems = {}
    for task, (index, _, _) in TASKS.items():
        row, entry = original[task], entries[task]
        raw, encoded, cert_bytes = (payload[f"{task}/{name}"] for name in FILE_NAMES.values())
        problem = json.loads(encoded)
        require(row["task_index"] == index == entry["task_index"] and validate_source(raw, entry) == problem
                and row["source_sha256"] == sha256(raw).hexdigest()
                and row["git_blob_sha1"] == entry["git_blob_sha1"]
                and row["problem_sha256"] == problem_sha256(problem)
                and row["certificate_sha256"] == sha256(cert_bytes).hexdigest(), "Certified task identity differs")
        key = unordered_problem_sha256(problem)
        require(key == row["unordered_problem_sha256"] and key not in checked_keys,
                "An ordered or item-permuted duplicate was found: " + task)
        checked_keys.add(key)
        verify_certificate(problem, json.loads(cert_bytes), raw)
        problems[task] = problem
    return problems


def prepare(out, audit_path, certified_archive=None):
    guard("benchmark")
    out, audit_path = Path(out), Path(audit_path)
    require(not out.exists(), "Preserve incomplete or previously prepared input cases")
    audit = checked_audit(read_json(audit_path))
    verify_frozen_roles()
    require(sha(REGISTRY) == REGISTRY_SHA, "KPLIB holdout registry differs")
    with tempfile.TemporaryDirectory() as temp:
        if certified_archive is None:
            origin_path = Path(temp) / "original.zip"
            download_archive(ORIGIN, os.environ.get("GITHUB_TOKEN", ""), origin_path)
        else:
            origin_path = Path(certified_archive)
        source, payload = read_certified_archive(origin_path)
    problems = verify_tasks(read_json(REGISTRY), source, payload, audit)
    out.mkdir(parents=True)
    # Each dispatch has its own receipt; the validated eligibility and input
    # identities stay byte-identical on a resume of the registered series.
    audit_copy = out / "history-receipt.json"
    audit_copy.write_bytes(audit_path.read_bytes())
    eligibility = out / "eligibility.json"
    stable_fields = ("schema", "status", "cohort", "original_input_audit",
                     "registered_history_sha256", "previous_holdout_search_runs")
    facts = {key: audit[key] for key in stable_fields}
    facts["additional_searched_problem_keys"] = sorted(audit.get("additional_searched_problem_keys", []))
    write_json(eligibility, facts)
    tasks = {}
    for task, (index, family, kind) in TASKS.items():
        task_dir = out / task
        task_dir.mkdir()
        item = {"task_index": index, "family": family, "class_label": kind, "banks": {}}
        for role, filename in FILE_NAMES.items():
            path = task_dir / filename
            path.write_bytes(payload[task + "/" + filename])
            item[role] = descriptor(out, path)
        for seed in SEEDS:
            bank_path = task_dir / "banks" / f"seed-{seed}.json"
            write_json(bank_path, make_bank(problems[task], index, seed, 160000))
            item["banks"][str(seed)] = descriptor(out, bank_path)
        tasks[task] = item
    schedule = out / "schedule.json"
    write_json(schedule, {"schema": "independent-validation100-schedule-v1", "cases": schedule_cases()})
    manifest = {"schema": "independent-validation100-inputs-v1", "status": "PAIRED_HOLDOUT_BANKS_PREPARED",
                "source_archive_sha256": ORIGIN["sha256"], "archive_origin": ORIGIN,
                "technical_manifest_sha256": TECHNICAL_MANIFEST, "registry_sha256": REGISTRY_SHA,
                "selection_sha256": SELECTION_SHA, "source_records_sha256": RECORDS_SHA,
                "schedule": descriptor(out, schedule), "prior_search_audit": descriptor(out, eligibility),
                "tasks": tasks, "bank_count": 300, "bank_size": 30, "bank_score_checks": 9000,
                "certificates_rechecked": 30, "witnesses_rechecked": 60, "physical_cases": 1200,
                "holdout_ga_runs": 0, "exact_solvers_rerun": False}
    write_json(out / "manifest.json", manifest)
    write_json(out / "preparation-receipt.json", {"inputs_manifest_sha256": sha(out / "manifest.json"),
               "live_audit": descriptor(out, audit_copy), "workflow_run_id": os.environ["GITHUB_RUN_ID"],
               "workflow_commit": os.environ["GITHUB_SHA"]})
    return manifest


if __name__ == "__main__":
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--audit", type=Path, required=True)
    cli.add_argument("--out", type=Path, required=True)
    cli.add_argument("--certified-archive", type=Path)
    args = cli.parse_args()
    prepared = prepare(args.out, args.audit, args.certified_archive)
    print(json.dumps({key: prepared[key] for key in ("status", "physical_cases", "bank_count", "holdout_ga_runs")}))
