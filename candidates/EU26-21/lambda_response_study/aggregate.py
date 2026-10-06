"""Authenticate every case and report controller reactions descriptively.

This module performs no fitting, score-based case selection, statistical test,
bootstrap or deserialization of downloaded model files. All graphics and
summaries are generated in CI after all thirty cases have completed.
"""
from __future__ import annotations

import argparse
from collections import Counter
import csv
import math
from pathlib import Path
import shutil
import statistics

from corrected_applied.data_protocol import (
    TRANSFORMED_FEATURE_NAMES, TRANSFORMED_PREDICTIVE_RAW_INDICES,
)
from local_optima_study.contract import per_class_metrics
from lambda_response_study.artifacts import (
    validate_preparation_metadata, validate_registry, validate_sources, validate_transport, validate_upload_identity,
)
from lambda_response_study.contract import (
    ARMS, CASE_SEEDS, PROBLEMS, PROTOCOL_ID, PROTOCOL_SHA256, authenticate,
    canonical_sha256, ensure_empty_output, file_sha256, read_json, require,
    verify_manifest, write_json,
)
from lambda_response_study.oracle import close, validate_trace


ARM_LABELS = {"adaptive": "Адаптивний λ", "fixed10": "Сталий λ=10"}
PROBLEM_LABELS = {"onemax": "OneMax", "census": "Census-Income"}
OUTCOME_LABELS = {"success": "Строге покращення", "tie": "Рівна оцінка", "rejection": "Гірший кандидат"}
OUTCOME_COLORS = {"success": "tab:green", "tie": "tab:gray", "rejection": "tab:red"}
EXAMPLE_SEED = 45001


def validate_metrics(metrics: dict, *, expected_rows: int = 99762) -> None:
    require(set(metrics) >= {"weighted", "unweighted"}, "missing metric scales")
    for scope in ("weighted", "unweighted"):
        block = metrics[scope]
        matrix = block["confusion_matrix"]
        require(isinstance(matrix, list) and len(matrix) == 2
                and all(isinstance(row, list) and len(row) == 2 for row in matrix),
                "confusion matrix must be two by two")
        require(all(type(value) in (int, float) and math.isfinite(value) and value >= 0
                    for row in matrix for value in row), "invalid confusion matrix entry")
        classes = per_class_metrics(matrix)
        require(set(block["classes"]) == {"0", "1"}, "missing class metrics")
        for label in classes:
            for key, value in classes[label].items():
                require(close(block["classes"][label][key], value),
                        f"derived class metric mismatch: {scope}/{label}/{key}")
        require(close(block["balanced_accuracy"], sum(c["recall"] for c in classes.values()) / 2),
                "balanced accuracy differs from class recalls")
        total = sum(sum(row) for row in matrix)
        require(total > 0 and all(sum(row) > 0 for row in matrix), "test classes must both be present")
        require(close(block["accuracy"], (matrix[0][0] + matrix[1][1]) / total),
                "accuracy differs from confusion matrix")
        if scope == "unweighted":
            require(total == expected_rows and all(type(value) is int for row in matrix for value in row),
                    "test record counts invalid")


def validate_training(metadata: dict, *, seed: int) -> None:
    validate_preparation_metadata(metadata, seed=seed)


def identity_matches(identity: dict, manifest: dict) -> None:
    name = identity["file"]
    require(name in manifest["files"]
            and {key: identity[key] for key in ("sha256", "bytes")} == manifest["files"][name],
            "referenced file is not bound to its authenticated bytes")


def outcome(event: dict) -> str:
    if event["strict_success"]:
        return "success"
    return "tie" if event["candidate_score"] == event["parent_score_before"] else "rejection"


