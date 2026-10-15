"""CI-only descriptive reporting of the sixteen already verified pilot logs.

This module does not run a search, solver, bootstrap or significance test.  It
does not turn one technical seed into an estimate of algorithmic superiority.
"""

from __future__ import annotations

from collections import Counter
import gzip
import math
import os
from pathlib import Path, PurePosixPath

from . import contract as c


METHOD_LABELS = {"fixed": "Стала мутація", "adaptive_mutation": "Адаптивна мутація"}
START_LABELS = {"cloned": "копії центра", "bank": "випадковий банк"}


def _initial_record(log):
    values = [score["profit"] for score in log["initial_scores"] if score["feasible"]]
    c.require(bool(values), "The registered beginnings must have a feasible initial record")
    return max(values)


def _population_points(log):
    """Population statistics at observed checkpoints, never candidate averages."""
    scores = list(log["initial_scores"]) + [
        {name: row[name] for name in ("weight", "profit", "feasible")}
        for row in log["candidates"]]
    points = []
    checkpoints = [(0, list(range(30)))] + [
        (event["end_call"], event["population_after"]) for event in log["generations"]]
    for call, population in checkpoints:
        c.require(len(population) == 30 and all(type(ref) is int and 0 <= ref < len(scores)
                                              for ref in population), "Invalid population reference")
        feasible = [scores[ref]["profit"] for ref in population if scores[ref]["feasible"]]
        points.append({"call": call, "feasible_count": len(feasible),
                       "mean_feasible_profit": sum(feasible) / len(feasible) if feasible else None})
    return points


def _describe(log, row, case):
    candidates, generations = log["candidates"], log["generations"]
    initial, summary = _initial_record(log), log["summary"]
    c.require(log["budget"] == 5000 and len(candidates) == 5000 and
              summary["new_calls"] == summary["physical_evaluations"] == 5000,
              "Incomplete reporting input")
    calls = [candidate["call"] for candidate in candidates]
    c.require(calls == list(range(1, 5001)), "Candidate calls must be complete and consecutive")
    improvements = [candidate["call"] for candidate in candidates
                    if candidate["feasible"] and candidate["profit"] > initial]
    first = improvements[0] if improvements else None
    c.require(row["initial_record"] == initial and row["first_improvement_call"] == first and
              row["calls_to_improvement_capped"] == (first if first is not None else 5000),
              "Stored and reconstructed improvement endpoints differ")
    records = [initial] + [candidate["record_profit"] for candidate in candidates]
    c.require(all(type(value) is int for value in records) and
              all(a <= b for a, b in zip(records, records[1:])) and
              records[-1] == summary["best_profit"], "Invalid feasible-record trajectory")
    complete = [event for event in generations if event["complete"]]
    strict = [event for event in complete if event["record_after"] is not None and
              (event["record_before"] is None or event["record_after"] > event["record_before"])]
    increases = [event for event in complete if event["p_m_next"] > event["p_m"]]
    decreases = [event for event in complete if event["p_m_next"] < event["p_m"]]
    doubles = [event for event in complete if event["controller_event"] == "STAGNATION_DOUBLE"]
    halves = [event for event in complete if event["controller_event"] == "SUCCESS_HALVE"]
    observed_flips = [len(candidate["mutation_bits"]) for candidate in candidates]
    expected_total = sum((event["end_call"] - event["start_call"] + 1) *
                         log["problem"]["n"] * event["p_m"] for event in generations)
    points = _population_points(log)
    optimum = case["exact"]["confirmed_optimum"]
    center_profit = case["certificate"]["center"]["profit"]
    global_control = row["start"] == "cloned" and center_profit == optimum
    if global_control:
        endpoint = "GLOBAL_NEGATIVE_CONTROL"
        endpoint_label = "глобальний негативний контроль"
        c.require(initial == optimum == summary["best_profit"] and first is None,
                  "A global-center negative control reported an impossible improvement")
    elif row["start"] == "cloned":
        endpoint = "ESCAPE_FROM_CERTIFIED_CENTER"
        endpoint_label = "вихід із підтвердженого неглобального центра"
        c.require(case["status"].startswith("ADMITTED_") and initial == center_profit < optimum,
                  "A cloned non-global start lacks its certified-center binding")
    else:
        endpoint = "IMPROVEMENT_OF_BANK_RECORD"
        endpoint_label = "поліпшення початкового рекорду банку"
    c.require(summary["best_profit"] <= optimum, "Reported record exceeds the external exact optimum")
    return {
        "task": row["task"], "start": row["start"], "method": row["method"], "seed": 76001,
        "endpoint": endpoint, "endpoint_label": endpoint_label,
        "center_status": case["status"], "external_exact_optimum": optimum,
        "initial_record": initial, "final_record": summary["best_profit"],
        "record_gain": summary["best_profit"] - initial,
        "first_improvement_call": first, "improvement_observed": first is not None,
        "restricted_calls": first if first is not None else 5000, "censored": first is None,
        "new_calls": 5000, "engine_initial_score_validation_checks": summary["known_score_validation_evaluations"],
        "independent_log_score_checks": row["verification"]["independent_score_checks"],
        "duplicate_calls": summary["duplicate_calls"], "infeasible_calls": summary["infeasible_calls"],
        "strict_record_improvement_generations": len(strict),
        "halving_triggers": len(halves), "doubling_triggers": len(doubles),
        "actual_probability_increases": len(increases), "actual_probability_decreases": len(decreases),
        "unchanged_at_trigger_bounds": sum(event["p_m_next"] == event["p_m"] for event in halves + doubles),
        "final_mutation_probability": summary["final_mutation_probability"],
        "full_generations": summary["full_generations"], "partial_children": summary["partial_children"],
        "mean_observed_mutated_bits": sum(observed_flips) / 5000,
        "mean_conditional_expected_mutated_bits": expected_total / 5000,
        "observed_mutation_bit_histogram": {str(k): v for k, v in sorted(Counter(observed_flips).items())},
        "final_population_feasible_count": points[-1]["feasible_count"],
        "final_population_mean_feasible_profit": points[-1]["mean_feasible_profit"],
        "controller_triggers": [{name: event[name] for name in (
            "generation", "end_call", "p_m", "p_m_next", "controller_event",
            "record_before", "record_after")} for event in generations
            if event["controller_event"] in ("SUCCESS_HALVE", "STAGNATION_DOUBLE")],
        "journal": row["journal"], "journal_identity": row["journal_identity"],
    }


