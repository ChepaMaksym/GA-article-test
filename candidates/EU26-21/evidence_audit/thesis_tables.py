"""Descriptive post-outcome tables from one authenticated, immutable campaign.

No optimizer, classifier, dataset loader, model deserializer or inferential
analysis is executed. The fixed campaign's decisions are copied unchanged.
"""
from __future__ import annotations

import argparse
import csv
import math
import os
from pathlib import Path
import statistics

from common_bridge import fetch_source_artifacts as source

RUN_ID = 34233477859
SOURCE_SHA = "79c9b154206cdc3d318b90b598c7f0f48ca02b53"
SOURCE_REF = "refs/tags/eu26-21-common-bridge-evidence-v2"
PROTOCOL_SHA = "730cd436db59d23da7dab5e24c49bc7b28d65379136fad7fd2d2370e0a436205"
PROTOCOL_ID = "EU26-21-COMMON-WBA-BSF-AUC-400-V1"
ARMS = ("chc_harmonized", "lambda_no_reset")
METRICS = ("validation_wba", "test_wba", "features", "bsf_auc", "calls")
AUC_KEY = "normalized_auc_best_so_far_validation_wba_1_400"
DECISION_NOTE = (
    "Descriptive post-outcome report; all 30 seed pairs are retained. "
    "The fixed campaign decision is FAIL_NONINFERIORITY. Efficiency and "
    "subset-size claims remain BLOCKED_BY_QUALITY_NONINFERIORITY. "
    "No bootstrap, hypothesis test, or scientific decision is recomputed here."
)
REPORT_HASHES = {
    "campaign-report.json": "b3696b0369e9e42053ef1563dc881bf470a2c5e07f75227921bf80dfd6c26f1e",
    "reaggregated-report.json": "372ac18ab11b614b43ef93514b7d07393e92a130905c3a8e214482df523d29bb",
}


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def _score(value: object) -> float:
    _require(type(value) in (int, float), "score must be numeric")
    _require(math.isfinite(value) and 0 <= value <= 1, "score outside [0,1]")
    return float(value)


def preserved_analysis(evidence_dir: Path):
    reports = []
    for name, digest in REPORT_HASHES.items():
        path = evidence_dir / name
        _require(source._file_sha256(path) == digest, "published report byte SHA mismatch")
        report = source._load_json(path)
        _require(report.get("schema") == "eu26-21-common-bridge-report-v1", "report schema mismatch")
        reports.append(report["analysis"])
    _require(reports[0] == reports[1], "campaign and independent reaggregation disagree")
    return reports[0]


