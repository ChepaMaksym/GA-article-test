"""Exact descriptive selection and CI-only exports for fixed-mutation tuning.

This module consumes verified compact records. It never imports a search
executor, prepares starts, or solves a knapsack. Replaying raw journals and
authenticating artifact provenance are separate admission steps.
"""
from collections import defaultdict
from fractions import Fraction
from pathlib import Path, PurePosixPath
import argparse
import csv
import math
import re
from statistics import NormalDist

from studies.knapsack_parameters.population_validation_100.common import (
    read_json, write_json, require, sha,
)

TOTAL = 100000
TARGETS = (93, 95, 99)
CHECKPOINTS = (5000, 10000, 20000, 50000, 100000)
TYPES = ("UC", "WC", "SC")
TUNING_FAMILIES = tuple(f"s{i:03d}" for i in range(50, 60))
VALIDATION_FAMILIES = tuple(f"s{i:03d}" for i in range(60, 70))
TUNING_SEEDS = (150001, 150002, 150003)
VALIDATION_SEEDS = tuple(range(160001, 160011))
MUTATIONS = (25, 50, 75, 100, 150, 200)
MUTATION_CONFIGS = tuple((mu, 100, bp) for mu in (10, 15, 20) for bp in MUTATIONS)
OLD_CONFIGS = tuple((mu, pc, 100) for mu in (10, 15, 20, 25) for pc in (70, 80, 90, 100))
CONFIGS = tuple(sorted(set(MUTATION_CONFIGS) | set(OLD_CONFIGS)))
CONTROLS = ((15, 100, 100), (10, 90, 100), (20, 90, 100))
RAW_FILES = {"journal.json.gz", "verification.json", "operator_bins.json", "observations.json.gz", "record.json"}


def configuration(row):
    """Return population, crossover percent, and integer mutation basis points."""
    return row["mu"], row["pc_percentage"], row["mutation_basis_points"]


def identity(row):
    return row["task"], row["seed"], *configuration(row)


def mean(values):
    values = list(values)
    require(bool(values), "Cannot average an empty group")
    return sum(values, Fraction()) / len(values)


def normalize_retained(row):
    """Label a separately authenticated historical 1% record explicitly.

    Call only after verifying the retained artifact's registered origin and
    digest. This helper does not establish raw-journal provenance by itself.
    """
    copied = dict(row)
    require("mutation_basis_points" not in copied or copied["mutation_basis_points"] == 100,
            "Retained crossover-grid records must have mutation 1%")
    require((copied.get("mu"), copied.get("pc_percentage"), 100) in OLD_CONFIGS,
            "Retained configuration is outside the completed grid")
    copied["mutation_basis_points"] = 100
    return copied


def gap(row, q=TOTAL):
    best = row["best"] if q == TOTAL else next(p["record_profit"] for p in row["checkpoints"] if p["q"] == q)
    return Fraction(100 * (row["optimum"] - best), row["optimum"])


def threshold(row, target):
    return next((q for q, value in row["events"] if 100 * value >= target * row["optimum"]), None)


def _finite(value, name, lower=0, upper=None):
    require(type(value) in (int, float) and math.isfinite(value) and value >= lower
            and (upper is None or value <= upper), "Invalid " + name)


def _digest(value):
    return type(value) is str and re.fullmatch(r"[0-9a-f]{64}", value) is not None


