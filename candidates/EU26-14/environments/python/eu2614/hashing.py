"""Streaming byte-identity gates bound to one retained descriptor."""

from __future__ import annotations

import hashlib
import os
import stat
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, BinaryIO, Iterator

from .errors import VerificationError


CHUNK_BYTES = 1024 * 1024


_DIRECTORY_FLAGS = (
    getattr(os, "O_PATH", os.O_RDONLY)
    | getattr(os, "O_DIRECTORY", 0)
    | getattr(os, "O_CLOEXEC", 0)
    | getattr(os, "O_NOFOLLOW", 0)
)


def hash_stream(stream: BinaryIO) -> dict[str, Any]:
    """Hash an already-open regular file from byte zero to EOF."""
    stream.seek(0)
    sha256 = hashlib.sha256()
    md5 = hashlib.md5(usedforsecurity=False)
    size = 0
    while chunk := stream.read(CHUNK_BYTES):
        size += len(chunk)
        sha256.update(chunk)
        md5.update(chunk)
    return {"bytes": size, "sha256": sha256.hexdigest(), "md5": md5.hexdigest()}


def _verify_identity(observed: dict[str, Any], expected: dict[str, Any], label: str) -> None:
    for field in ("bytes", "sha256", "md5"):
        if field in expected and observed[field] != expected[field]:
            raise VerificationError(f"{label} {field} differs")


def _fingerprint(metadata: os.stat_result) -> tuple[int, int, int, int, int, int]:
    return (
        metadata.st_dev,
        metadata.st_ino,
        metadata.st_mode,
        metadata.st_size,
        metadata.st_mtime_ns,
        metadata.st_ctime_ns,
    )


@dataclass
class VerifiedInput:
    path: Path
    stream: BinaryIO
    identity: dict[str, Any]
    device: int
    inode: int


@contextmanager
def open_parent_nofollow(
    path: Path, *, label: str, create: bool = False
) -> Iterator[tuple[Path, int, str]]:
    """Retain a parent directory FD after traversing without symlinks."""
    absolute = Path(os.path.abspath(path))
    leaf = absolute.name
    if not leaf:
        raise VerificationError(f"{label} path has no file name")
    descriptor: int | None = None
    try:
        descriptor = os.open(os.sep, _DIRECTORY_FLAGS)
        for component in absolute.parent.parts[1:]:
            try:
                child = os.open(component, _DIRECTORY_FLAGS, dir_fd=descriptor)
            except FileNotFoundError:
                if not create:
                    raise
                try:
                    os.mkdir(component, 0o777, dir_fd=descriptor)
                except FileExistsError:
                    pass
                child = os.open(component, _DIRECTORY_FLAGS, dir_fd=descriptor)
            os.close(descriptor)
            descriptor = child
    except (OSError, ValueError) as error:
        if descriptor is not None:
            os.close(descriptor)
        raise VerificationError(
            f"cannot securely traverse parent of {label}: {error}"
        ) from error
    try:
        yield absolute, descriptor, leaf
    finally:
        os.close(descriptor)


@contextmanager
def open_verified(
    path: Path, expected: dict[str, Any], *, label: str
) -> Iterator[VerifiedInput]:
    """Open, hash, consume, and re-hash one immutable descriptor.

    Path replacement can neither change the bytes parsed from the retained
    descriptor nor silently pass: the final path identity must still name the
    same inode.
    """
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    with open_parent_nofollow(path, label=label) as (absolute, parent_fd, leaf):
        try:
            before_path = os.stat(leaf, dir_fd=parent_fd, follow_symlinks=False)
        except OSError as error:
            raise VerificationError(f"cannot lstat {label}: {error}") from error
        if stat.S_ISLNK(before_path.st_mode) or not stat.S_ISREG(before_path.st_mode):
            raise VerificationError(f"{label} must be a regular non-symlink file")
        try:
            descriptor = os.open(leaf, flags, dir_fd=parent_fd)
        except OSError as error:
            raise VerificationError(f"cannot securely open {label}: {error}") from error
        try:
            stream = os.fdopen(descriptor, "rb", closefd=True)
        except BaseException:
            os.close(descriptor)
            raise
        try:
            before_fd = os.fstat(stream.fileno())
            if not stat.S_ISREG(before_fd.st_mode):
                raise VerificationError(f"{label} descriptor is not regular")
            if (before_path.st_dev, before_path.st_ino) != (
                before_fd.st_dev,
                before_fd.st_ino,
            ):
                raise VerificationError(f"{label} changed between lstat and open")
            initial_fingerprint = _fingerprint(before_fd)
            identity = hash_stream(stream)
            _verify_identity(identity, expected, label)
            stream.seek(0)
            verified = VerifiedInput(
                path=absolute,
                stream=stream,
                identity=identity,
                device=before_fd.st_dev,
                inode=before_fd.st_ino,
            )
            try:
                yield verified
            finally:
                after_consume = os.fstat(stream.fileno())
                if _fingerprint(after_consume) != initial_fingerprint:
                    raise VerificationError(f"{label} metadata changed during verification")
                final_identity = hash_stream(stream)
                if final_identity != identity:
                    raise VerificationError(f"{label} bytes changed during verification")
                after_hash = os.fstat(stream.fileno())
                if _fingerprint(after_hash) != initial_fingerprint:
                    raise VerificationError(f"{label} metadata changed during post-hash")
                try:
                    after_path = os.stat(leaf, dir_fd=parent_fd, follow_symlinks=False)
                except OSError as error:
                    raise VerificationError(
                        f"{label} path vanished during verification"
                    ) from error
                if stat.S_ISLNK(after_path.st_mode) or (
                    after_path.st_dev,
                    after_path.st_ino,
                ) != (before_fd.st_dev, before_fd.st_ino):
                    raise VerificationError(f"{label} path was replaced during verification")
                with open_parent_nofollow(absolute, label=label) as (
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
                        raise VerificationError(
                            f"{label} parent path was replaced during verification"
                        )
                    resolved_path = os.stat(
                        resolved_leaf,
                        dir_fd=resolved_parent_fd,
                        follow_symlinks=False,
                    )
                    if stat.S_ISLNK(resolved_path.st_mode) or (
                        resolved_path.st_dev,
                        resolved_path.st_ino,
                    ) != (before_fd.st_dev, before_fd.st_ino):
                        raise VerificationError(
                            f"{label} path was replaced during verification"
                        )
        except VerificationError:
            raise
        except OSError as error:
            raise VerificationError(f"I/O failure while verifying {label}: {error}") from error
        finally:
            stream.close()


def git_blob_sha1(payload: bytes) -> str:
    header = b"blob " + str(len(payload)).encode("ascii") + b"\0"
    return hashlib.sha1(header + payload, usedforsecurity=False).hexdigest()
