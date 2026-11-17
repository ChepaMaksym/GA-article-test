"""Exact descriptive processing of immutable tuning records, executed in CI.

The public pure helpers accept already loaded values so CI unit tests can
exercise boundaries without importing a GA, a solver, or a plotting library.
``summarize`` and the CLI require GitHub Actions before reading evidence or
performing analysis. Historical aggregate CSV and selection JSON beside the
source are checked, never rewritten.

Output contract (schema ``knapsack-iterative-validation-analysis-v1``):
``summary.json`` contains ``configuration_metrics`` (four frozen configurations),
``pair_summaries`` (all six A/B pairs), ``ranking_audit`` (all 31 historical
configurations), ``audit`` and the unchanged ``historical_selection``. Each
rational is exported as {value, numerator, denominator}; CSV rational columns
have matching ``_numerator``/``_denominator`` companions. ``provenance.json``
binds every input and generated artifact by SHA-256. Run, family, paired and
leave-one-family-out CSV files retain their full individual rows. Attainment
flags distinguish an event at 100000 from nonattainment restricted to 100000.
"""

from __future__ import annotations

import argparse
from collections import defaultdict
import csv
from fractions import Fraction
import gzip
import hashlib
from itertools import combinations
import json
import math
import os
from pathlib import Path
import re
from typing import Iterable, Mapping, Sequence


SCHEMA = "knapsack-iterative-validation-analysis-v1"
SOURCE_SCHEMA = "mutation-grid-100-validated-union-v1"
SOURCE_SHA256 = "70adbcca7b27e645f8a01b7f8662358d62c347bf02a4edb825996ebf62a1af32"
TOTAL = 100000
TARGETS = (93, 95, 99)
CHECKPOINTS = (5000, 10000, 20000, 50000, TOTAL)
FAMILIES = tuple(f"s{i:03d}" for i in range(50, 60))
TYPES = ("UC", "WC", "SC")
SEEDS = (150001, 150002, 150003)
CONFIGS = tuple(sorted(
    {(mu, pc, 100) for mu in (10, 15, 20, 25) for pc in (70, 80, 90, 100)}
    | {(mu, 100, bp) for mu in (10, 15, 20) for bp in (25, 50, 75, 100, 150, 200)}
))
SELECTED_CONFIGS = ((10, 90, 100), (15, 90, 100), (15, 100, 100), (20, 90, 100))
PRIMARY_PAIR = (SELECTED_CONFIGS[0], SELECTED_CONFIGS[1])
RAW_FILES = frozenset(("journal.json.gz", "verification.json", "operator_bins.json",
                       "observations.json.gz", "record.json"))
METRICS = ("gap_100000_percent", "restricted_t93", "restricted_t95", "restricted_t99",
           "restricted_t100", *(f"gap_{q}_percent" for q in CHECKPOINTS[:-1]))


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError("Invalid iterative validation: " + message)


def require_ci() -> None:
    require(os.environ.get("GITHUB_ACTIONS") == "true", "GitHub Actions is required")


def _integer(value, minimum=0, maximum=None) -> bool:
    return (type(value) is int and value >= minimum
            and (maximum is None or value <= maximum))


def _digest(value) -> bool:
    return type(value) is str and re.fullmatch(r"[0-9a-f]{64}", value) is not None


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def configuration(row: Mapping) -> tuple[int, int, int]:
    values = tuple(row.get(k) for k in ("mu", "pc_percentage", "mutation_basis_points"))
    require(all(type(v) is int for v in values), "configuration parameters must be integers")
    return values


def configuration_id(config: Sequence[int]) -> str:
    mu, pc, bp = config
    return f"mu{mu}-pc{pc}-pm{bp}bp"


def _config(config: Sequence[int]) -> dict:
    return {"configuration_id": configuration_id(config),
            **dict(zip(("mu", "pc_percentage", "mutation_basis_points"), config))}


def identity(row: Mapping) -> tuple:
    return row["task"], row["seed"], *configuration(row)


def mean(values: Iterable) -> Fraction:
    values = list(values)
    require(bool(values), "cannot average an empty group")
    return sum((Fraction(value) for value in values), Fraction()) / len(values)


