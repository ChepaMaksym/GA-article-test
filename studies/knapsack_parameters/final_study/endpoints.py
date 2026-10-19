"""Prospective quality endpoints; no search or exact-solver dependency.

The authorization for the 10-run resource probe does not release confirmatory
statistics. Pure endpoint fixtures are exercised only by CI software tests.
"""
from collections import defaultdict
from fractions import Fraction
import os
import re
from statistics import fmean

CONTRAST_IDS = ("static_winner_over_base", "mutation_over_classical",
                "crossover_over_classical", "balanced_over_unbalanced")


def _require(ok, message):
    if not ok:
        raise ValueError(message)


def _ci_only():
    _require(os.environ.get("GITHUB_ACTIONS") == "true" and
             os.environ.get("GITHUB_REPOSITORY") == "ChepaMaksym/GA-article-test" and
             os.environ.get("GITHUB_REF") == "refs/heads/research/masters-ga-diversity-crossover",
             "Endpoint computation is CI-only")


def gap_percent(optimum, value):
    _ci_only()
    _require(type(optimum) is int and optimum > 0 and type(value) is int and 0 <= value <= optimum,
             "Invalid exact quality endpoint")
    return 100 * Fraction(optimum - value, optimum)


def prefix_record(log, new_queries):
    """Reconstruct an endpoint, including evaluated children of an unfinished block.

    This does not change/resume population state and is not another search run.
    Callers must also authenticate/replay the full original journal.
    """
    _ci_only()
    _require(type(new_queries) is int and 0 <= new_queries <= log["budget"] and
             len(log["candidates"]) == log["budget"], "Incomplete journal or invalid prefix")
    problem = log["problem"]
    def score(mask):
        _require(type(mask) is str and len(mask) == problem["n"] and set(mask) <= {"0", "1"},
                 "Invalid endpoint witness mask")
        weight = sum(w for bit, w in zip(mask, problem["weights"], strict=True) if bit == "1")
        profit = sum(v for bit, v in zip(mask, problem["profits"], strict=True) if bit == "1")
        return {"weight": weight, "profit": profit, "feasible": weight <= problem["capacity"]}
    _require(len(log["initial_masks"]) == len(log["initial_scores"]) and log["initial_masks"],
             "Missing known beginning")
    best, best_mask, best_query = -1, None, None
    for mask, known in zip(log["initial_masks"], log["initial_scores"], strict=True):
        actual = score(mask)
        _require(actual == known, "Incorrect initial endpoint score")
        if actual["feasible"] and actual["profit"] > best:
            best, best_mask, best_query = actual["profit"], mask, 0
    _require(best >= 0, "No initial feasible record")
    for query, row in enumerate(log["candidates"][:new_queries], 1):
        actual = score(row["mask"])
        _require(row["call"] == query and all(row[key] == value for key, value in actual.items()),
                 "Corrupted endpoint query or witness")
        if actual["feasible"] and actual["profit"] > best:
            best, best_mask, best_query = actual["profit"], row["mask"], query
    return {"known_initial_positions": len(log["initial_masks"]), "new_queries": new_queries,
            "total_logical_evaluations": len(log["initial_masks"]) + new_queries,
            "best_profit": best, "best_mask": best_mask, "best_new_query": best_query,
            "derived_prefix_not_an_additional_run": True}


def family_means(rows):
    """Equal repeats -> equal tasks -> equal families, including unequal class counts."""
    _ci_only()
    tasks, identities = defaultdict(list), set()
    for row in rows:
        task, seed, value = row["task"], row["seed"], row["value"]
        _require(type(task) is str and re.fullmatch(r"(?:UC|WC|SC)-s\d{3}", task) is not None and
                 type(seed) is int and (task, seed) not in identities, "Duplicate or invalid weighting identity")
        identities.add((task, seed))
        tasks[task].append(Fraction(value))
    _require(tasks, "No family observations")
    families = defaultdict(list)
    for task, values in tasks.items():
        families[task.split("-")[1]].append(sum(values) / len(values))
    return {family: sum(values) / len(values) for family, values in sorted(families.items())}


def four_gap_intervals(family_vectors, *, software_fixture=False):
    """Independent registered contrast streams; production remains resource-gated."""
    _ci_only()
    from . import authority as a
    grant = a.resource_grant()
    _require(software_fixture is True or grant.get("confirmatory_statistics_authorized") is True,
             "BLOCKED_MAIN_RESOURCE_APPROVAL: no confirmatory statistics for a resource probe")
    import numpy as np
    from studies.knapsack_parameters.ga_study.statistics import bca_family_intervals
    values = np.asarray(family_vectors, dtype=float)
    _require(values.ndim == 2 and values.shape[1] == 4 and values.shape[0] > 0 and
             np.isfinite(values).all(), "Four finite family gap effects required")
    results = []
    for column, name in enumerate(CONTRAST_IDS):
        # Historical BCa implementation is reused unmodified; only its labels
        # are replaced for this separate, explicitly registered four-endpoint study.
        entropy = [91031, column]
        derived_seed = int(np.random.SeedSequence(entropy).generate_state(1, dtype=np.uint64)[0])
        computed = bca_family_intervals(values, seed=derived_seed, confidence_level=0.9875,
                                        replicates=50000)
        interval = dict(computed["intervals"][column])
        interval["contrast_id"] = name
        interval["rng_entropy"] = entropy
        interval["derived_seed"] = derived_seed
        interval["resample_index_sha256"] = computed["resample_index_sha256"]
        results.append(interval)
    return {"scope": "SOFTWARE_FIXTURE" if software_fixture else "FINAL_RANDOM_START_QUALITY",
            "method": "BCa", "family_count": len(values), "replicates": 50000,
            "confidence_each": 0.9875, "positive_direction": "control gap minus investigated gap",
            "intervals": results}
