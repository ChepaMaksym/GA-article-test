"""Render the same CI summary into CSV-backed figures and three report formats."""

import subprocess
from pathlib import Path
from tempfile import TemporaryDirectory
from xml.dom import minidom
from zipfile import ZipFile


LABEL = {
    "IDENTICAL": "Тотожна конфігурація",
    "DESCRIPTIVE": "Описовий результат",
    "FAVOURS_CANDIDATE": "Перевага кандидата",
    "FAVOURS_CONTROL": "Перевага контролю",
    "DIRECTION_UNRESOLVED": "Напрям переваги не встановлено",
}
COLORS = ("#3b648c", "#c3641d", "#70679d", "#297450")


def number(value, digits=3):
    return f"{value:.{digits}f}".replace(".", ",").replace("-", "−")


def plots(output, summary, curves):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    folder = output / "figures"
    folder.mkdir()
    profiles = summary["profiles"]
    labels = [p["configuration"] for p in profiles]
    captions = []

    def save(fig, key, caption):
        for ext in ("png", "svg"):
            fig.savefig(folder / f"{key}.{ext}", dpi=190, bbox_inches="tight")
        plt.close(fig)
        captions.append({"image": "figures/" + key + ".png", "caption": caption})

    fig, ax = plt.subplots(figsize=(7.1, 3.3), layout="constrained")
    bars = ax.barh(labels, [p["final_gap"] for p in profiles], color=COLORS)
    ax.invert_yaxis()
    ax.set_xlim(left=0)
    ax.set_xlabel("Середнє кінцеве відставання, % оптимальної цінності")
    ax.set_ylabel("Популяція / схрещування / мутація")
    ax.grid(axis="x", alpha=.2)
    ax.legend([bars[0]], ["Середнє за десятьма сімействами"], fontsize=8)
    save(fig, "quality", "Рисунок 1 – Середнє відставання після 100 000 оцінювань.")
    for index, (target, points) in enumerate(curves.items(), 2):
        fig, ax = plt.subplots(figsize=(7.1, 3.65), layout="constrained")
        for label, color, style in zip(labels, COLORS, ("-", "--", "-.", ":"), strict=True):
            series = [p for p in points if p["configuration"] == label]
            ax.step([p["evaluations"] for p in series], [p["percent"] for p in series],
                    where="post", label=label, color=color, linestyle=style, linewidth=1.65)
        ax.set_xlim(0, 100000)
        # The symlog axis keeps q=0 and shows early crossings and the entire search.
        ax.set_xscale("symlog", linthresh=1000, linscale=1)
        ticks = [0, 500, 1000, 2500, 5000, 10000, 50000, 100000]
        ax.set_xticks(ticks, ["0", "500", "1 000", "2 500", "5 000", "10 000", "50 000", "100 000"],
                      fontsize=8)
        ax.set_ylim(0, 100)
        ax.set_xlabel("Загальна кількість оцінювань")
        ax.set_ylabel(f"Досягли {target}% оптимуму, % запусків")
        ax.grid(alpha=.2)
        ax.legend(title="Популяція / схрещування / мутація", fontsize=8, title_fontsize=8)
        save(fig, f"attainment-{target}",
             f"Рисунок {index} – Досягнення {target}% оптимуму. Вісь оцінювань лінійна до 1000, далі логарифмічна.")
    return captions


