"""CI-only explanatory rendering from frozen records and explicit teaching models."""
from __future__ import annotations

import argparse
import csv
from fractions import Fraction
import hashlib
import itertools
import json
import math
import os
from pathlib import Path
import re
import time
import unittest

from ..main_study import contract

REPO_ROOT = Path(__file__).resolve().parents[3]
CASE_REL = "studies/knapsack_parameters/evidence/run-37637475385/cases/UC-s000/case.json"
NEIGHBORS_REL = "studies/knapsack_parameters/evidence/run-37637475385/cases/UC-s000/neighbors.csv"
ANALYSIS_REL = "studies/diversity_crossover/main_evidence/run-38396509102/analysis.json"
MAIN_RESULTS_REL = "studies/diversity_crossover/main_evidence/run-38396509102/RESULTS_UK.md"
DATA_REL = "studies/knapsack_parameters/inputs/source/00Uncorrelated/n00100/R01000/s000.kp"
INPUT_SHA256 = {
    CASE_REL: "0b6cebdd7dd2b7c16951b3d7d5af01a5ed33eb3536ffb6eb6a3d99a1e03d98d9",
    NEIGHBORS_REL: "d80aa6fdd2315b4619d29a867a2c9923634a8f67d67c5f2f27561abfca0c6ec7",
    ANALYSIS_REL: "24205ecd361021f80697e634b09a03dccb3a1bfd344406efdf191f4d6e84f661",
    MAIN_RESULTS_REL: "77b54ab3fbb225299b4ed138dd1db1f02713efecb80ac56a2f62d452504799bf",
    DATA_REL: "e05b24ea5b60e90ad38a2e4b46c87a73f197a5828b06b8bb298c9668ecfafed5",
}
SOURCE_SHA = "c856c9d6811eda51cb4c8b1786033e122249a52d"
SOURCE_DIGEST = "9359220a9ac47f4bf6df816817c01f526cd25ce4a8ebd9100f1502c51c816d3a"
EXPLANATORY_ID = "GA-SIMPLE-QUESTION-FIGURES-V1"
REGISTRATION_SHA = "e69425f"


def require(condition, message):
    if not condition:
        raise ValueError(message)


def mutation_probability(p, n=100, r=3):
    require(type(n) is int and type(r) is int and 0 <= r <= n and n > 0,
            "Invalid mutation dimensions")
    require(isinstance(p, (int, float)) and math.isfinite(p) and 0 <= p <= 1,
            "Invalid mutation probability")
    return p**r * (1-p)**(n-r)


def lambda_example():
    rows = [{"generation": 0, "lambda": 10.0, "event": "початок"}]
    value = 10.0
    for generation in range(1, 6):
        success = generation == 5
        value = max(1.0, value / 1.5) if success else min(40.0, value * 1.5**0.25)
        rows.append({"generation": generation, "lambda": value,
                     "event": "строге поліпшення" if success else "без поліпшення"})
    return rows


def toy_crossover_probabilities():
    weights, values, capacity = (2, 2, 1, 1), (2, 2, 2, 2), 2
    result = []
    for a, b in (("1000", "0100"), ("0010", "0001")):
        outcomes = {"".join(bits) for bits in itertools.product(
            *(tuple(sorted({left, right})) for left, right in zip(a, b)))}
        useful = sum(sum(w for w, bit in zip(weights, y) if bit == "1") <= capacity and
                     sum(v for v, bit in zip(values, y) if bit == "1") > 2 for y in outcomes)
        result.append(Fraction(useful, len(outcomes)))
    return result


