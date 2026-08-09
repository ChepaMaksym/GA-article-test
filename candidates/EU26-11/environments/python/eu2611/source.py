"""Authenticate the exact ModularCMAES source used for eligibility evidence."""

from __future__ import annotations

import hashlib
import subprocess
from pathlib import Path
from typing import Mapping


class SourceIdentityError(ValueError):
    """Raised when the source checkout differs from the frozen tag."""


def _git(checkout: Path, *arguments: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(checkout), *arguments],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    if result.returncode != 0:
        raise SourceIdentityError(
            f"git {' '.join(arguments)} failed: {result.stderr.strip()}"
        )
    return result.stdout.strip()


def _member_identity(path: Path, expected: Mapping[str, object]) -> dict[str, object]:
    if path.is_symlink() or not path.is_file():
        raise SourceIdentityError(f"required source member is not a regular file: {path}")
    payload = path.read_bytes()
    observed_sha256 = hashlib.sha256(payload).hexdigest()
    if len(payload) != expected["bytes"]:
        raise SourceIdentityError(f"source member byte-size mismatch: {path}")
    if observed_sha256 != expected["sha256"]:
        raise SourceIdentityError(f"source member SHA-256 mismatch: {path}")
    return {"bytes": len(payload), "sha256": observed_sha256}


def _require_ordered_markers(text: str, markers: tuple[str, ...], *, member: str) -> None:
    cursor = -1
    for marker in markers:
        position = text.find(marker, cursor + 1)
        if position < 0:
            raise SourceIdentityError(f"{member} lacks frozen marker: {marker}")
        if position <= cursor:
            raise SourceIdentityError(f"{member} adaptation markers are out of order")
        cursor = position


def verify_source_checkout(checkout: Path, contract: Mapping[str, object]) -> dict[str, object]:
    """Verify Git identity, licensing, and within-generation adaptation calls."""

    if checkout.is_symlink():
        raise SourceIdentityError("source checkout must not be a symbolic link")
    checkout = checkout.resolve()
    if not checkout.is_dir():
        raise SourceIdentityError("source checkout is not a regular directory")
    observed_commit = _git(checkout, "rev-parse", "HEAD^{commit}")
    observed_tree = _git(checkout, "rev-parse", "HEAD^{tree}")
    if observed_commit != contract["commit"]:
        raise SourceIdentityError("source commit differs from the frozen commit")
    if observed_tree != contract["tree"]:
        raise SourceIdentityError("source tree differs from the frozen tree")
    if _git(checkout, "status", "--porcelain=v1", "--untracked-files=all"):
        raise SourceIdentityError("source checkout is dirty")
    tags = set(_git(checkout, "tag", "--points-at", "HEAD").splitlines())
    if contract["tag"] not in tags:
        raise SourceIdentityError("frozen source tag does not point at HEAD")

    member_results: dict[str, object] = {}
    for relative, expected in contract["members"].items():
        member_results[relative] = _member_identity(checkout / relative, expected)

    main_text = (checkout / "modcma" / "modularcmaes.py").read_text(encoding="utf-8")
    parameters_text = (checkout / "modcma" / "parameters.py").read_text(
        encoding="utf-8"
    )
    _require_ordered_markers(
        main_text,
        ("self.mutate()", "self.select()", "self.recombine()", "self.adapt()"),
        member="modcma/modularcmaes.py",
    )
    _require_ordered_markers(
        parameters_text,
        (
            "self.adapt_evolution_paths()",
            "self.adapt_sigma()",
            "self.adapt_covariance_matrix()",
            "self.perform_eigendecomposition()",
        ),
        member="modcma/parameters.py",
    )
    required_formula_markers = (
        "self.sigma *= np.exp(",
        "rank_one = self.c1 * self.pc * self.pc.T",
        "self.C = old_C + rank_one + rank_mu",
        "self.dm = (self.m - self.m_old) / self.sigma",
    )
    for marker in required_formula_markers:
        if marker not in parameters_text:
            raise SourceIdentityError(f"parameters source lacks formula marker: {marker}")

    return {
        "status": "PASS_SOURCE_ADAPTATION_GATE",
        "commit": observed_commit,
        "tree": observed_tree,
        "tag": contract["tag"],
        "license": contract["license"],
        "members": member_results,
        "generation_order": ["mutate", "select", "recombine", "adapt"],
        "adaptation_order": [
            "evolution_paths",
            "step_size",
            "covariance_matrix",
            "eigendecomposition",
        ],
    }
