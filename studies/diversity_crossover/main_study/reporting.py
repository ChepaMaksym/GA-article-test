"""Registered research figures and the complete compact numerical appendix.

CI-only rendering consumes already calculated analysis and independently replayed
traces. It executes neither a search nor additional inferential tests.
"""

from __future__ import annotations

import csv
import json
import math
from pathlib import Path
from typing import Mapping, Sequence

from .analysis import BUDGET, METHODS, PROTOCOL, SEEDS, TASKS, escape_observation, finite, identity, require
from .contract import ci_only

LABELS = {"baseline": "Базовий", "directed": "Спрямований", "repeated": "Повторний", "mutation_control": "Лише мутація"}
STYLES = {"baseline": ("#202020", "-"), "directed": ("#17649a", "--"), "repeated": ("#b45324", "-."), "mutation_control": ("#787878", ":")}


def number(value, *, scale=1, digits=4):
    return "не застосовується" if value is None else f"{value * scale:.{digits}f}"


def interval_text(interval):
    if interval["status"] != "DEFINED_BCA":
        return f"UNDEFINED_BCA ({interval['reason']}); межі не встановлено"
    return f"[{number(interval['lower'], scale=100)}; {number(interval['upper'], scale=100)}] в.п."


def validate_traces(traces, rows):
    """Validate the fixed examples without manufacturing missing trajectories."""
    indexed = {identity(row): row for row in rows if row["status"] == "COMPLETE"}
    expected = {(task, start, method, 71001) for task in ("UC-s000", "Jump4") for start in ("cloned", "bank") for method in METHODS}
    found = {}
    for item in traces or []:
        key = identity(item)
        require(key in expected and key not in found and key in indexed, "unregistered, duplicate, or unsupported example trace")
        points = item["points"]
        require(isinstance(points, list) and len(points) >= 2 and points[0]["call"] == 0 and points[-1]["call"] == BUDGET,
                "trace lacks initial/terminal state")
        previous_call, previous_record = -1, -math.inf
        for point in points:
            call, record = point["call"], finite(point["best_value"], "trace record")
            require(type(call) is int and previous_call < call <= BUDGET and record >= previous_record, "trace call/record order differs")
            if point["mean_feasible_value"] is not None:
                require(0 <= finite(point["mean_feasible_value"], "trace feasible mean") <= record, "trace population mean exceeds record")
            require(0 <= finite(point["diversity"], "trace D") <= 1, "trace D outside [0,1]")
            previous_call, previous_record = call, record
        search = indexed[key]["search"]
        require(points[0]["best_value"] == search["initial_record"]["score"]["value"] and
                points[-1]["best_value"] == search["record"]["score"]["value"], "trace/compact record endpoints differ")
        for field in ("diversity", "mean_feasible_value"):
            require(math.isclose(finite(points[-1][field], field), finite(search["metrics"][field], field), rel_tol=1e-12, abs_tol=1e-15),
                    "trace/compact population endpoint differs")
        found[key] = points
    order = lambda key: (("UC-s000", "Jump4").index(key[0]), ("cloned", "bank").index(key[1]), METHODS.index(key[2]))
    return found, [list(key) for key in sorted(expected - found.keys(), key=order)]


def save_figure(fig, output, stem):
    files = []
    for extension in ("png", "pdf"):
        relative = f"figures/{stem}.{extension}"
        fig.savefig(output / relative, dpi=180)
        files.append(relative)
    return files