def validate_row(row, phase="tuning"):
    """Check numerical identity, full record history, endpoints and costs.

    Historical and new evidence paths have different suffixes. This function
    enforces a safe task/seed prefix; the caller must additionally authenticate
    exact artifact path, receipt, source SHA and replay status at admission.
    """
    require(phase in ("tuning", "validation"), "Unknown analysis phase")
    require(type(row) is dict, "A compact record must be an object")
    families = TUNING_FAMILIES if phase == "tuning" else VALIDATION_FAMILIES
    seeds = TUNING_SEEDS if phase == "tuning" else VALIDATION_SEEDS
    require(row.get("family") in families and row.get("class_label") in TYPES
            and type(row.get("seed")) is int and row["seed"] in seeds, "Task/seed outside protocol")
    require(all(type(row.get(k)) is int for k in ("mu", "pc_percentage", "mutation_basis_points"))
            and configuration(row) in CONFIGS, "Unregistered fixed configuration")
    family, kind, mu = row["family"], row["class_label"], row["mu"]
    require(row.get("task") == f"n00100-{kind}-{family}", "Task name differs from family/type")
    expected_index = (3 if phase == "tuning" else 33) + (int(family[1:]) - (50 if phase == "tuning" else 60)) * 3 + TYPES.index(kind)
    require(type(row.get("task_index")) is int and row["task_index"] == expected_index,
            "Task index differs from the frozen registry")
    optimum, best = row.get("optimum"), row.get("best")
    require(type(optimum) is int and type(best) is int and optimum > 0 and 0 <= best <= optimum,
            "Invalid optimum or feasible record")
    events = row.get("events")
    require(type(events) is list and bool(events), "Record events are missing")
    require(all(type(e) is list and len(e) == 2 and type(e[0]) is int and type(e[1]) is int
                and 1 <= e[0] <= TOTAL and 0 <= e[1] <= optimum for e in events), "Invalid record event")
    require(events[0] == [1, 0], "The first evaluated mask must be the empty mask")
    require(all(a[0] < b[0] and a[1] < b[1] for a, b in zip(events, events[1:])),
            "Record history must strictly improve at increasing evaluation numbers")
    require(events[-1][1] == best, "Final record differs from event history")
    targets = row.get("targets")
    require(type(targets) is dict and set(targets) == {str(t) for t in TARGETS}, "Target inventory differs")
    for target in TARGETS:
        expected = threshold(row, target)
        value = targets[str(target)]
        require(type(value) is dict and type(value.get("attained")) is bool
                and value["attained"] == (expected is not None)
                and value.get("first_total_evaluation") == expected
                and type(value.get("restricted_evaluations")) is int
                and value["restricted_evaluations"] == (expected if expected is not None else TOTAL),
                "Threshold hit, nonattainment or restricted evaluations differ")
    points = row.get("checkpoints")
    require(type(points) is list and len(points) == len(CHECKPOINTS)
            and all(type(p) is dict for p in points), "Five checkpoint objects are required")
    by_q = {p.get("q"): p for p in points}
    require(set(by_q) == set(CHECKPOINTS) and len(by_q) == len(points), "Checkpoint inventory differs")
    for q in CHECKPOINTS:
        point = by_q[q]
        expected = next(value for event_q, value in reversed(events) if event_q <= q)
        require(type(point.get("q")) is int and type(point.get("record_profit")) is int
                and point["record_profit"] == expected, "Checkpoint record differs")
        require(type(point.get("completed_generations")) is int
                and point["completed_generations"] == (q - mu) // (mu - 1), "Checkpoint generation count differs")
        metrics = point.get("population_metrics")
        require(type(metrics) is dict and metrics.get("population_size") == mu, "Completed population size differs")
        _finite(metrics.get("unique_fraction"), "unique fraction", upper=1)
        _finite(metrics.get("feasible_fraction"), "feasible fraction", upper=1)
        _finite(metrics.get("mean_pairwise_hamming"), "mean Hamming distance", upper=100)
    require(type(row.get("completed_generations")) is int
            and row["completed_generations"] == (TOTAL - mu) // (mu - 1), "Final generation count differs")
    require(type(row.get("duplicates")) is int and 0 <= row["duplicates"] <= TOTAL - mu, "Duplicate count invalid")
    hashes = row.get("artifact_hashes")
    require(type(hashes) is dict and set(hashes) == RAW_FILES and all(_digest(s) for s in hashes.values()),
            "Raw evidence hash inventory differs")
    prefix = row.get("artifact_prefix")
    require(type(prefix) is str and "\\" not in prefix and ":" not in prefix,
            "Unsafe artifact prefix")
    parts = PurePosixPath(prefix)
    require(not parts.is_absolute() and ".." not in parts.parts
            and parts.parts[:2] == (row["task"], f'seed-{row["seed"]}'), "Evidence identity/path differs")
    require(_digest(row.get("bank_sha256")) and _digest(row.get("certificate_sha256")),
            "Bank or certificate checksum missing")
    timing = row.get("timing")
    require(type(timing) is dict, "Per-run costs are required")
    names = ("search_seconds", "log_write_seconds", "verification_seconds", "observations_seconds", "case_seconds", "artifact_bytes")
    for name in names:
        _finite(timing.get(name), name)
    require(timing["case_seconds"] >= sum(timing[n] for n in names[:4]), "Case time omits an accounted component")
    return row


def _validate_collection(rows, configs, families, seeds, phase):
    require(type(rows) is list, "Records must be a list")
    expected = {(f"n00100-{kind}-{family}", seed, *config)
                for family in families for kind in TYPES for seed in seeds for config in configs}
    seen = set()
    paired = defaultdict(list)
    task_rows = defaultdict(list)
    for row in rows:
        validate_row(row, phase)
        key = identity(row)
        require(key not in seen, "Duplicate compact identity")
        seen.add(key)
        paired[(row["task"], row["seed"])].append(row)
        task_rows[row["task"]].append(row)
    require(seen == expected and len(rows) == len(expected), "Missing or substituted task/seed/configuration")
    for group in paired.values():
        require(len({r["bank_sha256"] for r in group}) == 1,
                "Corresponding configurations use different initial bank bytes")
    for group in task_rows.values():
        require(len({r["optimum"] for r in group}) == len({r["certificate_sha256"] for r in group}) == 1,
                "One task has inconsistent exact references")
    return rows


def validate_union(rows):
    """Require exactly 31 configurations, 90 paired cases each: 2790 rows."""
    return _validate_collection(rows, CONFIGS, TUNING_FAMILIES, TUNING_SEEDS, "tuning")


def family_means(rows, config, value, families=TUNING_FAMILIES, seeds=TUNING_SEEDS):
    groups = defaultdict(list)
    for row in rows:
        if configuration(row) == config:
            groups[(row["family"], row["class_label"])].append(row)
    result = []
    for family in families:
        task_values = []
        for kind in TYPES:
            group = groups[(family, kind)]
            require(len(group) == len(seeds) and {r["seed"] for r in group} == set(seeds),
                    "Task repetitions are incomplete")
            task_values.append(mean(value(r) for r in group))
        result.append(mean(task_values))
    return tuple(result)


def summarize(rows):
    """Produce exact metrics; rounding occurs only in exported presentation."""
    validate_union(rows)
    result = {}
    for config in CONFIGS:
        group = [r for r in rows if configuration(r) == config]
        family_gap = family_means(rows, config, gap)
        family_t93 = family_means(rows, config, lambda r: r["targets"]["93"]["restricted_evaluations"])
        data = {"configuration": config, "runs": len(group), "family_final_gap": family_gap,
                "family_t93": family_t93, "mean_gap_100000_percent": mean(family_gap),
                "worst_family_gap_100000_percent": max(family_gap), "mean_restricted_t93": mean(family_t93),
                "worst_family_t93": max(family_t93)}
        for q in CHECKPOINTS:
            data[f"mean_gap_{q}_percent"] = mean(family_means(rows, config, lambda r, q=q: gap(r, q)))
        for target in TARGETS:
            attained = sum(r["targets"][str(target)]["attained"] for r in group)
            data[f"attained_{target}"] = attained
            data[f"not_attained_{target}"] = len(group) - attained
            data[f"nonattainment_{target}"] = mean(family_means(rows, config,
                lambda r, target=target: int(not r["targets"][str(target)]["attained"])))
            data[f"mean_restricted_t{target}"] = mean(family_means(rows, config,
                lambda r, target=target: r["targets"][str(target)]["restricted_evaluations"]))
        data["mean_search_seconds"] = mean(family_means(rows, config,
            lambda r: Fraction(str(r["timing"]["search_seconds"]))))
        result[config] = data
    return result


def choose_recommendations(metrics):
    require(set(metrics) == set(CONFIGS), "All 31 configurations are required before selection")
    def preferences(config):
        mu, pc, bp = config
        return abs(bp - 100), abs(pc - 90), mu, bp, pc
    quality = min(CONFIGS, key=lambda c: (metrics[c]["mean_gap_100000_percent"],
        metrics[c]["worst_family_gap_100000_percent"], metrics[c]["mean_restricted_t93"], *preferences(c)))
    speed = min(CONFIGS, key=lambda c: (metrics[c]["mean_restricted_t93"], metrics[c]["nonattainment_93"],
        metrics[c]["mean_gap_100000_percent"], metrics[c]["worst_family_t93"], *preferences(c)))
    return {"quality": quality, "speed": speed}


def _config_object(config):
    return dict(zip(("mu", "pc_percentage", "mutation_basis_points"), config))


def _rational(value):
    value = Fraction(value)
    return {"numerator": value.numerator, "denominator": value.denominator}


def _csv(path, rows):
    require(bool(rows), "Cannot export an empty table")
    with Path(path).open("x", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]), delimiter=";")
        writer.writeheader()
        writer.writerows(rows)


