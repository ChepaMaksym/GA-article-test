"""Shared access to the externally authenticated EU26-09 fixture."""

from __future__ import annotations

import os
from pathlib import Path

from eu2609.contract import load_contract


CONTRACT = load_contract()


def upstream() -> Path:
    value = os.environ.get("EU2609_UPSTREAM")
    if not value:
        raise RuntimeError("EU2609_UPSTREAM must name the authenticated checkout")
    return Path(value).expanduser().resolve(strict=True)


def raw_payload() -> bytes:
    return (upstream() / CONTRACT["raw_member"]["path"]).read_bytes()


def replace_once(payload: bytes, old: bytes, new: bytes) -> bytes:
    if payload.count(old) != 1:
        raise AssertionError(f"mutation needle count is {payload.count(old)}, expected one")
    return payload.replace(old, new, 1)
