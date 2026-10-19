"""Title-free CI figures: retained development summaries and verified probes.

No new search, significance test, or outcome-based example selection occurs.
Numbered questions/answers belong in the document captions, not image titles.
"""
import hashlib
import json
import os
from pathlib import Path
from statistics import fmean

METHODS = ("classical", "adaptive_mutation", "adaptive_crossover", "unbalanced_gap", "balanced_gap")
LABELS = {"classical": "Класичний ГА", "adaptive_mutation": "Адаптивна мутація",
          "adaptive_crossover": "Адаптивне схрещування", "unbalanced_gap": "Архів без балансування",
          "balanced_gap": "Балансований архів"}
COLORS = dict(zip(METHODS, ("#222222", "#0072B2", "#D55E00", "#009E73", "#CC79A7"), strict=True))
STYLES = dict(zip(METHODS, ("-", "--", "-.", ":", (0, (5, 1, 1, 1))), strict=True))


def _require(ok, message):
    if not ok:
        raise ValueError(message)


def _plotting(output):
    _require(os.environ.get("GITHUB_ACTIONS") == "true" and
             os.environ.get("GITHUB_REPOSITORY") == "ChepaMaksym/GA-article-test" and
             os.environ.get("GITHUB_REF") == "refs/heads/research/masters-ga-diversity-crossover",
             "Scientific figures are generated only in the registered CI environment")
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 11,
                         "axes.spines.top": False, "axes.spines.right": False})
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    return plt, output


def _save(plt, figure, path):
    _require(not path.exists(), "Refuse to overwrite a scientific figure")
    _require(not figure._suptitle or not figure._suptitle.get_text(), "No figure title is allowed")
    _require(all(not ax.get_title() for ax in figure.axes), "No panel title is allowed")
    figure.savefig(path, dpi=180)
    plt.close(figure)
    return path.name


def render_historical_fixed(output):
    """Render unchanged computed cells; do not recompute grid statistics."""
    plt, output = _plotting(output)
    root = Path(__file__).resolve().parents[3]
    basic = root / "studies/knapsack_parameters/basic_parameters"
    frozen = json.loads((basic / "inputs/frozen_winner.json").read_text(encoding="utf-8"))
    path = basic / "evidence/run-39012696900/ci-selected/analysis.json"
    _require(hashlib.sha256(path.read_bytes()).hexdigest() == frozen["analysis_sha256"],
             "Historical computed grid bytes changed")
    report = json.loads(path.read_text(encoding="utf-8"))
    configs = report["configurations"]
    _require(report["runs"] == 37500 and report["configuration_count"] == len(configs) == 125 and
             report["winner_id"] == frozen["configuration_id"], "Incomplete historical fixed grid")
    mutations, crossovers = (0, .005, .01, .03, .08), (0, .25, .5, .9, 1)
    lookup = {(row["p_m"], row["p_c"], row["population_size"]): row for row in configs}
    _require(len(lookup) == 125, "Duplicate fixed-grid cells")
    maximum = max(row["mean_gap"] * 100 for row in configs)
    figures = []
    for size in (10, 20, 30, 50, 100):
        values = [[lookup[(pm, pc, size)]["mean_gap"] * 100 for pc in crossovers] for pm in mutations]
        fig, ax = plt.subplots(figsize=(7.4, 5.4), layout="constrained")
        artist = ax.imshow(values, origin="lower", vmin=0, vmax=maximum, cmap="viridis_r", aspect="auto")
        ax.set_xticks(range(5), [f"{100*x:g}" for x in crossovers])
        ax.set_yticks(range(5), [f"{100*x:g}" for x in mutations])
        ax.set_xlabel(f"Імовірність схрещування, %\nПопуляція: {size} особин")
        ax.set_ylabel("Імовірність мутації біта, %")
        for row in range(5):
            for col in range(5):
                ax.text(col, row, f"{values[row][col]:.2f}".replace(".", ","),
                        ha="center", va="center", fontsize=10,
                        bbox={"facecolor": "white", "alpha": .8, "edgecolor": "none", "pad": 1.5})
        fig.colorbar(artist, ax=ax, label="Кінцеве відставання від оптимуму, %")
        figures.append(_save(plt, fig, output / f"fixed_population_{size}.png"))
    fig, axes = plt.subplots(1, 3, figsize=(14.5, 4.3), layout="constrained")
    for ax, parameter in zip(axes, ("p_m", "p_c", "population_size"), strict=True):
        fixed = {"p_m": .01, "p_c": .9, "population_size": 30}
        for curve in report["conditional_effects"]:
            if curve["varying_parameter"] != parameter:
                continue
            anchor = all(fixed[key] == value for key, value in curve["fixed_parameters"].items())
            multiple = 1 if parameter == "population_size" else 100
            ax.plot([point["level"] * multiple for point in curve["points"]],
                    [point["mean_gap"] * 100 for point in curve["points"]],
                    color="#222222" if anchor else "#999999", alpha=1 if anchor else .2,
                    linewidth=2 if anchor else .75, marker="o" if anchor else None,
                    label="Опорні інші параметри" if anchor else None)
        ax.set_xlabel({"p_m": "Мутація біта, %", "p_c": "Схрещування, %",
                       "population_size": "Популяція, особин"}[parameter])
        ax.set_ylabel("Кінцеве відставання, %")
        ax.grid(alpha=.25)
        ax.legend(fontsize=8)
    figures.append(_save(plt, fig, output / "fixed_parameter_effects.png"))
    fig, axes = plt.subplots(2, 1, figsize=(7.5, 6.5), layout="constrained")
    sizes = (10, 20, 30, 50, 100)
    anchor = [lookup[(.01, .9, size)] for size in sizes]
    axes[0].plot(sizes, [100*row["mean_initial_gap"] for row in anchor], "o--", color="#777777", label="Початковий рекорд")
    axes[0].plot(sizes, [100*row["mean_gap"] for row in anchor], "o-", color="#222222", label="Кінцевий рекорд")
    axes[0].set_ylabel("Відставання від оптимуму, %")
    axes[0].legend()
    axes[1].plot(sizes, [row["complete_generations"] for row in anchor], "o-", color="#222222")
    axes[1].set_ylabel("Повні покоління")
    for ax in axes:
        ax.set_xlabel("Популяція, особин")
        ax.grid(alpha=.25)
    figures.append(_save(plt, fig, output / "fixed_initial_final_and_generations.png"))
    return figures


