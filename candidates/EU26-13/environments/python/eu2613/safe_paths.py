"""Component-wise no-follow access for retained verifier inputs and outputs."""

from __future__ import annotations

import os
import stat
from pathlib import Path

from .errors import VerificationError


NOFOLLOW = getattr(os, "O_NOFOLLOW", None)
DIRECTORY = getattr(os, "O_DIRECTORY", None)
CLOEXEC = getattr(os, "O_CLOEXEC", 0)


def _parts(path: Path | str, stage: str) -> tuple[bool, list[str]]:
    raw = os.fspath(path)
    if not isinstance(raw, str) or not raw or "\x00" in raw:
        raise VerificationError(stage, "path must be a non-empty NUL-free string")
    if NOFOLLOW is None or DIRECTORY is None:
        raise VerificationError(stage, "platform lacks required no-follow directory support")
    absolute = raw.startswith("/")
    components = raw.split("/")
    if absolute:
        components = components[1:]
    if not components or any(part in ("", ".", "..") for part in components):
        raise VerificationError(stage, f"path contains an unsafe component: {raw!r}")
    return absolute, components


def _open_parent(
    path: Path | str,
    stage: str,
    *,
    create_parents: bool,
) -> tuple[int, str]:
    absolute, components = _parts(path, stage)
    directory_fd = os.open("/" if absolute else ".", os.O_RDONLY | DIRECTORY | CLOEXEC)
    try:
        for component in components[:-1]:
            try:
                child_fd = os.open(
                    component,
                    os.O_RDONLY | DIRECTORY | NOFOLLOW | CLOEXEC,
                    dir_fd=directory_fd,
                )
            except FileNotFoundError:
                if not create_parents:
                    raise
                os.mkdir(component, mode=0o755, dir_fd=directory_fd)
                child_fd = os.open(
                    component,
                    os.O_RDONLY | DIRECTORY | NOFOLLOW | CLOEXEC,
                    dir_fd=directory_fd,
                )
            os.close(directory_fd)
            directory_fd = child_fd
        return directory_fd, components[-1]
    except Exception:
        os.close(directory_fd)
        raise


def safe_read_bytes(
    path: Path | str,
    *,
    stage: str,
    maximum_bytes: int | None = None,
) -> bytes:
    """Read a regular file without following any supplied path component."""

    if maximum_bytes is not None and (type(maximum_bytes) is not int or maximum_bytes < 0):
        raise VerificationError(stage, "maximum_bytes must be a non-negative integer")
    try:
        directory_fd, name = _open_parent(path, stage, create_parents=False)
    except (OSError, VerificationError) as exc:
        if isinstance(exc, VerificationError):
            raise
        raise VerificationError(stage, f"cannot open input parent for {path}: {exc}") from exc
    file_fd: int | None = None
    try:
        before_open = os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
        if not stat.S_ISREG(before_open.st_mode):
            raise VerificationError(stage, f"input is not a regular file: {path}")
        file_fd = os.open(
            name,
            os.O_RDONLY | os.O_NONBLOCK | NOFOLLOW | CLOEXEC,
            dir_fd=directory_fd,
        )
        metadata = os.fstat(file_fd)
        if not stat.S_ISREG(metadata.st_mode):
            raise VerificationError(stage, f"input is not a regular file: {path}")
        if (before_open.st_dev, before_open.st_ino) != (metadata.st_dev, metadata.st_ino):
            raise VerificationError(stage, f"input leaf identity changed during open: {path}")
        if maximum_bytes is not None and metadata.st_size > maximum_bytes:
            raise VerificationError(stage, f"input exceeds {maximum_bytes} bytes: {path}")
        chunks: list[bytes] = []
        total = 0
        while True:
            limit = 1024 * 1024
            if maximum_bytes is not None:
                limit = min(limit, maximum_bytes - total + 1)
            chunk = os.read(file_fd, limit)
            if not chunk:
                break
            chunks.append(chunk)
            total += len(chunk)
            if maximum_bytes is not None and total > maximum_bytes:
                raise VerificationError(stage, f"input exceeds {maximum_bytes} bytes: {path}")
        return b"".join(chunks)
    except OSError as exc:
        raise VerificationError(stage, f"cannot read no-follow input {path}: {exc}") from exc
    finally:
        if file_fd is not None:
            os.close(file_fd)
        os.close(directory_fd)


def safe_write_text_once(path: Path | str, payload: str, *, stage: str) -> None:
    """Create a regular file once, refusing symlinks in every path component."""

    if not isinstance(payload, str):
        raise VerificationError(stage, "output payload must be text")
    try:
        directory_fd, name = _open_parent(path, stage, create_parents=True)
    except (OSError, VerificationError) as exc:
        if isinstance(exc, VerificationError):
            raise
        raise VerificationError(stage, f"cannot open output parent for {path}: {exc}") from exc
    file_fd: int | None = None
    created = False
    try:
        retained_parent = os.fstat(directory_fd)
        file_fd = os.open(
            name,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | NOFOLLOW | CLOEXEC,
            0o644,
            dir_fd=directory_fd,
        )
        created = True
        metadata = os.fstat(file_fd)
        if not stat.S_ISREG(metadata.st_mode):
            raise VerificationError(stage, f"output is not a regular file: {path}")
        data = payload.encode("utf-8")
        offset = 0
        while offset < len(data):
            written = os.write(file_fd, data[offset:])
            if written <= 0:
                raise VerificationError(stage, f"short output write: {path}")
            offset += written
        os.fsync(file_fd)
        current_parent_fd, current_name = _open_parent(
            path,
            stage,
            create_parents=False,
        )
        current_file_fd: int | None = None
        try:
            current_parent = os.fstat(current_parent_fd)
            if (current_parent.st_dev, current_parent.st_ino) != (
                retained_parent.st_dev,
                retained_parent.st_ino,
            ):
                raise VerificationError(stage, f"output parent identity changed: {path}")
            if current_name != name:
                raise VerificationError(stage, f"output leaf name changed: {path}")
            current_file_fd = os.open(
                current_name,
                os.O_RDONLY | os.O_NONBLOCK | NOFOLLOW | CLOEXEC,
                dir_fd=current_parent_fd,
            )
            retained_file = os.fstat(file_fd)
            current_file = os.fstat(current_file_fd)
            if not stat.S_ISREG(current_file.st_mode) or (
                current_file.st_dev,
                current_file.st_ino,
            ) != (retained_file.st_dev, retained_file.st_ino):
                raise VerificationError(stage, f"output leaf identity changed: {path}")
        finally:
            if current_file_fd is not None:
                os.close(current_file_fd)
            os.close(current_parent_fd)
        os.fsync(directory_fd)
    except FileExistsError as exc:
        raise VerificationError(stage, f"refusing to overwrite {path}") from exc
    except Exception as exc:
        if created:
            try:
                retained_file = os.fstat(file_fd) if file_fd is not None else None
                current_leaf = os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
                if retained_file is not None and (
                    current_leaf.st_dev,
                    current_leaf.st_ino,
                ) == (retained_file.st_dev, retained_file.st_ino):
                    os.unlink(name, dir_fd=directory_fd)
            except OSError:
                pass
        if isinstance(exc, VerificationError):
            raise
        raise VerificationError(stage, f"cannot write no-follow output {path}: {exc}") from exc
    finally:
        if file_fd is not None:
            os.close(file_fd)
        os.close(directory_fd)
