from __future__ import annotations

import argparse
import json
import statistics
from pathlib import Path

from compare_source_native_old import (
    DIMENSION,
    PUBLISHED_MEAN_FE,
    PUBLISHED_MEAN_TOL,
    RUNS,
    download_reference,
    matrix_diff,
    parse_author_runs,
    read_reference,
    sha256_file,
)

CENSOR_FE = 100001


def tolerant_first_hits(runs):
    matrix = [[-1 for _ in range(RUNS)] for _ in range(DIMENSION + 1)]
    expected = {(i, DIMENSION - i): i for i in range(DIMENSION + 1)}
    completeness = []
    endpoints_censored = []
    endpoints_complete = []

    for run_index, events in enumerate(runs):
        seen = set()
        for evaluation, x, y in events:
            point = expected.get((x, y))
            if point is None or point in seen:
                continue
            matrix[point][run_index] = evaluation
            seen.add(point)

        missing = [point for point in range(DIMENSION + 1) if matrix[point][run_index] < 0]
        complete = not missing
        observed = [matrix[p][run_index] for p in range(DIMENSION + 1) if matrix[p][run_index] >= 0]
        endpoint = max(observed) if complete else CENSOR_FE
        endpoints_censored.append(endpoint)
        if complete:
            endpoints_complete.append(max(observed))
        completeness.append(
            {
                "run": run_index,
                "complete": complete,
                "observed_points": len(seen),
                "missing_point_indexes": missing,
                "censored_endpoint_fe": endpoint,
            }
        )

    return matrix, endpoints_censored, endpoints_complete, completeness


def observed_cell_diff(source, reference):
    mismatch = 0
    compared = 0
    examples = []
    for point in range(DIMENSION + 1):
        for run in range(RUNS):
            value = source[point][run]
            if value < 0:
                continue
            compared += 1
            if value != reference[point][run]:
                mismatch += 1
                if len(examples) < 30:
                    examples.append(
                        {
                            "point_index": point,
                            "run": run,
                            "source": value,
                            "reference": reference[point][run],
                            "difference": value - reference[point][run],
                        }
                    )
    return {"compared_cells": compared, "mismatch_count": mismatch, "examples": examples}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--author-output-root", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--compiler-label", required=True)
    parser.add_argument("--gsemo-sha", required=True)
    parser.add_argument("--ioh-sha", required=True)
    args = parser.parse_args()

    output = Path(args.output_dir).resolve()
    output.mkdir(parents=True, exist_ok=True)
    work = output / "work"
    work.mkdir(exist_ok=True)

    archive, archive_sha, archive_url = download_reference(work)
    reference_matrix, reference_endpoints, reference_member_sha = read_reference(archive)
    source_runs, source_info = parse_author_runs(Path(args.author_output_root).resolve())
    source_matrix, source_censored, source_complete, completeness = tolerant_first_hits(source_runs)

    complete_runs = [entry["run"] for entry in completeness if entry["complete"]]
    incomplete_runs = [entry["run"] for entry in completeness if not entry["complete"]]
    full_diff = matrix_diff(source_matrix, reference_matrix)
    observed_diff = observed_cell_diff(source_matrix, reference_matrix)

    exact_matrix = full_diff["mismatch_count"] == 0
    exact_endpoints = (
        len(complete_runs) == RUNS
        and all(a == b for a, b in zip(source_censored, reference_endpoints))
    )
    reference_mean = statistics.fmean(reference_endpoints)
    paper_raw_ok = abs(reference_mean - PUBLISHED_MEAN_FE) <= PUBLISHED_MEAN_TOL
    exact_replay = exact_matrix and exact_endpoints and paper_raw_ok

    report = {
        "schema": "eu26-27-historical-environment-probe-v1",
        "research_tag": "RESEARCH_2",
        "compiler_label": args.compiler_label,
        "gsemo_sha": args.gsemo_sha,
        "ioh_sha": args.ioh_sha,
        "decision": "EXACT_MATCH" if exact_replay else "NO_EXACT_MATCH",
        "source_native": {
            **source_info,
            "runs": RUNS,
            "complete_run_count": len(complete_runs),
            "incomplete_runs": incomplete_runs,
            "censored_mean_fe": statistics.fmean(source_censored),
            "censored_median_fe": statistics.median(source_censored),
            "complete_run_mean_fe": statistics.fmean(source_complete) if source_complete else None,
            "complete_run_median_fe": statistics.median(source_complete) if source_complete else None,
            "completeness": completeness,
        },
        "reference": {
            "archive_sha256": archive_sha,
            "member_sha256": reference_member_sha,
            "download_url_used": archive_url,
            "mean_fe": reference_mean,
            "median_fe": statistics.median(reference_endpoints),
            "published_mean_fe": PUBLISHED_MEAN_FE,
            "published_raw_alignment": paper_raw_ok,
        },
        "exact_first_hit_matrix_match": exact_matrix,
        "exact_endpoint_vector_match": exact_endpoints,
        "full_matrix_diff": full_diff,
        "observed_cell_diff": observed_diff,
        "scientific_note": (
            "Censored endpoint 100001 is diagnostic only. It cannot turn an incomplete run into a PASS. "
            "The sole PASS condition is exact raw replay under the preregistered source-native gate."
        ),
    }

    report_path = output / "report.json"
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    manifest = {"report.json": sha256_file(report_path)}
    (output / "SHA256SUMS.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    lines = [
        f"# Historical environment probe — {args.compiler_label}",
        "",
        "```text",
        f"decision: {report['decision']}",
        f"complete runs: {len(complete_runs)}/{RUNS}",
        f"incomplete runs: {incomplete_runs}",
        f"source censored mean FE: {report['source_native']['censored_mean_fe']:.6f}",
        f"reference mean FE: {reference_mean:.6f}",
        f"exact first-hit matrix: {exact_matrix}",
        f"exact endpoint vector: {exact_endpoints}",
        f"observed-cell mismatches: {observed_diff['mismatch_count']}/{observed_diff['compared_cells']}",
        "```",
        "",
        "This diagnostic exits successfully even for a scientific mismatch so every frozen environment is retained. "
        "The binder, not this job exit code, decides whether any environment exactly reproduces Zenodo.",
    ]
    (output / "summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
