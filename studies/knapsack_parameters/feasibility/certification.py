"""Independent integer witnesses and complete radius-two certificates.

Scientific callers and these fixtures run only in GitHub Actions. This module
does not import ascent evaluation or either dynamic-programming transition core.
"""

from __future__ import annotations

import csv
import hashlib
import io
import math
from numbers import Real
from pathlib import Path
import time

from .data_audit import Instance
from .solvers import PreparationDeadlineExceeded


SCHEMA = "knapsack-local-certificate-v1"
COLUMNS = ("neighbor_index", "distance", "flip_i", "flip_j", "weight", "profit",
           "feasible", "reason", "comparison")


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def _deadline(deadline: float | None) -> None:
    if deadline is None:
        return
    _require(not isinstance(deadline, bool) and isinstance(deadline, Real) and math.isfinite(deadline),
             "deadline must be a finite non-boolean monotonic timestamp")
    if time.monotonic() >= deadline:
        raise PreparationDeadlineExceeded("independent certification deadline exceeded")


def _check_instance(instance: Instance) -> None:
    _require(isinstance(instance, Instance), "instance must be an audited immutable Instance")
    _require(type(instance.n) is int and instance.n > 0, "invalid instance dimension")
    _require(type(instance.capacity) is int and instance.capacity > 0, "invalid capacity")
    _require(len(instance.profits) == len(instance.weights) == instance.n, "item count mismatch")
    _require(isinstance(instance.profits, tuple) and isinstance(instance.weights, tuple), "item arrays must be immutable tuples")
    _require(all(type(value) is int and value > 0 for value in (*instance.profits, *instance.weights)),
             "items must have positive exact integer weights and profits")


def evaluate_mask(instance: Instance, mask: str) -> dict:
    """Recompute original-row integer sums, never using a producer's score."""
    _check_instance(instance)
    _require(type(mask) is str and len(mask) == instance.n and set(mask) <= {"0", "1"},
             "mask must be a complete binary string in source item order")
    weight = 0
    profit = 0
    for position in range(instance.n):
        if mask[position] == "1":
            weight += instance.weights[position]
            profit += instance.profits[position]
    return {"mask": mask, "weight": weight, "profit": profit,
            "feasible": weight <= instance.capacity}


def validate_witness(instance: Instance, result: dict) -> dict:
    """Validate one exact solver's own reconstructed witness independently."""
    _require(isinstance(result, dict), "missing exact-method result")
    optimum = result.get("optimum_profit")
    _require(type(optimum) is int and optimum >= 0, "optimum must be a nonnegative exact integer")
    witness = evaluate_mask(instance, result.get("witness_mask"))
    _require(witness["feasible"], "exact witness exceeds capacity")
    _require(witness["profit"] == optimum, "witness does not attain the declared optimum")
    for name, value in (("witness_weight", witness["weight"]), ("witness_profit", witness["profit"])):
        _require(type(result.get(name)) is int and result[name] == value, f"incorrect {name}")
    return witness


def _flips(n: int):
    # This enumeration is independent of the producer's ascent neighborhood.
    for first in range(n):
        yield (first,)
    for first in range(n):
        for second in range(first + 1, n):
            yield (first, second)


def _row(instance: Instance, center: dict, flips: tuple[int, ...], index: int) -> dict:
    mask = list(center["mask"])
    for position in flips:
        mask[position] = "0" if mask[position] == "1" else "1"
    score = evaluate_mask(instance, "".join(mask))
    if not score["feasible"]:
        comparison, reason = "INVALID", "CAPACITY_EXCEEDED"
    else:
        comparison = ("BETTER" if score["profit"] > center["profit"] else
                      "EQUAL" if score["profit"] == center["profit"] else "WORSE")
        reason = "FEASIBLE"
    return {"neighbor_index": index, "distance": len(flips), "flips": list(flips),
            "weight": score["weight"], "profit": score["profit"],
            "feasible": score["feasible"], "reason": reason, "comparison": comparison}