def primary_figures(output, rows, analysis, traces=None):
    ci_only()
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.lines import Line2D

    (output / "figures").mkdir(parents=True, exist_ok=True)
    h1, h2 = analysis["primary"]["H1"], analysis["primary"]["H2"]
    files = []
    fig, axes = plt.subplots(1, 3, figsize=(15, 4.7), gridspec_kw={"width_ratios": [1, 1.05, 1.7]})
    pairs = h1["paired_table"]
    cells = [[pairs["both_fail"], pairs["directed_only"]], [pairs["baseline_only"], pairs["both_succeed"]]]
    axes[0].axis("off")
    table = axes[0].table(cellText=cells, rowLabels=["Базовий: невихід", "Базовий: вихід"],
                          colLabels=["Спрямований:\nневихід", "Спрямований:\nвихід"], cellLoc="center", loc="center")
    table.auto_set_font_size(False)
    table.set_fontsize(9)
    table.scale(1, 2.4)
    axes[0].set_title("Усі 30 пар seeds")
    axes[1].axvline(0, color="#9ca3af", linewidth=1)
    estimate, interval = h1["estimate_percentage_points"], h1["supplementary_bca"]
    axes[1].plot([estimate], [0], "o", color=STYLES["directed"][0])
    if interval["status"] == "DEFINED_BCA":
        axes[1].hlines(0, interval["lower"] * 100, interval["upper"] * 100, color=STYLES["directed"][0], linewidth=2)
    else:
        axes[1].text(0.5, 0.2, "Додатковий BCa:\nUNDEFINED_BCA", transform=axes[1].transAxes, ha="center", fontsize=9)
    axes[1].set_yticks([])
    axes[1].set_ylim(-1, 1)
    axes[1].set_xlabel("Спрямований − базовий, в.п.")
    axes[1].set_title(f"Δ_J = {estimate:.2f} в.п.\nТочний p = {h1['exact_p']:.6g}; α=0,025")
    for method in ("baseline", "directed"):
        selected = [row for row in rows if row["task"] == "Jump4" and row["start"] == "cloned" and row["method"] == method]
        require(len(selected) == len(SEEDS), "H1 escape curve lacks paired observations")
        calls = [row["escape_call"] for row in selected if row["escape"]]
        xs = sorted({0, BUDGET, *calls})
        ys = [100 * sum(call <= x for call in calls) / len(selected) for x in xs]
        color, style = STYLES[method]
        axes[2].step(xs, ys, where="post", color=color, linestyle=style, label=LABELS[method])
    axes[2].set(xlim=(0, BUDGET), ylim=(0, 100), xlabel="Нові пошукові оцінювання", ylabel="Накопичені виходи з усіх 30 запусків, %", title="Невиходи залишаються у знаменнику")
    axes[2].legend()
    axes[2].grid(alpha=0.2)
    fig.suptitle("H1: чи частіше спрямований добір знаходить глобальний набір Jump4 зі старту копій?")
    fig.text(0.5, 0.01, "Основний критерій — точний двосторонній Мак-Немар. BCa 97,5% додатковий; практичний поріг не визначено.", ha="center", fontsize=8)
    fig.tight_layout(rect=(0.035, 0.045, 1, 0.91))
    files += save_figure(fig, output, "main-H1")
    plt.close(fig)

    fig = plt.figure(figsize=(13, 8))
    grid = fig.add_gridspec(2, 3, height_ratios=[1.8, 1])
    contrast = fig.add_subplot(grid[0, :])
    families = h2["family_contrasts"]
    names = [item["family"] for item in families] + ["Δ_K: рівні сімейства"]
    values = [100 * item["value"] for item in families] + [100 * h2["estimate"]]
    ys = list(range(len(names)))
    contrast.scatter(values[:-1], ys[:-1], color="#787878", label="Описові сімейні різниці")
    contrast.scatter(values[-1:], ys[-1:], color=STYLES["repeated"][0], marker="D", label="Первинний Δ_K")
    interval = h2["bca"]
    if interval["status"] == "DEFINED_BCA":
        contrast.hlines(ys[-1], interval["lower"] * 100, interval["upper"] * 100, color=STYLES["repeated"][0], linewidth=2)
    else:
        contrast.annotate("UNDEFINED_BCA: лише описова оцінка", (values[-1], ys[-1]), xytext=(10, -15), textcoords="offset points", fontsize=8)
    contrast.set_yticks(ys, names)
    contrast.invert_yaxis()
    contrast.axvline(0, color="#9ca3af", linewidth=1)
    contrast.set_xlabel("Повторний − базовий: частка корисних кінцевих кандидатів / 5000, в.п.")
    contrast.legend(loc="best", fontsize=9)
    contrast.grid(axis="x", alpha=0.2)
    methods = {entry["method"]: entry for entry in analysis["knapsack_bank_method_summaries"]}
    panels = (("equal_family_crossover_query_fraction", "Запити схрещування\n/ всі 5000 запитів"),
              ("equal_family_candidate_feasible_fraction", "Допустимі кінцеві кандидати\n/ всі 5000 запитів"),
              ("conditional_productivity_pooled", "U_post / N_both_feasible\n(об'єднані умовні підрахунки)"))
    for col, (field, title) in enumerate(panels):
        axis = fig.add_subplot(grid[1, col])
        for position, method in enumerate(("baseline", "repeated")):
            raw = methods[method][field]
            value = raw["value"] if isinstance(raw, dict) else raw
            if value is None:
                axis.text(position, 0.05, "NOT_APPLICABLE", rotation=90, ha="center", va="bottom", fontsize=8)
            else:
                axis.bar(position, 100 * value, color=STYLES[method][0], width=0.6)
        axis.set_xticks([0, 1], [LABELS[method] for method in ("baseline", "repeated")])
        axis.set_ylabel("%")
        axis.set_title(title, fontsize=10)
        axis.grid(axis="y", alpha=0.2)
        axis.set_ylim(bottom=0)
    fig.suptitle("H2: чи дає повторний профіль більше корисних кандидатів за однакові витрати?")
    fig.text(0.5, 0.01, "Парні seeds → задача → три класи сімейства → десять рівних сімейств. BCa 97,5%, 50 000 перевибірок сімейств.\nУмовна частка — діагностика; пакет із чотирьох витрачає чотири запити.", ha="center", fontsize=8)
    fig.tight_layout(rect=(0, 0.065, 1, 0.94))
    files += save_figure(fig, output, "main-H2")
    plt.close(fig)

    trace_map, missing = validate_traces(traces, rows)
    fig, axes = plt.subplots(3, 4, figsize=(17, 9), sharex=True)
    examples = [(task, start) for task in ("UC-s000", "Jump4") for start in ("cloned", "bank")]
    for col, (task, start) in enumerate(examples):
        available = False
        for method in METHODS:
            points = trace_map.get((task, start, method, 71001))
            if points is None:
                continue
            available = True
            color, style = STYLES[method]
            xs = [point["call"] for point in points]
            for axis, field in zip(axes[:, col], ("best_value", "mean_feasible_value", "diversity"), strict=True):
                axis.step(xs, [math.nan if point[field] is None else point[field] for point in points], where="post", color=color, linestyle=style, linewidth=1.2)
        for axis in axes[:, col]:
            axis.grid(alpha=0.2)
            axis.set_xlim(0, BUDGET)
            if not available:
                axis.text(0.5, 0.5, "Немає перевірених даних", transform=axis.transAxes, ha="center", fontsize=9)
        ds = [point["diversity"] for method in METHODS for point in trace_map.get((task, start, method, 71001), [])]
        axes[2, col].set_ylim(0, min(1, max(0.05, max(ds, default=0) * 1.1)))
        axes[0, col].set_title(f"{task}: {'копії' if start == 'cloned' else 'банк'}")
        axes[2, col].set_xlabel("Нові оцінювання")
        absent = [LABELS[method] for method in METHODS if (task, start, method, 71001) not in trace_map]
        if absent and available:
            axes[0, col].text(0.02, 0.02, "Пропуск: " + ", ".join(absent), transform=axes[0, col].transAxes, fontsize=7)
    for axis, label in zip(axes[:, 0], ("Рекорд", "Середня допустима\nцінність", "Нормоване D"), strict=True):
        axis.set_ylabel(label)
    handles = [Line2D([0], [0], color=STYLES[method][0], linestyle=STYLES[method][1], label=LABELS[method]) for method in METHODS]
    fig.legend(handles=handles, loc="upper center", ncol=4, bbox_to_anchor=(0.5, 0.945))
    fig.suptitle("Що відбувається з популяцією? Наперед обраний seed 71001, два початки")
    fig.text(0.5, 0.012, "Окремі приклади, не довірчі інтервали. Лінії з однаковими значеннями не зміщено. Пропуски не відновлено інтерполяцією.", ha="center", fontsize=8)
    fig.tight_layout(rect=(0, 0.045, 1, 0.9))
    files += save_figure(fig, output, "main-trajectories")
    plt.close(fig)
    return files, missing