def validate_case(directory: Path, source: dict, registry: dict, registry_sha256: str,
                  *, expected_sha: str, seed: int, preparation: dict) -> dict:
    manifest = verify_manifest(directory / "manifest.json", expected_sha=expected_sha)
    validate_upload_identity(manifest, source, kind="case", seed=seed,
                             expected_sha=expected_sha, run_id=registry["source_run_id"])
    row = read_json(directory / "case.json")
    require(manifest["kind"] == "case" and manifest["row_file"] == "case.json"
            and row["schema"] == "eu26-21-lr-case-v1" and row["status"] == "PASS_CASE"
            and row["seed"] == seed and row["provenance"] == manifest["provenance"],
            "case identity, completion or provenance mismatch")
    entry = registry["cases"][seed - CASE_SEEDS[0]]
    source_preparation = {"registry_sha256": registry_sha256,
                          **{key: entry[key] for key in ("preparation", "source_run_id", "source_artifact_id",
                                                        "source_artifact_name", "source_artifact_digest")}}
    require(row["preparation"] == source_preparation and row["training_data"] == preparation["training_data"]
            and row["initial"] == preparation["initial"], "case did not replay its frozen weak state")
    validate_training(row["training_data"], seed=seed)
    require(set(row["problems"]) == set(PROBLEMS) and set(row["traces"]) == set(PROBLEMS),
            "problem coverage mismatch")
    all_calls, real_fits = 0, 0
    known_census = {tuple(item["mask"]): item["score"] for item in preparation["evaluations"]}
    for problem in PROBLEMS:
        arms = row["problems"][problem]["arms"]
        require(set(arms) == set(ARMS) and set(row["traces"][problem]) == set(ARMS), "arm coverage mismatch")
        for arm in ARMS:
            trace = arms[arm]
            identity = row["traces"][problem][arm]
            identity_matches(identity, manifest)
            require(identity["file"] == f"trace-{problem}-{arm}.json"
                    and read_json(directory / identity["file"]) == trace, "trace differs from authenticated separate file")
            require(trace["arm"] == arm and trace["problem"] == problem
                    and trace["search_seed"] == seed + (1000003 if problem == "onemax" else 2000003),
                    "trace problem, arm or random stream mismatch")
            expected_initial = {"mask": [0] * 40, "score": 0.0, "lambda": 10.0, "call": 0} if problem == "onemax" else {
                "mask": preparation["initial"]["mask"], "score": preparation["initial"]["score"],
                "lambda": 10.0, "call": 0}
            require(trace["initial"] == expected_initial, "trace initial state differs from protocol")
            check = validate_trace(trace)
            require(check["mismatches"] == 0, "nonzero oracle mismatch")
            all_calls += trace["counts"]["physical_calls"]
            if problem == "census":
                real_fits += trace["counts"]["actual_tree_fits"]
                for point in trace["evaluations"]:
                    mask, value = tuple(point["mask"]), point["score"]
                    require(mask not in known_census or known_census[mask] == value,
                            "same real mask has inconsistent scores across preparation or arms")
                    known_census[mask] = value
        adaptive, fixed = arms["adaptive"], arms["fixed10"]
        require(adaptive["rng_initial_state"] == fixed["rng_initial_state"]
                and adaptive["evaluations"][:20] == fixed["evaluations"][:20],
                "paired first-generation randomness or candidates differ")
        a, f = adaptive["generation_trace"][0], fixed["generation_trace"][0]
        for key in ("parent_before", "parent_score_before", "parent_after", "parent_score_after",
                    "candidate_mask", "candidate_score", "strict_success", "accepted", "parent_changed",
                    "lambda_before", "offspring_count", "mutation_probability", "crossover_probability",
                    "mutation_strength", "selected_mutant_index", "selected_mutant_mask", "selected_mutant_score",
                    "candidate_phase", "candidate_phase_index", "eligible_count", "RNG_state_before", "RNG_state_after"):
            require(a[key] == f[key], "paired first generation differs: " + key)
    freeze_identity = row["final_masks_freeze"]
    identity_matches(freeze_identity, manifest)
    require(freeze_identity["file"] == "terminal-masks.json", "unexpected terminal freeze file")
    freeze = read_json(directory / freeze_identity["file"])
    finals = {arm: row["problems"]["census"]["arms"][arm]["final"] for arm in ARMS}
    require(freeze == {"schema": "eu26-21-lr-terminal-freeze-v1", "seed": seed,
            "provenance": row["provenance"], "preparation": source_preparation, "parents": finals,
            "selected_by": "accepted_parent_after_generation_20", "test_evaluations_so_far": 0},
            "real terminal masks were not frozen before test")
    require(set(row["models"]) == set(row["test_metrics"]) == set(row["test_evaluations"]) == set(ARMS),
            "terminal model or test metric coverage mismatch")
    for arm in ARMS:
        model, final = row["models"][arm], finals[arm]
        identity_matches(model, manifest)
        require(model["file"] == f"model-{arm}.joblib" and model["seed"] == seed and model["arm"] == arm
                and model["mask"] == final["mask"] and sum(final["mask"]) > 0
                and model["selected_feature_names"] == [name for name, bit in zip(TRANSFORMED_FEATURE_NAMES, final["mask"]) if bit]
                and model["classifier"] == "DecisionTreeClassifier(random_state=0)"
                and model["preprocessing_fit_partition"] == model["terminal_fit_partition"] == "internal_training_only"
                and model["reload_verification"] == "PASS_EXACT_NON_TEST_PROBE"
                and model["test_access_during_reload"] is False, "terminal model or mask provenance mismatch")
        require(row["test_evaluations"][arm] == 1, "official test may only be evaluated once per arm")
        validate_metrics(row["test_metrics"][arm])
    require(row["counts"] == {"preparation_calls": 40, "search_calls": all_calls,
                              "search_tree_fits": real_fits, "test_evaluations": 2}, "case counter mismatch")
    return row


