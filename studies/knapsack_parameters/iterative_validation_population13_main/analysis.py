"""CI-only descriptive comparison of one new configuration and frozen evidence.

The historical 31-configuration validator remains unchanged. New population-13
evidence has its own admission contract and is joined only after all 90 cases
have been independently verified. Importing this module performs no research.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
import csv
from fractions import Fraction
import gzip
import json
import math
import os
from pathlib import Path, PurePosixPath
import re

from .common import (HERE, ROOT, SOURCE_SHA256, TOTAL, descriptor, guard_main,
                     registered_cases, validate_case_origin)
from studies.knapsack_parameters.iterative_validation import analysis as historical
from studies.knapsack_parameters.population_validation_100.common import read_json, require, sha


NEW_CONFIGURATION = (13, 90, 100)
COMPARATORS = ((10, 90, 100), (15, 90, 100), (15, 100, 100), (20, 90, 100))
DISPLAY_CONFIGURATIONS = (COMPARATORS[0], NEW_CONFIGURATION, *COMPARATORS[1:])
TARGETS = (93, 95, 99)
CHECKPOINTS = (5000, 10000, 20000, 50000, 100000)
FAMILIES = tuple(f"s{number:03d}" for number in range(50, 60))
TYPES = ("UC", "WC", "SC")
SEEDS = (150001, 150002, 150003)
PAYLOADS = frozenset(("journal.json.gz", "verification.json", "operator_bins.json",
                      "observations.json.gz"))
FIXED_PARAMETERS = {"p_m": .01, "p_c": .9, "target_mu": 13,
                    "tournament_size": 2, "elite_count": 1}
COLORS = {(10, 90, 100): "#1764a0", (13, 90, 100): "#c53235",
          (15, 90, 100): "#db7625", (15, 100, 100): "#37935b",
          (20, 90, 100): "#9064b0"}
SCHEMA = "population13-main-descriptive-analysis-v1"


def _integer(value, minimum=0, maximum=None):
    return type(value) is int and value >= minimum and (maximum is None or value <= maximum)


def _digest(value):
    return type(value) is str and re.fullmatch(r"[0-9a-f]{64}", value) is not None


def _finite(value):
    return type(value) in (int, float) and math.isfinite(value) and value >= 0


def _safe(root, relative):
    require(type(relative) is str and relative and "\\" not in relative and ":" not in relative,
            "Unsafe analysis evidence path")
    pieces = PurePosixPath(relative)
    require(not pieces.is_absolute() and ".." not in pieces.parts
            and pieces.as_posix() == relative, "Noncanonical analysis evidence path")
    root = Path(root).resolve()
    path = root.joinpath(*pieces.parts)
    require(path.is_file() and not path.is_symlink() and path.resolve().is_relative_to(root),
            "Missing or unsafe analysis evidence: " + relative)
    return path


def _configuration(row):
    return historical.configuration(row)


def _label(config):
    mu, pc, mutation = config
    return f"{mu} / {pc}% / {mutation / 100:g}%"


def _population(point, mu):
    require(type(point) is dict and point.get("population_size") == mu,
            "Completed population size differs")
    for count, fraction in (("unique_count", "unique_fraction"), ("feasible_count", "feasible_fraction")):
        require(_integer(point.get(count), 1, mu) and _finite(point.get(fraction))
                and abs(point[fraction] - point[count] / mu) <= 1e-12,
                "Population count or fraction differs: " + count)
    pairs = mu * (mu - 1) // 2
    require(point.get("unordered_pairs") == pairs
            and _integer(point.get("pairwise_hamming_sum"), 0, 100 * pairs)
            and _finite(point.get("mean_pairwise_hamming"))
            and abs(point["mean_pairwise_hamming"] - point["pairwise_hamming_sum"] / pairs) <= 1e-12,
            "Population Hamming accounting differs")


def _validate_bins(operators, verified, new_calls):
    require(type(operators) is dict and operators.get("premutation_score_checks") == new_calls
            and verified.get("premutation_score_checks") == new_calls,
            "Independent operator-evaluation accounting differs")
    bins = operators.get("operator_bins")
    fields = {"distance", "total", "crossed", "novel_crossed", "feasible_crossed", "better_both_crossed"}
    require(type(bins) is list and len(bins) == 101
            and all(type(row) is dict and set(row) == fields for row in bins),
            "All 101 operator distance bins are required")
    require({row["distance"] for row in bins} == set(range(101)), "Operator distance bins differ")
    for row in bins:
        require(all(_integer(row[key]) for key in fields), "Operator-bin counts must be nonnegative integers")
        require(row["crossed"] <= row["total"]
                and all(row[key] <= row["crossed"] for key in
                        ("novel_crossed", "feasible_crossed", "better_both_crossed")),
                "Operator subset counts exceed their denominators")
    require(sum(row["total"] for row in bins) == new_calls, "Operator bins do not cover all offspring")


def new_compact(case, record, observed, verified, operators, record_sha256):
    """Validate admitted numerical receipts without invoking search or replay."""
    require(type(record) is dict and record.get("schema") == "population13-main-case-v1"
            and record.get("status") == "VERIFIED", "Only verified main-case receipts are admissible")
    require(all(type(record.get(key)) is type(value) and record[key] == value for key, value in case.items()
                if key not in {"problem", "certificate", "source", "bank"}),
            "Main case differs from its exact registered identity")
    require(_configuration(record) == NEW_CONFIGURATION and record.get("tournament_size") == 2
            and record.get("elite_count") == 1, "Fixed main configuration differs")
    mu, new_calls = 13, TOTAL - 13
    for key, value in (("initial_evaluations", mu), ("new_evaluations", new_calls),
                       ("total_evaluations", TOTAL), ("completed_generations", 8332),
                       ("terminal_partial_children", 3)):
        require(type(record.get(key)) is int and record[key] == value, "Main evaluation receipt differs: " + key)
    require(type(observed) is dict and observed.get("schema") == "population-crossover-observations-v1"
            and observed.get("total_evaluations") == TOTAL and observed.get("initial_evaluations") == mu
            and observed.get("new_evaluations") == new_calls
            and observed.get("search_evaluations_performed") == 0,
            "Postsearch observations must not add search evaluations")
    optimum, best = observed.get("optimum"), observed.get("final_best_profit")
    require(_integer(optimum, 1) and _integer(best, 0, optimum), "Invalid reference optimum or feasible record")
    raw_events = observed.get("record_events")
    require(type(raw_events) is list and all(type(item) is dict for item in raw_events), "Record events are absent")
    events = historical.validate_events([[item.get("q"), item.get("profit")] for item in raw_events],
                                        optimum, best=best)
    require(events[0] == (1, 0), "The first evaluated chromosome must be the empty chromosome")
    for item in raw_events:
        mask = item.get("mask")
        require(type(mask) is str and len(mask) == 100 and set(mask) <= {"0", "1"}
                and item.get("phase") == ("initializing" if item["q"] <= mu else "search"),
                "Event chromosome or total-evaluation phase differs")
    historical._stored_number(observed.get("final_gap_percent"), Fraction(100 * (optimum - best), optimum),
                              "final_gap_percent")
    targets = observed.get("targets")
    require(type(targets) is dict and set(targets) == {str(target) for target in TARGETS},
            "Target inventory differs")
    for target in TARGETS:
        expected = historical.first_attainment(events, optimum, target)
        actual = targets[str(target)]
        require(type(actual) is dict and type(actual.get("attained")) is bool
                and type(actual.get("restricted_evaluations")) is int
                and (actual.get("first_total_evaluation") is None
                     or type(actual["first_total_evaluation"]) is int)
                and actual == expected, "Stored target differs from integer-exact first attainment")
    require(observed.get("completed_generations") == 8332
            and observed.get("terminal_partial_offspring") == 3, "Observation generation accounting differs")
    points = observed.get("checkpoints")
    require(type(points) is list and len(points) == len(CHECKPOINTS)
            and all(type(point) is dict and type(point.get("q")) is int for point in points),
            "Five total-evaluation checkpoints are required")
    by_q = {point["q"]: point for point in points}
    require(len(by_q) == len(CHECKPOINTS) and set(by_q) == set(CHECKPOINTS), "Checkpoint inventory differs")
    for q in CHECKPOINTS:
        point = by_q[q]
        profit = historical._record_at(events, q)
        completed, partial = divmod(q - mu, mu - 1)
        require(point.get("record_profit") == profit and point.get("initial_evaluations") == mu
                and point.get("offspring_evaluations") == q - mu
                and point.get("completed_generations") == completed
                and point.get("partial_offspring_count") == partial
                and point.get("population_total_q") == mu + completed * (mu - 1)
                and point.get("phase") == "search" and point.get("parameters") == FIXED_PARAMETERS,
                "Checkpoint record, committed population, phase, or parameters differ")
        historical._stored_number(point.get("gap_percent"), Fraction(100 * (optimum - profit), optimum),
                                  "checkpoint_gap_percent")
        _population(point.get("population_metrics"), mu)
    require(type(verified) is dict and verified.get("verification_status") == "VERIFIED",
            "Independent verifier receipt is missing")
    expected_checks = {"new_calls": new_calls, "initial_score_checks": mu,
                       "final_score_checks": new_calls, "premutation_score_checks": new_calls,
                       "independent_score_checks": mu + 2 * new_calls,
                       "completed_generations": 8332, "partial_generations": 1, "record_profit": best}
    require(all(type(verified.get(key)) is int and verified[key] == value
                for key, value in expected_checks.items()), "Independent replay accounting differs")
    require(verified.get("final_parameters") == FIXED_PARAMETERS
            and type(verified.get("summary")) is dict
            and verified["summary"].get("partial_children") == 3,
            "Independent final parameter or partial-block receipt differs")
    _validate_bins(operators, verified, new_calls)
    require(_integer(verified.get("duplicate_candidates"), 0, new_calls), "Invalid independently counted duplicates")
    require(_finite(record.get("search_seconds")) and _digest(record_sha256), "Invalid timing or record-file digest")
    require(all(_digest(record.get(name)) for name in
                ("bank_sha256", "certificate_sha256", "problem_sha256", "source_manifest_sha256")),
            "Original input or source-manifest digest is absent")
    hashes = record.get("artifact_hashes")
    require(type(hashes) is dict and set(hashes) == PAYLOADS and all(_digest(value) for value in hashes.values()),
            "The main payload-hash inventory differs")
    return {**{key: record[key] for key in ("case_id", "task", "task_index", "family", "class_label", "seed",
                                           "mu", "pc_percentage", "mutation_basis_points")},
            "n": 100, "total_evaluations": TOTAL, "initial_evaluations": mu, "new_evaluations": new_calls,
            "optimum": optimum, "best": best, "events": [list(event) for event in events],
            "targets": targets, "checkpoints": points, "completed_generations": 8332,
            "terminal_partial_children": 3, "duplicates": verified["duplicate_candidates"],
            "bank_sha256": record["bank_sha256"], "certificate_sha256": record["certificate_sha256"],
            "problem_sha256": record["problem_sha256"],
            "artifact_hashes": {**hashes, "record.json": record_sha256},
            "artifact_prefix": record["case_id"], "source_manifest_sha256": record["source_manifest_sha256"],
            "workflow_run_id": record["workflow_run_id"], "workflow_commit": record["workflow_commit"],
            "timing": {"search_seconds": record["search_seconds"]}}


def load_new_runs(results, inputs, authorization):
    """Authenticate all 90 full evidence bundles and their original inputs."""
    root, inputs = Path(results).resolve(), Path(inputs).resolve()
    require(root.is_dir() and inputs.is_dir(), "Results and prepared input directories are required")
    manifest_path = _safe(inputs, "manifest.json")
    manifest = read_json(manifest_path)
    require(manifest.get("schema") == "population13-main-inputs-v1"
            and manifest.get("status") == "NINETY_PAIRED_CASES_READY"
            and manifest.get("new_bank_count") == 0 and manifest.get("retained_bank_count") == 90
            and manifest.get("ga_runs") == 0 and manifest.get("exact_solver_calls") == 0
            and manifest.get("source_manifest_sha256") == authorization["source_manifest_sha256"],
            "Prepared input provenance differs")
    expected = {case["case_id"]: case for case in registered_cases()}
    prepared = manifest.get("cases")
    require(type(prepared) is list and len(prepared) == 90
            and all(type(case) is dict for case in prepared)
            and {case.get("case_id") for case in prepared} == set(expected), "Prepared case rectangle differs")
    files = manifest.get("files")
    require(type(files) is list and len({row.get("path") for row in files}) == len(files),
            "Prepared file inventory is duplicated")
    inventory = {row["path"]: row for row in files}
    for item in files:
        descriptor(inputs, item)
    by_id = {case["case_id"]: case for case in prepared}
    for case_id, case in by_id.items():
        require(all(type(case.get(key)) is type(value) and case[key] == value
                    for key, value in expected[case_id].items()), "Prepared case identity differs")
        for key in ("problem", "certificate", "source", "bank"):
            item = case.get(key)
            require(type(item) is dict and inventory.get(item.get("path")) == item,
                    "Prepared case descriptor differs from its inventory")
    paths = sorted(root.rglob("record.json"))
    require(len(paths) == 90, "Exactly 90 independently verified main receipts are required")
    seen, compact, evidence = set(), [], []
    current_input_sha = sha(manifest_path)
    for path in paths:
        require(not path.is_symlink() and path.resolve().is_relative_to(root), "Unsafe main-case receipt")
        record = read_json(path)
        require({item.name for item in path.parent.iterdir()} == PAYLOADS | {"record.json"}
                and all(item.is_file() and not item.is_symlink() for item in path.parent.iterdir()),
                "An analyzed completed case must contain exactly five canonical files")
        require(type(record) is dict and record.get("case_id") in expected
                and record["case_id"] not in seen, "Unknown or duplicate main-case identity")
        case_id = record["case_id"]
        origin = validate_case_origin(record, authorization)
        require(record.get("source_manifest_sha256") == authorization["source_manifest_sha256"],
                "Mixed main source seals")
        prior = str(record.get("workflow_run_id")) != os.environ.get("GITHUB_RUN_ID")
        expected_input_sha = origin.get("inputs_manifest_sha256") if prior else current_input_sha
        require(_digest(expected_input_sha) and record.get("inputs_manifest_sha256") == expected_input_sha,
                "Main receipt input manifest differs from its admitted origin")
        case = by_id[case_id]
        for key in ("bank", "certificate", "problem", "source"):
            require(record.get(key + "_sha256") == case[key]["sha256"],
                    "Main case is not paired with the original input: " + key)
        require(type(record.get("artifact_hashes")) is dict and set(record["artifact_hashes"]) == PAYLOADS,
                "Four case payloads are required")
        payloads = {}
        for name, digest in record["artifact_hashes"].items():
            item = _safe(path.parent, name)
            require(_digest(digest) and sha(item) == digest, "Case payload checksum differs: " + name)
            payloads[name] = item
        observed = read_json(payloads["observations.json.gz"])
        verified = read_json(payloads["verification.json"])
        operators = read_json(payloads["operator_bins.json"])
        value = new_compact(expected[case_id], record, observed, verified, operators, sha(path))
        certificate = read_json(descriptor(inputs, case["certificate"]))
        require(certificate.get("optimum") == value["optimum"], "Observation optimum differs from the exact certificate")
        compact.append(value)
        seen.add(case_id)
        evidence.append({"case_id": case_id, "record_sha256": sha(path),
                         "workflow_run_id": record["workflow_run_id"], "workflow_commit": record["workflow_commit"],
                         "inputs_manifest_sha256": record["inputs_manifest_sha256"],
                         "artifact_hashes": value["artifact_hashes"]})
    require(seen == set(expected), "Main task/seed rectangle is incomplete")
    return compact, evidence, manifest_path


def paired_diagnostics(metrics):
    """Describe four control-minus-population13 contrasts with equal family weights."""
    groups = defaultdict(dict)
    for row in metrics:
        key = (row["task"], row["seed"])
        require(key not in groups[_configuration(row)], "Duplicate paired metric identity")
        groups[_configuration(row)][key] = row
    new = groups[NEW_CONFIGURATION]
    require(len(new) == 90, "Population13 requires all 90 paired metrics")
    paired, family, omitted, summaries = [], [], [], []
    metrics_to_compare = ("gap_100000_percent", "restricted_t93", "restricted_t95", "restricted_t99")
    for config in COMPARATORS:
        control = groups[config]
        require(set(control) == set(new), "Control and new task/seed pairs differ")
        contrast = historical.configuration_id(config) + "_minus_" + historical.configuration_id(NEW_CONFIGURATION)
        rows = []
        for key in sorted(new):
            candidate, baseline = new[key], control[key]
            row = {"contrast": contrast, "control_configuration": historical.configuration_id(config),
                   "candidate_configuration": historical.configuration_id(NEW_CONFIGURATION),
                   **{name: candidate[name] for name in ("task", "family", "class_label", "seed")}}
            for metric in metrics_to_compare:
                row["delta_" + metric] = baseline[metric] - candidate[metric]
            paired.append(row)
            rows.append(row)
        summary = {"contrast": contrast, "control_configuration": historical.configuration_id(config),
                   "paired_runs": 90, "families": 10}
        by_family = {name: {"contrast": contrast, "family": name} for name in FAMILIES}
        for metric in metrics_to_compare:
            field = "delta_" + metric
            value, family_values = historical._hierarchical(rows, field)
            summary["mean_" + field] = value
            summary["candidate_smaller_" + metric] = sum(row[field] > 0 for row in rows)
            summary["control_smaller_" + metric] = sum(row[field] < 0 for row in rows)
            summary["ties_" + metric] = sum(row[field] == 0 for row in rows)
            for name in FAMILIES:
                by_family[name]["mean_" + field] = family_values[name]
        family.extend(by_family.values())
        summaries.append(summary)
        for name in FAMILIES:
            remaining = [row for row in rows if row["family"] != name]
            item = {"contrast": contrast, "omitted_family": name, "remaining_families": 9,
                    "remaining_pairs": len(remaining)}
            for metric in metrics_to_compare:
                item["mean_delta_" + metric] = historical._hierarchical(remaining, "delta_" + metric)[0]
            omitted.append(item)
    return paired, family, omitted, summaries


def attainment_curves(metrics, target):
    """Return monotone exact step data; every failed run stays in the denominator."""
    require(target in TARGETS, "Unregistered attainment target")
    groups, seen = defaultdict(list), set()
    for row in metrics:
        identity = historical.identity(row)
        require(identity not in seen, "Duplicate attainment-curve identity")
        seen.add(identity)
        groups[_configuration(row)].append(row)
    require(set(groups) == set(DISPLAY_CONFIGURATIONS), "Five curve configurations are required")
    grid = sorted({0, TOTAL} | {row[f"first_t{target}"] for row in metrics if row[f"attained_{target}"]})
    result = []
    expected_pairs = {(f"n00100-{kind}-{family}", seed)
                      for family in FAMILIES for kind in TYPES for seed in SEEDS}
    for config in DISPLAY_CONFIGURATIONS:
        rows = groups[config]
        require(len(rows) == 90 and {(row["task"], row["seed"]) for row in rows} == expected_pairs,
                "A curve must retain all 90 registered task/seed pairs")
        previous = Fraction()
        for q in grid:
            successes = sum(row[f"attained_{target}"] and row[f"first_t{target}"] <= q for row in rows)
            fraction = Fraction(successes, len(rows))
            require(fraction >= previous, "Attainment curve decreases")
            previous = fraction
            result.append({"configuration_id": historical.configuration_id(config), "mu": config[0],
                           "pc_percentage": config[1], "mutation_basis_points": config[2],
                           "target_percent": target, "q": q, "attained": successes,
                           "not_yet_attained": len(rows) - successes, "denominator": len(rows),
                           "attainment_percent": 100 * fraction})
    return result


def _write_json(path, value):
    path.write_bytes((json.dumps(historical.json_ready(value), ensure_ascii=False, indent=2,
                                allow_nan=False) + "\n").encode("utf-8"))


def _write_json_gz(path, value):
    # Compress the full union so the archived source rows do not dominate the
    # analysis allowance. The JSON values and exact rational fields are kept.
    payload = (json.dumps(historical.json_ready(value), ensure_ascii=False,
                          separators=(",", ":"), allow_nan=False) + "\n").encode("utf-8")
    with path.open("xb") as raw:
        with gzip.GzipFile(filename="", mode="wb", compresslevel=3, fileobj=raw, mtime=0) as stream:
            stream.write(payload)


def _write_csv(path, rows):
    require(bool(rows), "Cannot export an empty scientific CSV")
    values = []
    for row in rows:
        item = {}
        for key, value in row.items():
            if isinstance(value, Fraction):
                item[key] = repr(float(value))
                item[key + "_numerator"], item[key + "_denominator"] = value.numerator, value.denominator
            elif type(value) is bool:
                item[key] = "true" if value else "false"
            else:
                item[key] = value
        values.append(item)
    fields = list(dict.fromkeys(key for row in values for key in row))
    with path.open("x", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fields, delimiter=";", lineterminator="\n")
        writer.writeheader()
        writer.writerows(values)


def _plots(output, summaries, curves, family_rows):
    """Render the same admitted summaries exported in the numerical tables."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 11, "axes.grid": True,
                         "grid.alpha": .22, "svg.fonttype": "none"})
    folder = output / "figures"
    folder.mkdir()
    captions = []
    by_config = {_configuration(row): row for row in summaries}

    def save(fig, name, caption):
        fig.tight_layout()
        for suffix in ("png", "svg"):
            fig.savefig(folder / (name + "." + suffix), dpi=180, bbox_inches="tight")
        plt.close(fig)
        captions.append({"file": "figures/" + name + ".png", "caption": caption})

    fig, ax = plt.subplots(figsize=(8.6, 4.5))
    positions = list(range(len(DISPLAY_CONFIGURATIONS)))
    values = [float(by_config[c]["mean_gap_100000_percent"]) for c in DISPLAY_CONFIGURATIONS]
    ax.barh(positions, values, color=[COLORS[c] for c in DISPLAY_CONFIGURATIONS],
            label="Середнє кінцеве відставання")
    ax.set_yticks(positions, [_label(c) for c in DISPLAY_CONFIGURATIONS])
    ax.invert_yaxis()
    ax.set_xlabel("Кінцеве відставання від оптимуму, %")
    ax.set_ylabel("Популяція / схрещування / мутація")
    ax.set_xlim(left=0)
    ax.legend(loc="best")
    save(fig, "final-quality", "Кінцева якість після 100 000 загальних оцінювань. Менше значення відповідає кращій якості.")
    for target in TARGETS:
        for maximum in ((TOTAL, 2500) if target in (93, 95) else (TOTAL,)):
            fig, ax = plt.subplots(figsize=(8.6, 4.5))
            for config in DISPLAY_CONFIGURATIONS:
                rows = [row for row in curves[target] if historical.configuration(row) == config]
                ax.step([row["q"] for row in rows], [float(row["attainment_percent"]) for row in rows],
                        where="post", color=COLORS[config], label=_label(config), linewidth=1.7)
            ax.set_xlim(0, maximum)
            ax.set_ylim(0, 100)
            ax.set_xlabel("Загальна кількість оцінювань, включно з початком")
            ax.set_ylabel(f"Досягли {target}% оптимуму, % запусків")
            ax.ticklabel_format(style="plain", axis="x")
            ax.legend(loc="lower right", fontsize=9)
            suffix = "" if maximum == TOTAL else "-first2500"
            caption = (f"Досягнення {target}% оптимуму. По 90 запусків на конфігурацію; недосягнення залишаються у знаменнику. "
                       + ("Повний діапазон: 0–100 000 оцінювань." if maximum == TOTAL
                          else "Заздалегідь визначене збільшення ділянки 0–2500 оцінювань; повний діапазон збережено окремо."))
            save(fig, f"attainment-{target}" + suffix, caption)
    fig, ax = plt.subplots(figsize=(8.6, 4.5))
    for config in DISPLAY_CONFIGURATIONS:
        row = by_config[config]
        ax.scatter(float(row["mean_restricted_t93"]), float(row["mean_gap_100000_percent"]),
                   color=COLORS[config], label=_label(config), s=55, marker="D" if config == NEW_CONFIGURATION else "o")
    ax.set_xlabel("Обмежене середнє число оцінювань до 93% оптимуму")
    ax.set_ylabel("Середнє кінцеве відставання, %")
    ax.legend(loc="best", fontsize=9)
    save(fig, "speed-quality", "Швидкість досягнення 93% оптимуму та кінцева якість. Менші значення обох показників відповідають кращому результату.")
    for metric, label, units in (("gap_100000_percent", "Кінцеве відставання", "в.п."),
                                 ("restricted_t93", "Оцінювання до 93% оптимуму", "оцінювань")):
        fig, ax = plt.subplots(figsize=(9, 4.8))
        for config in COMPARATORS:
            name = historical.configuration_id(config) + "_minus_" + historical.configuration_id(NEW_CONFIGURATION)
            mapping = {row["family"]: row["mean_delta_" + metric] for row in family_rows if row["contrast"] == name}
            ax.plot(FAMILIES, [float(mapping[f]) for f in FAMILIES], marker="o", color=COLORS[config],
                    label=_label(config), linewidth=1.3)
        ax.axhline(0, color="#444444", linewidth=.9, label="Нульова різниця")
        ax.set_xlabel("Сімейство задач")
        ax.set_ylabel(f"Показник контролю мінус показник популяції 13, {units}")
        ax.tick_params(axis="x", rotation=35)
        ax.legend(loc="best", fontsize=8)
        save(fig, "family-" + metric, label + ": десять сімейних ефектів. Додатна різниця означає менший показник для популяції 13; це описова діагностика.")
    return captions


