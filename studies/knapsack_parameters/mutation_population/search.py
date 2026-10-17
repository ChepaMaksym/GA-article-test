"""Thin, CI-only adapter over the unchanged registered mutation-only kernel.

The adapter deliberately has no oracle parameter and no population controller.
Its independent verifier belongs to the historical implementation, not to the
search kernel.  Scientific authorization is enforced by the outer phase driver.
"""
from __future__ import annotations

import hashlib
import json
import os

from studies.adaptive_parameters.mutation_only import engine, verifier


PROFILES = ("fixed", "adaptive_mutation")
ADAPTIVE_POPULATION_IMPLEMENTED = False


def _require(condition, message):
    if not condition:
        raise ValueError(message)


def _ci_only():
    _require(os.environ.get("GITHUB_ACTIONS") == "true", "Execution is CI-only")
    _require(os.environ.get("GITHUB_REPOSITORY") == "ChepaMaksym/GA-article-test",
             "Wrong repository")
    _require(os.environ.get("GITHUB_REF") ==
             "refs/heads/research/masters-ga-diversity-crossover", "Wrong branch")


def run_profile(problem, initial_masks, initial_scores, method, seed, task_index,
                start_index, budget=5000):
    """Run one admitted profile and independently replay its complete journal.

    Small budgets are supported for CI fixtures.  The execution-phase contract
    separately requires exactly 5000 new calls for a scientific run.  An
    unsupported profile fails before creating RNGs or evaluating a candidate.
    """
    _ci_only()
    _require(method in PROFILES,
             "Profile is not admitted; adaptive_population has no controller")
    log = engine.run_search(problem, initial_masks, initial_scores, method,
                            engine.make_rngs(seed, task_index, start_index), budget)
    verification = verifier.verify_log(log)
    _require(verification.get("verification_status") == "VERIFIED",
             "Independent journal reconstruction failed")
    _require(verification["summary"] == log["summary"], "Reconstructed summary differs")
    return {"log": log, "verification": verification}


def verify_paired_first_generation(fixed_log, adaptive_log):
    """Check paired starts and operators, not the deliberately different feedback.

    The next controller event may differ already after generation one, even
    when the offspring, selected parents and all consumed random values match.
    """
    _ci_only()
    _require(fixed_log.get("method") == "fixed" and
             adaptive_log.get("method") == "adaptive_mutation", "Wrong profile pair")
    for name in ("problem", "initial_masks", "initial_scores", "rng_initial", "budget"):
        _require(fixed_log.get(name) == adaptive_log.get(name), "Paired " + name + " differs")
    _require(fixed_log.get("generations") and adaptive_log.get("generations"),
             "Missing first generation")
    first = [row for row in fixed_log["candidates"] if row["generation"] == 1]
    second = [row for row in adaptive_log["candidates"] if row["generation"] == 1]
    _require(first == second and len(first) == min(29, fixed_log["budget"]),
             "Paired first-generation candidates differ")
    for field in ("generation", "start_call", "end_call", "complete", "population_before",
                  "elite_index", "p_m", "stagnation_before", "record_before", "record_after",
                  "population_after", "rng_before", "rng_after"):
        _require(field in fixed_log["generations"][0] and
                 field in adaptive_log["generations"][0] and
                 fixed_log["generations"][0].get(field) ==
                 adaptive_log["generations"][0].get(field), "Paired first " + field + " differs")
    digest = hashlib.sha256(json.dumps(first, sort_keys=True, separators=(",", ":"),
                                      allow_nan=False).encode("utf-8")).hexdigest()
    return {"status": "VERIFIED", "first_generation_calls": len(first),
            "first_generation_sha256": digest,
            "same_initial_rng_states": True, "population_size": 30,
            "crossover_probability": 0.9}
