"""CI-only aggregation of exact secondary artifacts; no new search is executed."""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import shutil
import tempfile

from ..ga_study.transport import api_get, download_zip, extract_bundle, verify_artifact_identity
from .analysis import CONTRAST_IDS, MUTATIONS, CROSSOVERS, POPULATIONS
from .contract import (PROTOCOL_ID, REPOSITORY, SOURCE_RUN, SOURCE_SHA, authenticate,
    ROOT, file_identity, output_directory, read_json, require, sha256_bytes, write_json, write_file_manifest)

LABELS = {"mutation_3_over_1": "Мутація 3/n проти 1/n",
    "crossover_09_over_0": "Схрещування 0,9 проти 0",
    "population_50_over_10": "Популяція 50 проти 10",
    "mutation_crossover_interaction": "Взаємодія мутації та схрещування"}
CORRELATION_LABELS = {"random_invalid_gap": "Випадковий початок: недопустимі запити та відставання",
    "random_duplicate_gap": "Випадковий початок: дублікати та відставання",
    "local_invalid_escape": "Локальний початок: недопустимі запити та вихід",
    "local_duplicate_escape": "Локальний початок: дублікати та вихід"}


def verify_identity(record, identity):
    for field in ("protocol_id", "protocol_sha256", "implementation_commit_sha",
                  "implementation_fingerprint", "run_id", "run_attempt", "source_run_id",
                  "source_implementation_commit_sha", "source_summaries_sha256", "registry_sha256"):
        require(record.get(field) == identity[field], "mixed secondary provenance: " + field)
    require(record.get("new_search_runs") == 0 and record.get("new_exact_solver_runs") == 0,
            "unauthorized new computations")


def report_status(analysis, trace, tests, identity):
    verify_identity(analysis, identity)
    verify_identity(trace["provenance"], identity)
    verify_identity(tests["provenance"], identity)
    require(tests.get("schema_version") == "ga-knapsack-secondary-tests-v1" and
            tests.get("passed") is True and tests.get("outcome") == "success" and
            type(tests.get("test_count")) is int and tests["test_count"] > 0,
            "secondary fixture evidence missing or failed")
    require(analysis.get("status") == "COMPLETE_COMPACT_ANALYSIS" and analysis.get("exploratory") is True
            and analysis["counts"]["runs"] == 35640 and len(analysis["loo"]) == 10
            and len(analysis["correlations"]) == 4 and len(analysis["configuration_summaries"]) == 54,
            "incomplete compact secondary analysis")
    require(trace.get("protocol_id") == PROTOCOL_ID and trace.get("expected_case_count") == 6,
            "incorrect trace scope")
    require(trace["source"]["artifact_id"] == 11557059267 and
            trace["source"]["run_id"] == SOURCE_RUN and
            trace["source"]["implementation_commit_sha"] == SOURCE_SHA,
            "unapproved historical trace source")
    if trace.get("status") == "PARTIAL_TRACE_AUDIT":
        require(trace.get("fault") and trace["fault"].get("replacement_selected") is False,
                "partial trace audit must preserve failure and forbid replacement")
        return "PARTIAL_TRACE_AUDIT"
    require(trace.get("status") == "COMPLETE_TRACE_AUDIT" and trace.get("verified_case_count") == 6
            and len(trace["cases"]) == 6 and all(row.get("verified") is True for row in trace["cases"])
            and trace.get("retained_traces"), "incomplete full trace audit")
    identities = {(row["identity"]["start_profile"], row["identity"]["configuration_id"])
                  for row in trace["cases"]}
    require(identities == {(start, config) for start in ("random", "local")
            for config in ("m0p5-c0p9-n30", "m1-c0p9-n30", "m3-c0p9-n30")}
            and all(row["identity"]["instance_id"] == "UC-s000" and
                    row["identity"]["repeat_seed"] == 51001 for row in trace["cases"]),
            "missing, duplicate or substituted historical case")
    return "COMPLETE_SECONDARY_REVIEW"


def number(value, digits=4, multiplier=1):
    return "не визначено" if value is None else f"{value * multiplier:.{digits}f}".replace(".", ",")


def interval(row):
    if row.get("lower") is None or row.get("upper") is None:
        return "не визначено"
    return f"[{number(row['lower'], multiplier=100)}; {number(row['upper'], multiplier=100)}]"


def population_points(trajectory):
    # No fictional continuation of population metrics through a terminal prefix.
    return [row for row in trajectory if row["generation"] == 0 or row["complete"]]


