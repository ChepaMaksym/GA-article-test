"""Aggregate independently replayed 100-item population comparison records.

The registered 900-run comparison is the only admissible input. No search,
initialisation, exact solver, resampling, or plotting is run on import. The
entry point is guarded by the separately approved main-stage resource limit.
"""
from bisect import bisect_right
from collections import defaultdict
import argparse
import csv
from fractions import Fraction
from hashlib import sha256
import json
import math
import os
from pathlib import Path, PurePosixPath
import re
from statistics import NormalDist

from .common import guard_main

HERE = Path(__file__).resolve().parent
POPS = (10, 20, 30)
TYPES = ("UC", "WC", "SC")
FAMILIES = tuple(f"s{number:03d}" for number in range(50, 60))
SEEDS = tuple(range(150001, 150011))
CHECKPOINTS = (5000, 10000, 20000, 50000, 100000)
TARGETS = (93, 95, 99)
TOTAL = 100000
CONTRASTS = ((10, "population10_minus_population20"),
             (30, "population30_minus_population20"))
FILES = {"journal.json.gz", "verification.json", "operator_bins.json",
         "observations.json.gz", "record.json"}


def require(condition, message):
    if not condition:
        raise ValueError("100-item population analysis: " + message)


def read(path):
    with Path(path).open("r", encoding="utf-8-sig") as stream:
        return json.load(stream)


def file_sha(path):
    digest = sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _execution_context():
    """Bind every compact shard to this exact authorized CI run and code seal."""
    commit = os.environ.get("GITHUB_SHA", "")
    run_id = os.environ.get("GITHUB_RUN_ID", "")
    require(re.fullmatch(r"[0-9a-f]{40}", commit) is not None, "missing or invalid CI commit")
    require(re.fullmatch(r"[0-9]+", run_id) is not None, "missing or invalid CI run ID")
    return {"workflow_commit": commit, "workflow_run_id": run_id,
            "code_manifest_sha256": file_sha(HERE / "source_manifest.json")}


def save_json(path, data):
    with Path(path).open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(data, stream, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")


def save_csv(path, rows):
    require(bool(rows), "empty CSV is not a result")
    with Path(path).open("x", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]), delimiter=";")
        writer.writeheader()
        writer.writerows(rows)


def gap(optimum, best):
    require(type(optimum) is int and type(best) is int and 0 <= best <= optimum and optimum > 0,
            "reference optimum or feasible record is invalid")
    return Fraction(100 * (optimum - best), optimum)


def mean(values):
    data = list(values)
    require(bool(data), "cannot average an empty group")
    return sum(data, Fraction()) / len(data)


def _fraction(value, name):
    require(type(value) in (int, float) and math.isfinite(value) and 0 <= value <= 1,
            "invalid " + name)
    return float(value)


def _finite(value, name):
    require(type(value) in (int, float) and math.isfinite(value) and value >= 0,
            "invalid " + name)
    return float(value)


def _sha256_string(value):
    return type(value) is str and re.fullmatch(r"[0-9a-f]{64}", value) is not None


def _safe_prefix(value):
    if type(value) is not str or "\\" in value or ":" in value:
        return False
    path = PurePosixPath(value)
    return bool(path.parts) and not path.is_absolute() and ".." not in path.parts


