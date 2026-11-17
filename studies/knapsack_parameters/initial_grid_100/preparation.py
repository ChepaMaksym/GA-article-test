"""Authenticate retained inputs and certify new validation tasks outside the GA.

Preparation is admitted only in the separately authorized technical CI stage.
No GA search is imported or invoked by this module. New validation tasks have
no initial banks until their selected configurations have been frozen.
"""
from __future__ import annotations

import argparse
from hashlib import sha1, sha256
from pathlib import Path
import re
import time

from .common import HERE, guard_stage
from studies.knapsack_parameters.population_validation_100.common import (
    read_json, require, require_ci, sha, write_json,
)
from studies.knapsack_parameters.population_validation_100.preparation import (
    _fetch, make_bank, score, validate_source,
)
from studies.knapsack_parameters.population_size_study.inputs import (
    problem_sha256, unordered_problem_sha256,
)
from studies.knapsack_parameters.population_size_study.io_utils import extract_artifact


SOURCE_COMMIT = "c5bea0df8169749caaba5ce7dfcf21437aa1ca5c"
RETAINED_INPUT_SHA256 = "1feb6f74fd0929f4e690a6a352f0c76e8ed41022c81df1109feab8f340a06ee5"
CLASSES = (("UC", "00Uncorrelated"), ("WC", "01WeaklyCorrelated"),
           ("SC", "02StronglyCorrelated"))
TECHNICAL = (("n00100-UC-s000", 0), ("n00100-WC-s001", 1), ("n00100-SC-s005", 2))


def _entry_identity(entry):
    match = re.fullmatch(r"n00100-(UC|WC|SC)-s([0-9]{3})", entry.get("task_id", ""))
    require(match is not None, "Source task identity must name a 100-item registered task")
    label, family = match.group(1), int(match.group(2))
    require(entry.get("source_path") == f"{dict(CLASSES)[label]}/n00100/R01000/s{family:03d}.kp",
            "Source path differs from its registered task identity")
    require(re.fullmatch(r"[0-9a-f]{40}", entry.get("git_blob_sha1", "")) is not None,
            "Pinned source Git blob is absent")
    require(type(entry.get("source_bytes", entry.get("bytes"))) is int
            and entry.get("source_bytes", entry.get("bytes")) > 0, "Pinned source byte length is absent")
    return label, family


def validate_registry(registry, protocol):
    """Reject substituted task ranges before fetching or solving any task."""
    require(registry.get("source_repository") == "likr/kplib"
            and registry.get("source_commit") == protocol.get("source_commit") == SOURCE_COMMIT
            and registry.get("source_base_url") == f"https://raw.githubusercontent.com/likr/kplib/{SOURCE_COMMIT}/",
            "KPLIB source revision differs from the registered study")
    history, validation, technical = (registry.get(name) for name in
                                    ("historical_cases", "validation_cases", "technical_cases"))
    require(all(type(rows) is list for rows in (history, validation, technical)), "Source registry inventories are absent")
    expected_history = {(label, family) for label, _ in CLASSES for family in range(60)}
    require(len(history) == 180 and {_entry_identity(row) for row in history} == expected_history,
            "Historical duplicate audit must cover exactly 180 prior 100-item tasks")
    expected_validation = {(label, family) for label, _ in CLASSES for family in range(60, 70)}
    require(len(validation) == 30 and {_entry_identity(row) for row in validation} == expected_validation,
            "Validation inventory must cover exactly thirty tasks from s060 through s069")
    for row in validation:
        label, family = _entry_identity(row)
        require(row.get("task_index") == 33 + (family - 60) * 3 + tuple(x[0] for x in CLASSES).index(label),
                "New task index differs from the frozen family/type order")
    require(len(technical) == 3 and {(row.get("task_id"), row.get("task_index")) for row in technical} == set(TECHNICAL),
            "Technical corpus or task indices differ")
    for row in technical:
        _entry_identity(row)
    require(registry.get("holdout_audit", {}).get("ga_results_found") is False,
            "Source audit has not excluded prior project GA results for new validation tasks")


def admit_new_problem(problem, historical_keys, admitted_keys):
    """Reject both ordered and item-permuted duplicates without replacing tasks."""
    key = unordered_problem_sha256(problem)
    require(key not in historical_keys and key not in admitted_keys,
            "Duplicate or previously used validation problem; the task must not be substituted")
    admitted_keys.add(key)
    return key


