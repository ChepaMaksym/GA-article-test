#!/usr/bin/env python3
"""Fail-closed audit of the pinned CHC-QX author snapshot."""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
import subprocess

EXPECTED_COMMIT = "6ac5a7ec77f8a7c096ab4d019254fcc897988fd6"
EXPECTED_BLOBS = {
    "code/Dataset.py": "18c8d417f7236ef0af3c8a35279a1914679cac74",
    "code/Evolution.py": "05b0d8afc02faee688e5d1ff8e24531ae41307c7",
    "code/Example.ipynb": "87d2ea5caada5278853553de2c73d2ec6083f9b6",
    "data/census-income.data": "e780a25c2dec3f1a10d65cca9ea05001a77b37b6",
    "results/results.csv": "4783d460d75bad4ee6a7ce1b191da9c5c0fc5e77",
}


def git(root: Path, *args: str) -> str:
    return subprocess.check_output(
        ["git", "-C", str(root), *args],
        text=True,
        stderr=subprocess.STDOUT,
    ).strip()


def audit_dataset(path: Path) -> tuple[int, set[str]]:
    rows = 0
    labels: set[str] = set()
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.reader(handle)
        for row_number, row in enumerate(reader, start=1):
            if len(row) != 42:
                raise SystemExit(
                    f"Census row {row_number} has {len(row)} fields instead of 42"
                )
            rows += 1
            labels.add(row[-1].strip())
    if rows != 199_523:
        raise SystemExit(f"unexpected Census row count: {rows}")
    if len(labels) != 2:
        raise SystemExit(f"unexpected Census target labels: {sorted(labels)!r}")
    return rows, labels


def notebook_text(notebook: dict) -> str:
    chunks: list[str] = []
    for cell in notebook.get("cells", []):
        chunks.extend(str(value) for value in cell.get("source", []))
        for output in cell.get("outputs", []):
            chunks.extend(str(value) for value in output.get("text", []))
            data = output.get("data", {})
            for values in data.values():
                if isinstance(values, list):
                    chunks.extend(str(value) for value in values)
                else:
                    chunks.append(str(values))
    return "".join(chunks)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("upstream", type=Path)
    args = parser.parse_args()
    root = args.upstream.resolve()

    commit = git(root, "rev-parse", "HEAD")
    if commit != EXPECTED_COMMIT:
        raise SystemExit(f"unexpected upstream commit: {commit}")

    for relative, expected_blob in EXPECTED_BLOBS.items():
        path = root / relative
        if not path.is_file():
            raise SystemExit(f"pinned upstream file missing: {relative}")
        actual_blob = git(root, "rev-parse", f"HEAD:{relative}")
        if actual_blob != expected_blob:
            raise SystemExit(
                f"upstream blob changed for {relative}: "
                f"{actual_blob} != {expected_blob}"
            )

    evolution = (root / "code" / "Evolution.py").read_text(
        encoding="utf-8", errors="strict"
    )
    dataset_source = (root / "code" / "Dataset.py").read_text(
        encoding="utf-8", errors="strict"
    )

    evolution_tokens = [
        'creator.create("FitnessMin", base.Fitness, weights=(1.0,))',
        'toolbox.register("mate", Evolution.HUX)',
        'toolbox.register("mutate", tools.mutFlipBit, indpb=1/3)',
        "def CHCqx(baseline_individual, f, n_individual, f_no_change, population_size=50",
        "d = ind_size // 4",
        "while (no_change < f_no_change):",
        "Evolution.CHC(gaqx_individual, toolbox, d, population, max_generations=f",
        "if (d == 0):",
        "toolbox.mutate(mutant)",
        "d -= 1",
        "if ind not in evaluated_population:",
        "fitness = Evolution.evaluate(ind, task, target_dataset, baseline_individual)[0]",
    ]
    missing = [token for token in evolution_tokens if token not in evolution]
    if missing:
        raise SystemExit(f"Evolution source contract changed; missing {missing}")

    dataset_tokens = [
        "self.df = self.df.sample(frac=1, random_state=10)",
        "X_train = self.X[0:int(0.6 * len(self.X)), :]",
        "X_val = self.X[int(0.6 * len(self.X)):int(0.8 * len(self.X)), :]",
        "X_test = self.X[int(0.8 * len(self.X)):, :]",
        "X_train_normalized = (X_train - mean) / std",
        "self.ValidationAccuracy = accuracy_score(self.y_val, y_pred)",
        "self.TestAccuracy = accuracy_score(self.y_test, y_pred)",
    ]
    missing = [token for token in dataset_tokens if token not in dataset_source]
    if missing:
        raise SystemExit(f"Dataset source contract changed; missing {missing}")

    rows, labels = audit_dataset(root / "data" / "census-income.data")

    notebook = json.loads(
        (root / "code" / "Example.ipynb").read_text(encoding="utf-8")
    )
    text = notebook_text(notebook)
    notebook_tokens = [
        "Evolution.CHCqx(dataset, 10, 10, 2, population_size, verbose=1)",
        "Meta-model sample size: 14964",
        "Best Individual =  0.9491 , Gen =  60",
        "Test accuracy: % 94.96",
        "Solution found in:  55.46 sec",
        "Selected features indexes:  [12 16 17 19 40]",
        "DecisionTreeClassifier(random_state=0)",
        "population_size = 50",
    ]
    missing = [token for token in notebook_tokens if token not in text]
    if missing:
        raise SystemExit(f"executed notebook endpoint changed; missing {missing}")

    results_text = (root / "results" / "results.csv").read_text(encoding="utf-8")
    if results_text != ",algorithm,time,test\n":
        raise SystemExit("unexpected results.csv content")

    print(f"PASS_SOURCE_COMMIT {commit}")
    for relative, blob in EXPECTED_BLOBS.items():
        print(f"PASS_BLOB {blob} {relative}")
    print(
        "PASS_CENSUS_STRUCTURE "
        f"rows={rows} columns=42 features=41 labels={sorted(labels)!r}"
    )
    print(
        "PASS_NOTEBOOK_ENDPOINT sample=14964 validation=0.9491 "
        "generation=60 test_percent=94.96 features=12,16,17,19,40"
    )
    print(
        "KNOWN_LIMITATION results/results.csv contains only its header; "
        "the executed notebook and paper table are the numerical evidence"
    )


if __name__ == "__main__":
    main()
