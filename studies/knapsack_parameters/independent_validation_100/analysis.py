"""Compute independent holdout endpoints from authenticated CI compact receipts."""

import argparse
import csv
import hashlib
import json
import os
from collections import Counter
from fractions import Fraction
from pathlib import Path

from studies.knapsack_parameters.ga_study.statistics import bca_family_intervals
from studies.knapsack_parameters.mutation_grid_100 import analysis as historic

from . import common
from .preparation import input_descriptors


QUALITY = (15, 100, 100)
SPEED = (10, 90, 100)
REFERENCE = (20, 90, 100)
SECONDARY = (15, 90, 100)
PROFILES = (QUALITY, SPEED, REFERENCE, SECONDARY)
CONTROLS = (QUALITY, SPEED, REFERENCE)
FAMILIES = historic.VALIDATION_FAMILIES
SEEDS = historic.VALIDATION_SEEDS
TARGETS = historic.TARGETS
TOTAL = historic.TOTAL
CONFIDENCE = Fraction(119, 120)
EXPECTED = 1200


def profile_name(config):
    mu, crossover, mutation_bp = config
    return f"{mu} / {crossover}% / {Fraction(mutation_bp, 100)}%"


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def read_json(path):
    return json.loads(path.read_bytes())


def write_json(path, data):
    path.write_bytes((json.dumps(data, indent=2, ensure_ascii=False, allow_nan=False) + "\n").encode())


def write_csv(path, rows):
    with path.open("x", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]), delimiter=";")
        writer.writeheader()
        writer.writerows(rows)


def check_descriptor(root, item):
    path = (root / item["path"]).resolve(strict=True)
    require(path.is_relative_to(root.resolve()) and path.is_file()
            and path.stat().st_size == item["bytes"] and sha(path) == item["sha256"],
            "Prepared input does not match its manifest")
    return path


def load_cases(compacts, inputs, authorization):
    manifest_path = inputs / "manifest.json"
    manifest_hash, manifest = sha(manifest_path), read_json(manifest_path)
    schedule = read_json(check_descriptor(inputs, manifest["schedule"]))
    indexed_cases = {historic.identity(row): row for row in schedule["cases"]}
    require(len(indexed_cases) == len(schedule["cases"]) == EXPECTED, "Incomplete registered schedule")
    certificates, evidence, rows = {}, [], []
    for path in sorted(compacts.rglob("records/*.json")):
        row = read_json(path)
        require(row.get("schema") == "independent-validation100-case-v1"
                and row.get("status") == "VERIFIED", "A replay-verified case is required")
        common.validate_origin(row, authorization)
        key = historic.identity(row)
        require(key in indexed_cases, "Unregistered case in the compact receipts")
        case = indexed_cases[key]
        require(path.name == case["case_id"] + ".json" and case["case_id"] == row["case_id"]
                and row["inputs_manifest_sha256"] == manifest_hash
                and row["task_index"] == case["task_index"], "Case or prepared-manifest identity differs")
        mu, pc, bp = historic.configuration(row)
        prefix = f"{row['task']}/seed-{row['seed']}/mu{mu}-pc{pc}-pm{bp}bp"
        require(row["artifact_prefix"] == prefix, "Raw evidence identity differs")
        descriptors = input_descriptors(manifest, case)
        for field in ("problem", "certificate", "source", "bank"):
            require(row[field + "_sha256"] == descriptors[field]["sha256"], "Source/receipt digest differs")
        if row["task"] not in certificates:
            cert_path = check_descriptor(inputs, descriptors["certificate"])
            certificates[row["task"]] = read_json(cert_path)["optimum"]
        require(row["optimum"] == certificates[row["task"]], "Compact optimum differs from certified optimum")
        rows.append(row)
        evidence.append({"case_id": row["case_id"], "compact_sha256": sha(path),
                         "raw_file_sha256": row["artifact_hashes"], "workflow_run_id": row["workflow_run_id"],
                         "workflow_commit": row["workflow_commit"]})
    historic._validate_collection(rows, PROFILES, FAMILIES, SEEDS, "validation")
    return rows, evidence, manifest, manifest_hash


def family_values(rows, config, getter):
    return historic.family_means(rows, config, getter, FAMILIES, SEEDS)


