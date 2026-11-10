"""Validate the complete 1440-case grid and freeze one descriptive selection."""
import argparse
import csv
from fractions import Fraction
from pathlib import Path
import os

from .common import HERE, guard_stage, read_json, require, sha, write_json
from studies.knapsack_parameters.population_validation_100_main.analysis import validate_row
from studies.knapsack_parameters.population_validation_100_main.runner import _used_bytes

FAMILIES = tuple(f"s{i:03d}" for i in range(50, 60))
TYPES = ("UC", "WC", "SC")
CONFIGS = tuple((mu, pc) for mu in (10, 15, 20, 25) for pc in (70, 80, 90, 100))
SEEDS = (150001, 150002, 150003)


def identity(row):
    return row["task"], row["seed"], row["mu"], row["pc_percentage"]


def choose_config(family_scores):
    """Use exact rational family means and the registered tie-breaking order."""
    require(set(family_scores) == set(CONFIGS) and all(len(v) == 10 for v in family_scores.values()),
            "Sixteen complete family vectors are required")
    return min(CONFIGS, key=lambda pair: (sum(family_scores[pair], Fraction()) / 10,
               max(family_scores[pair]), abs(pair[1] - 90), pair[0], pair[1]))


def gap(row, q=None):
    value = row["best"] if q is None else next(x["record_profit"] for x in row["checkpoints"] if x["q"] == q)
    return Fraction(100 * (row["optimum"] - value), row["optimum"])


def family_means(rows, pair, q=None):
    values = []
    for family in FAMILIES:
        tasks = []
        for kind in TYPES:
            case_rows = [r for r in rows if (r["family"], r["class_label"], r["mu"], r["pc_percentage"]) ==
                         (family, kind, pair[0], pair[1])]
            require(len(case_rows) == 3 and {r["seed"] for r in case_rows} == set(SEEDS), "Task repeats differ")
            tasks.append(sum((gap(r, q) for r in case_rows), Fraction()) / 3)
        values.append(sum(tasks, Fraction()) / 3)
    return values


def verify_row(row, family, mu, pc, retained=False):
    require((mu, pc) in CONFIGS and row.get("pc_percentage") == pc and row.get("seed") in SEEDS,
            "Unregistered grid configuration or repeat")
    expected_prefix = f'{row["task"]}/seed-{row["seed"]}'
    if not retained:
        expected_prefix += f'/mu{mu}-pc{pc}'
    require(row.get("artifact_prefix") == expected_prefix, "Evidence identity or path differs")
    # Reuse the frozen validator for all score, event, checkpoint and target
    # invariants, after independently validating the extended path above.
    copy = dict(row)
    copy["artifact_prefix"] = f'{row["task"]}/seed-{row["seed"]}'
    validate_row(copy, family, mu)
    return row


