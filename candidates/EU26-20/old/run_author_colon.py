#!/usr/bin/env python3
"""Prepare and execute the pinned author AGAwER source for the Colon endpoint.

The upstream file is notebook-style and contains mutually exclusive dataset/ranker cells
in one linear Python file. We apply only compatibility edits needed to select the Colon
experiment and the author's published precomputed feature list. Algorithm statements are
otherwise preserved. Every repair is documented because this is source-compatibility,
not a claim that the raw file executes unchanged.
"""
from pathlib import Path
import argparse
import os
import subprocess
import sys


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("upstream", type=Path)
    ap.add_argument("--seed", type=int, default=1)
    args = ap.parse_args()
    root = args.upstream.resolve()
    src = (root / "CMF-AGAwER.py").read_text(encoding="utf-8")

    colon = root / "Datasets" / "Colon.xlsx"
    features = root / "The top 50 features selected from each ranker (CEI, MI, and FR) and their concatenation (features.npy)" / "Colon" / "features.npy"

    lines = src.splitlines()
    out = []
    colon_seen = False
    for line in lines:
        stripped = line.strip()
        # Select only Colon. The published script otherwise overwrites df eight times.
        if stripped.startswith("df = pd.read_excel") or stripped.startswith("df = pd.read_csv"):
            if "Colon.xlsx" in line and not colon_seen:
                out.append(f"df = pd.read_excel({str(colon)!r}, header=None)")
                colon_seen = True
            else:
                out.append("# EU26-20 disabled alternate dataset: " + line)
        # Colon labels are already converted by the line immediately following its load.
        # Disable label conversions belonging to the subsequently disabled datasets.
        elif stripped.startswith("df.iloc[:,df.shape[1]-1].replace") and colon_seen and "'Normal':1, 'Tumor':2" not in line:
            out.append("# EU26-20 disabled alternate label conversion: " + line)
        # The ranker section contains a notebook-cell bug: after computing integer feature
        # indices in Xn, it executes Xn=X[Xn] with a stale float-valued Xn in linear mode.
        # We do not need to recompute rankers because the authors publish features.npy and
        # README explicitly permits loading it directly. Skip ranker execution entirely.
        elif stripped == "t0=time()":
            out.append("# EU26-20 skip recomputation of published rankers; use features.npy")
            out.append("if False:")
            out.append("    " + line)
        elif out and out[-1].startswith("if False:"):
            out.append("    " + line)
        elif stripped == "###########  Metrics Evaluation using 5-fold stratified cross validation before applying CMF-AGAwER":
            # close the synthetic if False block by returning to column zero
            out.append(line)
        elif stripped == "search_space=features":
            out.append(f"search_space=np.load({str(features)!r}).tolist()")
        else:
            out.append(line)
    src = "\n".join(out)

    # The simple line-wise indentation above cannot safely delimit the whole notebook
    # ranker cell, so replace that cell structurally between stable published markers.
    start = src.find("# EU26-20 skip recomputation of published rankers; use features.npy")
    end_marker = "###########  Metrics Evaluation using 5-fold stratified cross validation before applying CMF-AGAwER"
    end = src.find(end_marker)
    if start < 0 or end < 0 or end <= start:
        raise SystemExit("ranker cell boundaries not found")
    src = src[:start] + (
        "# EU26-20: README-authorized direct use of published features.npy; "
        "ranker recomputation omitted for source replay.\n"
    ) + src[end:]

    if not colon_seen:
        raise SystemExit("Colon load site not found")
    if "search_space=np.load" not in src:
        raise SystemExit("search-space patch failed")

    marker = "###############SHAP"
    if marker not in src:
        raise SystemExit("result boundary marker missing")
    src = src.split(marker, 1)[0]

    seed_block = (
        "\n# EU26-20 deterministic replay seed\n"
        f"random.seed({args.seed})\n"
        f"np.random.seed({args.seed})\n"
    )
    anchor = 'warnings.simplefilter("ignore")'
    src = src.replace(anchor, anchor + seed_block, 1)

    target = Path(os.environ.get("RUNNER_TEMP", "/tmp")) / f"eu26-20-colon-seed-{args.seed}.py"
    target.write_text(src, encoding="utf-8")
    print(f"GENERATED={target}")
    cp = subprocess.run([sys.executable, str(target)], text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    print(cp.stdout)
    if cp.returncode:
        raise SystemExit(cp.returncode)


if __name__ == "__main__":
    main()
