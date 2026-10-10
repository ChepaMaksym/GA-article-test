"""Exploratory review of frozen GA evidence; scientific execution is CI-only.

This module never calls a search kernel or an exact solver.  Compact witnesses
and the complete frozen run rectangle are checked before any statistics are
computed.  Historical inferential results remain separate from secondary
leave-one-family-out diagnostics and descriptive correlations.
"""

from __future__ import annotations

import argparse
from collections import defaultdict
import gzip
import hashlib
import json
import math
import os
from pathlib import Path
from statistics import NormalDist
from typing import Mapping, Sequence

import numpy as np

from studies.knapsack_parameters.ga_study.statistics import bca_family_intervals

from .contract import (
    MODULE_ROOT, PROTOCOL_ID, SOURCE_ROOT, SOURCE_RUN, SOURCE_SHA,
    load_context, output_directory, read_json, require, write_file_manifest, write_json,
)


LIMIT = 5000
SEEDS = tuple(range(51001, 51031))
MUTATIONS = (0.5, 1.0, 3.0)
CROSSOVERS = (0.0, 0.5, 0.9)
POPULATIONS = (10, 30, 50)
FAMILIES = tuple(f"s{i:03d}" for i in range(10))
CONTRAST_IDS = (
    "mutation_3_over_1", "crossover_09_over_0", "population_50_over_10",
    "mutation_crossover_interaction",
)
BASELINE = "m1-c0p9-n30"
COMPACT_FIELDS = frozenset((
    "instance_id", "start_profile", "repeat_seed", "configuration_id",
    "mutation_numerator", "crossover_probability", "population_size",
    "best_mask", "best_profit", "best_weight", "best_request",
    "escape_event", "first_escape_request", "censored", "logical_requests",
    "physical_evaluations", "invalid_request_count", "duplicate_count",
    "complete_generations", "terminal_partial",
))


def configuration_grid() -> dict[str, dict]:
    """Define the frozen grid independently of the production GA kernel."""
    def token(value):
        return format(value, ".12g").replace(".", "p")
    return {
        f"m{token(m)}-c{token(c)}-n{n}": {
            "configuration_id": f"m{token(m)}-c{token(c)}-n{n}",
            "mutation_numerator": m, "crossover_probability": c,
            "population_size": n,
        }
        for m in MUTATIONS for c in CROSSOVERS for n in POPULATIONS
    }


def validate_source_report(report: dict) -> None:
    """Bind compact rows to the immutable completed source, not the new SHA."""
    require(report.get("implementation_commit_sha") == SOURCE_SHA,
            "source implementation SHA mismatch")
    require(report.get("protocol_id") == "GA-KNAPSACK-PARAMETERS-MAIN-V1"
            and report.get("status") == "COMPLETE_VERIFIED_MAIN",
            "source report is not the completed registered main series")
    for field, expected in (("runs", 35640), ("random_runs", 24300),
                            ("local_runs", 11340), ("logical_requests", 178200000),
                            ("source_job_count", 90)):
        require(type(report.get(field)) is int and report[field] == expected,
                f"source {field} mismatch")
    provenance = report.get("provenance", {})
    require(provenance.get("implementation_commit_sha") == SOURCE_SHA,
            "source provenance SHA mismatch")
    source_rows = provenance.get("sources", [])
    require(isinstance(source_rows, list) and len(source_rows) == 90,
            "source job provenance is incomplete")
    require(all(row.get("run_id") == SOURCE_RUN for row in source_rows),
            "source run provenance mismatch")