def render_report(analysis):
    lines = ["# Основне порівняння добору батьків і повторного схрещування", "", f"Протокол {PROTOCOL}. Статус: {analysis['status']}.", "",
             f"Повні незалежно перевірені запуски: {analysis['complete_runs']}/{analysis['expected_runs']}; нові пошукові оцінювання: {analysis['completed_search_calls']:,}.", ""]
    if analysis["status"] != "COMPLETE_MAIN":
        return "\n".join(lines + ["Первинний аналіз не виконано: сукупність неповна. Відсутні або невиконані вимірювання не зараховано як нулі чи невиходи.", ""])
    h1, h2 = analysis["primary"]["H1"], analysis["primary"]["H2"]
    table = h1["paired_table"]
    lines += ["## H1: вихід на Jump4 зі старту копій", "", "| Базовий метод | Спрямований: невихід | Спрямований: вихід |", "| --- | ---: | ---: |",
              f"| Невихід | {table['both_fail']} | {table['directed_only']} |", f"| Вихід | {table['baseline_only']} | {table['both_succeed']} |", "",
              f"Δ_J = {number(h1['estimate'], scale=100)} в.п.; точний двосторонній p = {h1['exact_p']:.8g}, α=0,025. Додатковий 97,5% BCa: {interval_text(h1['supplementary_bca'])}.", "",
              ("Зареєстрований точний критерій дає номінальне свідчення вищої частоти виходу спрямованого методу на Jump4 у цих умовах." if h1["nominal_superiority_supported"] else
               "Зареєстрований критерій не встановив вищої частоти виходу спрямованого методу. Це не доказ рівності."), "",
              "Одиниця аналізу — ціла парна реалізація seed; запити всередині запуску не є незалежними спостереженнями.", "",
              "![H1: парна таблиця, ефект і накопичені виходи](figures/main-H1.png)", "",
              "## H2: корисні кінцеві кандидати за однаковий бюджет", "",
              f"Δ_K = {number(h2['estimate'], scale=100)} в.п.; 97,5% BCa: {interval_text(h2['bca'])}.", "",
              ("Нижня межа зареєстрованого інтервалу перевищує нуль: є номінальне свідчення переваги повторного профілю за цим показником на обраному наборі." if h2["nominal_superiority_supported"] else
               "Додатної переваги повторного профілю за зареєстрованим правилом не встановлено; за UNDEFINED_BCA збережено тільки описову оцінку."), "",
              "U_post рахує допустимих кінцевих нащадків гілки схрещування, строго кращих за обох допустимих батьків. Знаменник — усі 5000 нових запитів; враховано невибраних нащадків і останній префікс. Ефект стосується повного повторного профілю, частка запитів схрещування й кількість замін якого відрізняються. U_post може включати користь мутації й не ізолює причинний ефект схрещування.", "",
              "| Сімейство | Задачі | Повторний − базовий, в.п. |", "| --- | --- | ---: |"]
    for family in h2["family_contrasts"]:
        lines.append(f"| {family['family']} | {', '.join(family['tasks'])} | {number(family['value'], scale=100)} |")
    lines += ["", "Парні seeds усереднено до задачі, три класи до сімейства, десять сімейств мають рівні ваги. 50 000 перевибірок і jackknife вилучають цілі сімейства. Десять сімейств не гарантують незалежності чи представлення всіх задач рюкзака.", "",
              "![H2: сімейні різниці, первинний інтервал і знаменники](figures/main-H2.png)", "",
              "## Діагностика знаменників", "", "| Метод | U_post / всі запити, % | Запити схрещування, % | Допустимі кандидати, % | Умовна U_post / N_both_feasible, % |", "| --- | ---: | ---: | ---: | ---: |"]
    for item in analysis["knapsack_bank_method_summaries"]:
        lines.append(f"| {LABELS[item['method']]} | {number(item['equal_family_q'], scale=100)} | {number(item['equal_family_crossover_query_fraction'], scale=100)} | {number(item['equal_family_candidate_feasible_fraction'], scale=100)} | {number(item['conditional_productivity_pooled']['value'], scale=100)} |")
    lines += ["", "Перші три частки мають рівні сімейні ваги. Умовна частка об'єднує чисельники й знаменники й залишається діагностикою; нульовий знаменник означає NOT_APPLICABLE. U_pre оцінено після пошуку й не включено до нових пошукових запитів.", "",
              "## Локальні центри: лише описові результати", "", "| Метод | Абсолютні виходи | Рівно-сімейна частота, % | Сімейно-зважене обмежене число запитів | Строгі центри: виходи | SC-s005-плато: виходи |", "| --- | ---: | ---: | ---: | ---: | ---: |"]
    for item in analysis["local_family_summaries"]:
        lines.append(f"| {LABELS[item['method']]} | {item['raw_escapes']} / {item['runs']} | {number(item['equal_family_escape_rate'], scale=100)} | {number(item['equal_family_restricted_calls'], digits=2)} | {item['strict_centers']['escapes']} / {item['strict_centers']['runs']} | {item['plateau']['escapes']} / {item['plateau']['runs']} |")
    lines += ["", "Невихід має T=5000 та окремий прапорець цензурування; вихід на запиті 5000 має те саме T, але інший статус. Нерівна кількість локальних задач у сімействах дозволяє загальній частці й сімейній оцінці різнитися. Невихід не доводить глобальності; для одного плато окремого тесту немає.", "",
              "## Наперед обрані траєкторії", "", "![Рекорд, середня допустима цінність і D: UC-s000 та Jump4, seed 71001](figures/main-trajectories.png)", "",
              "Обидва початки й усі методи показано без штучного зміщення ліній. Це приклади, не довірчі інтервали; відсутні дані не інтерполюються.", "",
              "## Межі висновків і числовий додаток", "",
              "Є лише дві первинні статистичні заяви. Інші початки, Jump8, OneMax, Flat, глобальні контролі й порівняння описові без додаткових p-значень. Для Flat зростання якості не оцінюється. Пілотний seed 70001 не включено. Практичні пороги не визначено: практично значущу або універсальну перевагу не заявлено; 30 seeds не гарантують потужності.", "",
              "Параметри цього дослідження сталі; адаптації λ немає. Воно не є завершеною реплікацією статей і не встановлює нового алгоритму. Банк і клони відрізняються одночасно якістю, різноманітністю та локальністю й не ізолюють вплив D.", "",
              "analysis.json містить первинні оцінки, всі парні різниці, сімейні ваги й описові групи. run-metrics.csv містить усі 6304 фізичні запуски, включно з 64 глобальними контролями. Повні журнали, свідки й хеші — у джерельних пакетах; підготовчі й перевірні оцінювання та runner-хвилини обліковуються окремо.", ""]
    return "\n".join(lines)