def plot_tuning(metrics, out, chosen):
    """Generate publication artifacts only when explicitly called in CI."""
    from .common import guard_stage
    guard_stage("tuning")
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np
    out = Path(out)
    out.mkdir(exist_ok=False)
    gap_values = [float(metrics[c][f"mean_gap_{q}_percent"]) for c in MUTATION_CONFIGS for q in (50000, TOTAL)]
    low, high = min(gap_values), max(gap_values)
    if low == high:
        low, high = low - .0005, high + .0005
    for key, filename, label, scale in (
        ("mean_gap_50000_percent", "mutation-gap-50000", "Середнє відставання від OPT, %", (low, high)),
        ("mean_gap_100000_percent", "mutation-gap-100000", "Середнє відставання від OPT, %", (low, high)),
        ("mean_restricted_t93", "mutation-time93", "Обмежене середнє число оцінювань до 93% OPT", None),
    ):
        matrix = np.array([[float(metrics[(mu, 100, bp)][key]) for bp in MUTATIONS] for mu in (10, 15, 20)])
        fig, ax = plt.subplots(figsize=(9, 4.5), layout="constrained")
        image = ax.imshow(matrix, cmap="YlGnBu", aspect="auto",
                          vmin=scale[0] if scale else None, vmax=scale[1] if scale else None)
        norm_low, norm_high = image.get_clim()
        for i in range(3):
            for j in range(6):
                value = matrix[i, j]
                color = "white" if norm_high > norm_low and (value - norm_low) / (norm_high - norm_low) > .57 else "#132238"
                text = f"{value:.3f}" if "gap" in key else f"{value:.1f}"
                ax.text(j, i, text.replace(".", ","), ha="center", va="center", color=color)
        ax.set_xticks(range(6), [str(bp / 100).replace(".", ",") for bp in MUTATIONS])
        ax.set_yticks(range(3), ("10", "15", "20"))
        ax.set_xlabel("Імовірність мутації біта, %")
        ax.set_ylabel("Популяція, особин")
        fig.colorbar(image, ax=ax, label=label + "; менше — краще")
        for extension in ("png", "svg"):
            fig.savefig(out / f"{filename}.{extension}", dpi=200, bbox_inches="tight")
        plt.close(fig)
    fig, ax = plt.subplots(figsize=(8, 5), layout="constrained")
    for group, marker, color, label in ((OLD_CONFIGS, "o", "#4774a5", "Завершена сітка популяції та схрещування"),
                                      (tuple(c for c in MUTATION_CONFIGS if c not in OLD_CONFIGS), "s", "#ba522d", "Додані значення мутації")):
        ax.scatter([float(metrics[c]["mean_restricted_t93"]) for c in group],
                   [float(metrics[c]["mean_gap_100000_percent"]) for c in group], marker=marker, color=color, label=label)
    for role, config in chosen.items():
        value = metrics[config]
        ax.annotate("Кінцева якість" if role == "quality" else "Швидкість до 93%",
                    (float(value["mean_restricted_t93"]), float(value["mean_gap_100000_percent"])),
                    xytext=(8, 10 if role == "quality" else -18), textcoords="offset points")
    ax.set_xlabel("Обмежене середнє число оцінювань до 93% OPT")
    ax.set_ylabel("Кінцеве середнє відставання від OPT, %")
    ax.grid(alpha=.2)
    ax.legend(fontsize=8)
    for extension in ("png", "svg"):
        fig.savefig(out / f"speed-and-quality.{extension}", dpi=200, bbox_inches="tight")
    plt.close(fig)


