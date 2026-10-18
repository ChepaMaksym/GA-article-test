"""Independent, evaluator-free replay of the frozen selection contract.

No production archive, gap, selection or comparison function is imported.
The receipt verifies recorded operations, not genetic search effectiveness or
numerical reproduction of the authors' complete algorithm.
"""
from __future__ import annotations

from copy import deepcopy
from decimal import Decimal, localcontext
import math
from numbers import Real
import os


_EDGE_GAP = float.fromhex("0x1.fffffep+127")
_POINT_FIELDS = {"id", "objectives", "selected"}
_PLAN_FIELDS = {"schema", "archive", "dimension", "balanced", "gaps", "priorities"}
_EVENT_FIELDS = {"schema", "tournament_draws", "neighbor_side", "first_index",
                 "second_index", "first_id", "second_id", "first_priority",
                 "counts_before", "counts_after", "singleton"}
_BLOCK_FIELDS = {"archive_before", "plan", "requests", "events",
                 "archive_after_selection", "new_points", "archive_after_update"}
_JOURNAL_FIELDS = {"schema", "balanced", "initial_points", "initial_archive",
                   "blocks", "final_archive", "accounting"}


def _require(condition, message):
    if not condition:
        raise ValueError("Independent B-NTGA verification: " + message)


def _ci_only():
    _require(os.environ.get("GITHUB_ACTIONS") == "true", "execution is CI-only")
    _require(os.environ.get("GITHUB_REPOSITORY") == "ChepaMaksym/GA-article-test",
             "wrong repository")
    _require(os.environ.get("GITHUB_REF") ==
             "refs/heads/research/masters-ga-diversity-crossover", "wrong branch")


def _fields(value, fields, label):
    _require(type(value) is dict and set(value) == fields, label + " fields differ")


def _same(actual, expected, label):
    """Strict JSON shapes and integers; finite floats use the stated tolerance."""
    _require(type(actual) is type(expected), label + " type differs")
    if type(expected) is dict:
        _require(set(actual) == set(expected), label + " keys differ")
        for name in expected:
            _same(actual[name], expected[name], label + "." + name)
    elif type(expected) is list:
        _require(len(actual) == len(expected), label + " length differs")
        for index, (found, wanted) in enumerate(zip(actual, expected, strict=True)):
            _same(found, wanted, label + f"[{index}]")
    elif type(expected) is float:
        _require(math.isfinite(actual) and math.isfinite(expected) and
                 math.isclose(actual, expected, rel_tol=1e-12, abs_tol=1e-12),
                 label + " finite numeric value differs")
    else:
        _require(type(expected) in (str, int, bool, type(None)) and actual == expected,
                 label + " value differs")


def _points(raw, label):
    _require(type(raw) in (list, tuple), label + " must be a sequence")
    result = []
    dimension = None
    for point in raw:
        _fields(point, _POINT_FIELDS, label + " point")
        _require(type(point["id"]) is str and bool(point["id"].strip()), "invalid point id")
        _require(type(point["selected"]) is int and point["selected"] >= 0,
                 "invalid selection count")
        vector = point["objectives"]
        _require(type(vector) is list and bool(vector), "empty/non-list objective vector")
        _require(all(isinstance(value, Real) and not isinstance(value, bool)
                     for value in vector), "non-real objective coordinate")
        try:
            coordinates = [float(value) for value in vector]
        except (OverflowError, ValueError, TypeError) as error:
            raise ValueError("Independent B-NTGA verification: coordinate conversion failed") from error
        _require(all(math.isfinite(value) for value in coordinates), "nonfinite objective")
        dimension = len(coordinates) if dimension is None else dimension
        _require(len(coordinates) == dimension, "inconsistent objective dimensions")
        result.append({"id": point["id"], "objectives": coordinates,
                       "selected": point["selected"]})
    return result


def _dominates(left, right):
    comparisons = list(zip(left["objectives"], right["objectives"], strict=True))
    return all(a <= b for a, b in comparisons) and any(a < b for a, b in comparisons)


def _assert_archive(points):
    _require(len({point["id"] for point in points}) == len(points), "duplicate archive id")
    _require(len({tuple(point["objectives"]) for point in points}) == len(points),
             "duplicate archive objective vector")
    _require(not any(_dominates(a, b) for i, a in enumerate(points)
                     for j, b in enumerate(points) if i != j), "dominated archive member")


def _rebuild_archive(new_raw, old_raw=()):
    """Reconstruct by pairwise dominance, without production functions."""
    old = _points(old_raw, "existing")
    new = _points(new_raw, "new")
    _assert_archive(old)
    combined = old + new
    if combined:
        _require(len({len(point["objectives"]) for point in combined}) == 1,
                 "mixed old/new dimensions")
    identity_vectors = {}
    for point in combined:
        vector = tuple(point["objectives"])
        _require(point["id"] not in identity_vectors or
                 identity_vectors[point["id"]] == vector, "id reused with different objectives")
        identity_vectors[point["id"]] = vector
    old_vectors = {tuple(point["objectives"]) for point in old}
    last_new = {tuple(point["objectives"]): index for index, point in enumerate(new)}
    candidates = list(old)
    for index, point in enumerate(new):
        vector = tuple(point["objectives"])
        if vector not in old_vectors and last_new[vector] == index:
            candidates.append({"id": point["id"], "objectives": point["objectives"],
                               "selected": 0})
    result = [deepcopy(point) for point in candidates
              if not any(_dominates(other, point) for other in candidates)]
    _assert_archive(result)
    return result


