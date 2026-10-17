"""Three labelled mutation profiles over unchanged historical search kernels.

The SD-labelled profile is a bounded equivalence view of the verified fixed
path, not a newly sampled third run.  Active SD search is deliberately absent.
New KPLIB searches require a later scientific release by the outer authority.
"""
from __future__ import annotations

import hashlib
import json
import math
import os

from studies.adaptive_parameters.mutation_only import verifier as historical
from studies.knapsack_parameters.mutation_population import search as old_search

from . import controller


SCHEMA = "knapsack-mutation-rules-derived-sd-v1"
PROFILES = ("fixed", "own_adaptive_mutation", "paper_sd_mutation")


def _require(condition, message):
    if not condition:
        raise ValueError("Invalid mutation-rule comparison: " + message)


def _ci_only():
    _require(os.environ.get("GITHUB_ACTIONS") == "true", "CI only")
    _require(os.environ.get("GITHUB_REPOSITORY") == "ChepaMaksym/GA-article-test",
             "wrong repository")
    _require(os.environ.get("GITHUB_REF") ==
             "refs/heads/research/masters-ga-diversity-crossover", "wrong branch")


def source_journal_sha256(log):
    """Hash canonical UTF-8 JSON, without modifying the source journal."""
    raw = json.dumps(log, sort_keys=True, ensure_ascii=False,
                     separators=(",", ":"), allow_nan=False).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _domain(log):
    _require(type(log) is dict and log.get("method") == "fixed",
             "the shared source must be an unchanged fixed journal")
    _require(type(log.get("problem")) is dict and
             type(log["problem"].get("n")) is int and log["problem"]["n"] == 100,
             "only n=100 is admitted")
    budget = log.get("budget")
    _require(type(budget) is int and 1 <= budget <= 5000,
             "derived execution is restricted to budget 1..5000")
    bound = controller.threshold(100, 1, R=100 ** 3)
    _require(type(bound) in (int, float) and math.isfinite(bound) and bound > budget,
             "inactive-radius proof fails; an active controller cannot use fixed search")
    return budget, bound


def derive_sd_view(fixed_log):
    """Derive an independently verifiable SD view with zero extra search calls.

    The source keeps its historical method and schema.  Its operators and RNG
    consumption are replayed before reading any fitness signals for the view.
    The sufficient inactivity bound is checked before replay or derivation.
    """
    _ci_only()
    budget, bound = _domain(fixed_log)
    replay = historical.verify_log(fixed_log)
    _require(replay["verification_status"] == "VERIFIED", "unverified fixed source")
    state = controller.initial_state(100)
    trace = []
    for event in fixed_log["generations"]:
        before, after = event["record_before"], event["record_after"]
        success = after is not None and (before is None or after > before)
        children = event["end_call"] - event["start_call"] + 1
        transition = controller.transition(100, state, children, success,
                                           complete=event["complete"], R=100 ** 3)
        _require(transition["before"]["r"] == transition["after"]["r"] == 1,
                 "active SD cannot be represented by a fixed journal")
        _require(transition["p_before"] == event["p_m"], "shared mutation probability differs")
        trace.append({"generation": event["generation"], "start_call": event["start_call"],
            "end_call": event["end_call"], "complete": event["complete"],
            "children": children, "strict_success": success,
            "record_before": before, "record_after": after,
            "r_before": int(transition["before"]["r"]),
            "u_before": transition["before"]["u"], "p_m": transition["p_before"],
            "threshold": transition["threshold"],
            "r_after": int(transition["after"]["r"]),
            "u_after": transition["after"]["u"], "p_m_next": transition["p_after"],
            "event": transition["event"]})
        state = transition["after"]
    return {"schema": SCHEMA, "requested_profile": "paper_sd_mutation",
        "backend_profile": "fixed", "status": "BOUNDED_EQUIVALENCE",
        "source_journal_sha256": source_journal_sha256(fixed_log),
        "domain": {"n": 100, "population_size": 30, "crossover_probability": 0.9,
                   "budget": budget, "r_initial": 1, "u_initial": 0, "R": 100 ** 3},
        "proof": {"threshold_r1": bound, "budget_strictly_below_threshold": True,
                  "radius_inactive": True,
                  "equivalence_kind": "REGISTERED_BOUNDED_OPERATOR_PATH"},
        "controller_trace": trace,
        "accounting": {"logical_profile_search_evaluations": budget,
                       "additional_physical_search_evaluations": 0,
                       "shared_source_physical_search_evaluations": budget,
                       "new_independent_search_runs": 0},
        "construction_verification": {
            "source_operator_replay_score_checks": replay["independent_score_checks"],
            "controller_events": len(trace)}}


def run_comparison(problem, initial_masks, initial_scores, seed, task_index,
                   start_index, budget=5000):
    """CI test-fixture adapter; scientific release is an outer-driver duty.

    It physically executes only fixed and the unchanged own heuristic.  The
    source controller is represented as a separately labelled equivalent view.
    The function accepts only oracle-free historical problem/initial interfaces.
    """
    _ci_only()
    _require(type(problem) is dict and type(problem.get("n")) is int and
             problem["n"] == 100, "only n=100 is admitted")
    _require(type(budget) is int and 1 <= budget <= 5000, "budget outside bounded domain")
    _require(controller.threshold(100, 1, R=100 ** 3) > budget,
             "inactive-radius proof fails before execution")
    fixed = old_search.run_profile(problem, initial_masks, initial_scores, "fixed",
                                   seed, task_index, start_index, budget)
    own = old_search.run_profile(problem, initial_masks, initial_scores, "adaptive_mutation",
                                 seed, task_index, start_index, budget)
    pair = old_search.verify_paired_first_generation(fixed["log"], own["log"])
    derived = derive_sd_view(fixed["log"])
    from .verifier import verify_sd_view
    independent = verify_sd_view(fixed["log"], derived)
    return {"schema": "knapsack-mutation-rules-comparison-v1", "profiles": {
        "fixed": fixed, "own_adaptive_mutation": own,
        "paper_sd_mutation": {"view": derived, "verification": independent}},
        "paired_first_generation": pair,
        "accounting": {"physical_search_runs": 2,
                       "physical_search_evaluations": 2 * budget,
                       "logical_profiles": 3,
                       "logical_profile_search_evaluations": 3 * budget,
                       "derived_additional_physical_search_evaluations": 0,
                       "initial_score_validation_evaluations": 60,
                       "operator_replay_score_checks": 4 * (budget + 30),
                       "independent_sd_controller_events": len(derived["controller_trace"])}}