def load_inputs(root=REPO_ROOT):
    root = Path(root)
    for relative, digest in INPUT_SHA256.items():
        require(hashlib.sha256((root / relative).read_bytes()).hexdigest() == digest,
                "Input checksum mismatch: " + relative)
    case = json.loads((root / CASE_REL).read_text(encoding="utf-8"))
    analysis = json.loads((root / ANALYSIS_REL).read_text(encoding="utf-8"))
    require(case["instance_id"] == "UC-s000" and case["n"] == 100 and
            case["status"] == "ADMITTED_STRICT_LOCAL" and case["certificate"]["strict"] and
            not case["certificate"]["plateau"] and case["certificate"]["higher_feasible"] == 0 and
            case["certificate"]["equal_feasible"] == 0 and
            case["provenance"]["run_id"] == 37637475385, "Wrong locality case")
    tokens = [int(token) for token in (root / DATA_REL).read_text().split()]
    n, capacity = tokens[:2]
    require(n == 100 and capacity == case["capacity"] and len(tokens) == 2 + 2*n,
            "Wrong original data dimensions")
    values, weights = tokens[2::2], tokens[3::2]

    def evaluate_mask(mask):
        require(isinstance(mask, str) and len(mask) == n and not set(mask)-{"0", "1"},
                "Invalid witness mask")
        return (sum(w for w, bit in zip(weights, mask) if bit == "1"),
                sum(v for v, bit in zip(values, mask) if bit == "1"))

    center = case["certificate"]["center"]
    require(evaluate_mask(center["mask"]) == (center["weight"], center["profit"]) and
            center["weight"] <= capacity and center["profit"] == 46510, "Invalid center")
    witness = case["exact"]["capacity"]
    witness_weight, witness_profit = evaluate_mask(witness["witness_mask"])
    distance = sum(a != b for a, b in zip(center["mask"], witness["witness_mask"]))
    require(witness_weight == witness["witness_weight"] <= capacity and
            witness_profit == witness["witness_profit"] == case["exact"]["confirmed_optimum"] ==
            case["exact"]["profit"]["optimum_profit"] == 46537 and
            case["exact"]["witness_verified"] is True and distance == 3, "Invalid optimal witness")
    with (root / NEIGHBORS_REL).open(encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))
    seen, feasible_gains = set(), {1: [], 2: []}
    for index, row in enumerate(rows, 1):
        d = int(row["distance"])
        require(d in (1, 2) and int(row["neighbor_index"]) == index, "Wrong neighbor order")
        flips = (int(row["flip_i"]),) if d == 1 else (int(row["flip_i"]), int(row["flip_j"]))
        require(all(0 <= bit < n for bit in flips) and len(set(flips)) == d and
                tuple(sorted(flips)) == flips and flips not in seen, "Invalid neighbor indices")
        seen.add(flips)
        mask = list(center["mask"])
        for bit in flips:
            mask[bit] = "0" if mask[bit] == "1" else "1"
        weight, profit = evaluate_mask("".join(mask))
        feasible = weight <= capacity
        require((weight, profit) == (int(row["weight"]), int(row["profit"])) and
                row["feasible"] == str(int(feasible)), "Invalid recorded neighbor evaluation")
        require(row["reason"] == ("FEASIBLE" if feasible else "CAPACITY_EXCEEDED") and
                row["comparison"] == ("WORSE" if feasible else "INVALID"),
                "Invalid neighbor classification")
        if feasible:
            require(profit < center["profit"], "Certificate has a non-worse neighbor")
            feasible_gains[d].append(profit-center["profit"])
    expected = {(i,) for i in range(n)} | set(itertools.combinations(range(n), 2))
    require(seen == expected and len(rows) == 5050 and all(feasible_gains.values()),
            "Incomplete neighborhood certificate")
    require(analysis["status"] == "COMPLETE_MAIN" and analysis["complete_runs"] == 6304 and
            analysis["completed_search_calls"] == 31520000 and
            analysis["implementation_sha"] == SOURCE_SHA and
            analysis["adaptive_parameters"] is False and not analysis["missing_identities"] and
            analysis["incomplete_runs"] == [], "Wrong or incomplete historical analysis")
    groups = analysis["descriptive_groups"]
    outcomes = []
    for task in ("Jump4", "Jump8"):
        for method in ("baseline", "directed"):
            matched = [g for g in groups if g["task"] == task and g["method"] == method and
                       g["start"] == "cloned" and g["series"] == "main"]
            require(len(matched) == 1 and matched[0]["runs"] == 30, "Wrong model group")
            group = matched[0]
            require(0 <= group["escapes"] <= 30 and group["nonexits"] == 30-group["escapes"],
                    "Wrong model exit counts")
            outcomes.append({"task": task, "method": method,
                             "successes": group["escapes"], "runs": group["runs"]})
    for method in ("baseline", "directed"):
        matched = [g for g in groups if g["task"].startswith(("UC-", "WC-", "SC-")) and
                   g["method"] == method and g["start"] == "cloned" and g["series"] == "main"]
        require(len(matched) == 14 and len({g["task"] for g in matched}) == 14 and
                all(g["runs"] == 30 and g["escapes"] == 0 and g["nonexits"] == 30
                    for g in matched), "Wrong local knapsack groups")
        outcomes.append({"task": "KPLIB-local", "method": method,
                         "successes": sum(g["escapes"] for g in matched),
                         "runs": sum(g["runs"] for g in matched)})
    require([(g["successes"], g["runs"]) for g in outcomes] ==
            [(8, 30), (30, 30), (0, 30), (0, 30), (0, 420), (0, 420)],
            "Unexpected frozen historical counts")
    return {"locality": {"max_gain_by_distance": {str(d): max(gains) for d, gains in feasible_gains.items()},
                         "witness_gain": witness_profit-center["profit"], "witness_distance": distance,
                         "center_profit": center["profit"], "optimum_profit": witness_profit,
                         "n": n, "neighbors": len(rows), "feasible_neighbors": sum(map(len, feasible_gains.values()))},
            "outcomes": outcomes}


