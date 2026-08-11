#!/usr/bin/env python3
"""Fail-closed audit of the pinned CMF-AGAwER author snapshot."""
from pathlib import Path
import argparse
import re

EXPECTED_COMMIT = "d24e61e78ac197ad75342e8f4be5d63d17bd9e7a"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("upstream", type=Path)
    args = ap.parse_args()
    root = args.upstream.resolve()
    source = (root / "CMF-AGAwER.py").read_text(encoding="utf-8", errors="strict")

    required = [
        "pcc=0.9", "pmm=0.4", "nPop=10", "MaxIt=100",
        "TagCheck=20", "AdaptCheck=6", "pcc=pcc-0.3", "pmm=pmm+0.2",
        "DecisionTreeClassifier(random_state=42)",
        "StratifiedKFold(n_splits=5)",
        "radius=find_max_distance(distance_matrix)[0]/2",
    ]
    missing = [x for x in required if x not in source]
    if missing:
        raise SystemExit(f"source contract changed; missing {missing}")

    colon = root / "Datasets" / "Colon.xlsx"
    features = root / "The top 50 features selected from each ranker (CEI, MI, and FR) and their concatenation (features.npy)" / "Colon" / "features.npy"
    if not colon.is_file() or not features.is_file():
        raise SystemExit("Colon artifacts missing")

    # Important reproducibility divergence: the paper specifies ceil for nc/nm,
    # while the published Python uses built-in round(). Keep this visible.
    if "nc=2*round(pc*nPop/2)" not in source or "nm=round(pm*nPop)" not in source:
        raise SystemExit("expected paper/source rounding divergence disappeared")

    print("PASS_SOURCE_CONTRACT")
    print("KNOWN_DIVERGENCE: paper ceil offspring counts vs source Python round")


if __name__ == "__main__":
    main()
