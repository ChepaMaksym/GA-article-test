"""Validation and descriptive analysis of registered stagnation observations.

This module never runs a search or a solver.  Scientific use, including plotting,
is restricted to the registered GitHub Actions workflow.
"""

from __future__ import annotations

from collections import Counter, defaultdict
import json
import math
from pathlib import Path
import re
from statistics import mean
from typing import Iterable


PROTOCOL_ID = "GA-KNAPSACK-STAGNATION-DIAGNOSIS-V1"
STATES = (
    "N2_NOT_LOCAL",
    "N2_STRICT_NONGLOBAL",
    "N2_NONSTRICT_NONGLOBAL",
    "GLOBAL_OPTIMUM",
)
STATE_LABELS = {
    "N2_NOT_LOCAL": "Є кращий сусід",
    "N2_STRICT_NONGLOBAL": "Строгий локальний максимум",
    "N2_NONSTRICT_NONGLOBAL": "Нестрогий локальний максимум",
    "GLOBAL_OPTIMUM": "Глобальний оптимум",
}
COMMON_PROVENANCE = (
    "protocol_id", "phase", "implementation_commit_sha", "protocol_sha256",
    "implementation_fingerprint", "bank_manifest_sha256",
)
HASH_FIELDS = (
    "protocol_sha256", "implementation_fingerprint", "bank_manifest_sha256",
    "source_sha256",
)
CHECKPOINTS = (0, 1000, 2500, 5000)


def _identity(row: dict) -> tuple[str, int]:
    instance = row.get("instance_id")
    seed = row.get("repeat_seed")
    if not isinstance(instance, str) or not re.fullmatch(r"(UC|WC|SC)-s00[0-9]", instance):
        raise ValueError("Invalid registered instance identity")
    if type(seed) is not int:
        raise ValueError("Invalid repeat seed")
    phase = row.get("phase")
    if phase == "probe":
        if instance not in {"UC-s000", "SC-s005", "SC-s000"} or seed != 92999:
            raise ValueError("Unregistered technical probe identity")
    elif phase == "main":
        if not 93001 <= seed <= 93030:
            raise ValueError("Unregistered main seed")
    else:
        raise ValueError("Invalid phase")
    if row.get("class_label") != instance[:2] or row.get("family") != instance[3:]:
        raise ValueError("Instance, class and family disagree")
    return instance, seed


def _registered_identities(phase: str) -> set[tuple[str, int]]:
    if phase == "probe":
        return {(case, 92999) for case in ("UC-s000", "SC-s005", "SC-s000")}
    return {
        (f"{label}-s{index:03d}", seed)
        for label in ("UC", "WC", "SC")
        for index in range(10)
        for seed in range(93001, 93031)
    }


def _finite(value, field: str, low: float = 0, high: float = math.inf) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"Invalid numeric {field}")
    if not math.isfinite(value) or not low <= value <= high:
        raise ValueError(f"Out-of-range {field}")
    return float(value)


def _validate_complete(row: dict) -> None:
    for field, expected in (
        ("logical_requests", 5030), ("new_evaluations", 5000),
        ("initial_evaluations", 30),
    ):
        if type(row.get(field)) is not int or row[field] != expected:
            raise ValueError(f"Incorrect {field}")
    checkpoints = row.get("checkpoints")
    if not isinstance(checkpoints, list) or [item.get("q") for item in checkpoints] != list(CHECKPOINTS):
        raise ValueError("Missing, duplicate or unordered checkpoints")
    previous = None
    for item in checkpoints:
        q = item["q"]
        last = item.get("last_improvement_q")
        age = item.get("stagnation_age")
        if type(last) is not int or not 0 <= last <= q:
            raise ValueError("Invalid last improvement index")
        if type(age) is not int or age != q - last:
            raise ValueError("Incorrect stagnation age")
        if type(item.get("stagnant")) is not bool or item["stagnant"] != (age >= 1000):
            raise ValueError("Incorrect stagnation flag")
        if item.get("state") not in STATES:
            raise ValueError("Unknown diagnostic state")
        if not isinstance(item.get("mask"), str) or not re.fullmatch(r"[01]{100}", item["mask"]):
            raise ValueError("Invalid retained mask")
        for field in ("best_profit", "best_weight"):
            if type(item.get(field)) is not int or item[field] < 0:
                raise ValueError(f"Invalid {field}")
        if not isinstance(item.get("certificate_id"), str) or not item["certificate_id"]:
            raise ValueError("Missing certificate reference")
        for field in ("population_refs", "pending_refs"):
            if not isinstance(item.get(field), list):
                raise ValueError(f"Missing {field}")
        if len(item["population_refs"]) != 30 or len(item["pending_refs"]) > 28:
            raise ValueError("Invalid population or pending prefix")
        _finite(item.get("unique_fraction"), "unique_fraction", 0, 1)
        _finite(item.get("mean_pairwise_hamming"), "mean_pairwise_hamming", 0, 100)
        if previous is not None:
            if item["best_profit"] < previous["best_profit"] or last < previous["last_improvement_q"]:
                raise ValueError("Nonmonotone strict record")
            if item["best_profit"] == previous["best_profit"]:
                if item["mask"] != previous["mask"] or last != previous["last_improvement_q"]:
                    raise ValueError("Equal record must retain its first witness")
            elif last <= previous["q"]:
                raise ValueError("Improved record has an impossible query index")
        previous = item
    if len(checkpoints[-1]["pending_refs"]) != 12:
        raise ValueError("Terminal prefix must have twelve evaluated candidates")
    timings = row.get("timings", {})
    if not isinstance(timings, dict):
        raise ValueError("Invalid time accounting")
    for field, value in timings.items():
        _finite(value, f"timings.{field}")
    if type(row.get("output_bytes")) is not int or row["output_bytes"] < 0:
        raise ValueError("Invalid byte accounting")


