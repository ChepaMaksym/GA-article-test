"""Canonical report hashing and fail-closed output writes."""

from __future__ import annotations

import hashlib
import json
import os
import stat
from pathlib import Path
from typing import Any

from .errors import VerificationError


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("ascii")


def bind_report(report: dict[str, Any], *, domain: bytes) -> dict[str, Any]:
    if "report_digest" in report:
        raise VerificationError("report already has a digest")
    bound = dict(report)
    digest = hashlib.sha256(domain + b"\0" + canonical_bytes(bound)).hexdigest()
    bound["report_digest"] = f"sha256:{digest}"
    return bound


def write_new_json(path: Path, value: Any) -> None:
    """Atomically create a report without replacing any existing path."""
    path = Path(os.path.abspath(path))
    if path.exists() or path.is_symlink():
        raise VerificationError(f"refusing to overwrite {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(
        value,
        sort_keys=True,
        indent=2,
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8") + b"\n"
    flags = (
        os.O_WRONLY
        | os.O_CREAT
        | os.O_EXCL
        | getattr(os, "O_CLOEXEC", 0)
        | getattr(os, "O_NOFOLLOW", 0)
    )
    try:
        descriptor = os.open(path, flags, 0o644)
    except OSError as error:
        raise VerificationError(f"cannot create new output {path}: {error}") from error
    created = os.fstat(descriptor)
    if not stat.S_ISREG(created.st_mode):
        os.close(descriptor)
        raise VerificationError("new output descriptor is not regular")
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        observed = os.lstat(path)
        if (observed.st_dev, observed.st_ino) != (created.st_dev, created.st_ino):
            raise VerificationError("output path changed during creation")
    except BaseException:
        try:
            observed = os.lstat(path)
            if (observed.st_dev, observed.st_ino) == (created.st_dev, created.st_ino):
                path.unlink()
        except OSError:
            pass
        raise