def validate_row(row, family, mu):
    require(type(row) is dict and row.get("family") == family and row.get("mu") == mu,
            "shard identity or population differs")
    label, seed = row.get("class_label"), row.get("seed")
    require(label in TYPES and type(seed) is int and seed in SEEDS, "task type or seed outside protocol")
    task = f"n00100-{label}-{family}"
    require(row.get("task") == task, "task name differs from family/type")
    expected_index = 3 + (int(family[1:]) - 50) * 3 + TYPES.index(label)
    require(row.get("task_index") == expected_index, "task index differs from source registry")
    optimum, best = row.get("optimum"), row.get("best")
    gap(optimum, best)
    events = row.get("events")
    require(type(events) is list and bool(events), "record history is missing")
    for event in events:
        require(type(event) is list and len(event) == 2 and type(event[0]) is int and type(event[1]) is int
                and 1 <= event[0] <= TOTAL and 0 <= event[1] <= optimum, "invalid record event")
    require(events[0] == [1, 0], "the known empty initial mask must be the first record")
    require(all(a[0] < b[0] and a[1] < b[1] for a, b in zip(events, events[1:])),
            "record events must strictly improve and have increasing evaluation numbers")
    require(events[-1][1] == best, "final record differs from record history")
    targets = row.get("targets")
    require(type(targets) is dict and set(targets) == {str(t) for t in TARGETS}, "target inventory differs")
    for target in TARGETS:
        expected = next((q for q, profit in events if 100 * profit >= target * optimum), None)
        value = targets[str(target)]
        require(type(value) is dict and value.get("first_total_evaluation") == expected
                and type(value.get("attained")) is bool and value["attained"] == (expected is not None)
                and value.get("restricted_evaluations") == (expected if expected is not None else TOTAL),
                "threshold hit or restricted evaluation count differs")
    points = row.get("checkpoints")
    require(type(points) is list and len(points) == len(CHECKPOINTS), "five checkpoints are required")
    by_q = {point.get("q"): point for point in points if type(point) is dict}
    require(set(by_q) == set(CHECKPOINTS) and len(by_q) == len(points), "checkpoint inventory differs")
    for q in CHECKPOINTS:
        point = by_q[q]
        expected_profit = next(profit for event_q, profit in reversed(events) if event_q <= q)
        require(type(point.get("q")) is int and type(point.get("record_profit")) is int
                and point["record_profit"] == expected_profit, "checkpoint record differs")
        require(type(point.get("completed_generations")) is int
                and point["completed_generations"] == (q - mu) // (mu - 1), "checkpoint generation count differs")
        metrics = point.get("population_metrics")
        require(type(metrics) is dict and metrics.get("population_size") == mu, "completed population size differs")
        _fraction(metrics.get("unique_fraction"), "unique population fraction")
        _fraction(metrics.get("feasible_fraction"), "feasible population fraction")
        require(_finite(metrics.get("mean_pairwise_hamming"), "mean Hamming distance") <= 100,
                "mean Hamming distance exceeds chromosome length")
    require(row.get("completed_generations") == (TOTAL - mu) // (mu - 1), "final generation count differs")
    duplicates = row.get("duplicates")
    require(type(duplicates) is int and 0 <= duplicates <= TOTAL - mu, "duplicate count invalid")
    hashes = row.get("artifact_hashes")
    require(type(hashes) is dict and set(hashes) == FILES and all(_sha256_string(s) for s in hashes.values()),
            "raw evidence hash inventory differs")
    require(_safe_prefix(row.get("artifact_prefix")) and row["artifact_prefix"] == f"{task}/seed-{seed}",
            "unsafe or mismatched raw evidence path")
    require(_sha256_string(row.get("bank_sha256")) and _sha256_string(row.get("certificate_sha256")),
            "initial-bank or exact-reference checksum missing")
    timing = row.get("timing")
    require(type(timing) is dict, "per-run cost accounting is required")
    for name in ("search_seconds", "log_write_seconds", "verification_seconds", "observations_seconds", "case_seconds", "artifact_bytes"):
        _finite(timing.get(name), name)
    require(timing["case_seconds"] >= sum(timing[name] for name in
            ("search_seconds", "log_write_seconds", "verification_seconds", "observations_seconds")),
            "full case time omits an accounted component")
    return row


def load_shards(root, protocol):
    root = Path(root)
    require(root.is_dir(), "compact shard root is absent")
    files = sorted(root.rglob("compact.json"))
    require(len(files) == 30, "exactly thirty compact shard manifests are required")
    expected = {(family, mu) for family in FAMILIES for mu in POPS}
    seen, records, provenance = set(), [], []
    prepared_manifest = None
    execution = _execution_context()
    for path in files:
        require(path.is_file() and not path.is_symlink() and path.resolve().is_relative_to(root.resolve()),
                "compact manifest path is unsafe")
        data = read(path)
        family, mu = data.get("family"), data.get("mu")
        require(data.get("schema") == "population-validation-100-main-shard-v1"
                and data.get("status") == "VERIFIED" and (family, mu) in expected,
                "invalid or incomplete verified shard")
        for field, expected_value in execution.items():
            require(data.get(field) == expected_value, "CI source or execution identity differs: " + field)
        require((family, mu) not in seen, "duplicate family/population shard")
        seen.add((family, mu))
        current_manifest = data.get("source_manifest_sha256")
        require(_sha256_string(current_manifest), "prepared-input manifest SHA-256 is invalid")
        if prepared_manifest is None:
            prepared_manifest = current_manifest
        require(current_manifest == prepared_manifest, "different paired bank manifests between shards")
        require(data.get("technical_input_manifest_sha256") == protocol["technical_input_manifest_sha256"],
                "certified technical-stage inputs differ")
        raw_name = data.get("raw_artifact_name")
        require(raw_name == f"population100-main-raw-{family}-mu{mu}-{execution['workflow_run_id']}",
                "raw artifact identity differs")
        rows = data.get("runs")
        require(type(rows) is list and len(rows) == 30, "shard must contain 30 verified runs")
        for row in rows:
            records.append(validate_row(row, family, mu))
        provenance.append({"family": family, "mu": mu, "compact_artifact_path": path.relative_to(root).as_posix(),
                           "compact_sha256": file_sha(path), "raw_artifact_name": raw_name,
                           "prepared_input_manifest_sha256": current_manifest,
                           "technical_input_manifest_sha256": data["technical_input_manifest_sha256"],
                           **execution})
    require(seen == expected and len(records) == 900, "complete 900-run shard grid is required")
    identities = [(r["task"], r["seed"], r["mu"]) for r in records]
    expected_ids = {(f"n00100-{kind}-{family}", seed, mu)
                    for family in FAMILIES for kind in TYPES for seed in SEEDS for mu in POPS}
    require(len(set(identities)) == len(expected_ids) == len(identities) and set(identities) == expected_ids,
            "duplicate or missing task/seed/population identity")
    for task in {r["task"] for r in records}:
        require(len({r["optimum"] for r in records if r["task"] == task}) == 1,
                "one task has inconsistent exact optima")
        require(len({r["certificate_sha256"] for r in records if r["task"] == task}) == 1,
                "one task has inconsistent exact-reference bytes")
        for seed in SEEDS:
            require(len({r["bank_sha256"] for r in records if r["task"] == task and r["seed"] == seed}) == 1,
                    "paired populations did not use the same initial bank")
    return records, provenance


def family_means(records, mu, getter):
    result = {}
    for family in FAMILIES:
        task_means = []
        for kind in TYPES:
            rows = [r for r in records if (r["family"], r["class_label"], r["mu"]) == (family, kind, mu)]
            require(len(rows) == len(SEEDS), "a task lacks ten matched repeats")
            task_means.append(mean(getter(row) for row in rows))
        result[family] = mean(task_means)
    return result


def bca(family_effects, *, replicates, seed, confidence):
    """Whole-family BCa with half-weight bias ties and linear quantiles.

    Numerical convention follows the project's frozen crossover-population
    analysis and uses common family draws for both registered contrasts.
    """
    require(replicates == 50000 and seed == 150031 and confidence == .975, "registered bootstrap parameters differ")
    return _bca_compute(family_effects, replicates=replicates, seed=seed, confidence=confidence)


def _bca_compute(family_effects, *, replicates, seed, confidence):
    """Numerical helper also accepts small synthetic CI-only test samples."""
    import numpy as np
    values = np.asarray(family_effects, dtype=float)
    require(values.shape == (10, 2) and np.isfinite(values).all(), "ten pairs of family effects required")
    require(type(replicates) is int and replicates >= 2 and type(seed) is int and 0 < confidence < 1,
            "invalid numerical bootstrap parameters")
    generator = np.random.Generator(np.random.PCG64(np.random.SeedSequence([seed])))
    indices = generator.integers(0, 10, size=(replicates, 10))
    distribution = values[indices].mean(axis=1)
    estimate = values.mean(axis=0)
    jackknife = (values.sum(axis=0) - values) / 9
    alpha, normal = 1 - confidence, NormalDist()
    intervals = []
    for col, (_, name) in enumerate(CONTRASTS):
        boot = distribution[:, col]
        current = {"contrast_id": name, "estimate_pp": float(estimate[col]), "lower_pp": None, "upper_pp": None,
                   "status": "DESCRIPTIVE_UNDEFINED", "reason": None, "positive_lower_bound": False,
                   "negative_upper_bound": False}
        differences = jackknife[:, col].mean() - jackknife[:, col]
        denominator = 6 * float(np.sum(differences ** 2)) ** 1.5
        fraction = (np.count_nonzero(boot < estimate[col]) + .5 * np.count_nonzero(boot == estimate[col])) / replicates
        if np.all(boot == boot[0]) or denominator == 0 or not math.isfinite(denominator) or not 0 < fraction < 1:
            current["reason"] = "degenerate_or_undefined_BCa"
        else:
            acceleration = float(np.sum(differences ** 3)) / denominator
            bias = normal.inv_cdf(float(fraction))
            probabilities = []
            for tail in (alpha / 2, 1 - alpha / 2):
                term = bias + normal.inv_cdf(tail)
                divisor = 1 - acceleration * term
                probabilities.append(normal.cdf(bias + term / divisor) if divisor else math.nan)
            if not all(math.isfinite(p) and 0 < p < 1 for p in probabilities) or probabilities[0] >= probabilities[1]:
                current["reason"] = "invalid_adjusted_quantiles"
            else:
                low, high = map(float, np.quantile(boot, probabilities, method="linear"))
                if not math.isfinite(low + high) or low >= high:
                    current["reason"] = "degenerate_or_reversed_interval"
                else:
                    current.update(status="NOMINAL_BCA", lower_pp=low, upper_pp=high,
                                   positive_lower_bound=low > 0, negative_upper_bound=high < 0,
                                   bias_correction=bias, acceleration=acceleration,
                                   adjusted_quantiles=probabilities)
        intervals.append(current)
    return {"method": "BCa", "family_count": 10, "replicates": replicates, "seed": seed,
            "confidence_each": confidence, "nominal_joint_confidence": 1 - 2 * (1 - confidence),
            "resampling_unit": "whole_family", "bias_ties": "half_weight", "quantile_method": "linear",
            "resample_index_sha256": sha256(indices.astype("<i8", copy=False).tobytes()).hexdigest(),
            "intervals": intervals}


def summarize(records):
    family_gaps = {mu: family_means(records, mu, lambda r: gap(r["optimum"], r["best"])) for mu in POPS}
    family_rows, loo_rows, vectors = [], [], []
    for family in FAMILIES:
        effects = [family_gaps[control][family] - family_gaps[20][family] for control, _ in CONTRASTS]
        family_rows.append({"family": family, "gap_mu10_percent": float(family_gaps[10][family]),
                            "gap_mu20_percent": float(family_gaps[20][family]),
                            "gap_mu30_percent": float(family_gaps[30][family]),
                            **{name + "_pp": float(value) for (_, name), value in zip(CONTRASTS, effects)}})
        vectors.append([float(value) for value in effects])
        loo_rows.append({"excluded_family": family,
                         **{name + "_pp": float(mean(family_gaps[control][f] - family_gaps[20][f]
                                                     for f in FAMILIES if f != family))
                            for control, name in CONTRASTS}})
    contrasts = bca(vectors, replicates=50000, seed=150031, confidence=.975)
    profile_rows, checkpoint_rows, cost_rows = [], [], []
    for mu in POPS:
        rows = [row for row in records if row["mu"] == mu]
        require(len(rows) == 300, "each population must have 300 runs")
        summary = {"mu": mu, "runs": len(rows), "mean_final_gap_percent": float(mean(family_gaps[mu].values())),
                   "optimum_count": sum(row["best"] == row["optimum"] for row in rows),
                   "nonoptimum_count": sum(row["best"] < row["optimum"] for row in rows)}
        for target in TARGETS:
            hits = sum(row["targets"][str(target)]["attained"] for row in rows)
            summary[f"attained_{target}"] = hits
            summary[f"not_attained_{target}"] = len(rows) - hits
            summary[f"restricted_mean_{target}"] = float(mean(family_means(
                rows, mu, lambda r, t=target: r["targets"][str(t)]["restricted_evaluations"]).values()))
        profile_rows.append(summary)
        for q in CHECKPOINTS:
            def point(row):
                return next(value for value in row["checkpoints"] if value["q"] == q)
            family_checkpoint = family_means(rows, mu, lambda r: gap(r["optimum"], point(r)["record_profit"]))
            def metric(name):
                return sum(point(r)["population_metrics"][name] for r in rows) / len(rows)
            checkpoint_rows.append({"mu": mu, "total_evaluations": q, "runs": len(rows),
                                    "mean_gap_percent": float(mean(family_checkpoint.values())),
                                    "mean_unique_percent": 100 * metric("unique_fraction"),
                                    "mean_feasible_percent": 100 * metric("feasible_fraction"),
                                    "mean_pairwise_hamming_bits": metric("mean_pairwise_hamming"),
                                    "mean_completed_generations": sum(point(r)["completed_generations"] for r in rows) / len(rows)})
        costs = {name: sum(r["timing"][name] for r in rows) for name in
                 ("search_seconds", "log_write_seconds", "verification_seconds", "observations_seconds", "case_seconds", "artifact_bytes")}
        cost_rows.append({"mu": mu, "runs": len(rows), **costs})
    return profile_rows, checkpoint_rows, family_rows, loo_rows, cost_rows, contrasts


def plot(records, checkpoints, family_rows, destination):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    colors = {10: "#1869aa", 20: "#c65422", 30: "#19864c"}
    styles = {10: "-", 20: "--", 30: ":"}
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 11, "axes.spines.top": False,
                         "axes.spines.right": False, "savefig.bbox": "tight"})
    names = []

    def finish(fig, name):
        fig.savefig(destination / (name + ".png"), dpi=200)
        fig.savefig(destination / (name + ".svg"))
        plt.close(fig)
        names.append(name)

    if any(row["mean_gap_percent"] != 0 for row in checkpoints):
        fig, ax = plt.subplots(figsize=(9, 4.7), layout="constrained")
        for mu in POPS:
            values = [next(row["mean_gap_percent"] for row in checkpoints
                           if row["mu"] == mu and row["total_evaluations"] == q) for q in CHECKPOINTS]
            ax.plot(CHECKPOINTS, values, marker="o", color=colors[mu], linestyle=styles[mu], label=f"Популяція {mu}")
        ax.set(xlim=(0, TOTAL), ylim=(0, None), xlabel="Загальна кількість оцінювань",
               ylabel="Середнє відставання від OPT, %")
        ax.set_xticks([0, 20000, 40000, 60000, 80000, 100000], ["0", "20 000", "40 000", "60 000", "80 000", "100 000"])
        ax.legend(); ax.grid(alpha=.23)
        finish(fig, "quality-checkpoints")

    for target in TARGETS:
        hit_lists = {mu: sorted(row["targets"][str(target)]["first_total_evaluation"]
                                for row in records if row["mu"] == mu and row["targets"][str(target)]["attained"])
                     for mu in POPS}
        all_hits = [hit for values in hit_lists.values() for hit in values]
        if not all_hits:
            continue
        latest_hit = max(all_hits)
        zoom_end = min(TOTAL, max(5000, int(math.ceil(latest_hit * 1.05 / 5000)) * 5000))
        axes_count = 2 if zoom_end < TOTAL else 1
        fig, axes = plt.subplots(1, axes_count, figsize=(11 if axes_count == 2 else 8.5, 4.3),
                                 squeeze=False, layout="constrained")
        ends = (zoom_end, TOTAL) if axes_count == 2 else (TOTAL,)
        for ax, end in zip(axes.flat, ends):
            for mu in POPS:
                hits = hit_lists[mu]
                xs = sorted({0, end, *(q for q in hits if q <= end)})
                ys = [100 * bisect_right(hits, q) / 300 for q in xs]
                ax.step(xs, ys, where="post", color=colors[mu], linestyle=styles[mu], label=f"Популяція {mu}")
            ax.set(xlim=(0, end), ylim=(0, 100), xlabel="Загальна кількість оцінювань",
                   ylabel=f"Досягли {target}% OPT, % запусків")
            ax.legend(loc="lower right", fontsize=8)
            ax.grid(alpha=.22)
        finish(fig, f"attainment-{target}")

    effects = [[row[name + "_pp"] for _, name in CONTRASTS] for row in family_rows]
    if any(value != 0 for pair in effects for value in pair):
        fig, ax = plt.subplots(figsize=(8.5, 5.0), layout="constrained")
        y = list(range(len(FAMILIES)))
        ax.scatter([pair[0] for pair in effects], [v - .13 for v in y], color="#1869aa", marker="o", label="10 мінус 20")
        ax.scatter([pair[1] for pair in effects], [v + .13 for v in y], color="#c65422", marker="s", label="30 мінус 20")
        ax.axvline(0, color="#444444", linewidth=1)
        ax.set_yticks(y, FAMILIES)
        ax.invert_yaxis()
        ax.set_xlabel("Відставання контролю мінус відставання популяції 20, в.п.")
        ax.set_ylabel("Сімейство задач")
        ax.legend(); ax.grid(axis="x", alpha=.22)
        finish(fig, "family-effects")

    for name, ylabel, limit in (("mean_unique_percent", "Унікальні хромосоми, %", (0, 100)),
                                ("mean_feasible_percent", "Допустимі особини, %", (0, 100)),
                                ("mean_pairwise_hamming_bits", "Середня відстань Геммінга, бітів", (0, 100))):
        values = [row[name] for row in checkpoints]
        if max(values) == min(values):
            continue
        fig, ax = plt.subplots(figsize=(9, 4.2), layout="constrained")
        for mu in POPS:
            current = [next(row[name] for row in checkpoints if row["mu"] == mu
                            and row["total_evaluations"] == q) for q in CHECKPOINTS]
            ax.plot(CHECKPOINTS, current, marker="o", color=colors[mu], linestyle=styles[mu], label=f"Популяція {mu}")
        ax.set(xlim=(0, TOTAL), ylim=limit, xlabel="Загальна кількість оцінювань", ylabel=ylabel)
        ax.set_xticks([0, 20000, 40000, 60000, 80000, 100000], ["0", "20 000", "40 000", "60 000", "80 000", "100 000"])
        ax.legend(); ax.grid(alpha=.23)
        finish(fig, name)
    return names


