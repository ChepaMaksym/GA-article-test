"""Post-outcome descriptions of authenticated traces; no search or inference."""
from __future__ import annotations

import argparse
import csv
import math
import os
from pathlib import Path
import statistics

from common_bridge import trace_contract
from evidence_audit import thesis_tables as tables

PLAN = Path(__file__).with_name("ADAPTIVE_DIAGNOSTICS_PLAN_UK.md")
EXAMPLE_SEED = 41001
NOTE = (
    "Ретроспективний опис усіх 30 пар, без нового пошуку та перевірки гіпотез. "
    "Відсутність поліпшень не доводить локальної оптимальності. "
    "Успіх покоління означає поліпшення відносно батьківської маски, "
    "а не обов'язково новий глобальний рекорд. Кінцеві інтервали "
    "обмежені завершенням спостереження на оцінюванні 400. "
    "Висновок FAIL_NONINFERIORITY не змінено; переваги за ефективністю "
    "і кількістю ознак залишаються BLOCKED_BY_QUALITY_NONINFERIORITY."
)
ARM_LABELS = {"chc_harmonized": "Базовий CHC", "lambda_no_reset": "Адаптивний алгоритм"}
GENERATION_FIELDS = (
    "seed", "arm", "generation", "calls_before", "calls_after", "lambda_before",
    "lambda_after", "strict_success", "accepted", "parent_wba_before",
    "parent_negative_fraction_before", "candidate_wba", "candidate_negative_fraction",
    "planned_offspring_count_per_phase", "evaluated_offspring_count_per_phase",
    "mutation_probability", "crossover_probability", "mutation_strength", "tail_truncated",
    "phase", "distance_before", "distance_after", "generated_fresh_offspring",
    "evaluated_fresh_offspring", "partial_population_update_skipped",
)


def _require(condition, message):
    if not condition:
        raise ValueError(message)


def evaluation_ages(records):
    """Reset ages at boundary 50, but retain the record from calls 1..50.

    This counts logical calls, including repeated masks. No retrospective
    threshold is introduced to classify an interval as a local optimum.
    """
    _require(len(records) == 400, "expected exactly 400 evaluations")
    best = None
    lex_age = quality_age = 0
    output = []
    for call, row in enumerate(records, 1):
        _require(type(row["call"]) is int and row["call"] == call, "evaluation order mismatch")
        quality = tables._score(row["validation_weighted_balanced_accuracy"])
        count = row["selected_feature_count"]
        _require(type(count) is int and 0 <= count <= 40, "invalid feature count")
        secondary = row["negative_selected_feature_fraction"]
        _require(type(secondary) in (float, int) and math.isfinite(secondary)
                 and secondary == -count / 40, "secondary objective mismatch")
        mask = row["mask"]
        _require(isinstance(mask, list) and len(mask) == 40
                 and all(type(bit) is int and bit in (0, 1) for bit in mask)
                 and sum(mask) == count, "evaluation mask mismatch")
        fitness = (quality, secondary)
        lex_update = best is None or fitness > best
        quality_update = best is None or quality > best[0]
        _require(row["terminal_best_update"] is lex_update, "global record flag mismatch")
        if lex_update:
            best = fitness
        _require(row["best_so_far_weighted_balanced_accuracy"] == best[0],
                 "best-so-far quality mismatch")
        if call < 50:
            continue
        if call == 50:
            # The boundary is a new observation window, not a claimed improvement.
            lex_update = quality_update = False
        else:
            lex_age = 0 if lex_update else lex_age + 1
            quality_age = 0 if quality_update else quality_age + 1
        output.append({
            "call": call, "boundary_only": call == 50,
            "best_validation_wba": best[0], "best_selected_feature_count": round(-40 * best[1]),
            "lexicographic_record_update": lex_update, "quality_record_update": quality_update,
            "lexicographic_record_age": lex_age, "quality_record_age": quality_age,
        })
    return output