def validate_compact_row(row: dict, instance, case: dict) -> tuple:
    """Recompute the retained witness using integer sums in original bit order."""
    require(isinstance(row, dict) and set(row) == COMPACT_FIELDS,
            "unknown or missing compact fields")
    require(row["instance_id"] == instance.instance_id == case["instance_id"],
            "compact instance mismatch")
    seed = row["repeat_seed"]
    require(type(seed) is int and seed in SEEDS, "seed outside frozen main series")
    profile = row["start_profile"]
    require(profile in ("random", "local"), "unknown start profile")
    require(profile != "local" or case["status"].startswith("ADMITTED_"),
            "local result from a nonadmitted center")
    configs = configuration_grid()
    config_id = row["configuration_id"]
    require(config_id in configs, "unknown configuration ID")
    config = configs[config_id]
    for field, expected in config.items():
        require(row[field] == expected and not isinstance(row[field], bool),
                f"configuration parameter mismatch: {field}")
    size = config["population_size"]
    require(type(row["population_size"]) is int, "population size is not an integer")
    require(type(row["logical_requests"]) is int and row["logical_requests"] == LIMIT,
            "logical request limit mismatch")
    require(type(row["physical_evaluations"]) is int
            and row["physical_evaluations"] == LIMIT - size,
            "physical search request count mismatch")
    complete, remainder = divmod(LIMIT - size, size - 1)
    require(type(row["complete_generations"]) is int
            and row["complete_generations"] == complete
            and type(row["terminal_partial"]) is bool
            and row["terminal_partial"] is bool(remainder),
            "terminal-generation accounting mismatch")
    for field in ("duplicate_count", "invalid_request_count"):
        require(type(row[field]) is int and 0 <= row[field] <= LIMIT,
                f"invalid compact counter: {field}")
    require(type(row["best_request"]) is int and 1 <= row["best_request"] <= LIMIT,
            "invalid best request number")
    mask = row["best_mask"]
    require(isinstance(mask, str) and len(mask) == instance.n
            and set(mask) <= {"0", "1"}, "invalid best witness mask")
    require(len(instance.weights) == len(instance.profits) == instance.n,
            "witness item arrays have inconsistent dimensions")
    weight = sum(w for bit, w in zip(mask, instance.weights, strict=True) if bit == "1")
    profit = sum(v for bit, v in zip(mask, instance.profits, strict=True) if bit == "1")
    require(type(row["best_weight"]) is int and type(row["best_profit"]) is int
            and weight == row["best_weight"] and profit == row["best_profit"]
            and weight <= instance.capacity, "best-mask integer witness mismatch")
    optimum = case["payload"]["exact"]["confirmed_optimum"]
    require(type(optimum) is int and optimum > 0 and 0 <= profit <= optimum,
            "witness profit outside the confirmed optimum")
    if profile == "local":
        center = case["payload"]["certificate"]["center"]["profit"]
        require(type(row["escape_event"]) is bool and type(row["censored"]) is bool
                and row["censored"] is not row["escape_event"],
                "escape and censor flags are inconsistent")
        if row["escape_event"]:
            first = row["first_escape_request"]
            require(type(first) is int and size < first <= LIMIT
                    and profit > center and row["best_request"] >= first,
                    "escape endpoint is inconsistent with the best witness")
        else:
            require(row["first_escape_request"] is None and profit == center,
                    "nonevent changed the center record")
    else:
        require(row["escape_event"] is None and row["first_escape_request"] is None
                and row["censored"] is None, "random result has a local escape endpoint")
    return instance.instance_id, profile, seed, config_id


def validate_rectangle(rows: Sequence[dict], instances: Mapping, cases: Mapping) -> dict:
    grid = configuration_grid()
    expected = {
        (name, profile, seed, config)
        for name, case in cases.items()
        for profile in (("random", "local") if case["status"].startswith("ADMITTED_")
                        else ("random",))
        for seed in SEEDS for config in grid
    }
    found = set()
    for row in rows:
        require(isinstance(row, dict) and row.get("instance_id") in cases,
                "unknown compact instance")
        name = row["instance_id"]
        require(name in instances, "missing frozen item data")
        key = validate_compact_row(row, instances[name], cases[name])
        require(key in expected and key not in found, "duplicate or unexpected run identity")
        found.add(key)
    require(found == expected and len(rows) == len(expected),
            "incomplete compact seed/configuration/profile rectangle")
    local = [row for row in rows if row["start_profile"] == "local"]
    return {
        "runs": len(rows), "random_runs": len(rows) - len(local), "local_runs": len(local),
        "logical_requests": sum(row["logical_requests"] for row in rows),
        "physical_search_evaluations": sum(row["physical_evaluations"] for row in rows),
        "escape_events": sum(row["escape_event"] for row in local),
        "censored_nonevents": sum(row["censored"] for row in local),
        "events_at_limit": sum(row["escape_event"] and row["first_escape_request"] == LIMIT
                               for row in local),
        "retained_best_witnesses_verified": len(rows),
        "terminal_partial_runs": sum(row["terminal_partial"] for row in rows),
    }


