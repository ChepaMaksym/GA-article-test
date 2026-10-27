"""Six separate, title-free figures for four matched historical profiles."""
from pathlib import Path
import math
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from . import authority as a
from .review import COLORS, NAMES, PROFILES


QUALITY_LABELS = {0: "Сталі параметри", 1: "Змінюється лише мутація",
                  4: "Змінюється лише популяція", 5: "Змінюються мутація й популяція"}


def quality_figure(cells):
    """Direct labels and a zero-origin scale replace the four-cell map."""
    a.ci_only()
    a.require(len(cells) == 4 and {c["profile"] for c in cells} == set(PROFILES), "four unique quality profiles required")
    a.require(all(c["runs"] == 900 and math.isfinite(c["mean_final_gap_percent"]) and
                  0 <= c["mean_final_gap_percent"] <= 6 for c in cells), "invalid quality values/denominators")
    ordered = sorted(cells, key=lambda c: (c["mean_final_gap_percent"], c["profile"]))
    fig, ax = plt.subplots(figsize=(10, 3.6), constrained_layout=True)
    bars = ax.barh(range(4), [c["mean_final_gap_percent"] for c in ordered], height=.52,
                   color=[COLORS[c["profile"]] for c in ordered], zorder=3)
    ax.set_yticks(range(4), [QUALITY_LABELS[c["profile"]] for c in ordered], fontsize=12)
    ax.invert_yaxis()
    ax.set_xlim(0, 6)
    ax.set_xticks(range(7))
    ax.set_xlabel("Середнє відставання від оптимуму, %", fontsize=12)
    ax.set_ylabel("Варіант алгоритму", fontsize=12)
    ax.grid(axis="x", alpha=.2, zorder=0)
    ax.spines[["top", "right"]].set_visible(False)
    for bar, cell in zip(bars, ordered, strict=True):
        ax.text(bar.get_width() + .08, bar.get_y() + bar.get_height()/2,
                f"{cell['mean_final_gap_percent']:.3f}%".replace(".", ","),
                va="center", fontsize=13, fontweight="bold", color="#173044")
    return fig, ax, [{"profile": c["profile"], "label": QUALITY_LABELS[c["profile"]],
                      "gap_percent": c["mean_final_gap_percent"], "bar_width": bar.get_width(), "runs": c["runs"]}
                     for c, bar in zip(ordered, bars, strict=True)]


def render_quality(summary, directory):
    a.ci_only()
    a.require(summary["status"] == "COMPLETE_VERIFIED_SECONDARY_REVIEW", "unverified saved figure source")
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 11, "savefig.dpi": 180,
                         "axes.formatter.useoffset": False})
    fig, ax, bars = quality_figure(summary["cells"])
    a.require(len(fig.axes) == 1 and not ax.get_title(), "one title-free chart required")
    receipt = {"file": "06_joint_quality.png", "kind": "horizontal_bars", "bars": bars,
               "xlabel": ax.get_xlabel(), "ylabel": ax.get_ylabel(), "xlim": list(ax.get_xlim()),
               "inside_title": ax.get_title(), "colorbar": False, "new_analysis": False,
               "caption": "Середнє кінцеве відставання чотирьох варіантів. Коротший стовпчик означає кращу якість; по 900 запусків, сімейства мають рівну вагу."}
    for suffix in (".png", ".svg"):
        fig.savefig(directory / ("06_joint_quality" + suffix), bbox_inches="tight")
    plt.close(fig)
    return receipt