def _summary(instance: Instance, center: dict, rows: list[dict]) -> dict:
    higher = sum(row["comparison"] == "BETTER" for row in rows)
    equal = sum(row["comparison"] == "EQUAL" for row in rows)
    lower = sum(row["comparison"] == "WORSE" for row in rows)
    valid = sum(row["feasible"] for row in rows)
    expected = instance.n + instance.n * (instance.n - 1) // 2
    complete = len(rows) == expected
    local = complete and center["feasible"] and higher == 0
    return {"schema_version": SCHEMA, "center": center, "n": instance.n,
            "expected_neighbor_count": expected, "neighbor_count": len(rows),
            "local_maximum": local, "strict": local and equal == 0,
            "plateau": local and equal > 0, "higher_feasible": higher,
            "equal_feasible": equal, "lower_feasible": lower,
            "valid_count": valid, "invalid_count": len(rows) - valid}


def certify_center(instance: Instance, center_mask: str, *, deadline: float | None = None) -> tuple[dict, list[dict]]:
    _deadline(deadline)
    center = evaluate_mask(instance, center_mask)
    _require(center["feasible"], "local certificate requires a feasible center")
    rows = []
    for index, flips in enumerate(_flips(instance.n), 1):
        _deadline(deadline)
        rows.append(_row(instance, center, flips, index))
    _deadline(deadline)
    return _summary(instance, center, rows), rows


def _csv_record(row: dict) -> dict:
    flips = row["flips"]
    return {"neighbor_index": str(row["neighbor_index"]), "distance": str(row["distance"]),
            "flip_i": str(flips[0]), "flip_j": str(flips[1]) if len(flips) == 2 else "",
            "weight": str(row["weight"]), "profit": str(row["profit"]),
            "feasible": "1" if row["feasible"] else "0", "reason": row["reason"],
            "comparison": row["comparison"]}


def write_certificate_csv(path: Path, rows: list[dict]) -> dict:
    """Retain reconstructible masks as center plus zero-based flipped indices."""
    path = Path(path)
    _require(not path.exists(), "existing certificate evidence must not be overwritten")
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=COLUMNS, lineterminator="\n")
    writer.writeheader()
    for row in rows:
        writer.writerow(_csv_record(row))
    raw = stream.getvalue().encode("utf-8")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(raw)
    return {"file": path.name, "sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw)}


def validate_certificate(instance: Instance, certificate: dict, path: Path, *, deadline: float | None = None) -> dict:
    """Read every retained row and independently recompute the entire proof."""
    _deadline(deadline)
    _require(isinstance(certificate, dict) and certificate.get("schema_version") == SCHEMA,
             "unknown certificate schema")
    _require(isinstance(certificate.get("center"), dict), "missing certificate center")
    center = evaluate_mask(instance, certificate.get("center", {}).get("mask"))
    _require(center["feasible"], "certificate center is not feasible")
    _require(certificate.get("center") == center, "certificate center score is inconsistent")
    for field in ("weight", "profit"):
        _require(type(certificate["center"].get(field)) is int, "center values must be exact integers")
    _require(type(certificate["center"].get("feasible")) is bool, "center feasibility must be boolean")
    for field in ("n", "expected_neighbor_count", "neighbor_count", "higher_feasible", "equal_feasible",
                  "lower_feasible", "valid_count", "invalid_count"):
        _require(type(certificate.get(field)) is int and certificate[field] >= 0, "certificate counters must be exact integers")
    for field in ("local_maximum", "strict", "plateau"):
        _require(type(certificate.get(field)) is bool, "locality fields must be boolean")
    rows = []
    with Path(path).open("r", encoding="utf-8", newline="") as source:
        reader = csv.DictReader(source)
        _require(tuple(reader.fieldnames or ()) == COLUMNS, "unexpected neighbor CSV schema")
        for index, flips in enumerate(_flips(instance.n), 1):
            _deadline(deadline)
            actual = next(reader, None)
            _require(actual is not None, "missing neighbor evidence")
            expected = _row(instance, center, flips, index)
            _require(actual == _csv_record(expected), f"incorrect, duplicate or out-of-order neighbor {index}")
            rows.append(expected)
        _require(next(reader, None) is None, "unexpected extra neighbor evidence")
    expected_summary = _summary(instance, center, rows)
    _require(certificate == expected_summary, "certificate summary differs from independently verified rows")
    _deadline(deadline)
    return expected_summary