def summarize(rows):
    summaries, families, vectors = [], [], {}
    for config in PROFILES:
        subset = [r for r in rows if historic.configuration(r) == config]
        stats = {"final_gap": family_values(subset, config, historic.gap)}
        stats["search_seconds"] = family_values(subset, config, lambda r: Fraction(str(r["timing"]["search_seconds"])))
        for target in TARGETS:
            stats[f"t{target}"] = family_values(subset, config,
                lambda r, target=target: r["targets"][str(target)]["restricted_evaluations"])
        for q in historic.CHECKPOINTS[:-1]:
            stats[f"gap_{q}"] = family_values(subset, config, lambda r, q=q: historic.gap(r, q))
        vectors[config] = stats
        summary = {"configuration": profile_name(config), "runs": len(subset)}
        summary.update({key: float(historic.mean(values)) for key, values in stats.items()})
        for target in TARGETS:
            hit = sum(r["targets"][str(target)]["attained"] for r in subset)
            summary[f"attained_{target}"] = hit
            summary[f"missed_{target}"] = len(subset) - hit
        summaries.append(summary)
        families.extend({"configuration": profile_name(config), "family": family,
                         **{key: float(values[i]) for key, values in stats.items()}}
                        for i, family in enumerate(FAMILIES))
    return summaries, families, vectors


def differences(left, right):
    return tuple(a - b for a, b in zip(left, right, strict=True))


def conclusion(interval):
    if interval["status"] == "IDENTICAL":
        return "IDENTICAL"
    if interval["status"] != "INFERENTIAL_BCA":
        return "DESCRIPTIVE"
    if interval["lower"] > 0:
        return "FAVOURS_CANDIDATE"
    if interval["upper"] < 0:
        return "FAVOURS_CONTROL"
    return "DIRECTION_UNRESOLVED"


def primary_comparisons(vectors):
    pairs, calculated, family_rows = [], [], []
    for role, candidate, metric in (("quality", QUALITY, "final_gap"), ("speed", SPEED, "t93")):
        for control in CONTROLS:
            effects = differences(vectors[control][metric], vectors[candidate][metric])
            pair = {"role": role, "candidate": profile_name(candidate), "control": profile_name(control),
                    "metric": metric, "estimate": float(historic.mean(effects)),
                    "status": "IDENTICAL" if candidate == control else "PENDING", "lower": None, "upper": None}
            if candidate != control:
                calculated.append((pair, effects))
            pairs.append(pair)
            for index, family in enumerate(FAMILIES):
                family_rows.append({"role": role, "candidate": pair["candidate"], "control": pair["control"],
                    "metric": metric, "family": family, "effect": float(effects[index]),
                    "mean_without_family": float(historic.mean(effects[:index] + effects[index + 1:]))})
    # These four columns are the four distinct physical contrasts across the six roles.
    # Generic helper contrast names are specific to its original study and are not exported.
    matrix = [[float(effects[index]) for _, effects in calculated] for index in range(len(FAMILIES))]
    bootstrap = bca_family_intervals(matrix, replicates=50000, seed=160031, confidence_level=float(CONFIDENCE))
    for (pair, _), interval in zip(calculated, bootstrap["intervals"], strict=True):
        pair.update(status=interval["status"], lower=interval["lower"], upper=interval["upper"])
    for pair in pairs:
        pair["conclusion"] = conclusion(pair)
    support = all(pair["conclusion"] == "FAVOURS_CANDIDATE" for pair in pairs
                  if pair["role"] == "quality" and pair["status"] != "IDENTICAL")
    return pairs, family_rows, support, bootstrap["resample_index_sha256"]


def secondary_diagnostic(rows, vectors):
    paired = {config: {(r["task"], r["seed"]): r["targets"]["93"]["restricted_evaluations"]
                       for r in rows if historic.configuration(r) == config} for config in (SPEED, SECONDARY)}
    left, right = paired[SPEED], paired[SECONDARY]
    require(len(left) == 300 and set(left) == set(right), "Unpaired secondary diagnostic")
    # Positive means that the smaller population reached the target earlier.
    deltas = differences(vectors[SECONDARY]["t93"], vectors[SPEED]["t93"])
    fam = [{"family": family, "t93_mu15_minus_mu10": float(deltas[i]),
            "without_family": float(historic.mean(deltas[:i] + deltas[i + 1:]))}
           for i, family in enumerate(FAMILIES)]
    return {"mean_t93_mu15_minus_mu10": float(historic.mean(deltas)),
            "mu10_faster": sum(left[k] < right[k] for k in left),
            "mu15_faster": sum(right[k] < left[k] for k in left),
            "ties": sum(left[k] == right[k] for k in left), "paired_runs": len(left),
            "analysis": "PRESPECIFIED_SECONDARY_DESCRIPTIVE", "families": fam}


