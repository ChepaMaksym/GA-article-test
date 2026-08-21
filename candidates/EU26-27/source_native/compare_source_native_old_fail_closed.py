from __future__ import annotations

import argparse
import json
import os
import statistics
from pathlib import Path
from typing import Any

import compare_source_native_old as old

BUDGET_FE = 100000
CENSORED_ENDPOINT_FE = BUDGET_FE + 1


def source_first_hits_fail_closed(
    runs: list[list[tuple[int, int, int]]],
) -> tuple[list[list[int]], list[int], list[int], dict[int, int]]:
    """Extract first hits without discarding incomplete runs.

    Missing Pareto points stay at -1 in the raw source matrix.  For endpoint
    distribution summaries only, an incomplete run is right-censored at
    BUDGET_FE + 1.  Exact-replay gates are always false when any source cell is
    missing; censoring is never treated as a successful endpoint.
    """
    matrix: list[list[int]] = [[-1 for _ in range(old.RUNS)] for _ in range(old.DIMENSION + 1)]
    expected = {(i, old.DIMENSION - i): i for i in range(old.DIMENSION + 1)}
    incomplete_runs: list[int] = []
    missing_by_run: dict[int, int] = {}
    endpoints: list[int] = []

    for run_index, events in enumerate(runs):
        seen: set[int] = set()
        for evaluation, x, y in events:
            point = expected.get((x, y))
            if point is None or point in seen:
                continue
            matrix[point][run_index] = evaluation
            seen.add(point)

        missing = (old.DIMENSION + 1) - len(seen)
        if missing:
            incomplete_runs.append(run_index)
            missing_by_run[run_index] = missing
            endpoints.append(CENSORED_ENDPOINT_FE)
        else:
            endpoints.append(max(matrix[p][run_index] for p in range(old.DIMENSION + 1)))

    return matrix, endpoints, incomplete_runs, missing_by_run


