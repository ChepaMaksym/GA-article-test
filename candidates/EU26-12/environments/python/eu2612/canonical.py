"""Canonical report binding and non-overwriting evidence writes."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any, Mapping


class ReportError(ValueError):
    """Raised when report construction violates the evidence contract."""


def canonical_bytes(value: Mapping[str, Any]) -> bytes:
    """Encode a mapping deterministically and reject non-finite JSON values."""

    try:
        return json.dumps(
            value,
            allow_nan=False,
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("ascii")
    except (TypeError, ValueError) as error:
        raise ReportError(f"report is not canonical JSON: {error}") from error


def bind_report(value: Mapping[str, Any], *, domain: bytes) -> dict[str, Any]:
    """Return a copy with a domain-separated SHA-256 report digest."""

    if not isinstance(domain, bytes) or not domain:
        raise ReportError("report domain must be non-empty bytes")
    if "report_digest" in value:
        raise ReportError("unbound report must not provide report_digest")
    report = dict(value)
    report["report_digest"] = hashlib.sha256(
        domain + b"\0" + canonical_bytes(report)
    ).hexdigest()
    return report


def write_new_json(path: Path, value: Mapping[str, Any]) -> None:
    """Atomically create one report without following or replacing a path."""

    requested = path.expanduser()
    if requested.exists() or requested.is_symlink():
        raise FileExistsError(f"report path already exists: {requested}")
    target = requested.absolute()
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=True,
        indent=2,
        sort_keys=True,
    ).encode("ascii") + b"\n"
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
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
