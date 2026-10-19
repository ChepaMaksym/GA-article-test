"""Performance-equivalent archive executor with one validated plan per block.

Only structural validation is reused. Fitness queries are never cached.
Historical operators, evaluation helpers, raw-log schema and independent
verifiers remain unchanged. The caller saves the raw log before verification.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
import os

from studies.adaptive_parameters.mutation_only.engine import make_rngs
from studies.knapsack_parameters.bntga_selection import knapsack as historical
from studies.knapsack_parameters.bntga_selection import operator as legacy_operator


SCHEMA = historical.SCHEMA
METHODS = ("unbalanced_gap", "balanced_gap")


def _require(condition, message):
    if not condition:
        raise ValueError(message)


def _ci_only():
    _require(os.environ.get("GITHUB_ACTIONS") == "true" and
             os.environ.get("GITHUB_REPOSITORY") == "ChepaMaksym/GA-article-test" and
             os.environ.get("GITHUB_REF") == "refs/heads/research/masters-ga-diversity-crossover",
             "Execution requires the registered repository and branch in GitHub Actions")


@dataclass(frozen=True, slots=True)
class _CompiledSelection:
    # Every descendant of this object is immutable. No caller-owned archive or
    # journal dictionary is retained, so changing a logged plan cannot change
    # later selections within this block.
    entries: tuple
    dimension: int | None
    balanced: bool
    gaps: tuple
    priorities: tuple

    def journal_plan(self):
        return {
            "schema": legacy_operator.PLAN_SCHEMA,
            "archive": [{"id": identity, "objectives": list(objectives), "selected": count}
                        for identity, objectives, count in self.entries],
            "dimension": self.dimension, "balanced": self.balanced,
            "gaps": list(self.gaps), "priorities": list(self.priorities),
        }


def compile_selection(archive, dimension, balanced=True):
    """Validate with the unchanged operator exactly once for this generation."""
    plan = legacy_operator.freeze_selection(archive, dimension, balanced)
    return _CompiledSelection(
        entries=tuple((point["id"], tuple(point["objectives"]), point["selected"])
                      for point in plan["archive"]),
        dimension=plan["dimension"], balanced=plan["balanced"],
        gaps=tuple(plan["gaps"]), priorities=tuple(plan["priorities"]),
    )


def select_prevalidated_pair(session, current_counts, tournament_draws, neighbor_side=None):
    """Emit the legacy event without rechecking pairwise archive dominance.

    Counter identity/types and explicit draws are still checked on each call.
    Copying the full before/after counters remains O(A), as required by the
    unchanged evidence format. Priorities never use the current counters.
    """
    _require(type(session) is _CompiledSelection, "A compiled immutable selection plan is required")
    identities = {entry[0] for entry in session.entries}
    _require(isinstance(current_counts, dict) and set(current_counts) == identities,
             "current_counts must contain exactly the frozen archive ids")
    counts = {}
    for identity, _objectives, snapshot in session.entries:
        value = current_counts[identity]
        _require(type(value) is int and value >= snapshot, "Invalid or decreased selection counter")
        counts[identity] = value
    _require(isinstance(tournament_draws, list), "tournament_draws must be a list")
    size = len(session.entries)
    singleton = size == 1
    if singleton:
        _require(not tournament_draws and neighbor_side is None,
                 "Singleton selection consumes no tournament or neighbor draw")
        first = second = 0
        priority = None
    else:
        _require(bool(tournament_draws), "Tournament must contain at least one draw")
        _require(all(type(index) is int and 0 <= index < size for index in tournament_draws),
                 "Tournament draw must index the sorted archive")
        first = tournament_draws[0]
        for drawn in tournament_draws[1:]:
            if session.priorities[drawn] > session.priorities[first]:
                first = drawn
        if first in (0, size - 1):
            _require(neighbor_side is None, "Boundary selection consumes no neighbor draw")
            second = 1 if first == 0 else first - 1
        else:
            _require(type(neighbor_side) is int and neighbor_side in (0, 1),
                     "Interior neighbor must be 0 (next) or 1 (previous)")
            second = first + 1 if neighbor_side == 0 else first - 1
        priority = session.priorities[first]
    after = dict(counts)
    if not singleton:
        after[session.entries[first][0]] += 1
        after[session.entries[second][0]] += 1
    return {
        "schema": legacy_operator.EVENT_SCHEMA,
        "tournament_draws": list(tournament_draws), "neighbor_side": neighbor_side,
        "first_index": first, "second_index": second,
        "first_id": session.entries[first][0], "second_id": session.entries[second][0],
        "first_priority": priority, "counts_before": dict(counts),
        "counts_after": after, "singleton": singleton,
    }


def _pair(session, counts, selection_rng):
    size = len(session.entries)
    if size == 1:
        return select_prevalidated_pair(session, counts, [], None)
    draws = [int(selection_rng.integers(size)) for _ in range(2)]
    winner = draws[0]
    if session.priorities[draws[1]] > session.priorities[winner]:
        winner = draws[1]
    side = int(selection_rng.integers(2)) if 0 < winner < size - 1 else None
    return select_prevalidated_pair(session, counts, draws, side)


def run_archive_search(problem, initial_masks, initial_scores, balanced, rngs, budget=5000):
    """Return the exact historical scientific journal, without verifying it.

    The only execution difference is compile_selection once per generation in
    place of validating the same frozen plan before every pair. No oracle,
    checkpoint, file path or independent-verifier callback enters the kernel.
    """
    _ci_only()
    historical._problem(problem)
    historical._integer(budget, "budget", 1)
    _require(type(balanced) is bool, "balanced must be bool")
    _require(isinstance(initial_masks, list) and isinstance(initial_scores, list) and
             len(initial_masks) == len(initial_scores) == historical.MU,
             "Exactly 30 known initial masks and scores are required")
    historical._rngs(rngs)
    n, capacity = problem["n"], problem["capacity"]
    masks, scores = list(initial_masks), []
    known_by_mask = {}
    for mask, known in zip(masks, initial_scores):
        historical._mask(mask, n)
        historical._known_score(known)
        actual = historical._score(problem, mask)
        _require(actual == known, "Known initial score disagrees with the exact mask")
        scores.append(actual)
        known_by_mask[mask] = deepcopy(actual)
    _require(any(score["feasible"] for score in scores),
             "At least one feasible initial mask is required; no hidden restart is allowed")
    archive = legacy_operator.update_archive([
        historical._point(problem, mask, score)
        for mask, score in zip(masks, scores) if score["feasible"]
    ])
    canonical_problem = {"n": n, "weights": list(problem["weights"]),
                         "profits": list(problem["profits"]), "capacity": capacity}
    method = "balanced_gap" if balanced else "unbalanced_gap"
    log = {
        "schema": SCHEMA, "method": method, "problem": canonical_problem,
        "initial_masks": list(masks), "initial_scores": deepcopy(scores),
        "initial_archive": deepcopy(archive), "rng_initial": historical._states(rngs),
        "budget": budget, "candidates": [], "generations": [],
        "summary": None, "rng_final": None,
    }
    population = list(range(historical.MU))
    seen = set(masks)
    best_mask = best_profit = best_call = None
    for mask, score in zip(masks, scores):
        if score["feasible"] and (best_profit is None or score["profit"] > best_profit):
            best_mask, best_profit, best_call = mask, score["profit"], 0
    calls = full_generations = partial_children = duplicate_calls = infeasible_calls = 0
    probability = 1 / n
    while calls < budget:
        generation = len(log["generations"]) + 1
        before = list(population)
        archive_before = deepcopy(archive)
        rng_before = historical._states(rngs)
        record_before = best_profit
        keys = [historical._quality(scores[reference], capacity) for reference in before]
        best_key = max(keys)
        elite_ties = [index for index, key in enumerate(keys) if key == best_key]
        elite_index = (elite_ties[0] if len(elite_ties) == 1
                       else elite_ties[int(rngs["ties"].integers(len(elite_ties)))])
        elite_reference = before[elite_index]
        dimension = int(rngs["selection"].integers(2)) if len(archive) > 1 else None
        session = compile_selection(archive, dimension, balanced)
        plan = session.journal_plan()
        working_counts = {point["id"]: point["selected"] for point in archive}
        child_references = []
        start_call = calls + 1
        for _ in range(min(historical.MU - 1, budget - calls)):
            event = _pair(session, working_counts, rngs["selection"])
            working_counts = dict(event["counts_after"])
            first, second = event["first_id"], event["second_id"]
            parent_scores = [deepcopy(known_by_mask[first]), deepcopy(known_by_mask[second])]
            crosses = bool(rngs["branch"].random() < historical.PC)
            if crosses:
                choices = rngs["crossover"].random(n) < 0.5
                pre = "".join(first[index] if choices[index] else second[index] for index in range(n))
            else:
                pre = first
            mutation_bits = [index for index, changed in
                             enumerate(rngs["mutation"].random(n) < probability) if changed]
            bits = list(pre)
            for index in mutation_bits:
                bits[index] = "0" if bits[index] == "1" else "1"
            mask = "".join(bits)
            # The immutable plan is reused; every candidate is still evaluated.
            score = historical._score(problem, mask)
            calls += 1
            duplicate = mask in seen
            duplicate_calls += int(duplicate)
            infeasible_calls += int(not score["feasible"])
            seen.add(mask)
            if score["feasible"] and score["profit"] > best_profit:
                best_mask, best_profit, best_call = mask, score["profit"], calls
            reference = len(masks)
            masks.append(mask)
            scores.append(score)
            known_by_mask[mask] = deepcopy(score)
            child_references.append(reference)
            log["candidates"].append({
                "call": calls, "generation": generation,
                "parent_indices": [event["first_index"], event["second_index"]],
                "parent_masks": [first, second], "parent_scores": parent_scores,
                "selection_event": event, "crossover": crosses,
                "pre_mask": pre, "mutation_bits": mutation_bits, "mask": mask,
                **score, "duplicate": duplicate,
                "record_profit": best_profit, "record_call": best_call,
            })
        complete = len(child_references) == historical.MU - 1
        after_selection = deepcopy(archive_before)
        for point in after_selection:
            point["selected"] = working_counts[point["id"]]
        if complete:
            population = [elite_reference] + child_references
            archive = legacy_operator.update_archive([
                historical._point(problem, masks[reference], scores[reference])
                for reference in child_references if scores[reference]["feasible"]
            ], existing=after_selection)
            full_generations += 1
        else:
            partial_children = len(child_references)
        log["generations"].append({
            "generation": generation, "start_call": start_call, "end_call": calls,
            "complete": complete, "population_before": before,
            "elite_index": elite_index, "elite_reference": elite_reference,
            "p_m": probability, "p_c": historical.PC,
            "record_before": record_before, "record_after": best_profit,
            "archive_before": archive_before, "plan": plan,
            "working_counts": dict(working_counts), "archive_after_selection": after_selection,
            "archive_after": deepcopy(archive), "population_after": list(population),
            "rng_before": rng_before, "rng_after": historical._states(rngs),
        })
    log["summary"] = {
        "new_calls": calls, "physical_evaluations": calls,
        "known_score_validation_evaluations": historical.MU,
        "duplicate_calls": duplicate_calls, "infeasible_calls": infeasible_calls,
        "full_generations": full_generations, "partial_children": partial_children,
        "best_mask": best_mask, "best_profit": best_profit, "best_call": best_call,
        "final_population": list(population), "final_archive": deepcopy(archive),
        "archive_size": len(archive), "final_mutation_probability": probability,
    }
    log["rng_final"] = historical._states(rngs)
    return log


def run(problem, initial_population, method, seed, task_index, start_index, budget=5000):
    """Convenience seed adapter; raw executor remains available for RNG fixtures."""
    _ci_only()
    _require(method in METHODS, "Only the two registered archive profiles are accepted")
    _require(type(initial_population) is dict and
             set(initial_population) == {"initial_masks", "initial_scores"},
             "Initial population accepts only initial_masks and initial_scores")
    return run_archive_search(
        problem, initial_population["initial_masks"], initial_population["initial_scores"],
        method == "balanced_gap", make_rngs(seed, task_index, start_index), budget,
    )