def validate_events(events, optimum: int, total: int = TOTAL,
                    best: int | None = None) -> tuple[tuple[int, int], ...]:
    """Check a complete increasing record trace on q=1..total, inclusively.

    A compact trace records improvements, so its last event need not be at
    ``total``. It must begin at q=1. Initial evaluations and the final allowed
    evaluation receive the same treatment as every other evaluation.
    """
    require(_integer(optimum, 1) and _integer(total, 1), "invalid optimum or evaluation limit")
    require(type(events) in (list, tuple) and bool(events), "record events are missing")
    converted = []
    for event in events:
        require(type(event) in (list, tuple) and len(event) == 2,
                "each record event must contain q and profit")
        q, value = event
        require(_integer(q, 1, total) and _integer(value, 0, optimum), "invalid integer record event")
        if converted:
            require(q > converted[-1][0] and value > converted[-1][1],
                    "record events must strictly increase in q and profit")
        converted.append((q, value))
    require(converted[0][0] == 1, "record history must begin with evaluation 1")
    if best is not None:
        require(_integer(best, 0, optimum) and best == converted[-1][1],
                "final best differs from record events")
    return tuple(converted)


def first_attainment(events, optimum: int, threshold: int, total: int = TOTAL) -> dict:
    """First integer-exact ``100 * profit >= threshold * optimum`` event.

    The restricted value equals ``total`` both for an event at the last
    evaluation and for nonattainment; ``attained`` preserves that distinction.
    ``threshold=100`` measures attainment of the exact optimum.
    """
    require(_integer(threshold, 1, 100), "target must be an integer percent in 1..100")
    trace = validate_events(events, optimum, total)
    first = next((q for q, value in trace if 100 * value >= threshold * optimum), None)
    return {"attained": first is not None, "first_total_evaluation": first,
            "restricted_evaluations": total if first is None else first}


def _record_at(events: Sequence, q: int) -> int:
    return next(value for event_q, value in reversed(events) if event_q <= q)


def _check_optional_gap(row: Mapping, expected: Fraction) -> None:
    for name in ("final_gap_percent", "gap_percent"):
        if name in row:
            _stored_number(row[name], expected, name)


def _stored_number(stored, exact, name: str) -> None:
    """Compare retained binary/decimal presentation only at its precision.

    Scientific ranking and diagnostics always use the untouched Fraction.
    This tolerance is solely for historically serialized float means.
    """
    require(type(stored) in (str, int, float) and not isinstance(stored, bool),
            "invalid stored numeric field: " + name)
    try:
        number = float(stored)
    except (TypeError, ValueError, OverflowError) as error:
        raise ValueError("Invalid stored numeric field: " + name) from error
    if type(exact) is int:
        require(math.isfinite(number) and Fraction(str(stored)) == exact,
                "stored integer/count field differs: " + name)
        return
    tolerance = 1e-12 if ("gap" in name or "attainment" in name) else 1e-9
    require(math.isfinite(number) and abs(number - float(exact)) <= tolerance,
            "stored numeric field differs: " + name)


