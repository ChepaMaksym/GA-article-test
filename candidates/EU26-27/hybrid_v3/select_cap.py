from __future__ import annotations

import argparse
import csv
import json
import statistics
from pathlib import Path

DIMENSION = 100
CAPS = (15, 20, 30, 40, 60, 100)
DEV_SEEDS = tuple(range(28001, 28031))


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


def paired_median_reduction(old: list[int], candidate: list[int]) -> float:
    return statistics.median((o - c) / o for o, c in zip(old, candidate))


def choose_cap(scores: dict[int, float]) -> int:
    return min(CAPS, key=lambda cap: (-scores[cap], cap))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runs-root", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    root = Path(args.runs_root)
    old = [parse_single_endpoint(root / "OLD" / f"seed-{seed}") for seed in DEV_SEEDS]
    cap_endpoints: dict[int, list[int]] = {}
    scores: dict[int, float] = {}
    rows = []

    for cap in CAPS:
        values = [parse_single_endpoint(root / f"CAP{cap}" / f"seed-{seed}") for seed in DEV_SEEDS]
        cap_endpoints[cap] = values
        scores[cap] = paired_median_reduction(old, values)

    selected = choose_cap(scores)

    for index, seed in enumerate(DEV_SEEDS):
        row = {"run": index + 1, "seed": seed, "OLD": old[index]}
        for cap in CAPS:
            row[f"CAP{cap}"] = cap_endpoints[cap][index]
        rows.append(row)

    report = {
        "schema": "eu26-27-hybrid-v3-development-selection-v1",
        "development_seeds": list(DEV_SEEDS),
        "caps": list(CAPS),
        "selection_rule": "largest paired median relative FE reduction; exact tie -> smaller cap",
        "scores": {str(cap): scores[cap] for cap in CAPS},
        "median_fe": {
            "OLD": statistics.median(old),
            **{f"CAP{cap}": statistics.median(cap_endpoints[cap]) for cap in CAPS},
        },
        "mean_fe": {
            "OLD": statistics.fmean(old),
            **{f"CAP{cap}": statistics.fmean(cap_endpoints[cap]) for cap in CAPS},
        },
        "selected_cap": selected,
        "selected_algorithm": f"HybridCap{selected}",
    }

    out = Path(args.output)
    out.mkdir(parents=True, exist_ok=True)
    (out / "selected_cap.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    with (out / "development_endpoints.csv").open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=["run", "seed", "OLD", *[f"CAP{cap}" for cap in CAPS]])
        writer.writeheader()
        writer.writerows(rows)

    lines = [
        "# EU26-27 HYBRID v3 development selection",
        "",
        "```text",
        f"selected cap: {selected}",
        f"selected algorithm: HybridCap{selected}",
    ]
    for cap in CAPS:
        lines.append(f"cap {cap}: paired median relative FE reduction = {scores[cap]:.6%}")
    lines += ["```", "", "These development results are not confirmatory evidence."]
    summary = "\n".join(lines) + "\n"
    (out / "summary.md").write_text(summary)
    print(summary)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
