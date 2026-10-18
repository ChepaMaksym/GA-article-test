"""Three-profile comparison over a common initial population and query budget.

This is infrastructure for the approved auxiliary-objective transfer, not an
authorization to launch a scientific series. The CI driver runs toy fixtures
only. Exact optima and certificates are absent from all search interfaces.
"""
from __future__ import annotations

from collections import Counter
import hashlib
import json
import os

from studies.adaptive_parameters.mutation_only import engine as historical_engine
from studies.knapsack_parameters.mutation_population import search as historical_search

from . import knapsack

PROFILES = ("classical", "unbalanced_gap", "balanced_gap")


def _require(condition, message):
    if not condition:
        raise ValueError(message)


def _ci_only():
    _require(os.environ.get("GITHUB_ACTIONS") == "true", "Execution is CI-only")
    _require(os.environ.get("GITHUB_REPOSITORY") == "ChepaMaksym/GA-article-test" and
             os.environ.get("GITHUB_REF") == "refs/heads/research/masters-ga-diversity-crossover",
             "Wrong repository or branch")


def run_profile(problem, initial_masks, initial_scores, method, seed, task_index,
                start_index, budget=5000):
    """Run one admitted profile and independently reconstruct its journal."""
    _ci_only()
    _require(method in PROFILES, "Unknown B-NTGA transfer profile")
    knapsack._problem(problem)
    _require(isinstance(initial_masks, list) and isinstance(initial_scores, list) and
             len(initial_masks) == len(initial_scores) == 30 and
             any(type(score) is dict and score.get("feasible") is True for score in initial_scores),
             "All profiles require 30 known starts with at least one feasible member")
    if method == "classical":
        # The historical method label remains fixed in the untouched log.
        result = historical_search.run_profile(problem, initial_masks, initial_scores,
                                                "fixed", seed, task_index, start_index, budget)
        return {"requested_profile": "classical", **result}
    log = knapsack.run_archive_search(problem, initial_masks, initial_scores,
        method == "balanced_gap", historical_engine.make_rngs(seed, task_index, start_index), budget)
    from .knapsack_verifier import verify_archive_log
    verification = verify_archive_log(log)
    _require(verification.get("verification_status") == "VERIFIED" and
             verification.get("summary") == log["summary"], "Independent archive reconstruction failed")
    return {"requested_profile": method, "log": log, "verification": verification}


def verify_first_generation(unbalanced_log, balanced_log):
    """Only the two archive profiles should share the first generation."""
    _ci_only()
    _require(unbalanced_log.get("method") == "unbalanced_gap" and
             balanced_log.get("method") == "balanced_gap", "Wrong archive profile pair")
    for field in ("problem", "initial_masks", "initial_scores", "initial_archive", "rng_initial", "budget"):
        _require(unbalanced_log.get(field) == balanced_log.get(field), "Paired " + field + " differs")
    one = [row for row in unbalanced_log["candidates"] if row["generation"] == 1]
    two = [row for row in balanced_log["candidates"] if row["generation"] == 1]
    _require(one == two and len(one) == min(29, unbalanced_log["budget"]),
             "Initial zero-count archive trajectories differ")
    for field in ("population_before", "population_after", "archive_before", "archive_after",
                  "working_counts", "rng_before", "rng_after", "complete"):
        _require(unbalanced_log["generations"][0][field] == balanced_log["generations"][0][field],
                 "Paired first generation " + field + " differs")
    digest = hashlib.sha256(json.dumps(one, sort_keys=True, separators=(",", ":"),
                                      allow_nan=False).encode("utf-8")).hexdigest()
    return {"status": "VERIFIED", "first_generation_calls": len(one),
            "first_generation_sha256": digest,
            "classical_first_generation_equality_required": False}


