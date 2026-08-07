"""Strict canonical JSON helpers for deterministic validation objects."""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from typing import Any


class StrictJSONError(ValueError):
    """Raised for duplicate keys, non-finite constants, or malformed JSON."""


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise StrictJSONError(f"duplicate JSON object key: {key}")
        result[key] = value
    return result


def _reject_constant(value: str) -> Any:
    raise StrictJSONError(f"non-finite JSON constant is forbidden: {value}")


def _finite_float(value: str) -> float:
    parsed = float(value)
    if not math.isfinite(parsed):
        raise StrictJSONError(f"JSON number overflows the finite float range: {value}")
    return parsed


def strict_json_loads(payload: str) -> Any:
    """Parse JSON while rejecting duplicate keys and every non-finite number."""

    try:
        return json.loads(
            payload,
            object_pairs_hook=_unique_object,
            parse_constant=_reject_constant,
            parse_float=_finite_float,
        )
    except json.JSONDecodeError as error:
        raise StrictJSONError(str(error)) from error


def strict_json_load(path: Path) -> Any:
    return strict_json_loads(path.read_text(encoding="utf-8"))


def canonical_value(value: Any) -> Any:
    if value is None or isinstance(value, (bool, str, int)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("canonical payload contains NaN or Inf")
        return value
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        result: dict[str, Any] = {}
        for key, child in value.items():
            if not isinstance(key, str):
                raise TypeError("canonical dictionary keys must be strings")
            result[key] = canonical_value(child)
        return result
    if isinstance(value, (list, tuple)):
        return [canonical_value(child) for child in value]
    raise TypeError(f"unsupported canonical type: {type(value).__name__}")


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        canonical_value(value),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def sha256_value(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()