def _validate_row(row: Mapping) -> None:
    require(type(row) is dict, "a run must be an object")
    config = configuration(row)
    require(config in CONFIGS, "configuration is outside the frozen 31-configuration grid")
    family, kind, seed = row.get("family"), row.get("class_label"), row.get("seed")
    require(family in FAMILIES and kind in TYPES and type(seed) is int and seed in SEEDS,
            "family, task type or seed is outside the frozen rectangle")
    require(row.get("task") == f"n00100-{kind}-{family}", "task differs from n=100 family/type")
    expected_index = 3 + (int(family[1:]) - 50) * 3 + TYPES.index(kind)
    require(type(row.get("task_index")) is int and row["task_index"] == expected_index,
            "task index differs from the frozen registry")
    for name, expected in (("n", 100), ("total_evaluations", TOTAL),
                           ("initial_evaluations", config[0]), ("new_evaluations", TOTAL - config[0])):
        if name in row:
            require(type(row[name]) is int and row[name] == expected, name + " differs")
    optimum, best = row.get("optimum"), row.get("best")
    require(_integer(optimum, 1) and _integer(best, 0, optimum), "invalid integer optimum or final best")
    events = validate_events(row.get("events"), optimum, best=best)
    require(events[0] == (1, 0), "frozen initial evaluation must be the empty mask")
    require(type(row.get("targets")) is dict and set(row["targets"]) == {str(t) for t in TARGETS},
            "stored target inventory differs")
    for target in TARGETS:
        expected = first_attainment(events, optimum, target)
        stored = row["targets"][str(target)]
        require(type(stored) is dict and type(stored.get("attained")) is bool,
                "stored attainment flag must be Boolean")
        require(stored.get("attained") == expected["attained"]
                and stored.get("first_total_evaluation") == expected["first_total_evaluation"]
                and (stored.get("first_total_evaluation") is None
                     or type(stored["first_total_evaluation"]) is int)
                and type(stored.get("restricted_evaluations")) is int
                and stored["restricted_evaluations"] == expected["restricted_evaluations"],
                "stored threshold hit differs from integer record events")
    checkpoints = row.get("checkpoints")
    require(type(checkpoints) is list and len(checkpoints) == len(CHECKPOINTS)
            and all(type(p) is dict for p in checkpoints), "five checkpoint objects are required")
    require(all(type(p.get("q")) is int for p in checkpoints), "checkpoint q must be an integer")
    by_q = {p.get("q"): p for p in checkpoints}
    require(len(by_q) == len(CHECKPOINTS) and set(by_q) == set(CHECKPOINTS),
            "checkpoint inventory differs")
    for q in CHECKPOINTS:
        point = by_q[q]
        profit = _record_at(events, q)
        require(type(point.get("q")) is int and type(point.get("record_profit")) is int
                and point["record_profit"] == profit, "stored checkpoint differs from events")
        require(type(point.get("completed_generations")) is int
                and point["completed_generations"] == (q - config[0]) // (config[0] - 1),
                "checkpoint generation accounting differs")
        population = point.get("population_metrics")
        require(type(population) is dict and type(population.get("population_size")) is int
                and population["population_size"] == config[0], "checkpoint population differs")
        _check_optional_gap(point, Fraction(100 * (optimum - profit), optimum))
    require(type(row.get("completed_generations")) is int
            and row["completed_generations"] == (TOTAL - config[0]) // (config[0] - 1),
            "terminal generation accounting differs")
    require(_integer(row.get("duplicates"), 0, TOTAL - config[0]), "invalid duplicate count")
    require(_digest(row.get("bank_sha256")) and _digest(row.get("certificate_sha256")),
            "initial-bank or exact-reference checksum is missing")
    hashes = row.get("artifact_hashes")
    require(type(hashes) is dict and set(hashes) == RAW_FILES
            and all(_digest(v) for v in hashes.values()), "raw artifact checksum inventory differs")
    prefix = row.get("artifact_prefix")
    require(type(prefix) is str and prefix.startswith(f'{row["task"]}/seed-{seed}/')
            and ".." not in prefix.split("/") and "\\" not in prefix and ":" not in prefix,
            "artifact identity/path differs")
    timing = row.get("timing")
    require(type(timing) is dict and type(timing.get("search_seconds")) in (int, float)
            and math.isfinite(timing["search_seconds"]) and timing["search_seconds"] >= 0,
            "search timing is invalid")
    _check_optional_gap(row, Fraction(100 * (optimum - best), optimum))


def validate_source(document: Mapping) -> list[dict]:
    """Fail closed on the complete 2790-row, 31 by 90 paired source."""
    require(type(document) is dict and set(document) == {"provenance", "runs", "schema", "status"},
            "source document fields differ")
    require(document["schema"] == SOURCE_SCHEMA and document["status"] == "VERIFIED_2790",
            "source schema/status is not the frozen verified union")
    provenance = document["provenance"]
    require(type(provenance) is dict and provenance.get("status") == "ALL_CASES_INDEPENDENTLY_VERIFIED"
            and provenance.get("retained_cases") == 1440 and provenance.get("new_cases") == 1350,
            "source verification provenance differs")
    rows = document["runs"]
    require(type(rows) is list and len(rows) == 2790, "exactly 2790 source runs are required")
    expected = {(f"n00100-{kind}-{family}", seed, *config)
                for family in FAMILIES for kind in TYPES for seed in SEEDS for config in CONFIGS}
    seen, banks, references = set(), defaultdict(set), defaultdict(set)
    for row in rows:
        _validate_row(row)
        key = identity(row)
        require(key not in seen, "duplicate source run identity")
        seen.add(key)
        banks[(row["task"], row["seed"])].add(row["bank_sha256"])
        references[row["task"]].add((row["optimum"], row["certificate_sha256"]))
    require(seen == expected, "source task/seed/configuration rectangle differs")
    require(all(len(v) == 1 for v in banks.values()), "paired configurations use different initial banks")
    require(all(len(v) == 1 for v in references.values()), "task exact optimum/certificate differs")
    return rows


