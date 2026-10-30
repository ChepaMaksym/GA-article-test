"""CI-only descriptive analysis of frozen recipient records; no GA runs."""
import argparse
from collections import defaultdict
import gzip
import hashlib
import json
import math
import os
from pathlib import Path
from statistics import NormalDist, fmean, stdev

PROFILES = ("k2", "k3", "k4", "k5", "adaptive", "replay")
CONTROLS = ("k2", "k3", "k4", "k5", "replay")


def main():
    if os.environ.get("GITHUB_ACTIONS") != "true":
        raise RuntimeError("Numerical analysis is restricted to CI")
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    source, out = Path(args.source), Path(args.output)
    out.mkdir(parents=True, exist_ok=True)
    manifest = json.loads((source / "file_manifest.json").read_text(encoding="utf-8"))
    entries = {x["path"]: x for x in manifest["files"]}
    for filename in ("compact_records.json.gz", "series_summary.json"):
        data = (source / filename).read_bytes()
        item = entries[filename]
        if len(data) != item["bytes"] or hashlib.sha256(data).hexdigest() != item["sha256"]:
            raise ValueError("Frozen source identity mismatch: " + filename)
    rows = json.loads(gzip.decompress((source / "compact_records.json.gz").read_bytes()))
    summary = json.loads((source / "series_summary.json").read_text(encoding="utf-8"))
    identities = {(r["task"], r["seed"], r["profile"]) for r in rows}
    if len(rows) != 5400 or len(identities) != 5400:
        raise ValueError("Missing or duplicate recipient identities")
    expected = {(f"{kind}-s{i:03}", seed, profile) for kind in ("UC", "WC", "SC")
                for i in range(40, 50) for seed in range(110001, 110031) for profile in PROFILES}
    if identities != expected:
        raise ValueError("Unexpected task, seed or profile")
    observations = defaultdict(list)
    for r in rows:
        for q in (0, 1000, 2500, 5000):
            event = [x for x in r["record_events"] if x["q"] <= q][-1]
            observations[(r["profile"], r["family"], r["task"], q)].append(100 * (r["optimum"] - event["profit"]) / r["optimum"])
    checkpoints = []
    for p in PROFILES:
        for q in (0, 1000, 2500, 5000):
            family = [fmean(fmean(observations[(p, f"s{i:03}", f"{kind}-s{i:03}", q)])
                            for kind in ("UC", "WC", "SC")) for i in range(40, 50)]
            checkpoints.append({"profile": p, "query": q, "family_weighted_gap_percent": fmean(family)})
    family_effects = summary["primary_analysis"]["family_effects"]
    loo = []
    for control in CONTROLS:
        for row in family_effects:
            other = [x["effects"][control] for x in family_effects if x["family"] != row["family"]]
            loo.append({"control": control, "family": row["family"], "effect": row["effects"][control],
                        "leave_one_out": fmean(other)})
    # Normal approximation plus a t-quantile asymptotic correction. This is
    # a planning scenario, not a guarantee of BCa coverage or future variance.
    z = NormalDist().inv_cdf(0.9875)
    estimates = []
    for h in (0.1, 0.2):
        for multiplier in (1.0, 1.5, 2.0):
            required = {}
            for control in ("k3", "replay"):
                sd = stdev(x["effects"][control] for x in family_effects) * multiplier
                n = 3
                while True:
                    df = n - 1
                    t = z + (z**3 + z)/(4*df) + (5*z**5 + 16*z**3 + 3*z)/(96*df**2)
                    if t * sd / math.sqrt(n) <= h:
                        break
                    n += 1
                required[control] = n
            n = max(required.values())
            # 30 seed repetitions and all three task types; 5 recipients + donor.
            runs = 540*n
            # Historical whole-study allocated runner time and compressed search
            # logs, divided by all 6356 pilot+main runs, then scaled linearly by
            # the doubled query budget with a further 50% contingency. This is
            # intentionally labeled as a weak proxy, not a measured forecast.
            time_proxy = math.ceil(runs * (174 / 6356) * 2 * 1.5)
            bytes_proxy = math.ceil(runs * (1599912478 / 6356) * 2 * 1.5)
            estimates.append({"half_width_pp": h, "sd_multiplier": multiplier, "per_contrast": required,
                              "families": n, "repetitions": 30, "physical_runs": runs,
                              "new_evaluations": 5400000*n,
                              "runner_minutes_proxy": time_proxy, "journal_bytes_proxy": bytes_proxy,
                              "resource_status": "rough historical linear proxy; requires new resource pilot"})
    result = {"status": "DESCRIPTIVE", "checkpoints": checkpoints, "family_and_leave_one_out": loo,
              "activity": summary["activity_cells"], "planning_scenarios": estimates,
              "existing_intervals_recomputed": False,
              "limitations": "Ten observed families cannot establish coverage or predict future variance reliably."}
    (out / "review.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(8, 4.5))
    labels = {"k2": "Сталий турнір 2", "k3": "Сталий турнір 3", "adaptive": "Адаптивний", "replay": "Готовий розклад"}
    colors = {"k2": "#1765a0", "k3": "#5698c4", "adaptive": "#c65024", "replay": "#8755a4"}
    for p in ("k2", "k3", "adaptive", "replay"):
        r = next(x for x in summary["prespecified_examples"] if x["profile"] == p)
        xs = [x["q"] for x in r["record_events"]] + [5000]
        ys = [100*x["profit"]/r["optimum"] for x in r["record_events"]]
        ax.step(xs, ys + [ys[-1]], where="post", label=labels[p], color=colors[p])
    ax.set_xlabel("Нові оцінювання")
    ax.set_ylabel("Рекорд, % від оптимуму")
    ax.legend()
    ax.grid(alpha=.2)
    fig.tight_layout()
    fig.savefig(out / "trajectory_four_profiles.png", dpi=200)
    plt.close(fig)


if __name__ == "__main__":
    main()
