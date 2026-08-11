#!/usr/bin/env python3
"""Execute the pinned author AGAwER source for the Colon OLD endpoint.

The upstream file is notebook-style: mutually exclusive dataset/ranker cells and
post-experiment analyses are concatenated into one linear script. This wrapper
applies only compatibility edits required to select the published Colon
experiment and the author's published ``features.npy`` search space. The AGAwER
search statements are otherwise preserved.

This is an author-source compatibility profile, not the independent paper
profile. In particular, it deliberately preserves the author's Python
``round`` offspring counts and other source-level semantics.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from typing import Any

EXPECTED_COMMIT = "d24e61e78ac197ad75342e8f4be5d63d17bd9e7a"
RESULT_PREFIX = "EU26_20_RESULT="


def _replace_between(text: str, start_marker: str, end_marker: str, replacement: str) -> str:
    start = text.find(start_marker)
    end = text.find(end_marker)
    if start < 0 or end < 0 or end <= start:
        raise SystemExit(
            f"source layout changed; cannot replace range {start_marker!r} .. {end_marker!r}"
        )
    return text[:start] + replacement + text[end:]


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _prepare_source(root: Path, seed: int) -> tuple[str, dict[str, Any]]:
    source_path = root / "CMF-AGAwER.py"
    colon_path = root / "Datasets" / "Colon.xlsx"
    features_path = (
        root
        / "The top 50 features selected from each ranker (CEI, MI, and FR) and their concatenation (features.npy)"
        / "Colon"
        / "features.npy"
    )
    for path in (source_path, colon_path, features_path):
        if not path.is_file():
            raise SystemExit(f"required upstream artifact missing: {path}")

    try:
        commit = subprocess.check_output(
            ["git", "-C", str(root), "rev-parse", "HEAD"], text=True
        ).strip()
    except (OSError, subprocess.CalledProcessError) as exc:
        raise SystemExit(f"cannot authenticate upstream checkout: {exc}") from exc
    if commit != EXPECTED_COMMIT:
        raise SystemExit(f"unexpected upstream commit: {commit}")

    src = source_path.read_text(encoding="utf-8", errors="strict")

    # Select Colon. The published notebook-style file otherwise overwrites df
    # with each later dataset assignment.
    lines: list[str] = []
    colon_seen = False
    for line in src.splitlines():
        stripped = line.strip()
        if stripped.startswith("df = pd.read_excel") or stripped.startswith("df = pd.read_csv"):
            if "Colon.xlsx" in line and not colon_seen:
                lines.append(f"df = pd.read_excel({str(colon_path)!r}, header=None)")
                colon_seen = True
            else:
                lines.append("# EU26-20 disabled alternate dataset: " + line)
        elif (
            stripped.startswith("df.iloc[:,df.shape[1]-1].replace")
            and colon_seen
            and "'Normal':1, 'Tumor':2" not in line
        ):
            lines.append("# EU26-20 disabled alternate label conversion: " + line)
        elif stripped == "search_space=features":
            lines.append(f"search_space=np.load({str(features_path)!r}).tolist()")
        else:
            lines.append(line)
    src = "\n".join(lines)
    if not colon_seen:
        raise SystemExit("Colon dataset load site not found")
    if "search_space=np.load" not in src:
        raise SystemExit("published feature-list selection patch failed")

    # README explicitly allows loading the published features.npy directly.
    # Skip the ranker notebook cell, whose linear execution contains stale-Xn
    # statements that are not part of the AGAwER endpoint.
    ranker_start = "t0=time()"
    baseline_start = (
        "###########  Metrics Evaluation using 5-fold stratified cross validation "
        "before applying CMF-AGAwER"
    )
    src = _replace_between(
        src,
        ranker_start,
        baseline_start,
        (
            "# EU26-20: README-authorized direct use of the published features.npy; "
            "ranker recomputation omitted for source replay.\n\n"
        ),
    )

    # Table 5 uses stratified 5-fold CV. Remove the separate 100 random
    # train/test diagnostic cell before the GA and freeze the 5-fold baseline.
    random_split_start = (
        "###########  Metrics Evaluation using  stratified train-test split "
        "before applying CMF-AGAwER"
    )
    ga_start = "##############################  GENETIC ALGORITHM #######################"
    src = _replace_between(
        src,
        random_split_start,
        ga_start,
        "_eu_baseline_accuracy = round(float(np.mean(s)), 2)\n\n",
    )

    # Exclude SHAP/filter benchmarking after the AGA endpoint.
    result_boundary = "###############SHAP"
    if result_boundary not in src:
        raise SystemExit("post-AGA boundary marker missing")
    src = src.split(result_boundary, 1)[0]

    # Seed both random streams used by the source.
    anchor = 'warnings.simplefilter("ignore")'
    if src.count(anchor) != 1:
        raise SystemExit("random-seed insertion anchor changed")
    seed_block = (
        "\n# EU26-20 deterministic source replay seed\n"
        f"random.seed({seed})\n"
        f"np.random.seed({seed})\n"
    )
    src = src.replace(anchor, anchor + seed_block, 1)

    # Prevent a source-only reporting NameError if the initial elite is never
    # strictly improved. Match the complete initial-ledger context because the
    # source contains more than one textual BestAcc assignment elsewhere.
    best_context = (
        "BestFits[it]=BestSol.fit\n"
        "Best_External_fits[it]=Best_REP_fit\n"
        "BestAcc=BestSol.fit\n"
        "##store worst fit"
    )
    if src.count(best_context) != 1:
        raise SystemExit(
            f"initial-best reporting context changed; found {src.count(best_context)}"
        )
    best_replacement = (
        "BestFits[it]=BestSol.fit\n"
        "Best_External_fits[it]=Best_REP_fit\n"
        "BestAcc=BestSol.fit\n"
        "BestList=BestSol.List\n"
        "BestPosition=BestSol.position\n"
        "BestPre=BestSol.precision\n"
        "BestRec=BestSol.recall\n"
        "BestFmeasure=BestSol.fmeasure\n"
        "BestMCC=BestSol.mcc\n"
        "##store worst fit"
    )
    src = src.replace(best_context, best_replacement, 1)

    # Append a machine-readable endpoint without changing the optimizer.
    summary = r"""