def _instance_means(rows: Sequence[dict], extractor) -> dict[str, float]:
    grouped = defaultdict(list)
    for row in rows:
        grouped[row["instance_id"]].append(extractor(row))
    require(bool(grouped), "empty metric group")
    return {name: float(np.mean(grouped[name])) for name in sorted(grouped)}


def family_values(rows: Sequence[dict], cases: Mapping, extractor) -> dict[str, float]:
    """Each seed has equal weight within a task; each task within its family."""
    grouped = defaultdict(list)
    for name, value in _instance_means(rows, extractor).items():
        grouped[cases[name]["family"]].append(value)
    return {family: float(np.mean(grouped[family])) for family in sorted(grouped)}


def equal_family_mean(rows: Sequence[dict], cases: Mapping, extractor) -> float:
    return float(np.mean(list(family_values(rows, cases, extractor).values())))


def independent_contrasts(rates: np.ndarray) -> np.ndarray:
    values = np.asarray(rates, dtype=np.float64)
    require(values.shape == (3, 3, 3) and np.isfinite(values).all()
            and (values >= 0).all() and (values <= 1).all(), "invalid factorial rates")
    return np.asarray([
        np.mean(values[2, :, :] - values[1, :, :]),
        np.mean(values[:, 2, :] - values[:, 0, :]),
        np.mean(values[:, :, 2] - values[:, :, 0]),
        np.mean((values[2, 2, :] - values[1, 2, :])
                - (values[2, 0, :] - values[1, 0, :])),
    ])


def rebuild_family_contrasts(rows: Sequence[dict], cases: Mapping) -> tuple[list[dict], np.ndarray]:
    events = defaultdict(lambda: defaultdict(list))
    for row in rows:
        if row["start_profile"] == "local":
            key = (row["mutation_numerator"], row["crossover_probability"], row["population_size"])
            events[row["instance_id"]][key].append(int(row["escape_event"]))
    grouped = defaultdict(list)
    for name in sorted(events):
        rates = np.empty((3, 3, 3), dtype=np.float64)
        for m, mutation in enumerate(MUTATIONS):
            for c, crossover in enumerate(CROSSOVERS):
                for p, population in enumerate(POPULATIONS):
                    repetitions = events[name][(mutation, crossover, population)]
                    require(len(repetitions) == 30, "missing registered seed repetitions")
                    rates[m, c, p] = np.mean(repetitions)
        grouped[cases[name]["family"]].append((name, independent_contrasts(rates)))
    require(tuple(sorted(grouped)) == FAMILIES, "primary analysis does not contain all ten families")
    memberships, vectors = [], []
    for family in sorted(grouped):
        entries = grouped[family]
        vector = np.mean(np.stack([value for _, value in entries]), axis=0)
        vectors.append(vector)
        memberships.append({
            "family": family, "instances": [name for name, _ in entries],
            "classes": [cases[name]["class_label"] for name, _ in entries],
            "admitted_class_count": len(entries),
            "contrasts": dict(zip(CONTRAST_IDS, map(float, vector), strict=True)),
        })
    return memberships, np.stack(vectors)


def _undefined_interval(name: str, estimate: float, reason: str) -> dict:
    return {"contrast_id": name, "estimate": float(estimate), "lower": None,
            "upper": None, "status": "DESCRIPTIVE_ONLY", "reason": reason,
            "positive_effect_supported": False, "negative_effect_supported": False}