def summarize_runs(rows: Iterable[dict], *, expected_identities=None) -> dict:
    """Validate rows and report the registered ratio of weighted counts.

    Incomplete/unverified rows remain in completeness accounting, but never
    become observations, zeros, or successful replacements.  Source-file
    hashes may differ between instances; scientific implementation provenance
    may not differ between rows of one aggregation.
    """
    rows = list(rows)
    seen: set[tuple[str, int]] = set()
    provenance = None
    sources = {}
    complete = []
    incomplete = []
    for row in rows:
        identity = _identity(row)
        if identity in seen:
            raise ValueError("Duplicate run identity")
        seen.add(identity)
        if row.get("protocol_id") != PROTOCOL_ID:
            raise ValueError("Wrong protocol")
        commit = row.get("implementation_commit_sha")
        if not isinstance(commit, str) or not re.fullmatch(r"[0-9a-f]{40}", commit):
            raise ValueError("Invalid implementation SHA")
        for field in HASH_FIELDS:
            value = row.get(field)
            if not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{64}", value):
                raise ValueError(f"Invalid {field}")
        row_provenance = {field: row.get(field) for field in COMMON_PROVENANCE}
        if provenance is None:
            provenance = row_provenance
        elif row_provenance != provenance:
            raise ValueError("Mixed scientific provenance or phase")
        if identity[0] in sources and sources[identity[0]] != row["source_sha256"]:
            raise ValueError("Mixed instance source hashes")
        sources[identity[0]] = row["source_sha256"]
        if row.get("status") == "COMPLETE" and row.get("verified") is True:
            _validate_complete(row)
            complete.append(row)
        else:
            incomplete.append({
                "instance_id": identity[0], "repeat_seed": identity[1],
                "status": row.get("status", "MISSING_STATUS"),
                "verified": row.get("verified") is True,
                "reason": row.get("reason", row.get("error", "")),
            })
    phase = provenance["phase"] if provenance else None
    expected = (
        {tuple(identity) for identity in expected_identities}
        if expected_identities is not None else
        (_registered_identities(phase) if phase else set())
    )
    if seen - expected:
        raise ValueError("Unexpected run identities")
    missing = sorted(expected - seen)
    states = Counter({state: 0 for state in STATES})
    stagnant_states = Counter({state: 0 for state in STATES})
    by_family = defaultdict(lambda: defaultdict(list))
    terminal = []
    for row in complete:
        item = row["checkpoints"][-1]
        states[item["state"]] += 1
        if item["stagnant"]:
            stagnant_states[item["state"]] += 1
        numerator = int(item["stagnant"] and item["state"] == "N2_NOT_LOCAL")
        denominator = int(item["stagnant"])
        by_family[row["family"]][row["instance_id"]].append((numerator, denominator))
        terminal.append({
            "instance_id": row["instance_id"], "family": row["family"],
            "repeat_seed": row["repeat_seed"], "state": item["state"],
            "stagnation_age": item["stagnation_age"], "stagnant": item["stagnant"],
            "certificate_id": item["certificate_id"],
        })
    families = []
    for family, tasks in sorted(by_family.items()):
        task_rows = []
        for instance, values in sorted(tasks.items()):
            task_rows.append({
                "instance_id": instance, "runs": len(values),
                "numerator": sum(value[0] for value in values),
                "denominator": sum(value[1] for value in values),
                "numerator_mean": mean(value[0] for value in values),
                "denominator_mean": mean(value[1] for value in values),
            })
        numerator_mean = mean(task["numerator_mean"] for task in task_rows)
        denominator_mean = mean(task["denominator_mean"] for task in task_rows)
        families.append({
            "family": family, "tasks": task_rows, "task_count": len(task_rows),
            "runs": sum(task["runs"] for task in task_rows),
            "numerator": sum(task["numerator"] for task in task_rows),
            "denominator": sum(task["denominator"] for task in task_rows),
            "numerator_mean": numerator_mean, "denominator_mean": denominator_mean,
            "family_weight": 1 / len(by_family),
            "conditional_fraction": (
                numerator_mean / denominator_mean if denominator_mean else None
            ),
        })
    weighted_numerator = mean(family["numerator_mean"] for family in families) if families else 0.0
    weighted_denominator = mean(family["denominator_mean"] for family in families) if families else 0.0
    denominator = sum(stagnant_states.values())
    numerator = stagnant_states["N2_NOT_LOCAL"]
    is_complete = bool(expected) and not missing and not incomplete and len(complete) == len(expected)
    return {
        "schema_version": "knapsack-stagnation-analysis-v1",
        "protocol_id": PROTOCOL_ID,
        "phase": phase,
        "provenance": provenance,
        "completeness": {
            "status": "COMPLETE" if is_complete else "INCOMPLETE",
            "expected": len(expected), "received": len(rows), "verified_complete": len(complete),
            "missing": [{"instance_id": case, "repeat_seed": seed} for case, seed in missing],
            "incomplete": incomplete,
        },
        "inference_status": "TECHNICAL_ONLY" if phase == "probe" else (
            "DESCRIPTIVE_COMPLETE" if is_complete else "PARTIAL_DESCRIPTIVE_ONLY"
        ),
        "primary": {
            "status": "DEFINED" if weighted_denominator else "UNDEFINED",
            "value": weighted_numerator / weighted_denominator if weighted_denominator else None,
            "weighted_numerator": weighted_numerator,
            "weighted_denominator": weighted_denominator,
            "absolute_numerator": numerator, "absolute_denominator": denominator,
            "pooled_fraction": numerator / denominator if denominator else None,
            "weighting": "mean_repeats_then_mean_tasks_then_equal_families_ratio_of_counts",
            "interpretation": "TECHNICAL_ONLY" if phase == "probe" else (
                "REGISTERED_DESCRIPTIVE_ESTIMATE" if is_complete else "INCOMPLETE_NOT_FINAL"
            ),
        },
        "state_counts": dict(states),
        "stagnant_state_counts": dict(stagnant_states),
        "families": families,
        "terminal_observations": terminal,
        "evaluation_accounting": {
            "initial": 30 * len(complete), "new_search": 5000 * len(complete),
            "logical_total": 5030 * len(complete),
            "incomplete_run_evaluations_not_imputed": True,
        },
    }


