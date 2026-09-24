"""Select immutable per-seed attempt identities, never scientific outcomes."""
from __future__ import annotations

import re
from typing import Any, Mapping, Sequence


def select_seed_artifacts(
    available: Sequence[Mapping[str, Any]], *, run_id: int, run_attempt: int,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    pattern = re.compile(rf"eu26-21-common-bridge-seed-(410[0-9]{{2}})-{run_id}-([1-9][0-9]*)")
    grouped: dict[int, list[dict[str, Any]]] = {seed: [] for seed in range(41001, 41031)}
    for item in available:
        match = pattern.fullmatch(str(item.get("name", "")))
        if match is None:
            continue
        seed, attempt = map(int, match.groups())
        if seed not in grouped or attempt > run_attempt:
            raise ValueError("artifact has unexpected seed or future attempt")
        if item.get("expired") is not False:
            raise ValueError("campaign evidence artifact expired")
        if type(item.get("id")) is not int or item["id"] < 1:
            raise ValueError("artifact lacks a positive immutable ID")
        if re.fullmatch(r"sha256:[0-9a-f]{64}", str(item.get("digest"))) is None:
            raise ValueError("artifact lacks an immutable SHA-256 digest")
        grouped[seed].append({
            "seed": seed, "id": item["id"], "name": item["name"],
            "digest": item["digest"], "run_attempt": attempt,
        })
    selected: list[dict[str, Any]] = []
    history: list[dict[str, Any]] = []
    for seed, candidates in grouped.items():
        if not candidates:
            raise ValueError(f"source artifact missing for seed {seed}")
        candidates.sort(key=lambda item: item["run_attempt"])
        if len({item["run_attempt"] for item in candidates}) != len(candidates):
            raise ValueError(f"duplicate seed/attempt artifacts for seed {seed}")
        selected.append(candidates[-1])
        history.extend({**item, "selected": item is candidates[-1]} for item in candidates)
    if len({item["id"] for item in history}) != len(history):
        raise ValueError("source artifact IDs are not unique")
    return selected, history
