#!/usr/bin/env python3
"""Fail-closed audit of the pinned CMF-AGAwER author snapshot."""
from __future__ import annotations

import argparse
from pathlib import Path
import subprocess

import numpy as np

EXPECTED_COMMIT = "d24e61e78ac197ad75342e8f4be5d63d17bd9e7a"
EXPECTED_BLOBS = {
    "CMF-AGAwER.py": "80ebd0599ac328e09373f21d3c61bb86004d184a",
    "Datasets/Colon.xlsx": "0c02aa35b606e433079e4e858f091624f9ab05ab",
    (
        "The top 50 features selected from each ranker (CEI, MI, and FR) "
        "and their concatenation (features.npy)/Colon/features.npy"
    ): "5ea58b5418a235ff1afcea97f76df81a07d9b1db",
}


def _git(root: Path, *args: str) -> str:
    return subprocess.check_output(
        ["git", "-C", str(root), *args], text=True, stderr=subprocess.STDOUT
    ).strip()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("upstream", type=Path)
    args = parser.parse_args()
    root = args.upstream.resolve()

    commit = _git(root, "rev-parse", "HEAD")
    if commit != EXPECTED_COMMIT:
        raise SystemExit(f"unexpected upstream commit: {commit}")

    for path, expected_blob in EXPECTED_BLOBS.items():
        actual_blob = _git(root, "rev-parse", f"HEAD:{path}")
        if actual_blob != expected_blob:
            raise SystemExit(
                f"upstream blob changed for {path}: {actual_blob} != {expected_blob}"
            )
        if not (root / path).is_file():
            raise SystemExit(f"pinned upstream file missing: {path}")

    source_path = root / "CMF-AGAwER.py"
    source = source_path.read_text(encoding="utf-8", errors="strict")
    required = [
        "pcc=0.9",
        "pmm=0.4",
        "nPop=10",
        "MaxIt=100",
        "TagCheck=20",
        "AdaptCheck=6",
        "pcc=pcc-0.3",
        "pmm=pmm+0.2",
        "DecisionTreeClassifier(random_state=42)",
        "StratifiedKFold(n_splits=5)",
        "radius=find_max_distance(distance_matrix)[0]/2",
        "nc=2*round(pc*nPop/2)",
        "nm=round(pm*nPop)",
    ]
    missing = [token for token in required if token not in source]
    if missing:
        raise SystemExit(f"source contract changed; missing {missing}")

    features_path = root / next(
        path for path in EXPECTED_BLOBS if path.endswith("features.npy")
    )
    features = np.load(features_path, allow_pickle=False)
    flattened = [int(value) for value in np.asarray(features).reshape(-1).tolist()]
    if len(flattened) != 128 or len(set(flattened)) != 128:
        raise SystemExit(
            f"unexpected Colon search space: {len(flattened)} values, "
            f"{len(set(flattened))} unique"
        )
    if min(flattened) < 0 or max(flattened) >= 2000:
        raise SystemExit("Colon feature list escapes the 2000-feature dataset")

    # Preserve rather than silently repair material paper/source differences.
    # Paper equations use ceil for nc/nm; the published Python uses round().
    print("KNOWN_DIVERGENCE: paper ceil offspring counts vs source Python round")

    # The public file is notebook-style, not a directly selectable experiment:
    # later dataset cells overwrite Colon and a ranker cell uses stale Xn state.
    dataset_loads = source.count("df = pd.read_excel") + source.count("df = pd.read_csv")
    if dataset_loads < 9 or "Xn=X[Xn]" not in source:
        raise SystemExit("expected notebook-selection defects disappeared")
    print(
        "KNOWN_SOURCE_DEFECT: linear execution overwrites datasets and hits stale Xn=X[Xn]"
    )

    # In the population probability refresh, the loop variable is j but the
    # assignment uses stale i. Source-compatibility preserves this; the separate
    # clean-room paper profile must use Fits[j] = pop[j].fit.
    probability_bug = "for j in range (nPop):\n       Fits[i]=pop[i].fit"
    if probability_bug not in source:
        raise SystemExit("expected stale-index probability defect disappeared")
    print("KNOWN_SOURCE_DEFECT: probability refresh uses stale i inside for-j loop")

    print(f"PASS_SOURCE_CONTRACT commit={commit}")
    for path, blob in EXPECTED_BLOBS.items():
        print(f"PASS_BLOB {blob} {path}")
    print("PASS_COLON_FEATURE_SPACE size=128 unique=128 range_within_0_1999")


if __name__ == "__main__":
    main()