def write_appendix(output, rows):
    relative = "run-metrics.csv"
    fields = ("task", "start", "method", "seed", "series", "status", "verification_status", "new_calls", "initial_value", "terminal_value", "relative_gap", "escape_status", "escape", "escape_call", "restricted_calls", "censored", "crossover_candidates", "both_parents_feasible_candidates", "U_pre", "U_post", "q_per_5000", "conditional_status", "conditional_productivity", "candidate_feasible", "invalid_candidates", "duplicate_candidates", "accepted_replacements", "incomplete_batches", "terminal_mean_feasible_value", "terminal_unique_fraction", "terminal_D", "directed_active_steps", "directed_changed_position_steps")
    order = lambda row: (TASKS.index(row["task"]), ("cloned", "bank").index(row["start"]), row["seed"], METHODS.index(row["method"]))
    with (output / relative).open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for row in sorted(rows, key=order):
            record = {key: row.get(key) for key in fields[:7]}
            if row["status"] == "COMPLETE":
                search, product, event = row["search"], row["productivity"], escape_observation(row)
                record.update(new_calls=search["new_calls"], initial_value=row["initial_value"], terminal_value=search["record"]["score"]["value"], relative_gap=row["relative_gap"], escape_status=event["status"], escape=event["event"], escape_call=event["call"], restricted_calls=event["restricted_calls"], censored=event["censored"], crossover_candidates=product["crossover_candidates"], both_parents_feasible_candidates=product["both_parents_feasible_candidates"], U_pre=product["pre_mutation_better_than_both"], U_post=product["post_mutation_better_than_both"], q_per_5000=product["post_mutation_better_than_both"] / BUDGET, conditional_status=product["conditional_status"], conditional_productivity=product["post_mutation_better_fraction"], candidate_feasible=search["candidate_feasible"], invalid_candidates=search["invalid_candidates"], duplicate_candidates=search["duplicate_candidates"], accepted_replacements=search["accepted_steps"], incomplete_batches=search["incomplete_steps"], terminal_mean_feasible_value=search["metrics"]["mean_feasible_value"], terminal_unique_fraction=search["metrics"]["unique_fraction"], terminal_D=search["metrics"]["diversity"], directed_active_steps=row["directed_activity"]["active_steps"], directed_changed_position_steps=row["directed_activity"]["changed_position_steps"])
            writer.writerow(record)
    return relative


def report(output, rows, analysis, traces=None):
    """Render calculated analysis; source/transport provenance belongs to aggregate."""
    ci_only()
    require(analysis["protocol_id"] == PROTOCOL, "report protocol mismatch")
    destination = Path(output)
    destination.mkdir(parents=True, exist_ok=True)
    figures, missing = primary_figures(destination, rows, analysis, traces) if analysis["status"] == "COMPLETE_MAIN" else ([], [])
    appendix = write_appendix(destination, rows)
    (destination / "analysis.json").write_text(json.dumps(analysis, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    text = render_report(analysis)
    if missing:
        text += "\nПропущені перевірені приклади траєкторій: " + "; ".join("/".join(map(str, key)) for key in missing) + ".\n"
    (destination / "RESULTS_UK.md").write_text(text, encoding="utf-8")
    return {"files": ["RESULTS_UK.md", "analysis.json", appendix, *figures], "figures": figures, "missing_example_traces": missing}
