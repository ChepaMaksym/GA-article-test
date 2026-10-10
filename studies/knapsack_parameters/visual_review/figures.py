"""Question-led, CI-only figures from immutable historical observations.

This module renders supplied observations.  It runs no search, solver,
bootstrap, hypothesis test, or interpolation of missing event times.
"""
from __future__ import annotations

import os
from pathlib import Path
import textwrap


WIDTH_INCHES = 6.8
MIN_FONT_POINTS = 11
CONTRAST_LABELS = {
    "mutation_3_over_1": "Мутація\n3/n проти 1/n",
    "crossover_09_over_0": "Схрещування\n0,9 проти 0",
    "population_50_over_10": "Популяція\n50 проти 10",
    "mutation_crossover_interaction": "Взаємодія мутації\nзі схрещуванням",
}
MUTATION_STYLES = {
    "m0p5": {"linestyle": ":", "marker": "o", "label": "Мутація 0,5/n"},
    "m1": {"linestyle": "--", "marker": "s", "label": "Мутація 1/n"},
    "m3": {"linestyle": "-.", "marker": "^", "label": "Мутація 3/n"},
}


def _number(value: float, decimals: int = 4, signed: bool = False) -> str:
    specification = ("+" if signed else "") + "." + str(decimals) + "f"
    return format(value, specification).replace(".", ",")


def _wrapped(text: str, width: int = 80) -> str:
    return "\n".join(textwrap.wrap(text, width=width, break_long_words=False,
                                   break_on_hyphens=False))


def _figure(plt, *, question: str, answer: str, limitation: str,
            rows: int, height: float, left: float = 0.16,
            bottom: float = 0.20, top: float = 0.86):
    figure, axes = plt.subplots(rows, 1, figsize=(WIDTH_INCHES, height), squeeze=False)
    figure.subplots_adjust(left=left, right=0.97, bottom=bottom, top=top,
                           hspace=0.63 if rows > 1 else 0.2)
    figure.suptitle(_wrapped(question, 66), x=0.5, y=0.985,
                   fontsize=12, fontweight="bold", va="top")
    footer = (_wrapped("Відповідь: " + answer) + "\n" +
              _wrapped("Межі тлумачення: " + limitation))
    figure.text(0.045, 0.025, footer, ha="left", va="bottom", fontsize=11,
                linespacing=1.25)
    return figure, [row[0] for row in axes]


def _save(plt, figure, output: Path, slug: str, question: str, answer: str,
          limitation: str) -> dict:
    directory = output / "figures"
    directory.mkdir(parents=True, exist_ok=True)
    png, pdf = directory / (slug + ".png"), directory / (slug + ".pdf")
    # The canvas has the final A4 insertion width; text is not rescued by
    # shrinking an oversized multi-panel figure after generation.
    figure.savefig(png, dpi=250, facecolor="white")
    figure.savefig(pdf, facecolor="white", metadata={"CreationDate": None,
                                                   "ModDate": None})
    plt.close(figure)
    return {"slug": slug, "question": question, "answer": answer,
            "limitation": limitation,
            "png": png.relative_to(output).as_posix(),
            "pdf": pdf.relative_to(output).as_posix()}