def diagnostic_bca(values: np.ndarray, *, seed_entropy: Sequence[int], replicates: int = 50000,
                   confidence_level: float = 0.9875) -> dict:
    """Independent BCa calculation using precisely the registered LOO RNG.

    Intervals are sensitivity diagnostics after outcomes were seen.  They are
    not additional superiority tests and are not substitutes for the primary CI.
    """
    matrix = np.asarray(values, dtype=np.float64)
    require(matrix.ndim == 2 and matrix.shape[1] == 4 and len(matrix) >= 2
            and np.isfinite(matrix).all(), "invalid diagnostic family matrix")
    require(type(replicates) is int and replicates > 1 and 0 < confidence_level < 1,
            "invalid diagnostic bootstrap settings")
    entropy = list(seed_entropy)
    require(bool(entropy) and all(type(value) is int and value >= 0 for value in entropy),
            "invalid diagnostic RNG entropy")
    n = len(matrix)
    estimates = matrix.mean(axis=0)
    result = {
        "method": "BCa", "role": "secondary_descriptive_stability_diagnostic",
        "family_count": n, "replicates": replicates,
        "seed_sequence_entropy": entropy,
        "rng": f"PCG64(SeedSequence({entropy}))", "confidence_level_each": confidence_level,
        "bootstrap_unit": "whole source-index family", "jackknife_unit": "whole source-index family",
        "ties": "half weight in bias correction", "quantile_method": "linear",
        "resample_index_sha256": None, "superiority_tests": False, "intervals": [],
    }
    if n < 5:
        result["intervals"] = [_undefined_interval(name, value, "fewer_than_five_families")
                               for name, value in zip(CONTRAST_IDS, estimates, strict=True)]
        return result
    rng = np.random.Generator(np.random.PCG64(np.random.SeedSequence(entropy)))
    indices = rng.integers(0, n, size=(replicates, n))
    result["resample_index_sha256"] = hashlib.sha256(
        indices.astype("<i8", copy=False).tobytes(order="C")).hexdigest()
    samples = matrix[indices].mean(axis=1)
    jackknife = (matrix.sum(axis=0) - matrix) / (n - 1)
    normal = NormalDist()
    alpha = 1 - confidence_level
    tails = (normal.inv_cdf(alpha / 2), normal.inv_cdf(1 - alpha / 2))
    for column, name in enumerate(CONTRAST_IDS):
        observed = float(estimates[column])
        distribution = samples[:, column]
        if np.all(distribution == distribution[0]):
            result["intervals"].append(_undefined_interval(name, observed, "degenerate_bootstrap_distribution"))
            continue
        jack = jackknife[:, column]
        delta = jack.mean() - jack
        denominator = 6 * float(np.sum(delta ** 2)) ** 1.5
        if denominator == 0 or not math.isfinite(denominator):
            result["intervals"].append(_undefined_interval(name, observed, "undefined_jackknife_acceleration"))
            continue
        acceleration = float(np.sum(delta ** 3)) / denominator
        fraction = float((np.count_nonzero(distribution < observed)
                          + 0.5 * np.count_nonzero(distribution == observed)) / replicates)
        if not 0 < fraction < 1:
            result["intervals"].append(_undefined_interval(name, observed, "nonfinite_bias_correction"))
            continue
        z0 = normal.inv_cdf(fraction)
        adjusted = []
        for tail in tails:
            divisor = 1 - acceleration * (z0 + tail)
            adjusted.append(math.nan if divisor == 0 or not math.isfinite(divisor)
                            else normal.cdf(z0 + (z0 + tail) / divisor))
        if (not all(math.isfinite(value) and 0 < value < 1 for value in adjusted)
                or adjusted[0] >= adjusted[1]):
            result["intervals"].append(_undefined_interval(name, observed, "invalid_adjusted_quantiles"))
            continue
        low, high = map(float, np.quantile(distribution, adjusted, method="linear"))
        if not (math.isfinite(low) and math.isfinite(high)) or low >= high:
            result["intervals"].append(_undefined_interval(name, observed, "nonfinite_reversed_or_degenerate_interval"))
            continue
        result["intervals"].append({
            "contrast_id": name, "estimate": observed, "lower": low, "upper": high,
            "status": "DIAGNOSTIC_BCA", "reason": None,
            "positive_effect_supported": False, "negative_effect_supported": False,
            "bias_correction": z0, "bias_fraction": fraction, "acceleration": acceleration,
            "adjusted_quantiles": adjusted,
            "interval_excludes_zero_above": low > 0, "interval_excludes_zero_below": high < 0,
        })
    return result


def average_ranks(values: Sequence[float]) -> np.ndarray:
    array = np.asarray(values, dtype=np.float64)
    require(array.ndim == 1 and len(array) > 0 and np.isfinite(array).all(),
            "ranks require a nonempty finite vector")
    order = np.argsort(array, kind="stable")
    ranks = np.empty(len(array), dtype=np.float64)
    first = 0
    while first < len(array):
        last = first + 1
        while last < len(array) and array[order[last]] == array[order[first]]:
            last += 1
        ranks[order[first:last]] = (first + 1 + last) / 2
        first = last
    return ranks


