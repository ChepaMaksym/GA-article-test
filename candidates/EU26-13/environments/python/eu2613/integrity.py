"""Deterministic identity for the code exercised by retained attestations."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from .contract import CANDIDATE_ROOT
from .errors import VerificationError


PATTERNS = (
    "config/verification_contract.json",
    "fixtures/frozen_endpoint.json",
    "environments/python/**/*.py",
    "tests/run_python_tests.py",
    "tests/python/**/*.py",
    "tests/octave/**/*.m",
)


def implementation_manifest() -> dict[str, Any]:
    paths: set[Path] = set()
    for pattern in PATTERNS:
        paths.update(path for path in CANDIDATE_ROOT.glob(pattern) if path.is_file())
    if not paths:
        raise VerificationError("INTEGRITY", "implementation manifest is empty")
    records = []
    aggregate = hashlib.sha256()
    for path in sorted(paths, key=lambda item: item.relative_to(CANDIDATE_ROOT).as_posix()):
        if path.is_symlink():
            raise VerificationError("INTEGRITY", f"symlink is forbidden: {path}")
        relative = path.relative_to(CANDIDATE_ROOT).as_posix()
        payload = path.read_bytes()
        digest = hashlib.sha256(payload).hexdigest()
        records.append({"path": relative, "bytes": len(payload), "sha256": digest})
        aggregate.update(relative.encode("utf-8"))
        aggregate.update(b"\0")
        aggregate.update(str(len(payload)).encode("ascii"))
        aggregate.update(b"\0")
        aggregate.update(digest.encode("ascii"))
        aggregate.update(b"\n")
    return {
        "files": len(records),
        "sha256": aggregate.hexdigest(),
        "records": records,
    }