# EU26-20 structured OLD endpoint
import json as _eu_json

_eu_best = pop[0]
_eu_features = [int(v) for v in list(_eu_best.List)]
_eu_fit = float(_eu_best.fit)
if abs(_eu_fit - float(BestAcc)) > 1e-12:
    raise RuntimeError("final elitist population and BestAcc diverged")
if not _eu_features or len(_eu_features) != len(set(_eu_features)):
    raise RuntimeError("final feature subset is empty or contains duplicates")
if any(v not in set(int(z) for z in search_space) for v in _eu_features):
    raise RuntimeError("final subset escaped the published search space")

_eu_horizon = max(1, int(it))
_eu_target_indices = np.where(np.asarray(BestFits[:_eu_horizon]) >= 0.94)[0]
_eu_first_target_iteration = (
    int(_eu_target_indices[0]) if len(_eu_target_indices) else None
)
_eu_first_target_nfe = (
    int(nfe[_eu_first_target_iteration])
    if _eu_first_target_iteration is not None
    else None
)

def _eu_optional_float(value):
    return None if value is None else float(value)

_eu_labels, _eu_counts = np.unique(np.asarray(y), return_counts=True)
_eu_result = {
    "schema": "eu26-20-colon-old-v1",
    "profile": "author_source_compatibility",
    "seed": __SEED__,
    "upstream_commit": "__COMMIT__",
    "offspring_rounding": "python_round_ties_to_even",
    "dataset_rows": int(X.shape[0]),
    "raw_features": int(X.shape[1]),
    "class_labels": [int(v) for v in _eu_labels.tolist()],
    "class_counts": [int(v) for v in _eu_counts.tolist()],
    "search_space_size": int(len(search_space)),
    "baseline_accuracy": float(_eu_baseline_accuracy),
    "best_accuracy": _eu_fit,
    "subset_length": int(len(_eu_features)),
    "features": _eu_features,
    "precision": _eu_optional_float(_eu_best.precision),
    "recall": _eu_optional_float(_eu_best.recall),
    "fscore": _eu_optional_float(_eu_best.fmeasure),
    "mcc": _eu_optional_float(_eu_best.mcc),
    "nfe": int(NFE),
    "iterations": int(it),
    "adaptive_events": int(Adaptive),
    "final_pc": float(pcc),
    "final_pm": float(pmm),
    "first_target_iteration": _eu_first_target_iteration,
    "first_target_nfe": _eu_first_target_nfe,
}
print("EU26_20_RESULT=" + _eu_json.dumps(_eu_result, sort_keys=True))
"""
    summary = summary.replace("__SEED__", str(seed)).replace("__COMMIT__", EXPECTED_COMMIT)
    src = src.rstrip() + "\n" + summary.lstrip()

    metadata: dict[str, Any] = {
        "upstream_commit": commit,
        "source_sha256": _sha256(source_path),
        "dataset_sha256": _sha256(colon_path),
        "features_sha256": _sha256(features_path),
    }
    return src, metadata


def _parse_result(stdout: str) -> dict[str, Any]:
    matches = [
        line[len(RESULT_PREFIX) :]
        for line in stdout.splitlines()
        if line.startswith(RESULT_PREFIX)
    ]
    if len(matches) != 1:
        raise SystemExit(f"expected one structured result, found {len(matches)}")
    try:
        result = json.loads(matches[0])
    except json.JSONDecodeError as exc:
        raise SystemExit(f"invalid structured result: {exc}") from exc

    expected = {
        "schema": "eu26-20-colon-old-v1",
        "profile": "author_source_compatibility",
        "dataset_rows": 62,
        "raw_features": 2000,
        "class_counts": [22, 40],
        "search_space_size": 128,
        "baseline_accuracy": 0.69,
    }
    for key, value in expected.items():
        if result.get(key) != value:
            raise SystemExit(f"source endpoint invariant failed: {key}={result.get(key)!r}")
    if result.get("class_labels") != [1, 2]:
        raise SystemExit(f"unexpected Colon labels: {result.get('class_labels')!r}")
    features = result.get("features")
    if not isinstance(features, list) or not features:
        raise SystemExit("missing final feature subset")
    if len(features) != len(set(features)) or len(features) != result.get("subset_length"):
        raise SystemExit("invalid final feature subset")
    value = result.get("best_accuracy")
    if not isinstance(value, (int, float)) or not 0.0 <= float(value) <= 1.0:
        raise SystemExit(f"invalid best_accuracy={value!r}")
    for metric in ("precision", "recall", "fscore"):
        value = result.get(metric)
        if value is not None and (
            not isinstance(value, (int, float)) or not 0.0 <= float(value) <= 1.0
        ):
            raise SystemExit(f"invalid metric {metric}={value!r}")
    if int(result.get("nfe", 0)) <= 0 or int(result.get("iterations", 0)) <= 0:
        raise SystemExit("invalid effort accounting")
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("upstream", type=Path)
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--output-json", type=Path)
    parser.add_argument("--log-file", type=Path)
    parser.add_argument("--quiet", action="store_true")
    parser.add_argument("--retain-generated", type=Path)
    args = parser.parse_args()

    root = args.upstream.resolve()
    generated, metadata = _prepare_source(root, args.seed)
    target = (
        args.retain_generated.resolve()
        if args.retain_generated
        else Path(os.environ.get("RUNNER_TEMP", "/tmp"))
        / f"eu26-20-colon-seed-{args.seed}.py"
    )
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(generated, encoding="utf-8")

    completed = subprocess.run(
        [sys.executable, str(target)],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    stdout = completed.stdout
    if args.log_file:
        args.log_file.parent.mkdir(parents=True, exist_ok=True)
        args.log_file.write_text(stdout, encoding="utf-8")
    if not args.quiet:
        print(stdout, end="")
    if completed.returncode:
        raise SystemExit(completed.returncode)

    result = _parse_result(stdout)
    result.update(metadata)
    if args.output_json:
        args.output_json.parent.mkdir(parents=True, exist_ok=True)
        args.output_json.write_text(
            json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
    print(RESULT_PREFIX + json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
