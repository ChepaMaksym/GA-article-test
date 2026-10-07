"""Deterministic ratio-greedy preparation and complete radius-two ascent.

The subsequent certificate must independently rebuild and evaluate neighbors;
neither this module's deltas nor its pass summaries are a local certificate.
No evolutionary algorithm or random population is implemented here.
"""

from __future__ import annotations

from functools import cmp_to_key

from .data_audit import Instance
from .solvers import check_deadline


def _validate_instance(instance: Instance) -> None:
    if not isinstance(instance, Instance):
        raise TypeError("instance must be the immutable audited Instance")
    if type(instance.n) is not int or instance.n <= 0:
        raise ValueError("n must be a positive integer")
    if type(instance.capacity) is not int or instance.capacity <= 0:
        raise ValueError("capacity must be a positive integer")
    if not isinstance(instance.profits, tuple) or not isinstance(instance.weights, tuple):
        raise TypeError("item arrays must be immutable tuples")
    if len(instance.profits) != instance.n or len(instance.weights) != instance.n:
        raise ValueError("item arrays must contain exactly n entries")
    if any(type(value) is not int or value <= 0 for value in instance.profits + instance.weights):
        raise ValueError("profits and weights must be positive non-boolean integers")


def greedy_start(instance: Instance, *, deadline: float | None = None) -> dict:
    """Use exact cross-products; return bits in original, never sorted, order."""
    check_deadline(deadline)
    _validate_instance(instance)

    def compare(first: int, second: int) -> int:
        left = instance.profits[first] * instance.weights[second]
        right = instance.profits[second] * instance.weights[first]
        if left != right:
            return -1 if left > right else 1
        return (first > second) - (first < second)

    order = sorted(range(instance.n), key=cmp_to_key(compare))
    bits = [0] * instance.n
    weight = 0
    profit = 0
    for original_index in order:
        check_deadline(deadline)
        if weight + instance.weights[original_index] <= instance.capacity:
            bits[original_index] = 1
            weight += instance.weights[original_index]
            profit += instance.profits[original_index]
    return {
        "mask": "".join(str(bit) for bit in bits),
        "weight": weight,
        "profit": profit,
        "item_order": order,
        "items_considered": instance.n,
        "ratio_comparison": "exact_integer_cross_products",
        "ratio_tie_break": "smaller_original_zero_based_index",
    }


def _best_neighbor(instance: Instance, bits: list[int], weight: int, profit: int,
                   deadline: float | None) -> dict:
    """Inspect every distance-one/two mask, including infeasible neighbors.

    These exact deltas are used only for ascent, never by the independent
    certificate.  Tuple comparisons implement the preregistered tie rule even
    though all one-bit moves are visited before the two-bit moves.
    """
    weight_changes = [(1 if bit == 0 else -1) * w for bit, w in zip(bits, instance.weights)]
    profit_changes = [(1 if bit == 0 else -1) * p for bit, p in zip(bits, instance.profits)]
    best_profit = profit
    best_weight = weight
    best_flips = None
    queries = 0
    feasible_count = 0
    improving_count = 0

    def consider(flips: tuple[int, ...], candidate_weight: int, candidate_profit: int) -> None:
        nonlocal best_profit, best_weight, best_flips, queries, feasible_count, improving_count
        queries += 1
        if candidate_weight > instance.capacity:
            return
        feasible_count += 1
        if candidate_profit <= profit:
            return
        improving_count += 1
        if (candidate_profit > best_profit
                or (candidate_profit == best_profit and (best_flips is None or flips < best_flips))):
            best_profit = candidate_profit
            best_weight = candidate_weight
            best_flips = flips

    for first in range(instance.n):
        check_deadline(deadline)
        consider((first,), weight + weight_changes[first], profit + profit_changes[first])
    for first in range(instance.n):
        check_deadline(deadline)
        for second in range(first + 1, instance.n):
            consider((first, second), weight + weight_changes[first] + weight_changes[second],
                     profit + profit_changes[first] + profit_changes[second])
    check_deadline(deadline)
    expected_queries = instance.n + instance.n * (instance.n - 1) // 2
    if queries != expected_queries:
        raise ArithmeticError("ascent did not inspect the complete radius-two neighborhood")
    return {
        "flipped_indices": best_flips,
        "weight": best_weight,
        "profit": best_profit,
        "neighbor_queries": queries,
        "feasible_neighbors": feasible_count,
        "infeasible_neighbors": queries - feasible_count,
        "strictly_improving_neighbors": improving_count,
    }


def prepare_center(instance: Instance, *, max_passes: int = 100,
                   deadline: float | None = None) -> dict:
    """Return a natural-stop center or an explicitly capped preparation.

    A strict improvement on the last allowed pass remains capped even if the
    resulting center happens to be global or already locally optimal.  This
    function never claims independent certification or local admission.
    """
    check_deadline(deadline)
    _validate_instance(instance)
    if type(max_passes) is not int or not 1 <= max_passes <= 100:
        raise ValueError("max_passes must be a non-boolean integer in [1,100]")
    greedy = greedy_start(instance, deadline=deadline)
    bits = [int(bit) for bit in greedy["mask"]]
    weight, profit = greedy["weight"], greedy["profit"]
    pass_trace = []
    neighbor_queries = 0
    natural_stop = False

    for pass_index in range(1, max_passes + 1):
        check_deadline(deadline)
        mask_before = "".join(str(bit) for bit in bits)
        weight_before, profit_before = weight, profit
        best = _best_neighbor(instance, bits, weight, profit, deadline)
        flips = best["flipped_indices"]
        neighbor_queries += best["neighbor_queries"]
        if flips is not None:
            for original_index in flips:
                bits[original_index] = 1 - bits[original_index]
            # Verify every applied move from the original item arrays, rather
            # than propagating a wrong cached delta through future passes.
            weight = sum(w * bit for w, bit in zip(instance.weights, bits))
            profit = sum(p * bit for p, bit in zip(instance.profits, bits))
            if weight != best["weight"] or profit != best["profit"]:
                raise ArithmeticError("ascent delta disagrees with the applied mask")
            if weight > instance.capacity or profit <= profit_before:
                raise ArithmeticError("ascent accepted a non-strict or infeasible move")
        pass_trace.append({
            "pass": pass_index,
            "center_before": {"mask": mask_before, "weight": weight_before, "profit": profit_before},
            "center_after": {"mask": "".join(str(bit) for bit in bits), "weight": weight, "profit": profit},
            "flipped_indices": list(flips) if flips is not None else None,
            "strict_improvement": flips is not None,
            "neighbor_queries": best["neighbor_queries"],
            "feasible_neighbors": best["feasible_neighbors"],
            "infeasible_neighbors": best["infeasible_neighbors"],
            "strictly_improving_neighbors": best["strictly_improving_neighbors"],
        })
        if flips is None:
            natural_stop = True
            break

    check_deadline(deadline)
    return {
        "schema_version": "knapsack-feasibility-ascent-v1",
        "greedy": greedy,
        "center": {"mask": "".join(str(bit) for bit in bits), "weight": weight, "profit": profit},
        "natural_stop": natural_stop,
        "preparation_capped": not natural_stop,
        "status": "NATURAL_STOP_UNCERTIFIED" if natural_stop else "EXCLUDED_PREPARATION_CAP",
        "passes_completed": len(pass_trace),
        "max_passes": max_passes,
        "neighbor_queries": neighbor_queries,
        "pass_trace": pass_trace,
        "independent_certificate_issued": False,
        "index_base": 0,
        "rng_used": False,
    }
