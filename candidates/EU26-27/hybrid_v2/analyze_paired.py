from __future__ import annotations

import argparse
import csv
import json
import math
import random
import statistics
from pathlib import Path

DIMENSION = 100
BOOTSTRAP_SEED = 28028
BOOTSTRAP_SAMPLES = 50_000
PROFILES = ("OLD", "HYBRID_ROLLBACK", "HYBRID_FLOOR")


def read_seeds(path: Path) -> list[int]:
    rows = list(csv.DictReader(path.read_text().splitlines()))
    seeds = [int(row["seed"]) for row in rows]
    if len(seeds) != 30 or len(set(seeds)) != 30:
        raise RuntimeError("seed ledger must contain 30 unique seeds")
    if set(seeds) & set(range(27001, 27031)):
        raise RuntimeError("v2 holdout overlaps retired v1 confirmatory seeds")
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


def parse_controller_trace(root: Path, marker: str) -> dict[str, float | int | None]:
    stdout = root / "stdout.txt"
    if not stdout.exists():
        return {"updates": 0, "min_lambda": None, "max_lambda": None, "median_lambda": None, "rollbacks": 0}
    values: list[float] = []
    rollbacks = 0
    previous_bad = None
    previous_delta = None
    for raw in stdout.read_text(errors="replace").splitlines():
        if not raw.startswith(marker + " "):
            continue
        fields = raw.split()
        if marker == "HYBRID_V2_ROLLBACK" and len(fields) >= 7:
            value = float(fields[1])
            bad = int(fields[5])
            delta = int(fields[6])
            if previous_bad is not None and previous_bad > 0 and bad == 0 and previous_delta is not None and delta == previous_delta + 1:
                rollbacks += 1
            previous_bad, previous_delta = bad, delta
        elif marker == "HYBRID_V2_FLOOR" and len(fields) >= 4:
            value = float(fields[1])
        else:
            continue
        values.append(value)
    return {
        "updates": len(values),
        "min_lambda": min(values) if values else None,
        "max_lambda": max(values) if values else None,
        "median_lambda": statistics.median(values) if values else None,
        "rollbacks": rollbacks,
    }


def percentile(values: list[float], q: float) -> float:
    ordered = sorted(values)
    pos = (len(ordered) - 1) * q
    lo, hi = math.floor(pos), math.ceil(pos)
    if lo == hi:
        return ordered[lo]
    weight = pos - lo
    return ordered[lo] * (1 - weight) + ordered[hi] * weight


def paired_relative_reductions(old: list[int], candidate: list[int]) -> list[float]:
    if len(old) != len(candidate):
        raise ValueError("paired vectors differ in length")
    return [(o - c) / o for o, c in zip(old, candidate)]


def bootstrap_median_ci(values: list[float]) -> tuple[float, float]:
    rng = random.Random(BOOTSTRAP_SEED)
    n = len(values)
    medians: list[float] = []
    for _ in range(BOOTSTRAP_SAMPLES):
        sample = [values[rng.randrange(n)] for _ in range(n)]
        medians.append(statistics.median(sample))
    return percentile(medians, 0.025), percentile(medians, 0.975)