def matrix_diff_fail_closed(source: list[list[int]], reference: list[list[int]]) -> dict[str, Any]:
    missing_source_cells = 0
    observed_mismatch_count = 0
    exact_mismatch_count = 0
    max_abs_observed_difference = 0
    examples: list[dict[str, Any]] = []

    for point in range(old.DIMENSION + 1):
        for run in range(old.RUNS):
            sv = source[point][run]
            rv = reference[point][run]
            if sv < 0:
                missing_source_cells += 1
                exact_mismatch_count += 1
                if len(examples) < 25:
                    examples.append(
                        {"point_index": point, "run": run, "source": None, "reference": rv, "kind": "missing_source_hit"}
                    )
                continue
            if sv != rv:
                observed_mismatch_count += 1
                exact_mismatch_count += 1
                max_abs_observed_difference = max(max_abs_observed_difference, abs(sv - rv))
                if len(examples) < 25:
                    examples.append(
                        {"point_index": point, "run": run, "source": sv, "reference": rv, "kind": "value_mismatch"}
                    )

    return {
        "exact_mismatch_count": exact_mismatch_count,
        "missing_source_cells": missing_source_cells,
        "observed_mismatch_count": observed_mismatch_count,
        "max_abs_observed_difference": max_abs_observed_difference,
        "examples": examples,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--author-output-root", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--gsemo-sha", required=True)
    parser.add_argument("--ioh-sha", required=True)
    parser.add_argument("--runner-os", default=os.environ.get("RUNNER_OS", "unknown"))
    args = parser.parse_args()

    output = Path(args.output_dir).resolve()
    output.mkdir(parents=True, exist_ok=True)
    work = output / "work"
    work.mkdir(exist_ok=True)

    archive, archive_sha, archive_url = old.download_reference(work)
    reference_matrix, reference_endpoints, reference_member_sha = old.read_reference(archive)
    source_runs, source_info = old.parse_author_runs(Path(args.author_output_root).resolve())
    source_matrix, source_endpoints_censored, incomplete_runs, missing_by_run = source_first_hits_fail_closed(source_runs)

    diff = matrix_diff_fail_closed(source_matrix, reference_matrix)
    complete_runs = old.RUNS - len(incomplete_runs)

    endpoint_mismatches: list[dict[str, Any]] = []
    for run, (source_value, reference_value) in enumerate(zip(source_endpoints_censored, reference_endpoints)):
        if run in missing_by_run:
            endpoint_mismatches.append(
                {
                    "run": run,
                    "source": None,
                    "source_censored_at": CENSORED_ENDPOINT_FE,
                    "reference": reference_value,
                    "kind": "incomplete_source_run",
                }
            )
        elif source_value != reference_value:
            endpoint_mismatches.append(
                {
                    "run": run,
                    "source": source_value,
                    "reference": reference_value,
                    "difference": source_value - reference_value,
                    "kind": "endpoint_value_mismatch",
                }
            )

    reference_mean = statistics.fmean(reference_endpoints)
    reference_median = statistics.median(reference_endpoints)
    source_censored_mean = statistics.fmean(source_endpoints_censored)
    source_censored_median = statistics.median(source_endpoints_censored)
    complete_source_endpoints = [
        value for run, value in enumerate(source_endpoints_censored) if run not in missing_by_run
    ]
    source_complete_only_mean = statistics.fmean(complete_source_endpoints) if complete_source_endpoints else None
    source_complete_only_median = statistics.median(complete_source_endpoints) if complete_source_endpoints else None

    paper_raw_ok = abs(reference_mean - old.PUBLISHED_MEAN_FE) <= old.PUBLISHED_MEAN_TOL
    exact_matrix = diff["exact_mismatch_count"] == 0
    exact_endpoints = not endpoint_mismatches
    decision = (
        "PASS_SOURCE_NATIVE_OLD"
        if exact_matrix and exact_endpoints and paper_raw_ok
        else "FAIL_SOURCE_NATIVE_OLD"
    )

    old.write_ecdf_svg(output / "endpoint_ecdf.svg", reference_endpoints, source_endpoints_censored)
    old.write_run_scatter_svg(output / "run_by_run.svg", reference_endpoints, source_endpoints_censored)

    report = {
        "schema": "eu26-27-source-native-old-report-v3-fail-closed",
        "decision": decision,
        "research_tag": "RESEARCH_2",
        "old_implementation": "FurongYe/GSEMO exact paper-era source",
        "gsemo_sha": args.gsemo_sha,
        "iohexperimenter_sha": args.ioh_sha,
        "runner_os": args.runner_os,
        "protocol": {
            "problem": "OneMinMax",
            "dimension": old.DIMENSION,
            "algorithm": "TwoRate",
            "lambda": 10,
            "initial_pm": 1 / old.DIMENSION,
            "adapt_metric": "HV",
            "budget_fe": BUDGET_FE,
            "runs": old.RUNS,
            "global_rng_seed": 10,
            "execution": "100 sequential runs in one global RNG stream",
            "censoring_rule_for_summaries_only": CENSORED_ENDPOINT_FE,
            "censoring_can_satisfy_exact_gate": False,
        },
        "reference": {
            "zenodo_record": old.ZENODO_RECORD,
            "member": old.REFERENCE_MEMBER,
            "download_url_used": archive_url,
            "archive_sha256": archive_sha,
            "member_sha256": reference_member_sha,
            "runs": len(reference_endpoints),
            "mean_fe": reference_mean,
            "median_fe": reference_median,
            "published_mean_fe": old.PUBLISHED_MEAN_FE,
            "published_mean_tolerance": old.PUBLISHED_MEAN_TOL,
            "published_raw_alignment": paper_raw_ok,
        },
        "source_native": {
            "runs": old.RUNS,
            "complete_runs": complete_runs,
            "incomplete_runs": incomplete_runs,
            "missing_pareto_points_by_run": {str(k): v for k, v in sorted(missing_by_run.items())},
            "censored_endpoint_fe": CENSORED_ENDPOINT_FE,
            "censored_mean_fe": source_censored_mean,
            "censored_median_fe": source_censored_median,
            "complete_only_mean_fe": source_complete_only_mean,
            "complete_only_median_fe": source_complete_only_median,
            **source_info,
        },
        "exact_first_hit_matrix_match": exact_matrix,
        "first_hit_matrix_diff": diff,
        "exact_endpoint_vector_match": exact_endpoints,
        "endpoint_mismatch_count": len(endpoint_mismatches),
        "endpoint_mismatch_examples": endpoint_mismatches[:25],
        "claim_boundary": {
            "hybrid_authorized": decision == "PASS_SOURCE_NATIVE_OLD",
            "historical_exact_replay_claim": decision == "PASS_SOURCE_NATIVE_OLD",
            "aggregate_similarity_can_authorize_hybrid": False,
            "wall_clock_claim": False,
            "worker_parallelism_claim": False,
            "note": (
                "Incomplete runs are retained and censored only for descriptive endpoint summaries. "
                "They force both exact replay gates to fail. The historical OLD remains a sequential "
                "global-RNG batch; parallelizing it would change the experiment."
            ),
        },
    }

    report_path = output / "report.json"
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    manifest = {
        "report.json": old.sha256_file(report_path),
        "endpoint_ecdf.svg": old.sha256_file(output / "endpoint_ecdf.svg"),
        "run_by_run.svg": old.sha256_file(output / "run_by_run.svg"),
    }
    (output / "SHA256SUMS.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    summary = [
        "# EU26-27 source-native OLD — fail-closed report",
        "",
        "```text",
        f"decision: {decision}",
        f"complete source runs: {complete_runs}/{old.RUNS}",
        f"incomplete source runs: {incomplete_runs}",
        f"reference mean FE: {reference_mean:.6f}",
        f"source censored mean FE: {source_censored_mean:.6f}",
        f"reference median FE: {reference_median:.6f}",
        f"source censored median FE: {source_censored_median:.6f}",
        f"missing source first-hit cells: {diff['missing_source_cells']}",
        f"observed first-hit mismatches: {diff['observed_mismatch_count']}",
        f"exact first-hit matrix: {exact_matrix}",
        f"exact endpoint vector: {exact_endpoints}",
        f"published {old.PUBLISHED_MEAN_FE:.0f} alignment of Zenodo raw mean: {paper_raw_ok}",
        "```",
        "",
        "Censoring is descriptive only and cannot satisfy the exact replay gate.",
        "HYBRID is authorized only when the decision is PASS_SOURCE_NATIVE_OLD.",
    ]
    (output / "summary.md").write_text("\n".join(summary) + "\n", encoding="utf-8")
    print("\n".join(summary))
    return 0 if decision == "PASS_SOURCE_NATIVE_OLD" else 2


if __name__ == "__main__":
    raise SystemExit(main())