def _trace(log):
    masks = list(log["initial_masks"]) + [row["mask"] for row in log["candidates"]]
    scores = list(log["initial_scores"]) + [{key: row[key] for key in ("weight", "profit", "feasible")}
                                           for row in log["candidates"]]
    def population(refs, query):
        chosen = [masks[ref] for ref in refs]
        values = [scores[ref]["profit"] for ref in refs if scores[ref]["feasible"]]
        mu, n = len(refs), log["problem"]["n"]
        differences = 0
        for bit in range(n):
            ones = sum(mask[bit] == "1" for mask in chosen)
            differences += ones * (mu-ones)
        return {"query": query, "mean": fmean(values) if values else None,
                "diversity": differences / (n*mu*(mu-1)/2) if mu > 1 else 0}
    best = max(row["profit"] for row in log["initial_scores"] if row["feasible"])
    records = [(0, best)]
    for row in log["candidates"]:
        if row["feasible"] and row["profit"] > best:
            best = row["profit"]
        records.append((row["call"], best))
    populations = [population(list(range(len(log["initial_masks"]))), 0)]
    populations += [population(event["population_after"], event["end_call"])
                    for event in log["generations"] if event["complete"]]
    return records, populations


def _compact_row(row):
    """Discard event/counter dictionaries before the next large journal is read."""
    log = row["log"]
    parameters = [{name: event.get(name, .9) for name in ("start_call", "p_m", "p_c")}
                  for event in log["generations"]]
    activity = []
    if row["method"] in ("unbalanced_gap", "balanced_gap"):
        by_generation = {}
        for candidate in log["candidates"]:
            by_generation.setdefault(candidate["generation"], []).append(candidate)
        for event in log["generations"]:
            plan, altered = event["plan"], 0
            candidates = by_generation[event["generation"]]
            for candidate in candidates:
                selection = candidate["selection_event"]
                if row["method"] == "balanced_gap" and not selection["singleton"]:
                    draws = selection["tournament_draws"]
                    first = draws[0]
                    for drawn in draws[1:]:
                        if plan["gaps"][drawn] > plan["gaps"][first]:
                            first = drawn
                    altered += first != selection["first_index"]
            # Both query and size describe the observed end-of-block state.
            # The unchanged archive_after of a terminal prefix is retained.
            activity.append({"query": event["end_call"], "size": len(event["archive_after"]),
                             "switches": 100*altered/len(candidates)})
    return _trace(log), parameters, activity