def _expected_plan(raw_archive, dimension, balanced):
    _require(type(balanced) is bool, "balanced must be Boolean")
    archive = _points(raw_archive, "plan archive")
    _require(bool(archive), "empty selection archive")
    _assert_archive(archive)
    if len(archive) == 1:
        _require(dimension is None, "singleton must not draw a dimension")
        return {"schema": "bntga-frozen-plan-v1", "archive": archive,
                "dimension": None, "balanced": balanced, "gaps": [None],
                "priorities": [None]}
    _require(type(dimension) is int and 0 <= dimension < len(archive[0]["objectives"]),
             "invalid dimension index")
    ordered = sorted(archive, key=lambda point: (point["objectives"][dimension], point["id"]))
    intervals = [ordered[index + 1]["objectives"][dimension] -
                 ordered[index]["objectives"][dimension]
                 for index in range(len(ordered) - 1)]
    _require(all(math.isfinite(value) and 0 <= value <= _EDGE_GAP for value in intervals),
             "objective difference outside finite float32 gap bound")
    gaps = [_EDGE_GAP] + [max(intervals[index - 1], intervals[index])
                           for index in range(1, len(ordered) - 1)] + [_EDGE_GAP]
    priorities = []
    with localcontext() as context:
        context.prec = 80
        for point, gap in zip(ordered, gaps, strict=True):
            # Decimal is independent of production Fraction arithmetic and
            # avoids overflowing conversion of a large integer denominator.
            priority = (float(Decimal.from_float(gap) / Decimal(point["selected"] + 1))
                        if balanced else gap)
            _require(math.isfinite(priority) and priority >= 0, "invalid finite priority")
            priorities.append(priority)
    return {"schema": "bntga-frozen-plan-v1", "archive": ordered,
            "dimension": dimension, "balanced": balanced, "gaps": gaps,
            "priorities": priorities}


def _expected_event(plan, counts, draws, side):
    _fields(plan, _PLAN_FIELDS, "plan")
    archive = plan["archive"]
    ids = [point["id"] for point in archive]
    _require(type(counts) is dict and set(counts) == set(ids), "counter identity mismatch")
    _require(all(type(counts[point["id"]]) is int and
                 counts[point["id"]] >= point["selected"] for point in archive),
             "invalid/decreased current counter")
    _require(type(draws) is list, "tournament draws must be a list")
    before = dict(counts)
    after = dict(counts)
    singleton = len(archive) == 1
    if singleton:
        _require(not draws and side is None, "singleton consumed random choices")
        first = second = 0
        priority = None
    else:
        _require(bool(draws) and all(type(index) is int and 0 <= index < len(archive)
                                    for index in draws), "invalid tournament index")
        first = draws[0]
        for index in draws[1:]:
            if plan["priorities"][index] > plan["priorities"][first]:
                first = index
        if first == 0 or first == len(archive) - 1:
            _require(side is None, "edge must not draw a neighbor side")
            second = 1 if first == 0 else first - 1
        else:
            _require(type(side) is int and side in (0, 1), "invalid interior neighbor side")
            second = first + 1 if side == 0 else first - 1
        after[ids[first]] += 1
        after[ids[second]] += 1
        priority = plan["priorities"][first]
    return {"schema": "bntga-selection-event-v1", "tournament_draws": list(draws),
            "neighbor_side": side, "first_index": first, "second_index": second,
            "first_id": ids[first], "second_id": ids[second], "first_priority": priority,
            "counts_before": before, "counts_after": after, "singleton": singleton}


def verify_journal(journal):
    """Rebuild archived vectors, frozen priorities, choices and accounting."""
    _ci_only()
    _fields(journal, _JOURNAL_FIELDS, "journal")
    _same(journal["schema"], "bntga-operator-journal-v1", "journal schema")
    _require(type(journal["balanced"]) is bool, "invalid balanced flag")
    _require(type(journal["initial_points"]) is list and type(journal["blocks"]) is list,
             "journal inputs must be lists")
    archive = _rebuild_archive(journal["initial_points"])
    _same(journal["initial_archive"], archive, "initial archive")
    pairs = 0
    supplied = len(journal["initial_points"])
    for index, block in enumerate(journal["blocks"]):
        label = f"block[{index}]"
        _fields(block, _BLOCK_FIELDS, label)
        _same(block["archive_before"], archive, label + " archive before")
        _fields(block["plan"], _PLAN_FIELDS, label + " plan")
        plan = _expected_plan(archive, block["plan"]["dimension"], journal["balanced"])
        _same(block["plan"], plan, label + " frozen plan")
        _require(type(block["requests"]) is list and type(block["events"]) is list and
                 len(block["requests"]) == len(block["events"]), "request/event count mismatch")
        counts = {point["id"]: point["selected"] for point in archive}
        for request, event in zip(block["requests"], block["events"], strict=True):
            _fields(request, {"tournament_draws", "neighbor_side"}, "selection request")
            _fields(event, _EVENT_FIELDS, "selection event")
            expected = _expected_event(plan, counts, request["tournament_draws"],
                                       request["neighbor_side"])
            _same(event, expected, label + " selection event")
            counts = expected["counts_after"]
            pairs += 1
        after_selection = [{**point, "selected": counts[point["id"]]} for point in archive]
        _same(block["archive_after_selection"], after_selection, label + " archive counters")
        _require(type(block["new_points"]) is list, "new points must be a list")
        supplied += len(block["new_points"])
        archive = _rebuild_archive(block["new_points"], after_selection)
        _same(block["archive_after_update"], archive, label + " archive update")
    _same(journal["final_archive"], archive, "final archive")
    expected_accounting = {"selection_pairs": pairs, "objective_vectors_supplied": supplied,
                           "new_fitness_evaluations": 0}
    _same(journal["accounting"], expected_accounting, "accounting")
    return {"status": "VERIFIED", **expected_accounting}
