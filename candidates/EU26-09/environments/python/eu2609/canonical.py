"""Canonical report hashing and fail-closed new-path writes."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any, Mapping


def canonical_bytes(value: Mapping[str, Any]) -> bytes:
    return json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("ascii")


def bind_report(value: Mapping[str, Any], *, domain: bytes) -> dict[str, Any]:
    report = dict(value)
    report["report_digest"] = hashlib.sha256(domain + b"\0" + canonical_bytes(report)).hexdigest()
    return report


def write_new_json(path: Path, value: Mapping[str, Any]) -> None:
    """Write one report to a caller-selected path without overwriting evidence."""

    target = path.expanduser().resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=True,
        indent=2,
        sort_keys=True,
    ).encode("ascii") + b"\n"
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    descriptor = os.open(target, flags, 0o600)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
    except BaseException:
        try:
            target.unlink()
        except FileNotFoundError:
            pass
        raise