def _certificate(plt, data: dict, output: Path) -> dict:
    question = "Чому UC-s000 є локальним, але не глобальним максимумом?"
    answer = ("Кращих допустимих одно- й двобітних сусідів немає. "
              "Окремий трьохбітний свідок підвищує цінність на 27.")
    limitation = ("Це проєкція повного сертифіката 5050 сусідів, не весь "
                  "ландшафт пошуку. Свідок не входить до цих 5050 точок.")
    figure, axes = _figure(plt, question=question, answer=answer,
                           limitation=limitation, rows=2, height=7.9,
                           bottom=0.19, top=0.88)
    case = data["case"]
    center = case["certificate"]["center"]
    witness = case["exact"]["witness_verification"]["capacity"]
    capacity = case["capacity"]
    feasible = [row for row in data["neighbors"] if row["feasible"]]
    infeasible = [row for row in data["neighbors"] if not row["feasible"]]
    for ax in axes:
        ax.scatter([row["weight"] - capacity for row in feasible],
                   [row["profit"] - center["profit"] for row in feasible],
                   s=10, marker="o", facecolors="none", edgecolors="black",
                   linewidths=0.45, alpha=0.55, label="Допустимі сусіди")
        ax.scatter([row["weight"] - capacity for row in infeasible],
                   [row["profit"] - center["profit"] for row in infeasible],
                   s=10, marker="x", color="0.60", linewidths=0.5,
                   alpha=0.5, label="Недопустимі сусіди")
        ax.axvline(0, color="black", linestyle="--", linewidth=1)
        ax.axhline(0, color="black", linestyle=":", linewidth=1)
        ax.scatter(center["weight"] - capacity, 0, marker="D", s=55,
                   color="black", zorder=5, label="Центр")
        ax.scatter(witness["weight"] - capacity,
                   witness["profit"] - center["profit"], marker="*", s=150,
                   color="black", zorder=6, label="Трьохбітний свідок")
        ax.set_xlabel("Вага набору мінус місткість")
        ax.set_ylabel("Цінність мінус\nцінність центра")
    axes[0].set_title("Повний огляд усіх 5050 сусідів", fontsize=11)
    axes[0].legend(loc="upper left", fontsize=11, framealpha=0.95,
                   handletextpad=0.5, borderpad=0.4)
    axes[1].set_title("Наближення біля центра: масштаб змінено явно", fontsize=11)
    axes[1].set_xlim(-200, 200)
    axes[1].set_ylim(-200, 150)
    axes[1].annotate("Центр (−58; 0)", xy=(center["weight"] - capacity, 0),
                     xytext=(-185, -95), fontsize=11,
                     arrowprops={"arrowstyle": "-", "color": "black"})
    axes[1].annotate("Свідок (−26; +27)\nвідстань — три біти",
                     xy=(witness["weight"] - capacity,
                         witness["profit"] - center["profit"]),
                     xytext=(-190, 93), fontsize=11,
                     arrowprops={"arrowstyle": "-", "color": "black"})
    axes[1].text(0.76, 0.85, "Кращих сусідів\nліворуч від межі: 0", fontsize=11,
                 transform=axes[1].transAxes, ha="center",
                 bbox={"facecolor": "white", "edgecolor": "none", "alpha": 0.9})
    return _save(plt, figure, output, "01_local_certificate", question, answer, limitation)


def _primary(plt, data: dict, output: Path) -> dict:
    question = "Який параметр має встановлений напрям ефекту?"
    answer = "Лише популяційний контраст має додатну нижню межу; ефект малий."
    limitation = ("Це чотири первинні BCa-інтервали 98,75%. "
                  "Вони не визначають найкращу конфігурацію для кожної задачі.")
    figure, (ax,) = _figure(plt, question=question, answer=answer,
                            limitation=limitation, rows=1, height=5.5,
                            left=0.35, bottom=0.26, top=0.84)
    rows = data["analysis"]["primary_contrasts"]
    for y, row in enumerate(rows):
        ax.plot([row["lower"] * 100, row["upper"] * 100], [y, y],
                color="black", linewidth=1.7)
        ax.plot(row["estimate"] * 100, y, "ko", markersize=5)
        ax.text(row["estimate"] * 100, y - 0.20,
                _number(row["estimate"] * 100, signed=True),
                fontsize=11, ha="center", va="bottom")
    ax.axvline(0, color="0.35", linestyle="--", linewidth=1)
    ax.set_yticks(range(len(rows)), [CONTRAST_LABELS[row["contrast_id"]] for row in rows])
    ax.set_ylim(len(rows) - 0.5, -0.65)
    ax.set_xlim(-2.0, 0.75)
    ax.set_xlabel("Різниця частот виходу, відсоткові пункти")
    ax.grid(axis="x", color="0.9", linewidth=0.6)
    return _save(plt, figure, output, "02_primary_effects", question, answer, limitation)


