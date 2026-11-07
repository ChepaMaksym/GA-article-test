"""Preparation-only exact oracles with independent transitions and packed witnesses.

The capacity DP maximizes profit at each capacity. The separate profit DP
minimizes weight at each exact profit. Neither oracle is available to the GA.
Only one numeric row is retained; item decisions occupy one bit per state.
"""
from __future__ import annotations

import math
from numbers import Real
import os
from time import monotonic, perf_counter_ns

import numpy as np


DEFAULT_MEMORY_LIMIT_BYTES = 512 * 1024 * 1024


class ExactResourceLimit(ValueError):
    """An exact calculation exceeds its declared resource limit."""


class ExactPreparationTimeout(TimeoutError):
    """The caller's absolute monotonic deadline has expired."""


def _ci_only():
    if os.environ.get("GITHUB_ACTIONS") != "true":
        raise ValueError("Exact preparation is allowed only in GitHub Actions")


def _check_deadline(deadline):
    if deadline is None:
        return
    if isinstance(deadline, bool) or not isinstance(deadline, Real) or not math.isfinite(deadline):
        raise ValueError("deadline must be a finite non-boolean monotonic timestamp")
    if monotonic() >= deadline:
        raise ExactPreparationTimeout("Exact preparation deadline reached")


def _problem(problem):
    if type(problem) is not dict or set(problem) != {"n", "capacity", "weights", "profits"}:
        raise ValueError("Only the knapsack problem fields are accepted")
    if type(problem["n"]) is not int or problem["n"] < 1:
        raise ValueError("n must be a positive integer")
    if type(problem["capacity"]) is not int or problem["capacity"] < 0:
        raise ValueError("capacity must be a nonnegative integer")
    for name in ("weights", "profits"):
        if not isinstance(problem[name], (list, tuple)) or len(problem[name]) != problem["n"]:
            raise ValueError("Wrong item-vector length")
        if any(type(value) is not int or value <= 0 for value in problem[name]):
            raise ValueError("Item entries must be positive non-boolean integers")
    largest = int(np.iinfo(np.int64).max)
    if sum(problem["weights"]) >= largest or sum(problem["profits"]) > largest:
        raise ExactResourceLimit("Input sums exceed the exact int64 representation")


def resource_plan(problem, *, memory_limit_bytes=DEFAULT_MEMORY_LIMIT_BYTES):
    """Bound the arrays before allocation; the guard never substitutes an approximation."""
    _problem(problem)
    if type(memory_limit_bytes) is not int or memory_limit_bytes <= 0:
        raise ValueError("memory_limit_bytes must be a positive integer")
    n = problem["n"]
    capacity = min(problem["capacity"], sum(problem["weights"]))
    profit = sum(problem["profits"])
    plans = {}
    for method, dimension in (("capacity", capacity), ("profit", profit)):
        states = dimension + 1
        packed_row_bytes = (states + 7) // 8
        # Sixty-four bytes per state conservatively cover the live numeric,
        # boolean, indexing and temporary arrays used by either implementation.
        array_bound = 64 * states + n * packed_row_bytes
        estimated = array_bound + n * 1024 + 1024 * 1024
        plans[method] = {"dimension": dimension, "states": states,
                         "packed_decision_bytes": n * packed_row_bytes,
                         "estimated_peak_bytes": estimated}
        if estimated > memory_limit_bytes:
            raise ExactResourceLimit(f"Exact {method} DP exceeds the declared memory limit")
    return {"n": n, "capacity_eff": capacity, "sum_weights": sum(problem["weights"]),
            "sum_profits": profit, "memory_limit_bytes": memory_limit_bytes,
            "oracles": plans, "storage": "int64_row_and_little_endian_packed_item_decisions"}


