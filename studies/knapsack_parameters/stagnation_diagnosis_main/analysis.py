"""Registered descriptive main-series readout, without additional hypotheses."""
from __future__ import annotations

from collections import Counter
from copy import deepcopy
from pathlib import Path
import os

from ..stagnation_diagnosis import analysis as original
from . import contract as c

STATES, STATE_LABELS = original.STATES, original.STATE_LABELS


def expected_identities():
    return {(f"{label}-s{index:03d}", seed) for label in ("UC", "WC", "SC")
            for index in range(10) for seed in range(93001, 93031)}


def summarize_runs(rows, *, expected=None):
    rows = list(rows)
    legacy = deepcopy(rows)
    provenance = None
    for actual, copy in zip(rows, legacy):
        c.require(actual.get("protocol_id") == c.PROTOCOL_ID and actual.get("scientific_protocol_id") == c.SCIENTIFIC_ID
                  and actual.get("phase") == "main" and actual.get("technical_fingerprint") == c.TECHNICAL_FINGERPRINT
                  and actual.get("bank_manifest_sha256") == c.BANK_SHA
                  and all(actual.get(key) is not None for key in c.PROVENANCE_KEYS),
                  "Foreign main scientific identity")
        current = {key: actual.get(key) for key in c.PROVENANCE_KEYS + ("bank_manifest_sha256",)}
        if provenance is None:
            provenance = current
        c.require(current == provenance, "Mixed main provenance")
        if actual.get("status") == "COMPLETE" and actual.get("verified") is True:
            replay = actual.get("aggregate_independent_verification", {})
            c.require(replay.get("search", {}).get("status") == "PASS_REPLAY" and
                      replay.get("diagnosis", {}).get("status") == "PASS_DIAGNOSIS",
                      "Main observation lacks independent transported replay")
        # The unchanged validation library has its own immutable scientific ID.
        # Only a detached adapter copy receives that ID; no evidence is rewritten.
        copy["protocol_id"] = c.SCIENTIFIC_ID
    result = original.summarize_runs(legacy, expected_identities=expected_identities() if expected is None else expected)
    result.update(protocol_id=c.PROTOCOL_ID, scientific_protocol_id=c.SCIENTIFIC_ID,
                  phase="main", provenance=provenance,
                  inference_status="REGISTERED_DESCRIPTIVE_COMPLETE" if result["completeness"]["status"] == "COMPLETE"
                  else "PARTIAL_DESCRIPTIVE_ONLY")
    complete = [row for row in rows if row.get("status") == "COMPLETE" and row.get("verified") is True]
    result["checkpoint_counts"] = []
    for index, q in enumerate((0, 1000, 2500, 5000)):
        counts, stagnant = Counter({state: 0 for state in STATES}), Counter({state: 0 for state in STATES})
        for row in complete:
            item = row["checkpoints"][index]
            counts[item["state"]] += 1
            if item["stagnant"]:
                stagnant[item["state"]] += 1
        result["checkpoint_counts"].append({"q": q, "state_counts": dict(counts),
                                            "stagnant_state_counts": dict(stagnant)})
    accounting = result["evaluation_accounting"]
    accounting["initial_are_known_frozen_evaluations_not_new_search"] = True
    accounting["verification_costs"] = {
        "worker_bank_revalidation": sum(row.get("accounting", {}).get("bank_revalidation_evaluations", 0) for row in complete),
        "worker_search_replay": sum(row.get("accounting", {}).get("search_replay_evaluations", 0) for row in complete),
        "worker_verification_total": sum(row.get("accounting", {}).get("worker_verification_total_evaluations", 0) for row in complete),
        "aggregate_verification_total": sum(row.get("aggregate_independent_verification", {}).get("aggregate_verification_total_evaluations", 0) for row in complete),
    }
    result["no_additional_inferential_tests"] = True
    return result