def render_probe(rows, output):
    """Descriptive fixed-example pictures only, after all ten independent replays."""
    plt, output = _plotting(output)
    expected = {(task, start, method) for task, start in (("UC-s000", "cloned"), ("SC-s005", "bank"))
                for method in METHODS}
    found, traces, parameters, archives = {}, {}, {}, {}
    # rows may be a streaming reader. Retain only compact plotting arrays, never
    # ten complete archive journals in memory at once.
    for row in rows:
        key = (row["task"], row["start"], row["method"])
        _require(key in expected and key not in found and row.get("verification_status") == "VERIFIED",
                 "Duplicate, unverified or unregistered plotted probe")
        found[key] = {name: row[name] for name in ("task", "start", "method", "optimum")}
        traces[key], parameters[key], activity = _compact_row(row)
        if activity:
            archives[key] = activity
        # Do not keep the previous generator row alive during next(), which
        # decodes the next journal before rebinding the loop variable.
        del row
    _require(len(found) == 10 and set(found) == expected,
             "All ten verified resource probes required for new trajectory pictures")
    figures = []
    fig, axes = plt.subplots(3, 2, figsize=(14, 10), layout="constrained", sharex="col", sharey="row")
    for column, (task, start) in enumerate((("UC-s000", "cloned"), ("SC-s005", "bank"))):
        for method in METHODS:
            row = found[(task, start, method)]
            records, population = traces[(task, start, method)]
            style = {"color": COLORS[method], "linestyle": STYLES[method], "label": LABELS[method]}
            axes[0, column].step([p[0] for p in records], [100*(row["optimum"]-p[1])/row["optimum"] for p in records],
                                 where="post", **style)
            axes[1, column].step([p["query"] for p in population],
                                 [100*p["mean"]/row["optimum"] if p["mean"] is not None else float("nan") for p in population],
                                 where="post", **style)
            axes[2, column].step([p["query"] for p in population], [100*p["diversity"] for p in population],
                                 where="post", **style)
        axes[0, column].set_ylabel("Відставання рекорду, %")
        axes[0, column].set_ylim(bottom=0)
        axes[1, column].set_ylabel("Середня допустима цінність, % OPT")
        axes[2, column].set_ylabel("Середня генетична відстань, %")
        axes[2, column].set_xlabel("Нові оцінювання\n" + task + ("; копії центра" if start == "cloned" else "; випадковий початок"))
        axes[0, column].legend(fontsize=8)
        for ax in axes[:, column]:
            ax.grid(alpha=.2)
            ax.set_xlim(0, 5000)
    figures.append(_save(plt, fig, output / "probe_search_dynamics.png"))
    fig, axes = plt.subplots(2, 2, figsize=(13, 7), layout="constrained", sharex="col", sharey="row")
    for column, (task, start) in enumerate((("UC-s000", "cloned"), ("SC-s005", "bank"))):
        for row_index, (parameter, active, label) in enumerate((("p_m", "adaptive_mutation", "Мутація біта, %"),
                                                              ("p_c", "adaptive_crossover", "Схрещування, %"))):
            for method in ("classical", active):
                events = parameters[(task, start, method)]
                x = [event["start_call"]-1 for event in events] + [5000]
                y = [100*event.get(parameter, .9) for event in events]
                y.append(y[-1])
                axes[row_index, column].step(x, y, where="post", color=COLORS[method],
                                             linestyle=STYLES[method], label=LABELS[method])
            axes[row_index, column].set_ylabel(label)
            axes[row_index, column].legend(fontsize=8)
            axes[row_index, column].grid(alpha=.2)
        axes[1, column].set_xlabel("Нові оцінювання\n" + task)
    figures.append(_save(plt, fig, output / "probe_parameter_changes.png"))
    fig, axes = plt.subplots(2, 2, figsize=(13, 7), layout="constrained", sharex="col", sharey="row")
    for column, (task, start) in enumerate((("UC-s000", "cloned"), ("SC-s005", "bank"))):
        for method in ("unbalanced_gap", "balanced_gap"):
            activity = archives[(task, start, method)]
            queries = [point["query"] for point in activity]
            sizes = [point["size"] for point in activity]
            switches = [point["switches"] for point in activity]
            style = {"color": COLORS[method], "linestyle": STYLES[method], "label": LABELS[method]}
            axes[0, column].step(queries, sizes, where="post", **style)
            axes[1, column].plot(queries, switches, **style)
        axes[0, column].set_ylabel("Набори в архіві, кількість")
        axes[1, column].set_ylabel("Зміна першого батька пам'яттю, %")
        axes[1, column].set_xlabel("Нові оцінювання\n" + task)
        for ax in axes[:, column]:
            ax.legend(fontsize=8)
            ax.grid(alpha=.2)
    figures.append(_save(plt, fig, output / "probe_archive_activity.png"))
    return figures