def collect(inputs, blocks):
    inputs, blocks = Path(inputs), Path(blocks)
    stage = read_json(inputs / "stage_manifest.json")
    require(stage.get("schema") == "initial-grid-100-stage-inputs-v1" and stage.get("stage") == "tuning"
            and stage.get("status") == "STAGE_INPUTS_PREPARED" and stage.get("new_case_count") == 1260
            and stage.get("retained_count") == 180, "Prepared tuning inputs differ")
    require(sha(inputs / "schedule.json") == stage["schedule_sha256"]
            and sha(inputs / "reused.json") == stage["reused_sha256"]
            and sha(inputs / "prepared/manifest.json") == stage["prepared_manifest_sha256"], "Tuning inputs changed")
    tasks = {t["task"]: t for t in read_json(inputs / "prepared/manifest.json")["tasks"]}
    schedule = read_json(inputs / "schedule.json")
    expected_blocks = {item["shard_id"]: item["cases"] for item in schedule["shards"]}
    require(len(expected_blocks) == 210 and schedule.get("physical_runs") == 1260, "Block schedule differs")
    files = sorted(blocks.rglob("shard.json"))
    require(len(files) == 210, "All 210 complete tuning blocks are required")
    rows, provenance, seen_blocks = [], [], set()
    for file in files:
        require(not file.is_symlink() and file.resolve().is_relative_to(blocks.resolve()), "Unsafe compact evidence")
        data = read_json(file)
        block_id = data.get("shard_id")
        require(data.get("schema") == "initial-grid-100-tuning-shard-v1" and data.get("status") == "VERIFIED"
                and block_id in expected_blocks and block_id not in seen_blocks,
                "Invalid or duplicate completed block")
        seen_blocks.add(block_id)
        require(data.get("workflow_run_id") == os.environ.get("GITHUB_RUN_ID")
                and data.get("workflow_commit") == os.environ.get("GITHUB_SHA")
                and data.get("source_manifest_sha256") == sha(HERE / "source_manifest.json")
                and data.get("stage_manifest_sha256") == sha(inputs / "stage_manifest.json")
                and data.get("raw_artifact_name") == f'initial-grid100-tuning-raw-{block_id}-{os.environ["GITHUB_RUN_ID"]}',
                "Block provenance differs")
        expected = {identity(c) for c in expected_blocks[block_id]}
        block_rows = data.get("runs")
        require(isinstance(block_rows, list) and len(block_rows) == 6
                and {identity(row) for row in block_rows} == expected, "Block identities differ")
        receipts = sorted((file.parent / "records").glob("*.json"))
        require(len(receipts) == 6 and {identity(read_json(p)): read_json(p) for p in receipts} ==
                {identity(row): row for row in block_rows}, "Per-case receipts differ from the completed block")
        for row in block_rows:
            verify_row(row, row["family"], row["mu"], row["pc_percentage"])
            rows.append(row)
        provenance.append({"shard_id": block_id, "compact_sha256": sha(file),
                           "raw_artifact_name": data["raw_artifact_name"]})
    require(seen_blocks == set(expected_blocks) and len(rows) == 1260, "New tuning cases are incomplete")
    retained = read_json(inputs / "reused.json")
    require(retained.get("status") == "VERIFIED_180_RETAINED" and retained.get("original_run_id") == 42813784277
            and len(retained.get("runs", [])) == 180, "Retained case evidence differs")
    for row in retained["runs"]:
        require((row["mu"], row["pc_percentage"]) in ((10, 90), (20, 90)), "Unexpected retained configuration")
        verify_row(row, row["family"], row["mu"], row["pc_percentage"], retained=True)
        rows.append(row)
    expected = {(f"n00100-{kind}-{family}", seed, mu, pc) for family in FAMILIES for kind in TYPES
                for seed in SEEDS for mu, pc in CONFIGS}
    actual = [identity(row) for row in rows]
    require(len(rows) == len(set(actual)) == len(expected) == 1440 and set(actual) == expected,
            "Grid contains a missing, duplicate or substituted case")
    for row in rows:
        task = tasks[row["task"]]
        bank = next(item for item in task["banks"] if item["seed"] == row["seed"])
        require(row["task_index"] == task["task_index"] and row["bank_sha256"] == bank["sha256"]
                and row["certificate_sha256"] == task["certificate_sha256"]
                and row["optimum"] == read_json(inputs / "prepared" / row["task"] / "certificate.json")["optimum"],
                "A grid record differs from the common bank or exact reference")
    rows.sort(key=lambda r: (r["task_index"], r["seed"], r["mu"], r["pc_percentage"]))
    return rows, provenance, retained["provenance"]


