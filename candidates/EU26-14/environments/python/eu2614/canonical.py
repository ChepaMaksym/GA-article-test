"""Canonical report hashing and fail-closed output writes."""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import stat
from pathlib import Path
from typing import Any

from .errors import VerificationError
from .hashing import open_parent_nofollow


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


def verify_report_digest(report: dict[str, Any], *, domain: bytes) -> None:
    """Recompute a domain-separated report digest and reject all drift."""
    digest = report.get("report_digest")
    if (
        type(digest) is not str
        or len(digest) != 71
        or not digest.startswith("sha256:")
        or any(character not in "0123456789abcdef" for character in digest[7:])
    ):
        raise VerificationError("report digest format differs")
    unbound = dict(report)
    del unbound["report_digest"]
    expected = bind_report(unbound, domain=domain)["report_digest"]
    if not hmac.compare_digest(digest, expected):
        raise VerificationError("report digest differs")


def write_new_json(path: Path, value: Any) -> None:
    """Atomically create a report without replacing any existing path."""
    path = Path(os.path.abspath(path))
    if path.exists() or path.is_symlink():
        raise VerificationError(f"refusing to overwrite {path}")
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
    with open_parent_nofollow(path, label="output path", create=True) as (
        absolute,
        parent_fd,
        leaf,
    ):
        try:
            descriptor = os.open(leaf, flags, 0o644, dir_fd=parent_fd)
        except OSError as error:
            raise VerificationError(f"cannot create new output {path}: {error}") from error
        created: os.stat_result | None = None
        open_descriptor = descriptor
        try:
            created = os.fstat(descriptor)
            if not stat.S_ISREG(created.st_mode):
                raise VerificationError("new output descriptor is not regular")
            with os.fdopen(descriptor, "wb") as stream:
                open_descriptor = -1
                stream.write(payload)
                stream.flush()
                os.fsync(stream.fileno())
            observed = os.stat(leaf, dir_fd=parent_fd, follow_symlinks=False)
            if stat.S_ISLNK(observed.st_mode) or (
                observed.st_dev,
                observed.st_ino,
            ) != (created.st_dev, created.st_ino):
                raise VerificationError("output path changed during creation")
            with open_parent_nofollow(absolute, label="output path") as (
                _,
                resolved_parent_fd,
                resolved_leaf,
            ):
                retained_parent = os.fstat(parent_fd)
                resolved_parent = os.fstat(resolved_parent_fd)
                if (retained_parent.st_dev, retained_parent.st_ino) != (
                    resolved_parent.st_dev,
                    resolved_parent.st_ino,
                ):
                    raise VerificationError("output parent path changed during creation")
                resolved = os.stat(
                    resolved_leaf,
                    dir_fd=resolved_parent_fd,
                    follow_symlinks=False,
                )
                if stat.S_ISLNK(resolved.st_mode) or (
                    resolved.st_dev,
                    resolved.st_ino,
                ) != (created.st_dev, created.st_ino):
                    raise VerificationError("output path changed during creation")
        except BaseException:
            if open_descriptor >= 0:
                try:
                    os.close(open_descriptor)
                except OSError:
                    pass
            if created is not None:
                try:
                    observed = os.stat(leaf, dir_fd=parent_fd, follow_symlinks=False)
                    if (observed.st_dev, observed.st_ino) == (
                        created.st_dev,
                        created.st_ino,
                    ):
                        os.unlink(leaf, dir_fd=parent_fd)
                except OSError:
                    pass
            raise
