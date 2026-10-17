"""Independent bounded-SD verification; no production controller imports.

The historical verifier reconstructs the shared fixed operator/RNG path.  This
module independently computes the source threshold with 80-digit Decimal
arithmetic and reconstructs the separately labelled generation adapter.
"""
from __future__ import annotations

from decimal import Decimal, localcontext
import hashlib
import json
import math
import os

from studies.adaptive_parameters.mutation_only import verifier as historical


SCHEMA = "knapsack-mutation-rules-derived-sd-v1"
FIELDS = {"schema", "requested_profile", "backend_profile", "status",
          "source_journal_sha256", "domain", "proof", "controller_trace",
          "accounting", "construction_verification"}
TRACE_FIELDS = {"generation", "start_call", "end_call", "complete", "children",
                "strict_success", "record_before", "record_after", "r_before",
                "u_before", "p_m", "threshold", "r_after", "u_after",
                "p_m_next", "event"}


def _require(condition, message):
    if not condition:
        raise ValueError("Invalid bounded SD view: " + message)


def _ci_only():
    _require(os.environ.get("GITHUB_ACTIONS") == "true", "CI only")
    _require(os.environ.get("GITHUB_REPOSITORY") == "ChepaMaksym/GA-article-test",
             "wrong repository")
    _require(os.environ.get("GITHUB_REF") ==
             "refs/heads/research/masters-ga-diversity-crossover", "wrong branch")


def _same(actual, expected, label):
    try:
        left = json.dumps(actual, sort_keys=True, separators=(",", ":"), allow_nan=False)
        right = json.dumps(expected, sort_keys=True, separators=(",", ":"), allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise ValueError("Invalid bounded SD view: non-JSON " + label) from exc
    _require(left == right, label)


def _close(actual, expected, label):
    _require(type(actual) in (int, float) and math.isfinite(actual) and
             math.isclose(actual, float(expected), rel_tol=1e-12, abs_tol=1e-12), label)


def _threshold(n, radius, confidence):
    """Independent transcription of the full-version ln(e*n*R) expression."""
    with localcontext() as context:
        context.prec = 80
        size, strength, remainder = Decimal(n), Decimal(radius), Decimal(n - radius)
        return ((size / strength) ** radius *
                (size / remainder) ** (n - radius) *
                (Decimal(1) + size.ln() + Decimal(confidence).ln()))


def _digest(log):
    raw = json.dumps(log, sort_keys=True, ensure_ascii=False,
                     separators=(",", ":"), allow_nan=False).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def verify_sd_view(fixed_log, view):
    """Verify source operators, bound proof and every derived SD transition.

    Verification evaluates existing records; it performs no new search and
    does not assert numerical replication or retained SD runtime guarantees.
    """
    _ci_only()
    _require(type(fixed_log) is dict and type(view) is dict and set(view) == FIELDS,
             "journal/view shape")
    _require(fixed_log.get("method") == "fixed", "source must retain method=fixed")
    _require(type(fixed_log.get("problem")) is dict and
             fixed_log["problem"].get("n") == 100 and
             type(fixed_log["problem"].get("n")) is int, "n=100 required")
    budget = fixed_log.get("budget")
    _require(type(budget) is int and 1 <= budget <= 5000,
             "only the registered budget domain 1..5000 is supported")
    threshold = _threshold(100, 1, 100 ** 3)
    _require(Decimal(budget) < threshold, "inactive-radius proof fails")
    replay = historical.verify_log(fixed_log)
    _same(replay["verification_status"], "VERIFIED", "source operator verification")
    for name, expected in (("schema", SCHEMA), ("requested_profile", "paper_sd_mutation"),
                           ("backend_profile", "fixed"), ("status", "BOUNDED_EQUIVALENCE"),
                           ("source_journal_sha256", _digest(fixed_log))):
        _same(view[name], expected, name)
    _same(view["domain"], {"n": 100, "population_size": 30,
          "crossover_probability": 0.9, "budget": budget, "r_initial": 1,
          "u_initial": 0, "R": 100 ** 3}, "bounded domain")
    proof = view["proof"]
    _require(type(proof) is dict and set(proof) == {
        "threshold_r1", "budget_strictly_below_threshold", "radius_inactive",
        "equivalence_kind"}, "proof fields")
    _close(proof["threshold_r1"], threshold, "independent 80-digit initial threshold")
    _same(proof["budget_strictly_below_threshold"], True, "strict budget proof")
    _same(proof["radius_inactive"], True, "radius inactivity")
    _same(proof["equivalence_kind"], "REGISTERED_BOUNDED_OPERATOR_PATH",
          "equivalence is not a general algorithm claim")

    trace = view["controller_trace"]
    events = fixed_log["generations"]
    _require(type(trace) is list and len(trace) == len(events), "complete controller trace")
    radius, stagnant = 1, 0
    for index, (row, event) in enumerate(zip(trace, events, strict=True), 1):
        _require(type(row) is dict and set(row) == TRACE_FIELDS, "trace fields")
        children = event["end_call"] - event["start_call"] + 1
        before, after = event["record_before"], event["record_after"]
        success = after is not None and (before is None or after > before)
        current_threshold = _threshold(100, radius, 100 ** 3)
        if not event["complete"]:
            next_radius, next_stagnant, action = radius, stagnant, "PARTIAL_NO_UPDATE"
        elif success:
            next_radius, next_stagnant, action = 1, 0, "STRICT_SUCCESS_RESET"
        elif Decimal(stagnant + children) > current_threshold:
            next_radius, next_stagnant, action = min(radius + 1, 50), 0, "STAGNATION_INCREASE"
        else:
            next_radius, next_stagnant, action = radius, stagnant + children, "NO_CHANGE"
        expected = {"generation": index, "start_call": event["start_call"],
                    "end_call": event["end_call"], "complete": event["complete"],
                    "children": children, "strict_success": success,
                    "record_before": before, "record_after": after,
                    "r_before": radius, "u_before": stagnant,
                    "r_after": next_radius, "u_after": next_stagnant, "event": action}
        for name, value in expected.items():
            _same(row[name], value, "trace " + str(index) + " " + name)
        _close(row["p_m"], Decimal(radius) / 100, "mutation before")
        _close(row["p_m_next"], Decimal(next_radius) / 100, "mutation after")
        _close(row["threshold"], current_threshold, "independent event threshold")
        _require(radius == next_radius == 1, "derived view cannot represent active SD")
        _close(event["p_m"], Decimal(radius) / 100, "shared operator probability")
        radius, stagnant = next_radius, next_stagnant

    expected_accounting = {"logical_profile_search_evaluations": budget,
        "additional_physical_search_evaluations": 0,
        "shared_source_physical_search_evaluations": budget,
        "new_independent_search_runs": 0}
    _same(view["accounting"], expected_accounting, "physical/logical accounting")
    expected_checks = {"source_operator_replay_score_checks": budget + 30,
                       "controller_events": len(events)}
    _same(view["construction_verification"], expected_checks, "construction checks")
    return {"verification_status": "VERIFIED", "source_journal_sha256": _digest(fixed_log),
            "requested_profile": "paper_sd_mutation", "status": "BOUNDED_EQUIVALENCE",
            "logical_profile_search_evaluations": budget,
            "additional_physical_search_evaluations": 0,
            "independent_source_score_checks": replay["independent_score_checks"],
            "independent_controller_events": len(events),
            "decimal_precision": 80, "threshold_r1": str(threshold),
            "final_radius": radius, "final_stagnation": stagnant}