def attainment(rows, target):
    points = []
    for config in PROFILES:
        subset = [r for r in rows if historic.configuration(r) == config]
        require(len(subset) == 300, "Attainment denominator differs")
        hits = Counter(r["targets"][str(target)]["first_total_evaluation"] for r in subset)
        misses = hits.pop(None, 0)
        # Equal numbers of paired repeats per task and tasks per family give equal event weights.
        cumulative = 0
        for q in sorted({0, TOTAL, *hits}):
            cumulative += hits[q]
            points.append({"configuration": profile_name(config), "target": target, "evaluations": q,
                           "reached": cumulative, "denominator": 300, "percent": 100 * cumulative / 300})
        require(cumulative + misses == 300, "Final attainment count differs")
    return points


def analyze(compacts, inputs, out, authorization_id):
    _, authorization = common.guard("main")
    require(authorization["authorization_id"] == authorization_id, "Analysis authorization differs")
    rows, evidence, source, manifest_hash = load_cases(Path(compacts), Path(inputs), authorization)
    summaries, family_metrics, vectors = summarize(rows)
    pairs, family_effects, supported, draw_hash = primary_comparisons(vectors)
    secondary = secondary_diagnostic(rows, vectors)
    curves = {target: attainment(rows, target) for target in TARGETS}
    for target, sequence in curves.items():
        endpoints = {r["configuration"]: r["reached"] for r in sequence if r["evaluations"] == TOTAL}
        require(all(endpoints[r["configuration"]] == r[f"attained_{target}"] for r in summaries),
                "Figure and table attainment totals differ")
    output = Path(out)
    output.mkdir(parents=True, exist_ok=False)
    summary = {"schema": "independent-validation100-analysis-v1", "status": "VERIFIED_1200",
        "physical_runs": EXPECTED, "families": 10, "tasks": 30, "runs_per_profile": 300,
        "search_evaluations_including_initial": EXPECTED * TOTAL,
        "bca": {"nominal_confidence_each": float(CONFIDENCE), "registered_comparisons": 6,
                "draws": 50000, "seed": 160031, "resampling_unit": "family",
                "resample_index_sha256": draw_hash, "bias_ties": "half", "quantiles": "linear"},
        "profiles": summaries, "primary": pairs, "secondary": secondary,
        "quality_base_confirmed_against_both_distinct_controls": supported,
        "source_manifest_sha256": authorization["source_manifest_sha256"],
        "inputs_manifest_sha256": manifest_hash, "authorization_id": authorization_id,
        "workflow_run_id": os.environ["GITHUB_RUN_ID"], "workflow_commit": os.environ["GITHUB_SHA"]}
    write_json(output / "summary.json", summary)
    write_csv(output / "profiles.csv", summaries)
    write_csv(output / "family-metrics.csv", family_metrics)
    write_csv(output / "primary-comparisons.csv", pairs)
    write_csv(output / "family-effects.csv", family_effects)
    write_csv(output / "secondary-speed.csv", secondary["families"])
    for target, sequence in curves.items():
        write_csv(output / f"attainment-{target}.csv", sequence)
    from .report import build_report
    build_report(output, summary, curves, family_effects)
    generated = [{"path": p.relative_to(output).as_posix(), "bytes": p.stat().st_size, "sha256": sha(p)}
                 for p in sorted(output.rglob("*")) if p.is_file()]
    write_json(output / "provenance.json", {"status": summary["status"], "source_manifest_sha256":
        summary["source_manifest_sha256"], "inputs_manifest_sha256": manifest_hash,
        "selection_sha256": source["selection_sha256"], "workflow_run_id": summary["workflow_run_id"],
        "workflow_commit": summary["workflow_commit"], "cases": evidence, "generated": generated})
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for option in ("compacts", "inputs", "out", "authorization-id"):
        parser.add_argument("--" + option, required=True)
    args = parser.parse_args()
    result = analyze(args.compacts, args.inputs, args.out, args.authorization_id)
    print(json.dumps({"status": result["status"], "physical_runs": result["physical_runs"]}))
