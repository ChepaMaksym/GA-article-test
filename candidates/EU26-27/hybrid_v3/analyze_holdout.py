from __future__ import annotations

import argparse
import csv
import json
import math
import random
import statistics
from pathlib import Path

DIMENSION = 100
BOOTSTRAP_SEED = 29029
BOOTSTRAP_SAMPLES = 50_000


def read_holdout(path: Path) -> list[int]:
    rows = list(csv.DictReader(path.read_text().splitlines()))
    seeds = [int(row["seed"]) for row in rows]
    if seeds != list(range(29001, 29031)):
        raise RuntimeError("v3 holdout must be exactly 29001..29030")
    retired = set(range(27001, 27031)) | set(range(28001, 28031))
    if set(seeds) & retired:
        raise RuntimeError("v3 holdout overlaps retired v1/v2 seeds")
    return seeds


def parse_single_endpoint(root: Path) -> int:
    dat_files = sorted(root.rglob("*.dat"))
    if len(dat_files) != 1:
        raise RuntimeError(f"expected one .dat below {root}, found {len(dat_files)}")
    expected = {(i, DIMENSION - i): i for i in range(DIMENSION + 1)}
    first_hit: dict[int, int] = {}
    active = False
    for raw in dat_files[0].read_text().splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith("evaluations"):
            if active:
                raise RuntimeError(f"multiple runs in {dat_files[0]}")
            active = True
            continue
        if not active:
            continue
        fields = line.split()
        if len(fields) < 3:
            continue
        try:
            evaluation = int(float(fields[0]))
            x = int(float(fields[1]))
            y = int(float(fields[2]))
        except ValueError:
            continue
        point = expected.get((x, y))
        if point is not None and point not in first_hit:
            first_hit[point] = evaluation
    if len(first_hit) != DIMENSION + 1:
        raise RuntimeError(f"incomplete Pareto front below {root}: {len(first_hit)}/101")
    return max(first_hit.values())


def percentile(values: list[float], q: float) -> float:
    ordered = sorted(values)
    pos = (len(ordered) - 1) * q
    lo, hi = math.floor(pos), math.ceil(pos)
    if lo == hi:
        return ordered[lo]
    weight = pos - lo
    return ordered[lo] * (1 - weight) + ordered[hi] * weight


def bootstrap_median_ci(values: list[float]) -> tuple[float, float]:
    rng = random.Random(BOOTSTRAP_SEED)
    n = len(values)
    medians = []
    for _ in range(BOOTSTRAP_SAMPLES):
        sample = [values[rng.randrange(n)] for _ in range(n)]
        medians.append(statistics.median(sample))
    return percentile(medians, 0.025), percentile(medians, 0.975)


def write_svg(path: Path, old: list[int], candidate: list[int], selected: int) -> None:
    width, height, margin = 900, 520, 70
    all_values = old + candidate
    ymax, ymin = max(all_values) * 1.05, min(all_values) * 0.95
    span = max(1.0, ymax - ymin)

    def xy(index: int, value: int) -> tuple[float, float]:
        x = margin + index / 29 * (width - 2 * margin)
        y = height - margin - (value - ymin) / span * (height - 2 * margin)
        return x, y

    old_points = " ".join(f"{x:.2f},{y:.2f}" for x, y in (xy(i, v) for i, v in enumerate(old)))
    new_points = " ".join(f"{x:.2f},{y:.2f}" for x, y in (xy(i, v) for i, v in enumerate(candidate)))
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">
<rect width="100%" height="100%" fill="white"/>
<text x="{width/2}" y="28" text-anchor="middle" font-family="sans-serif" font-size="19">EU26-27 v3 holdout: OLD vs HybridCap{selected}</text>
<line x1="{margin}" y1="{height-margin}" x2="{width-margin}" y2="{height-margin}" stroke="black"/>
<line x1="{margin}" y1="{margin}" x2="{margin}" y2="{height-margin}" stroke="black"/>
<polyline fill="none" stroke="black" stroke-width="1.8" points="{old_points}"/>
<polyline fill="none" stroke="black" stroke-width="1.8" stroke-dasharray="8,4" points="{new_points}"/>
<text x="{width-250}" y="45" font-family="sans-serif" font-size="14">OLD</text>
<text x="{width-250}" y="69" font-family="sans-serif" font-size="14">HybridCap{selected}</text>
<text x="{width/2}" y="{height-18}" text-anchor="middle" font-family="sans-serif" font-size="14">holdout seed index</text>
<text x="18" y="{height/2}" transform="rotate(-90 18 {height/2})" text-anchor="middle" font-family="sans-serif" font-size="14">function evaluations</text>
</svg>'''
    path.write_text(svg)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runs-root", required=True)
    parser.add_argument("--seeds", required=True)
    parser.add_argument("--selection", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    seeds = read_holdout(Path(args.seeds))
    selection = json.loads(Path(args.selection).read_text())
    selected = int(selection["selected_cap"])
    if selected not in (15, 20, 30, 40, 60, 100):
        raise RuntimeError(f"invalid selected cap {selected}")

    root = Path(args.runs_root)
    old = []
    candidate = []
    rows = []
    for run_index, seed in enumerate(seeds, start=1):
        o = parse_single_endpoint(root / "OLD" / f"seed-{seed}")
        c = parse_single_endpoint(root / "V3" / f"seed-{seed}")
        old.append(o)
        candidate.append(c)
        rows.append({"run": run_index, "seed": seed, "OLD": o, f"HybridCap{selected}": c})

    reductions = [(o - c) / o for o, c in zip(old, candidate)]
    median = statistics.median(reductions)
    ci = bootstrap_median_ci(reductions)
    status = "PASS" if ci[0] > 0 else "FAIL"

    report = {
        "schema": "eu26-27-hybrid-v3-confirmatory-v1",
        "selected_cap": selected,
        "selected_algorithm": f"HybridCap{selected}",
        "selection_source": "retired v2 development seeds 28001..28030",
        "holdout_seeds": seeds,
        "complete_runs": {"OLD": len(old), "V3": len(candidate)},
        "median_fe": {"OLD": statistics.median(old), "V3": statistics.median(candidate)},
        "mean_fe": {"OLD": statistics.fmean(old), "V3": statistics.fmean(candidate)},
        "H1": {
            "statistic": "paired median relative FE reduction OLD -> selected capped hybrid",
            "median": median,
            "ci95_percentile_bootstrap": list(ci),
            "bootstrap_samples": BOOTSTRAP_SAMPLES,
            "bootstrap_seed": BOOTSTRAP_SEED,
            "status": status,
        },
    }

    out = Path(args.output)
    out.mkdir(parents=True, exist_ok=True)
    (out / "report.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    with (out / "paired_endpoints.csv").open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    write_svg(out / "paired_fe.svg", old, candidate, selected)

    summary = f'''# EU26-27 HYBRID v3 confirmatory result

```text
selected cap: {selected}
OLD median FE: {statistics.median(old)}
V3 median FE: {statistics.median(candidate)}
H1 paired median relative FE reduction: {median:.6%}
H1 95% bootstrap CI: [{ci[0]:.6%}, {ci[1]:.6%}]
H1: {status}
```
'''
    (out / "summary.md").write_text(summary)
    print(summary)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