def export_tuning(rows, out, provenance):
    """Freeze two descriptive choices, machine data and CI figures.

    The caller authenticates the complete per-case receipts before invoking
    this function. The saved record digest binds both choices to their input.
    """
    from .common import guard_stage
    guard_stage("tuning")
    require(type(provenance) is dict and provenance.get("status") == "ALL_CASES_INDEPENDENTLY_VERIFIED",
            "A complete independently verified provenance ledger is required")
    out = Path(out)
    require(not out.exists(), "Preserve previous analysis output")
    metrics = summarize(rows)
    chosen = choose_recommendations(metrics)
    out.mkdir(parents=True)
    write_json(out / "validated_records.json.gz", {"schema": "mutation-grid-100-validated-union-v1",
               "status": "VERIFIED_2790", "runs": rows, "provenance": provenance})
    exports = []
    for config in CONFIGS:
        row = {**_config_object(config), "runs": metrics[config]["runs"]}
        for name, value in metrics[config].items():
            if name not in ("configuration", "runs", "family_final_gap", "family_t93"):
                row[name] = float(value) if isinstance(value, Fraction) else value
        exports.append(row)
    _csv(out / "all-configurations.csv", exports)
    _csv(out / "mutation-grid.csv", [r for r in exports if (r["mu"], r["pc_percentage"], r["mutation_basis_points"]) in MUTATION_CONFIGS])
    selections = {role: {**_config_object(config),
                        "mean_final_gap_exact": _rational(metrics[config]["mean_gap_100000_percent"]),
                        "mean_restricted_t93_exact": _rational(metrics[config]["mean_restricted_t93"])}
                  for role, config in chosen.items()}
    selection = {"schema": "mutation-grid-100-selections-v1", "status": "SELECTED_BEFORE_VALIDATION",
                 "selections": selections, "same_configuration": chosen["quality"] == chosen["speed"],
                 "source_records_sha256": sha(out / "validated_records.json.gz"),
                 "independent_validation_started": False, "selection_is_descriptive": True}
    write_json(out / "selection.json", selection)
    family_exports = [{**_config_object(c), "family": family,
                       "mean_final_gap_percent": float(metrics[c]["family_final_gap"][index]),
                       "mean_restricted_t93": float(metrics[c]["family_t93"][index])}
                      for c in CONFIGS for index, family in enumerate(TUNING_FAMILIES)]
    _csv(out / "family-metrics.csv", family_exports)
    plot_tuning(metrics, out / "figures", chosen)
    return selection


