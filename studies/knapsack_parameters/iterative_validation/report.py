"""Ukrainian Markdown, Matplotlib figures and PDF exports, only in CI.

Figure captions are placed below figures in PDFs and in external metadata;
axes contain units and legends, without internal titles. No figure is made
at import time. This module does not import any scientific search code.
"""

from __future__ import annotations

from pathlib import Path
import textwrap

from .analysis import (
    FAMILIES, PRIMARY_PAIR, SELECTED_CONFIGS, TARGETS, TOTAL,
    configuration_id, require_ci, write_json,
)


COLORS = ("#1764a0", "#db7625", "#37935b", "#9064b0")
MARKERS = ("o", "s", "^", "D")


def _label(config):
    return f"μ = {config[0]}, pс = {config[1]} %, pм = {config[2] / 100:g} %"


def _short(identifier):
    return identifier.replace("-pm100bp", "").replace("mu", "μ=").replace("-pc", ", pс=") + "%"


def _number(value, places=3):
    return f"{float(value):,.{places}f}".replace(",", " ").replace(".", ",")


def _primary(result):
    return next(row for row in result["pair_summaries"] if row["primary_diagnostic"])


def markdown(result) -> str:
    primary = _primary(result)
    lines = [
        "# Поетапна перевірка параметрів: описовий аналіз збережених даних",
        "",
        "Проаналізовано вже отримані результати добору параметрів для задач із 100 предметами. "
        "Повна перевірка охоплює 2790 записів: 31 конфігурацію × 10 сімейств × 3 типи задач × 3 повторення. "
        "Усі конфігурації використовують ті самі пари «задача, початкове число». "
        "Окремо порівняно чотири наперед визначені конфігурації за мутації 1 %.",
        "",
        "## Визначення та межі перевірки",
        "",
        "Шкала q охоплює 100 000 оцінювань, включно з початковою популяцією q = 1…μ. "
        "T₉₃, T₉₅ і T₉₉ — перше оцінювання, коли цілочисельний запис задовольняє "
        "100·v ≥ t·оптимум. T₁₀₀ означає досягнення точного оптимуму. "
        "За недосягнення обмежене T дорівнює 100 000; окрема логічна ознака зберігає відмінність "
        "між недосягненням та досягненням саме на останньому оцінюванні.",
        "",
        "Відставання дорівнює 100·(оптимум − v)/оптимум. Середні обчислено точно як раціональні числа: "
        "спершу за повтореннями задачі, потім за трьома задачами сімейства, потім за десятьма сімействами. "
        "Округлення застосовано лише в читабельних таблицях та рисунках. CSV містять чисельники й знаменники.",
        "",
        "Перевірено збережені компактні події, початкові ідентичності, узгодженість збережених SHA-256 банків "
        "початкових популяцій; вміст банків не хешувався повторно. Також перевірено "
        "посилання на точні оптимуми, досягнення цілей, п’ять контрольних точок та історичні агрегати. "
        "Цей етап не відтворює повні журнали заново. Історичний статус незалежної перевірки "
        "1350 нових та 1440 повторно використаних записів перенесено в provenance.json із джерела.",
        "",
        "Активність операторів з operator_bins.json, повні маски розв’язків і первинні журнали "
        "на цьому етапі повторно не перевіряються. Збережені SHA-256 цих артефактів є посиланнями "
        "на історичні докази; вони не замінюють нового аудиту їхнього вмісту. "
        "Діагностика активності операторів залишається відкритим пунктом.",
        "",
        "## Чотири конфігурації",
        "",
        "| μ | pс, % | Кінцеве відставання, % | Обмежене T₉₃, оцінювання | T₉₅, оцінювання | T₉₉, оцінювання | Досягли 99 % | Точний оптимум |",
        "|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in result["configuration_metrics"]:
        lines.append(f'| {row["mu"]} | {row["pc_percentage"]} | {_number(row["mean_gap_100000_percent"], 6)} '
                     f'| {_number(row["mean_restricted_t93"])} | {_number(row["mean_restricted_t95"])} '
                     f'| {_number(row["mean_restricted_t99"])} | {row["attained_99"]}/90 | {row["attained_100"]}/90 |')
    lines.extend([
        "", "## Парні описові діагностики", "",
        "Для кожної з шести пар A і B зіставлено 90 спільних пар «задача, початкове число». "
        "Δ = B − A. Додатне Δ означає раніше досягнення цілі або менше відставання для A. "
        "Від’ємне Δ означає відповідну перевагу B. Відставання порівнюється у відсоткових пунктах.",
        "",
        "| A | B | Середнє ΔT₉₃, оцінювання | Середнє Δвідставання, в.п. |",
        "|---|---|---:|---:|",
    ])
    for row in result["pair_summaries"]:
        lines.append(f'| {_short(row["configuration_a"])} | {_short(row["configuration_b"])} '
                     f'| {_number(row["mean_delta_restricted_t93"])} '
                     f'| {_number(row["mean_delta_gap_100000_percent"], 6)} |')
    lines.extend([
        "", "## Основна діагностика: μ = 10 проти μ = 15 за pс = 90 %", "",
        f'У цій парі A = μ 10, B = μ 15. Середнє ΔT₉₃ становить '
        f'{_number(primary["mean_delta_restricted_t93"])} оцінювання; середнє Δкінцевого відставання — '
        f'{_number(primary["mean_delta_gap_100000_percent"], 6)} відсоткового пункта. '
        f'A має менше обмежене T₉₃ у {primary["a_earlier_or_smaller_restricted_t93"]} парах, '
        f'B має менше обмежене T₉₃ у {primary["b_earlier_or_smaller_restricted_t93"]} парах; '
        f'однакове обмежене T₉₃ — у {primary["ties_restricted_t93"]} парах. '
        "Рівність на межі 100 000 оцінювань може означати недосягнення цілі.",
        "",
    ])
    for metric, label, units in (("restricted_t93", "ΔT₉₃", "оцінювання"),
                                  ("gap_100000_percent", "Δкінцевого відставання", "в.п.")):
        values = [r["mean_delta_" + metric] for r in result["leave_one_family_out"] if r["primary_diagnostic"]]
        positive, negative, ties = (sum(v > 0 for v in values), sum(v < 0 for v in values), sum(v == 0 for v in values))
        lines.append(f'Після почергового вилучення одного сімейства {label} змінюється від '
                     f'{_number(min(values), 6)} до {_number(max(values), 6)} {units}. '
                     f'Додатний знак у {positive}/10 випадках, від’ємний — у {negative}/10, нульовий — у {ties}/10.')
        lines.append("")
    lines.extend([
        "Це перевірка чутливості описових середніх до складу десяти сімейств. "
        "Вона не є довірчим інтервалом, перевіркою гіпотез або доказом еквівалентності. "
        "Повторення однієї задачі не трактуються як незалежні задачі. "
        "Ці результати походять із вибірки добору параметрів; незалежну перевірку ще не виконано.",
        "", "## Аудит історичних середніх і ранжування", "",
        "ranking-audit.csv містить усі 31 конфігурацію, точні середні та окремі ранги за кінцевим відставанням "
        "і T₉₃. Однакові точні середні мають однаковий ранг. Усі середні та лічильники зіставлено з "
        "історичним all-configurations.csv; припустиме абсолютне відхилення серіалізації становить "
        "10⁻¹² відсоткового пункта для відставання та 10⁻⁹ оцінювання для середніх T. "
        "Лічильники збігаються точно. Історичні точні раціональні середні вибраних конфігурацій збігаються точно.",
        "",
        "Історичний вибір збережено без змін: якість — μ = 15, pс = 100 %, мутація 1 %; "
        "швидкість — μ = 10, pс = 90 %, мутація 1 %. Цей етап не виконує нового добору параметрів "
        "і не запускає нових генетичних пошуків. Дослідження μ = 13 належить до окремого наступного етапу.",
        "", "## Файли та рисунки", "",
        "Таблиці CSV мають UTF-8 із BOM та роздільник «;». summary.json містить точні числові результати, "
        "provenance.json — SHA-256 входів і виходів. figure-metadata.json містить зовнішні підписи "
        "до кожного PNG/SVG; PDF-альбом відтворює підписи під рисунками. "
        "Криві досягнення 93 %, 95 % і 99 % мають окремі осі 0–100 %.",
        "",
    ])
    return "\n".join(lines)


def _plots(result, plt):
    metrics = {r["configuration_id"]: r for r in result["configuration_metrics"]}
    runs = result["run_metrics"]
    fig, ax = plt.subplots(figsize=(8.0, 5.4))
    for config, color, marker in zip(SELECTED_CONFIGS, COLORS, MARKERS):
        row = metrics[configuration_id(config)]
        ax.scatter(float(row["mean_restricted_t93"]), float(row["mean_gap_100000_percent"]),
                   s=80, color=color, marker=marker, label=_label(config), zorder=3)
    ax.set(xlabel="Середнє обмежене T₉₃, оцінювання",
           ylabel="Середнє кінцеве відставання від оптимуму, %")
    ax.grid(alpha=.25)
    ax.legend(fontsize=9)
    yield "quality-speed", fig, ("Зіставлення чотирьох конфігурацій за середнім обмеженим T₉₃ "
                                  "та кінцевим відставанням після 100 000 оцінювань. Менші значення обох осей кращі.")
    for target in TARGETS:
        fig, ax = plt.subplots(figsize=(8.0, 5.4))
        for config, color in zip(SELECTED_CONFIGS, COLORS):
            own = [r for r in runs if r["configuration_id"] == configuration_id(config)]
            times = sorted(r[f"first_t{target}"] for r in own if r[f"attained_{target}"])
            xs = [0, *times, TOTAL]
            ys = [0, *(100 * (i + 1) / len(own) for i in range(len(times))), 100 * len(times) / len(own)]
            ax.step(xs, ys, where="post", color=color, label=_label(config))
        ax.set(xlim=(0, TOTAL), ylim=(0, 100), xlabel="Загальні оцінювання, включно з початковими",
               ylabel=f"Досягли {target} % оптимуму, % запусків")
        ax.ticklabel_format(axis="x", style="plain")
        ax.grid(alpha=.25)
        ax.legend(fontsize=9, loc="lower right")
        yield f"attainment-{target}", fig, (f"Емпірична крива першого досягнення {target} % оптимуму. "
                                            "Знаменник — усі 90 запусків конфігурації; недосягнення не утворюють подій. "
                                            "Вісь частки запусків охоплює 0–100 %.")
    for metric, label, units in (("restricted_t93", "T₉₃", "оцінювання"),
                                  ("gap_100000_percent", "кінцеве відставання", "в.п.")):
        own = [r for r in result["family_differences"] if r["primary_diagnostic"]]
        mapping = {r["family"]: r["mean_delta_" + metric] for r in own}
        fig, ax = plt.subplots(figsize=(8.0, 5.4))
        ax.plot(FAMILIES, [float(mapping[f]) for f in FAMILIES], marker="o", color=COLORS[0],
                label="A: μ = 10; B: μ = 15; pс = 90 %")
        ax.axhline(0, color="#555555", linewidth=.9, label="Однакові середні")
        ax.set(xlabel="Сімейство задач", ylabel=f"Середнє Δ ({label}), {units}")
        ax.grid(alpha=.25)
        ax.legend(fontsize=9)
        yield f"family-differences-{metric}", fig, (f"Основна діагностика за сімействами: Δ{label} = B − A. "
                                                   "Кожна точка усереднює три повторення кожного з трьох типів задач. "
                                                   "Додатне значення відповідає перевазі A.")
        fig, ax = plt.subplots(figsize=(10.2, 5.8))
        labels = []
        for index, pair in enumerate(result["pair_summaries"]):
            rows = [r for r in result["paired_differences"] if r["pair_id"] == pair["pair_id"]]
            offsets = [((i % 15) - 7) * .014 for i in range(len(rows))]
            ax.scatter([index + offset for offset in offsets], [float(r["delta_" + metric]) for r in rows],
                       s=12, alpha=.45, color=COLORS[0], label="Парна різниця запусків" if index == 0 else None)
            ax.scatter(index, float(pair["mean_delta_" + metric]), color="#b22b35", marker="D", s=46,
                       zorder=4, label="Середнє з рівними вагами сімейств" if index == 0 else None)
            labels.append(_short(pair["configuration_a"]) + "\n→ " + _short(pair["configuration_b"]))
        ax.axhline(0, color="#555555", linewidth=.9, label="Нульова різниця")
        ax.set(xticks=range(len(labels)), xticklabels=labels, xlabel="Пара A → B", ylabel=f"Δ ({label}) = B − A, {units}")
        ax.tick_params(axis="x", labelsize=8)
        ax.grid(axis="y", alpha=.25)
        ax.legend(fontsize=8)
        yield f"paired-differences-{metric}", fig, (f"Усі шість пар чотирьох конфігурацій: 90 парних різниць {label} "
                                                   "у кожній групі. Горизонтальний зсув точок служить читабельності. "
                                                   "Ромби позначають описові середні; додатне Δ означає перевагу A.")


def _text_pages(plt, title, paragraphs):
    """Paginate wrapped lines inside explicit top and bottom margins."""
    top, bottom, line_height, paragraph_gap = .88, .085, .021, .023
    page_number = 1

    def new_page(number):
        page = plt.figure(figsize=(8.27, 11.69))
        heading = title if number == 1 else f"{title} (продовження {number})"
        page.text(.085, .94, heading, fontsize=16, va="top", weight="bold")
        return page

    fig, y, has_content = new_page(page_number), top, False
    for paragraph in paragraphs:
        lines = textwrap.wrap(paragraph, width=93, break_long_words=False, break_on_hyphens=False)
        if not lines:
            continue
        required = line_height * len(lines) + paragraph_gap
        if has_content and required <= top - bottom and y - required < bottom:
            yield fig
            page_number += 1
            fig, y, has_content = new_page(page_number), top, False
        while lines:
            available = int((y - bottom) / line_height)
            if available < 1:
                yield fig
                page_number += 1
                fig, y, has_content = new_page(page_number), top, False
                continue
            chunk, lines = lines[:available], lines[available:]
            fig.text(.085, y, "\n".join(chunk), fontsize=10, va="top", linespacing=1.45)
            y -= line_height * len(chunk)
            has_content = True
            if lines:
                yield fig
                page_number += 1
                fig, y, has_content = new_page(page_number), top, False
        y -= paragraph_gap
    if has_content:
        yield fig


def render_report(result, output: Path) -> None:
    require_ci()
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.backends.backend_pdf import PdfPages
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10,
                         "axes.labelsize": 10, "pdf.fonttype": 42, "svg.fonttype": "none"})
    output = Path(output)
    (output / "report.md").write_text(markdown(result), encoding="utf-8")
    figure_dir = output / "figures"
    figure_dir.mkdir()
    metadata = []
    primary = _primary(result)
    paragraphs = [
        "Збережена вибірка добору параметрів: 2790 записів, 31 конфігурація, 30 задач із 100 предметами, "
        "три початкові числа для кожної задачі. Окремий описовий аналіз: чотири конфігурації, шість пар, "
        "90 узгоджених запусків у кожній парі. Мутація чотирьох конфігурацій становить 1 %.",
        "T₉₃, T₉₅ і T₉₉ відновлено за цілочисельними подіями 100·v ≥ t·оптимум. "
        "Шкала включає початкові оцінювання q = 1…μ і останнє q = 100 000. За недосягнення "
        "обмежене T дорівнює 100 000, а окрема ознака досягнення лишається хибною.",
        "Середні отримано точно: повторення → задача → сімейство. Різниці Δ = B − A; "
        "додатний знак означає раніше досягнення або менше відставання для A. "
        "Усі обчислення та рисунки виконуються в GitHub Actions.",
        f'Основна діагностика A: μ = 10, B: μ = 15, pс = 90 %. '
        f'Середнє ΔT₉₃: {_number(primary["mean_delta_restricted_t93"])} оцінювання. '
        f'Середнє Δкінцевого відставання: {_number(primary["mean_delta_gap_100000_percent"], 6)} в.п. '
        f'A має менше обмежене T₉₃ у {primary["a_earlier_or_smaller_restricted_t93"]} парах, '
        f'B — у {primary["b_earlier_or_smaller_restricted_t93"]}; '
        f'однакове обмежене T₉₃ — у {primary["ties_restricted_t93"]} парах. '
        "Рівність на межі може означати недосягнення цілі.",
        "Перевірено компактні події, ідентичності, узгодженість збережених SHA-256 банків; "
        "вміст банків не хешувався повторно. Також перевірено узгодженість збережених "
        "точних оптимумів і SHA-256 сертифікатів, збережені цілі, контрольні точки, усі історичні "
        "середні та точні значення історичного вибору. "
        "Повні журнали на цьому етапі заново не відтворювалися.",
        "Активність операторів з operator_bins.json, повні маски розв’язків і первинні журнали "
        "повторно не перевіряються. Їхні збережені SHA-256 служать посиланнями на історичні докази; "
        "діагностика активності операторів залишається відкритим пунктом.",
        "Історичний вибір незмінний: якість — μ = 15, pс = 100 %; швидкість — μ = 10, pс = 90 %. "
        "Аналіз описовий: без перевірок гіпотез, довірчих інтервалів та тверджень про еквівалентність. "
        "Незалежну перевірку і дослідження μ = 13 ще не виконано.",
        "Точні чисельники та знаменники доступні у CSV і JSON. Результати вилучення кожного сімейства "
        "наведено в leave-one-family-out.csv. report.md містить повний читабельний виклад; "
        "figure-album.pdf містить усі рисунки з підписами. provenance.json зв’язує входи й виходи через SHA-256.",
    ]
    pdf_metadata = {"Title": "Поетапна перевірка параметрів рюкзака", "Author": "CI analysis",
                    "Subject": "Описовий аудит збережених компактних записів"}
    with PdfPages(output / "short-report.pdf", metadata=pdf_metadata) as short_pdf, \
            PdfPages(output / "figure-album.pdf", metadata=pdf_metadata) as album:
        for page in _text_pages(plt, "Описовий аудит параметрів", paragraphs):
            short_pdf.savefig(page)
            plt.close(page)
        for index, (name, fig, caption) in enumerate(_plots(result, plt), 1):
            # Space for a caption outside axes; no internal plot titles.
            fig.subplots_adjust(left=.13, right=.97, top=.96, bottom=.30)
            png, svg = figure_dir / (name + ".png"), figure_dir / (name + ".svg")
            fig.savefig(png, dpi=180, bbox_inches="tight")
            fig.savefig(svg, bbox_inches="tight")
            fig.text(.085, .17, "\n".join(textwrap.wrap(f"Рисунок {index}. {caption}", width=108)),
                     fontsize=9, va="top", linespacing=1.4)
            album.savefig(fig)
            if name in ("quality-speed", "attainment-93", "family-differences-restricted_t93"):
                short_pdf.savefig(fig)
            metadata.append({"id": name, "number": index, "caption_uk": caption,
                             "png": png.relative_to(output).as_posix(),
                             "svg": svg.relative_to(output).as_posix(),
                             "axes_internal_title": None,
                             "data_scope": "frozen tuning evidence; descriptive only"})
            plt.close(fig)
    write_json(output / "figure-metadata.json", {"schema": "knapsack-iterative-validation-figures-v1",
                                                "figures": metadata})