def _read_verified_logs(output, pilot):
    registration = c.read_json(c.MODULE / "registration.json")
    expected = {(task, start, method) for task in registration["tasks"]
                for start in registration["starts"] for method in registration["methods"]}
    c.require(pilot.get("protocol_id") == c.PROTOCOL and
              pilot.get("status") == "COMPLETE_TECHNICAL_PILOT" and
              pilot.get("runs") == 16 and pilot.get("new_calls") == 80000 and
              pilot.get("technical_seed") == 76001 and pilot.get("superiority_tested") is False and
              pilot.get("bootstrap_performed") is False and
              pilot.get("implementation_sha") == os.environ.get("GITHUB_SHA") and
              pilot.get("source_manifest") == c.source_manifest(), "Wrong pilot report identity")
    seen, logs, descriptions = set(), {}, []
    for row in pilot["results"]:
        identity = row["task"], row["start"], row["method"]
        c.require(identity in expected - seen and row["seed"] == 76001, "Duplicate or unauthorized pilot row")
        seen.add(identity)
        relative = PurePosixPath(row["journal"])
        expected_path = f"journals/{row['task']}-{row['start']}-{row['method']}.json.gz"
        path = output / relative
        c.require(row["journal"] == expected_path and not relative.is_absolute() and
                  ".." not in relative.parts and "\\" not in row["journal"] and
                  path.resolve().is_relative_to(output) and not path.is_symlink() and
                  c.identity(path) == row["journal_identity"], "Unbound or corrupted pilot journal")
        with gzip.open(path, "rb") as stream:
            content = stream.read(128 * 1024 * 1024 + 1)
        c.require(len(content) <= 128 * 1024 * 1024, "Oversized expanded journal")
        envelope = c.json.loads(content)
        c.require(envelope["task"] == row["task"] and envelope["start"] == row["start"] and
                  envelope["seed"] == 76001 and all(envelope["provenance"].get(name) == pilot.get(name)
                  for name in ("protocol_id", "implementation_sha", "run_id", "run_attempt", "source_manifest")),
                  "Journal and pilot provenance differ")
        log = envelope["log"]
        verification = envelope["verification"]
        c.require(log["method"] == row["method"] and
                  verification == row["verification"] and verification["verification_status"] == "VERIFIED" and
                  verification["summary"] == log["summary"] == row["summary"], "Missing verified-log binding")
        case = c.read_json(c.ROOT /
            f"studies/knapsack_parameters/evidence/run-37637475385/cases/{row['task']}/case.json")
        logs[identity] = log
        descriptions.append(_describe(log, row, case))
    c.require(seen == expected and len(descriptions) == 16, "Incomplete descriptive report")
    return logs, descriptions