def solve_capacity(problem, *, memory_limit_bytes=DEFAULT_MEMORY_LIMIT_BYTES, deadline=None):
    """Independently maximize profit for each at-most capacity, excluding ties."""
    _ci_only()
    _check_deadline(deadline)
    plan = resource_plan(problem, memory_limit_bytes=memory_limit_bytes)
    dimension = plan["capacity_eff"]
    try:
        row = np.zeros(dimension + 1, dtype=np.int64)
        decisions = []
        for weight, profit in zip(problem["weights"], problem["profits"], strict=True):
            _check_deadline(deadline)
            selected = np.zeros(dimension + 1, dtype=np.uint8)
            if weight <= dimension:
                # Materializing proposals before assignment prevents item reuse.
                included_profit = row[:-weight] + profit
                improved = included_profit > row[weight:]
                target = row[weight:]
                target[improved] = included_profit[improved]
                selected[weight:] = improved
            decisions.append(np.packbits(selected, bitorder="little"))
        _check_deadline(deadline)
        optimum = int(row[dimension])
        remaining_capacity = dimension
        mask = ["0"] * problem["n"]
        for item in range(problem["n"] - 1, -1, -1):
            packed = decisions[item]
            chosen = (int(packed[remaining_capacity // 8]) >> (remaining_capacity % 8)) & 1
            if chosen:
                mask[item] = "1"
                remaining_capacity -= problem["weights"][item]
                if remaining_capacity < 0:
                    raise ArithmeticError("Capacity witness entered a negative state")
        total_weight = sum(w for w, bit in zip(problem["weights"], mask, strict=True) if bit == "1")
        total_profit = sum(v for v, bit in zip(problem["profits"], mask, strict=True) if bit == "1")
        if total_weight > problem["capacity"] or total_profit != optimum:
            raise ArithmeticError("Capacity witness does not certify its optimum")
    except MemoryError as error:
        raise ExactResourceLimit("Memory allocation failed during capacity DP") from error
    return {"method": "capacity_max_profit_dp_packed_witness", "optimum_profit": optimum,
            "witness_mask": "".join(mask), "witness_weight": total_weight,
            "witness_profit": total_profit, "dimension": dimension,
            "tie_rule": "exclude_current_item_on_equal_profit", "arithmetic": "exact_int64",
            "estimated_peak_bytes": plan["oracles"]["capacity"]["estimated_peak_bytes"]}


def solve_profit(problem, *, memory_limit_bytes=DEFAULT_MEMORY_LIMIT_BYTES, deadline=None):
    """Independently minimize actual weight at each exact profit, excluding ties."""
    _ci_only()
    _check_deadline(deadline)
    plan = resource_plan(problem, memory_limit_bytes=memory_limit_bytes)
    dimension = plan["sum_profits"]
    unreachable = plan["sum_weights"] + 1
    try:
        minimum_weights = np.full(dimension + 1, unreachable, dtype=np.int64)
        minimum_weights[0] = 0
        history = []
        for item_profit, item_weight in zip(problem["profits"], problem["weights"], strict=True):
            _check_deadline(deadline)
            predecessors = minimum_weights[:-item_profit]
            reachable = predecessors != unreachable
            included_weights = np.full(predecessors.shape, unreachable, dtype=np.int64)
            # No addition is performed on unreachable sentinels. Every valid
            # included weight is at most the exact sum of source weights.
            np.add(predecessors, item_weight, out=included_weights, where=reachable)
            improves_weight = included_weights < minimum_weights[item_profit:]
            target_weights = minimum_weights[item_profit:]
            target_weights[improves_weight] = included_weights[improves_weight]
            decisions_for_item = np.zeros(dimension + 1, dtype=np.uint8)
            decisions_for_item[item_profit:] = improves_weight
            history.append(np.packbits(decisions_for_item, bitorder="little"))
        _check_deadline(deadline)
        feasible_profits = np.flatnonzero((minimum_weights != unreachable)
                                         & (minimum_weights <= problem["capacity"]))
        optimum_profit = int(feasible_profits[-1])
        exact_minimum_weight = int(minimum_weights[optimum_profit])
        remaining_profit = optimum_profit
        witness_bits = ["0" for _ in range(problem["n"])]
        for source_item in reversed(range(problem["n"])):
            byte = int(history[source_item][remaining_profit >> 3])
            included = bool(byte & (1 << (remaining_profit & 7)))
            if included:
                witness_bits[source_item] = "1"
                remaining_profit -= problem["profits"][source_item]
                if remaining_profit < 0:
                    raise ArithmeticError("Profit witness entered a negative state")
        witness_profit = sum(problem["profits"][i] for i, bit in enumerate(witness_bits) if bit == "1")
        witness_weight = sum(problem["weights"][i] for i, bit in enumerate(witness_bits) if bit == "1")
        if (remaining_profit != 0 or witness_profit != optimum_profit
                or witness_weight != exact_minimum_weight or witness_weight > problem["capacity"]):
            raise ArithmeticError("Profit witness does not certify its optimum")
    except MemoryError as error:
        raise ExactResourceLimit("Memory allocation failed during profit DP") from error
    return {"method": "profit_min_weight_dp_independent_packed_witness", "optimum_profit": optimum_profit,
            "witness_mask": "".join(witness_bits), "witness_weight": witness_weight,
            "witness_profit": witness_profit, "minimum_weight_at_optimum": exact_minimum_weight,
            "dimension": dimension, "tie_rule": "exclude_current_item_on_equal_minimum_weight",
            "arithmetic": "exact_int64", "unreachable_sentinel": unreachable,
            "estimated_peak_bytes": plan["oracles"]["profit"]["estimated_peak_bytes"]}


def certify_problem(problem, *, memory_limit_bytes=DEFAULT_MEMORY_LIMIT_BYTES, deadline=None):
    """Require agreement of two exact optima and independently feasible witnesses."""
    _ci_only()
    _check_deadline(deadline)
    plan = resource_plan(problem, memory_limit_bytes=memory_limit_bytes)
    first_started = perf_counter_ns()
    capacity_certificate = solve_capacity(problem, memory_limit_bytes=memory_limit_bytes, deadline=deadline)
    capacity_ns = perf_counter_ns() - first_started
    second_started = perf_counter_ns()
    profit_certificate = solve_profit(problem, memory_limit_bytes=memory_limit_bytes, deadline=deadline)
    profit_ns = perf_counter_ns() - second_started
    if capacity_certificate["optimum_profit"] != profit_certificate["optimum_profit"]:
        raise ArithmeticError("The two independent exact optima disagree")
    return {"status": "CERTIFIED_TWO_INDEPENDENT_EXACT_ORACLES",
            "optimum": capacity_certificate["optimum_profit"],
            "capacity_certificate": capacity_certificate, "profit_certificate": profit_certificate,
            "resource_plan": plan, "timing_ns": {"capacity_oracle": capacity_ns, "profit_oracle": profit_ns},
            "search_uses_optimum": False}
