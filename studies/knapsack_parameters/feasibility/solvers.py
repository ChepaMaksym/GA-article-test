"""Two exact 0-1 knapsack DPs with independent transition implementations.

This preparation-only module is executed scientifically only in CI.  Tables
are retained only while restoring a witness and are never returned as evidence.
Profit-oriented states contain actual minimum integer weights, not weights
clipped at the capacity; input weights have no additional invented upper bound.
"""

from __future__ import annotations

from array import array
import math
from numbers import Real
import time

from .data_audit import Instance

MAX_DIMENSION = 200000
MAX_CELLS = 20000100


class ResourceLimitExceeded(ValueError):
    """Registered resource boundary exceeded; no approximate answer is supplied."""


class PreparationDeadlineExceeded(TimeoutError):
    """The caller's absolute monotonic preparation deadline was reached."""


def check_deadline(deadline: float | None) -> None:
    """Check an optional absolute monotonic deadline without changing it."""
    if deadline is None:
        return
    if isinstance(deadline, bool) or not isinstance(deadline, Real):
        raise TypeError("deadline must be a non-boolean real monotonic timestamp")
    if not math.isfinite(deadline):
        raise ValueError("deadline must be finite")
    if time.monotonic() >= deadline:
        raise PreparationDeadlineExceeded("registered preparation deadline reached")


def resource_plan(instance: Instance) -> dict:
    """Validate inputs and both preregistered dimensions before any DP allocation."""
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
    total_weight = sum(instance.weights)
    total_profit = sum(instance.profits)
    capacity_eff = min(instance.capacity, total_weight)
    capacity_cells = (instance.n + 1) * (capacity_eff + 1)
    profit_cells = (instance.n + 1) * (total_profit + 1)
    if capacity_eff > MAX_DIMENSION or total_profit > MAX_DIMENSION:
        raise ResourceLimitExceeded("registered DP dimension exceeds 200000")
    if capacity_cells > MAX_CELLS or profit_cells > MAX_CELLS:
        raise ResourceLimitExceeded("registered conceptual DP cells exceed 20000100")
    return {
        "capacity_eff": capacity_eff,
        "sum_profits": total_profit,
        "sum_weights": total_weight,
        "capacity_cells": capacity_cells,
        "profit_cells": profit_cells,
    }


def solve_capacity(instance: Instance, *, deadline: float | None = None) -> dict:
    """Maximize profit for every capacity using only the preceding item row.

    On an equal-value transition the current item is excluded.  Full immutable
    item rows, rather than mutable one-dimensional parent pointers, make the
    recovered mask a 0-1 witness even when many capacities share a predecessor.
    """
    check_deadline(deadline)
    plan = resource_plan(instance)
    dimension = plan["capacity_eff"]
    try:
        # Profits cannot exceed the registered sum bound.  This compact array
        # is not used by the independent profit-oriented transition core.
        if array("I").itemsize < 4:
            raise ResourceLimitExceeded("platform unsigned-int storage is too narrow")
        rows = [array("I", [0]) * (dimension + 1)]
        for item in range(instance.n):
            check_deadline(deadline)
            previous = rows[-1]
            current = array("I", previous)
            profit, weight = instance.profits[item], instance.weights[item]
            for capacity in range(weight, dimension + 1):
                if capacity % 8192 == 0:
                    check_deadline(deadline)
                included = previous[capacity - weight] + profit
                if included > previous[capacity]:
                    current[capacity] = included
            rows.append(current)
        check_deadline(deadline)
        optimum = int(rows[-1][dimension])
        remaining = dimension
        bits = [0] * instance.n
        for row_index in range(instance.n, 0, -1):
            if rows[row_index][remaining] == rows[row_index - 1][remaining]:
                continue
            item = row_index - 1
            if instance.weights[item] > remaining:
                raise ArithmeticError("capacity DP backtrack selected an oversized item")
            bits[item] = 1
            remaining -= instance.weights[item]
        witness_weight = sum(instance.weights[i] for i, bit in enumerate(bits) if bit)
        witness_profit = sum(instance.profits[i] for i, bit in enumerate(bits) if bit)
        if witness_profit != optimum or witness_weight > instance.capacity:
            raise ArithmeticError("capacity DP witness does not certify its optimum")
    except MemoryError as error:
        raise ResourceLimitExceeded("memory unavailable for exact capacity DP") from error
    return {
        "method": "capacity_max_profit_dp_with_witness_exclude_current_item_on_equal",
        "optimum_profit": optimum,
        "witness_mask": "".join(str(bit) for bit in bits),
        "witness_weight": witness_weight,
        "witness_profit": witness_profit,
        "dimension": dimension,
        "conceptual_cells": plan["capacity_cells"],
        "tie_rule": "exclude_current_item_on_equal",
        "arithmetic": "exact_integer",
    }


def solve_profit(instance: Instance, *, deadline: float | None = None) -> dict:
    """Independently minimize actual weight for each exactly achievable profit.

    Unreachable states use sum(weights)+1.  Python integer rows preserve actual
    minimum weights even beyond capacity and beyond unsigned 64-bit storage.
    There is no shared transition or witness-restoration core with capacity DP.
    """
    check_deadline(deadline)
    plan = resource_plan(instance)
    dimension = plan["sum_profits"]
    unreachable = plan["sum_weights"] + 1
    try:
        first = [unreachable] * (dimension + 1)
        first[0] = 0
        table = [first]
        for item_index in range(instance.n):
            check_deadline(deadline)
            prior = table[-1]
            next_row = prior.copy()
            item_profit = instance.profits[item_index]
            item_weight = instance.weights[item_index]
            for target in range(item_profit, dimension + 1):
                if target % 8192 == 0:
                    check_deadline(deadline)
                predecessor_weight = prior[target - item_profit]
                if predecessor_weight == unreachable:
                    continue
                proposed_weight = predecessor_weight + item_weight
                if proposed_weight < prior[target]:
                    next_row[target] = proposed_weight
            table.append(next_row)
        check_deadline(deadline)
        optimum_profit = next(
            value for value in range(dimension, -1, -1)
            if table[-1][value] <= instance.capacity
        )
        target_profit = optimum_profit
        witness = [0 for _ in range(instance.n)]
        for item_count in range(instance.n, 0, -1):
            if table[item_count][target_profit] == table[item_count - 1][target_profit]:
                continue
            original_item = item_count - 1
            witness[original_item] = 1
            target_profit -= instance.profits[original_item]
            if target_profit < 0:
                raise ArithmeticError("profit DP witness crossed a negative profit state")
        recovered_profit = sum(p * bit for p, bit in zip(instance.profits, witness))
        recovered_weight = sum(w * bit for w, bit in zip(instance.weights, witness))
        if (target_profit != 0 or recovered_profit != optimum_profit
                or recovered_weight > instance.capacity
                or recovered_weight != table[-1][optimum_profit]):
            raise ArithmeticError("profit DP witness does not certify its optimum")
    except MemoryError as error:
        raise ResourceLimitExceeded("memory unavailable for exact profit DP") from error
    return {
        "method": "profit_min_weight_dp_independent_transition_core",
        "optimum_profit": optimum_profit,
        "witness_mask": "".join(str(bit) for bit in witness),
        "witness_weight": recovered_weight,
        "witness_profit": recovered_profit,
        "minimum_weight_at_optimum": int(table[-1][optimum_profit]),
        "dimension": dimension,
        "conceptual_cells": plan["profit_cells"],
        "tie_rule": "exclude_current_item_on_equal_minimum_weight",
        "arithmetic": "unbounded_exact_integer",
        "unreachable_sentinel": unreachable,
    }
