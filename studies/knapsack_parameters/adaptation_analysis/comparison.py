"""Five matched profiles, one physical classical control, no lambda substitute."""
from __future__ import annotations

import os

from studies.adaptive_parameters.mutation_only import engine as historical_engine
from studies.adaptive_parameters.mutation_only import verifier as mutation_verifier
from studies.knapsack_parameters.mutation_population import search as mutation_search
from studies.knapsack_parameters.bntga_selection import knapsack_comparison as archive_search
from studies.knapsack_parameters.bntga_selection.knapsack_verifier import verify_archive_log

ACTIVE_PROFILES = ("classical", "adaptive_mutation", "adaptive_crossover",
                   "unbalanced_gap", "balanced_gap")
DEFERRED_PROFILES = ("lambda_fixed", "lambda_own")


def require(condition, message):
    if not condition:
        raise ValueError(message)


def ci_only():
    require(os.environ.get("GITHUB_ACTIONS") == "true" and
            os.environ.get("GITHUB_REPOSITORY") == "ChepaMaksym/GA-article-test" and
            os.environ.get("GITHUB_REF") == "refs/heads/research/masters-ga-diversity-crossover",
            "Execution is restricted to the registered repository/branch in GitHub Actions")


def lambda_status():
    return {"status": "BLOCKED_LAMBDA_REPLICATION", "implemented": False,
            "search_runs": None, "advantage": None,
            "reason": "Full numerical article replication and separate resource approval required"}


def verify_profile_log(method, log):
    ci_only()
    if method in DEFERRED_PROFILES:
        raise ValueError("BLOCKED_LAMBDA_REPLICATION")
    require(method in ACTIVE_PROFILES and type(log) is dict, "Unknown comparison profile or log")
    expected = {"classical": "fixed", "adaptive_mutation": "adaptive_mutation",
                "adaptive_crossover": "adaptive_crossover", "unbalanced_gap": "unbalanced_gap",
                "balanced_gap": "balanced_gap"}[method]
    require(log.get("method") == expected, "Method/log identity mismatch")
    if method in ("classical", "adaptive_mutation"):
        result = mutation_verifier.verify_log(log)
    elif method == "adaptive_crossover":
        from .crossover_verifier import verify_log
        result = verify_log(log)
    else:
        result = verify_archive_log(log)
    require(result.get("verification_status") == "VERIFIED" and
            result.get("summary") == log.get("summary"), "Independent reconstruction failed")
    return result


def run_profile(problem, initial_masks, initial_scores, method, seed, task_index,
                start_index, budget=5000):
    ci_only()
    if method in DEFERRED_PROFILES:
        raise ValueError("BLOCKED_LAMBDA_REPLICATION")
    require(method in ACTIVE_PROFILES, "Unknown adaptation profile")
    # All methods share the archive module's explicit input/resource domain.
    from studies.knapsack_parameters.bntga_selection.knapsack import _problem
    _problem(problem)
    require(type(budget) is int and budget > 0, "Positive integer budget required")
    require(isinstance(initial_scores, list) and len(initial_scores) == 30 and
            any(type(row) is dict and row.get("feasible") is True for row in initial_scores),
            "Exactly 30 known scores, including a feasible mask, required")
    if method in ("classical", "unbalanced_gap", "balanced_gap"):
        result = archive_search.run_profile(problem, initial_masks, initial_scores, method,
                                            seed, task_index, start_index, budget)
    elif method == "adaptive_mutation":
        result = mutation_search.run_profile(problem, initial_masks, initial_scores,
                                             method, seed, task_index, start_index, budget)
    else:
        from .crossover import run_search
        log = run_search(problem, initial_masks, initial_scores, method,
                         historical_engine.make_rngs(seed, task_index, start_index), budget)
        result = {"log": log, "verification": verify_profile_log(method, log)}
    return {**result, "requested_profile": method}


def verify_crossover_first_generation(classical, adaptive):
    ci_only()
    require(classical.get("method") == "fixed" and adaptive.get("method") == "adaptive_crossover",
            "Wrong crossover comparison pair")
    for name in ("problem", "initial_masks", "initial_scores", "rng_initial", "budget"):
        require(classical.get(name) == adaptive.get(name), "Paired " + name + " differs")
    old = [row for row in classical["candidates"] if row["generation"] == 1]
    new = [{key: value for key, value in row.items() if key != "parent_distance"}
           for row in adaptive["candidates"] if row["generation"] == 1]
    require(old == new and len(old) == min(29, classical["budget"]), "Crossover first generation differs")
    for name in ("population_before", "population_after", "elite_index", "record_before",
                 "record_after", "rng_before", "rng_after", "complete", "p_m"):
        require(classical["generations"][0][name] == adaptive["generations"][0][name],
                "First generation " + name + " differs")
    require(adaptive["generations"][0]["p_c"] == 0.9, "First generation must use p_c=0.9")
    return {"status": "VERIFIED", "first_generation_calls": len(old)}


def run_comparison(problem, initial_masks, initial_scores, seed, task_index,
                   start_index, budget=5000):
    ci_only()
    profiles = {method: run_profile(problem, initial_masks, initial_scores, method,
                                     seed, task_index, start_index, budget)
                for method in ACTIVE_PROFILES}
    fixed = profiles["classical"]["log"]
    mutation_pair = mutation_search.verify_paired_first_generation(
        fixed, profiles["adaptive_mutation"]["log"])
    crossover_pair = verify_crossover_first_generation(fixed, profiles["adaptive_crossover"]["log"])
    archive_pair = archive_search.verify_first_generation(
        profiles["unbalanced_gap"]["log"], profiles["balanced_gap"]["log"])
    return {"schema": "ga-adaptation-comparison-v1", "profiles": profiles,
            "pairing": {"mutation": mutation_pair, "crossover": crossover_pair, "archive": archive_pair},
            "lambda": lambda_status(),
            "accounting": {"physical_search_runs": 5, "classical_control_runs": 1,
                           "new_search_evaluations": 5 * budget,
                           "known_score_validation_evaluations": 150,
                           "independent_score_checks": 5 * (budget + 30)}}