def measured_main_quote(rows: Iterable[dict], summary: dict) -> dict:
    """A conservative measured quote, never a grant of execution authority."""
    rows = list(rows)
    if summary["phase"] != "probe" or summary["completeness"]["status"] != "COMPLETE":
        return {"status": "UNAVAILABLE", "reason": "Complete registered probe required", "authorized": False}
    if any("total_seconds" not in row.get("timings", {}) for row in rows):
        return {"status": "UNAVAILABLE", "reason": "Complete total timing required", "authorized": False}
    if any("aggregation_replay_seconds" not in row for row in rows):
        return {"status": "UNAVAILABLE", "reason": "Independent aggregation replay timing required", "authorized": False}
    slowest = max(_finite(row["timings"]["total_seconds"], "total_seconds") for row in rows)
    aggregation_slowest = max(_finite(row["aggregation_replay_seconds"], "aggregation_replay_seconds") for row in rows)
    largest = max(row["output_bytes"] for row in rows)
    # Explicit planning allowances: 50% runtime, 25% bytes, 30 worker jobs
    # at two minutes startup each, and ten service runner minutes.  The
    # eventual implementation must still obtain a separately approved budget.
    # The aggregation intentionally repeats the raw search and certificate
    # audit.  Its cost is additional to the same audits inside each worker.
    # Separate maxima are conservative even if different cases attain them.
    per_run_bound = slowest + aggregation_slowest
    worker_minutes = math.ceil(900 * per_run_bound * 1.5 / 60)
    return {
        "status": "MEASURED_PLANNING_ESTIMATE", "authorized": False,
        "main_runs": 900, "main_new_evaluations": 4_500_000,
        "max_measured_run_seconds": slowest, "max_measured_run_bytes": largest,
        "max_measured_aggregation_replay_seconds": aggregation_slowest,
        "per_run_worker_plus_aggregation_bound_seconds": per_run_bound,
        "runtime_reserve_factor": 1.5, "byte_reserve_factor": 1.25,
        "proposed_worker_jobs": 30, "startup_minutes_per_worker": 2,
        "service_runner_minutes": 10,
        "estimated_runner_minutes": worker_minutes + 70,
        "estimated_bytes": math.ceil(largest * 900 * 1.25),
        "limits": "Three technical cases do not bound all instance costs; approval and runtime enforcement remain mandatory.",
    }