def figures(analysis, trace, output):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 9,
        "axes.spines.top": False, "axes.spines.right": False, "figure.facecolor": "white"})
    directory = output / "figures"
    directory.mkdir()
    names = []
    fig, axes = plt.subplots(4, 3, figsize=(14, 11), layout="constrained")
    for i, contrast in enumerate(CONTRAST_IDS):
        primary = next(row for row in analysis["primary_contrasts"] if row["contrast_id"] == contrast)
        for ax in axes[i]:
            ax.axvline(0, color=".6", linestyle=":")
            ax.set_xlabel("Різниця частот виходу, в.п.")
        ax = axes[i, 0]
        point = primary["estimate"] * 100
        ax.plot([primary["lower"] * 100, primary["upper"] * 100], [0, 0], color="black")
        ax.plot(point, 0, "ko")
        ax.set_yticks([])
        ax.set_title(LABELS[contrast] + "\nПервинний інтервал 98,75 %")
        ax = axes[i, 1]
        families = analysis["family_contrasts"]
        ax.scatter([row["contrasts"][contrast] * 100 for row in families], range(10), color="black", s=20)
        ax.set_yticks(range(10), [row["family"] for row in families])
        ax.set_title("Ефекти окремих сімейств")
        ax = axes[i, 2]
        for j, row in enumerate(analysis["loo"]):
            item = next(v for v in row["statistics"]["intervals"] if v["contrast_id"] == contrast)
            ax.plot(item["estimate"] * 100, j, "ko", markersize=3)
            if item.get("lower") is not None:
                ax.plot([item["lower"] * 100, item["upper"] * 100], [j, j], color=".45", linewidth=1)
        ax.set_yticks(range(10), ["без " + row["omitted_family"] for row in analysis["loo"]])
        ax.set_title("Діагностика без одного сімейства\nНе нова первинна перевірка")
    path = directory / "01_effects_stability.png"
    fig.savefig(path, dpi=170)
    plt.close(fig)
    names.append(path)
    fig, axes = plt.subplots(1, 2, figsize=(12, 8), layout="constrained")
    labels = [f"мутація {m:g}/n; схрещування {c:g}".replace(".", ",")
              for m in MUTATIONS for c in CROSSOVERS]
    for ax, profile, metric, title in (
        (axes[0], "local", "escape_rate_equal_family", "Локальний початок: частота виходу, %"),
        (axes[1], "random", "mean_final_relative_gap_equal_family", "Випадковий початок: відставання, %")):
        grid = np.asarray([[next(row[metric] * 100 for row in analysis["configuration_summaries"]
            if row["start_profile"] == profile and row["mutation_numerator"] == m
            and row["crossover_probability"] == c and row["population_size"] == n)
            for n in POPULATIONS] for m in MUTATIONS for c in CROSSOVERS])
        heat = ax.imshow(grid, cmap="Greys", aspect="auto", vmin=0)
        ax.set_yticks(range(9), labels)
        ax.set_xticks(range(3), [str(n) for n in POPULATIONS])
        ax.set_xlabel("Розмір популяції")
        ax.set_title(title)
        threshold = float(grid.max()) / 2
        for y in range(9):
            for x in range(3):
                ax.text(x, y, number(grid[y, x], 3), ha="center", va="center",
                        color="white" if grid[y, x] > threshold else "black")
        fig.colorbar(heat, ax=ax, shrink=.6)
    path = directory / "02_parameter_dependencies.png"
    fig.savefig(path, dpi=170)
    plt.close(fig)
    names.append(path)
    if trace["status"] == "COMPLETE_TRACE_AUDIT":
        fig, axes = plt.subplots(2, 3, figsize=(14, 8), layout="constrained")
        for y, profile in enumerate(("random", "local")):
            for case in trace["cases"]:
                if case["identity"]["start_profile"] != profile:
                    continue
                config = case["identity"]["configuration_id"]
                mutation = config.split("-")[0][1:].replace("p", ",")
                style = {"0,5": ":", "1": "-", "3": "--"}[mutation]
                for x, metric in enumerate(("best_profit", "mean_feasible_profit", "diversity")):
                    rows = case["trajectory"] if x == 0 else population_points(case["trajectory"])
                    axes[y, x].plot([row["last_request"] for row in rows],
                        [row[metric] for row in rows], color="black", linestyle=style, label=f"мутація {mutation}/n")
            for x, title in enumerate(("Рекорд на межах поколінь і завершального префікса", "Середня цінність допустимої популяції", "Різноманітність: частка унікальних масок")):
                axes[y, x].set_title(("Випадковий" if y == 0 else "Локальний") + " початок\n" + title)
                axes[y, x].set_xlabel("Логічні оцінювання")
                axes[y, x].legend(fontsize=8)
        fig.suptitle("UC-s000, seed 51001: шість перевірених історичних траєкторій")
        path = directory / "03_verified_trajectories.png"
        fig.savefig(path, dpi=170)
        plt.close(fig)
        names.append(path)
    return [{"path": path.relative_to(output).as_posix(), **file_identity(path),
             "scientific_generation": "GitHub Actions only"} for path in names]


