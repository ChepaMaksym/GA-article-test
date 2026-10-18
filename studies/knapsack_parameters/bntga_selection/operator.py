"""Independent, evaluator-free B-NTGA archive-selection operator.

This implements only the admitted operator contract, not the complete author
algorithm or a knapsack adapter.  All objective coordinates are minimized in
the explicitly supplied coordinate space.  Random choices are caller inputs.
"""

from __future__ import annotations

import math
from fractions import Fraction
from numbers import Real


FLOAT32_MAX = float.fromhex("0x1.fffffep+127")
PLAN_SCHEMA = "bntga-frozen-plan-v1"
EVENT_SCHEMA = "bntga-selection-event-v1"
_POINT_KEYS = {"id", "objectives", "selected"}
_PLAN_KEYS = {"schema", "archive", "dimension", "balanced", "gaps", "priorities"}


def _counter(value: object, name: str) -> int:
    if type(value) is not int or value < 0:
        raise ValueError(f"{name} must be a nonnegative integer, not bool")
    return value


def _coordinate(value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise ValueError("objective coordinates must be finite real numbers")
    try:
        converted = float(value)
    except (OverflowError, ValueError, TypeError) as error:
        raise ValueError("objective coordinate is not finite float64") from error
    if not math.isfinite(converted):
        raise ValueError("objective coordinates must be finite")
    return converted


def _points(values: object, name: str) -> list[dict]:
    if not isinstance(values, (list, tuple)):
        raise ValueError(f"{name} must be a list or tuple of points")
    copied = []
    for value in values:
        if not isinstance(value, dict) or set(value) != _POINT_KEYS:
            raise ValueError("point must contain exactly id, objectives, selected")
        identity = value["id"]
        if not isinstance(identity, str) or not identity.strip():
            raise ValueError("point id must be a nonempty string")
        objectives = value["objectives"]
        if not isinstance(objectives, list) or not objectives:
            raise ValueError("objectives must be a nonempty list")
        copied.append(
            {
                "id": identity,
                "objectives": [_coordinate(item) for item in objectives],
                "selected": _counter(value["selected"], "selected"),
            }
        )
    return copied


def _consistent(points: list[dict]) -> None:
    dimension = None
    identities = {}
    for point in points:
        coordinates = tuple(point["objectives"])
        if dimension is None:
            dimension = len(coordinates)
        elif len(coordinates) != dimension:
            raise ValueError("objective dimensions must agree")
        identity = point["id"]
        if identity in identities and identities[identity] != coordinates:
            raise ValueError("one id cannot identify different objective vectors")
        identities[identity] = coordinates


def _dominates(first: dict, second: dict) -> bool:
    left, right = first["objectives"], second["objectives"]
    return all(a <= b for a, b in zip(left, right)) and any(
        a < b for a, b in zip(left, right)
    )


def _existing_archive(points: list[dict]) -> None:
    _consistent(points)
    if len({point["id"] for point in points}) != len(points):
        raise ValueError("existing archive ids must be unique")
    if len({tuple(point["objectives"]) for point in points}) != len(points):
        raise ValueError("existing archive objective vectors must be unique")
    for index, point in enumerate(points):
        if any(_dominates(other, point) for other in points[:index] + points[index + 1 :]):
            raise ValueError("existing archive must already be nondominated")


def update_archive(new_points: object, existing: object = ()) -> list[dict]:
    """Return a fresh nondominated archive, preserving documented tie rules.

    Existing representatives win objective ties.  Within a new batch the last
    representative of an objective vector wins and enters with selected=0.
    Counters on surviving existing representatives are retained.
    """
    previous = _points(existing, "existing")
    incoming = _points(new_points, "new_points")
    _existing_archive(previous)
    _consistent(previous + incoming)
    old_vectors = {tuple(point["objectives"]) for point in previous}
    last_new = {
        tuple(point["objectives"]): index for index, point in enumerate(incoming)
    }
    candidates = list(previous)
    for index, point in enumerate(incoming):
        vector = tuple(point["objectives"])
        if vector not in old_vectors and last_new[vector] == index:
            candidates.append(
                {"id": point["id"], "objectives": list(point["objectives"]), "selected": 0}
            )
    return [
        point
        for index, point in enumerate(candidates)
        if not any(
            _dominates(other, point)
            for other in candidates[:index] + candidates[index + 1 :]
        )
    ]


def _balanced_priority(gap: float, selected: int) -> float:
    # Exact rational division avoids overflowing conversion of an arbitrarily
    # large integer denominator.  Conversion of the bounded ratio is float64;
    # underflow to zero is an ordinary finite floating-point result.
    return float(Fraction.from_float(gap) / (selected + 1))


def freeze_selection(archive: object, dimension: object, balanced: bool = True) -> dict:
    """Freeze coordinate order, gap values, and priorities for one block."""
    points = _points(archive, "archive")
    _existing_archive(points)
    if not points:
        raise ValueError("selection requires a nonempty archive")
    if type(balanced) is not bool:
        raise ValueError("balanced must be bool")
    if len(points) == 1:
        if dimension is not None:
            raise ValueError("singleton selection consumes no dimension draw")
        return {
            "schema": PLAN_SCHEMA,
            "archive": points,
            "dimension": None,
            "balanced": balanced,
            "gaps": [None],
            "priorities": [None],
        }
    if type(dimension) is not int or not 0 <= dimension < len(points[0]["objectives"]):
        raise ValueError("dimension must be an integer objective index")
    ordered = sorted(points, key=lambda point: (point["objectives"][dimension], point["id"]))
    distances = []
    for left, right in zip(ordered, ordered[1:]):
        distance = right["objectives"][dimension] - left["objectives"][dimension]
        if not math.isfinite(distance) or distance > FLOAT32_MAX:
            raise ValueError("adjacent objective gap exceeds finite float32 maximum")
        distances.append(distance)
    gaps = [FLOAT32_MAX]
    gaps.extend(max(distances[index - 1], distances[index]) for index in range(1, len(ordered) - 1))
    gaps.append(FLOAT32_MAX)
    priorities = [
        _balanced_priority(gap, point["selected"]) if balanced else gap
        for point, gap in zip(ordered, gaps)
    ]
    return {
        "schema": PLAN_SCHEMA,
        "archive": ordered,
        "dimension": dimension,
        "balanced": balanced,
        "gaps": gaps,
        "priorities": priorities,
    }


def _validated_plan(plan: object) -> dict:
    if not isinstance(plan, dict) or set(plan) != _PLAN_KEYS:
        raise ValueError("plan fields do not match the frozen-plan schema")
    if plan["schema"] != PLAN_SCHEMA:
        raise ValueError("unrecognized frozen-plan schema")
    expected = freeze_selection(plan["archive"], plan["dimension"], plan["balanced"])
    for name in ("gaps", "priorities"):
        supplied = plan[name]
        if not isinstance(supplied, list) or len(supplied) != len(expected[name]):
            raise ValueError("frozen numerical vectors have incorrect shape")
        for value, required in zip(supplied, expected[name]):
            if required is None:
                if value is not None:
                    raise ValueError("singleton numerical entries must be null")
            elif _coordinate(value) != required:
                raise ValueError("frozen numerical values differ from the archive snapshot")
    if plan["archive"] != expected["archive"]:
        raise ValueError("plan archive is not in its frozen stable coordinate order")
    return expected


def select_pair(
    plan: object,
    current_counts: object,
    tournament_draws: object,
    neighbor_side: object = None,
) -> dict:
    """Select one pair from explicit draws without modifying any input.

    Current counters record past pairs but do not affect this block's frozen
    priorities.  For internal positions, 0 selects next and 1 previous.
    """
    frozen = _validated_plan(plan)
    archive = frozen["archive"]
    identities = {point["id"] for point in archive}
    if not isinstance(current_counts, dict) or set(current_counts) != identities:
        raise ValueError("current_counts must contain exactly the frozen archive ids")
    counts = {}
    for point in archive:
        identity = point["id"]
        count = _counter(current_counts[identity], "current count")
        if count < point["selected"]:
            raise ValueError("current count cannot precede the frozen snapshot")
        counts[identity] = count
    if not isinstance(tournament_draws, list):
        raise ValueError("tournament_draws must be a list")
    singleton = len(archive) == 1
    if singleton:
        if tournament_draws or neighbor_side is not None:
            raise ValueError("singleton selection consumes no tournament or neighbor draw")
        first = second = 0
        priority = None
    else:
        if not tournament_draws:
            raise ValueError("tournament must contain at least one draw")
        for draw in tournament_draws:
            if type(draw) is not int or not 0 <= draw < len(archive):
                raise ValueError("tournament draw must index the sorted archive")
        first = tournament_draws[0]
        for draw in tournament_draws[1:]:
            if frozen["priorities"][draw] > frozen["priorities"][first]:
                first = draw
        if first == 0 or first == len(archive) - 1:
            if neighbor_side is not None:
                raise ValueError("boundary selection consumes no neighbor draw")
            second = 1 if first == 0 else first - 1
        else:
            if type(neighbor_side) is not int or neighbor_side not in (0, 1):
                raise ValueError("interior neighbor_side must be 0 (next) or 1 (previous)")
            second = first + 1 if neighbor_side == 0 else first - 1
        priority = frozen["priorities"][first]
    after = dict(counts)
    if not singleton:
        after[archive[first]["id"]] += 1
        after[archive[second]["id"]] += 1
    return {
        "schema": EVENT_SCHEMA,
        "tournament_draws": list(tournament_draws),
        "neighbor_side": neighbor_side,
        "first_index": first,
        "second_index": second,
        "first_id": archive[first]["id"],
        "second_id": archive[second]["id"],
        "first_priority": priority,
        "counts_before": dict(counts),
        "counts_after": after,
        "singleton": singleton,
    }