def write_report(output, rows, summary):
    c.require(os.environ.get("GITHUB_ACTIONS") == "true", "Scientific reports are CI-only")
    output = Path(output).resolve()
    c.require(not output.is_relative_to(c.ROOT), "Report must be outside checkout")
    output.mkdir(parents=True, exist_ok=True)
    rows = list(rows)
    figures = original._make_figures(output, rows, summary)
    primary, complete = summary["primary"], summary["completeness"]
    count, total = primary["absolute_numerator"], primary["absolute_denominator"]
    fraction = original._percent(primary["value"])
    lines = ["# Чи означає застій генетичного алгоритму локальний максимум?", "",
        "## Питання та гіпотеза", "",
        "Перевіряється, чи збережений найкращий набір справді є локальним максимумом, коли пошук тривалий час не дає нового рекорду. Гіпотеза передбачає наявність випадків застою, для яких існує кращий допустимий одно- або двобітний сусід.", "",
        "## Метод дослідження", "",
        "Використано 30 задач рюкзака зі 100 предметами та по 30 незалежно ініціалізованих повторень. Досліджується одна стала конфігурація звичайного поколіннєвого генетичного алгоритму: популяція 30, мутація біта 1%, рівномірне схрещування з імовірністю 90%, два турніри по двоє та одна еліта.", "",
        "Початкова популяція містить порожню маску та 29 випадкових. Її 30 відомих оцінок обліковуються окремо від 5000 нових пошукових оцінювань. Дублікати та недопустимі набори враховуються; виправлення наборів, рестарти й пошукове кешування не застосовуються.", "",
        "Тривалість застою дорівнює різниці між поточним номером нового оцінювання та моментом останнього строгого рекорду. Якщо початковий рекорд не поліпшився, його момент дорівнює нулю. Порогом застою є 1000 оцінювань. Це операційне визначення, а не критерій оптимальності [1].", "",
        "На точках 0, 1000, 2500 і 5000 збережено маску-рекорд, завершену популяцію та оцінених нащадків незавершеного покоління. Після пошуку незалежно перевірено всі 5050 одно- й двобітних сусідів кожної унікальної маски-рекорду. Глобальність установлювалася зіставленням з уже підтвердженим точним оптимумом. Діагностика не керувала пошуком.", "",
        "Останні 12 нащадків після 172 повних поколінь ураховано в рекорді, але незавершену заміну популяції не застосовано. Різноманітність виміряно часткою унікальних масок і середньою попарною відстанню Геммінга, включно з парами однакових масок.", "",
        "## Результати", "",
        f"Незалежно перевірено {complete['verified_complete']} із {complete['expected']} запланованих запусків. Новий пошук містить {summary['evaluation_accounting']['new_search']} оцінювань; відомі початкові оцінки обліковано окремо.", ""]
    if complete["status"] != "COMPLETE":
        lines += ["Серія неповна. Відсутні чи неперевірені випадки не замінено нулями або успішнішими повтореннями. Наведені частки не є остаточними.", ""]
    lines += ["Таблиця 1. Незалежно перевірений стан збереженого рекорду наприкінці пошуку", "",
              "| Стан | Усі перевірені запуски | Із застоєм |", "|---|---:|---:|"]
    for state in STATES:
        lines.append(f"| {STATE_LABELS[state]} | {summary['state_counts'][state]} | {summary['stagnant_state_counts'][state]} |")
    lines += ["", f"У {count} із {total} випадків застою збережена маска мала кращого допустимого сусіда. Сімейно-зважена частка становить {fraction}.", "",
        "Спочатку усереднено повторення задачі, потім задачі сімейства. Десять сімейств отримали рівну вагу. Підсумок є відношенням зважених кількостей, не середнім умовних часток. Абсолютні кількості наведено поряд із часткою.", "",
        "Таблиця 2. Випадки застою та доступного покращення за сімействами", "",
        "| Сімейство | Запуски | Застій із кращим сусідом | Усі випадки застою | Частка серед застою |",
        "|---|---:|---:|---:|---:|"]
    for family in summary["families"]:
        lines.append(f"| {family['family']} | {family['runs']} | {family['numerator']} | {family['denominator']} | {original._percent(family['conditional_fraction'])} |")
    for index, (path, caption) in enumerate(figures, 1):
        lines += ["", f"![{caption}]({path})", "", f"Рисунок {index}. {caption}"]
    lines += ["", "## Обмеження", "",
        "Поріг 1000 оцінювань обрано до основних запусків; інші пороги не підбиралися. Висновки стосуються однієї конфігурації, визначених початків, 30 задач і бюджету 5000 нових оцінювань. Сімейна структура врахована під час усереднення, але не доводить незалежності всіх властивостей задач.", "",
        "Локальність визначається щодо заданого одно- й двобітного сусідства [2]. Нестрогий локальний максимум із рівноцінним сусідом не є доказом замкненості всього плато. Сертифікат маски не поширюється на всю популяцію. Плоска траєкторія сама по собі не підтверджує локальності чи глобальності.", "",
        "## Висновок", ""]
    if complete["status"] != "COMPLETE":
        lines.append("Остаточна відповідь потребує завершення й перевірки всіх передбачених запусків.")
    elif not total:
        lines.append("За визначеним порогом випадків застою не виявлено. Основна умовна частка невизначена; це не нуль і не доказ еквівалентності застою та оптимальності.")
    elif count:
        lines.append(f"Тривала відсутність нового рекорду не завжди відповідала локальній оптимальності. У {count} із {total} випадків застою збережений набір усе ще мав допустиме одно- або двобітне покращення. Частка за зареєстрованим сімейним зважуванням становить {fraction}. Отже, для розрізнення застою та локального максимуму потрібна перевірка сусідства, а не лише спостереження за рекордом.")
    else:
        lines.append("У цій серії серед випадків застою не виявлено збережених масок із кращим одно- або двобітним сусідом. Це не доводить, що застій завжди означає локальну оптимальність в інших задачах, конфігураціях чи бюджетах.")
    lines += ["", "Результат є описовою емпіричною оцінкою. Відмінність між застоєм і локальною оптимальністю не заявляється як новизна. Нових перевірок переваги, p-значень, бутстрепу або добору сприятливих випадків не проводилося.", "",
        "## Джерела", "",
        "1. Rajabi A., Witt C. Stagnation Detection in Highly Multimodal Fitness Landscapes. Algorithmica, 2024. https://doi.org/10.1007/s00453-024-01249-w", "",
        "2. Verel S., Ochoa G., Tomassini M. Local Optima Networks of NK Landscapes with Neutrality. IEEE Transactions on Evolutionary Computation, 2011. https://doi.org/10.1109/TEVC.2010.2046175", "",
        "## Додаток. Походження результатів", "",
        f"Запуск: https://github.com/{c.old.REPOSITORY}/actions/runs/{summary.get('provenance', {}).get('run_id', 'unknown')}", "",
        "Повні журнали, початки, сертифікати, хеші транспортних архівів і внутрішніх файлів збережено окремо. Попередні технічні проби до основної частоти не включено. Історичне ядро та наявний диплом не змінено.", ""]
    (output / "report.md").write_text("\n".join(lines), encoding="utf-8")
    c.write_json(output / "summary.json", summary)
    return {"report": "report.md", "figures": [path for path, _ in figures]}