def _percent(value) -> str:
    return "не визначено" if value is None else f"{100 * value:.2f}".replace(".", ",") + "%"


def _make_figures(output: Path, rows: list[dict], summary: dict) -> list[tuple[str, str]]:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10, "axes.spines.top": False, "axes.spines.right": False})
    figures = []
    counts = summary["stagnant_state_counts"]
    present = [state for state in STATES if counts[state]]
    if present:
        fig, ax = plt.subplots(figsize=(8.2, 4.8), layout="constrained")
        bars = ax.barh([STATE_LABELS[state] for state in present], [counts[state] for state in present], color="#355C7D")
        ax.bar_label(bars, padding=4)
        ax.set_xlabel("Кількість запусків із застоєм")
        ax.set_xlim(0, max(counts.values()) * 1.2 + 0.5)
        path = "state_composition.png"
        fig.savefig(output / path, dpi=200)
        plt.close(fig)
        figures.append((path, "Склад перевірених станів серед запусків із застоєм на завершенні пошуку."))
    observations = summary["terminal_observations"]
    grouped = {state: [item["stagnation_age"] for item in observations if item["state"] == state] for state in STATES}
    present = [state for state in STATES if grouped[state]]
    ages = {item["stagnation_age"] for item in observations}
    if len(ages) > 1:
        fig, ax = plt.subplots(figsize=(8.2, 4.8), layout="constrained")
        ax.boxplot([grouped[state] for state in present], orientation="horizontal", tick_labels=[STATE_LABELS[state] for state in present], showfliers=True)
        ax.set_xlabel("Оцінювання від останнього строгого покращення")
        ax.set_xlim(left=0)
        path = "stagnation_by_state.png"
        fig.savefig(output / path, dpi=200)
        plt.close(fig)
        figures.append((path, "Тривалість застою залежно від незалежно перевіреного стану збереженої маски."))
    seed = 92999 if summary["phase"] == "probe" else 93001
    example = next((row for row in rows if row.get("instance_id") == "UC-s000" and row.get("repeat_seed") == seed and row.get("status") == "COMPLETE" and row.get("verified") is True), None)
    if example is not None:
        trajectory = example.get("population_trajectory", [])
        if trajectory:
            fig, axes = plt.subplots(3, 1, figsize=(7.4, 8.2), sharex=True, layout="constrained")
            q = [item["q"] for item in trajectory]
            axes[0].step(q, [item["best_profit"] for item in trajectory], where="post", color="#355C7D", label="Рекорд")
            axes[0].set_ylabel("Цінність")
            axes[0].legend()
            axes[1].step(q, [item["unique_fraction"] for item in trajectory], where="post", color="#2C7A61", label="Унікальні маски")
            axes[1].set_ylabel("Частка")
            axes[1].set_ylim(-0.03, 1.03)
            axes[1].legend()
            axes[2].step(q, [item["mean_pairwise_hamming"] for item in trajectory], where="post", color="#A65A2E", label="Попарна відстань")
            axes[2].set_ylabel("Біти")
            axes[2].set_xlabel("Нові пошукові оцінювання")
            axes[2].legend()
            path = "fixed_example.png"
            fig.savefig(output / path, dpi=200)
            plt.close(fig)
            label = "Технічна ілюстрація" if summary["phase"] == "probe" else "Наперед визначений приклад"
            figures.append((path, f"{label} UC-s000, seed {seed}: рекорд і різноманітність останньої завершеної популяції. Оцінені нащадки неповного покоління впливають на рекорд, але не на склад цієї популяції."))
    return figures