def describe_trace(trace):
    """Validate transitions independently, then describe a single frozen trace."""
    arm, seed = trace["arm"], trace["seed"]
    _require(arm in tables.ARMS, "unknown arm")
    _require(type(seed) is int and seed in tables.source.EXPECTED_SEEDS, "unknown seed")
    _require(trace["reset"] is False and type(trace["reset_events"]) is int
             and trace["reset_events"] == 0, "reset must remain disabled")
    _require(trace["initial_population_calls"] == 50 and trace["objective_calls"] == 400,
             "observation window mismatch")
    records, generations, state = trace["evaluations"], trace["generation_trace"], trace["terminal_state"]
    calls = evaluation_ages(records)
    trace_contract.validate_generations(arm, generations, records, state)
    for row in calls:
        row.update(seed=seed, arm=arm)
    generation_rows = []
    for row in generations:
        flat = {key: row[key] for key in GENERATION_FIELDS if key in row}
        flat.update(seed=seed, arm=arm)
        if arm == "lambda_no_reset":
            flat.update(parent_wba_before=row["parent_fitness_before"][0],
                        parent_negative_fraction_before=row["parent_fitness_before"][1],
                        candidate_wba=row["candidate_fitness"][0],
                        candidate_negative_fraction=row["candidate_fitness"][1])
        generation_rows.append(flat)
    summary = {"seed": seed, "arm": arm, "post_initialization_calls": 350,
               "generation_count": len(generations), "reset_count": 0,
               "terminal_intervals_right_censored": True}
    for prefix in ("lexicographic", "quality"):
        key = f"{prefix}_record_age"
        summary[f"maximum_{key}"] = max(row[key] for row in calls)
        summary[f"terminal_{key}"] = calls[-1][key]
        summary[f"{prefix}_record_updates"] = sum(row[f"{prefix}_record_update"] for row in calls)
    if arm == "lambda_no_reset":
        summary.update(
            lambda_initial=generations[0]["lambda_before"], lambda_final=state["final_lambda"],
            lambda_maximum_used=max(row["lambda_before"] for row in generations),
            successful_generations=sum(row["strict_success"] for row in generations),
            unsuccessful_generations=sum(not row["strict_success"] for row in generations),
            accepted_neutral_generations=sum(row["accepted"] and not row["strict_success"]
                                             for row in generations),
            lambda_upper_bound_used=any(row["lambda_before"] == 40.0 for row in generations),
            terminal_lambda_unused=True,
        )
    return calls, generation_rows, summary


def load_diagnostics(rows_dir, expected_path, verified_path):
    # Reuse full byte, artifact, source revision, pairing and result validation.
    _, _, provenance = tables.load_pairs(rows_dir, expected_path, verified_path)
    paths = {Path(item["path"]).name: rows_dir / item["path"] for item in provenance["inputs"]}
    all_calls, all_generations, summaries = [], [], []
    for seed in tables.source.EXPECTED_SEEDS:
        for suffix in ("chc", "lambda"):
            path = paths[f"seed-{seed}-{suffix}-trace.json"]
            calls, generations, summary = describe_trace(tables.source._load_json(path))
            all_calls.extend(calls)
            all_generations.extend(generations)
            summaries.append(summary)
    return all_calls, all_generations, summaries, provenance


def _write_csv(path, rows, fields):
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def _plots(calls, generations, summaries, output_dir):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    example = [row for row in generations if row["seed"] == EXAMPLE_SEED
               and row["arm"] == "lambda_no_reset"]
    fig, axes = plt.subplots(3, 1, figsize=(10, 9), sharex=True, layout="constrained")
    # Plot only the value actually used on each generation's call interval.
    x = [50] + [row["calls_after"] for row in example[:-1]] + [400]
    y = [1.0] + [row["lambda_after"] for row in example[:-1]] + [example[-1]["lambda_before"]]
    axes[0].step(x, y, where="post", color="tab:orange", label="λ, застосоване в поколінні")
    successes = [row for row in example if row["strict_success"]]
    axes[0].scatter([row["calls_after"] for row in successes],
                    [row["lambda_after"] for row in successes], marker="v", color="green",
                    zorder=3, label="Успішне покоління: λ після оновлення")
    axes[0].scatter([400], [example[-1]["lambda_after"]], facecolors="none", edgecolors="black",
                    zorder=4, label="Кінцеве λ: далі не застосовувалось")
    axes[0].set(ylabel="Значення λ", title="Пара 41001: спостережена реакція адаптивного алгоритму")
    axes[0].legend(fontsize=8)
    for arm in tables.ARMS:
        selected = [row for row in calls if row["seed"] == EXAMPLE_SEED and row["arm"] == arm]
        axes[1].step([row["call"] for row in selected], [row["best_validation_wba"] for row in selected],
                     where="post", label=ARM_LABELS[arm])
        axes[2].step([row["call"] for row in selected], [row["lexicographic_record_age"] for row in selected],
                     where="post", label=ARM_LABELS[arm])
    axes[1].set(ylabel="Найкраща валідаційна WBA")
    axes[2].set(ylabel="Оцінювань без нового\nнайкращого розв'язку",
                xlabel="Кількість оцінювань (межа 50: завершення спільної ініціалізації)", xlim=(50, 402))
    for axis in axes:
        axis.grid(alpha=0.2)
    axes[1].legend(fontsize=9)
    axes[2].legend(fontsize=9)
    fig.savefig(output_dir / "lambda-response-41001.png", dpi=180)
    plt.close(fig)

    fig, axis = plt.subplots(figsize=(11, 5), layout="constrained")
    for arm, offset, marker in zip(tables.ARMS, (-0.16, 0.16), ("o", "s")):
        selected = [row for row in summaries if row["arm"] == arm]
        axis.scatter([row["seed"] + offset for row in selected],
                     [row["maximum_lexicographic_record_age"] for row in selected],
                     marker=marker, label=ARM_LABELS[arm])
    axis.set(xlabel="Початкове значення генератора пари",
             ylabel="Найбільша спостережена кількість оцінювань\nбез нового найкращого розв'язку",
             title="Усі 30 пар: опис інтервалів без поліпшень після ініціалізації")
    axis.ticklabel_format(axis="x", style="plain", useOffset=False)
    axis.set_xticks(list(tables.source.EXPECTED_SEEDS)[::3])
    axis.set_ylim(bottom=0)
    axis.grid(alpha=0.2)
    axis.legend()
    fig.savefig(output_dir / "stagnation-all-seeds.png", dpi=180)
    plt.close(fig)