def read_source(source, expected_sha256: str) -> dict:
    """Authenticate compressed bytes before parsing; never substitute evidence."""
    require(_digest(expected_sha256), "expected SHA-256 must be 64 lowercase hexadecimal characters")
    path = Path(source)
    require(path.is_file(), "source evidence does not exist")
    require(sha256(path) == expected_sha256, "source SHA-256 mismatch")
    with gzip.open(path, "rt", encoding="utf-8") as stream:
        document = json.load(stream)
    require(type(document) is dict, "source must be a JSON object")
    return document


load_source = read_source


def _run_metrics(row: Mapping) -> dict:
    result = {**_config(configuration(row)),
              **{k: row[k] for k in ("task", "family", "class_label", "seed", "optimum", "best")},
              "n": 100, "total_evaluations": TOTAL,
              "search_seconds": Fraction(str(row["timing"]["search_seconds"]))}
    for q in CHECKPOINTS:
        result[f"gap_{q}_percent"] = Fraction(100 * (row["optimum"] - _record_at(row["events"], q)), row["optimum"])
    result["final_gap_percent"] = result["gap_100000_percent"]
    for target in (*TARGETS, 100):
        endpoint = first_attainment(row["events"], row["optimum"], target)
        result[f"attained_{target}"] = endpoint["attained"]
        result[f"first_t{target}"] = endpoint["first_total_evaluation"]
        result[f"restricted_t{target}"] = endpoint["restricted_evaluations"]
    return result


def _hierarchical(values: Sequence[Mapping], metric: str) -> tuple[Fraction, dict[str, Fraction]]:
    """Average repetitions, then tasks, then families with equal weights."""
    tasks = defaultdict(list)
    for row in values:
        tasks[(row["family"], row["task"])].append(row[metric])
    families = defaultdict(list)
    for (family, _), task_values in tasks.items():
        families[family].append(mean(task_values))
    family_means = {family: mean(values) for family, values in sorted(families.items())}
    return mean(family_means.values()), family_means


def aggregate(run_metrics: Sequence[Mapping]) -> list[dict]:
    """Exact equally weighted summaries; full-rectangle admission is separate."""
    grouped = defaultdict(list)
    seen = set()
    for row in run_metrics:
        key = identity(row)
        require(key not in seen, "duplicate run metric identity")
        seen.add(key)
        grouped[configuration(row)].append(row)
    require(bool(grouped), "run metrics are empty")
    result = []
    for config, rows in sorted(grouped.items()):
        value = {**_config(config), "runs": len(rows),
                 "tasks": len({r["task"] for r in rows}), "families": len({r["family"] for r in rows})}
        for metric in METRICS:
            average, families = _hierarchical(rows, metric)
            value["mean_" + metric] = average
            value["worst_family_" + metric] = max(families.values())
        value["mean_search_seconds"] = _hierarchical(rows, "search_seconds")[0]
        for target in (*TARGETS, 100):
            attained = sum(r[f"attained_{target}"] for r in rows)
            value[f"attained_{target}"] = attained
            value[f"not_attained_{target}"] = len(rows) - attained
            value[f"attainment_{target}"] = _hierarchical(rows, f"attained_{target}")[0]
            value[f"nonattainment_{target}"] = 1 - value[f"attainment_{target}"]
        result.append(value)
    return result


def _family_metrics(run_metrics: Sequence[Mapping]) -> list[dict]:
    groups = defaultdict(list)
    for row in run_metrics:
        groups[(configuration(row), row["family"])].append(row)
    return [{**_config(config), "family": family, **aggregate(rows)[0]}
            for (config, family), rows in sorted(groups.items())]