def write_svg(path: Path, endpoints: dict[str, list[int]]) -> None:
    width, height, margin = 900, 520, 70
    all_values = sum(endpoints.values(), [])
    ymax, ymin = max(all_values) * 1.05, min(all_values) * 0.95
    span = max(1.0, ymax - ymin)

    def xy(index: int, value: int) -> tuple[float, float]:
        x = margin + index / 29 * (width - 2 * margin)
        y = height - margin - (value - ymin) / span * (height - 2 * margin)
        return x, y

    dash = ["", " stroke-dasharray=\"8,4\"", " stroke-dasharray=\"2,5\""]
    lines = []
    labels = []
    for idx, profile in enumerate(PROFILES):
        points = " ".join(f"{x:.2f},{y:.2f}" for x, y in (xy(i, v) for i, v in enumerate(endpoints[profile])))
        lines.append(f'<polyline fill="none" stroke="black" stroke-width="1.8"{dash[idx]} points="{points}"/>')
        labels.append(f'<text x="{width-280}" y="{45 + idx*24}" font-family="sans-serif" font-size="14">{profile}</text>')
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">
<rect width="100%" height="100%" fill="white"/>
<text x="{width/2}" y="28" text-anchor="middle" font-family="sans-serif" font-size="19">EU26-27 HYBRID v2 paired FE to Pareto completion</text>
<line x1="{margin}" y1="{height-margin}" x2="{width-margin}" y2="{height-margin}" stroke="black"/>
<line x1="{margin}" y1="{margin}" x2="{margin}" y2="{height-margin}" stroke="black"/>
{''.join(lines)}
{''.join(labels)}
<text x="{width/2}" y="{height-18}" text-anchor="middle" font-family="sans-serif" font-size="14">holdout seed index</text>
<text x="18" y="{height/2}" transform="rotate(-90 18 {height/2})" text-anchor="middle" font-family="sans-serif" font-size="14">function evaluations</text>
</svg>'''
    path.write_text(svg)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runs-root", required=True)
    parser.add_argument("--seeds", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    root = Path(args.runs_root)
    seeds = read_seeds(Path(args.seeds))
    endpoints: dict[str, list[int]] = {profile: [] for profile in PROFILES}
    rows = []
    traces = {"HYBRID_ROLLBACK": [], "HYBRID_FLOOR": []}

    for run_index, seed in enumerate(seeds, start=1):
        record = {"run": run_index, "seed": seed}
        for profile in PROFILES:
            run_root = root / profile / f"seed-{seed}"
            endpoint = parse_single_endpoint(run_root)
            endpoints[profile].append(endpoint)
            record[profile] = endpoint
        traces["HYBRID_ROLLBACK"].append(parse_controller_trace(root / "HYBRID_ROLLBACK" / f"seed-{seed}", "HYBRID_V2_ROLLBACK"))
        traces["HYBRID_FLOOR"].append(parse_controller_trace(root / "HYBRID_FLOOR" / f"seed-{seed}", "HYBRID_V2_FLOOR"))
        rows.append(record)

    h1_values = paired_relative_reductions(endpoints["OLD"], endpoints["HYBRID_ROLLBACK"])
    h1_ci = bootstrap_median_ci(h1_values)
    h1_median = statistics.median(h1_values)
    h1_status = "PASS" if h1_ci[0] > 0 else "FAIL"

    h2_values = paired_relative_reductions(endpoints["HYBRID_FLOOR"], endpoints["HYBRID_ROLLBACK"])
    h2_ci = bootstrap_median_ci(h2_values)
    h2_median = statistics.median(h2_values)
    h2_status = "POSITIVE" if h2_ci[0] > 0 else ("NEGATIVE" if h2_ci[1] < 0 else "NO_CLEAR_EFFECT")

    report = {
        "schema": "eu26-27-hybrid-v2-confirmatory-v1",
        "seeds": seeds,
        "complete_runs": {profile: len(values) for profile, values in endpoints.items()},
        "median_fe": {profile: statistics.median(values) for profile, values in endpoints.items()},
        "mean_fe": {profile: statistics.fmean(values) for profile, values in endpoints.items()},
        "H1": {
            "statistic": "paired median relative FE reduction OLD -> HYBRID_ROLLBACK",
            "median": h1_median,
            "ci95_percentile_bootstrap": list(h1_ci),
            "bootstrap_samples": BOOTSTRAP_SAMPLES,
            "bootstrap_seed": BOOTSTRAP_SEED,
            "status": h1_status,
        },
        "H2": {
            "statistic": "paired median relative FE reduction HYBRID_FLOOR -> HYBRID_ROLLBACK",
            "median": h2_median,
            "ci95_percentile_bootstrap": list(h2_ci),
            "status": h2_status,
        },
        "controller_traces": traces,
        "rows": rows,
    }

    out = Path(args.output)
    out.mkdir(parents=True, exist_ok=True)
    (out / "report.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    with (out / "paired_endpoints.csv").open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=["run", "seed", *PROFILES])
        writer.writeheader()
        writer.writerows(rows)
    write_svg(out / "paired_fe.svg", endpoints)

    rollback_counts = [int(item["rollbacks"]) for item in traces["HYBRID_ROLLBACK"]]
    rollback_maxima = [float(item["max_lambda"]) for item in traces["HYBRID_ROLLBACK"] if item["max_lambda"] is not None]
    summary = f'''# EU26-27 HYBRID v2 confirmatory result

```text
OLD median FE: {statistics.median(endpoints['OLD'])}
HYBRID_ROLLBACK median FE: {statistics.median(endpoints['HYBRID_ROLLBACK'])}
HYBRID_FLOOR median FE: {statistics.median(endpoints['HYBRID_FLOOR'])}
H1 median relative reduction: {h1_median:.6%}
H1 95% bootstrap CI: [{h1_ci[0]:.6%}, {h1_ci[1]:.6%}]
H1: {h1_status}
H2 rollback-specific median: {h2_median:.6%}
H2 95% bootstrap CI: [{h2_ci[0]:.6%}, {h2_ci[1]:.6%}]
H2: {h2_status}
median rollback events/run: {statistics.median(rollback_counts)}
median max lambda/run: {statistics.median(rollback_maxima) if rollback_maxima else 'n/a'}
```
'''
    (out / "summary.md").write_text(summary)
    print(summary)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