def markdown(summary, captions):
    roles = {"quality": "Кінцева якість", "speed": "Швидкість до 93%"}
    secondary = summary["secondary"]
    difference = secondary["mean_t93_mu15_minus_mu10"]
    without = [r["without_family"] for r in secondary["families"]]
    if min(without) > 0:
        sensitivity = "За почергового вилучення кожного сімейства раніше досягала цілі популяція 10."
    elif max(without) < 0:
        sensitivity = "За почергового вилучення кожного сімейства раніше досягала цілі популяція 15."
    elif min(without) < 0 < max(without):
        sensitivity = "За почергового вилучення сімейств напрям різниці змінювався."
    else:
        sensitivity = "Серед оцінок із вилученням одного сімейства є нульова різниця."
    text = ["# Незалежна перевірка початкових параметрів генетичного алгоритму",
            "", "## Постановка й умови", "",
            "Мета дослідження полягає у перевірці відтворюваності двох рекомендацій для рюкзака зі 100 предметами. "
            "Для кінцевої якості раніше обрано 15 особин, схрещування 100% і мутацію 1%. "
            "Для досягнення 93% оптимуму обрано 10 особин, схрещування 90% і мутацію 1%.",
            "", "До серії увійшли 30 задач десяти сімейств s060–s069 класів UC, WC та SC. "
            "Виконано десять парних повторень кожної фізичної конфігурації на задачу. "
            "Кожний із 1200 журналів пошуку пройшов незалежну програмну перевірку. "
            "До 100 000 загальних оцінювань входять початкові особини. "
            "Результати усереднено послідовно за повтореннями, задачами та сімействами.", "",
            "## Результати чотирьох конфігурацій", "",
            "| Популяція / схрещування / мутація | Відставання, % | Оцінювань до 93% | Досягли 93% | Досягли 95% | Досягли 99% |",
            "|---|---:|---:|---:|---:|---:|"]
    for row in summary["profiles"]:
        text.append(f"| {row['configuration']} | {number(row['final_gap'], 6)} | {number(row['t93'])} "
                    f"| {row['attained_93']}/300 | {row['attained_95']}/300 | {row['attained_99']}/300 |")
    text += ["", "Відставання обчислено за найкращою допустимою цінністю на завершенні пошуку. "
             "Для часу досягнення цілі використано перший номер оцінювання, на якому досягнуто порогу. "
             "Кожному недосягненню відповідає значення 100 000. Втрати до 7%, 5% і 1% відповідають порогам 93%, 95% і 99%.",
             "", "## Первинні порівняння", "",
             "Додатна різниця показника контролю та кандидата відповідає кращому результату кандидата. "
             "Для кінцевої якості одиницею є відсотковий пункт, для швидкості одиницею є оцінювання. "
             "Номінальний інтервал для кожного порівняння становить 99,1667% з урахуванням шести "
             "заздалегідь визначених порівнянь. У кожній із 50 000 повторних вибірок відбирали цілі сімейства.", "",
             "| Показник | Контроль | Різниця | Нижня межа | Верхня межа | Висновок |",
             "|---|---|---:|---:|---:|---|"]
    for row in summary["primary"]:
        bounds = [number(x, 6) if x is not None else "–" for x in (row["lower"], row["upper"])]
        text.append(f"| {roles[row['role']]} | {row['control']} | {number(row['estimate'], 6)} | "
                    f"{bounds[0]} | {bounds[1]} | {LABEL[row['conclusion']]} |")
    text += ["", "## Парне порівняння популяцій 10 і 15 за схрещування 90%", "",
             "Різниця середніх чисел оцінювань до 93% оптимуму (15 мінус 10 особин) становила "
             f"{number(difference)}. Популяція 10 досягла меншого обмеженого часу в {secondary['mu10_faster']} "
             f"парах, популяція 15 у {secondary['mu15_faster']}. Збіги отримано в {secondary['ties']} парах. "
             f"{sensitivity} Додаткову діагностику проведено за 300 парами. "
             "Різниця 0,067 оцінювання у попередній серії характеризує вибірку добору. "
             "Для незалежної серії практичну межу еквівалентності конфігурацій не визначали.", "",
             "## Кінцева якість і перебіг пошуку", ""]
    for item in captions:
        text += [f"![]({item['image']})", "", item["caption"], ""]
    text += ["## Висновки", ""]
    for role, candidate in (("quality", "15 / 100% / 1%"), ("speed", "10 / 90% / 1%")):
        verdicts = [f"{r['control']} ({LABEL[r['conclusion']].lower()})"
                    for r in summary["primary"] if r["role"] == role and r["status"] != "IDENTICAL"]
        text += [f"{roles[role]}. Для кандидата {candidate} отримано такі результати за контролями: "
                 + ", ".join(verdicts) + ".", ""]
    if summary["quality_base_confirmed_against_both_distinct_controls"]:
        text.append("Обидва первинні порівняння кінцевої якості підтримали перевагу конфігурації "
                    "15 / 100% / 1%. Для наступного дослідження відбору її можна використати як підтверджену базу.")
    else:
        text.append("Умова підтвердження бази 15 / 100% / 1% для наступного дослідження відбору "
                    "вимагала додатних нижніх меж обох інтервалів кінцевої якості. За отриманими даними умову не виконано.")
    text += ["", "Висновки стосуються використаних задач, операторів та граничної кількості оцінювань. "
             "Одиницею статистичного узагальнення є сімейство задач. Десять випробуваних сімейств визначають "
             "обсяг незалежної інформації для оцінки невизначеності.", ""]
    return "\n".join(text)