def _draw_uc(output, logs, descriptions):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.backends.backend_pdf import PdfPages

    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10,
                         "axes.titlesize": 12, "axes.labelsize": 11,
                         "figure.facecolor": "white", "axes.facecolor": "white",
                         "axes.spines.top": False, "axes.spines.right": False,
                         "pdf.fonttype": 42})
    indexed = {(row["task"], row["start"], row["method"]): row for row in descriptions}
    figures = []
    with PdfPages(output / "Прості_графіки_мутації.pdf",
                  metadata={"Title": "Власна адаптація мутації: технічний пілот",
                            "Author": "", "CreationDate": None, "ModDate": None}) as pdf:
        for start in ("cloned", "bank"):
            fig, axes = plt.subplots(3, 1, figsize=(12, 11.5), sharex=True)
            fig.subplots_adjust(left=.11, right=.97, bottom=.12, top=.92, hspace=.35)
            invalid_notes = []
            for method, style, color, marker in (("fixed", "--", ".4", "."),
                                                  ("adaptive_mutation", "-", "black", "x")):
                log = logs[("UC-s000", start, method)]
                description = indexed[("UC-s000", start, method)]
                candidates, generations = log["candidates"], log["generations"]
                feasible = [row for row in candidates if row["feasible"]]
                axes[0].scatter([row["call"] for row in feasible], [row["profit"] for row in feasible],
                                s=4, marker=marker, color=".55", alpha=.16, linewidths=.3,
                                rasterized=True, label=f"Кандидати: {METHOD_LABELS[method].lower()}")
                axes[0].plot([0] + [row["call"] for row in candidates],
                             [description["initial_record"]] + [row["record_profit"] for row in candidates],
                             linestyle=style, color=color, linewidth=2,
                             label=(f"Рекорд, {METHOD_LABELS[method].lower()}: "
                                    f"{description['initial_record']} → {description['final_record']} "
                                    f"(Δ {description['record_gain']:+d})"))
                invalid_notes.append(f"{METHOD_LABELS[method]}: {description['infeasible_calls']}/5000")
                population = _population_points(log)
                axes[1].step([point["call"] for point in population],
                             [point["mean_feasible_profit"] for point in population], where="post",
                             linestyle=style, color=color, linewidth=1.8, label=METHOD_LABELS[method])
                # The parameter shown is the one used by each query, not an update
                # retroactively assigned to the generation that produced it.
                x = [0] + [event["start_call"] for event in generations] + [5000]
                y = [100 / log["problem"]["n"]] + [100 * event["p_m"] for event in generations] + [
                    100 * generations[-1]["p_m"]]
                axes[2].step(x, y, where="post", linestyle=style, color=color,
                             linewidth=1.8, label=METHOD_LABELS[method])
            axes[0].set_title("Кандидати й рекорд: чи було знайдено кращий набір?")
            axes[0].set_ylabel("Цінність допустимого набору")
            axes[0].legend(frameon=False, fontsize=8, loc="lower right", ncols=1)
            axes[0].text(.01, .03, "Недопустимі не прирівняно до нуля; їх кількість:\n" +
                         "; ".join(invalid_notes), transform=axes[0].transAxes, fontsize=8,
                         va="bottom", bbox={"facecolor": "white", "edgecolor": "none", "alpha": .85})
            axes[1].set_title("Популяція: як змінювалася середня допустима цінність?")
            axes[1].set_ylabel("Середнє лише допустимих особин")
            axes[1].legend(frameon=False, fontsize=9)
            axes[2].set_title("Мутація: коли і на скільки змінювався параметр?")
            axes[2].set_ylabel("Імовірність зміни біта, %")
            axes[2].set_yticks([1, 2, 4, 8])
            axes[2].set_ylim(.5, 8.5)
            axes[2].legend(frameon=False, fontsize=9)
            for ax in axes:
                ax.set_xlim(0, 5000)
                ax.grid(color=".88", linewidth=.6)
                ax.set_axisbelow(True)
            axes[-1].set_xlabel("Нові оцінювання; відомий початок — точка 0")
            fig.suptitle(f"UC-s000 • {START_LABELS[start]} • технічний seed 76001", fontsize=16)
            fig.text(.11, .07, "Рекорд не спадає за означенням; окремі кандидати й середнє популяції можуть погіршуватися.\n"
                     "Середнє обчислено лише серед допустимих особин; їх кількість може змінюватися.\n"
                     "За n=100 рівні мутації 1–8% задають E[L]=1–8 бітів, не фіксоване число змін.\n"
                     "Один seed не доводить переваги. Збіг ліній не розсувається штучно; останній префікс не оновлює популяцію.",
                     fontsize=9, va="top")
            name = f"UC-s000-{start}.png"
            fig.savefig(output / name, dpi=160)
            pdf.savefig(fig)
            plt.close(fig)
            figures.append({"path": name, "task": "UC-s000", "start": start, "seed": 76001,
                            "panels": ["feasible_candidate_cloud_and_record", "mean_feasible_population", "applied_mutation_probability"]})
    return figures


