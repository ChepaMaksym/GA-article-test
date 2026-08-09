"""Shared tar path and type checks."""

from __future__ import annotations

import tarfile
from pathlib import PurePosixPath

from .errors import VerificationError


def validate_tar_member(member: tarfile.TarInfo, seen: set[str]) -> None:
    name = member.name
    if not isinstance(name, str) or not name or "\x00" in name or "\\" in name:
        raise VerificationError("tar member name is invalid")
    path = PurePosixPath(name)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        raise VerificationError(f"unsafe tar member path: {name!r}")
    if path.as_posix() != name:
        raise VerificationError(f"non-canonical tar member path: {name!r}")
    if name in seen:
        raise VerificationError(f"duplicate tar member: {name}")
    seen.add(name)
    if not (member.isfile() or member.isdir()):
        raise VerificationError(f"tar member type is not admitted: {name}")
    if member.size < 0:
        raise VerificationError(f"negative tar member size: {name}")
    if member.isdir() and member.size != 0:
        raise VerificationError(f"tar directory has a payload: {name}")
