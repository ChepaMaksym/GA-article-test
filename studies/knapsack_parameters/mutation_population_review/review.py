"""Reaggregate saved records and replay four saved journals; never run search."""
from __future__ import annotations

from collections import defaultdict
import csv
import gzip
import io
import json
import math
from pathlib import Path
from statistics import fmean
import zipfile

from . import authority as a

PROFILES = (0, 1, 4, 5)
NAMES = {0: "Сталі параметри", 1: "Адаптивна мутація", 4: "Адаптивна популяція", 5: "Мутація та популяція"}
COLORS = {0: "#1765a0", 1: "#b54620", 4: "#6c5aa6", 5: "#207a54"}
TASKS = tuple(f"{kind}-s{i:03d}" for i in range(20, 30) for kind in ("UC", "WC", "SC"))
SEEDS = tuple(range(97001, 97031))


def validate_events(events, budget=5000):
    a.require(type(events) is list and bool(events) and events[0]["q"] == 0, "record lacks known beginning")
    previous_q = previous_profit = -1
    for event in events:
        q, profit = event["q"], event["profit"]
        a.require(type(q) is int and 0 <= q <= budget and q > previous_q and
                  type(profit) is int and profit > previous_profit, "nonmonotone/corrupt record history")
        previous_q, previous_profit = q, profit


def target_query(events, optimum, target):
    return next((e["q"] for e in events if 100 * e["profit"] >= target * optimum), None)


def family_values(rows, getter):
    tasks = defaultdict(list)
    for row in rows:
        tasks[(row["family"], row["task"])].append(getter(row))
    families = defaultdict(list)
    for (family, _), values in tasks.items():
        families[family].append(fmean(values))
    return {family: fmean(values) for family, values in sorted(families.items())}


def validate_rectangle(rows, tasks, seeds, profiles, source_sha):
    expected = {(task, seed, profile) for task in tasks for seed in seeds for profile in profiles}
    seen, starts = set(), {}
    for row in rows:
        key = (row["task"], row["seed"], row["profile"])
        a.require(key in expected and key not in seen, "foreign or duplicate run identity")
        seen.add(key)
        a.require(row["verification_status"] == "VERIFIED" and row["stage"] == "main" and row["start"] == "bank" and
                  row["implementation_sha"] == source_sha and row["family"] == row["task"].split("-")[1] and
                  row["n"] == 100 and row["budget"] == 5000, "mixed scientific provenance")
        validate_events(row["record_events"])
        a.require(row["record_events"][0]["profit"] == row["initial_best_profit"] and
                  row["record_events"][-1]["profit"] == row["final_best_profit"] and
                  0 <= row["final_best_profit"] <= row["optimum"], "record endpoints/reference mismatch")
        actual_gap = 100 * (row["optimum"] - row["final_best_profit"]) / row["optimum"]
        a.require(math.isclose(actual_gap, row["final_gap_percent"], rel_tol=0, abs_tol=1e-12), "stored gap mismatch")
        for target in (95, 99):
            a.require(target_query(row["record_events"], row["optimum"], target) == row["first_targets"][str(target)],
                      "first target does not match saved history")
        beginning = tuple(row[field] for field in ("initial_population_sha256", "initial_rng_sha256",
                         "first_generation_sha256", "problem_sha256", "initial_best_profit", "optimum"))
        pair = key[:2]
        if pair in starts:
            a.require(starts[pair] == beginning, "unpaired beginning/RNG/first generation")
        else:
            starts[pair] = beginning
    a.require(seen == expected, "incomplete task/seed/profile rectangle")


