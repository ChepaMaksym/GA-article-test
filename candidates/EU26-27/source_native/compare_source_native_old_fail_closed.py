from __future__ import annotations

import argparse
import json
import os
import statistics
from pathlib import Path
from typing import Any

import compare_source_native_old as old

PAPER_TITLE = "Towards Self-adaptive Mutation in Evolutionary Multi-Objective Algorithms"
PAPER_MEAN_FE = 61624.0
PAPER_MEAN_TOL = 1.0
DEFAULT_SAFETY_CAP_FE = 10_000_000


def extract_first_hits(
    runs: list[list[tuple[int, int, int]]],
) -> tuple[list[list[int]], list[int | None], list[int]]:
    """Extract the first hit of every OneMinMax Pareto point for every run.

    The paper measures FEs until the complete Pareto front is obtained. Missing
    Pareto points are therefore a hard replay failure; they are not censored or
    converted into synthetic endpoints.
    """
    matrix = [[-1 for _ in range(old.RUNS)] for _ in range(old.DIMENSION + 1)]
    expected = {(i, old.DIMENSION - i): i for i in range(old.DIMENSION + 1)}
    incomplete: list[int] = []
    endpoints: list[int | None] = []

    for run, events in enumerate(runs):
        seen: set[int] = set()
        for evaluation, x, y in events:
            point = expected.get((x, y))
            if point is None or point in seen:
                continue
            matrix[point][run] = evaluation
            seen.add(point)

        if len(seen) != old.DIMENSION + 1:
            incomplete.append(run)
            endpoints.append(None)
        else:
            endpoints.append(max(matrix[p][run] for p in range(old.DIMENSION + 1)))

    return matrix, endpoints, incomplete


def matrix_diff(source: list[list[int]], reference: list[list[int]]) -> dict[str, Any]:
    mismatches = 0
    missing = 0
    max_abs_difference = 0
    examples: list[dict[str, Any]] = []

    for point in range(old.DIMENSION + 1):
        for run in range(old.RUNS):
            source_value = source[point][run]
            reference_value = reference[point][run]
            if source_value < 0:
                missing += 1
                mismatches += 1
                if len(examples) < 25:
                    examples.append(
                        {
                            "point_index": point,
                            "run": run,
                            "source": None,
                            "reference": reference_value,
                            "kind": "missing_source_hit",
                        }
                    )
                continue
            if source_value != reference_value:
                mismatches += 1
                max_abs_difference = max(max_abs_difference, abs(source_value - reference_value))
                if len(examples) < 25:
                    examples.append(
                        {
                            "point_index": point,
                            "run": run,
                            "source": source_value,
                            "reference": reference_value,
                            "difference": source_value - reference_value,
                            "kind": "value_mismatch",
                        }
                    )

    return {
        "mismatch_count": mismatches,
        "missing_count": missing,
        "max_abs_difference": max_abs_difference,
        "examples": examples,
    }


def endpoint_diff(source: list[int | None], reference: list[int]) -> list[dict[str, Any]]:
    mismatches: list[dict[str, Any]] = []
    for run, (source_value, reference_value) in enumerate(zip(source, reference)):
        if source_value is None:
            mismatches.append(
                {
                    "run": run,
                    "source": None,
                    "reference": reference_value,
                    "kind": "incomplete_source_run",
                }
            )
        elif source_value != reference_value:
            mismatches.append(
                {
                    "run": run,
                    "source": source_value,
                    "reference": reference_value,
                    "difference": source_value - reference_value,
                    "kind": "endpoint_value_mismatch",
                }
            )
    return mismatches


