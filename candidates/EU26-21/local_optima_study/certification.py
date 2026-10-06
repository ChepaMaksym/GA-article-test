"""Deterministic diagnostic preparation outside every search-call ledger.

All N1 neighbors are audited. A higher-WBA N2 witness proves only that the
audited center is not globally optimal for this fixed empirical objective.
Failing to find that witness never proves global optimality.
"""
from __future__ import annotations

from itertools import combinations
from typing import Any, Callable, Sequence

from hybrid_1.core import Fitness, Mask, mutate_exact
from local_optima_study.search import _integer, validate_fitness, validate_mask


def prepare_case(
    objective: Callable[[Mask], Any],
    start_mask: Sequence[int],
    expected_fitness: Any,
    *,
    max_passes: int = 20,
) -> dict[str, Any]:
    """Prepare and audit one center, without exposing its witness to search.

    Repeated scores must agree exactly. Bad returns, interrupted evaluation,
    nondeterminism and source-score mismatches raise rather than becoming valid
    ineligible cases. The fixed-dimensional upper bound is 1+20n+(1+n)+n(n-1)/2.
    """
    if not callable(objective):
        raise TypeError("objective must be callable")
    source_mask = validate_mask(start_mask)
    source_fitness = validate_fitness(expected_fitness)
    max_passes = _integer(max_passes, "max_passes", minimum=1)
    if max_passes > 20:
        raise ValueError("at most twenty complete ascent passes are allowed")
    dimension = len(source_mask)
    maximum_calls = 1 + max_passes * dimension + 1 + dimension + dimension * (dimension - 1) // 2
    records: list[dict[str, Any]] = []
    observed: dict[Mask, Fitness] = {source_mask: source_fitness}

    def evaluate(mask: Mask, phase: str, *, changed_bits: Sequence[int] = (), one_bit_pass: int | None = None) -> Fitness:
        if len(records) >= maximum_calls:
            raise RuntimeError("diagnostic-call upper bound exhausted")
        score = validate_fitness(objective(mask))
        previous = observed.get(mask)
        if previous is not None and previous != score:
            raise ValueError("deterministic objective did not reproduce a previously observed mask score")
        observed[mask] = score
        records.append({
            "call": len(records) + 1, "phase": phase, "one_bit_pass": one_bit_pass,
            "mask": list(mask), "fitness": list(score),
            "validation_weighted_balanced_accuracy": score[0],
            "negative_selected_feature_fraction": score[1],
            "selected_feature_count": sum(mask), "changed_bits": list(changed_bits),
        })
        return score

    center, center_score = source_mask, evaluate(source_mask, "source_center_recheck")
    ascent: list[dict[str, Any]] = []
    converged_in_ascent = False
    for pass_number in range(1, max_passes + 1):
        before_mask, before_score = center, center_score
        calls_before = len(records)
        candidates = []
        for bit in range(dimension):
            neighbor = mutate_exact(center, [bit])
            score = evaluate(neighbor, "ascent_one_bit", changed_bits=[bit], one_bit_pass=pass_number)
            candidates.append((score, bit, neighbor))
        # Ordered enumeration plus max-by-fitness keeps the smallest bit index
        # in a complete-fitness tie; no neutral full-fitness walk is made.
        best_score, best_bit, best_mask = max(candidates, key=lambda item: item[0])
        moved = best_score > center_score
        if moved:
            center, center_score = best_mask, best_score
        ascent.append({
            "pass": pass_number, "calls_before": calls_before, "calls_after": len(records),
            "center_before": list(before_mask), "fitness_before": list(before_score),
            "best_neighbor_bit": best_bit, "best_neighbor_mask": list(best_mask),
            "best_neighbor_fitness": list(best_score), "moved": moved,
            "center_after": list(center), "fitness_after": list(center_score),
        })
        if not moved:
            converged_in_ascent = True
            break

    cap_hit = len(ascent) == max_passes and not converged_in_ascent
    audit_start = len(records)
    audit_center_score = evaluate(center, "audit_center_recheck")
    if audit_center_score != center_score:
        raise ValueError("independent audit did not reproduce final-center fitness")
    neighbors: list[dict[str, Any]] = []
    for bit in range(dimension):
        neighbor = mutate_exact(center, [bit])
        score = evaluate(neighbor, "audit_one_bit", changed_bits=[bit])
        neighbors.append({
            "bit": bit, "mask": list(neighbor), "fitness": list(score), "call": len(records),
        })
    neighbor_scores = [tuple(row["fitness"]) for row in neighbors]
    lex_local = all(score <= center_score for score in neighbor_scores)
    wba_local = all(score[0] <= center_score[0] for score in neighbor_scores)
    equal_wba = [row["bit"] for row in neighbors if row["fitness"][0] == center_score[0]]
    equal_full = [row["bit"] for row in neighbors if tuple(row["fitness"]) == center_score]
    certificate = {
        "complete": len(neighbors) == dimension and len(records) - audit_start == dimension + 1,
        "audit_calls_before": audit_start, "audit_calls_after": len(records),
        "center_recheck_fitness": list(audit_center_score), "neighbors": neighbors,
        "lexicographic_local_maximum": lex_local, "wba_local_maximum": wba_local,
        "strict_wba_local_maximum": all(score[0] < center_score[0] for score in neighbor_scores),
        "strict_lexicographic_local_maximum": all(score < center_score for score in neighbor_scores),
        "equal_wba_neighbors": equal_wba, "equal_full_fitness_neighbors": equal_full,
        "wba_plateau": bool(equal_wba), "lexicographic_plateau": bool(equal_full),
    }
    witness = None
    witness_calls = 0
    if lex_local and wba_local and certificate["complete"]:
        for first_bit, second_bit in combinations(range(dimension), 2):
            neighbor = mutate_exact(center, [first_bit, second_bit])
            score = evaluate(neighbor, "two_bit_witness", changed_bits=[first_bit, second_bit])
            witness_calls += 1
            if score[0] > center_score[0]:
                witness = {
                    "mask": list(neighbor), "fitness": list(score),
                    "changed_bits": [first_bit, second_bit], "call": len(records),
                }
                break
    eligible = bool(certificate["complete"] and lex_local and wba_local and witness is not None)
    status = (
        "eligible" if eligible else
        "ineligible_final_one_bit_not_local" if not (lex_local and wba_local) else
        "ineligible_no_two_bit_witness"
    )
    return {
        "schema": "eu26-21-local-optima-preparation-v1",
        "eligible": eligible, "status": status,
        "dimension": dimension, "source_mask": list(source_mask), "source_fitness": list(source_fitness),
        "center_mask": list(center), "center_fitness": list(center_score),
        "one_bit_passes": len(ascent), "pass_cap_hit": cap_hit,
        "ascent_trace": ascent, "certificate": certificate,
        "witness": witness, "witness_calls": witness_calls,
        "diagnostic_calls": len(records), "diagnostic_call_upper_bound": maximum_calls,
        "evaluations": records,
    }