def _markdown(rows, provenance):
    lines = ["# Власна адаптація лише мутації: технічний пілот", "",
        "Статус: **16/16 перевірених запусків**, 80 000 нових пошукових оцінювань. "
        "Один технічний seed 76001; це перевірка реалізації, не статистична перевірка переваги.", "",
        "Популяція стала: 30 особин; схрещування стале: 0,9. Лише власний контролер мутації "
        "змінює її ймовірність після завершеного покоління. Правило не є відтворенням статті або адаптацією λ.", "",
        "## Що сталося з рекордом?", "",
        "У рядках `cloned` поліпшення означає вихід вище збереженого центра, крім SC-s000: "
        "це глобальний негативний контроль. У рядках `bank` це поліпшення початкового рекорду випадкового банку, "
        "а не доведений вихід із локального максимуму.", "",
        "| Задача | Початок | Метод | Початковий рекорд | Кінцевий рекорд | Приріст | Перше поліпшення, запит |",
        "| --- | --- | --- | ---: | ---: | ---: | --- |"]
    for row in rows:
        first = str(row["first_improvement_call"]) if row["first_improvement_call"] is not None else "немає до 5000"
        if row["endpoint"] == "GLOBAL_NEGATIVE_CONTROL":
            first = "глобальний контроль: немає"
        lines.append(f"| {row['task']} | {START_LABELS[row['start']]} | {METHOD_LABELS[row['method']]} | "
                     f"{row['initial_record']} | {row['final_record']} | {row['record_gain']:+d} | {first} |")
    lines += ["", "*Невиходи не вилучено. Для них обмежене число запитів дорівнює 5000; "
        "вихід саме на запиті 5000 має той самий час, але інший прапорець події. "
        "Відсутність поліпшення не встановлює глобальності: глобальні позначки походять лише із зовнішніх точних доказів.*", "",
        "## Як працював контролер і на що витрачалися оцінювання?", "",
        "«Сигнали успіху» — завершені покоління зі строгим зростанням допустимого рекорду. "
        "Подвоєння — спрацювання порога п'яти поколінь; на верхній межі воно може не змінювати ймовірність. "
        "Фактичні підвищення й зниження наведено окремо.", "",
        "| Задача | Початок | Метод | Повтори масок | Недопустимі | Сигнали успіху | Подвоєння: тригери | Фактичні ↑ / ↓ | Кінцева мутація, % |",
        "| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |"]
    for row in rows:
        lines.append(f"| {row['task']} | {START_LABELS[row['start']]} | {METHOD_LABELS[row['method']]} | "
                     f"{row['duplicate_calls']} | {row['infeasible_calls']} | {row['strict_record_improvement_generations']} | "
                     f"{row['doubling_triggers']} | {row['actual_probability_increases']} / {row['actual_probability_decreases']} | "
                     f"{100*row['final_mutation_probability']:.2f} |")
    lines += ["", "Кожний рядок має рівно 5000 нових оцінювань: 172 повні покоління по 29 дітей "
        "та останні 12 дітей. Дублікати й недопустимі маски теж витрачають запит. "
        "Останні 12 дітей можуть поліпшити рекорд, але не змінюють популяції або контролера.", "",
        "*Сигнал успіху на нижній межі може не зменшити мутацію. E[L]=np_m — математичне сподівання, "
        "не обіцянка саме такого числа змінених бітів. Початкова підготовка, 30 внутрішніх перевірок відомих оцінок "
        "на запуск та незалежні перевірні оцінювання обліковуються окремо від 80 000 нових пошукових запитів.*", "",
        "## Два наперед обрані рисунки UC-s000", "",
        "[Двосторінковий PDF](Прості_графіки_мутації.pdf)", "",
        "![UC-s000: копії центра](UC-s000-cloned.png)", "",
        "![UC-s000: випадковий банк](UC-s000-bank.png)", "",
        "На верхній панелі — усі допустимі кандидати та окремо рекорд; недопустимим не присвоєно нульової цінності. "
        "Середня панель показує лише фактичну популяцію, а не середнє всіх кандидатів. "
        "Нижня — ймовірність мутації, застосовану до відповідних запитів; оновлення після покоління діє на наступне.", "",
        "*Монотонність рекорду є властивістю збереження найкращого результату. "
        "Плоскі або збіжні лінії не приховано. Рисунки не мають довірчих смуг: одна технічна реалізація "
        "не оцінює міжзапускову невизначеність і не доводить кореляції, причинності або переваги.*", "",
        "## Межі результату", "",
        "Підтверджено лише технічну повноту й незалежну перевірку журналів у зареєстрованих умовах. "
        "Пілот не відокремлює користь feedback від ефекту іншого середнього рівня мутації; "
        "таке питання потребує окремого погодженого порівняння. Параметри не налаштовано за його результатами.", "",
        "*Немає нової перевірки статистичної переваги, бутстрепу, універсального прискорення або встановленої новизни. "
        "Гірші діти можуть входити до неелітних місць поколіннєвого ГА; старе твердження про відкидання всіх "
        "одно- й двобітних відхилень у `(μ+1)` ГА сюди не переноситься. Контролер не діагностує локальність чи глобальність.*", "",
        "## Походження", "",
        f"Протокол: `{c.PROTOCOL}`. Реєстраційний коміт: `{c.REGISTRATION_SHA}`. "
        f"SHA реалізації: `{provenance['implementation_sha']}`; CI run `{provenance['run_id']}`, "
        f"attempt `{provenance['run_attempt']}`.", "",
        "Числові описи й ідентичності журналів: `report_descriptives.json`; "
        "первинні технічні підсумки: `pilot_summary.json`; повні журнали: `journals/`. "
        "Нових пошукових запусків або точних розв'язань під час оформлення звіту не виконано.", ""]
    return "\n".join(lines)