def number(value, decimals=3):
    return f"{value:.{decimals}f}".replace(".", ",")


def markdown_table(headers, rows):
    return "\n".join(["| " + " | ".join(headers) + " |", "| " + " | ".join("---" for _ in headers) + " |"] +
                     ["| " + " | ".join(map(str, row)) + " |" for row in rows])


def write_report(destination, profiles, checkpoints, families, costs, contrasts, names):
    lines = ["# Початкова популяція для задачі рюкзака зі 100 предметами", "",
             "Мета: порівняти популяцію 20 з популяціями 10 і 30 на нових задачах зі 100 предметами. "
             "Кандидата 20 обрано за результатами для 500 предметів. Порівняння для 100 предметів "
             "перевіряє перенесення, а результати різних розмірностей не об’єднуються.", "",
             "Усі варіанти використовують схрещування 90%, мутацію 1%, відбір із двох особин "
             "та одну еліту. Кожний запуск містить 100 000 загальних оцінювань разом із початком. "
             "Для кожного варіанта виконано 300 запусків: 30 задач, десять повторень на задачу.", "",
             "Таблиця 1 - Кінцеве відставання та досягнення цілей", "",
             markdown_table(["Популяція", "Середнє відставання, %", "Оптимум", "93% OPT", "95% OPT", "99% OPT"],
                            [(r["mu"], number(r["mean_final_gap_percent"]), f'{r["optimum_count"]}/300',
                              f'{r["attained_93"]}/300', f'{r["attained_95"]}/300', f'{r["attained_99"]}/300')
                             for r in profiles]), "",
             "Усереднення відставання виконано за повтореннями, задачами сімейства та сімействами. "
             "Десять сімейств мають однакову вагу. Недосягнення цілей залишено у знаменнику.", "",
             "Таблиця 2 - Первинні порівняння кінцевого відставання", "",
             markdown_table(["Контроль мінус популяція 20", "Ефект, в.п.", "Нижня межа", "Верхня межа", "Стан"],
                            [("Популяція " + str(control), number(item["estimate_pp"], 4),
                              "невизначено" if item["lower_pp"] is None else number(item["lower_pp"], 4),
                              "невизначено" if item["upper_pp"] is None else number(item["upper_pp"], 4),
                              "номінальний BCa 97,5%" if item["status"] == "NOMINAL_BCA" else "описова оцінка")
                             for (control, _), item in zip(CONTRASTS, contrasts["intervals"])]), "",
             "Додатний ефект означає менше відставання популяції 20. Інтервали використовують 50 000 "
             "вибірок цілих сімейств і мають номінальний рівень 97,5% для кожного порівняння. "
             "Повторне вибирання десяти сімейств не збільшує їхню кількість і не гарантує фактичного покриття. "
             "Невизначений інтервал не є доказом рівності.", "",
             "Таблиця 3 - Сімейні ефекти, відсоткові пункти", "",
             markdown_table(["Сімейство", "10 мінус 20", "30 мінус 20"],
                            [(r["family"], number(r[CONTRASTS[0][1] + "_pp"], 4),
                              number(r[CONTRASTS[1][1] + "_pp"], 4)) for r in families]), "",
             "Ефекти без одного сімейства наведено в окремій таблиці як діагностику впливу сімейств. "
             "Діагностика не змінює первинних порівнянь.", "",
             "Таблиця 4 - Обмежена середня кількість оцінювань до цілі", "",
             markdown_table(["Популяція", "93% OPT", "95% OPT", "99% OPT"],
                            [(r["mu"], number(r["restricted_mean_93"], 1), number(r["restricted_mean_95"], 1),
                              number(r["restricted_mean_99"], 1)) for r in profiles]), "",
             "Недосягнення враховується як 100 000 оцінювань. Значення 93%, 95% і 99% OPT відповідають "
             "втратам не більше 7%, 5% та 1%; їхню практичну прийнятність для окремого застосування не встановлено.", "",
             "Таблиця 5 - Стан завершеної популяції після 100 000 оцінювань", "",
             markdown_table(["Популяція", "Унікальні, %", "Допустимі, %", "Відстань Геммінга, бітів"],
                            [(mu, number(point["mean_unique_percent"], 1), number(point["mean_feasible_percent"], 1),
                              number(point["mean_pairwise_hamming_bits"], 1))
                             for mu in POPS for point in checkpoints
                             if point["mu"] == mu and point["total_evaluations"] == TOTAL]), "",
             "Для незавершеного покоління показано останню завершену популяцію; рекорд враховує всіх оцінених кандидатів.", "",
             "Таблиця 6 - Сумарний виміряний час окремих випадків, с", "",
             markdown_table(["Популяція", "Пошук", "Запис журналів", "Перевірка", "Спостереження", "Увесь випадок"],
                            [(r["mu"], number(r["search_seconds"], 1), number(r["log_write_seconds"], 1),
                              number(r["verification_seconds"], 1), number(r["observations_seconds"], 1),
                              number(r["case_seconds"], 1)) for r in costs]), "",
             "Суми часу випадків не дорівнюють тривалості паралельного виконання або облікованим runner-хвилинам. "
             "Повний час випадку включає додаткові записи й перевірку контрольних сум. "
             f"Сумарний обсяг файлів випадків становить {number(sum(r['artifact_bytes'] for r in costs) / 1024**3, 3)} GiB; "
             "розмір архівів і службових матеріалів обліковується окремо.", ""]
    titles = {"quality-checkpoints": "Середнє відставання в контрольних точках",
              "family-effects": "Різниця кінцевого відставання за сімействами",
              "mean_unique_percent": "Частка унікальних хромосом",
              "mean_feasible_percent": "Частка допустимих особин",
              "mean_pairwise_hamming_bits": "Середня попарна відстань Геммінга"}
    for target in TARGETS:
        titles[f"attainment-{target}"] = f"Досягнення {target}% OPT"
    for index, name in enumerate(names, 1):
        caption = f"Рисунок {index} - {titles[name]}"
        lines.extend([f"![{caption}](figures/{name}.png)", "", caption, ""])
        if name == "quality-checkpoints":
            lines.extend(["Лінії з’єднують середні значення в п’яти контрольних точках і не відтворюють повну траєкторію.", ""])
        elif name.startswith("attainment-"):
            lines.extend(["На кожній кривій 300 запусків. За наявності двох панелей ліва показує ранній відрізок, "
                          "права весь інтервал до 100 000 оцінювань. Лінії можуть збігатися.", ""])
    for target in TARGETS:
        if f"attainment-{target}" not in names:
            lines.extend([f"Ціль {target}% OPT не досягнута жодним запуском; числові дані наведено в таблицях 1 і 4.", ""])
    if "family-effects" not in names:
        lines.extend(["Усі сімейні ефекти дорівнюють нулю; числові дані наведено в таблиці 3.", ""])
    for interval in contrasts["intervals"]:
        control = 10 if interval["contrast_id"] == CONTRASTS[0][1] else 30
        if interval["status"] != "NOMINAL_BCA":
            wording = f"Для порівняння з популяцією {control} BCa-інтервал невизначений; повідомлено описову оцінку."
        elif interval["positive_lower_bound"]:
            wording = f"Для порівняння з популяцією {control} нижня номінальна межа ефекту додатна."
        elif interval["negative_upper_bound"]:
            wording = f"Для порівняння з популяцією {control} верхня номінальна межа ефекту від’ємна."
        else:
            wording = f"Для порівняння з популяцією {control} номінальний інтервал містить нуль; рівність не встановлено."
        lines.extend([wording, ""])
    lines.extend(["Результати стосуються визначених задач, операторів, контрольних конфігурацій і кількості оцінювань. "
                  "Перевірка не встановлює універсальної оптимальності популяції або схрещування. "
                  "Статичні варіанти не доводять результативності адаптивного керування.", ""])
    (destination / "Звіт.md").write_text("\n".join(lines), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--shards", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    protocol = guard_main()
    require(protocol["item_count"] == 100 and protocol["populations"] == list(POPS)
            and protocol["candidate_population"] == 20 and protocol["total_evaluations"] == TOTAL
            and tuple(protocol["checkpoints"]) == CHECKPOINTS and tuple(protocol["targets"]) == TARGETS
            and tuple(protocol["search_seeds"]) == SEEDS and protocol["bootstrap_samples"] == 50000
            and protocol["statistical_seed"] == 150031 and protocol["nominal_interval_level"] == .975,
            "registered analysis protocol differs")
    require(not args.out.exists(), "preserve any prior analysis output")
    records, provenance = load_shards(args.shards, protocol)
    profiles, checkpoints, families, loo, costs, contrasts = summarize(records)
    args.out.mkdir(parents=True)
    figures = args.out / "figures"
    figures.mkdir()
    save_csv(args.out / "profiles.csv", profiles)
    save_csv(args.out / "checkpoints.csv", checkpoints)
    save_csv(args.out / "family_effects.csv", families)
    save_csv(args.out / "leave_one_family_out.csv", loo)
    save_csv(args.out / "costs.csv", costs)
    save_json(args.out / "primary_contrasts.json", contrasts)
    save_json(args.out / "provenance.json", {"schema": "population-validation-100-analysis-v1",
              "status": "VERIFIED_900_COMPACT_RECORDS", "runs": len(records), "shards": provenance,
              "main_source_manifest_sha256": file_sha(HERE / "source_manifest.json"),
              "raw_journal_limitation": "Raw files were independently replayed in shard jobs; aggregate verifies the compact manifests and their recorded raw-file identities without downloading or re-running raw journals.",
              "new_search_evaluations_in_analysis": 0})
    names = plot(records, checkpoints, families, figures)
    write_report(args.out, profiles, checkpoints, families, costs, contrasts, names)
    print("Verified 900 compact records and produced the registered two comparisons.", flush=True)


if __name__ == "__main__":
    main()