def preflight(output):
    identity = contract.authenticate(require_runtime=False)
    message = os.environ.get("COMMIT_MESSAGE", "")
    require(re.findall(r"\[([a-z-]+):([^\]]+)\]", message) == [("diversity-simple", "render")],
            "Wrong or mixed explanatory marker")
    require(contract.source_manifest()["sha256"] == SOURCE_DIGEST, "Frozen scientific files changed")
    for retry in range(11):
        try:
            usage = contract.runner_usage(include_current=True)
            break
        except ValueError as exc:
            if str(exc) != "Another branch workflow is still active" or retry == 10:
                raise
            time.sleep(2)
    own_used = sum(job["minutes"] for job in usage["prior_jobs"] if job["name"] == "simple_figures")
    require(own_used + 6 <= 12 and usage["used_runner_minutes"] + 6 <= 1200,
            "Insufficient cumulative figure or study budget")
    result = dict(usage, explanatory_id=EXPLANATORY_ID, own_used_runner_minutes=own_used,
                  own_reserved_runner_minutes=6, own_ceiling=12, provenance=identity)
    contract.write_json(Path(output) / "budget-preflight.json", result)
    print("Explanatory-only authorization; no search. Prior total minutes:", usage["used_runner_minutes"])


def tests(output):
    contract.ci_only()
    suite = unittest.defaultTestLoader.discover(str(Path(__file__).parent),
                                                pattern="test_figures.py", top_level_dir=str(REPO_ROOT))
    with (output / "tests.txt").open("w", encoding="utf-8") as stream:
        result = unittest.TextTestRunner(stream=stream, verbosity=2).run(suite)
    receipt = {"tests_passed": result.wasSuccessful(), "tests_run": result.testsRun,
               "failures": len(result.failures), "errors": len(result.errors), "skipped": len(result.skipped)}
    contract.write_json(output / "tests-receipt.json", receipt)
    require(result.wasSuccessful() and result.testsRun > 0 and not result.skipped,
            (output / "tests.txt").read_text(encoding="utf-8"))
    return receipt