def descriptive_spearman(x: Sequence[float], y: Sequence[float]) -> dict:
    a, b = np.asarray(x, dtype=np.float64), np.asarray(y, dtype=np.float64)
    require(a.ndim == b.ndim == 1 and len(a) == len(b) and len(a) >= 2
            and np.isfinite(a).all() and np.isfinite(b).all(), "invalid paired correlation values")
    result = {"method": "Spearman average ranks", "n_families": len(a),
              "role": "descriptive_only", "p_value": None, "causal_claim": False}
    if np.all(a == a[0]) or np.all(b == b[0]):
        return {**result, "status": "UNDEFINED", "rho": None, "reason": "constant_series"}
    ra, rb = average_ranks(a), average_ranks(b)
    da, db = ra - ra.mean(), rb - rb.mean()
    denominator = math.sqrt(float(np.dot(da, da)) * float(np.dot(db, db)))
    require(denominator > 0, "nonconstant rank vector unexpectedly has zero variance")
    rho = float(np.dot(da, db)) / denominator
    return {**result, "status": "DESCRIPTIVE", "rho": max(-1.0, min(1.0, rho)), "reason": None}


def _gap(row: dict, cases: Mapping) -> float:
    optimum = cases[row["instance_id"]]["payload"]["exact"]["confirmed_optimum"]
    return (optimum - row["best_profit"]) / optimum


def summarize_group(rows: Sequence[dict], cases: Mapping) -> dict:
    """Report raw counts alongside the different equal-family estimand."""
    profile = rows[0]["start_profile"]
    require(all(row["start_profile"] == profile for row in rows), "mixed start profiles in metric group")
    value = {
        "start_profile": profile, "run_count": len(rows),
        "instance_count": len({row["instance_id"] for row in rows}),
        "family_count": len({cases[row["instance_id"]]["family"] for row in rows}),
        "logical_requests": sum(row["logical_requests"] for row in rows),
        "physical_search_evaluations": sum(row["physical_evaluations"] for row in rows),
        "invalid_request_count": sum(row["invalid_request_count"] for row in rows),
        "duplicate_count": sum(row["duplicate_count"] for row in rows),
        "mean_invalid_request_fraction_equal_family": equal_family_mean(
            rows, cases, lambda row: row["invalid_request_count"] / LIMIT),
        "mean_duplicate_fraction_equal_family": equal_family_mean(
            rows, cases, lambda row: row["duplicate_count"] / LIMIT),
        "mean_duplicate_count_equal_family": equal_family_mean(
            rows, cases, lambda row: row["duplicate_count"]),
        "mean_final_relative_gap_equal_family": equal_family_mean(rows, cases, lambda row: _gap(row, cases)),
        "mean_best_profit_equal_family": equal_family_mean(rows, cases, lambda row: row["best_profit"]),
        "terminal_partial_runs": sum(row["terminal_partial"] for row in rows),
    }
    if profile == "local":
        events = sum(row["escape_event"] for row in rows)
        value.update(
            escape_events=events, censored_nonevents=len(rows) - events,
            escape_rate_raw=events / len(rows),
            raw_escape_frequency=events / len(rows),
            escape_success_count=events, successes=events, nonevents=len(rows) - events,
            escape_rate_equal_family=equal_family_mean(rows, cases, lambda row: int(row["escape_event"])),
            events_at_limit=sum(row["escape_event"] and row["first_escape_request"] == LIMIT for row in rows),
            mean_restricted_escape_time_equal_family=equal_family_mean(
                rows, cases, lambda row: row["first_escape_request"] if row["escape_event"] else LIMIT),
        )
    return value


