"""Strict canonical JSON and digest helpers for EU26-01."""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from typing import Any


class StrictJSONError(ValueError):
    """Raised when JSON is malformed, ambiguous, or non-finite."""


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise StrictJSONError(f"duplicate JSON object key: {key}")
        result[key] = value
    return result


def _reject_constant(value: str) -> Any:
    raise StrictJSONError(f"non-finite JSON constant is forbidden: {value}")


def strict_json_loads(payload: str) -> Any:
    """Parse JSON while rejecting duplicate keys and NaN/Infinity tokens."""

    try:
        return json.loads(
            payload,
            object_pairs_hook=_unique_object,
            parse_constant=_reject_constant,
        )
    except json.JSONDecodeError as error:
        raise StrictJSONError(str(error)) from error


def strict_json_load(path: Path) -> Any:
    return strict_json_loads(path.read_text(encoding="utf-8"))


def canonical(value: Any) -> Any:
    """Return a strict JSON value and reject opaque or non-finite state."""

    if value is None or isinstance(value, (bool, str)):
        return value
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("canonical data cannot contain NaN or infinity")
        return value
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        result: dict[str, Any] = {}
        for key, child in value.items():
            if not isinstance(key, str):
                raise TypeError("canonical dictionary keys must be strings")
            result[key] = canonical(child)
        return result
    if isinstance(value, (list, tuple)):
        return [canonical(child) for child in value]
    raise TypeError(f"unsupported canonical type: {type(value).__name__}")


def canonical_bytes(value: Any, *, domain: str) -> bytes:
    if not isinstance(domain, str) or not domain:
        raise ValueError("canonical digest domain must be a non-empty string")
    payload = json.dumps(
        canonical(value),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")
    return domain.encode("ascii") + b"\x00" + payload


def canonical_sha256(value: Any, *, domain: str) -> str:
    return hashlib.sha256(canonical_bytes(value, domain=domain)).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()
