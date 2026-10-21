"""Exact-count models and independently checked radius-two features.

These functions do not generate search candidates. Mutation probabilities
condition on repeatedly mutating one fixed mask, not on the complete GA.
Sampling probabilities concern uniform sampling without replacement from
the complete neighborhood, not a local-optimality certificate after a miss.
"""

from __future__ import annotations

from fractions import Fraction
import itertools
import math
from numbers import Integral, Real


def _integer(value, label, minimum=0):
    if not isinstance(value, Integral) or isinstance(value, bool) or value < minimum:
        raise ValueError(f"{label} must be an integer not below {minimum}")
    return int(value)


def _require(condition, message):
    if not condition:
        raise ValueError(message)


def mutation_probability(n: int, b1: int, b2: int, p: float) -> float:
    """Probability of landing on an improving one/two-bit neighbor.

    All other bits must remain unchanged. The disjoint neighbor events
    have probabilities p(1-p)^(n-1) and p^2(1-p)^(n-2), respectively.
    No statement about selection, crossover or future generations follows.
    """
    n = _integer(n, "n", 2)
    b1 = _integer(b1, "b1")
    b2 = _integer(b2, "b2")
    if b1 > n or b2 > n * (n - 1) // 2:
        raise ValueError("improving counts exceed their neighborhood sizes")
    if (not isinstance(p, Real) or isinstance(p, bool)
            or not math.isfinite(p) or not 0 <= p <= 1):
        raise ValueError("p must be a finite probability")
    p = float(p)
    return b1 * p * (1 - p) ** (n - 1) + b2 * p * p * (1 - p) ** (n - 2)


def detection_probability(total: int, better: int, sample: int) -> float:
    """Exact combinatorial probability, converted to float only at output."""
    total = _integer(total, "total", 1)
    better = _integer(better, "better")
    sample = _integer(sample, "sample")
    if better > total or sample > total:
        raise ValueError("better and sample cannot exceed total")
    if sample == 0 or better == 0:
        return 0.0
    if sample > total - better:
        return 1.0
    denominator = math.comb(total, sample)
    missed = math.comb(total - better, sample)
    return float(Fraction(denominator - missed, denominator))


def certificate_features(certificate, *, weights, profits, capacity):
    """Validate every saved neighbor and extract compact integer features.

    Original weights/profits are mandatory, so the extractor does not trust
    saved scores or relations. Provenance hashes and the source-run replay
    are separately checked by the execution layer and historical verifier.
    No exact optimum is solved here; its retained value is only checked for
    consistency with the listed masks.
    """
    capacity = _integer(capacity, "capacity", 1)
    weights = tuple(_integer(w, "weight", 1) for w in weights)
    profits = tuple(_integer(v, "profit", 1) for v in profits)
    n = len(weights)
    _require(n >= 2 and len(profits) == n, "source dimensions do not match")
    _require(isinstance(certificate, dict), "certificate must be an object")
    summary = certificate.get("summary")
    neighbors = certificate.get("neighbors")
    _require(isinstance(summary, dict) and isinstance(neighbors, list),
             "certificate summary and neighbor list required")
    center = summary.get("center_mask")
    _require(isinstance(center, str) and len(center) == n
             and set(center) <= {"0", "1"}, "invalid center mask")
    center_bits = tuple(int(bit) for bit in center)
    center_weight = sum(w * bit for w, bit in zip(weights, center_bits))
    center_profit = sum(v * bit for v, bit in zip(profits, center_bits))
    _require(center_weight <= capacity, "center is infeasible")
    optimum = _integer(summary.get("optimum"), "retained optimum")
    _require(center_profit <= optimum, "center exceeds retained optimum")
    total = n + n * (n - 1) // 2
    _require(len(neighbors) == total, "neighborhood is incomplete")
    types = {name: 0 for name in
             ("add_one", "remove_one", "swap_one", "add_two", "remove_two")}
    b1 = b2 = feasible_count = equal_count = 0
    gains = []
    positions = itertools.chain(((i,) for i in range(n)),
                                itertools.combinations(range(n), 2))
    for row, flips in zip(neighbors, positions):
        _require(isinstance(row, dict), "neighbor row must be an object")
        _require({"flips", "mask", "weight", "profit", "feasible",
                  "infeasibility_reason", "relation"} <= set(row),
                 "neighbor fields are incomplete")
        recorded_flips = row.get("flips")
        _require(isinstance(recorded_flips, list)
                 and all(type(i) is int for i in recorded_flips)
                 and recorded_flips == list(flips),
                 "neighbor flips are duplicated, reordered or incorrect")
        changed = set(flips)
        candidate = tuple(1 - bit if i in changed else bit
                          for i, bit in enumerate(center_bits))
        mask = "".join(map(str, candidate))
        weight = sum(w * bit for w, bit in zip(weights, candidate))
        profit = sum(v * bit for v, bit in zip(profits, candidate))
        feasible = weight <= capacity
        _require(not feasible or profit <= optimum,
                 "neighbor exceeds retained optimum")
        relation = ((profit > center_profit) - (profit < center_profit)) if feasible else None
        _require(row.get("mask") == mask
                 and type(row.get("weight")) is int and row["weight"] == weight
                 and type(row.get("profit")) is int and row["profit"] == profit
                 and type(row.get("feasible")) is bool and row["feasible"] is feasible,
                 "neighbor mask, score or feasibility mismatch")
        _require(row.get("infeasibility_reason") ==
                 (None if feasible else "CAPACITY_EXCEEDED"),
                 "neighbor infeasibility reason mismatch")
        _require((type(row.get("relation")) is int if feasible
                  else row.get("relation") is None)
                 and row.get("relation") == relation,
                 "neighbor relation mismatch")
        feasible_count += int(feasible)
        equal_count += int(feasible and profit == center_profit)
        if feasible and profit > center_profit:
            gains.append(profit - center_profit)
            if len(flips) == 1:
                b1 += 1
                kind = "add_one" if center_bits[flips[0]] == 0 else "remove_one"
            else:
                b2 += 1
                removed = sum(center_bits[i] for i in flips)
                kind = ("add_two" if removed == 0 else "remove_two"
                        if removed == 2 else "swap_one")
            types[kind] += 1
    state = ("GLOBAL_OPTIMUM" if center_profit == optimum
             else "N2_NOT_LOCAL" if gains
             else "N2_NONSTRICT_NONGLOBAL" if equal_count
             else "N2_STRICT_NONGLOBAL")
    if state == "GLOBAL_OPTIMUM":
        _require(not gains, "global center has an improving neighbor")
    expected = {"n": n, "center_weight": center_weight,
                "center_profit": center_profit, "neighbor_count": total,
                "feasible_neighbor_count": feasible_count,
                "infeasible_neighbor_count": total - feasible_count,
                "better_feasible_count": b1 + b2,
                "equal_feasible_count": equal_count}
    for field, value in expected.items():
        _require(type(summary.get(field)) is int and summary[field] == value,
                 f"certificate summary mismatch: {field}")
    _require(summary.get("state") == state, "certificate state mismatch")
    return {"n": n, "neighbor_count": total,
            "b1": b1, "b2": b2, "total_better": b1 + b2,
            "center_profit": center_profit, "center_weight": center_weight,
            "capacity": capacity, "slack": capacity - center_weight,
            "min_positive_gain": min(gains) if gains else None,
            "max_positive_gain": max(gains) if gains else None,
            "sum_positive_gain": sum(gains), "improvement_types": types}