def _pair_analysis(run_metrics: Sequence[Mapping]) -> tuple[list, list, list, list]:
    by_config = defaultdict(dict)
    for row in run_metrics:
        by_config[configuration(row)][(row["task"], row["seed"])] = row
    paired, family_rows, pair_summaries, loo_rows = [], [], [], []
    for a, b in combinations(SELECTED_CONFIGS, 2):
        left, right = by_config[a], by_config[b]
        require(set(left) == set(right) and len(left) == 90, "selected configurations are not paired over all 90 runs")
        pair_id = configuration_id(a) + "__" + configuration_id(b)
        meta = {"pair_id": pair_id, "configuration_a": configuration_id(a),
                "configuration_b": configuration_id(b), "primary_diagnostic": (a, b) == PRIMARY_PAIR}
        group = []
        for key in sorted(left):
            ra, rb = left[key], right[key]
            value = {**meta, **{k: ra[k] for k in ("task", "family", "class_label", "seed")}}
            for metric in METRICS:
                value["delta_" + metric] = rb[metric] - ra[metric]
            for target in (*TARGETS, 100):
                value[f"attained_a_{target}"] = ra[f"attained_{target}"]
                value[f"attained_b_{target}"] = rb[f"attained_{target}"]
            paired.append(value)
            group.append(value)
        summary = {**meta, "paired_runs": 90, "families": len(FAMILIES)}
        families = {family: {**meta, "family": family, "paired_runs": 9} for family in FAMILIES}
        for metric in METRICS:
            delta = "delta_" + metric
            average, family_means = _hierarchical(group, delta)
            summary["mean_" + delta] = average
            summary["a_earlier_or_smaller_" + metric] = sum(r[delta] > 0 for r in group)
            summary["b_earlier_or_smaller_" + metric] = sum(r[delta] < 0 for r in group)
            summary["ties_" + metric] = sum(r[delta] == 0 for r in group)
            for family in FAMILIES:
                families[family]["mean_" + delta] = family_means[family]
        family_rows.extend(families.values())
        pair_summaries.append(summary)
        for omitted in FAMILIES:
            remaining = [r for r in group if r["family"] != omitted]
            value = {**meta, "omitted_family": omitted, "remaining_families": 9,
                     "remaining_paired_runs": len(remaining)}
            for metric in METRICS:
                average = _hierarchical(remaining, "delta_" + metric)[0]
                value["mean_delta_" + metric] = average
                value["direction_" + metric] = "A" if average > 0 else "B" if average < 0 else "tie"
            loo_rows.append(value)
    return paired, family_rows, pair_summaries, loo_rows


def _ranks(metrics: Sequence[Mapping]) -> list[dict]:
    gap_sorted = sorted(metrics, key=lambda r: (r["mean_gap_100000_percent"], configuration(r)))
    speed_sorted = sorted(metrics, key=lambda r: (r["mean_restricted_t93"], configuration(r)))
    # Equal exact means share competition ranks; configuration only orders ties.
    def rank_map(ordered, key):
        result, rank, previous = {}, 0, None
        for index, row in enumerate(ordered, 1):
            if previous is None or row[key] != previous:
                rank = index
            result[row["configuration_id"]] = rank
            previous = row[key]
        return result
    gap_ranks = rank_map(gap_sorted, "mean_gap_100000_percent")
    speed_ranks = rank_map(speed_sorted, "mean_restricted_t93")
    return [{**row, "final_gap_rank": gap_ranks[row["configuration_id"]],
             "t93_rank": speed_ranks[row["configuration_id"]],
             "selected_for_diagnostic": configuration(row) in SELECTED_CONFIGS}
            for row in gap_sorted]