def baseline_metrics(rows: Sequence[dict], cases: Mapping, pairs: Sequence[dict]) -> tuple[list[dict], list[dict]]:
    families = []
    by_profile = {}
    for profile in ("random", "local"):
        subset = [row for row in rows if row["start_profile"] == profile and row["configuration_id"] == BASELINE]
        extractors = {
            "invalid_request_fraction": lambda row: row["invalid_request_count"] / LIMIT,
            "duplicate_fraction": lambda row: row["duplicate_count"] / LIMIT,
            "final_relative_gap": lambda row: _gap(row, cases),
        }
        if profile == "local":
            extractors["escape_frequency"] = lambda row: int(row["escape_event"])
        metrics = {name: family_values(subset, cases, extractor) for name, extractor in extractors.items()}
        require(all(tuple(values) == FAMILIES for values in metrics.values()),
                "baseline does not cover ten families")
        by_profile[profile] = metrics
        for family in FAMILIES:
            selected = [row for row in subset if cases[row["instance_id"]]["family"] == family]
            families.append({"start_profile": profile, "family": family,
                             "configuration_id": BASELINE,
                             "instances": sorted({row["instance_id"] for row in selected}),
                             "instance_count": len({row["instance_id"] for row in selected}),
                             "run_count": len(selected),
                             **{name: values[family] for name, values in metrics.items()}})
    correlations = []
    for pair in pairs:
        metrics = by_profile[pair["start"]]
        x = [metrics[pair["x"]][family] for family in FAMILIES]
        y = [metrics[pair["y"]][family] for family in FAMILIES]
        correlations.append({**pair, **descriptive_spearman(x, y),
                             "families": list(FAMILIES), "x_values": x, "y_values": y,
                             "configuration_id": BASELINE})
    return families, correlations


def _verify_primary(original: dict, reconstructed: dict, memberships: list[dict], source_report: dict) -> list[dict]:
    require(original.get("seed") == 51031 and original.get("replicates") == 50000
            and original.get("confidence_level_each") == 0.9875
            and original.get("family_count") == 10, "source primary settings changed")
    require(original.get("resample_index_sha256") == reconstructed.get("resample_index_sha256"),
            "historical bootstrap index stream did not reconstruct")
    require(len(original.get("intervals", [])) == len(reconstructed["intervals"]) == 4,
            "primary interval count mismatch")
    source_memberships = source_report.get("family_memberships", [])
    require(len(source_memberships) == len(memberships) == 10, "historical family membership mismatch")
    for old, new in zip(source_memberships, memberships, strict=True):
        for field in ("family", "instances", "classes", "admitted_class_count"):
            require(old[field] == new[field], f"family membership mismatch: {field}")
        for name in CONTRAST_IDS:
            require(math.isclose(old["contrasts"][name], new["contrasts"][name], rel_tol=1e-12, abs_tol=1e-12),
                    "family contrast did not independently reconstruct")
    output = []
    for old, new in zip(original["intervals"], reconstructed["intervals"], strict=True):
        require(old["contrast_id"] == new["contrast_id"] and old["status"] == new["status"],
                "primary contrast identity/status mismatch")
        for field in ("estimate", "lower", "upper", "bias_correction", "bias_fraction", "acceleration"):
            a, b = old.get(field), new.get(field)
            require((a is None and b is None) or (a is not None and b is not None
                    and math.isclose(a, b, rel_tol=1e-12, abs_tol=1e-12)),
                    f"primary reconstruction mismatch: {field}")
        output.append({**old, "independently_rebuilt_estimate": new["estimate"],
                       "reconstruction_match": True, "role": "immutable_registered_primary",
                       "unit": "escape-frequency difference; multiply by 100 for percentage points"})
    return output