def describe(rows: list[dict]) -> dict:
    problems = {}
    for problem in PROBLEMS:
        summaries = {}
        for arm in ARMS:
            traces = [row["problems"][problem]["arms"][arm] for row in rows]
            events = [event for trace in traces for event in trace["generation_trace"]]
            finals = [trace["final"]["score"] for trace in traces]
            initials = [trace["initial"]["score"] for trace in traces]
            calls = [trace["counts"]["physical_calls"] for trace in traces]
            feature_counts = [sum(trace["final"]["mask"]) for trace in traces]
            states = Counter(outcome(event) for event in events)
            summaries[arm] = {
                "method": ARM_LABELS[arm], "cases": len(traces), "generations_per_case": 20,
                "initial_score_range": [min(initials), max(initials)],
                "median_initial_score": statistics.median(initials),
                "final_score_range": [min(finals), max(finals)], "median_final_score": statistics.median(finals),
                "median_parent_gain": statistics.median(t["final"]["score"] - t["initial"]["score"] for t in traces),
                "cases_without_parent_improvement": sum(t["final"]["score"] == t["initial"]["score"] for t in traces),
                "events": {key: states[key] for key in ("success", "tie", "rejection")},
                "physical_search_calls": sum(calls), "calls_range": [min(calls), max(calls)],
                "actual_tree_fits": sum(t["counts"]["actual_tree_fits"] for t in traces),
                "duplicate_queries": sum(t["counts"]["duplicate_queries"] for t in traces),
                "empty_penalty_queries": sum(point["kind"] == "empty_penalty" for t in traces for point in t["evaluations"]),
                "final_feature_count_range": [min(feature_counts), max(feature_counts)],
                "lambda_mismatches": sum(t["model_check"]["mismatches"] for t in traces),
                "max_abs_lambda_residual": max(t["model_check"]["max_abs_residual"] for t in traces),
            }
            if problem == "census":
                tests = [row["test_metrics"][arm]["weighted"]["balanced_accuracy"] for row in rows]
                summaries[arm].update({"test_evaluations": len(tests), "median_test_wba": statistics.median(tests),
                                      "test_wba_range": [min(tests), max(tests)]})
        problems[problem] = {"arms": summaries}
    example = next(row for row in rows if row["seed"] == EXAMPLE_SEED)
    examples = {}
    for problem in PROBLEMS:
        examples[problem] = {}
        for arm in ARMS:
            trace = example["problems"][problem]["arms"][arm]
            first_success = next((event for event in trace["generation_trace"] if event["strict_success"]), None)
            examples[problem][arm] = {
                "initial": trace["initial"], "final": trace["final"], "counts": trace["counts"],
                "first_success": {key: first_success[key] for key in (
                    "generation", "parent_score_before", "candidate_score", "score_delta_pp", "lambda_before",
                    "expected_lambda_after", "applied_lambda_after", "lambda_delta_percent", "lambda_residual")}
                if first_success is not None else None,
                "model_check": trace["model_check"],
            }
    return {"schema": "eu26-21-lr-descriptive-summary-v1", "protocol_id": PROTOCOL_ID,
            "protocol_sha256": PROTOCOL_SHA256, "cases_accounted": len(rows), "problems": problems,
            "preparation_calls": sum(row["counts"]["preparation_calls"] for row in rows),
            "test_evaluations": sum(row["counts"]["test_evaluations"] for row in rows),
            "example_seed": EXAMPLE_SEED, "example": examples,
            "hypothesis_tests": False, "bootstrap": False, "equal_objective_budget": False,
            "claims": {"new_controller": False, "speed_superiority": False, "test_superiority": False,
                       "local_optimum_escape": False, "historical_results_reinterpreted": False}}