def write_report(calls, generations, summaries, provenance, output_dir):
    expected = [(seed, arm) for seed in tables.source.EXPECTED_SEEDS for arm in tables.ARMS]
    _require([(row["seed"], row["arm"]) for row in summaries] == expected,
             "summary must include exactly all 30 ordered pairs")
    _require(len(calls) == 30 * 2 * 351, "incomplete per-call report")
    analysis = tables.preserved_analysis(Path(__file__).resolve().parents[1] / "common_bridge" / "evidence")
    group_summaries = {}
    age_metrics = [f"{position}_{criterion}_record_age"
                   for criterion in ("lexicographic", "quality")
                   for position in ("maximum", "terminal")]
    for arm in tables.ARMS:
        selected = [row for row in summaries if row["arm"] == arm]
        metrics = age_metrics + (["lambda_maximum_used", "lambda_final"]
                                 if arm == "lambda_no_reset" else [])
        group_summaries[arm] = {"count": len(selected), "descriptive_statistics": {
            metric: {"minimum": min(row[metric] for row in selected),
                     "median": statistics.median(row[metric] for row in selected),
                     "maximum": max(row[metric] for row in selected)}
            for metric in metrics}}
        if arm == "lambda_no_reset":
            group_summaries[arm]["runs_using_lambda_upper_bound"] = sum(
                row["lambda_upper_bound_used"] for row in selected)
    output_dir.mkdir(parents=True, exist_ok=False)
    _write_csv(output_dir / "per-call-diagnostics.csv", calls, list(calls[0]))
    _write_csv(output_dir / "generation-diagnostics.csv", generations, GENERATION_FIELDS)
    tables.source._write_json(output_dir / "summary.json", {
        "schema": "eu26-21-adaptive-diagnostics-summary-v1", "interpretation": NOTE,
        "example_seed": EXAMPLE_SEED, "example_selection": "first seed in fixed ledger",
        "observation_window": {"initial_boundary": 50, "first_call": 51, "last_call": 400},
        "seed_ledger": list(tables.source.EXPECTED_SEEDS), "arms": list(tables.ARMS),
        "per_seed_arm": summaries, "group_summaries": group_summaries,
        "preserved_analysis": analysis,
    })
    _plots(calls, generations, summaries, output_dir)
    lines = ["# Реакція адаптивного алгоритму за журналами завершеної серії", "", NOTE, "",
             "Лічильники на межі 50 обнулено; початковий рекорд включає перші 50 оцінювань.",
             "Лексикографічний рекорд враховує WBA і, за її рівності, меншу кількість ознак.",
             "Окремий лічильник без підвищення WBA не обнуляється через скорочення маски.",
             "Максимуми описують лише вікно 51–400, а не повну тривалість епізодів застою.", "",
             "Приклад 41001 обрано як перший номер до розрахунку показників.", "",
             "![Зміна λ, якості та інтервалів без поліпшень](lambda-response-41001.png)", "",
             "![Усі 30 пар](stagnation-all-seeds.png)", ""]
    (output_dir / "report.md").write_text("\n".join(lines), encoding="utf-8")
    report_sources = [Path(__file__), Path(tables.__file__), Path(trace_contract.__file__), PLAN]
    tables.source._write_json(output_dir / "diagnostics-manifest.json", {
        "schema": "eu26-21-adaptive-diagnostics-manifest-v1", **provenance,
        "protocol_id": tables.PROTOCOL_ID, "protocol_sha256": tables.PROTOCOL_SHA,
        "plan_sha256": tables.source._file_sha256(PLAN),
        "preserved_analysis": analysis, "preserved_report_sha256": tables.REPORT_HASHES,
        "report_sources": {path.name: tables.source._file_sha256(path) for path in report_sources},
        "interpretation": NOTE, "scientific_decisions_recomputed": False,
        "scientific_decisions_changed": False, "model_deserialization_performed": False,
        "training_performed": False, "optimizer_execution_performed": False,
        "report_run": {key: os.environ[key] for key in (
            "GITHUB_REPOSITORY", "GITHUB_RUN_ID", "GITHUB_RUN_ATTEMPT", "GITHUB_SHA",
            "GITHUB_REF", "THESIS_WORKFLOW_SHA")},
        "outputs": {path.name: {"bytes": path.stat().st_size,
                                "sha256": tables.source._file_sha256(path)}
                    for path in sorted(output_dir.iterdir())},
    })


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("rows-dir", "expected-ledger", "verified-ledger", "output-dir"):
        parser.add_argument(f"--{name}", type=Path, required=True)
    args = parser.parse_args()
    calls, generations, summaries, provenance = load_diagnostics(
        args.rows_dir, args.expected_ledger, args.verified_ledger)
    write_report(calls, generations, summaries, provenance, args.output_dir)


if __name__ == "__main__":
    main()