def _families(plt, data: dict, output: Path) -> dict:
    question = "Чи популяція 50 краща за 10 у всіх сімействах?"
    answer = ("Ні. Ненульовий популяційний контраст мають три сімейства; "
              "сім лежать на діагоналі рівності.")
    limitation = ("Частоти усереднено за рештою налаштувань і задачами сімейства. "
                  "Рисунок описовий, без нової перевірки переваги.")
    figure, (ax,) = _figure(plt, question=question, answer=answer,
                            limitation=limitation, rows=1, height=6.2,
                            bottom=0.23, top=0.86)
    pairs = data["population_pairs"]
    upper = max(0.5, max(max(row["n10"], row["n50"]) * 100 for row in pairs) * 1.2)
    ax.plot([0, upper], [0, upper], linestyle="--", color="0.35",
            linewidth=1, label="Рівність частот")
    groups = {}
    for row in pairs:
        groups.setdefault((row["n10"] * 100, row["n50"] * 100), []).append(row["family"])
    offsets = [(9, 12), (9, -27), (-62, 18), (-62, -25), (9, 28), (-62, 34)]
    for index, ((x, y), names) in enumerate(sorted(groups.items())):
        ax.plot(x, y, "ko", markersize=5, clip_on=False)
        label = "\n".join(", ".join(names[start:start + 3]) for start in range(0, len(names), 3))
        offset = offsets[index % len(offsets)]
        if x == 0 and y == 0:
            offset = (10, 12)
        ax.annotate(label, xy=(x, y), xytext=offset, textcoords="offset points",
                    fontsize=11, arrowprops={"arrowstyle": "-", "color": "0.5", "lw": 0.6})
    ax.set_xlim(0, upper)
    ax.set_ylim(0, upper)
    ax.set_aspect("equal", adjustable="box")
    ax.set_xlabel("Частота виходу за N=10, %")
    ax.set_ylabel("Частота виходу за N=50, %")
    ax.legend(loc="upper left", fontsize=11)
    ax.grid(color="0.9", linewidth=0.6)
    return _save(plt, figure, output, "03_family_population", question, answer, limitation)


def _conditions(plt, data: dict, output: Path) -> dict:
    question = "Чи вплив мутації залежить від інших налаштувань?"
    answer = "Описові частоти виходу змінюються залежно від поєднання параметрів."
    limitation = ("Спільна шкала трьох панелей. Лінії лише з'єднують категорії; "
                  "це не неперервна модель і не перевірка переможця серед 27 точок.")
    figure, axes = _figure(plt, question=question, answer=answer,
                           limitation=limitation, rows=3, height=7.9,
                           bottom=0.17, top=0.88)
    configurations = {
        (row["mutation_numerator"], row["crossover_probability"], row["population_size"]): row
        for row in data["analysis"]["configuration_summaries"] if row["start_profile"] == "local"
    }
    cross_styles = [(0, ":", "o", "Схрещування 0"),
                    (0.5, "--", "s", "Схрещування 0,5"),
                    (0.9, "-.", "^", "Схрещування 0,9")]
    for ax, population in zip(axes, (10, 30, 50)):
        for crossover, style, marker, label in cross_styles:
            values = [configurations[(mutation, crossover, population)]["escape_rate_equal_family"] * 100
                      for mutation in (0.5, 1, 3)]
            ax.plot([0, 1, 2], values, color="black", linestyle=style, marker=marker,
                    markersize=5, linewidth=1.25, label=label)
        ax.set_title("Популяція N=" + str(population), fontsize=11)
        ax.set_xticks([0, 1, 2], ["0,5/n", "1/n", "3/n"])
        ax.set_ylim(-0.04, 1.65)
        ax.set_yticks([0, 0.5, 1, 1.5], ["0", "0,5", "1,0", "1,5"])
        ax.set_xlim(-0.15, 2.15)
        ax.set_ylabel("Частота виходу, %")
        ax.grid(axis="y", color="0.9", linewidth=0.6)
    axes[0].legend(loc="upper right", fontsize=11, framealpha=0.95)
    axes[-1].set_xlabel("Імовірність мутації одного біта; n=100")
    return _save(plt, figure, output, "04_parameter_conditions", question, answer, limitation)


