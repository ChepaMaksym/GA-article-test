from __future__ import annotations

import json
from concurrent.futures import ProcessPoolExecutor
from hashlib import sha256
from typing import Iterable

from .old import OldRunResult, run_two_rate_old


def _task(args: tuple[int, int, int, int]) -> OldRunResult:
    seed, n, offspring, budget = args
    return run_two_rate_old(
        seed,
        n=n,
        offspring=offspring,
        max_evaluations=budget,
        record_trace=False,
    )


def run_campaign(
    seeds: Iterable[int],
    *,
    workers: int = 1,
    n: int = 100,
    offspring: int = 10,
    max_evaluations: int = 2_000_000,
) -> list[OldRunResult]:
    seed_list = [int(seed) for seed in seeds]
    if not seed_list:
        raise ValueError("seed ledger must not be empty")
    if len(seed_list) != len(set(seed_list)):
        raise ValueError("seed ledger contains duplicates")
    if workers not in {1, 2, 4}:
        raise ValueError("workers must be one of 1, 2, 4")
    args = [(seed, n, offspring, max_evaluations) for seed in seed_list]
    if workers == 1:
        results = [_task(arg) for arg in args]
    else:
        with ProcessPoolExecutor(max_workers=workers) as pool:
            results = list(pool.map(_task, args))
    return sorted(results, key=lambda result: result.seed)


def campaign_digest(results: list[OldRunResult]) -> str:
    if not results:
        raise ValueError("results must not be empty")
    payload = json.dumps(
        [result.canonical() for result in sorted(results, key=lambda item: item.seed)],
        sort_keys=True,
        separators=(",", ":"),
    )
    return sha256(payload.encode("utf-8")).hexdigest()
