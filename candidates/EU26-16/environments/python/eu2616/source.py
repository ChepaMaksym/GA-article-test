from __future__ import annotations

import hashlib
import os
import subprocess
from pathlib import Path
from typing import Any


class SourceIdentityError(ValueError):
    """Raised when a caller-supplied upstream checkout is not exact and clean."""


def _git(checkout: Path, *arguments: str) -> str:
    process = subprocess.run(
        ["git", "-C", os.fspath(checkout), *arguments],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
    )
    if process.returncode != 0:
        raise SourceIdentityError(process.stderr.strip() or "Git command failed")
    return process.stdout.strip()


def _resolve_member(checkout: Path, member_path: str) -> Path:
    root = checkout.resolve(strict=True)
    candidate = (root / member_path).resolve(strict=False)
    try:
        candidate.relative_to(root)
    except ValueError as error:
        raise SourceIdentityError(f"member escapes checkout: {member_path}") from error
    return candidate


def verify_member(checkout: Path, member: dict[str, Any]) -> dict[str, Any]:
    path_text = member["path"]
    path = _resolve_member(checkout, path_text)
    if not path.is_file():
        raise SourceIdentityError(f"required member is missing: {path_text}")
    payload = path.read_bytes()
    observed = {
        "path": path_text,
        "bytes": len(payload),
        "sha256": hashlib.sha256(payload).hexdigest(),
        "git_blob": _git(checkout, "rev-parse", f"HEAD:{path_text}"),
    }
    for key in ("bytes", "sha256", "git_blob"):
        if observed[key] != member[key]:
            raise SourceIdentityError(
                f"{path_text} {key} mismatch: expected {member[key]!r}, "
                f"observed {observed[key]!r}"
            )
    return observed


def authenticate_checkout(checkout: Path, contract: dict[str, Any]) -> dict[str, Any]:
    checkout = checkout.resolve(strict=True)
    if not (checkout / ".git").exists():
        raise SourceIdentityError("upstream path is not a Git checkout")
    upstream = contract["upstream"]
    commit = _git(checkout, "rev-parse", "HEAD")
    tree = _git(checkout, "rev-parse", "HEAD^{tree}")
    if commit != upstream["commit"]:
        raise SourceIdentityError(f"wrong upstream commit: {commit}")
    if tree != upstream["tree"]:
        raise SourceIdentityError(f"wrong upstream tree: {tree}")
    status = _git(checkout, "status", "--porcelain=v1", "--untracked-files=all")
    if status:
        raise SourceIdentityError("upstream checkout must be clean")
    tags = set(_git(checkout, "tag", "--points-at", "HEAD").splitlines())
    if upstream["tag"] not in tags:
        raise SourceIdentityError("v3.0 tag does not point at the checkout commit")
    members = [verify_member(checkout, member) for member in contract["required_members"]]
    return {
        "repository": upstream["repository"],
        "commit": commit,
        "tree": tree,
        "tag": upstream["tag"],
        "clean": True,
        "members": members,
    }


def assert_same_identity(before: dict[str, Any], after: dict[str, Any]) -> None:
    if before != after:
        raise SourceIdentityError("upstream identity changed during verification")


def probe_alg_source(checkout: Path, contract: dict[str, Any]) -> dict[str, Any]:
    path = _resolve_member(checkout, "src/g3pkemlc/Alg.java")
    source = path.read_text(encoding="utf-8")
    positions: list[int] = []
    cursor = 0
    for token in contract["source_tokens"]:
        position = source.find(token, cursor)
        if position < 0:
            raise SourceIdentityError(f"required Alg.java token missing or out of order: {token}")
        positions.append(position)
        cursor = position + len(token)
    transition_start = source.index("float step = (float)0.02;")
    transition_end = source.index("//Stop condition", transition_start)
    transition_slice = source[transition_start:transition_end]
    if "Math.min(" in transition_slice or "Math.max(" in transition_slice:
        raise SourceIdentityError("probability transition unexpectedly contains a clamp")
    return {
        "path": "src/g3pkemlc/Alg.java",
        "token_count": len(positions),
        "strictly_ordered": positions == sorted(positions) and len(set(positions)) == len(positions),
        "best_average_assignment_before_guard": positions[7] < positions[8],
        "probability_clamp_present": False,
        "stop_probe_after_probability_updates": positions[14] > positions[13],
    }