def _cases(data: dict, profile: str):
    return [row for row in data["trace"]["cases"]
            if row["identity"]["start_profile"] == profile]


def _record_gap(plt, data: dict, output: Path) -> dict:
    question = "Що означає відсутність виходу в конкретному запуску?"
    answer = ("Три локальні траєкторії збігаються: до оптимуму лишається 27. "
              "У цих спробах кращого набору не знайдено.")
    limitation = ("UC-s000, seed 51001; лише збережені межі поколінь і префікса. "
                  "Штрихи не встановлюють моменту зміни між точками; це не вся серія.")
    figure, axes = _figure(plt, question=question, answer=answer,
                           limitation=limitation, rows=2, height=7.9,
                           bottom=0.20, top=0.88)
    optimum = data["case"]["exact"]["confirmed_optimum"]
    for ax, profile in zip(axes, ("random", "local")):
        for case in _cases(data, profile):
            style = MUTATION_STYLES[case["identity"]["configuration_id"].split("-")[0]]
            rows = case["trajectory"]
            ax.plot([row["last_request"] for row in rows],
                    [optimum - row["best_profit"] for row in rows],
                    color="black", linestyle=style["linestyle"], marker=style["marker"],
                    markersize=2, linewidth=1, label=style["label"])
        ax.axhline(0, color="0.4", linestyle="--", linewidth=1)
        ax.set_xlim(0, 5000)
        ax.set_xlabel("Логічні оцінювання; початкові 30 враховано")
        ax.set_ylabel("Відставання рекорду\nвід оптимуму")
        ax.grid(axis="y", color="0.9", linewidth=0.6)
        ax.set_title("Випадковий початок" if profile == "random" else
                     "Локальний початок: окремий масштаб", fontsize=11)
    axes[0].set_ylim(bottom=0)
    axes[0].legend(loc="upper right", fontsize=11, framealpha=0.95)
    axes[1].set_ylim(-1, 31)
    axes[1].set_yticks([0, 10, 20, 27, 30])
    axes[1].text(0.025, 0.65, "Усі три рекорди збігаються:\nвідставання 27, виходу немає",
                 transform=axes[1].transAxes, fontsize=11,
                 bbox={"facecolor": "white", "edgecolor": "none", "alpha": 0.95})
    axes[1].text(0.025, 0.07, "Нуль — досягнутий точний оптимум",
                 transform=axes[1].transAxes, fontsize=11)
    return _save(plt, figure, output, "05_record_gap", question, answer, limitation)


def _stability(plt, data: dict, output: Path) -> dict:
    question = "Чи стійкий популяційний ефект до вилучення одного сімейства?"
    answer = "Без s005, s006 або s009 діагностичний інтервал торкається нуля."
    limitation = ("Вилучення сімейств — вторинна діагностика після перегляду "
                  "результатів. Вона не замінює первинного інтервалу 98,75%.")
    figure, (ax,) = _figure(plt, question=question, answer=answer,
                            limitation=limitation, rows=1, height=7.5,
                            left=0.30, bottom=0.19, top=0.87)
    analysis = data["analysis"]
    primary = next(row for row in analysis["primary_contrasts"]
                   if row["contrast_id"] == "population_50_over_10")
    rows = [primary]
    labels = ["Усі сімейства\n(первинний)"]
    for item in analysis["loo"]:
        rows.append(next(row for row in item["statistics"]["intervals"]
                         if row["contrast_id"] == "population_50_over_10"))
        labels.append("Без " + item["omitted_family"])
    for y, row in enumerate(rows):
        if row.get("lower") is not None and row.get("upper") is not None:
            ax.plot([row["lower"] * 100, row["upper"] * 100], [y, y],
                    color="black" if y == 0 else "0.45",
                    linewidth=1.7 if y == 0 else 1)
        ax.plot(row["estimate"] * 100, y, "ko", markersize=5 if y == 0 else 4)
    ax.axvline(0, color="black", linestyle="--", linewidth=1)
    ax.axhline(0.6, color="0.7", linewidth=0.8)
    ax.set_yticks(range(len(rows)), labels)
    ax.set_ylim(len(rows) - 0.5, -0.7)
    ax.set_xlim(-0.025, 0.58)
    ax.set_xlabel("Різниця частот виходу, відсоткові пункти")
    ax.grid(axis="x", color="0.9", linewidth=0.6)
    return _save(plt, figure, output, "06_population_stability", question, answer, limitation)


