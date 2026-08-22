from __future__ import annotations

import argparse
import json
import statistics
from pathlib import Path

import compare_source_native_old as old

PAPER_MEAN_FE = 61624.0
PAPER_MEAN_TOL = 1.0
DEFAULT_SAFETY_CAP_FE = 10_000_000


def extract_first_hits(runs: list[list[tuple[int, int, int]]]):
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


def matrix_diff(source: list[list[int]], reference: list[list[int]]):
    mismatches = 0
    missing = 0
    examples = []
    for point in range(old.DIMENSION + 1):
        for run in range(old.RUNS):
            sv = source[point][run]
            rv = reference[point][run]
            if sv < 0:
                missing += 1
                mismatches += 1
                if len(examples) < 25:
                    examples.append({"point": point, "run": run, "source": None, "reference": rv})
            elif sv != rv:
                mismatches += 1
                if len(examples) < 25:
                    examples.append({"point": point, "run": run, "source": sv, "reference": rv})
    return {"mismatch_count": mismatches, "missing_count": missing, "examples": examples}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--author-output-root", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--gsemo-sha", required=True)
    parser.add_argument("--ioh-sha", required=True)
    parser.add_argument("--safety-cap-fe", type=int, default=DEFAULT_SAFETY_CAP_FE)
    args = parser.parse_args()

    output = Path(args.output_dir).resolve()
    output.mkdir(parents=True, exist_ok=True)
    work = output / "work"
    work.mkdir(exist_ok=True)

    archive, archive_sha, archive_url = old.download_reference(work)
    reference_matrix, reference_endpoints, reference_member_sha = old.read_reference(archive)

    # The paper reports FEs until the entire Pareto front is obtained and does
    # not state a 100k cap in the experimental setup. The executable itself
    # stops early once the full Pareto front is found. Therefore a large cap is
    # used only as a non-binding safety ceiling, not as a claimed paper value.
    max_reference_endpoint = max(reference_endpoints)
    if max_reference_endpoint >= args.safety_cap_fe:
        raise RuntimeError(
            f"safety cap {args.safety_cap_fe} is binding for reference endpoint {max_reference_endpoint}"
        )

    source_runs, source_info = old.parse_author_runs(Path(args.author_output_root).resolve())
    source_matrix, source_endpoints, incomplete_runs = extract_first_hits(source_runs)
    diff = matrix_diff(source_matrix, reference_matrix)

    endpoint_mismatches = []
    for run, (source, reference) in enumerate(zip(source_endpoints, reference_endpoints)):
        if source is None:
            endpoint_mismatches.append({"run": run, "source": None, "reference": reference, "kind": "incomplete"})
        elif source != reference:
            endpoint_mismatches.append(
                {"run": run, "source": source, "reference": reference, "difference": source - reference}
            )

    paper_raw_mean = statistics.fmean(reference_endpoints)
    paper_raw_ok = abs(paper_raw_mean - PAPER_MEAN_FE) <= PAPER_MEAN_TOL
    exact_matrix = diff["mismatch_count"] == 0
    exact_endpoints = not endpoint_mismatches
    all_complete = not incomplete_runs
    decision = (
        "PASS_PAPER_FAITHFUL_OLD"
        if all_complete and exact_matrix and exact_endpoints and paper_raw_ok
        else "FAIL_PAPER_FAITHFUL_OLD"
    )

    complete_source_endpoints = [value for value in source_endpoints if value is not None]
    source_mean = statistics.fmean(complete_source_endpoints) if complete_source_endpoints else None

    report = {
        "schema": "eu26-27-paper-faithful-old-v1",
        "decision": decision,
        "paper": {
            "title": "Towards Self-adaptive Mutation in Evolutionary Multi-Objective Algorithms",
            "problem": "OneMinMax",
            "dimension": 100,
            "algorithm": "two-rate GSEMO",
            "metric": "HV",
            "lambda": 10,
            "runs": 100,
            "table_1_mean_fe": PAPER_MEAN_FE,
            "stop_semantics": "function evaluations until the entire Pareto front is obtained",
            "explicit_100k_budget_in_experimental_setup": False,
        },
        "execution": {
            "safety_cap_fe": args.safety_cap_fe,
            "safety_cap_is_claimed_paper_budget": False,
            "max_reference_endpoint_fe": max_reference_endpoint,
            "gsemo_sha": args.gsemo_sha,
            "ioh_sha": args.ioh_sha,
            "global_rng_seed": 10,
            "runs_are_sequential_single_rng_stream": True,
            **source_info,
        },
        "reference": {
            "zenodo_record": old.ZENODO_RECORD,
            "member": old.REFERENCE_MEMBER,
            "archive_sha256": archive_sha,
            "member_sha256": reference_member_sha,
            "download_url_used": archive_url,
            "mean_fe": paper_raw_mean,
            "published_mean_alignment": paper_raw_ok,
        },
        "source": {
            "complete_runs": old.RUNS - len(incomplete_runs),
            "incomplete_runs": incomplete_runs,
            "mean_fe_complete_runs": source_mean,
        },
        "exact_first_hit_matrix_match": exact_matrix,
        "matrix_diff": diff,
        "exact_endpoint_vector_match": exact_endpoints,
        "endpoint_mismatch_count": len(endpoint_mismatches),
        "endpoint_mismatch_examples": endpoint_mismatches[:25],
        "hybrid_authorized": decision == "PASS_PAPER_FAITHFUL_OLD",
    }

    report_path = output / "report.json"
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    summary = [
        "# EU26-27 paper-faithful OLD replay",
        "",
        "```text",
        f"decision: {decision}",
        f"complete source runs: {old.RUNS - len(incomplete_runs)}/{old.RUNS}",
        f"incomplete source runs: {incomplete_runs}",
        f"paper/Zenodo mean FE: {paper_raw_mean:.6f}",
        f"source mean FE: {source_mean if source_mean is not None else 'n/a'}",
        f"max Zenodo endpoint FE: {max_reference_endpoint}",
        f"non-binding safety cap FE: {args.safety_cap_fe}",
        f"exact first-hit matrix: {exact_matrix}",
        f"matrix mismatches: {diff['mismatch_count']}",
        f"exact endpoint vector: {exact_endpoints}",
        f"endpoint mismatches: {len(endpoint_mismatches)}",
        "```",
        "",
        "The paper measures function evaluations until the entire Pareto front is obtained.",
        "The 10,000,000 FE value is only a non-binding safety ceiling for replay; it is not asserted as a published budget.",
        "HYBRID is authorized only after PASS_PAPER_FAITHFUL_OLD.",
    ]
    (output / "summary.md").write_text("\n".join(summary) + "\n", encoding="utf-8")
    print("\n".join(summary))

    return 0 if decision == "PASS_PAPER_FAITHFUL_OLD" else 2


if __name__ == "__main__":
    raise SystemExit(main())