def render(summary, examples, directory):
    a.ci_only()
    a.require(summary["status"] == "COMPLETE_VERIFIED_SECONDARY_REVIEW", "incomplete review figure source")
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 11, "savefig.dpi": 180,
                         "axes.formatter.useoffset": False})
    receipt = {"figures": [], "inside_titles": 0, "new_search": False}

    def axis(ylabel):
        fig, ax = plt.subplots(figsize=(9.2, 4.3), constrained_layout=True)
        ax.set_xlabel("Нові оцінювання")
        ax.set_ylabel(ylabel)
        ax.set_xlim(0, 5000)
        ax.spines[["top", "right"]].set_visible(False)
        ax.grid(alpha=.22)
        return fig, ax

    def save(fig, ax, filename, caption):
        a.require(all(not item.get_title() for item in fig.axes), "inside-figure title")
        a.require(bool(ax.get_xlabel()) and bool(ax.get_ylabel()), "missing standalone axis label")
        legend = ax.get_legend()
        entry = {"file": filename, "caption": caption, "xlabel": ax.get_xlabel(), "ylabel": ax.get_ylabel(),
                 "ylim": list(ax.get_ylim()), "legend": [] if legend is None else [t.get_text() for t in legend.get_texts()],
                 "data_series": [{"label": line.get_label(), "points": len(line.get_xdata())} for line in ax.lines]}
        for suffix in (".png", ".svg"):
            fig.savefig(directory / (Path(filename).stem + suffix), bbox_inches="tight")
        plt.close(fig)
        receipt["figures"].append(entry)

    for field, filename, ylabel, scale, active, shared in (
        ("p_m", "01_mutation.png", "Мутація одного біта, %", 100, (1, 5), "Стала мутація: контроль і адаптація популяції"),
        ("target_mu", "02_population_target.png", "Цільовий розмір наступної\nпопуляції, осіб", 1, (4, 5), "Стала популяція: контроль і адаптація мутації")):
        fig, ax = axis(ylabel)
        fixed = .01 * scale if field == "p_m" else 30
        ax.plot([0, 5000], [fixed, fixed], color=COLORS[0], linestyle="--", linewidth=1.7, label=shared)
        for example in examples:
            if example["profile"] not in active:
                continue
            generations = example["generations"]
            x = [g["start_q"] - 1 for g in generations] + [5000]
            y = [scale * g["parameters_before"][field] for g in generations]
            ax.step(x, y + [y[-1]], where="post", color=COLORS[example["profile"]], linewidth=1.7,
                    label=NAMES[example["profile"]])
        ax.set_ylim((0, 8.6) if field == "p_m" else (0, 108))
        ax.legend(fontsize=9, loc="best")
        save(fig, ax, filename, "Застосовані значення параметра для UC-s020, повторення 97001. Зміна після завершеного покоління діє на наступне покоління; однакові сталі лінії об'єднано.")

    fig, ax = axis("Рекорд, % OPT")
    for example in examples:
        events = example["record_events"]
        x = [e["q"] for e in events] + [5000]
        y = [100 * e["profit"] / example["optimum"] for e in events]
        ax.step(x, y + [y[-1]], where="post", color=COLORS[example["profile"]], linewidth=1.8, label=NAMES[example["profile"]])
    ax.legend(fontsize=10, loc="lower right")
    save(fig, ax, "03_record.png", "Рекорд чотирьох варіантів для UC-s020, повторення 97001. OPT є точним оптимумом; приклад ілюструє перебіг пошуку, а підсумки спираються на всі запуски.")

    markers = {0: "o", 1: "x", 4: "s", 5: "^"}
    for target, ymax, filename in (("95", 100, "04_target95.png"), ("99", 5, "05_target99.png")):
        fig, ax = axis(f"Досягли {target}% OPT, % запусків")
        for cell in summary["cells"]:
            profile = cell["profile"]
            target_cell = cell["targets"][target]
            curve = target_cell["curve"]
            y = [100 * point["fraction"] for point in curve]
            a.require(max(y) <= ymax + 1e-10, "target exceeds declared vertical scale")
            ax.step([point["q"] for point in curve], y, where="post", linewidth=1.8, color=COLORS[profile],
                    linestyle="--" if target_cell["attained"] == 0 else "-",
                    label=f"{NAMES[profile]}: {target_cell['attained']}/900")
            ax.plot([5000], [y[-1]], marker=markers[profile], markersize=5, color=COLORS[profile], clip_on=False)
        ax.set_ylim(0, ymax)
        ax.legend(fontsize=9, loc="upper left")
        save(fig, ax, filename, f"Частка досягнення {target}% OPT за кількістю нових оцінювань. По 900 запусків на варіант, невдачі залишено у знаменнику; сімейства мають рівну вагу. Вертикальна шкала 0–{ymax}%.")

    fig, ax, _ = quality_figure(summary["cells"])
    save(fig, ax, "06_joint_quality.png", "Середнє кінцеве відставання чотирьох варіантів. Коротший стовпчик означає кращу якість; по 900 запусків. Це описове зіставлення.")
    return receipt