def aggregate(rows):
    a.ci_only()
    result = []
    for profile in PROFILES:
        subset = [row for row in rows if row["profile"] == profile]
        families = family_values(subset, lambda r: r["final_gap_percent"])
        targets = {}
        for target in (95, 99):
            hits = [r["first_targets"][str(target)] for r in subset]
            queries = sorted({0, 5000, *(q for q in hits if q is not None)})
            curve = [{"q": q, "fraction": fmean(family_values(subset,
                lambda r: int(r["first_targets"][str(target)] is not None and r["first_targets"][str(target)] <= q)).values())}
                for q in queries]
            targets[str(target)] = {"attained": sum(q is not None for q in hits),
                "not_attained": sum(q is None for q in hits), "denominator": len(subset), "curve": curve}
        result.append({"profile": profile, "name": NAMES[profile], "runs": len(subset),
            "mean_final_gap_percent": fmean(families.values()), "family_gap_percent": families, "targets": targets,
            "mean_full_generations": fmean(family_values(subset, lambda r: r["full_generations"]).values()),
            "mean_infeasible_fraction": fmean(family_values(subset, lambda r: r["infeasible_fraction"]).values()),
            "mean_duplicate_fraction": fmean(family_values(subset, lambda r: r["duplicate_fraction"]).values()),
            "query_weighted_parameters": {field: fmean(family_values(subset,
                lambda r: r["activity"][field]["query_weighted_mean"]).values()) for field in ("p_m", "target_mu")}})
    return result


def examples_from_archive(path, rows):
    a.ci_only()
    from ..parameter_dynamics.verifier import verify_log
    a.require(a.sha(Path(path).read_bytes()) == a.ZIP_SHA, "worker ZIP checksum mismatch")
    examples, sources = [], []
    with zipfile.ZipFile(path) as archive:
        names = archive.namelist()
        a.require(len(names) == len(set(names)), "duplicate ZIP members")
        manifest = json.loads(archive.read("file_manifest.json"))
        entries = {entry["path"]: entry for entry in manifest["files"]}
        a.require(len(entries) == len(manifest["files"]), "duplicate source manifest entries")
        for profile in PROFILES:
            name = f"logs/UC-s020-bank-97001-p{profile:02d}.json.gz"
            raw = archive.read(name)
            a.require(name in entries and len(raw) == entries[name]["bytes"] and a.sha(raw) == entries[name]["sha256"],
                      "journal bytes differ from worker manifest")
            log = json.loads(gzip.decompress(raw))
            row = next(r for r in rows if r["task"] == "UC-s020" and r["seed"] == 97001 and r["profile"] == profile)
            a.require(log["profile"] == profile and log["budget"] == 5000 and a.sha(a.canonical(log)) == row["journal_sha256"],
                      "journal differs from exact compact record")
            verification = verify_log(log)
            a.require(verification["verification_status"] == "VERIFIED", "historical journal did not replay")
            derived = verification["derived_metrics"]
            a.require(derived["record_events"] == row["record_events"] and
                      verification["summary"]["best_profit"] == row["final_best_profit"] and
                      verification["summary"]["best_mask"] == row["final_best_mask"], "replay differs from compact endpoints")
            for gen in derived["generation_trace"]:
                theta = gen["parameters_before"]
                a.require(theta["p_c"] == 0.9 and theta["tournament_size"] == 2 and theta["elite_count"] == 1,
                          "unexpected adaptation of another parameter")
                if not profile & 1:
                    a.require(theta["p_m"] == 0.01, "disabled mutation changed")
                if not profile & 4:
                    a.require(theta["target_mu"] == 30, "disabled population changed")
                if not gen["complete"]:
                    a.require(gen["parameters_after"] == theta and gen["controller_event"] == "PARTIAL_NO_UPDATE",
                              "partial generation changed controller")
            examples.append({"profile": profile, "name": NAMES[profile], "task": row["task"], "seed": row["seed"],
                "optimum": row["optimum"], "initial_best_profit": row["initial_best_profit"],
                "final_best_profit": row["final_best_profit"], "record_events": derived["record_events"],
                "generations": derived["generation_trace"], "population": derived["population_trace"],
                "verification": {k: v for k, v in verification.items() if k not in ("derived_metrics", "summary")}})
            sources.append({"path": name, **entries[name], "journal_sha256": row["journal_sha256"]})
    return examples, sources