def _describe_verified(log):
    """Post-search summaries; the record and population mean stay distinct."""
    masks = list(log["initial_masks"]) + [row["mask"] for row in log["candidates"]]
    profits = [row["profit"] for row in log["initial_scores"]] + [row["profit"] for row in log["candidates"]]
    feasible = [row["feasible"] for row in log["initial_scores"]] + [row["feasible"] for row in log["candidates"]]
    references = log["summary"]["final_population"]
    population = [masks[index] for index in references]
    feasible_values = [profits[index] for index in references if feasible[index]]
    n, mu = log["problem"]["n"], len(population)
    pair_distance = 0
    for position in range(n):
        count = sum(mask[position] == "1" for mask in population)
        pair_distance += count * (mu - count)
    parent_uses = Counter()
    generations = {row["generation"]: row for row in log["generations"]}
    for row in log["candidates"]:
        if "parent_masks" in row:
            parents = row["parent_masks"]
        else:
            before = generations[row["generation"]]["population_before"]
            parents = [masks[before[index]] for index in row["parent_indices"]]
        parent_uses.update(parents)
    total_parent_uses = sum(parent_uses.values())
    summary = log["summary"]
    return {"new_search_evaluations": summary["new_calls"],
            "best_feasible_profit": summary["best_profit"], "best_mask": summary["best_mask"],
            "best_call": summary["best_call"],
            "duplicate_candidates": summary["duplicate_calls"],
            "infeasible_candidates": summary["infeasible_calls"],
            "full_generations": summary["full_generations"],
            "terminal_prefix_children": summary["partial_children"],
            "final_population_feasible_count": len(feasible_values),
            "final_population_feasible_mean": sum(feasible_values) / len(feasible_values)
                if feasible_values else None,
            "final_population_unique_masks": len(set(population)),
            "final_population_normalized_hamming": 2 * pair_distance / (n * mu * (mu - 1)),
            "final_archive_size": summary.get("archive_size"),
            "unique_parent_masks_used": len(parent_uses),
            "largest_parent_use_share": max(parent_uses.values()) / total_parent_uses,
            "parent_uses_counted_even_for_same_mask": total_parent_uses,
            "record_is_not_population_mean": True}


def run_comparison(problem, initial_masks, initial_scores, seed, task_index,
                   start_index, budget=5000):
    """Equal-budget comparison. The outer scientific-execution gate stays closed."""
    _ci_only()
    profiles = {method: run_profile(problem, initial_masks, initial_scores, method,
                                    seed, task_index, start_index, budget) for method in PROFILES}
    paired = verify_first_generation(profiles["unbalanced_gap"]["log"],
                                     profiles["balanced_gap"]["log"])
    return {"schema": "bntga-knapsack-comparison-v1", "profiles": profiles,
            "archive_first_generation_pairing": paired,
            "descriptive": {method: _describe_verified(result["log"])
                            for method, result in profiles.items()},
            "accounting": {"physical_search_runs": 3,
                           "physical_new_search_evaluations": 3 * budget,
                           "initial_score_validation_evaluations": 90,
                           "independent_score_checks": 3 * (budget + 30)},
            "primary_mechanism_contrast": "balanced_gap versus unbalanced_gap",
            "classical_comparison_includes_archive_construction_change": True}


def teaching_knapsack_comparison():
    """A tiny declared instructional fixture, never a KPLIB result."""
    problem = {"n": 3, "weights": [6, 5, 5], "profits": [10, 8, 8], "capacity": 10}
    masks = ["100"] * 30
    scores = [{"weight": 6, "profit": 10, "feasible": True} for _ in masks]
    result = run_comparison(problem, masks, scores, 17, 0, 0, budget=61)
    return {"scope": "three_item_instructional_fixture_not_KPLIB_or_performance_evidence",
            "seed": 17, "new_queries_per_profile": 61,
            "known_start": "100", "initial_profit": 10,
            "independent_global_witness": {"mask": "011", "weight": 10, "profit": 16},
            "comparison": result,
            "interpretation_uk": "Навчальна перевірка трьох реалізацій на малій задачі; один seed і 61 запит не доводять переваги на KPLIB."}
