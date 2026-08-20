from __future__ import annotations

import json
import os
import platform
from concurrent.futures import ProcessPoolExecutor
from hashlib import sha256
from pathlib import Path
from statistics import median
from typing import Iterable

import numpy as np

from .core import make_uniform_instance
from .optimizer import RunResult, run_hybrid, run_old


def _pair_task(args: tuple[int, int, float, int, int, int, bool]) -> dict:
    seed, budget, target, n_nodes, salesmen, instance_seed, include_trace = args
    instance = make_uniform_instance(instance_seed, n_nodes, salesmen)
    old = run_old(instance, seed, budget, target)
    hybrid = run_hybrid(instance, seed, budget, target)
    if old.initial_population_digest != hybrid.initial_population_digest:
        raise RuntimeError("paired initial populations differ")
    row = {
        "seed": seed,
        "old": old.canonical(),
        "hybrid": hybrid.canonical(),
        "old_first_hit_nfe": old.first_hit_nfe,
        "hybrid_first_hit_nfe": hybrid.first_hit_nfe,
        "old_final": old.final_objective,
        "hybrid_final": hybrid.final_objective,
        "hybrid_minus_old": hybrid.final_objective - old.final_objective,
        "relative_nfe_reduction": (min(old.first_hit_nfe or budget, budget) - min(hybrid.first_hit_nfe or budget, budget)) / min(old.first_hit_nfe or budget, budget),
        "initial_population_digest": old.initial_population_digest,
        "old_generations": old.generations,
        "hybrid_generations": hybrid.generations,
        "hybrid_max_lambda": hybrid.lambda_max,
        "hybrid_resets": hybrid.reset_events,
    }
    if include_trace:
        row["lambda_trace"] = list(hybrid.lambda_trace)
    return row


def run_campaign(
    seeds: Iterable[int],
    budget: int = 1500,
    target: float = 1.830,
    workers: int = 1,
    instance_seed: int = 20240809,
    n_nodes: int = 50,
    salesmen: int = 10,
    include_trace: bool = False,
) -> list[dict]:
    args = [(int(s), int(budget), float(target), int(n_nodes), int(salesmen), int(instance_seed), bool(include_trace)) for s in seeds]
    if workers == 1:
        rows = [_pair_task(x) for x in args]
    else:
        with ProcessPoolExecutor(max_workers=workers) as pool:
            rows = list(pool.map(_pair_task, args))
    return sorted(rows, key=lambda r: r["seed"])


def percentile_bootstrap(values: list[float], *, seed: int = 20240809, resamples: int = 20000) -> tuple[float, float:
    data = np.asarray(values, dtype=np.float64)
    rng = np.random.default_rng(seed)
    stats = np.empty(resamples, dtype=np.float64)
    for i in range(resamples):
        sample = rng.choice(data, size=len(data), replace=True)
        stats[i] = np.median(sample)
    lo, hi = np.quantile(stats, [0.025, 0.975])
    return float(lo), float(hi)


def paired_summary(rows: list[dict], target: float, budget: int = 1500) -> dict:
    old_final = [float(r["old_final"]) for r in rows]
    hybrid_final = [float(r["hybrid_final"]) for r in rows]
    diffs = [float(r["hybrid_minus_old"]) for r in rows]
    reductions = [float(r["relative_nfe_reduction"]) for r in rows]
    old_capped = [min(int(r["old_first_hit_nfe"] or budget), budget) for r in rows]
    hybrid_capped = [min(int(r["hybrid_first_hit_nfe"] or budget), budget) for r in rows]
    old_cov = sum(r["old_first_hit_nfe"] is not None for r in rows)
    hybrid_cov = sum(r["hybrid_first_hit_nfe"] is not None for r in rows)
    better = sum(h < o for h, o in zip(hybrid_final, old_final))
    equal = sum(h == o for h, o in zip(hybrid_final, old_final))
    worse = len(rows) - better - equal
    fitness_ci = percentile_bootstrap(diffs, seed=9101)
    nfe_ci = percentile_bootstrap(reductions, seed=9102)
    quality_pass = fitness_ci[1] <= 0.01
    coverage_pass = hybrid_cov >= old_cov and hybrid_cov >= int(np.ceil(0.75 * len(rows)))
    efficiency_pass = nfe_ci[0] >= 0.20
    return {
        "pair_count": len(rows),
        "target": target,
        "budget": budget,
        "old_median_fitness": median(old_final),
        "hybrid_median_fitness": median(hybrid_final),
        "paired_median_hybrid_minus_old": median(diffs),
        "paired_fitness_difference_95pct_bootstrap": list(fitness_ci),
        "quality_noninferiority_margin_absolute": 0.01,
        "quality_noninferiority_pass": quality_pass,
        "old_target_coverage": old_cov,
        "hybrid_target_coverage": hybrid_cov,
        "coverage_pass": coverage_pass,
        "old_median_capped_nfe": median(old_capped),
        "hybrid_median_capped_nfe": median(hybrid_capped),
        "paired_median_nfe_reduction": median(reductions),
        "paired_nfe_reduction_95pct_bootstrap": list(nfe_ci),
        "efficiency_pass": efficiency_pass,
        "hybrid_better_equal_worse": [better, equal, worse],
        "joint_pass": quality_pass and coverage_pass and efficiency_pass,
    }


def scientific_digest(rows: list[dict]) -> str:
    canonical = []
    for r in rows:
        canonical.append({
            "seed": r["seed"],
            "old": r["old"],
            "hybrid": r["hybrid"],
            "old_first_hit_nfe": r["old_first_hit_nfe"],
            "hybrid_first_hit_nfe": r["hybrid_first_hit_nfe"],
            "old_final": round(r["old_final"], 15),
            "hybrid_final": round(r["hybrid_final"], 15),
            "relative_nfe_reduction": round(r["relative_nfe_reduction"], 15),
        })
    payload = json.dumps(canonical, sort_keys=True, separators=(",", ":"))
    return sha256(payload.encode()).hexdigest()


def environment_profile() -> dict:
    return {"python": platform.python_version(), "platform": platform.platform(), "cpu_count": os.cpu_count()}


def write_json(path: str | Path, obj) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj, indent=2, sort_keys=True), encoding="utf-8")