def bca_interval(family_effects, *, replicates=50000, seed=160031, confidence=Fraction(119, 120)):
    """Nominal paired whole-family BCa interval; constant vectors descriptive.

    More resamples do not add independent families or prove actual coverage.
    Identical configurations must be identified by the caller before invoking
    this numerical helper. Statistical replication is separate from replay.
    """
    from .common import guard_stage
    guard_stage("validation")
    import numpy as np
    require(len(family_effects) == 10 and type(replicates) is int and replicates == 50000
            and seed == 160031 and Fraction(confidence) == Fraction(119, 120), "Registered BCa design differs")
    values = np.array([float(x) for x in family_effects], dtype=float)
    require(bool(np.isfinite(values).all()), "Nonfinite family effect")
    estimate = float(values.mean())
    if bool((values == values[0]).all()):
        return {"status": "DEGENERATE_DESCRIPTIVE", "estimate": estimate, "lower": None, "upper": None}
    generator = np.random.Generator(np.random.PCG64(seed))
    draws = generator.integers(0, len(values), size=(replicates, len(values)))
    samples = values[draws].mean(axis=1)
    fraction = (float((samples < estimate).sum()) + .5 * float((samples == estimate).sum())) / replicates
    fraction = min(1 - .5 / replicates, max(.5 / replicates, fraction))
    normal = NormalDist()
    z0 = normal.inv_cdf(fraction)
    jack = np.array([np.delete(values, i).mean() for i in range(len(values))])
    differences = jack.mean() - jack
    denominator = 6 * float((differences ** 2).sum()) ** 1.5
    if denominator == 0:
        return {"status": "DEGENERATE_DESCRIPTIVE", "estimate": estimate, "lower": None, "upper": None}
    acceleration = float((differences ** 3).sum()) / denominator
    alpha = (1 - float(confidence)) / 2
    adjusted = []
    for probability in (alpha, 1 - alpha):
        z = normal.inv_cdf(probability)
        divisor = 1 - acceleration * (z0 + z)
        if divisor <= 0:
            return {"status": "UNDEFINED_BCA_DESCRIPTIVE", "estimate": estimate, "lower": None, "upper": None}
        adjusted.append(normal.cdf(z0 + (z0 + z) / divisor))
    if not 0 <= adjusted[0] <= adjusted[1] <= 1:
        return {"status": "UNDEFINED_BCA_DESCRIPTIVE", "estimate": estimate, "lower": None, "upper": None}
    lower, upper = np.quantile(samples, adjusted, method="linear")
    return {"status": "NOMINAL_BCA", "estimate": estimate, "lower": float(lower), "upper": float(upper),
            "confidence": float(confidence), "replicates": replicates, "families": len(values), "seed": seed}