def analyze(document: Mapping, source_sha256: str | None = None) -> dict:
    """Admit all source runs and compute a descriptive audit with exact means."""
    require_ci()
    source_rows = validate_source(document)
    all_runs = [_run_metrics(row) for row in source_rows]
    all_metrics = aggregate(all_runs)
    selected_runs = [r for r in all_runs if configuration(r) in SELECTED_CONFIGS]
    paired, family_differences, pair_summaries, loo = _pair_analysis(selected_runs)
    return {
        "schema": SCHEMA, "status": "DESCRIPTIVE_AUDIT_COMPLETE", "source_sha256": source_sha256,
        "audit": {"source_runs": len(source_rows), "source_configurations": len(CONFIGS),
                  "selected_runs": len(selected_runs), "selected_configurations": len(SELECTED_CONFIGS),
                  "paired_runs_per_comparison": 90, "pair_comparisons": 6, "tasks": 30,
                  "families": 10, "types_per_family": 3, "repetitions_per_task": 3,
                  "n": 100, "total_evaluations_including_initial": TOTAL,
                  "event_histories_verified": len(source_rows), "stored_targets_verified": len(source_rows) * 3,
                  "stored_checkpoints_verified": len(source_rows) * len(CHECKPOINTS),
                  "audit_scope": "retained compact events, endpoints, identities and historical aggregates; no new full-journal replay",
                  "historical_float_tolerance_gap_percentage_points": 1e-12,
                  "historical_float_tolerance_evaluations": 1e-9,
                  "historical_count_comparison": "exact",
                  "aggregation": "equal repetitions, then equal tasks, then equal families",
                  "delta_definition": "B minus A; positive means A earlier or smaller gap",
                  "inference": "descriptive only; no bootstrap, hypothesis tests or equivalence claims",
                  "historical_selection_replaced": False, "new_search_runs": 0},
        "run_metrics": selected_runs,
        "configuration_metrics": [r for r in all_metrics if configuration(r) in SELECTED_CONFIGS],
        "family_metrics": _family_metrics(selected_runs), "paired_differences": paired,
        "family_differences": family_differences, "pair_summaries": pair_summaries,
        "leave_one_family_out": loo, "ranking_audit": _ranks(all_metrics),
    }


def _audit_historical(result: dict, source: Path) -> tuple[dict, list[Path]]:
    table_path, selection_path = source.parent / "all-configurations.csv", source.parent / "selection.json"
    require(table_path.is_file() and selection_path.is_file(), "historical aggregate CSV and selection JSON are required beside the source")
    with table_path.open("r", encoding="utf-8-sig", newline="") as stream:
        stored_rows = list(csv.DictReader(stream, delimiter=";"))
    metrics = {configuration(r): r for r in result["ranking_audit"]}
    seen, checked = set(), 0
    for row in stored_rows:
        try:
            config = tuple(int(row[k]) for k in ("mu", "pc_percentage", "mutation_basis_points"))
        except (ValueError, TypeError, KeyError) as error:
            raise ValueError("Invalid historical CSV configuration") from error
        require(config in metrics and config not in seen, "historical aggregate configuration inventory differs")
        seen.add(config)
        current = metrics[config]
        for field, stored in row.items():
            if field in ("mu", "pc_percentage", "mutation_basis_points"):
                continue
            # The historical names for the two extrema omit 'restricted'.
            name = "worst_family_restricted_t93" if field == "worst_family_t93" else field
            require(name in current, "unknown historical aggregate metric: " + str(field))
            _stored_number(stored, current[name], field)
            checked += 1
    require(seen == set(CONFIGS) and len(stored_rows) == 31, "all 31 historical aggregate rows are required")
    selection = json.loads(selection_path.read_text(encoding="utf-8-sig"))
    require(selection.get("schema") == "mutation-grid-100-selections-v1"
            and selection.get("status") == "SELECTED_BEFORE_VALIDATION"
            and selection.get("source_records_sha256") == result["source_sha256"]
            and selection.get("selection_is_descriptive") is True
            and selection.get("independent_validation_started") is False,
            "historical selection identity/status differs")
    selections = selection.get("selections")
    require(type(selections) is dict and set(selections) == {"quality", "speed"}, "historical selection roles differ")
    frozen = {"quality": (15, 100, 100), "speed": (10, 90, 100)}
    def preferences(config):
        mu, pc, bp = config
        return abs(bp - 100), abs(pc - 90), mu, bp, pc
    reproduced = {
        "quality": min(CONFIGS, key=lambda c: (metrics[c]["mean_gap_100000_percent"],
            metrics[c]["worst_family_gap_100000_percent"], metrics[c]["mean_restricted_t93"], *preferences(c))),
        "speed": min(CONFIGS, key=lambda c: (metrics[c]["mean_restricted_t93"], metrics[c]["nonattainment_93"],
            metrics[c]["mean_gap_100000_percent"], metrics[c]["worst_family_restricted_t93"], *preferences(c))),
    }
    require(reproduced == frozen, "exact historical selection-rule audit differs from the retained selection")
    for role, selected in selections.items():
        config = configuration(selected)
        require(config == frozen[role], "historical selection configuration differs")
        for stored_name, metric_name in (("mean_final_gap_exact", "mean_gap_100000_percent"),
                                          ("mean_restricted_t93_exact", "mean_restricted_t93")):
            rational = selected.get(stored_name)
            require(type(rational) is dict and _integer(rational.get("numerator"))
                    and _integer(rational.get("denominator"), 1), "historical exact mean is malformed")
            require(Fraction(rational["numerator"], rational["denominator"]) == metrics[config][metric_name],
                    "historical exact mean differs")
    require(selection.get("same_configuration") is False, "historical selection identity flag differs")
    return {"aggregate_numeric_fields_checked": checked, "aggregate_csv_verified": True,
            "historical_exact_selection_verified": True, "historical_selection_rule_verified": True,
            "selection": selection}, [table_path, selection_path]