def analyze(expected_sha: str, output: Path) -> dict:
    instances, cases, source_report, identity = load_context(expected_sha)
    validate_source_report(source_report)
    instances = instances if isinstance(instances, dict) else {item.instance_id: item for item in instances}
    rows = []
    with gzip.open(SOURCE_ROOT / "run-summaries.jsonl.gz", "rt", encoding="utf-8") as stream:
        for line in stream:
            require(len(line) <= 8192 and len(rows) < 35640, "oversized or extra compact run data")
            rows.append(json.loads(line))
    counts = validate_rectangle(rows, instances, cases)
    require(counts["runs"] == 35640 and counts["random_runs"] == 24300
            and counts["local_runs"] == 11340 and counts["logical_requests"] == 178200000,
            "completed source totals did not reconstruct")
    protocol = read_json(MODULE_ROOT / "protocol.json")
    memberships, vectors = rebuild_family_contrasts(rows, cases)
    rebuilt_primary = bca_family_intervals(vectors, replicates=50000, seed=51031, confidence_level=0.9875)
    original_primary = source_report["primary_statistics"]
    primary = _verify_primary(original_primary, rebuilt_primary, memberships, source_report)
    loo = [{"omitted_family": family, "omitted_index": i,
            "retained_families": [name for name in FAMILIES if name != family],
            "statistics": diagnostic_bca(np.delete(vectors, i, axis=0), seed_entropy=[53001, i])}
           for i, family in enumerate(FAMILIES)]
    baseline_families, correlations = baseline_metrics(rows, cases, protocol["correlations"]["pairs"])
    config_rows, instance_rows = defaultdict(list), defaultdict(list)
    for row in rows:
        config_rows[(row["start_profile"], row["configuration_id"])].append(row)
        instance_rows[(row["instance_id"], row["start_profile"])].append(row)
    configuration_summaries = [
        {**summarize_group(config_rows[(profile, config_id)], cases), **config,
         "baseline": config_id == BASELINE, "role": "conditional_descriptive_parameter_comparison"}
        for profile in ("random", "local") for config_id, config in configuration_grid().items()
    ]
    per_instance_counts = [
        {**summarize_group(group, cases), "instance_id": name,
         "family": cases[name]["family"], "class_label": cases[name]["class_label"],
         "preparation_status": cases[name]["status"],
         "admitted_to_local_series": cases[name]["status"].startswith("ADMITTED_"),
         "center_type": "strict" if cases[name]["payload"]["certificate"]["strict"] else "plateau",
         "center_profit": cases[name]["payload"]["certificate"]["center"]["profit"],
         "optimum_profit": cases[name]["payload"]["exact"]["confirmed_optimum"]}
        for (name, _), group in sorted(instance_rows.items())
    ]
    local_rows = [row for row in rows if row["start_profile"] == "local"]
    result = {
        **identity, "schema_version": "ga-knapsack-secondary-analysis-v1", "protocol_id": PROTOCOL_ID,
        "status": "COMPLETE_COMPACT_ANALYSIS", "exploratory": True,
        "source_run_id": SOURCE_RUN, "source_implementation_commit_sha": SOURCE_SHA,
        "new_search_runs": 0, "new_exact_solver_runs": 0,
        "compact_witness_verification": "all retained best masks independently verified using integer sums",
        "compact_verification_limit": "complete request/RNG/operator logs require the separate prespecified trace audit",
        "counts": counts, "local_all_configurations": summarize_group(local_rows, cases),
        "primary_contrasts": primary, "primary_statistics_original": original_primary,
        "primary_statistics_reconstructed": rebuilt_primary, "family_contrasts": memberships,
        "loo": loo, "baseline_by_family": baseline_families, "correlations": correlations,
        "configuration_summaries": configuration_summaries, "per_instance_counts": per_instance_counts,
        "units": {"effects": "fractions; 0.01 is one percentage point",
                  "fractions": "logical requests including initial population",
                  "final_gap": "(confirmed_optimum - best_profit) / confirmed_optimum",
                  "restricted_time": "one-based logical request, including initial population; nonevents=5000",
                  "family_weighting": "equal seeds within instance, equal instances within family, equal families"},
        "interpretation_limits": [
            "leave-one-family-out intervals are exploratory diagnostics, not new primary tests",
            "raw escape rates and equally weighted family rates are distinct estimands",
            "correlations are descriptive and do not establish causation",
            "no lambda correlation or superiority is measured by this fixed-parameter study",
            "failure to exit does not certify global optimality",
        ],
    }
    output = output_directory(output)
    write_json(output / "analysis.json", result)
    write_file_manifest(output)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="CI-only secondary analysis of frozen main-series evidence")
    parser.add_argument("--expected-sha", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        result = analyze(args.expected_sha, args.output)
    except Exception as exc:
        # A failed reconstruction must never silently fall back to old published numbers.
        # Even failure metadata must not overwrite a checkout or existing evidence.
        if os.environ.get("GITHUB_ACTIONS") == "true":
            try:
                failure_output = output_directory(args.output)
                write_json(failure_output / "analysis-failure.json", {
                    "schema_version": "ga-knapsack-secondary-analysis-failure-v1", "protocol_id": PROTOCOL_ID,
                    "status": "FAILED_COMPACT_ANALYSIS", "expected_sha": args.expected_sha,
                    "error_type": type(exc).__name__, "error": str(exc), "new_search_runs": 0,
                })
                write_file_manifest(failure_output)
            except (OSError, ValueError):
                pass
        raise
    print(json.dumps({"status": result["status"], "runs": result["counts"]["runs"],
                      "correlations": len(result["correlations"]), "loo_cases": len(result["loo"])},
                     sort_keys=True))


if __name__ == "__main__":
    main()