def build_report(output):
    """Create two figures and a compact report after the authorized CI pilot."""
    provenance = c.authenticate(runtime=True)
    output = Path(output).resolve()
    c.require(output.is_dir(), "Pilot output directory is missing")
    for filename in ("RESULTS_UK.md", "report_descriptives.json", "Прості_графіки_мутації.pdf",
                     "UC-s000-cloned.png", "UC-s000-bank.png"):
        c.require(not (output / filename).exists(), "Reporting must not overwrite an existing result")
    pilot = c.read_json(output / "pilot_summary.json")
    c.require(all(pilot.get(name) == provenance.get(name) for name in
                  ("protocol_id", "implementation_sha", "run_id", "run_attempt", "source_manifest")),
              "Pilot and reporting checkout identities differ")
    logs, descriptions = _read_verified_logs(output, pilot)
    figures = _draw_uc(output, logs, descriptions)
    report = {"schema": "mutation-only-descriptive-report-v1", **provenance,
        "status": "COMPLETE_TECHNICAL_PILOT", "technical_seed": 76001,
        "runs": 16, "new_search_calls_in_pilot": 80000, "new_search_calls_in_reporting": 0,
        "new_exact_solver_runs": 0, "new_bootstrap_resamples": 0, "new_superiority_tests": 0,
        "inference": "DESCRIPTIVE_ONE_TECHNICAL_SEED_ONLY", "population_size": 30,
        "crossover_probability": 0.9, "results": descriptions, "figures": figures}
    c.write_json(output / "report_descriptives.json", report)
    (output / "RESULTS_UK.md").write_text(_markdown(descriptions, provenance), encoding="utf-8")
    print("Two UC-s000 illustrations and sixteen descriptive rows written; no new search or inference.")
    return report