def markdown(result):
    analysis, trace = result["analysis"], result["trace_audit"]
    lines = ["# Науковий розбір результатів генетичного алгоритму для задачі рюкзака", "",
        "## Дані та перевірка", "",
        "Завершена серія містить 35 640 запусків, 27 конфігурацій і 30 задач. "
        "Незалежно перевірено компактні підсумки й збережені найкращі маски. "
        "Нових запусків ГА або точних розв’язувачів не виконано.", "",
        f"Статус повного аудиту журналів: {trace['status']}; перевірено {trace['verified_case_count']}/6.", "",
        "## Незмінні первинні результати", "",
        "Таблиця 1. Зареєстровані контрасти частоти виходу", "",
        "| Контраст | Ефект, в.п. | Інтервал 98,75 %, в.п. |", "|---|---:|---|"]
    for row in analysis["primary_contrasts"]:
        lines.append(f"| {LABELS[row['contrast_id']]} | {number(row['estimate'], multiplier=100)} | {interval(row)} |")
    lines += ["", "Первинні оцінки й інтервали відновлено без зміни історичних критеріїв. "
        "Додатний популяційний ефект є малим; невизначений напрям інших ефектів не доводить їх рівності.", "",
        "## Стійкість до вилучення одного сімейства", "",
        "Таблиця 2. Діагностика популяційного контрасту", "",
        "| Вилучене сімейство | Ефект, в.п. | Діагностичний інтервал 98,75 %, в.п. |",
        "|---|---:|---|"]
    for case in analysis["loo"]:
        row = next(v for v in case["statistics"]["intervals"] if v["contrast_id"] == "population_50_over_10")
        lines.append(f"| {case['omitted_family']} | {number(row['estimate'], multiplier=100)} | {interval(row)} |")
    lines += ["", "*Це вторинна діагностика після перегляду результатів. "
        "Вона не замінює первинного критерію й не є підставою вибирати сприятливі сімейства.*", "",
        "## Описові кореляції", "", "Таблиця 3. Кореляції Спірмена між десятьма сімейними середніми", "",
        "| Зв’язок | ρ | Статус |", "|---|---:|---|"]
    for row in analysis["correlations"]:
        lines.append(f"| {CORRELATION_LABELS[row['id']]} | {number(row['rho'])} | {row['status']} |")
    lines += ["", "*Кореляції не встановлюють причинності; p-значення не обчислювалися. "
        "Сталий ряд має невизначену кореляцію, а не нульову. Серії адаптивного λ на рюкзаку немає.*", "",
        "## Абсолютні кількості й сімейне усереднення", ""]
    counts = analysis["local_all_configurations"]
    lines += [f"Локальна серія: {counts['escape_events']} виходів із {counts['run_count']} запусків; "
        f"невиходів {counts['censored_nonevents']}. Проста частка становить "
        f"{number(counts['escape_rate_raw'], multiplier=100)} %, сімейно-зважена "
        f"{number(counts['escape_rate_equal_family'], multiplier=100)} %. "
        "Різниця виникає через неоднакове число допущених задач у сімействах.", "",
        "## Межі внеску та професорський вердикт", "",
        "Робота має відтворюване експериментальне ядро та процедуру незалежної сертифікації "
        "підготовлених локальних максимумів. Емпіричні висновки обмежені заданими задачами, "
        "центрами й лімітом оцінювань. Відомі оператори, точні методи та BCa не є новим алгоритмом.", "",
        "*Перевага адаптивного λ на рюкзаку й адаптивна наукова новизна не встановлені. "
        "Невихід не доводить глобальної оптимальності. Технічна правильність не дорівнює "
        "числовому відтворенню статті або науковій перевазі.*", "", "## Походження", "",
        f"Історична серія: https://github.com/{REPOSITORY}/actions/runs/{SOURCE_RUN}", "",
        f"Вторинний розбір: https://github.com/{REPOSITORY}/actions/runs/{result['provenance']['run_id']}", "",
        "Повні вторинні оцінки, чотири кореляції, десять аналізів стійкості й реєстр контрольних сум "
        "наведено в report-data.json, analysis.json та sources.json."]
    return "\n".join(lines) + "\n"