def write_report(output, rows: Iterable[dict], summary: dict, *, phase: str) -> dict:
    """Write a new CI artifact report; never overwrite a thesis or its sources."""
    output = Path(output).resolve()
    checkout = Path(__file__).resolve().parents[3]
    if output == checkout or checkout in output.parents:
        raise ValueError("Generated scientific reports must be outside the source checkout")
    if phase != summary["phase"]:
        raise ValueError("Report phase mismatch")
    output.mkdir(parents=True, exist_ok=True)
    rows = list(rows)
    figures = _make_figures(output, rows, summary)
    quote = measured_main_quote(rows, summary)
    complete = summary["completeness"]
    primary = summary["primary"]
    lines = [
        "# Застій і локальна оптимальність у генетичному пошуку", "",
        "## Питання та гіпотеза", "",
        "Чи завжди відсутність покращення означає локальну оптимальність збереженого набору? Перевіряється припущення, що серед запусків із застоєм є випадки, у яких існує кращий допустимий одно- або двобітний сусід.", "",
        "## Метод", "",
        "Досліджується звичайний генетичний алгоритм для задачі рюкзака зі 100 предметами. Популяція містить 30 особин, мутація біта становить 1%, імовірність схрещування 90%. Застоєм вважається відсутність строгого рекорду протягом щонайменше 1000 нових оцінювань.", "",
        "Кожний завершений запуск містить 5000 нових оцінювань. Початкові 30 оцінок обліковуються окремо. Після пошуку незалежно перевіряються всі 5050 одно- й двобітних сусідів збережених масок. Діагностика не керує пошуком.", "",
        "## Результати", "",
        f"Незалежно перевірено {complete['verified_complete']} із {complete['expected']} запланованих запусків відповідного етапу.", "",
    ]
    if phase == "probe":
        lines += ["Наведено лише технічні проби з одним технічним початковим значенням генератора. Вони перевіряють реалізацію та ресурсні витрати, а не підтверджують гіпотезу для основної серії з 900 запусків.", ""]
    if complete["status"] != "COMPLETE":
        lines += ["Етап неповний. Відсутні та неперевірені випадки не замінено нульовими значеннями чи успішнішими повтореннями. Підсумки стосуються лише завершених перевірених записів.", ""]
    lines += [
        "| Перевірений стан | Усі завершені запуски | Запуски із застоєм |",
        "|---|---:|---:|",
    ]
    for state in STATES:
        lines.append(f"| {STATE_LABELS[state]} | {summary['state_counts'][state]} | {summary['stagnant_state_counts'][state]} |")
    lines += ["", f"Кращий сусід виявлено у {primary['absolute_numerator']} із {primary['absolute_denominator']} перевірених випадків застою. Відношення сімейно-зважених кількостей становить {_percent(primary['value'])}.", "",
        "Спочатку усереднюються повторення задачі, потім задачі сімейства. Сімейства отримують однакову вагу. Підсумок є відношенням зважених кількостей, а не середнім умовних часток сімейств.", "",
        "| Сімейство | Перевірені запуски | Застій із кращим сусідом | Усі випадки застою |",
        "|---|---:|---:|---:|",
    ]
    for family in summary["families"]:
        lines.append(f"| {family['family']} | {family['runs']} | {family['numerator']} | {family['denominator']} |")
    for index, (path, caption) in enumerate(figures, 1):
        lines += ["", f"![{caption}]({path})", "", f"Рисунок {index}. {caption}"]
    if len({item["stagnation_age"] for item in summary["terminal_observations"]}) <= 1:
        lines += ["", "Тривалість застою не має варіації у наявних перевірених записах, тому окремий графік не наведено."]
    if not figures or not any(path == "fixed_example.png" for path, _ in figures):
        lines += ["", "Траєкторія наперед визначеного прикладу відсутня серед завершених перевірених матеріалів. Інший випадок замість нього не обирався."]
    lines += ["", "## Обмеження та висновок", "",
        "Сертифікат стосується конкретної збереженої маски, а не всієї популяції. Рівноцінний сусід не доводить замкненості всього плато. Застій не є самостійним доказом локальної або глобальної оптимальності.", "",
        ("Технічні результати не встановлюють частоти станів у майбутній основній серії. Її запуск потребує окремого погодження виміряного кошторису." if phase == "probe" else "Частки описують визначені задачі, початки та бюджет. Вони не доводять універсальної поведінки генетичних алгоритмів."), "",
        "## Додаток. Походження та ресурсні витрати", "",
        "Технічні ідентифікатори та часові вимірювання наведено окремо від наукового викладу.", "",
        "```json", json.dumps({"provenance": summary["provenance"], "completeness": complete, "quote": quote}, ensure_ascii=False, indent=2), "```", "",
    ]
    (output / "report.md").write_text("\n".join(lines), encoding="utf-8")
    (output / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (output / "main_quote.json").write_text(json.dumps(quote, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {"report": "report.md", "summary": "summary.json", "quote": "main_quote.json", "figures": [path for path, _ in figures]}
