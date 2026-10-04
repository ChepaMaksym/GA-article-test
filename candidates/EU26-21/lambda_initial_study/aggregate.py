"""Complete-series validation, paired BCa analysis and figures; execution CI-only."""
from __future__ import annotations

import argparse
import csv
import math
from pathlib import Path
import re
import statistics
import warnings

import numpy as np
from scipy.stats import bootstrap

from corrected_applied.data_protocol import TRANSFORMED_FEATURE_NAMES
from local_optima_study.aggregate import validate_search_trace
from local_optima_study.contract import per_class_metrics
from lambda_initial_study.contract import (
    ALL_ARMS, CASE_SCHEMA, CASE_SEEDS, PROTOCOL_ID, PROTOCOL_SHA256, THIS_DIRECTORY,
    authenticate, canonical_sha256, file_sha256, mask_fitness,
    read_json, require, verify_manifest, write_json,
)

LABELS = {"chc_harmonized": "CHC", **{f"lambda_initial_{n}": f"Адаптивний, λ₀ = {n}"
                                        for n in (1, 5, 10, 20, 40)}}
AUC_KEY = "normalized_auc_best_so_far_validation_wba_51_400"


def validate_lambda_journal(trace: dict, initial_lambda: float) -> None:
    """Independently validate operators and transitions without training/RNG replay."""
    records, generations, state = trace["evaluations"], trace["generation_trace"], trace["terminal_state"]
    index = state["initial_parent_index"]
    require(type(index) is int and 0 <= index < 50, "invalid initial parent index")
    initial = [mask_fitness(row["mask"], row["fitness"]) for row in records[:50]]
    parent, fitness = initial[index]
    require(fitness == max(score for _, score in initial), "initial parent not best initial mask")
    cursor, value, any_tail = 50, float(initial_lambda), False
    require(bool(generations), "missing generation journal")
    for number, gen in enumerate(generations, 1):
        require(gen["generation"] == number and gen["calls_before"] == cursor,
                "generation index or starting call mismatch")
        require(gen["lambda_before"] == value and 1 <= value <= 40, "lambda bound/transition mismatch")
        planned = math.floor(value + .5)
        count = min(planned, (400 - cursor) // 2)
        finish = cursor + 2 * count
        require(count > 0 and gen["planned_offspring_count_per_phase"] == planned
                and gen["evaluated_offspring_count_per_phase"] == count
                and gen["calls_after"] == finish, "unbalanced generation or wrong tail count")
        require(gen["mutation_probability"] == value / 40 and gen["crossover_probability"] == 1 / value,
                "operators not based on actual lambda")
        require(tuple(gen["parent_before"]) == parent and tuple(gen["parent_fitness_before"]) == fitness,
                "wrong parent before generation")
        mutants, crossed = records[cursor:cursor + count], records[cursor + count:finish]
        for phase, rows in (("mutation", mutants), ("crossover", crossed)):
            require(len(rows) == count, "missing phase records")
            for i, row in enumerate(rows):
                require(row["phase"] == phase and row["phase_index"] == i and row["generation"] == number,
                        "wrong phase reference")
        strength = gen["mutation_strength"]
        require(type(strength) is int and 0 <= strength <= 40, "invalid mutation strength")
        values = [mask_fitness(row["mask"], row["fitness"]) for row in mutants]
        require(all(sum(a != b for a, b in zip(mask, parent)) == strength for mask, _ in values),
                "mutation Hamming distance differs from shared strength")
        chosen_index = gen["selected_mutant_index"]
        require(type(chosen_index) is int and 0 <= chosen_index < count, "invalid chosen mutant")
        chosen, chosen_score = values[chosen_index]
        require(chosen_score == max(score for _, score in values)
                and tuple(gen["selected_mutant_mask"]) == chosen
                and tuple(gen["selected_mutant_fitness"]) == chosen_score, "chosen mutant changed")
        crosses = [mask_fitness(row["mask"], row["fitness"]) for row in crossed]
        require(all(all(bit in (parent[i], chosen[i]) for i, bit in enumerate(mask)) for mask, _ in crosses),
                "crossover allele not inherited")
        if value == 1:
            require(all(mask == chosen for mask, _ in crosses), "lambda1 crossover not chosen mutant")
        if value == 40:
            require(strength == 40 and len({mask for mask, _ in values}) == 1,
                    "lambda40 did not preserve all complement duplicates")
        pool = [(chosen, chosen_score, "mutation", chosen_index)] + [
            (mask, score, "crossover", i) for i, (mask, score) in enumerate(crosses)]
        eligible = [item for item in pool if item[0] != parent]
        require(gen["eligible_count"] == len(eligible), "selection removed non-parent duplicates")
        candidate, score = mask_fitness(gen["candidate_mask"], gen["candidate_fitness"])
        reference = (candidate, score, gen["candidate_phase"], gen["candidate_phase_index"])
        require((reference in eligible and score == max(item[1] for item in eligible)) if eligible
                else reference == (parent, fitness, "parent", None), "invalid candidate selection")
        success, accepted = score > fitness, score >= fitness
        next_parent, next_fitness = (candidate, score) if accepted else (parent, fitness)
        next_value = max(1., value / 1.5) if success else min(40., value * 1.5 ** .25)
        require(gen["strict_success"] is success and gen["accepted"] is accepted
                and gen["parent_changed"] is (next_parent != parent), "acceptance/success mismatch")
        require(tuple(gen["parent_after"]) == next_parent and tuple(gen["parent_fitness_after"]) == next_fitness
                and gen["lambda_after"] == next_value and gen["reset_event"] is False, "post-generation state mismatch")
        require(gen["accepted_at_call"] == (finish if accepted and eligible else None), "acceptance call mismatch")
        require(gen["first_strict_improvement_call"] == next(
            (row["call"] for row in mutants + crossed if tuple(row["fitness"]) > fitness), None),
            "first improvement mismatch")
        require(gen["first_higher_start_wba_call"] is None and gen["accepted_higher_start_wba"] is False,
                "population run misrepresented as local escape")
        require(gen["tail_truncated"] is (count < planned), "tail flag mismatch")
        any_tail |= count < planned
        parent, fitness, value, cursor = next_parent, next_fitness, next_value, finish
    require(cursor == 400 and state["generation_count"] == len(generations)
            and state["final_lambda"] == value and tuple(state["parent_mask"]) == parent
            and tuple(state["parent_fitness"]) == fitness and state["tail_truncated"] is any_tail
            and state["parent_mask_sha256"] == canonical_sha256(list(parent)) and state["workers"] == 1,
            "terminal generation ledger mismatch")
    require(trace["termination_phase"] == ("paired_mutant_crossover_tail" if generations[-1]["tail_truncated"]
                                          else "complete_lambda_generation"), "wrong termination phase")


def validate_case(directory: Path, *, expected_sha: str, artifact: dict, source_run: int) -> dict:
    manifest = verify_manifest(directory / "manifest.json", expected_sha=expected_sha)
    row = read_json(directory / "case.json")
    require(row["schema"] == CASE_SCHEMA and row["seed"] in CASE_SEEDS
            and row["seed"] == manifest["seed"], "case schema or seed mismatch")
    require(row["provenance"] == manifest["provenance"] and row["provenance"]["run_id"] == source_run,
            "case provenance mismatch")
    require(row["artifact_name"] == artifact["name"] == manifest["artifact_name"], "source artifact name mismatch")
    named = re.fullmatch(r"eu26-21-lambda-case-([0-9]+)-([0-9]+)-([0-9]+)", artifact["name"])
    require(named is not None and tuple(map(int, named.groups())) ==
            (row["seed"], source_run, row["provenance"]["run_attempt"]), "artifact seed/run/attempt mismatch")
    require(row["feature_names"] == list(TRANSFORMED_FEATURE_NAMES) and set(row["arms"]) == set(ALL_ARMS),
            "feature mapping or six-arm completeness mismatch")
    require(row["counts"]["logical_validation_calls"] == 2400
            and row["counts"]["physical_validation_calls"] == 2150
            and row["counts"]["shared_initial_validation_calls"] == 50
            and row["counts"]["postinitial_validation_calls"] == 2100
            and row["counts"]["test_evaluations"] == 6, "physical/logical call totals mismatch")
    require(len(row["initial_masks"]) == 50 and len(row["initial_evaluations"]) == 50, "initial population count")
    require(row["pairing"]["initial_masks_sha256"] == canonical_sha256(row["initial_masks"])
            and row["pairing"]["first_50_evaluations_sha256"] == canonical_sha256(row["initial_evaluations"]),
            "initial population pairing hash mismatch")
    freeze_identity = row["terminal_masks_freeze"]
    require(freeze_identity["file"] == "terminal-masks.json"
            and freeze_identity["file"] in manifest["files"], "unlisted terminal freeze")
    require(file_sha256(directory / freeze_identity["file"]) == freeze_identity["sha256"], "mask freeze hash mismatch")
    freeze = read_json(directory / freeze_identity["file"])
    require(freeze["selected_by"] == "validation_only" and freeze["test_evaluations_so_far"] == 0
            and set(freeze["arms"]) == set(ALL_ARMS) and freeze["seed"] == row["seed"]
            and freeze["pairing"] == row["pairing"] and freeze["provenance"] == row["provenance"],
            "all masks not frozen before test or freeze provenance differs")
    traces = {}
    for arm in ALL_ARMS:
        record = row["arms"][arm]
        identity = record["trace"]
        require(identity["file"] in manifest["files"]
                and file_sha256(directory / identity["file"]) == identity["sha256"], "trace identity mismatch")
        trace = read_json(directory / identity["file"])
        require(trace["seed"] == row["seed"] and trace["arm"] == arm and trace["pairing"] == row["pairing"]
                and trace["implementation_sha"] == expected_sha and trace["protocol_id"] == PROTOCOL_ID,
                "trace provenance mismatch")
        validate_search_trace(trace)
        require(all(r["selected_feature_count"] == sum(r["mask"])
                    and r["mask_sha256"] == canonical_sha256(r["mask"]) for r in trace["evaluations"]),
                "evaluation mask hash/feature count mismatch")
        require(trace["terminal"]["selected_feature_count"] == sum(trace["terminal"]["mask"]),
                "terminal feature count mismatch")
        if arm != "chc_harmonized":
            validate_lambda_journal(trace, float(arm.rsplit("_", 1)[1]))
        first = [{"mask": r["mask"], "fitness": r.get("fitness", [r["validation_weighted_balanced_accuracy"],
                  r["negative_selected_feature_fraction"]])} for r in trace["evaluations"][:50]]
        require(first == row["initial_evaluations"] and [r["mask"] for r in first] == row["initial_masks"],
                "initial ordered scores differ across arms")
        require(record["terminal"] == trace["terminal"] == freeze["arms"][arm]
                and record["test_evaluations"] == 1 and record[AUC_KEY] == trace[AUC_KEY],
                "terminal/test/AUC record mismatch")
        ledger = record["evaluation_ledger"]
        require(ledger == trace["evaluation_ledger"], "row/trace accounting differs")
        require(ledger["logical_calls"] == 400 and ledger["initial_replayed_calls"] == 50
                and ledger["post_initial_physical_calls"] == 350
                and ledger["post_initialization_cache"] is False, "arm accounting mismatch")
        unique = len({tuple(r["mask"]) for r in trace["evaluations"]})
        require(ledger["unique_masks"] == unique and ledger["duplicate_queries"] == 400 - unique,
                "duplicate accounting mismatch")
        encountered = {tuple(r["mask"]) for r in trace["evaluations"][:50]}
        later_duplicates = 0
        for r in trace["evaluations"][50:]:
            value = tuple(r["mask"])
            later_duplicates += value in encountered
            encountered.add(value)
        require(ledger["post_initial_duplicate_queries"] == later_duplicates, "postinitial duplicate count mismatch")
        require(ledger["post_initial_actual_tree_fits"] == sum(bool(sum(r["mask"])) for r in trace["evaluations"][50:]),
                "post-initial tree-fit accounting mismatch")
        model = row["models"][arm]
        require(model["file"] in manifest["files"] and model["sha256"] == manifest["files"][model["file"]]["sha256"]
                and model["bytes"] == manifest["files"][model["file"]]["bytes"]
                and model["mask"] == record["terminal"]["mask"], "model identity mismatch")
        require(model["selected_feature_names"] == [name for name, bit in zip(row["feature_names"], model["mask"]) if bit],
                "selected feature name mismatch")
        for scale in ("weighted", "unweighted"):
            metrics = record["test_metrics"][scale]
            matrix = np.asarray(metrics["confusion_matrix"], dtype=float)
            require(matrix.shape == (2, 2) and np.isfinite(matrix).all() and (matrix >= 0).all(), "invalid confusion matrix")
            if scale == "unweighted":
                require(np.equal(matrix, np.floor(matrix)).all() and matrix.sum() == 99762, "incorrect record counts")
            require(metrics["classes"] == per_class_metrics(metrics["confusion_matrix"]), "incorrect class metrics")
            require(math.isclose(statistics.fmean(metrics["classes"][k]["recall"] for k in ("0", "1")),
                                 metrics["balanced_accuracy"], abs_tol=1e-12), "WBA not average recall")
        traces[arm] = trace
    require(len({traces[arm]["terminal_state"]["initial_parent_index"]
                 for arm in ALL_ARMS if arm != "chc_harmonized"}) == 1,
            "adaptive arms did not choose the same initial parent")
    shared = row["shared_initialization"]
    initial_fits = sum(bool(sum(mask)) for mask in row["initial_masks"])
    require(shared["physical_validation_calls"] == 50 and shared["actual_tree_fits"] == initial_fits
            and shared["unique_masks"] == len({tuple(m) for m in row["initial_masks"]})
            and shared["duplicate_queries"] == 50 - shared["unique_masks"]
            and shared["deduplication"] is False and shared["replay_is_position_checked"] is True,
            "shared initialization accounting mismatch")
    require(row["actual_validation_tree_fits"] == initial_fits + sum(
        row["arms"][arm]["evaluation_ledger"]["post_initial_actual_tree_fits"] for arm in ALL_ARMS),
        "total tree-fit accounting mismatch")
    return {"row": row, "traces": traces, "artifact": artifact,
            "manifest_sha256": file_sha256(directory / "manifest.json")}


def load_cases(root: Path, sources: dict, *, expected_sha: str, transport: dict) -> list[dict]:
    run_id = sources["source_run_id"]
    require(sources["schema"] == "eu26-21-lambda-initial-source-ledger-v1"
            and sources["implementation_sha"] == expected_sha
            and sources["protocol_sha256"] == PROTOCOL_SHA256, "source ledger contract mismatch")
    # Revalidate selection from all attempts, independently of downloaded contents.
    from lambda_initial_study.select_artifacts import select_artifacts
    recreated = select_artifacts({"artifacts": sources["attempts"]}, run_id=run_id, expected_sha=expected_sha)
    require(recreated["artifacts"] == sources["artifacts"], "source ledger no longer matches metadata-only policy")
    artifacts = {item["name"]: item for item in sources["artifacts"]}
    require(transport["schema"] == "eu26-21-exact-id-transport-ledger-v1"
            and transport["repository"] == "ChepaMaksym/GA-article-test"
            and transport["source_run_id"] == run_id and transport["implementation_sha"] == expected_sha
            and transport["complete"] is True and transport["kind"] == "lambda-case",
            "transport ledger identity mismatch")
    verified = transport["artifacts"]
    require(len(verified) == 30 and len({a["id"] for a in verified}) == 30, "transport completeness or duplicates")
    by_id = {a["id"]: a for a in verified}
    require(set(by_id) == {a["id"] for a in sources["artifacts"]}, "transport artifact IDs differ from fixed sources")
    for metadata in sources["artifacts"]:
        checked = by_id[metadata["id"]]
        require(all(checked[key] == metadata[key] for key in ("id", "name", "digest", "size_in_bytes"))
                and checked["zip_verified_before_extraction"] is True
                and checked["verified_zip_sha256"] == metadata["digest"][7:]
                and checked["verified_zip_bytes"] == metadata["size_in_bytes"], "transport ZIP digest/size mismatch")
    require({p.name for p in root.iterdir()} == set(artifacts), "download directories incomplete or contain extra files")
    cases = [validate_case(root / name, expected_sha=expected_sha, artifact=artifact, source_run=run_id)
             for name, artifact in artifacts.items()]
    require(len(cases) == 30 and {c["row"]["seed"] for c in cases} == set(CASE_SEEDS), "case completeness not 30/30")
    return sorted(cases, key=lambda c: c["row"]["seed"])


def paired_bca(differences: list[float], *, confidence: float, rng_seed: int) -> dict:
    """One difference per whole paired seed; equivalent to paired six-arm resampling."""
    require(all(math.isfinite(x) for x in differences), "nonfinite paired endpoint")
    result = {"estimate": statistics.fmean(differences) if differences else None, "interval": None,
              "confidence_level": confidence, "bootstrap_resamples": 50000, "analysis_seed": rng_seed,
              "unit": "whole_seed_case", "case_count": len(differences), "unavailable_reason": None}
    if len(differences) < 2:
        result["unavailable_reason"] = "fewer_than_two_seed_cases"
        return result
    if len(set(differences)) == 1:
        result["unavailable_reason"] = "constant_paired_differences"
        return result
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        fitted = bootstrap((np.asarray(differences),), np.mean, vectorized=True,
                           n_resamples=50000, method="BCa", confidence_level=confidence,
                           batch=2000, rng=np.random.default_rng(rng_seed))
    low, high = float(fitted.confidence_interval.low), float(fitted.confidence_interval.high)
    if not np.isfinite(fitted.bootstrap_distribution).all() or not math.isfinite(low) or not math.isfinite(high):
        result["unavailable_reason"] = "nonfinite_BCa"
    elif float(np.std(fitted.bootstrap_distribution)) == 0 or not low < high:
        result["unavailable_reason"] = "zero_bootstrap_variance_or_degenerate_interval"
    else:
        result["interval"] = [low, high]
    return result


def analyse(cases: list[dict]) -> dict:
    require(len(cases) == 30 and [c["row"]["seed"] for c in cases] == list(CASE_SEEDS), "analysis requires all 30 ordered cases")
    primary, secondary, joints = [], [], {}
    index = 0
    for value in (5, 10, 20, 40):
        arm = f"lambda_initial_{value}"
        differences = [c["row"]["arms"][arm][AUC_KEY] - c["row"]["arms"]["lambda_initial_1"][AUC_KEY] for c in cases]
        inference = paired_bca(differences, confidence=.9875, rng_seed=43031 + index)
        interval = inference["interval"]
        primary.append({"arm": arm, "reference": "lambda_initial_1", "endpoint": "postinitial_auc",
                        **inference, "advantage": interval is not None and interval[0] > 0,
                        "degradation": interval is not None and interval[1] < 0})
        index += 1
    for endpoint in ("test_wba", "postinitial_auc"):
        for value in (1, 5, 10, 20, 40):
            arm = f"lambda_initial_{value}"
            def endpoint_value(c: dict, name: str) -> float:
                row = c["row"]["arms"][name]
                return row["test_metrics"]["weighted"]["balanced_accuracy"] if endpoint == "test_wba" else row[AUC_KEY]
            differences = [endpoint_value(c, arm) - endpoint_value(c, "chc_harmonized") for c in cases]
            inference = paired_bca(differences, confidence=.995, rng_seed=43031 + index)
            margin = -.001 if endpoint == "test_wba" else 0.
            interval = inference["interval"]
            passed = interval is not None and interval[0] > margin
            secondary.append({"arm": arm, "reference": "chc_harmonized", "endpoint": endpoint,
                              **inference, "decision_margin": margin, "gate_passed": passed})
            joints.setdefault(arm, {})[endpoint] = passed
            index += 1
    return {"primary_contrasts": primary, "secondary_contrasts": secondary,
            "joint_search_advantage": {arm: all(gates.values()) for arm, gates in joints.items()},
            "multiplicity": "Bonferroni_separate_prespecified_families_4_and_10",
            "pooled_confusion_matrices": False, "global_14_contrast_95_coverage_claim": False}


def write_csv(path: Path, rows: list[dict]) -> None:
    require(bool(rows), "cannot write empty scientific CSV")
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def make_plots(cases: list[dict], analysis: dict, output: Path) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, axis = plt.subplots(figsize=(11, 6))
    for arm in ALL_ARMS:
        paths = np.asarray([[r["best_so_far_weighted_balanced_accuracy"] for r in c["traces"][arm]["evaluations"]] for c in cases])
        axis.plot(np.arange(1, 401), 100 * paths.mean(axis=0), label=LABELS[arm], linewidth=1.7)
    axis.axvline(50, color="black", linestyle="--", linewidth=1, label="Спільна ініціалізація: 50 оцінювань")
    axis.set(xlabel="Кількість логічних оцінювань", ylabel="Середня найкраща валідаційна WBA, %",
             title="Початкове λ та перебіг пошуку: 30 парних випадків")
    axis.grid(alpha=.2)
    axis.legend(fontsize=9)
    fig.tight_layout()
    fig.savefig(output / "initial-lambda-trajectories.png", dpi=180)
    plt.close(fig)
    fig, axis = plt.subplots(figsize=(10, 5))
    for i, contrast in enumerate(analysis["primary_contrasts"]):
        estimate, interval = contrast["estimate"], contrast["interval"]
        axis.plot(100 * estimate, i, "o", color="tab:blue")
        if interval is not None:
            axis.plot([100 * interval[0], 100 * interval[1]], [i, i], color="tab:blue", linewidth=2)
    axis.axvline(0, color="black", linewidth=1)
    axis.set(yticks=list(range(4)), yticklabels=[LABELS[c["arm"]] + " проти λ₀ = 1" for c in analysis["primary_contrasts"]],
             xlabel="Різниця післяініціалізаційного BSF-AUC, відсоткові пункти",
             title="Первинні контрасти: 98,75% BCa-інтервали")
    fig.tight_layout()
    fig.savefig(output / "initial-lambda-primary-intervals.png", dpi=180)
    plt.close(fig)


def build_report(cases: list[dict], sources: dict, *, output: Path, transport: dict) -> dict:
    analysis = analyse(cases)
    rows, class_rows, trajectory_rows, generation_rows = [], [], [], []
    for case in cases:
        seed, arms = case["row"]["seed"], case["row"]["arms"]
        for arm in ALL_ARMS:
            item, trace = arms[arm], case["traces"][arm]
            rows.append({"seed": seed, "arm": arm, "initial_lambda": None if arm == "chc_harmonized" else int(arm.rsplit("_", 1)[1]),
                         "validation_wba": item["terminal"]["fitness"][0],
                         "test_wba": item["test_metrics"]["weighted"]["balanced_accuracy"],
                         "selected_features": sum(item["terminal"]["mask"]), "postinitial_auc": item[AUC_KEY],
                         "logical_calls": 400, "physical_postinitial_calls": 350,
                         "duplicate_logical_calls": item["evaluation_ledger"]["duplicate_queries"],
                         "mask": "".join(map(str, item["terminal"]["mask"]))})
            for scale in ("weighted", "unweighted"):
                for label, metrics in item["test_metrics"][scale]["classes"].items():
                    class_rows.append({"seed": seed, "arm": arm, "scale": scale, "class": label, **metrics})
            for record in trace["evaluations"]:
                trajectory_rows.append({"seed": seed, "arm": arm, "call": record["call"],
                                        "best_so_far_validation_wba": record["best_so_far_weighted_balanced_accuracy"]})
            if arm != "chc_harmonized":
                for gen in trace["generation_trace"]:
                    generation_rows.append({"seed": seed, "arm": arm, **{k: gen[k] for k in
                        ("generation", "calls_before", "calls_after", "lambda_before", "lambda_after",
                         "mutation_strength", "strict_success", "tail_truncated")}})
    summaries = {}
    for arm in ALL_ARMS:
        selected = [r for r in rows if r["arm"] == arm]
        summaries[arm] = {"mean_postinitial_auc": statistics.fmean(r["postinitial_auc"] for r in selected),
                          "median_validation_wba": statistics.median(r["validation_wba"] for r in selected),
                          "median_test_wba": statistics.median(r["test_wba"] for r in selected),
                          "median_features": statistics.median(r["selected_features"] for r in selected),
                          "feature_range": [min(r["selected_features"] for r in selected), max(r["selected_features"] for r in selected)],
                          "mean_duplicate_logical_calls": statistics.fmean(r["duplicate_logical_calls"] for r in selected)}
    report = {"schema": "eu26-21-lambda-initial-report-v1", "protocol_id": PROTOCOL_ID,
              "protocol_sha256": PROTOCOL_SHA256, "implementation_sha": sources["implementation_sha"],
              "source_run_id": sources["source_run_id"], "case_count": 30, "arm_count": 6,
              "comparison_summary": summaries, "analysis": analysis,
              "counts": {"logical_validation_calls": 72000, "physical_validation_calls": 64500, "test_evaluations": 180},
              "source_artifacts": [{**c["artifact"], "manifest_sha256": c["manifest_sha256"]} for c in cases],
              "historical_noninferiority_status": "FAIL_NONINFERIORITY_UNCHANGED",
              "limitations": ["known_benchmark_not_independent_external_validation", "initialization_sensitivity_not_escape_proof",
                              "logical_AUC_not_wallclock_speedup", "not_universal_optimal_lambda", "adaptation_not_isolated_by_initial_value_comparison"]}
    output.mkdir(parents=True, exist_ok=True)
    require(not any(output.iterdir()), "report output directory not empty")
    write_json(output / "summary.json", report)
    write_json(output / "source-ledger.json", sources)
    write_json(output / "transport-ledger.json", transport)
    write_csv(output / "comparison.csv", rows)
    write_csv(output / "per-class-metrics.csv", class_rows)
    write_csv(output / "trajectories.csv", trajectory_rows)
    write_csv(output / "lambda-generations.csv", generation_rows)
    contrasts = [{"family": family, "arm": c["arm"], "reference": c["reference"], "endpoint": c["endpoint"],
                  "estimate": c["estimate"], "ci_low": c["interval"][0] if c["interval"] else None,
                  "ci_high": c["interval"][1] if c["interval"] else None, "confidence_level": c["confidence_level"],
                  "unavailable_reason": c["unavailable_reason"]}
                 for family, key in (("primary", "primary_contrasts"), ("secondary", "secondary_contrasts")) for c in analysis[key]]
    write_csv(output / "contrasts.csv", contrasts)
    lines = ["# Початкове λ та якість адаптивного пошуку", "",
             "Завершено 30 парних випадків для шести методів. У таблиці наведено медіани кінцевої якості й кількості ознак, "
             "але арифметичне середнє післяініціалізаційного BSF-AUC.", "",
             "| Метод | Валідаційна WBA, % | Тестова WBA, % | Медіана кількості ознак | Середній BSF-AUC |",
             "| --- | ---: | ---: | ---: | ---: |"]
    for arm, s in summaries.items():
        lines.append(f"| {LABELS[arm]} | {100*s['median_validation_wba']:.3f} | {100*s['median_test_wba']:.3f} | "
                     f"{s['median_features']:g} | {s['mean_postinitial_auc']:.6f} |")
    lines.extend(["", "## Первинні порівняння з початковим λ = 1", ""])
    for c in analysis["primary_contrasts"]:
        interval = "недоступний" if c["interval"] is None else f"[{c['interval'][0]:.6f}; {c['interval'][1]:.6f}]"
        decision = "поліпшення підтверджено" if c["advantage"] else ("погіршення підтверджено" if c["degradation"] else "поліпшення не підтверджено")
        lines.append(f"- {LABELS[c['arm']]}: середня парна різниця {c['estimate']:.6f}; 98,75% BCa-інтервал {interval}; {decision}.")
    lines.extend(["", "## Порівняння з CHC", "",
                  "Вторинні інтервали мають рівень 99,5%. Спільний висновок потребує проходження обох критеріїв: "
                  "тестова непоступливість з межею −0,001 та додатна валідаційна різниця BSF-AUC.", ""])
    for arm, passed in analysis["joint_search_advantage"].items():
        lines.append(f"- {LABELS[arm]}: спільну перевагу {'підтверджено' if passed else 'не підтверджено'}.")
    lines.extend(["", "*Висновки стосуються цього набору даних, заданої сітки λ та ліміту оцінювань. "
                  "Вони не встановлюють універсально найкраще λ, скорочення часу або виходу з локального максимуму. "
                  "Історичне негативне рішення щодо непоступливості незмінне.*", ""])
    (output / "report.md").write_text("\n".join(lines), encoding="utf-8")
    make_plots(cases, analysis, output)
    files = {p.name: {"sha256": file_sha256(p), "bytes": p.stat().st_size} for p in sorted(output.iterdir()) if p.is_file()}
    write_json(output / "report-manifest.json", {"schema": "eu26-21-lambda-initial-report-manifest-v1",
               "implementation_sha": sources["implementation_sha"], "source_run_id": sources["source_run_id"],
               "protocol_sha256": PROTOCOL_SHA256, "files": files})
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--expected-sha", required=True)
    for key in ("root", "sources", "output", "download-ledger"):
        parser.add_argument(f"--{key}", type=Path, required=True)
    args = parser.parse_args()
    authenticate(protocol_path=THIS_DIRECTORY / "protocol.json", expected_sha=args.expected_sha)
    sources = read_json(args.sources)
    transport = read_json(args.download_ledger)
    cases = load_cases(args.root, sources, expected_sha=args.expected_sha, transport=transport)
    build_report(cases, sources, output=args.output, transport=transport)
    print("PASS_COMPLETE_30_BY_6_LAMBDA_INITIAL_REPORT")


if __name__ == "__main__":
    main()
