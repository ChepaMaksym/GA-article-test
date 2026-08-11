#!/usr/bin/env python3
"""Prepare and execute the pinned author AGAwER source for the Colon endpoint.

Only experiment-selection/path/seed edits are applied. The generated script is retained
outside the repository by CI. This is a source-compatibility replay, distinct from the
independent paper-profile core in agawer_core.py.
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

    # Keep Colon load; disable the eight alternative dataset assignments that otherwise
    # overwrite df in the notebook-style author script.
    lines = src.splitlines()
    out = []
    colon_seen = False
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("df = pd.read_excel") or stripped.startswith("df = pd.read_csv"):
            if "Colon.xlsx" in line and not colon_seen:
                out.append(f"df = pd.read_excel({str(colon)!r}, header=None)")
                colon_seen = True
            else:
                out.append("# EU26-20 disabled alternate dataset: " + line)
        elif stripped == "search_space=features":
            out.append(f"search_space=np.load({str(features)!r}).tolist()")
        else:
            out.append(line)
    src = "\n".join(out)
    if not colon_seen:
        raise SystemExit("Colon load site not found")
    if "search_space=np.load" not in src:
        raise SystemExit("search-space patch failed")

    # The remainder after the AGAwER result is unrelated filter/plot benchmarking and
    # would obscure the target endpoint.
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