def _report(result, output, captions):
    metrics = {_configuration(row): row for row in result["configuration_metrics"]}
    table = ["| Популяція / схрещування / мутація | Кінцеве відставання, % | Оцінювань до 93% | Досягли 93% | Досягли 95% | Досягли 99% |",
             "|---|---:|---:|---:|---:|---:|"]
    for config in DISPLAY_CONFIGURATIONS:
        row = metrics[config]
        table.append(f"| {_label(config)} | {float(row['mean_gap_100000_percent']):.6f} | "
                     f"{float(row['mean_restricted_t93']):.6f} | {row['attained_93']}/90 | "
                     f"{row['attained_95']}/90 | {row['attained_99']}/90 |")
    new = metrics[NEW_CONFIGURATION]
    comparisons = []
    for row in result["pair_summaries"]:
        comparisons.append(f"- {row['control_configuration']}: відставання контролю мінус відставання популяції 13 "
                           f"становить {float(row['mean_delta_gap_100000_percent']):.6f} в.п.; "
                           f"різниця обмежених середніх до 93% становить {float(row['mean_delta_restricted_t93']):.6f} оцінювання. "
                           f"За часом до 93% менший показник популяції 13 отримано у {row['candidate_smaller_restricted_t93']} парах, "
                           f"контролю у {row['control_smaller_restricted_t93']}, збіг у {row['ties_restricted_t93']}.")
    text = ["# Популяція 13: якість і швидкість пошуку", "",
            "Виконано 90 нових запусків на 30 вже відомих задачах зі 100 предметами, по три повторення. "
            "Популяція становила 13 особин, схрещування 90%, мутація біта 1%, відбір із двох особин та одна елітна особина. "
            "Гранична кількість 100 000 оцінювань включає початкову популяцію.", "",
            "## Результати п’яти конфігурацій", "", *table, "",
            "Кількість оцінювань до 93% є обмеженим середнім: недосягнення цілі враховано як 100 000. "
            "Усереднення виконано послідовно за повтореннями, задачами та десятьма сімействами з однаковими вагами. "
            "Кінцеву якість та швидкість оцінено окремо.", "", "## Описові парні різниці", "", *comparisons, "",
            "Додатний ефект означає менший показник для популяції 13. Сімейні ефекти й оцінки з вилученням одного сімейства "
            "подано як діагностику впливу задач, без нових перевірок значущості, бутстрепу або тверджень про рівність.", "",
            "## Рисунки", ""]
    for item in captions:
        if item["file"].endswith(("attainment-93.png", "attainment-95.png")):
            text.extend([f"[Повний рисунок]({item['file']}): {item['caption']}", ""])
        else:
            text.extend([f"![]({item['file']})", "", item["caption"], ""])
    extrema = result["descriptive_extrema"]
    new_ranks = result["new_configuration_ranks"]
    text += ["## Висновки", "",
             f"Для популяції 13 середнє кінцеве відставання становить {float(new['mean_gap_100000_percent']):.6f}%, "
             f"обмежене середнє число оцінювань до 93% оптимуму {float(new['mean_restricted_t93']):.6f}. "
             f"Цілі 93%, 95% і 99% досягли відповідно {new['attained_93']}, {new['attained_95']} та {new['attained_99']} із 90 запусків.", "",
             f"Серед 32 фактично перевірених конфігурацій найменше спостережене середнє кінцеве відставання мають "
             f"{', '.join(extrema['smallest_final_gap'])}; найменше обмежене середнє до 93% мають "
             f"{', '.join(extrema['smallest_restricted_t93'])}. Популяція 13 має місце {new_ranks['final_gap_rank']} за середнім "
             f"кінцевим відставанням та {new_ranks['t93_rank']} за обмеженим середнім до 93%. Точні рівності середніх отримують однакове місце.", "",
             "Підсумкова таблиця 32 конфігурацій містить 2880 унікальних результатів. Історичні 31 конфігурацію, "
             "2790 записів та зафіксований вибір двох рекомендацій збережено. Популяцію 13 додано після перегляду результатів; "
             "порівняння на s050–s059 є додатковим описовим дослідженням відомих задач. Критерій швидкості становить число оцінювань; "
             "машинний час у CSV обліковує витрати виконання. Незалежна перевірка на нових задачах "
             "до результатів цієї серії не входить. Втрати до 7%, 5% і 1% відповідають цілям 93%, 95% та 99% оптимуму.", ""]
    (output / "report.md").write_bytes("\n".join(text).encode("utf-8"))