def population_checkpoints(examples):
    result = []
    for example in examples:
        for q in (0, 1000, 2500, 5000):
            population = next(p for p in reversed(example["population"]) if p["complete"] and p["q"] <= q)
            gen = next(g for g in example["generations"] if g["start_q"] <= max(1, q) <= g["q"])
            result.append({"profile": example["profile"], "name": example["name"], "q": q,
                "last_completed_population_q": population["q"], "committed_population_size": population["population_size"],
                "actual_parent_mu_for_query": gen["actual_parent_mu"],
                "applied_target_mu_for_query": gen["parameters_before"]["target_mu"],
                "applied_mutation_percent_for_query": 100 * gen["parameters_before"]["p_m"]})
    return result


def execute(archive, output):
    a.ci_only()
    source_summary = a.read(a.SOURCE / "series_summary.json")
    with gzip.open(a.SOURCE / "compact_records.json.gz", "rt", encoding="utf-8") as stream:
        all_rows = json.load(stream)
    validate_rectangle(all_rows, TASKS, SEEDS, tuple(range(32)), a.SOURCE_SHA)
    rows = [row for row in all_rows if row["profile"] in PROFILES]
    del all_rows
    validate_rectangle(rows, TASKS, SEEDS, PROFILES, a.SOURCE_SHA)
    cells = aggregate(rows)
    for cell in cells:
        old = next(c for c in source_summary["profile_cells"] if c["profile"] == cell["profile"] and c["start"] == "bank")
        a.require(math.isclose(cell["mean_final_gap_percent"], old["mean_final_gap_percent"], abs_tol=1e-12, rel_tol=0),
                  "reaggregation differs from frozen source")
        for target in ("95", "99"):
            a.require(cell["targets"][target]["attained"] == old["targets"][target]["attained"], "target totals differ")
    examples, journal_sources = examples_from_archive(archive, rows)
    checkpoints = population_checkpoints(examples)
    summary = {"protocol": a.PROTOCOL, "status": "COMPLETE_VERIFIED_SECONDARY_REVIEW", "secondary_descriptive": True,
        "new_ga_runs": 0, "new_search_evaluations": 0, "source_runs": 28800, "reviewed_runs": len(rows),
        "raw_journals_replayed": len(examples), "tasks": 30, "families": 10, "profiles": list(PROFILES),
        "source_run": a.SOURCE_RUN, "source_sha": a.SOURCE_SHA, "source_manifest_sha256": a.SOURCE_MANIFEST_SHA,
        "input_hashes": a.INPUT_HASHES, "source_artifact_id": a.ARTIFACT_ID, "source_zip_sha256": a.ZIP_SHA,
        "journal_sources": journal_sources, "cells": cells, "example": {"task": "UC-s020", "seed": 97001},
        "weighting": "repeat -> task -> family; ten families equally weighted",
        "new_primary_tests": 0, "bootstrap_resamples": 0,
        "historical_primary_analysis_sha256": a.sha(a.canonical(source_summary["primary_analysis"])),
        "limitations": ["Results were already inspected; this is a secondary descriptive analysis.",
            "Four raw example journals replayed; all 3600 endpoints reaggregated from historically verified compact records.",
            "One trajectory is illustrative and does not establish superiority or causation."]}
    output = Path(output)
    a.write(output / "review_summary.json", summary)
    a.write(output / "example_traces.json", examples)
    a.write(output / "population_checkpoints.json", checkpoints)
    fields = ("profile", "task", "family", "seed", "initial_best_profit", "final_best_profit", "final_gap_percent")
    with (output / "reviewed_endpoints.csv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=(*fields, "first95", "first99"))
        writer.writeheader()
        for row in rows:
            writer.writerow({**{k: row[k] for k in fields}, "first95": row["first_targets"]["95"], "first99": row["first_targets"]["99"]})
    return summary, examples
