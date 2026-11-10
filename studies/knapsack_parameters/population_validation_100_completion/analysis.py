"""Merge retained and completed cases without changing their recorded origins.

All numerical summaries, bootstrap intervals and figures reuse the frozen main
analysis.  Only evidence admission differs: two explicitly registered CI runs
contribute disjoint case identities. Importing this module performs no analysis.
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import re

from studies.knapsack_parameters.population_validation_100_main import analysis as frozen
from .common import HERE, guard_completion, read_json, require, sha
from .runner import load_original


def identity(row):
    return row["task"], row["seed"], row["mu"]


def missing_identity(row):
    return row["task"], row["seed"], row["mu"]


def execution_context():
    commit, run_id = os.environ.get("GITHUB_SHA", ""), os.environ.get("GITHUB_RUN_ID", "")
    require(re.fullmatch(r"[0-9a-f]{40}", commit) is not None, "Missing completion commit")
    require(re.fullmatch(r"[0-9]+", run_id) is not None, "Missing completion run identity")
    return {"workflow_commit": commit, "workflow_run_id": run_id,
            "code_manifest_sha256": sha(HERE / "source_manifest.json")}


def load_completed(prepared, original_compacts, completion_compacts, ledger_path):
    """Admit 886 original and 14 resumed records with separate provenance."""
    original, original_provenance, missing, prepared_sha = load_original(prepared, original_compacts)
    require(len(original) == 886 and len(missing) == 14, "Original completion inventory differs")
    ledger_path = Path(ledger_path)
    ledger = read_json(ledger_path)
    require(ledger.get("schema") == "population-validation-100-completion-ledger-v1"
            and ledger.get("status") == "MISSING_IDENTITIES_FROZEN"
            and ledger.get("completed") == 886
            and ledger.get("prepared_manifest_sha256") == prepared_sha,
            "Missing-case ledger differs from the retained evidence")
    expected_missing = {missing_identity(row) for row in missing}
    declared = ledger.get("missing")
    require(isinstance(declared, list) and len(declared) == 14
            and {missing_identity(row) for row in declared} == expected_missing,
            "Missing-case ledger contains duplicate or substituted identities")
    original_ids = {identity(row) for row in original}
    require(len(original_ids) == 886 and not original_ids.intersection(expected_missing),
            "Completion overlaps retained cases")
    retained_path = ledger_path.parent / "completed_records.json"
    require(retained_path.is_file() and sha(retained_path) == ledger.get("completed_records_sha256"),
            "Retained-case ledger checksum differs")
    retained = read_json(retained_path)
    require(retained.get("schema") == "population-validation-100-completion-original-v1"
            and retained.get("status") == "VERIFIED_886_RETAINED"
            and retained.get("records") == original
            and retained.get("provenance") == original_provenance,
            "Retained-case ledger no longer matches the original evidence")
    require(ledger.get("original_compact_provenance") == original_provenance,
            "Original compact provenance differs between preparation and analysis")
    context = execution_context()
    root = Path(completion_compacts)
    require(root.is_dir(), "Completion compact directory is absent")
    files = sorted(root.rglob("completion.json"))
    families = {row["family"] for row in missing}
    require(len(files) == len(families) == 4, "Four completion shards are required")
    recovered, provenance, seen_families = [], [], set()
    for path in files:
        require(not path.is_symlink() and path.resolve().is_relative_to(root.resolve()),
                "Unsafe completion compact path")
        data = read_json(path)
        family = data.get("family")
        require(data.get("schema") == "population-validation-100-completion-shard-v1"
                and data.get("status") == "VERIFIED" and data.get("mu") == 10
                and family in families and family not in seen_families,
                "Invalid or duplicated completion shard")
        seen_families.add(family)
        for name, value in context.items():
            require(data.get(name) == value, "Completion origin differs: " + name)
        require(data.get("original_run_id") == 42813784277
                and data.get("source_manifest_sha256") == prepared_sha
                and data.get("ledger_sha256") == sha(ledger_path),
                "Completion source bank or ledger differs")
        raw_name = f"population100-completion-raw-{family}-{context['workflow_run_id']}"
        require(data.get("raw_artifact_name") == raw_name, "Completion raw artifact identity differs")
        rows = data.get("runs")
        expected_family = {missing_identity(row) for row in missing if row["family"] == family}
        require(isinstance(rows, list) and len(rows) == len(expected_family)
                and {identity(row) for row in rows} == expected_family,
                "Completion family is incomplete, duplicated or substitutes a case")
        recovered.extend(frozen.validate_row(row, family, 10) for row in rows)
        provenance.append({"family": family, "mu": 10, "case_count": len(rows),
                           "compact_artifact_path": path.relative_to(root).as_posix(),
                           "compact_sha256": sha(path), "raw_artifact_name": raw_name,
                           "prepared_manifest_sha256": prepared_sha, "ledger_sha256": sha(ledger_path),
                           **context})
    require(seen_families == families and len(recovered) == 14
            and {identity(row) for row in recovered} == expected_missing,
            "The exact fourteen missing cases were not completed")
    records = original + recovered
    expected = {(f"n00100-{kind}-{family}", seed, mu)
                for family in frozen.FAMILIES for kind in frozen.TYPES
                for seed in frozen.SEEDS for mu in frozen.POPS}
    require(len(records) == len({identity(row) for row in records}) == len(expected) == 900
            and {identity(row) for row in records} == expected,
            "The final comparison must contain exactly 900 distinct registered cases")
    for task in {row["task"] for row in records}:
        task_rows = [row for row in records if row["task"] == task]
        require(len({row["optimum"] for row in task_rows}) == 1
                and len({row["certificate_sha256"] for row in task_rows}) == 1,
                "One task uses inconsistent exact-reference values or bytes")
        for seed in frozen.SEEDS:
            require(len({row["bank_sha256"] for row in task_rows if row["seed"] == seed}) == 1,
                    "Matched populations used different initial banks")
    records.sort(key=lambda row: (row["family"], frozen.TYPES.index(row["class_label"]), row["seed"], row["mu"]))
    return records, {"original": original_provenance, "completion": provenance,
                     "retained_case_count": 886, "completed_missing_case_count": 14,
                     "prepared_manifest_sha256": prepared_sha, "ledger_sha256": sha(ledger_path)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prepared", type=Path, required=True)
    parser.add_argument("--original-compacts", type=Path, required=True)
    parser.add_argument("--completion-compacts", type=Path, required=True)
    parser.add_argument("--ledger", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    guard_completion()
    require(not args.out.exists(), "Preserve prior analysis material")
    records, provenance = load_completed(args.prepared, args.original_compacts,
                                         args.completion_compacts, args.ledger)
    profiles, checkpoints, families, loo, costs, contrasts = frozen.summarize(records)
    args.out.mkdir(parents=True)
    figures = args.out / "figures"
    figures.mkdir()
    frozen.save_csv(args.out / "profiles.csv", profiles)
    frozen.save_csv(args.out / "checkpoints.csv", checkpoints)
    frozen.save_csv(args.out / "family_effects.csv", families)
    frozen.save_csv(args.out / "leave_one_family_out.csv", loo)
    frozen.save_csv(args.out / "costs.csv", costs)
    frozen.save_json(args.out / "primary_contrasts.json", contrasts)
    frozen.save_json(args.out / "provenance.json", {
        "schema": "population-validation-100-completion-analysis-v1",
        "status": "VERIFIED_900_RECORDS_FROM_TWO_REGISTERED_EXECUTIONS",
        "runs": len(records), "provenance": provenance,
        "completion_source_manifest_sha256": sha(HERE / "source_manifest.json"),
        "raw_journal_limitation": "All case journals were independently replayed in their producing CI jobs. "
        "The aggregate verifies authenticated original artifact provenance and case receipts, "
        "the registered completion ledger, and compact identities; it does not re-download or replay all raw journals.",
        "new_search_evaluations_in_analysis": 0})
    names = frozen.plot(records, checkpoints, families, figures)
    frozen.write_report(args.out, profiles, checkpoints, families, costs, contrasts, names)
    report = args.out / "Звіт.md"
    with report.open("a", encoding="utf-8") as stream:
        stream.write("\nПервинне виконання зберегло 886 перевірених запусків. Чотири завдання досягли "
                     "технічного ліміту часу; відсутні 14 запусків виконано окремо з тими самими "
                     "задачами, початковими банками, початковими станами генераторів і правилами алгоритму. "
                     "Завершені запуски не повторювалися. Підсумок охоплює всі 900 наперед визначених "
                     "ідентичностей. Правила порівняння, показники й статистичні інтервали збережено.\n")
    print("Verified 886 retained plus 14 completed cases; produced the registered 900-run comparison.", flush=True)


if __name__ == "__main__":
    main()
