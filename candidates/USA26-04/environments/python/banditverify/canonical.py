"""Strict canonical JSON and SHA-256 helpers for formula-only records."""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from typing import Any


HASH_DOMAIN = b"USA26-04-FORMULA-V1\0"


def _reject_nonfinite(value: Any) -> None:
    if isinstance(value, bool) or value is None or isinstance(value, (str, int)):
        return
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("canonical records cannot contain NaN or infinity")
        return
    if isinstance(value, list):
        for child in value:
            _reject_nonfinite(child)
        return
    if isinstance(value, dict):
        if any(not isinstance(key, str) for key in value):
            raise TypeError("canonical object keys must be strings")
        for child in value.values():
            _reject_nonfinite(child)
        return
    raise TypeError(f"unsupported canonical value type: {type(value).__name__}")


def canonical_json(value: Any) -> bytes:
    _reject_nonfinite(value)
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def formula_digest(records: list[dict[str, Any]]) -> str:
    ordered = sorted(records, key=lambda record: record["case_id"])
    digest = hashlib.sha256(HASH_DOMAIN)
    for record in ordered:
        payload = canonical_json(record)
        digest.update(len(payload).to_bytes(8, "little"))
        digest.update(payload)
    return digest.hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()