def _reference_document(destination):
    """Adjust the built-in Word template while preserving Office namespace prefixes."""
    blank = destination.with_name("base.docx")
    blank.write_bytes(subprocess.check_output(["pandoc", "--print-default-data-file", "reference.docx"]))
    word = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
    with ZipFile(blank) as src, ZipFile(destination, "w") as dst:
        for info in src.infolist():
            data = src.read(info)
            if info.filename in {"word/styles.xml", "word/document.xml"}:
                xml = minidom.parseString(data)
                if info.filename.endswith("styles.xml"):
                    for style in xml.getElementsByTagNameNS(word, "style"):
                        name = style.getAttributeNS(word, "styleId")
                        if name not in {"Normal", "BodyText", "FirstParagraph", "Caption", "ImageCaption"}:
                            continue
                        def child(parent, local_name):
                            elements = [n for n in parent.childNodes if n.localName == local_name]
                            if elements:
                                return elements[0]
                            element = xml.createElementNS(word, "w:" + local_name)
                            parent.appendChild(element)
                            return element
                        props = child(style, "pPr")
                        spacing = child(props, "spacing")
                        spacing.setAttributeNS(word, "w:line", "360")
                        spacing.setAttributeNS(word, "w:lineRule", "auto")
                        if name in {"BodyText", "FirstParagraph"}:
                            child(props, "ind").setAttributeNS(word, "w:firstLine", "850")
                        run = child(style, "rPr")
                        fonts = child(run, "rFonts")
                        for key in ("ascii", "hAnsi", "cs"):
                            fonts.setAttributeNS(word, "w:" + key, "Times New Roman")
                        child(run, "sz").setAttributeNS(word, "w:val", "28")
                else:
                    for margins in xml.getElementsByTagNameNS(word, "pgMar"):
                        for key, width in (("left", "1134"), ("right", "567"), ("top", "1134"), ("bottom", "1134")):
                            margins.setAttributeNS(word, "w:" + key, width)
                data = xml.toxml(encoding="utf-8")
            dst.writestr(info, data)


def build_report(output, summary, curves, family_effects):
    captions = plots(output, summary, curves)
    report = markdown(summary, captions)
    md = output / "Звіт.md"
    md.write_bytes(report.encode())
    with TemporaryDirectory() as work:
        work = Path(work)
        template = work / "reference.docx"
        _reference_document(template)
        document = output / "Звіт.docx"
        subprocess.run(["pandoc", str(md), "--from", "markdown-implicit_figures", "--to", "docx",
                        "--resource-path", str(output.resolve()), "--reference-doc", str(template),
                        "--metadata", "lang=uk-UA", "--output", str(document)], check=True)
        subprocess.run(["libreoffice", "-env:UserInstallation=" + (work / "lo").as_uri(), "--headless",
                        "--convert-to", "pdf", "--outdir", str(output.resolve()), str(document.resolve())],
                       check=True, timeout=120)
        pdf_text = subprocess.check_output(["pdftotext", str(output / "Звіт.pdf"), "-"]).decode()
        if not all(value in pdf_text for value in ("Висновки", "1200", "99,1667%", "Рисунок 4")):
            raise ValueError("The rendered PDF lacks a required section, sample count, interval or figure caption")
        with ZipFile(document) as zipped:
            if len([p for p in zipped.namelist() if p.startswith("word/media/")]) < len(captions):
                raise ValueError("The Word report did not embed all figures")