def write_csv(path: Path, rows: list[dict]) -> None:
    require(bool(rows), "empty report table")
    fields = list(dict.fromkeys(key for row in rows for key in row))
    with path.open("x", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def plot_example(output: Path, row: dict, *, problem: str) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.lines import Line2D

    arms = row["problems"][problem]["arms"]
    y_label = "Валідаційна WBA" if problem == "census" else "Частка одиничних бітів"
    fig, axes = plt.subplots(1, 2, figsize=(13, 4.8), sharey=True)
    for arm, ax in zip(ARMS, axes):
        trace = arms[arm]
        rows = [point for point in trace["evaluations"] if point["kind"] != "empty_penalty"]
        for phase, color in (("mutation", "tab:gray"), ("crossover", "tab:orange")):
            points = [point for point in rows if point["phase"] == phase]
            ax.scatter([point["call"] for point in points], [point["score"] for point in points],
                       s=9, alpha=.42, color=color, label="Мутація" if phase == "mutation" else "Схрещування")
        events = trace["generation_trace"]
        ax.step([0] + [event["calls_after"] for event in events],
                [trace["initial"]["score"]] + [event["parent_score_after"] for event in events],
                where="post", color="tab:blue", linewidth=1.8, label="Прийнятий батько")
        ax.step([0] + [point["call"] for point in trace["evaluations"]],
                [trace["initial"]["score"]] + [point["best_so_far_score"] for point in trace["evaluations"]],
                where="post", color="black", linestyle="--", linewidth=1, label="Найкраща знайдена оцінка")
        penalties = [point["call"] for point in trace["evaluations"] if point["kind"] == "empty_penalty"]
        if penalties:
            ax.scatter(penalties, [.02] * len(penalties), transform=ax.get_xaxis_transform(),
                       marker="x", color="tab:red", s=14, label="Порожня маска: штраф, не WBA")
        ax.set_title(ARM_LABELS[arm])
        ax.set_xlabel("Фізичні пошукові запити")
        ax.legend(fontsize=7)
        ax.grid(alpha=.2)
    axes[0].set_ylabel(y_label)
    fig.suptitle(f"{PROBLEM_LABELS[problem]}, випадок {EXAMPLE_SEED}: усі кандидати та прийнятий стан")
    fig.tight_layout()
    fig.savefig(output / f"{problem}-45001-candidates.png", dpi=180)
    plt.close(fig)

    fig, axes = plt.subplots(1, 2, figsize=(13, 4), sharey=True)
    for arm, ax in zip(ARMS, axes):
        events = arms[arm]["generation_trace"]
        xs = [0] + [event["generation"] for event in events]
        ax.plot(xs, [10] + [event["applied_lambda_after"] for event in events],
                color="tab:blue", label="Фактично застосоване λ")
        ax.plot(xs, [10] + [event["expected_lambda_after"] for event in events],
                linestyle="none", marker="o", markerfacecolor="none", color="tab:red", markersize=5,
                label="Незалежний розрахунок")
        ax.set_title(ARM_LABELS[arm])
        ax.set_xlabel("Завершене покоління")
        ax.legend(fontsize=8)
        ax.grid(alpha=.2)
    axes[0].set_ylabel("λ")
    fig.suptitle(f"{PROBLEM_LABELS[problem]}, випадок {EXAMPLE_SEED}: модель і фактичне оновлення λ")
    fig.tight_layout()
    fig.savefig(output / f"{problem}-45001-lambda-model.png", dpi=180)
    plt.close(fig)

    fig, axes = plt.subplots(1, 2, figsize=(13, 4.5), sharey=True)
    quality_label = "Приріст WBA, в.п." if problem == "census" else "Приріст частки одиниць, в.п. (не точність)"
    for arm, ax in zip(ARMS, axes):
        events = arms[arm]["generation_trace"]
        shown = [event for event in events if problem != "census" or sum(event["candidate_mask"]) > 0]
        ax.bar([event["generation"] for event in shown], [event["score_delta_pp"] for event in shown],
               color=[OUTCOME_COLORS[outcome(event)] for event in shown], alpha=.7)
        ax.axhline(0, color="black", linewidth=.7)
        penalties = [event for event in events if problem == "census" and not sum(event["candidate_mask"])]
        if penalties:
            ax.scatter([event["generation"] for event in penalties], [.02] * len(penalties),
                       transform=ax.get_xaxis_transform(), marker="x", color="tab:red", label="Кандидат зі штрафом, не WBA")
        right = ax.twinx()
        right.plot([event["generation"] for event in events], [event["lambda_delta_percent"] for event in events],
                   color="tab:blue", marker=".", linewidth=1.2)
        right.set_ylabel("Відносна зміна λ, %", color="tab:blue")
        right.set_ylim(-38, 15)
        ax.set_title(ARM_LABELS[arm])
        ax.set_xlabel("Завершене покоління")
        ax.grid(axis="y", alpha=.2)
    axes[0].set_ylabel(quality_label)
    handles = [Line2D([0], [0], color=OUTCOME_COLORS[key], linewidth=5, label=OUTCOME_LABELS[key])
               for key in ("success", "tie", "rejection")]
    handles.append(Line2D([0], [0], color="tab:blue", label="Зміна λ"))
    fig.legend(handles=handles, loc="lower center", ncol=4, fontsize=8)
    fig.suptitle(f"{PROBLEM_LABELS[problem]}, випадок {EXAMPLE_SEED}: приріст кандидата та реакція λ")
    fig.tight_layout(rect=(0, .08, 1, 1))
    fig.savefig(output / f"{problem}-45001-deltas.png", dpi=180)
    plt.close(fig)


def plot_all_cases(output: Path, rows: list[dict], *, problem: str) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, axes = plt.subplots(1, 2, figsize=(13, 4.5))
    for arm, color in (("adaptive", "tab:blue"), ("fixed10", "tab:orange")):
        traces = [row["problems"][problem]["arms"][arm] for row in rows]
        scores = [[trace["initial"]["score"]] + [event["parent_score_after"] for event in trace["generation_trace"]]
                  for trace in traces]
        lambdas = [[10] + [event["applied_lambda_after"] for event in trace["generation_trace"]] for trace in traces]
        for matrix, ax in ((scores, axes[0]), (lambdas, axes[1])):
            columns = list(zip(*matrix))
            require(len(columns) == 21, "all-case plot cannot pad incomplete generations")
            ax.fill_between(range(21), [min(values) for values in columns], [max(values) for values in columns],
                            color=color, alpha=.13)
            ax.plot(range(21), [statistics.median(values) for values in columns], color=color, label=ARM_LABELS[arm])
            ax.set_xlabel("Завершене покоління")
            ax.grid(alpha=.2)
            ax.legend(fontsize=8)
    axes[0].set_ylabel("Валідаційна WBA" if problem == "census" else "Частка одиничних бітів")
    axes[1].set_ylabel("λ")
    fig.suptitle(f"{PROBLEM_LABELS[problem]}: медіана та спостережений діапазон усіх 30 випадків; не довірчі інтервали")
    fig.tight_layout()
    fig.savefig(output / f"{problem}-all30-descriptive.png", dpi=180)
    plt.close(fig)


def write_results(output: Path, summary: dict, registry: dict) -> None:
    text = ["# Перевірка реакції λ за слабкого початкового стану", "",
            "Ураховано всі 30 зареєстрованих випадків для двох задач і двох методів. "
            "Кожен пошук завершив 20 повних поколінь. Серія перевіряє реалізацію правила керування λ; "
            "статистичну перевагу методів не оцінювали.", "",
            "За строгого покращення λ ділиться на 1,5 до нижньої межі 1. Без строгого покращення "
            "λ множиться на 1,5⁽¹⁄⁴⁾ до верхньої межі 40. Розмір приросту оцінки не змінює коефіцієнт реакції. "
            "У контрольному методі застосоване λ завжди дорівнює 10.", "",
            "## Початкові стани", "",
            "OneMax починається з 40 нульових бітів та оцінки 0. Ця оцінка означає частку одиничних бітів, "
            "а не точність класифікації. Для Census-Income з усіх 40 однобітних масок наперед вибрано маску "
            "з найнижчою валідаційною WBA; за однакової оцінки використано найменший індекс біта. "
            "Це спеціально підготовлений слабкий стан, а не типовий випадковий старт. "
            "В обох методах пари початкова маска та її відома оцінка однакові.", "",
            "Підготовка потребувала 1200 навчань дерев. Вона облікована окремо від пошуку. "
            "Вага спостереження використана під час навчання та оцінювання й не входить до 40 ознак.", "",
            "## Описові результати", "",
            "| Задача | Метод | Медіана початкової оцінки | Медіана кінцевої оцінки | Строгі покращення | "
            "Рівні оцінки | Гірші кандидати | Пошукові запити | Навчання дерев | Розбіжності λ |",
            "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for problem in PROBLEMS:
        for arm in ARMS:
            item = summary["problems"][problem]["arms"][arm]
            text.append(f"| {PROBLEM_LABELS[problem]} | {ARM_LABELS[arm]} | {item['median_initial_score']:.6f} | "
                        f"{item['median_final_score']:.6f} | {item['events']['success']} | {item['events']['tie']} | "
                        f"{item['events']['rejection']} | {item['physical_search_calls']} | {item['actual_tree_fits']} | "
                        f"{item['lambda_mismatches']} |")
    text += ["", "У таблиці оцінки наведено у шкалі від 0 до 1. Для WBA множення на 100 дає відсотки. "
             "Приріст WBA подано у відсоткових пунктах, а зміну λ як відносний відсоток. "
             "Штраф 0 за порожню маску не є виміряною WBA: для такої маски дерево не навчали.", "",
             "Сталі λ=10 мають 400 пошукових запитів на випадок. В адаптивних запусків число запитів "
             "залежить від λ; покоління не скорочували. Тому різниця кінцевих оцінок не доводить переваги "
             "за однакового обчислювального ресурсу.", "", "## Наперед визначений приклад 45001", ""]
    prepared = registry["cases"][0]["payload"]["initial"]
    text.append(f"Початкова ознака Census-Income: `{prepared['feature_name']}`, індекс біта {prepared['bit_index']}; "
                f"WBA {prepared['score']:.6f}. Приклад 45001 визначено до запусків, а не вибрано за результатом.")
    for problem in PROBLEMS:
        for arm in ARMS:
            example = summary["example"][problem][arm]
            success = example["first_success"]
            text += ["", f"{PROBLEM_LABELS[problem]}, {ARM_LABELS[arm]}: початкова оцінка "
                     f"{example['initial']['score']:.6f}, кінцева {example['final']['score']:.6f}; "
                     f"пошукових запитів {example['counts']['physical_calls']}."]
            if success is None:
                text.append("За 20 поколінь строгого покращення не спостерігали.")
            else:
                unit = "в.п. WBA" if problem == "census" else "в.п. частки одиничних бітів"
                text.append(f"Перше строге покращення у поколінні {success['generation']}: "
                            f"{success['score_delta_pp']:+.6f} {unit}. λ до покоління {success['lambda_before']:.12g}; "
                            f"очікуване λ після {success['expected_lambda_after']:.12g}, "
                            f"фактичне {success['applied_lambda_after']:.12g}; "
                            f"відносна зміна {success['lambda_delta_percent']:+.6f}%.")
    text += ["", "## Пояснення рисунків", "",
             "Рисунки `*-45001-candidates.png` показують усі оцінені кандидати, прийнятого батька та найкращу "
             "знайдену оцінку. Гірші кандидати не вилучені. Порожні маски позначено окремо як штраф, а не як "
             "нульову точність. Монотонність батьківського стану є наслідком відхилення гірших кандидатів; "
             "монотонність рекорду випливає з його означення.", "",
             "Рисунки `*-45001-lambda-model.png` зіставляють незалежний розрахунок із фактично застосованим λ. "
             "Накладання позначок означає відповідність формулі в межах абсолютного й відносного допусків 10⁻¹²; "
             "воно не доводить прогнозування майбутнього приросту якості.", "",
             "Рисунки `*-45001-deltas.png` показують приріст вибраного кандидата відносно батька та зміну λ "
             "після цього покоління. Додатний приріст, рівна оцінка та відхилення гіршого кандидата позначені "
             "окремо. Різним додатним приростам відповідає той самий коефіцієнт зниження λ, якщо нижня межа не активна.", "",
             "Рисунки `*-all30-descriptive.png` містять медіану та мінімальне і максимальне спостережені значення "
             "за поколіннями для всіх 30 випадків. Смуги не є довірчими інтервалами; незавершені траєкторії не доповнювали.", "",
             "## Фінальна тестова оцінка", "",
             "Фінальні батьківські маски обох реальних методів зафіксовано після двадцятого покоління до "
             "завантаження тестових даних. Загалом виконано 60 одноразових тестових оцінювань. "
             "Незважені матриці містять кількості записів; зважені показники враховують ваги спостережень. "
             "Матриці різних моделей не підсумовували як незалежну вибірку.", "",
             "| Метод | Медіана тестової WBA | Діапазон кількості вибраних ознак |",
             "|---|---:|---:|"]
    for arm in ARMS:
        item = summary["problems"]["census"]["arms"][arm]
        bounds = item["final_feature_count_range"]
        text.append(f"| {ARM_LABELS[arm]} | {100 * item['median_test_wba']:.6f}% | {bounds[0]}–{bounds[1]} |")
    text += ["", "*Серія не встановлює статистичної переваги, швидкості, здатності виходити з локальних максимумів "
             "або переваги тестової класифікації. Слабкий старт Census-Income підібрано за валідаційною оцінкою, "
             "тому він є умовою контрольованої демонстрації, а не оцінкою звичайної ініціалізації. "
             "OneMax і вибір ознак мають різні цільові функції; їхні результати не об'єднують. "
             "Результати попередніх серій залишаються незмінними.*", ""]
    (output / "RESULTS_UK.md").write_text("\n".join(text), encoding="utf-8")


def aggregate(*, root: Path, registry_path: Path, sources_path: Path, transport_path: Path,
              expected_sha: str, output: Path) -> dict:
    _, provenance = authenticate(expected_sha)
    sources, registry = read_json(sources_path), read_json(registry_path)
    validate_sources(sources, kind="case", expected_sha=expected_sha)
    preparations = validate_registry(registry, expected_sha=expected_sha)
    require(sources["source_run_id"] == registry["source_run_id"], "cases and preparation must share the fixed source run")
    validate_transport(sources, read_json(transport_path))
    rows = [validate_case(root / source["name"], source, registry, file_sha256(registry_path),
                          expected_sha=expected_sha, seed=seed, preparation=preparations[seed])
            for seed, source in zip(CASE_SEEDS, sources["artifacts"])]
    require(len(rows) == 30, "report completeness is not 30/30")
    ensure_empty_output(output)
    shutil.copyfile(registry_path, output / "registry.json")
    summary = describe(rows)
    summary.update({"provenance": provenance, "source_run_id": sources["source_run_id"],
                    "registry_sha256": file_sha256(registry_path),
                    "case_sources_sha256": file_sha256(sources_path),
                    "case_transport_sha256": file_sha256(transport_path),
                    "source_case_artifact_ids": [source["id"] for source in sources["artifacts"]],
                    "source_preparation_artifact_ids": [entry["source_artifact_id"] for entry in registry["cases"]]})
    cases, events, example_points, classes, preparation_points = [], [], [], [], []
    for row in rows:
        seed = row["seed"]
        for problem in PROBLEMS:
            for arm in ARMS:
                trace = row["problems"][problem]["arms"][arm]
                cases.append({"seed": seed, "problem": problem, "arm": arm, "status": row["status"],
                              "initial_score": trace["initial"]["score"], "final_score": trace["final"]["score"],
                              "parent_gain_pp": 100 * (trace["final"]["score"] - trace["initial"]["score"]),
                              "score_is_classification_wba": problem == "census",
                              "final_lambda": trace["final"]["lambda"], "features": sum(trace["final"]["mask"]),
                              "final_mask": "".join(map(str, trace["final"]["mask"])), **trace["counts"],
                              "lambda_mismatches": trace["model_check"]["mismatches"],
                              "max_abs_lambda_residual": trace["model_check"]["max_abs_residual"],
                              "test_wba": row["test_metrics"][arm]["weighted"]["balanced_accuracy"] if problem == "census" else None})
                for event in trace["generation_trace"]:
                    compact = {key: value for key, value in event.items() if not key.startswith("RNG_state_")
                               and not key.endswith("mask") and key not in ("parent_before", "parent_after")}
                    events.append({"seed": seed, "problem": problem, "arm": arm, **compact,
                                   "candidate_mask": "".join(map(str, event["candidate_mask"])),
                                   "parent_before": "".join(map(str, event["parent_before"])),
                                   "parent_after": "".join(map(str, event["parent_after"])),
                                   "outcome": outcome(event), "candidate_is_empty_penalty": problem == "census" and not sum(event["candidate_mask"]),
                                   "RNG_state_before_sha256": canonical_sha256(event["RNG_state_before"]),
                                   "RNG_state_after_sha256": canonical_sha256(event["RNG_state_after"])})
                if seed == EXAMPLE_SEED:
                    for point in trace["evaluations"]:
                        example_points.append({"seed": seed, "problem": problem, "arm": arm,
                                               **{key: value for key, value in point.items() if key != "mask"},
                                               "mask": "".join(map(str, point["mask"]))})
        for arm in ARMS:
            for scale in ("weighted", "unweighted"):
                for label, values in row["test_metrics"][arm][scale]["classes"].items():
                    matrix = row["test_metrics"][arm][scale]["confusion_matrix"]
                    classes.append({"seed": seed, "arm": arm, "scale": scale, "class": label, **values,
                                    "confusion_00": matrix[0][0], "confusion_01": matrix[0][1],
                                    "confusion_10": matrix[1][0], "confusion_11": matrix[1][1]})
        for point in preparations[seed]["evaluations"]:
            preparation_points.append({"seed": seed, "bit_index": point["bit_index"],
                                       "feature_name": TRANSFORMED_FEATURE_NAMES[point["bit_index"]], "wba": point["score"],
                                       "selected_initial": point["bit_index"] == preparations[seed]["initial"]["bit_index"]})
    for name, table in (("cases.csv", cases), ("events.csv", events), ("example-raw-evaluations.csv", example_points),
                        ("class-metrics.csv", classes), ("preparation-scores.csv", preparation_points)):
        write_csv(output / name, table)
    write_csv(output / "bit-feature-map.csv", [{"bit_index": index, "raw_index": raw_index, "feature_name": name}
              for index, (raw_index, name) in enumerate(zip(TRANSFORMED_PREDICTIVE_RAW_INDICES, TRANSFORMED_FEATURE_NAMES))])
    example = next(row for row in rows if row["seed"] == EXAMPLE_SEED)
    for problem in PROBLEMS:
        plot_example(output, example, problem=problem)
        plot_all_cases(output, rows, problem=problem)
    write_results(output, summary, registry)
    write_json(output / "summary.json", summary)
    write_json(output / "report-manifest.json", {
        "schema": "eu26-21-lr-report-manifest-v1", "protocol_id": PROTOCOL_ID, "protocol_sha256": PROTOCOL_SHA256,
        "provenance": provenance, "source_run_id": sources["source_run_id"],
        "source_case_artifact_ids": summary["source_case_artifact_ids"],
        "source_preparation_artifact_ids": summary["source_preparation_artifact_ids"],
        "files": {member.name: {"sha256": file_sha256(member), "bytes": member.stat().st_size}
                  for member in sorted(output.iterdir()) if member.is_file()}, "manifest_self_hash_excluded": True})
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--registry", type=Path, required=True)
    parser.add_argument("--sources", type=Path, required=True)
    parser.add_argument("--download-ledger", type=Path, required=True)
    parser.add_argument("--expected-sha", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    summary = aggregate(root=args.root, registry_path=args.registry, sources_path=args.sources,
                        transport_path=args.download_ledger, expected_sha=args.expected_sha, output=args.output)
    print(f"PASS_LAMBDA_RESPONSE_REPORT cases={summary['cases_accounted']}")


if __name__ == "__main__":
    main()