def json_ready(value):
    if isinstance(value, Fraction):
        return {"value": float(value), "numerator": value.numerator, "denominator": value.denominator}
    if isinstance(value, Mapping):
        return {str(k): json_ready(v) for k, v in value.items()}
    if isinstance(value, (tuple, list)):
        return [json_ready(v) for v in value]
    return value


def write_json(path: Path, value) -> None:
    path.write_text(json.dumps(json_ready(value), ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def write_csv(path: Path, rows: Sequence[Mapping]) -> None:
    require(bool(rows), "cannot export an empty CSV")
    expanded = []
    for row in rows:
        value = {}
        for key, field in row.items():
            if isinstance(field, Fraction):
                value[key] = repr(float(field))
                value[key + "_numerator"] = field.numerator
                value[key + "_denominator"] = field.denominator
            elif type(field) is bool:
                value[key] = "true" if field else "false"
            else:
                value[key] = field
        expanded.append(value)
    fields = list(dict.fromkeys(key for row in expanded for key in row))
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fields, delimiter=";", lineterminator="\n")
        writer.writeheader()
        writer.writerows(expanded)


def summarize(source, expected_sha256: str, output) -> dict:
    """Authenticate, audit and export the stage in a fresh output directory."""
    require_ci()
    require(expected_sha256 == SOURCE_SHA256, "source differs from the frozen historical SHA-256")
    source, output = Path(source).resolve(), Path(output).resolve()
    require(output != source.parent and source.parent not in output.parents,
            "outputs must be outside the retained source evidence directory")
    require(not output.exists(), "output directory already exists; use a fresh CI destination")
    document = read_source(source, expected_sha256)
    result = analyze(document, expected_sha256)
    historical, siblings = _audit_historical(result, source)
    result["audit"].update({k: v for k, v in historical.items() if k != "selection"})
    result["historical_selection"] = historical["selection"]
    output.mkdir(parents=True)
    tables = {"run-metrics.csv": "run_metrics", "configuration-metrics.csv": "configuration_metrics",
              "family-metrics.csv": "family_metrics", "paired-differences.csv": "paired_differences",
              "family-differences.csv": "family_differences", "paired-summary.csv": "pair_summaries",
              "leave-one-family-out.csv": "leave_one_family_out", "ranking-audit.csv": "ranking_audit"}
    for filename, key in tables.items():
        write_csv(output / filename, result[key])
    summary = {key: value for key, value in result.items()
               if key not in ("run_metrics", "family_metrics", "paired_differences", "family_differences", "leave_one_family_out")}
    summary["tables"] = tables
    write_json(output / "summary.json", summary)
    from .report import render_report
    render_report(result, output)
    inputs = [{"name": p.name, "bytes": p.stat().st_size, "sha256": sha256(p)} for p in (source, *siblings)]
    artifacts = [{"path": p.relative_to(output).as_posix(), "bytes": p.stat().st_size, "sha256": sha256(p)}
                 for p in sorted(output.rglob("*")) if p.is_file()]
    write_json(output / "provenance.json", {"schema": SCHEMA, "source": document["provenance"],
               "source_schema": document["schema"], "source_status": document["status"],
               "inputs": inputs, "artifacts": artifacts,
               "github": {name: os.environ.get(name) for name in
                          ("GITHUB_REPOSITORY", "GITHUB_SHA", "GITHUB_RUN_ID", "GITHUB_RUN_ATTEMPT")},
               "provenance_manifest_excludes_itself": True})
    return summary


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--expected-sha256", required=True)
    parser.add_argument("--output", required=True, type=Path, help="fresh output directory")
    args = parser.parse_args(argv)
    require_ci()
    result = summarize(args.source, args.expected_sha256, args.output)
    print(json.dumps({"status": result["status"], "output": str(args.output), "audit": result["audit"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
