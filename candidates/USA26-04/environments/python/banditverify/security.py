"""Strict input parsing and schema primitives for untrusted evidence files."""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any, Iterable


class EvidenceValidationError(ValueError):
    """Raised when an evidence artifact fails strict validation."""


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise EvidenceValidationError(f"duplicate JSON key: {key!r}")
        result[key] = value
    return result


def _reject_constant(value: str) -> None:
    raise EvidenceValidationError(f"non-standard JSON numeric constant: {value}")


def _bounded_int(value: str) -> int:
    if len(value.lstrip("-")) > 128:
        raise EvidenceValidationError("JSON integer exceeds the 128-digit evidence limit")
    return int(value)


def _bounded_float(value: str) -> float:
    if len(value) > 128:
        raise EvidenceValidationError("JSON float token exceeds the 128-character evidence limit")
    result = float(value)
    if not math.isfinite(result):
        raise EvidenceValidationError("JSON float must be finite")
    return result


def strict_json_load(path: Path, *, maximum_bytes: int = 16 * 1024 * 1024) -> Any:
    """Load bounded UTF-8 JSON while rejecting duplicates and NaN/Infinity."""

    try:
        size = path.stat().st_size
    except OSError as exc:
        raise EvidenceValidationError(f"cannot stat evidence file: {path}") from exc
    if size < 1 or size > maximum_bytes:
        raise EvidenceValidationError(
            f"evidence file size {size} is outside 1..{maximum_bytes} bytes"
        )
    try:
        text = path.read_text(encoding="utf-8", errors="strict")
        return json.loads(
            text,
            object_pairs_hook=_unique_object,
            parse_constant=_reject_constant,
            parse_int=_bounded_int,
            parse_float=_bounded_float,
        )
    except EvidenceValidationError:
        raise
    except (OSError, UnicodeError, ValueError, OverflowError) as exc:
        raise EvidenceValidationError(f"invalid strict JSON: {path}") from exc


def require_exact_keys(value: Any, expected: Iterable[str], context: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise EvidenceValidationError(f"{context} must be an object")
    expected_set = set(expected)
    actual_set = set(value)
    if actual_set != expected_set:
        missing = sorted(expected_set - actual_set)
        extra = sorted(actual_set - expected_set)
        raise EvidenceValidationError(
            f"{context} schema mismatch; missing={missing}, extra={extra}"
        )
    return value


def require_string(value: Any, context: str, *, nonempty: bool = True) -> str:
    if not isinstance(value, str) or (nonempty and not value):
        raise EvidenceValidationError(f"{context} must be a nonempty string")
    return value


def require_bool(value: Any, context: str) -> bool:
    if not isinstance(value, bool):
        raise EvidenceValidationError(f"{context} must be boolean")
    return value


def require_int(value: Any, context: str, *, minimum: int | None = None) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise EvidenceValidationError(f"{context} must be an integer")
    if minimum is not None and value < minimum:
        raise EvidenceValidationError(f"{context} must be >= {minimum}")
    return value
