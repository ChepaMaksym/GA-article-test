"""Authenticate a clean, non-vendored upstream checkout and its members."""

from __future__ import annotations

import hashlib
import os
import stat
import subprocess
from pathlib import Path, PurePosixPath
from typing import Any, Iterable, Mapping


class SourceIdentityError(ValueError):
    """Raised when Git or a required upstream member differs from the contract."""


def _git(checkout: Path, *args: str) -> str:
    process = subprocess.run(
        ["git", "-C", os.fspath(checkout), *args],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="strict",
        env={**os.environ, "LC_ALL": "C", "GIT_OPTIONAL_LOCKS": "0"},
    )
    if process.returncode:
        detail = process.stderr.strip() or process.stdout.strip()
        raise SourceIdentityError(f"git {' '.join(args)} failed: {detail}")
    return process.stdout.strip()


def _safe_member(checkout: Path, relative: str) -> Path:
    pure = PurePosixPath(relative)
    if pure.is_absolute() or not pure.parts or any(part in ("", ".", "..") for part in pure.parts):
        raise SourceIdentityError(f"unsafe source-member path: {relative!r}")
    path = checkout.joinpath(*pure.parts)
    try:
        resolved = path.resolve(strict=True)
    except OSError as error:
        raise SourceIdentityError(f"required source member is missing: {relative}") from error
    try:
        resolved.relative_to(checkout)
    except ValueError as error:
        raise SourceIdentityError(f"source member escapes checkout: {relative}") from error
    mode = path.lstat().st_mode
    if stat.S_ISLNK(mode) or not stat.S_ISREG(mode):
        raise SourceIdentityError(f"source member is not a regular file: {relative}")
    return resolved


def verify_member(checkout: Path, member: Mapping[str, Any]) -> dict[str, Any]:
    relative = member["path"]
    path = _safe_member(checkout, relative)
    payload = path.read_bytes()
    observed = {
        "path": relative,
        "bytes": len(payload),
        "sha256": hashlib.sha256(payload).hexdigest(),
        "git_blob": _git(checkout, "rev-parse", f"HEAD:{relative}"),
    }
    for field in ("bytes", "sha256", "git_blob"):
        if observed[field] != member[field]:
            raise SourceIdentityError(
                f"{relative} {field} differs: {observed[field]!r} != {member[field]!r}"
            )
    return observed


def _required_members(contract: Mapping[str, Any]) -> Iterable[Mapping[str, Any]]:
    upstream = contract["upstream"]
    yield {
        "path": upstream["license_path"],
        "bytes": upstream["license_bytes"],
        "sha256": upstream["license_sha256"],
        "git_blob": upstream["license_git_blob"],
    }
    yield contract["raw_member"]
    yield from contract["required_members"]


def authenticate_checkout(checkout: Path, contract: Mapping[str, Any]) -> dict[str, Any]:
    """Return a member manifest only for the exact clean commit and tree."""

    try:
        root = checkout.expanduser().resolve(strict=True)
    except OSError as error:
        raise SourceIdentityError(f"checkout does not exist: {checkout}") from error
    if not root.is_dir():
        raise SourceIdentityError("checkout is not a directory")
    observed_commit = _git(root, "rev-parse", "HEAD^{commit}")
    observed_tree = _git(root, "rev-parse", "HEAD^{tree}")
    expected = contract["upstream"]
    if observed_commit != expected["commit"]:
        raise SourceIdentityError(
            f"upstream commit differs: {observed_commit} != {expected['commit']}"
        )
    if observed_tree != expected["tree"]:
        raise SourceIdentityError(
            f"upstream tree differs: {observed_tree} != {expected['tree']}"
        )
    status_text = _git(root, "status", "--porcelain=v1", "--untracked-files=all")
    if status_text:
        raise SourceIdentityError(f"upstream checkout is dirty: {status_text}")
    members = [verify_member(root, member) for member in _required_members(contract)]
    origin = _git(root, "remote", "get-url", "origin")
    return {
        "checkout": os.fspath(root),
        "commit": observed_commit,
        "tree": observed_tree,
        "origin": origin,
        "clean": True,
        "member_count": len(members),
        "members": members,
    }


def assert_same_identity(before: Mapping[str, Any], after: Mapping[str, Any]) -> None:
    """Fail if source identity changed while it was being consumed."""

    fields = ("checkout", "commit", "tree", "clean", "members")
    for field in fields:
        if before.get(field) != after.get(field):
            raise SourceIdentityError(f"upstream identity changed during use: {field}")