def verify_certificate(problem, certificate, raw):
    """Recheck the retained independent-oracle labels and feasible witnesses."""
    require(certificate.get("status") == "CERTIFIED_TWO_INDEPENDENT_EXACT_ORACLES"
            and certificate.get("search_uses_optimum") is False,
            "The exact reference is incomplete or was exposed to search")
    optimum = certificate.get("optimum")
    require(type(optimum) is int and optimum > 0, "Reference optimum is absent")
    require(certificate.get("problem_sha256") == problem_sha256(problem)
            and certificate.get("source_sha256") == sha256(raw).hexdigest(),
            "Exact certificate input identity differs")
    methods = {"capacity_certificate": "capacity_max_profit_dp_packed_witness",
               "profit_certificate": "profit_min_weight_dp_independent_packed_witness"}
    for name, method in methods.items():
        witness = certificate.get(name, {})
        require(witness.get("method") == method and witness.get("optimum_profit") == optimum,
                "The two retained exact-oracle results disagree")
        measured = score(problem, witness.get("witness_mask"))
        require(measured["feasible"] and measured["profit"] == optimum == witness.get("witness_profit")
                and measured["weight"] == witness.get("witness_weight"),
                "An exact witness is infeasible or has an inconsistent score")


def _retained_inputs(destination):
    archive = HERE / "data" / "retained_inputs.zip"
    require(archive.is_file() and sha(archive) == RETAINED_INPUT_SHA256,
            "The original technical input archive differs")
    retained = destination / "retained_origin"
    extract_artifact(archive, retained, compressed_limit=1024**2, expanded_limit=16 * 1024**2)
    manifest = read_json(retained / "manifest.json")
    require(manifest.get("status") == "INPUTS_AUDITED_AND_CERTIFIED"
            and manifest.get("source_commit") == SOURCE_COMMIT
            and manifest.get("technical_tasks") == 3 and manifest.get("main_ga_runs") == 0,
            "Original input artifact provenance differs")
    seen = set()
    for row in manifest["files"]:
        relative = row["path"]
        require(type(relative) is str and relative not in seen and "\\" not in relative
                and ":" not in relative and not Path(relative).is_absolute() and ".." not in Path(relative).parts,
                "Unsafe or duplicated original evidence path")
        seen.add(relative)
        path = (retained / relative).resolve()
        require(path.is_relative_to(retained.resolve()) and path.is_file()
                and path.stat().st_size == row["bytes"] and sha(path) == row["sha256"],
                "Original retained input bytes differ")
    actual = {p.relative_to(retained).as_posix() for p in retained.rglob("*") if p.is_file()
              and p != retained / "manifest.json"}
    require(actual == seen, "Original retained input file inventory is incomplete")
    return retained, manifest