def _population(plt, data: dict, output: Path) -> dict:
    question = "Чи змінюється популяція, коли її рекорд залишається сталим?"
    answer = "Так. Середня цінність і різноманітність змінюються без нового рекорду."
    limitation = ("Три локальні UC-s000, seed 51001. Показники популяції "
                  "відсутні для незавершеного покоління: його не домальовано.")
    figure, axes = _figure(plt, question=question, answer=answer,
                           limitation=limitation, rows=2, height=7.9,
                           bottom=0.20, top=0.88)
    center = data["case"]["certificate"]["center"]["profit"]
    optimum = data["case"]["exact"]["confirmed_optimum"]
    for case in _cases(data, "local"):
        style = MUTATION_STYLES[case["identity"]["configuration_id"].split("-")[0]]
        rows = [row for row in case["trajectory"]
                if row["generation"] == 0 or row["complete"]]
        for ax, metric in zip(axes, ("mean_feasible_profit", "diversity")):
            ax.plot([row["last_request"] for row in rows], [row[metric] for row in rows],
                    color="black", linestyle=style["linestyle"], linewidth=1,
                    label=style["label"])
    axes[0].axhline(center, color="0.65", linestyle=":", linewidth=1)
    axes[0].axhline(optimum, color="0.35", linestyle="--", linewidth=1)
    axes[0].set_title("Середня цінність допустимих особин — не рекорд", fontsize=11)
    axes[0].set_ylabel("Середня цінність")
    axes[0].legend(loc="lower left", fontsize=11, framealpha=0.95)
    axes[0].text(0.03, 0.90, "Центр 46 510; оптимум 46 537; різниця 27",
                 transform=axes[0].transAxes, fontsize=11,
                 bbox={"facecolor": "white", "edgecolor": "none", "alpha": 0.95})
    axes[1].set_title("Різноманітність — не частота успішного виходу", fontsize=11)
    axes[1].set_ylabel("Частка унікальних масок")
    axes[1].set_ylim(0, 1.05)
    for ax in axes:
        ax.set_xlim(0, 5000)
        ax.set_xlabel("Логічні оцінювання; початкові 30 враховано")
        ax.grid(axis="y", color="0.9", linewidth=0.6)
    return _save(plt, figure, output, "07_population_diagnostics", question, answer, limitation)


def render(data: dict, output: Path) -> list[dict]:
    """Save seven figure pairs and their question/answer/limitation passports."""
    if os.environ.get("GITHUB_ACTIONS") != "true":
        raise RuntimeError("Scientific figures may be generated only in GitHub Actions")
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.rcParams.update({
        "font.family": "DejaVu Sans", "font.size": MIN_FONT_POINTS,
        "axes.titlesize": MIN_FONT_POINTS, "axes.labelsize": MIN_FONT_POINTS,
        "xtick.labelsize": MIN_FONT_POINTS, "ytick.labelsize": MIN_FONT_POINTS,
        "legend.fontsize": MIN_FONT_POINTS, "axes.spines.top": False,
        "axes.spines.right": False, "figure.facecolor": "white",
        "axes.facecolor": "white", "pdf.fonttype": 42,
    })
    output = Path(output)
    return [renderer(plt, data, output) for renderer in (
        _certificate, _primary, _families, _conditions, _record_gap,
        _stability, _population)]