def assert_non_binding_safety_cap(reference_endpoints: list[int], safety_cap_fe: int) -> None:
    max_reference_endpoint = max(reference_endpoints)
    if max_reference_endpoint >= safety_cap_fe:
        raise RuntimeError(
            f"safety cap {safety_cap_fe} is binding for authenticated reference endpoint "
            f"{max_reference_endpoint}"
        )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--author-output-root", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--gsemo-sha", required=True)
    parser.add_argument("--ioh-sha", required=True)
    parser.add_argument("--safety-cap-fe", type=int, default=DEFAULT_SAFETY_CAP_FE)
    parser.add_argument("--runner-os", default=os.environ.get("RUNNER_OS", "unknown"))
    args = parser.parse_args()

    output = Path(args.output_dir).resolve()
    output.mkdir(parents=True, exist_ok=True)
    work = output / "work"
    work.mkdir(exist_ok=True)

    archive, archive_sha, archive_url = old.download_reference(work)
    reference_matrix, reference_endpoints, reference_member_sha = old.read_reference(archive)
    assert_non_binding_safety_cap(reference_endpoints, args.safety_cap_fe)

    source_runs, source_info = old.parse_author_runs(Path(args.author_output_root).resolve())
    source_matrix, source_endpoints, incomplete_runs = extract_first_hits(source_runs)

    diff = matrix_diff(source_matrix, reference_matrix)
    endpoint_mismatches = endpoint_diff(source_endpoints, reference_endpoints)

    reference_mean = statistics.fmean(reference_endpoints)
    reference_median = statistics.median(reference_endpoints)
    complete_source_endpoints = [value for value in source_endpoints if value is not None]
    source_mean = statistics.fmean(complete_source_endpoints) if complete_source_endpoints else None
    source_median = statistics.median(complete_source_endpoints) if complete_source_endpoints else None

    paper_raw_ok = abs(reference_mean - PAPER_MEAN_FE) <= PAPER_MEAN_TOL
    all_complete = len(incomplete_runs) == 0
    exact_matrix = diff["mismatch_count"] == 0
    exact_endpoints = len(endpoint_mismatches) == 0

    decision = (
        "PASS_SOURCE_NATIVE_OLD"
        if all_complete and exact_matrix and exact_endpoints and paper_raw_ok
        else "FAIL_SOURCE_NATIVE_OLD"
    )

    # Preserve visual evidence while the pass/fail decision remains raw-data exact.
    if len(complete_source_endpoints) == old.RUNS:
        old.write_ecdf_svg(output / "endpoint_ecdf.svg", reference_endpoints, complete_source_endpoints)
        old.write_run_scatter_svg(output / "run_by_run.svg", reference_endpoints, complete_source_endpoints)

    report = {
        "schema": "eu26-27-source-native-old-v5-paper-faithful",
        "decision": decision,
        "research_tag": "RESEARCH_2",
        "paper": {
            "title": PAPER_TITLE,
            "problem": "OneMinMax",
            "dimension": old.DIMENSION,
            "algorithm": "two-rate GSEMO",
            "metric": "HV",
            "lambda": 10,
            "runs": old.RUNS,
            "table_1_mean_fe": PAPER_MEAN_FE,
            "stop_semantics": "function evaluations until the entire Pareto front is obtained",
            "explicit_100k_budget_in_experimental_setup": False,
        },
        "execution": {
            "author_source": "FurongYe/GSEMO exact paper-era source",
            "gsemo_sha": args.gsemo_sha,
            "iohexperimenter_sha": args.ioh_sha,
            "runner_os": args.runner_os,
            "problem": "OneMinMax",
            "dimension": old.DIMENSION,
            "algorithm": "TwoRate",
            "lambda": 10,
            "initial_pm": 1 / old.DIMENSION,
            "adapt_metric": "HV",
            "runs": old.RUNS,
            "global_rng_seed": 10,
            "execution_order": "100 sequential runs in one author global RNG stream",
            "safety_cap_fe": args.safety_cap_fe,
            "safety_cap_is_claimed_paper_budget": False,
            "max_authenticated_reference_endpoint_fe": max(reference_endpoints),
            "legacy_100k_cutoff_is_canonical": False,
            **source_info,
        },
        "reference": {
            "zenodo_record": old.ZENODO_RECORD,
            "member": old.REFERENCE_MEMBER,
            "download_url_used": archive_url,
            "archive_sha256": archive_sha,
            "member_sha256": reference_member_sha,
            "mean_fe": reference_mean,
            "median_fe": reference_median,
            "published_mean_fe": PAPER_MEAN_FE,
            "published_mean_tolerance": PAPER_MEAN_TOL,
            "published_raw_alignment": paper_raw_ok,
        },
        "source_native": {
            "runs": old.RUNS,
            "complete_runs": old.RUNS - len(incomplete_runs),
            "incomplete_runs": incomplete_runs,
            "mean_fe_complete_runs": source_mean,
            "median_fe_complete_runs": source_median,
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
            "legacy_100k_runs_are_diagnostic_only": True,
        },
    }

    report_path = output / "report.json"
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    manifest = {"report.json": old.sha256_file(report_path)}
    for name in ("endpoint_ecdf.svg", "run_by_run.svg"):
        path = output / name
        if path.is_file():
            manifest[name] = old.sha256_file(path)
    (output / "SHA256SUMS.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    summary = [
        "# EU26-27 canonical source-native OLD",
        "",
        "```text",
        f"decision: {decision}",
        f"complete source runs: {old.RUNS - len(incomplete_runs)}/{old.RUNS}",
        f"incomplete source runs: {incomplete_runs}",
        f"paper/Zenodo mean FE: {reference_mean:.6f}",
        f"source mean FE: {source_mean if source_mean is not None else 'n/a'}",
        f"reference median FE: {reference_median}",
        f"source median FE: {source_median if source_median is not None else 'n/a'}",
        f"max Zenodo endpoint FE: {max(reference_endpoints)}",
        f"non-binding safety cap FE: {args.safety_cap_fe}",
        f"exact first-hit matrix: {exact_matrix}",
        f"matrix mismatches: {diff['mismatch_count']}",
        f"exact endpoint vector: {exact_endpoints}",
        f"endpoint mismatches: {len(endpoint_mismatches)}",
        f"published {PAPER_MEAN_FE:.0f} alignment: {paper_raw_ok}",
        "```",
        "",
        "The paper reports FEs until the entire Pareto front is obtained; it does not state a 100,000-FE cap in the experimental setup.",
        "The safety cap is deliberately non-binding and is not asserted as a paper parameter.",
        "The former 100,000-FE replay is retained only as diagnostic evidence and cannot override this canonical gate.",
        "HYBRID is authorized only when this canonical decision is PASS_SOURCE_NATIVE_OLD.",
    ]
    (output / "summary.md").write_text("\n".join(summary) + "\n", encoding="utf-8")
    print("\n".join(summary))

    return 0 if decision == "PASS_SOURCE_NATIVE_OLD" else 2


if __name__ == "__main__":
    raise SystemExit(main())