def load_pairs(rows_dir: Path, expected_path: Path, verified_path: Path):
    """Bind fixed artifact identities, file bytes and all plotted observations."""
    expected = source.validate_expected_artifact_ledger(
        source._load_json(expected_path), repository=os.environ["GITHUB_REPOSITORY"],
        source_run_id=RUN_ID,
    )
    identity = {"source_run_attempt": 1, "source_head_sha": SOURCE_SHA,
                "source_workflow_sha": SOURCE_SHA, "source_ref": SOURCE_REF}
    _require(all(expected[key] == value for key, value in identity.items()), "wrong campaign")
    verified = source._load_json(verified_path)
    _require(verified.get("schema") == source.OUTPUT_SCHEMA, "verification schema mismatch")
    _require(verified.get("verification_status") == "PASS", "artifact verification failed")
    _require(verified.get("expected_ledger_sha256") == source._file_sha256(expected_path),
             "expected ledger byte SHA mismatch")
    for key in ("repository", "source_run_id", "source_workflow_path", *identity):
        _require(verified.get(key) == expected[key], f"verification {key} mismatch")
    artifacts = verified["artifacts"]
    _require(len(artifacts) == 30, "missing source seed")
    artifacts = sorted(artifacts, key=lambda item: item["seed"])
    _require([item["seed"] for item in artifacts] == list(source.EXPECTED_SEEDS),
             "invalid or duplicate seed ledger")
    pairs, curves, input_files = [], {arm: [] for arm in ARMS}, []
    for entry, fixed in zip(artifacts, expected["artifacts"]):
        _require(all(entry.get(key) == value for key, value in fixed.items()),
                 "fixed artifact identity mismatch")
        _require(entry.get("downloaded_zip_sha256") == fixed["digest"][7:]
                 and entry.get("api_run_id") == RUN_ID
                 and entry.get("api_head_sha") == SOURCE_SHA, "ZIP/run binding mismatch")
        seed, paths = entry["seed"], {}
        for item in entry["extracted_files"]:
            relative = source._safe_member_path(item["path"])
            path = rows_dir.joinpath(*relative.parts).resolve()
            _require(path.is_relative_to(rows_dir.resolve()), "input path escapes root")
            _require(path.name not in paths, "duplicate input filename")
            _require(path.stat().st_size == item["bytes"]
                     and source._file_sha256(path) == item["sha256"], "input byte/hash mismatch")
            paths[path.name] = path
            input_files.append(dict(item))
        names = {f"seed-{seed}{suffix}" for suffix in (
            ".json", "-status.json", "-manifest.json", "-chc-trace.json",
            "-lambda-trace.json", "-chc-model.joblib", "-lambda-model.joblib")}
        _require(set(paths) == names, "source artifact does not contain the seven seed files")
        row = source._load_json(paths[f"seed-{seed}.json"])
        _require(row.get("schema") == "eu26-21-common-bridge-row-v1"
                 and type(row.get("seed")) is int and row["seed"] == seed
                 and row.get("protocol_id") == PROTOCOL_ID,
                 "row schema/seed/protocol mismatch")
        provenance = row["provenance"]
        for key, value in {"run_id": RUN_ID, "run_attempt": 1, "implementation_sha": SOURCE_SHA,
                           "workflow_sha": SOURCE_SHA, "ref": SOURCE_REF,
                           "protocol_sha256": PROTOCOL_SHA, "artifact_name": fixed["name"]}.items():
            _require(provenance.get(key) == value, f"row {key} mismatch")
        _require(set(row["arms"]) == set(ARMS), "row arm mismatch")
        pair, first_fifty = {"seed": seed}, []
        for arm, suffix in zip(ARMS, ("chc", "lambda")):
            result = row["arms"][arm]
            trace_path = paths[f"seed-{seed}-{suffix}-trace.json"]
            _require(result["trace_file"] == trace_path.name
                     and result["trace_sha256"] == source._file_sha256(trace_path),
                     "row/trace byte binding mismatch")
            trace = source._load_json(trace_path)
            _require(trace.get("schema") == "eu26-21-common-bridge-trace-v1"
                     and type(trace.get("seed")) is int and trace["seed"] == seed
                     and trace.get("arm") == arm
                     and trace["provenance"].get("protocol_sha256") == PROTOCOL_SHA,
                     "trace identity mismatch")
            records = trace["evaluations"]
            _require(len(records) == 400 and [r["call"] for r in records] == list(range(1, 401)),
                     "trace must contain all 400 ordered calls")
            primary = [_score(r["validation_weighted_balanced_accuracy"]) for r in records]
            curve = [_score(r["best_so_far_weighted_balanced_accuracy"]) for r in records]
            best = 0.0
            for value, observed in zip(primary, curve):
                best = max(best, value)
                _require(observed == best, "best-so-far trace mismatch")
            terminal = result["terminal"]
            _require(all(terminal[key] == trace["terminal"][key]
                         for key in ("call", "mask", "fitness", "selected_feature_count")),
                     "terminal row/trace mismatch")
            features = terminal["selected_feature_count"]
            _require(type(features) is int and 1 <= features <= 40, "invalid feature count")
            _require(type(result["objective_calls"]) is int and result["objective_calls"] == 400
                     and trace["objective_calls"] == 400, "call budget mismatch")
            auc = _score(result[AUC_KEY])
            _require(math.isclose(auc, statistics.fmean(curve), abs_tol=1e-12, rel_tol=0),
                     "AUC/trace mismatch")
            values = (_score(terminal["fitness"][0]),
                      _score(terminal["test_weighted_balanced_accuracy"]), features, auc, 400)
            pair.update({f"{arm}_{key}": value for key, value in zip(METRICS, values)})
            curves[arm].append(curve)
            first_fifty.append(records[:50])
        _require(first_fifty[0] == first_fifty[1], "initial 50 paired evaluations differ")
        pair.update({f"difference_{key}": pair[f"{ARMS[1]}_{key}"] - pair[f"{ARMS[0]}_{key}"]
                     for key in METRICS})
        pairs.append(pair)
    return pairs, curves, {"source": expected, "inputs": input_files,
                           "expected_ledger_sha256": source._file_sha256(expected_path),
                           "verified_ledger_sha256": source._file_sha256(verified_path)}