def render(output):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.backends.backend_pdf import PdfPages
    from matplotlib.ticker import PercentFormatter

    identity = contract.authenticate()
    require(contract.source_manifest()["sha256"] == SOURCE_DIGEST, "Frozen source changed")
    tests_receipt = tests(output)
    data = load_inputs()
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 13, "axes.labelsize": 14,
                         "axes.titlesize": 16, "pdf.fonttype": 42, "ps.fonttype": 42,
                         "axes.spines.top": False, "axes.spines.right": False,
                         "figure.facecolor": "white", "axes.facecolor": "white"})
    passports = []

    def figure(question, category, answer, limitation):
        fig, ax = plt.subplots(figsize=(12, 7.3))
        fig.subplots_adjust(left=.13, right=.95, bottom=.29, top=.77)
        fig.text(.07, .94, question, fontsize=21, weight="bold", va="top")
        fig.text(.07, .865, category, fontsize=11, color=".35")
        fig.text(.07, .16, "Відповідь: " + answer, fontsize=14, weight="bold", va="top")
        fig.text(.07, .095, limitation, fontsize=11, va="top", color=".3")
        ax.grid(axis="y", color=".88", linewidth=.6)
        ax.set_axisbelow(True)
        return fig, ax

    def save(fig, name, question, category, values, answer, limitation, pdf):
        fig.savefig(output / (name + ".png"), dpi=160)
        fig.savefig(output / (name + ".pdf"))
        pdf.savefig(fig)
        plt.close(fig)
        passports.append({"id": name, "question": question, "evidence_type": category,
                          "values": values, "answer": answer, "limitation": limitation})

    with PdfPages(output / "Прості_графіки_ГА.pdf",
                  metadata={"Title": "Генетичний алгоритм: прості запитання й відповіді",
                            "Author": "", "CreationDate": None, "ModDate": None}) as pdf:
        question = "Чому цей максимум локальний, але не глобальний?"
        category = "ФАКТИЧНИЙ СЕРТИФІКАТ · UC-s000 · 100 предметів"
        answer = "Зміна 1–2 бітів не покращує набір; відомий 3-бітний перехід дає +27."
        limitation = ("Для 1–2 бітів перевірено всіх 5050 сусідів. Для 3 бітів показано оптимальний свідок.\n"
                      "Це сертифікат задачі, а не результат виходу генетичного алгоритму.")
        fig, ax = figure(question, category, answer, limitation)
        locality = data["locality"]
        gains = [locality["max_gain_by_distance"]["1"], locality["max_gain_by_distance"]["2"],
                 locality["witness_gain"]]
        bars = ax.bar([0, 1, 2], gains, color=[".7", ".45", "white"], edgecolor="black", width=.55)
        bars[2].set_hatch("///")
        ax.axhline(0, color="black", linewidth=1.2)
        for bar, value in zip(bars, gains):
            ax.annotate(f"{value:+d}", (bar.get_x()+bar.get_width()/2, value),
                        xytext=(0, 7 if value >= 0 else -7), textcoords="offset points",
                        ha="center", va="bottom" if value >= 0 else "top", weight="bold", fontsize=17)
        ax.set_xticks([0, 1, 2], ["1 біт\nнайкращий допустимий", "2 біти\nнайкращий допустимий",
                                 "3 біти\nоптимальний свідок"])
        ax.set_ylabel("Зміна цінності відносно центра")
        ax.set_ylim(min(gains)*1.32, max(gains)*1.6)
        save(fig, "01_local_maximum", question, category, locality, answer, limitation, pdf)

        question = "Яка мутація частіше створює конкретний кращий набір?"
        category = "ТОЧНА ФОРМУЛА · один мутант із незмінного центра · не експеримент"
        answer = "Для однієї заданої 3-бітної цілі найбільший шанс — за мутації 3%."
        limitation = ("P = p³(1−p)⁹⁷. Вісь показує розрахункове середнє на 1 млн спроб, а не виконані запуски.\n"
                      "Одна задана ціль, не всі поліпшення. Пік 3% не означає найкращий параметр усього ГА.")
        fig, ax = figure(question, category, answer, limitation)
        xs = [i/10000 for i in range(1001)]
        ys = [1_000_000*mutation_probability(p) for p in xs]
        ax.plot([100*x for x in xs], ys, color="black", linewidth=2)
        for p, marker, label in ((.01, "o", "1%"), (.03, "s", "3% — максимум для цієї цілі")):
            y = 1_000_000*mutation_probability(p)
            ax.plot(100*p, y, marker, color="black", markersize=7)
            ax.annotate(label, (100*p, y), xytext=(12, 10), textcoords="offset points", fontsize=12)
        ax.set_xlim(0, 10)
        ax.set_ylim(0, max(ys)*1.25)
        ax.set_xlabel("Імовірність зміни одного біта, %")
        ax.set_ylabel("Очікувані потрапляння на 1 млн спроб")
        save(fig, "02_mutation_probability", question, category,
             {"n": 100, "target_distance": 3, "p": xs, "probability": [y/1_000_000 for y in ys]},
             answer, limitation, pdf)

        question = "Як λ реагує на невдачі та успіх?"
        category = "НАВЧАЛЬНИЙ ПРИКЛАД · відоме правило λ · не траєкторія запуску"
        answer = "Чотири невдачі збільшують λ з 10 до 15; один успіх повертає до 10."
        limitation = ("F = 1,5; без поліпшення: λ × F^(1/4); строге поліпшення: λ ÷ F. Межі [1;40] не активні.\n"
                      "Це не адаптація виконаної серії різноманітності й не доказ кращої якості.")
        fig, ax = figure(question, category, answer, limitation)
        schedule = lambda_example()
        ax.plot([r["generation"] for r in schedule], [r["lambda"] for r in schedule],
                "-o", color="black", linewidth=2, markersize=7)
        for row in schedule:
            ax.annotate(f"{row['lambda']:.2f}".replace(".", ","), (row["generation"], row["lambda"]),
                        xytext=(0, 10), textcoords="offset points", ha="center")
        ax.set_xticks(range(6), ["Початок", "Невдача 1", "Невдача 2", "Невдача 3", "Невдача 4", "Успіх"])
        ax.set_ylabel("Значення λ")
        ax.set_xlabel("Завершене покоління")
        ax.set_ylim(0, 18)
        save(fig, "03_lambda_response", question, category, schedule, answer, limitation, pdf)

        question = "Чи допоміг спрямований добір у всіх задачах?"
        category = "ФАКТИЧНІ ЗАПУСКИ · однакові 5000 нових оцінювань · параметри сталі"
        answer = "На Jump4 — більше виходів. На Jump8 та локальних KPLIB виходів не було."
        limitation = ("Jump: вихід до глобального оптимуму; KPLIB: будь-яке допустиме поліпшення центра.\n"
                      "KPLIB: 14 центрів × 30 повторень (13 строгих, 1 плато). Нуль не доводить неможливості виходу.")
        fig, ax = figure(question, category, answer, limitation)
        for method, offset, fill, label in (("baseline", -.18, ".75", "Базовий"),
                                            ("directed", .18, ".2", "Спрямований добір")):
            rows = [next(r for r in data["outcomes"] if r["task"] == task and r["method"] == method)
                    for task in ("Jump4", "Jump8", "KPLIB-local")]
            positions = [i+offset for i in range(3)]
            rates = [r["successes"]/r["runs"] for r in rows]
            ax.bar(positions, rates, width=.32, color=fill, edgecolor="black", label=label)
            for x, rate, row in zip(positions, rates, rows):
                ax.annotate(f"{row['successes']}/{row['runs']}", (x, rate), xytext=(0, 6),
                            textcoords="offset points", ha="center", weight="bold", fontsize=13)
        ax.set_xticks(range(3), ["Jump4", "Jump8", "Локальні KPLIB"])
        ax.set_ylabel("Частка запусків із виходом")
        ax.yaxis.set_major_formatter(PercentFormatter(1))
        ax.set_ylim(0, 1.2)
        ax.set_yticks([0, .25, .5, .75, 1])
        ax.legend(frameon=False, loc="upper right")
        save(fig, "04_observed_exits", question, category, data["outcomes"], answer, limitation, pdf)

        question = "Чи достатньо однакової відстані між батьками?"
        category = "ПОВНИЙ НАВЧАЛЬНИЙ ПРИКЛАД · рівномірне схрещування · до мутації"
        answer = "Ні. За однакової відстані 2 шанс допустимого поліпшення — 0% або 25%."
        limitation = ("Місткість 2; ваги (2,2,1,1); цінності (2,2,2,2). Усі батьки допустимі з цінністю 2.\n"
                      "Кожний із чотирьох нащадків має шанс 1/4. Це не результат експериментальної серії.")
        fig, ax = figure(question, category, answer, limitation)
        ax.set_xlim(-.1, 4.7)
        ax.set_ylim(-.65, 1.65)
        ax.set_axis_off()
        labels = [("1000 × 0100", ["0000", "1000", "0100", "1100"], "0%", None),
                  ("0010 × 0001", ["0000", "0010", "0001", "0011"], "25%", "0011")]
        for y, (parents, children, probability, good) in zip((1, 0), labels):
            ax.text(-.05, y+.32, parents + "  →", fontsize=15, weight="bold")
            for x, child in enumerate(children):
                description = ("кращий допустимий" if child == good else
                               "недопустимий" if child == "1100" else "не кращий")
                ax.text(x+.3, y, child, fontsize=19, fontfamily="DejaVu Sans Mono", ha="center",
                        bbox={"boxstyle": "round,pad=.35", "facecolor": ".85" if child == good else "white",
                              "edgecolor": "black", "linewidth": 2 if child == good else 1})
                ax.text(x+.3, y-.31, description, fontsize=10, ha="center")
            ax.text(4.15, y, probability, fontsize=25, weight="bold", ha="center")
        save(fig, "05_crossover_example", question, category,
             {"weights": [2, 2, 1, 1], "values": [2, 2, 2, 2], "capacity": 2,
              "probabilities": [str(x) for x in toy_crossover_probabilities()]}, answer, limitation, pdf)

    contract.write_json(output / "figure-passports.json", {"explanatory_id": EXPLANATORY_ID,
        "post_result_explanatory_only": True, "new_search_calls": 0, "new_statistical_tests": 0,
        "new_three_bit_neighborhood_enumeration": False, "input_sha256": INPUT_SHA256,
        "source_sha": SOURCE_SHA, "provenance": identity, "tests": tests_receipt, "figures": passports})
    contract.write_json(output / "source-files.json", {"files": [
        {"path": p.relative_to(REPO_ROOT).as_posix(), **contract.file_identity(p)}
        for p in sorted(Path(__file__).parent.glob("*")) if p.is_file()]})
    index = ["# Прості графіки: запитання й відповіді", "",
             "Відкрийте **Прості_графіки_ГА.pdf**: п'ять сторінок, по одному запитанню на сторінку.", ""]
    for item in passports:
        index.extend([f"## {item['question']}", "", f"![{item['question']}]({item['id']}.png)", "",
                      item["evidence_type"], "", "**Відповідь:** " + item["answer"], "",
                      "*" + item["limitation"].replace("\n", " ") + "*", ""])
    index.extend(["## Джерела та межі", "",
        "1. Збережені сертифікати UC-s000: run 37637475385; основні результати: run 38396509102.",
        "2. Hevia Fajardo–Sudholt, 2022, алгоритм 1: https://mhevia.com/assets/pdf/journal_oplclga.pdf",
        "3. Модель рівномірного схрещування й побітової мутації: https://doi.org/10.1007/s00453-025-01323-x",
        "", "Нових запусків ГА, числової реплікації статей, бутстрепу або нових перевірок переваги немає.",
        "Підсумкова серія має сталі параметри. Навчальна λ-ілюстрація не є її адаптивною версією.",
        "Паспорти містять точні дані кожного рисунка й SHA256 усіх використаних входів.", ""])
    (output / "ПРОЧИТАЙ_МЕНЕ.md").write_text("\n".join(index), encoding="utf-8")
    contract.write_file_manifest(output)
    print("Five explanatory figures rendered. New search calls: 0.")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=("preflight", "render"))
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    contract.ci_only()
    args.output.mkdir(parents=True, exist_ok=True)
    if args.phase == "preflight":
        preflight(args.output)
    else:
        require((args.output / "budget-preflight.json").is_file(), "Missing preflight receipt")
        render(args.output)


if __name__ == "__main__":
    main()