def plot_heatmaps(metrics, out):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np
    values = [row[key] for row in metrics for key in ("mean_gap_50000_percent", "mean_gap_100000_percent")]
    low, high = min(values), max(values)
    if low == high:
        low, high = low - .5, high + .5
    for q in (50000, 100000):
        key = f"mean_gap_{q}_percent"
        matrix = np.array([[next(r[key] for r in metrics if (r["mu"], r["pc_percentage"]) == (mu, pc))
                            for pc in (70, 80, 90, 100)] for mu in (10, 15, 20, 25)])
        fig, ax = plt.subplots(figsize=(8, 5), layout="constrained")
        image = ax.imshow(matrix, cmap="YlGnBu", vmin=low, vmax=high, aspect="auto")
        for i in range(4):
            for j in range(4):
                color = "white" if (matrix[i, j] - low) / (high - low) > .57 else "#132238"
                ax.text(j, i, f"{matrix[i,j]:.3f}".replace(".", ","), ha="center", va="center", color=color)
        ax.set_xticks(range(4), ("70", "80", "90", "100"))
        ax.set_yticks(range(4), ("10", "15", "20", "25"))
        ax.set_xlabel("Імовірність схрещування, %")
        ax.set_ylabel("Популяція, особин")
        fig.colorbar(image, ax=ax, label="Середнє відставання від OPT, %")
        for extension in ("png", "svg"):
            fig.savefig(out / f"grid-{q}.{extension}", dpi=200, bbox_inches="tight")
        plt.close(fig)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inputs", type=Path, required=True)
    parser.add_argument("--blocks", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    guard_stage("tuning")
    require(not args.out.exists(), "Preserve prior selection and result files")
    rows, provenance, retained_provenance = collect(args.inputs, args.blocks)
    scores = {pair: family_means(rows, pair) for pair in CONFIGS}
    chosen = choose_config(scores)
    metrics = []
    for mu, pc in CONFIGS:
        family50 = family_means(rows, (mu, pc), 50000)
        metrics.append({"mu": mu, "pc_percentage": pc, "runs": 90,
                        "mean_gap_50000_percent": float(sum(family50, Fraction()) / 10),
                        "mean_gap_100000_percent": float(sum(scores[(mu, pc)], Fraction()) / 10),
                        "worst_family_gap_100000_percent": float(max(scores[(mu, pc)]))})
    args.out.mkdir(parents=True)
    with (args.out / "grid.csv").open("x", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(metrics[0]), delimiter=";")
        writer.writeheader(); writer.writerows(metrics)
    write_json(args.out / "validated_records.json.gz", {"schema": "initial-grid-100-validated-tuning-v1",
               "status": "VERIFIED_1440", "runs": rows, "provenance": provenance,
               "retained_provenance": retained_provenance})
    require(_used_bytes(args.out) <= 256 * 1024**2, "Tuning result artifact exceeds its reserved size")
    selection = {"schema": "initial-grid-100-selection-v1", "status": "SELECTED_BEFORE_VALIDATION",
                 "mu": chosen[0], "pc_percentage": chosen[1],
                 "source_tuning_inputs_sha256": sha(args.inputs / "stage_manifest.json"),
                 "source_tuning_records_sha256": sha(args.out / "validated_records.json.gz"),
                 "original_run_id": 42813784277, "tuning_run_id": os.environ["GITHUB_RUN_ID"],
                 "tuning_commit": os.environ["GITHUB_SHA"],
                 "source_manifest_sha256": sha(HERE / "source_manifest.json"),
                 "mean_final_gap_numerator": (sum(scores[chosen], Fraction()) / 10).numerator,
                 "mean_final_gap_denominator": (sum(scores[chosen], Fraction()) / 10).denominator,
                 "selection_criteria": ["minimum_family_weighted_gap", "minimum_worst_family_gap",
                                        "crossover_nearest_90", "smaller_population", "smaller_crossover"],
                 "independent_validation_started": False}
    write_json(args.out / "selection.json", selection)
    (args.out / "figures").mkdir()
    plot_heatmaps(metrics, args.out / "figures")
    require(_used_bytes(args.out) <= 256 * 1024**2, "Tuning figures exceed the reserved artifact size")
    print("Validated 1440 cases and froze a descriptive selection; independent search not started.", flush=True)


if __name__ == "__main__":
    main()
