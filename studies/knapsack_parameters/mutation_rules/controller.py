"""Pure mutation-strength rule from the pinned Rajabi--Witt author version.

The source is Algorithm 8 in chapter 3 of the lawful DTU thesis (PDF page 48).
Its journal-version threshold differs from the 2020 conference threshold.  These
functions do not implement the author's (1+1) EA, acceptance rule, or theorem.

``transition`` is our registered generation-boundary transfer: the mutation
probability stays constant while a generation's offspring are evaluated; only a
completed generation advances the failure counter.  A strict feasible record
resets the counter and strength at that boundary.  A terminal partial generation
never changes controller state, even if one of its candidates improves the record.
There is no RNG, objective evaluator, population operation, or oracle interface.
"""

from __future__ import annotations

import math


def _require(condition, message):
    if not condition:
        raise ValueError(message)


def _dimension(n):
    _require(type(n) is int and n >= 2, "n must be an exact integer >= 2")
    try:
        dimension = float(n)
    except (OverflowError, ValueError) as exc:
        raise ValueError("n cannot be represented by finite controller arithmetic") from exc
    _require(math.isfinite(dimension), "n must have a finite numerical representation")
    return dimension


def _number(value, name):
    _require(type(value) in (int, float), name + " must be a finite number, not a Boolean")
    try:
        number = float(value)
    except (OverflowError, ValueError) as exc:
        raise ValueError(name + " cannot be represented by finite controller arithmetic") from exc
    _require(math.isfinite(number), name + " must be finite")
    return number


def _strength(n, r):
    dimension = _dimension(n)
    strength = _number(r, "r")
    _require(1 <= strength <= dimension / 2, "r must be in [1, n/2]")
    return dimension, strength


def threshold(n, r, R=None):
    """Return T(r) with R=n**3 by default, rejecting non-finite results.

    The computation uses log(T) rather than constructing the two potentially
    huge powers.  R=n**3 uses an exact integer cube inside its logarithm, never a
    floating-point cube.  No rounding of T is performed: the
    source comparison is strictly ``u > T``.  Integer r is the usual trajectory;
    a real r is accepted to retain the source's n/2 cap for odd dimensions.
    """
    dimension, strength = _strength(n, r)
    log_n = math.log(dimension)
    if R is None:
        # Match an explicitly supplied n**3, including its floating rounding.
        # math.log also accepts integer arguments beyond the float range.
        log_R = math.log(n ** 3)
    else:
        failure_parameter = _number(R, "R")
        _require(failure_parameter >= 1, "R must be >= 1")
        log_R = math.log(failure_parameter)
    # log ln(e*n*R) is well-defined because n>=2 and R>=1.  log1p
    # avoids cancellation in ln(n/(n-r)) when r is small relative to n.
    log_threshold = (
        strength * (log_n - math.log(strength))
        - (dimension - strength) * math.log1p(-strength / dimension)
        + math.log(1 + log_n + log_R)
    )
    try:
        result = math.exp(log_threshold)
    except OverflowError as exc:
        raise ValueError("Source threshold is outside finite floating-point range") from exc
    _require(math.isfinite(result) and result > 0, "Source threshold must be positive and finite")
    return result


def initial_state(n):
    """Return an independent initial state; do not allocate random generators."""
    _dimension(n)
    return {"r": 1.0, "u": 0}


def transition(n, state, completed_evaluations, strict_success, complete=True, R=None):
    """Return a self-contained event without mutating the supplied state.

    A positive evaluation count is required for both complete and partial
    events.  Partial events expose their evaluated count but never add it to u.
    Strict success has priority over a threshold crossing; a tie is not success.
    """
    _require(type(state) is dict and set(state) == {"r", "u"},
             "Controller state must contain exactly r and u; extra metadata is forbidden")
    dimension, strength = _strength(n, state["r"])
    unsuccessful = state["u"]
    _require(type(unsuccessful) is int and unsuccessful >= 0,
             "u must be an exact nonnegative integer")
    _require(type(completed_evaluations) is int and completed_evaluations > 0,
             "completed_evaluations must be an exact positive integer")
    _require(type(strict_success) is bool and type(complete) is bool,
             "strict_success and complete must be Boolean flags")
    current_threshold = threshold(n, strength, R)
    before = {"r": strength, "u": unsuccessful}
    after = dict(before)

    if not complete:
        event = "PARTIAL_NO_UPDATE"
    elif strict_success:
        after = {"r": 1.0, "u": 0}
        event = "STRICT_SUCCESS_RESET"
    else:
        next_unsuccessful = unsuccessful + completed_evaluations
        if next_unsuccessful > current_threshold:
            next_strength = min(strength + 1, dimension / 2)
            after = {"r": next_strength, "u": 0}
            event = "STAGNATION_INCREASE" if next_strength > strength else "STAGNATION_CAPPED"
        else:
            after = {"r": strength, "u": next_unsuccessful}
            event = "NO_CHANGE"

    return {
        "before": before,
        "after": after,
        "p_before": strength / dimension,
        "p_after": after["r"] / dimension,
        "threshold": current_threshold,
        "event": event,
        "complete": complete,
        "completed_evaluations": completed_evaluations,
        "strict_success": strict_success,
    }