def aggregate(expected_sha, output):
    identity = authenticate(expected_sha)
    output = output_directory(output)
    run, attempt = identity["run_id"], identity["run_attempt"]
    all_metadata, page = [], 1
    while True:
        batch = api_get(f"https://api.github.com/repos/{REPOSITORY}/actions/runs/{run}/artifacts?per_page=100&page={page}")["artifacts"]
        all_metadata.extend(batch)
        if len(batch) < 100:
            break
        page += 1
    write_json(output / "artifact-api-metadata.json", {"run_id": run, "run_attempt": attempt, "artifacts": all_metadata})
    ledger = []
    with tempfile.TemporaryDirectory(prefix="secondary-aggregate-", dir=os.environ.get("RUNNER_TEMP")) as temporary:
        bundles = {}
        for kind in ("budget", "tests", "compact", "trace"):
            name = f"knapsack-review-{kind}-{run}-{attempt}"
            matches = [row for row in all_metadata if row["name"] == name]
            require(len(matches) == 1, "missing or duplicate current artifact: " + name)
            metadata = matches[0]
            verify_artifact_identity(metadata, artifact_id=metadata["id"], source_run_id=run, source_sha=expected_sha)
            raw = download_zip(metadata)
            directory = extract_bundle(raw, Path(temporary) / kind)
            ledger.append({"kind": kind, "artifact_id": metadata["id"], "artifact_name": name,
                "run_id": run, "run_attempt": attempt, "implementation_commit_sha": expected_sha,
                "zip_sha256": sha256_bytes(raw), "zip_bytes": len(raw),
                "internal_manifest_sha256": file_identity(directory / "file_manifest.json")["sha256"]})
            bundles[kind] = directory
        require(len({row["artifact_id"] for row in ledger}) == 4, "duplicate artifact IDs")
        budget = read_json(bundles["budget"] / "budget-preflight.json")
        require(budget["protocol_id"] == PROTOCOL_ID and budget["cumulative_ceiling_minutes"] == 60
                and budget["previous_rounded_runner_minutes"] + budget["reserved_current_minutes"] <= 60,
                "budget evidence invalid")
        analysis = read_json(bundles["compact"] / "analysis.json")
        trace = read_json(bundles["trace"] / "trace-audit.json")
        tests = read_json(bundles["tests"] / "tests.json")
        status = report_status(analysis, trace, tests, identity)
        for kind, filename in (("budget", "budget-preflight.json"), ("tests", "tests.json"),
                               ("compact", "analysis.json"), ("trace", "trace-audit.json")):
            shutil.copyfile(bundles[kind] / filename, output / filename)
        shutil.copyfile(bundles["tests"] / "fixtures.txt", output / "fixtures.txt")
        if trace["retained_traces"]:
            retained = trace["retained_traces"]
            require(retained["path"] == "retained-traces.tar.gz" and
                    file_identity(bundles["trace"] / retained["path"]) ==
                    {"bytes": retained["bytes"], "sha256": retained["sha256"]}, "retained trace archive differs")
            shutil.copyfile(bundles["trace"] / retained["path"], output / retained["path"])
    sources = {"schema_version": "ga-knapsack-secondary-sources-v1", "provenance": identity, "sources": ledger}
    write_json(output / "sources.json", sources)
    result = {"schema_version": "ga-knapsack-secondary-report-v1", "protocol_id": PROTOCOL_ID,
        "status": status, "provenance": identity, "analysis": analysis, "trace_audit": trace,
        "fixture_tests": tests, "budget": budget, "sources": sources,
        "primary_results_changed": False, "new_search_runs": 0, "new_exact_solver_runs": 0}
    result["figures"] = figures(analysis, trace, output)
    write_json(output / "report-data.json", result)
    (output / "RESULTS_UK.md").write_text(markdown(result), encoding="utf-8")
    write_file_manifest(output)
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--expected-sha", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    path = Path(args.output).resolve()
    fresh_external = not path.is_relative_to(ROOT) and (not path.exists() or
                     (path.is_dir() and not any(path.iterdir())))
    try:
        result = aggregate(args.expected_sha, args.output)
    except Exception as error:
        # Preserve failure; never replace missing/mixed scientific sources.
        if os.environ.get("GITHUB_ACTIONS") == "true" and fresh_external:
            write_json(path / "aggregation-failure.json", {"status": "INCOMPLETE_SECONDARY_REVIEW",
                "protocol_id": PROTOCOL_ID, "expected_sha": args.expected_sha,
                "error_type": type(error).__name__, "error": str(error), "replacement_selected": False})
            write_file_manifest(path)
        raise
    print(result["status"], "; source traces", result["trace_audit"]["verified_case_count"], "/6")


if __name__ == "__main__":
    main()