def write_report(pairs, curves, provenance, analysis, output_dir: Path):
    """Write arm medians, all paired rows and two explicitly descriptive plots."""
    _require([pair["seed"] for pair in pairs] == list(source.EXPECTED_SEEDS), "invalid report seeds")
    for endpoint, metric in (("quality_noninferiority", "test_wba"), ("auc_superiority", "bsf_auc"),
                             ("feature_count_secondary", "features")):
        _require(analysis[endpoint]["paired_values"] == [p[f"difference_{metric}"] for p in pairs],
                 "descriptive rows disagree with preserved analysis pairs")
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    output_dir.mkdir(parents=True, exist_ok=False)
    with (output_dir / "paired-seeds.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(pairs[0]))
        writer.writeheader()
        writer.writerows(pairs)
    lines = ["# Census common bridge: descriptive thesis tables", "", DECISION_NOTE, "",
             f"Source run: {RUN_ID}, attempt 1; source SHA: `{SOURCE_SHA}`.",
             f"Protocol: `{PROTOCOL_ID}`, SHA-256 `{PROTOCOL_SHA}`.", "",
             "Values below are arm medians over 30 seeds; WBA uses the 0–1 scale.", "",
             "| Arm | Terminal validation WBA | Test WBA | Features | BSF-AUC | Calls |",
             "| --- | ---: | ---: | ---: | ---: | ---: |"]
    for arm in ARMS:
        medians = [statistics.median(pair[f"{arm}_{key}"] for pair in pairs) for key in METRICS]
        lines.append(f"| {arm} | " + " | ".join(f"{value:.6g}" for value in medians) + " |")
    lines += ["", "BSF-AUC measures validation progress per logical call, not ROC-AUC or time.",
              "The trajectory plot shows arithmetic means; it provides no confidence bands.",
              "The per-seed margin line is a reference, not a per-seed hypothesis decision.", "",
              "![Per-seed test WBA differences](test-wba-differences.png)", "",
              "![Mean best-so-far validation trajectories](mean-bsf-trajectories.png)", ""]
    (output_dir / "report.md").write_text("\n".join(lines), encoding="utf-8")
    fig, axis = plt.subplots(figsize=(10, 4), layout="constrained")
    axis.scatter([pair["seed"] for pair in pairs], [pair["difference_test_wba"] for pair in pairs])
    axis.axhline(0, color="black", linewidth=1, label="Zero difference")
    axis.axhline(-0.001, color="firebrick", linestyle="--", label="Frozen NI margin")
    axis.set(xlabel="Paired seed", ylabel="Test WBA: lambda minus CHC",
             title="All 30 seeds — descriptive differences; NI failed")
    axis.ticklabel_format(axis="x", style="plain", useOffset=False)
    axis.legend()
    fig.savefig(output_dir / "test-wba-differences.png", dpi=160)
    plt.close(fig)
    fig, axis = plt.subplots(figsize=(10, 4), layout="constrained")
    for arm in ARMS:
        axis.plot(range(1, 401), [statistics.fmean(values) for values in zip(*curves[arm])], label=arm)
    axis.set(xlabel="Logical objective call", ylabel="Mean best-so-far validation WBA",
             title="Descriptive mean trajectories — efficiency claim blocked")
    axis.legend()
    fig.savefig(output_dir / "mean-bsf-trajectories.png", dpi=160)
    plt.close(fig)
    source._write_json(output_dir / "report-manifest.json", {
        "schema": "eu26-21-descriptive-thesis-report-v1", **provenance,
        "protocol_id": PROTOCOL_ID, "protocol_sha256": PROTOCOL_SHA,
        "preserved_analysis": analysis, "preserved_report_sha256": REPORT_HASHES,
        "interpretation": DECISION_NOTE, "scientific_decisions_recomputed": False,
        "scientific_decisions_changed": False, "seed_ledger": list(source.EXPECTED_SEEDS),
        "report_run": {key: os.environ[key] for key in (
            "GITHUB_REPOSITORY", "GITHUB_RUN_ID", "GITHUB_RUN_ATTEMPT", "GITHUB_SHA",
            "GITHUB_REF", "THESIS_WORKFLOW_SHA")},
        "outputs": {path.name: {"bytes": path.stat().st_size, "sha256": source._file_sha256(path)}
                    for path in sorted(output_dir.iterdir())},
    })


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("rows-dir", "expected-ledger", "verified-ledger", "output-dir"):
        parser.add_argument(f"--{name}", type=Path, required=True)
    args = parser.parse_args()
    analysis = preserved_analysis(Path(__file__).resolve().parents[1] / "common_bridge" / "evidence")
    pairs, curves, provenance = load_pairs(args.rows_dir, args.expected_ledger, args.verified_ledger)
    write_report(pairs, curves, provenance, analysis, args.output_dir)


if __name__ == "__main__":
    main()
