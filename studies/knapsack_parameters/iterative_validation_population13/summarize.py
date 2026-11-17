"""Consolidate six admitted technical cases; forecast resources, not winners."""
from __future__ import annotations

import argparse
import csv
import json
import math
import os
from pathlib import Path

from .common import TOTAL, guard_technical, registered_cases
from studies.knapsack_parameters.population_validation_100.common import read_json, require, sha, write_json


RAW_FILES = {"journal.json.gz", "verification.json", "operator_bins.json", "observations.json.gz"}


def consolidate(rows):
    """Keep incomplete evidence, but never project a main series from it."""
    expected = {row["case_id"]: row for row in registered_cases()}
    seen, commits, seals, runs = set(), set(), set(), set()
    for row in rows:
        require(type(row) is dict and row.get("case_id") in expected, "Unknown technical identity")
        fixed = expected[row["case_id"]]
        require(row["case_id"] not in seen and all(type(row.get(key)) is type(value) and row[key] == value
                for key, value in fixed.items()), "Duplicate or mismatched technical identity")
        require(row.get("schema") == "population13-technical-case-v1" and row.get("status") == "VERIFIED",
                "Only independently verified full cases enter a resource forecast")
        require(row.get("total_evaluations") == TOTAL
                and row.get("initial_evaluations") == fixed["mu"]
                and row.get("new_evaluations") == TOTAL - fixed["mu"]
                and row.get("pc_percentage") == 90 and row.get("mutation_basis_points") == 100
                and row.get("tournament_size") == 2 and row.get("elite_count") == 1,
                "Technical scope or evaluation accounting differs")
        seconds = row.get("case_seconds_before_receipt")
        size = row.get("artifact_bytes_before_receipt")
        require(type(seconds) in (int, float) and math.isfinite(seconds) and seconds > 0
                and type(size) is int and size > 0, "Invalid measured resource value")
        if fixed["mode"] == "compatibility":
            require(row.get("compatibility_scope") == "complete_journal_except_timing_ns"
                    and type(row.get("reference_journal_sha256")) is str,
                    "A compact comparison cannot replace historical journal compatibility")
        seen.add(row["case_id"])
        commits.add(row.get("workflow_commit"))
        seals.add(row.get("source_manifest_sha256"))
        runs.add(row.get("workflow_run_id"))
    require(len(commits) <= 1 and len(seals) <= 1 and len(runs) <= 1,
            "Mixed execution versions, source seals or workflow identities")
    missing = sorted(set(expected) - seen)
    result = {"schema": "population13-technical-summary-v1",
              "status": "TECHNICAL_INCOMPLETE" if missing else "SIX_TECHNICAL_CASES_VERIFIED",
              "verified_cases": len(rows), "missing_cases": missing,
              "technical_search_evaluations": sum(row["total_evaluations"] for row in rows),
              "main_runs_started": 0, "main_stage_authorized": False,
              "scientific_winner_selected_from_pilot": False, "cases": rows,
              "main_resource_forecast": None}
    if missing:
        return result
    # Use the slowest of all six cases, including stronger logging/replay costs
    # of the smaller retained control. This is a conservative planning scenario.
    slowest = max(row["case_seconds_before_receipt"] for row in rows)
    largest = max(row["artifact_bytes_before_receipt"] for row in rows)
    result["main_resource_forecast"] = {
        "status": "PROJECTION_REQUIRING_SEPARATE_APPROVAL",
        "main_runs": 90, "total_evaluations_including_initial": 9000000,
        "slowest_measured_case_seconds": slowest,
        "largest_measured_case_bytes_before_receipt": largest,
        "runtime_multiplier": 2.0, "artifact_multiplier": 1.5,
        "runner_setup_analysis_allowance_minutes": 10,
        "artifact_setup_analysis_allowance_bytes": 128 * 1024**2,
        "proposed_runner_minutes": math.ceil(90 * slowest * 2 / 60) + 10,
        "proposed_artifact_bytes": math.ceil(90 * largest * 1.5) + 128 * 1024**2,
        "limitations": "Three pilot instances do not establish timing for every instance; measured case timers exclude runner setup and final receipt writing, covered by explicit reserves. No main-series permission is inferred.",
    }
    return result


def summarize(results, output, authorization_id):
    protocol, authorization = guard_technical(authorization_id)
    root, output = Path(results).resolve(), Path(output)
    require(root.is_dir() and not output.exists(), "Preserve prior technical evidence")
    rows = []
    for path in sorted(root.rglob("record.json")):
        require(not path.is_symlink() and path.resolve().is_relative_to(root), "Unsafe result receipt")
        row = read_json(path)
        require(row.get("workflow_commit") == os.environ.get("GITHUB_SHA")
                and row.get("workflow_run_id") == os.environ.get("GITHUB_RUN_ID")
                and row.get("source_manifest_sha256") == authorization["source_manifest_sha256"]
                and row.get("authorization_id") == authorization["authorization_id"],
                "Case source or authorization differs")
        hashes = row.get("artifact_hashes")
        require(type(hashes) is dict and set(hashes) == RAW_FILES, "Case artifact inventory differs")
        for name, digest in hashes.items():
            artifact = path.parent / name
            require(artifact.is_file() and not artifact.is_symlink()
                    and artifact.resolve().is_relative_to(root) and sha(artifact) == digest,
                    "Case artifact bytes differ: " + name)
        require(read_json(path.parent / "verification.json").get("verification_status") == "VERIFIED",
                "Independent replay receipt is not verified")
        rows.append(row)
    result = consolidate(rows)
    output.mkdir(parents=True, exist_ok=False)
    write_json(output / "summary.json", result)
    columns = ("case_id", "mode", "task", "mu", "seed", "total_evaluations", "completed_generations",
               "terminal_partial_children", "search_seconds", "verification_seconds", "compatibility_seconds",
               "case_seconds_before_receipt", "artifact_bytes_before_receipt")
    with (output / "technical-cases.csv").open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=columns, delimiter=";", extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    text = ["# Технічна перевірка популяції 13", "", "Статус: " + result["status"], "",
            "Перевірено повних випадків: " + str(result["verified_cases"]) + " із 6.",
            "Основну серію з 90 запусків не розпочато. Технічні випадки не визначають кращу конфігурацію.", ""]
    forecast = result["main_resource_forecast"]
    if forecast:
        text += ["Кошторис наступної серії є прогнозом за виміряними технічними випадками.",
                 "Передбачено подвійний резерв часу та півтораразовий резерв матеріалів, окремо додано підготовку й аналіз.",
                 "Запропонований ліміт runner-хвилин: " + str(forecast["proposed_runner_minutes"]),
                 "Запропонований ліміт матеріалів у байтах: " + str(forecast["proposed_artifact_bytes"]),
                 "Окремий дозвіл основної серії ще потрібний. Точні вимірювання та припущення містяться в summary.json."]
    else:
        text += ["Відсутні випадки: " + ", ".join(result["missing_cases"]),
                 "Кошторис основної серії не обчислено з неповних доказів."]
    (output / "Технічний_підсумок.md").write_text("\n".join(text) + "\n", encoding="utf-8")
    size = sum(path.stat().st_size for path in output.rglob("*") if path.is_file())
    require(size <= protocol["limits"]["summary_artifact_bytes"], "Summary material limit exceeded")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--authorization-id", required=True)
    args = parser.parse_args()
    result = summarize(args.results, args.output, args.authorization_id)
    print(json.dumps({"status": result["status"], "verified_cases": result["verified_cases"]}))
    return 0 if not result["missing_cases"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