def final_comparisons(rows, selections):
    """Compute the six frozen comparisons, family effects and leave-one-out."""
    from .common import guard_stage
    guard_stage("validation")
    require(set(selections) == {"quality", "speed"}, "Two pre-frozen selection roles are required")
    chosen = {role: tuple(value[k] for k in ("mu", "pc_percentage", "mutation_basis_points"))
              for role, value in selections.items()}
    require(all(c in CONFIGS for c in chosen.values()), "Selected configuration was not in tuning")
    configs = tuple(sorted(set(CONTROLS) | set(chosen.values())))
    _validate_collection(rows, configs, VALIDATION_FAMILIES, VALIDATION_SEEDS, "validation")
    results = []
    for role in ("quality", "speed"):
        candidate = chosen[role]
        value = gap if role == "quality" else lambda r: r["targets"]["93"]["restricted_evaluations"]
        candidate_families = family_means(rows, candidate, value, VALIDATION_FAMILIES, VALIDATION_SEEDS)
        for control in CONTROLS:
            control_families = family_means(rows, control, value, VALIDATION_FAMILIES, VALIDATION_SEEDS)
            effects = tuple(a - b for a, b in zip(control_families, candidate_families))
            interval = ({"status": "IDENTICAL_CONFIGURATION", "estimate": 0.0, "lower": None, "upper": None}
                        if candidate == control else bca_interval(effects))
            results.append({"role": role, "metric": "final_gap_percentage_points" if role == "quality" else "restricted_t93_evaluations",
                            "candidate": _config_object(candidate), "control": _config_object(control),
                            "effect_direction": "control_minus_candidate", "interval": interval,
                            "family_effects": [{"family": family, "effect_exact": _rational(effect), "effect": float(effect)}
                                               for family, effect in zip(VALIDATION_FAMILIES, effects)],
                            "leave_one_family_out": [{"omitted_family": family, "effect": float(mean(effects[:i] + effects[i + 1:]))}
                                                     for i, family in enumerate(VALIDATION_FAMILIES)]})
    return results


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--records", type=Path, required=True,
                        help="Authenticated VERIFIED_2790 compact collection produced by the admission step")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    from .common import guard_stage
    guard_stage("tuning")
    data = read_json(args.records)
    require(data.get("schema") == "mutation-grid-100-validated-union-v1" and data.get("status") == "VERIFIED_2790",
            "Analysis requires the complete independently verified collection")
    export_tuning(data.get("runs"), args.out, data.get("provenance"))


if __name__ == "__main__":
    main()