def prepare(out):
    """Prepare technical banks and audit/certify validation inputs, without GA runs."""
    protocol = guard_stage("technical")
    require_ci()
    registry = read_json(HERE / "data" / "source_registry.json")
    validate_registry(registry, protocol)
    destination = Path(out)
    require(not destination.exists(), "Preserve previous or partial input preparation")
    destination.mkdir(parents=True, exist_ok=False)
    started = time.perf_counter()
    retained, retained_manifest = _retained_inputs(destination)
    readme = _fetch({"source_path": "README.md", "bytes": 1309}, registry)
    require(sha1(b"blob " + str(len(readme)).encode("ascii") + b"\0" + readme).hexdigest()
            == "0ab81c1f1b67e0a9696658950ecb02f3e8b443ad", "Pinned KPLIB license README differs")
    require(b"CC-BY-4.0" in readme or b"creativecommons.org/licenses/by/4.0" in readme,
            "Expected KPLIB attribution license is absent")
    (destination / "KPLIB_README.md").write_bytes(readme)
    historical_keys, historical_sources = set(), {}
    history_rows = []
    for entry in sorted(registry["historical_cases"], key=lambda row: row["source_path"]):
        raw = _fetch(entry, registry)
        problem = validate_source(raw, entry)
        key = unordered_problem_sha256(problem)
        historical_keys.add(key)
        historical_sources[entry["source_path"]] = (raw, problem)
        history_rows.append({"task": entry["task_id"], "source_path": entry["source_path"],
                             "git_blob_sha1": entry["git_blob_sha1"], "source_sha256": sha256(raw).hexdigest(),
                             "problem_sha256": problem_sha256(problem), "unordered_problem_sha256": key})
    write_json(destination / "historical_source_audit.json", {"checked_tasks": 180, "sources": history_rows})
    tasks = []
    for entry in sorted(registry["technical_cases"], key=lambda row: row["task_index"]):
        task = entry["task_id"]
        raw, problem = historical_sources[entry["source_path"]]
        retained_problem = read_json(retained / task / "problem.json")
        certificate = read_json(retained / task / "certificate.json")
        compatibility_bank = read_json(retained / task / "bank.json")
        require(problem == retained_problem, "Retained technical problem differs from pinned source bytes")
        verify_certificate(problem, certificate, raw)
        require(compatibility_bank.get("task_index") == entry["task_index"]
                and compatibility_bank.get("search_seed") == 149999
                and compatibility_bank.get("preparation_seed") == 149998,
                "Retained compatibility bank identity differs")
        # Regeneration is an independent preparation check, not a new GA search.
        regenerated = make_bank(problem, entry["task_index"], 149999, 149998)
        require(compatibility_bank == regenerated, "Retained compatibility bank or generator states differ")
        bank = make_bank(problem, entry["task_index"], 159999, 159998)
        folder = destination / task
        folder.mkdir()
        (folder / "source.kp").write_bytes(raw)
        (folder / "certificate.json").write_bytes((retained / task / "certificate.json").read_bytes())
        write_json(folder / "problem.json", problem)
        write_json(folder / "bank.json", bank)
        (folder / "compatibility_bank.json").write_bytes((retained / task / "bank.json").read_bytes())
        tasks.append({"task": task, "task_index": entry["task_index"], "phase": "technical",
                      "problem_sha256": problem_sha256(problem), "source_sha256": sha256(raw).hexdigest(),
                      "certificate_sha256": sha(folder / "certificate.json"),
                      "bank_sha256": sha(folder / "bank.json"),
                      "compatibility_bank_sha256": sha(folder / "compatibility_bank.json")})
    from studies.knapsack_parameters.population_size_study.exact import certify_problem
    admitted_keys = set()
    for entry in sorted(registry["validation_cases"], key=lambda row: row["task_index"]):
        raw = _fetch(entry, registry)
        problem = validate_source(raw, entry)
        key = admit_new_problem(problem, historical_keys, admitted_keys)
        begin = time.perf_counter()
        certificate = certify_problem(problem, memory_limit_bytes=512 * 1024**2, deadline=time.monotonic() + 30)
        certificate.update({"problem_sha256": problem_sha256(problem), "source_sha256": sha256(raw).hexdigest()})
        verify_certificate(problem, certificate, raw)
        task = entry["task_id"]
        folder = destination / task
        folder.mkdir()
        (folder / "source.kp").write_bytes(raw)
        write_json(folder / "problem.json", problem)
        write_json(folder / "certificate.json", certificate)
        tasks.append({"task": task, "task_index": entry["task_index"], "phase": "validation",
                      "source_sha256": sha256(raw).hexdigest(), "git_blob_sha1": entry["git_blob_sha1"],
                      "problem_sha256": problem_sha256(problem), "unordered_problem_sha256": key,
                      "certificate_sha256": sha(folder / "certificate.json"),
                      "certificate_seconds": time.perf_counter() - begin})
    require(len(tasks) == 33 and len(admitted_keys) == 30, "Prepared task inventory differs")
    files = [{"path": p.relative_to(destination).as_posix(), "bytes": p.stat().st_size, "sha256": sha(p)}
             for p in sorted(destination.rglob("*")) if p.is_file()]
    write_json(destination / "manifest.json", {
        "schema": "initial-grid-100-inputs-v1", "status": "INPUTS_AUDITED_AND_CERTIFIED",
        "tasks": tasks, "files": files, "source_commit": SOURCE_COMMIT,
        "technical_tasks": 3, "validation_tasks": 30, "historical_duplicate_inputs_checked": 180,
        "retained_input_archive_sha256": RETAINED_INPUT_SHA256,
        "retained_input_manifest_sha256": sha(retained / "manifest.json"),
        "license": "CC-BY-4.0", "readme_sha256": sha256(readme).hexdigest(),
        "physical_initial_score_checks": 180, "preparation_seconds": time.perf_counter() - started,
        "validation_ga_runs": 0, "validation_banks_prepared": False,
        "independence_scope": "Available project source/execution audit; external searches cannot be excluded",
    })
    print("Prepared three technical cases, retained compatibility banks and thirty certified validation tasks; no GA search executed.", flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    prepare(args.out)


if __name__ == "__main__":
    main()