def analyze(results, out, authorization_id=None, inputs=None):
    protocol, authorization = guard_main(authorization_id)
    require(inputs is not None, "Prepared inputs must be supplied to authenticate the comparison")
    output = Path(out)
    require(not output.exists(), "Preserve completed or incomplete prior analysis")
    source = ROOT / "studies/knapsack_parameters/iterative_validation/data/validated_records.json.gz"
    document = historical.read_source(source, SOURCE_SHA256)
    historical_rows = historical.validate_source(document)
    historical_metrics = [historical._run_metrics(row) for row in historical_rows]
    old_aggregates = historical.aggregate(historical_metrics)
    frozen_audit, siblings = historical._audit_historical(
        {"source_sha256": SOURCE_SHA256, "ranking_audit": historical._ranks(old_aggregates)}, source)
    new_rows, evidence, input_manifest_path = load_new_runs(results, inputs, authorization)
    by_pair = {(row["task"], row["seed"]): row for row in new_rows}
    for row in historical_rows:
        candidate = by_pair[(row["task"], row["seed"])]
        require(row["bank_sha256"] == candidate["bank_sha256"]
                and row["certificate_sha256"] == candidate["certificate_sha256"]
                and row["optimum"] == candidate["optimum"],
                "New and historical configurations do not share original banks or exact references")
    all_rows = [*historical_rows, *new_rows]
    all_metrics = [*historical_metrics, *(historical._run_metrics(row) for row in new_rows)]
    require(len(all_rows) == 2880 and len({historical.identity(row) for row in all_rows}) == 2880
            and len({_configuration(row) for row in all_rows}) == 32, "The verified union must contain 32 by 90 unique runs")
    selected = [row for row in all_metrics if _configuration(row) in DISPLAY_CONFIGURATIONS]
    require(len(selected) == 450, "Five complete 90-run configurations are required")
    summaries = historical.aggregate(selected)
    paired, families, omitted, contrasts = paired_diagnostics(selected)
    curves = {target: attainment_curves(selected, target) for target in TARGETS}
    rankings = [{**row, "selected_for_diagnostic": _configuration(row) in DISPLAY_CONFIGURATIONS,
                 "historical_configuration": _configuration(row) in historical.CONFIGS,
                 "new_configuration": _configuration(row) == NEW_CONFIGURATION}
                for row in historical._ranks(historical.aggregate(all_metrics))]
    minimum_gap = min(row["mean_gap_100000_percent"] for row in rankings)
    minimum_time = min(row["mean_restricted_t93"] for row in rankings)
    descriptive_extrema = {
        "smallest_final_gap": [row["configuration_id"] for row in rankings if row["mean_gap_100000_percent"] == minimum_gap],
        "smallest_restricted_t93": [row["configuration_id"] for row in rankings if row["mean_restricted_t93"] == minimum_time],
        "not_a_replacement_of_frozen_recommendations": True,
    }
    new_ranking = next(row for row in rankings if _configuration(row) == NEW_CONFIGURATION)
    result = {"schema": SCHEMA, "status": "VERIFIED_90_DESCRIPTIVE_COMPARISON_COMPLETE",
              "historical_source_sha256": SOURCE_SHA256, "historical_runs": 2790, "new_runs": 90,
              "union_runs": 2880, "union_configurations": 32, "selected_runs": 450,
              "tasks": 30, "families": 10, "repetitions_per_task": 3,
              "total_evaluations_including_initial": TOTAL, "new_search_evaluations_including_initial": 9000000,
              "source_manifest_sha256": authorization["source_manifest_sha256"],
              "workflow_run_id": os.environ["GITHUB_RUN_ID"], "workflow_commit": os.environ["GITHUB_SHA"],
              "authorization_id": authorization["authorization_id"],
              "analysis_kind": "post_selection_descriptive_known_tasks",
              "aggregation": "repetitions_then_tasks_then_equal_weight_families",
              "effect_definition": "control_minus_population13_positive_favors_population13",
              "bootstrap_samples": 0, "new_significance_tests": False, "equivalence_claims": False,
              "historical_selection_replaced": False, "independent_validation": False,
              "historical_selection": frozen_audit["selection"], "historical_audit": frozen_audit,
              "descriptive_extrema": descriptive_extrema,
              "new_configuration_ranks": {key: new_ranking[key] for key in ("final_gap_rank", "t93_rank")},
              "configuration_metrics": summaries, "pair_summaries": contrasts,
              "ranking_audit": rankings, "family_differences": families, "leave_one_family_out": omitted}
    output.mkdir(parents=True, exist_ok=False)
    _write_json(output / "summary.json", result)
    _write_json_gz(output / "verified-union.json.gz", {"schema": "population13-main-verified-union-v1",
                "status": "VERIFIED_2880", "historical_source_sha256": SOURCE_SHA256,
                "historical_records_unchanged": True, "new_cases_independently_verified": 90, "runs": all_rows})
    _write_csv(output / "all-32-configurations.csv", rankings)
    _write_csv(output / "five-configurations.csv", summaries)
    _write_csv(output / "run-metrics.csv", selected)
    _write_csv(output / "family-metrics.csv", historical._family_metrics(selected))
    _write_csv(output / "paired-differences.csv", paired)
    _write_csv(output / "family-differences.csv", families)
    _write_csv(output / "leave-one-family-out.csv", omitted)
    _write_csv(output / "pair-summaries.csv", contrasts)
    for target in TARGETS:
        _write_csv(output / f"attainment-{target}.csv", curves[target])
    figures = _plots(output, summaries, curves, families)
    _report(result, output, figures)
    _write_json(output / "figure-captions.json", figures)
    generated = [{"path": path.relative_to(output).as_posix(), "bytes": path.stat().st_size, "sha256": sha(path)}
                 for path in sorted(output.rglob("*")) if path.is_file()]
    _write_json(output / "provenance.json", {"schema": "population13-main-analysis-provenance-v1",
                "historical_source": {"path": source.relative_to(ROOT).as_posix(), "sha256": SOURCE_SHA256},
                "historical_audit_siblings": [{"path": path.relative_to(ROOT).as_posix(), "sha256": sha(path)} for path in siblings],
                "prepared_inputs_manifest_sha256": sha(input_manifest_path), "new_case_evidence": evidence,
                "source_manifest_sha256": authorization["source_manifest_sha256"],
                "workflow_run_id": os.environ["GITHUB_RUN_ID"], "workflow_commit": os.environ["GITHUB_SHA"],
                "generated": generated})
    size = sum(path.stat().st_size for path in output.rglob("*") if path.is_file())
    require(size <= protocol["limits"]["analysis_artifact_bytes"], "Analysis artifact limit exceeded")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results", type=Path, required=True)
    parser.add_argument("--inputs", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--authorization-id", required=True)
    args = parser.parse_args()
    result = analyze(args.results, args.out, args.authorization_id, args.inputs)
    print(json.dumps({"status": result["status"], "new_runs": result["new_runs"],
                      "union_runs": result["union_runs"], "historical_selection_replaced": False}))


if __name__ == "__main__":
    main()
