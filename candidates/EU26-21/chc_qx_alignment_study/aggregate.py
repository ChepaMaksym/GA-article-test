"""Complete-series proof validation and descriptive reporting, CI-only.

No training, hypothesis test, bootstrap, winner selection or right-padding is
performed. Models are authenticated as bytes and never deserialized here.
"""
from __future__ import annotations

import argparse
from collections import Counter
import csv
import gzip
import hashlib
import json
from pathlib import Path
import shutil
import statistics

from corrected_applied.data_protocol import TRANSFORMED_FEATURE_NAMES
from chc_qx_alignment_study.artifacts import validate_transport
from chc_qx_alignment_study.contract import (
    ALL_ARMS, CASE_SEEDS, CASE_SCHEMA, PROTOCOL_ID, PROTOCOL_SHA256, THIS_DIRECTORY,
    authenticate, canonical_sha256, file_sha256, read_json, require,
    validate_mask, verify_manifest, write_json,
)
from local_optima_study.contract import per_class_metrics
from chc_qx_alignment_study.validate_evidence import validate_diagnostic, validate_search


LABELS = {"chc_qx": "CHC із QX", "lambda_adaptive_qx": "Адаптивний λ із QX",
          "lambda_fixed1_qx": "Сталий λ=1 із QX"}
CLASSES = ("neither_local", "approximate_only_false_local", "both_local", "full_only_local")
CLASS_LABELS = {"neither_local": "Не максимум обох функцій",
                "approximate_only_false_local": "Хибний максимум наближення",
                "both_local": "Максимум обох функцій", "full_only_local": "Лише повний максимум"}


def close(actual: float, expected: float, name: str) -> None:
    require(abs(float(actual) - float(expected)) <= 1e-12, f"derived metric mismatch: {name}")


def validate_metrics(metrics: dict) -> None:
    for scope in ("weighted", "unweighted"):
        block = metrics[scope]
        matrix = block["confusion_matrix"]
        classes = per_class_metrics(matrix)
        require(set(block["classes"]) == {"0", "1"}, "missing class metrics")
        for label in classes:
            for key, value in classes[label].items():
                close(block["classes"][label][key], value, f"{scope}/{label}/{key}")
        wba = sum(classes[label]["recall"] for label in classes) / 2
        close(block["balanced_accuracy"], wba, scope + "/balanced_accuracy")
        total = sum(sum(row) for row in matrix)
        require(total > 0, "empty test confusion matrix")
        close(block["accuracy"], (matrix[0][0] + matrix[1][1]) / total, scope + "/accuracy")
        if scope == "unweighted":
            require(total == 99762 and all(type(value) is int and value >= 0
                    for row in matrix for value in row), "test record counts invalid")


def validate_case(directory: Path, source: dict, registry: dict, registry_sha256: str,
                  *, expected_sha: str, seed: int, preparation: dict | None = None) -> tuple[dict, dict]:
    manifest = verify_manifest(directory / "manifest.json", expected_sha=expected_sha)
    require(manifest["seed"] == seed and manifest["artifact_name"] == source["name"]
            and manifest["row_file"] == "case.json", "case manifest identity mismatch")
    row = read_json(directory / "case.json")
    require(row["schema"] == CASE_SCHEMA and row["seed"] == seed
            and row["artifact_name"] == source["name"]
            and row["provenance"] == manifest["provenance"], "case identity mismatch")
    require(row["provenance"]["run_id"] == registry["source_run_id"]
            and source["workflow_run"]["id"] == row["provenance"]["run_id"], "case source run mismatch")
    entry = registry["cases"][seed - CASE_SEEDS[0]]
    source_preparation = row["preparation"]
    require(source_preparation["registry_sha256"] == registry_sha256
            and source_preparation["preparation"] == entry["preparation"]
            and source_preparation["source_run_id"] == entry["source_run_id"]
            and source_preparation["source_artifact_id"] == entry["source_artifact_id"], "case did not replay frozen preparation")
    if preparation is not None:
        require(row["initial_masks"] == preparation["initial_masks"]
                and row["initial_scores"] == preparation["initial_scores"]
                and row["training_data"] == preparation["training_data"], "case initialization differs from original preparation")
    if row["status"] == "NOT_EVALUABLE_SAMPLER":
        require(entry["status"] == "NOT_EVALUABLE_SAMPLER" and row["arms"] == {}
                and row["counts"]["test_evaluations"] == 0
                and row["counts"]["diagnostic_calls"] == 0, "invalid preparation exclusion")
        return row, {}
    require(entry["status"] == "PASS_PREPARATION"
            and row["status"] in ("PASS_CASE_COMPLETE", "CASE_WITH_NOT_EVALUABLE_ARM")
            and set(row["arms"]) == set(ALL_ARMS), "case completeness mismatch")
    require(row["training_data"]["feature_names"] == list(TRANSFORMED_FEATURE_NAMES), "feature-bit order mismatch")
    freeze_id = row["terminal_masks_freeze"]
    require(freeze_id["file"] in manifest["files"]
            and {key: freeze_id[key] for key in ("sha256", "bytes")} == manifest["files"][freeze_id["file"]],
            "terminal freeze identity mismatch")
    freeze = read_json(directory / freeze_id["file"])
    require(freeze["test_evaluations_so_far"] == 0
            and set(freeze["arms"]) == set(ALL_ARMS)
            and freeze["selected_by"] == "full_internal_training_validation_only",
            "terminal masks were not frozen before test")
    traces = {}
    for arm in ALL_ARMS:
        summary = row["arms"][arm]
        trace_identity = summary["trace"]
        require(trace_identity["file"] in manifest["files"]
                and {key: trace_identity[key] for key in ("sha256", "bytes")} == manifest["files"][trace_identity["file"]],
                "unlisted search trace or false trace identity")
        trace = read_json(directory / trace_identity["file"])
        require(trace["arm"] == arm and trace["seed"] == seed, "search trace identity mismatch")
        validate_search(trace, row["initial_masks"], row["initial_scores"])
        for key in ("selected_mask", "full_validation_wba", "active_logical_calls",
                    "active_physical_calls", "full_calls", "checkpoint_visits", "chunks",
                    "terminal_state", "stop_reason", "snapshot"):
            require(summary[key] == trace[key], f"trace summary mismatch: {key}")
        diagnostic_identity = summary["diagnostics"]
        require(diagnostic_identity["file"] in manifest["files"]
                and {key: diagnostic_identity[key] for key in ("sha256", "bytes")} == manifest["files"][diagnostic_identity["file"]],
                "diagnostic evidence absent or false identity")
        diagnostic = read_json(directory / diagnostic_identity["file"])
        require(diagnostic["seed"] == seed and diagnostic["arm"] == arm
                and diagnostic["provenance"] == row["provenance"], "diagnostic source identity mismatch")
        validate_diagnostic(diagnostic, trace["snapshot"])
        require(diagnostic["approximate"]["center_wba"] == trace["snapshot"]["active_wba"],
                "independent center did not reproduce search WBA")
        counts = summary["counts"]
        require(counts["active"]["physical_calls"] == trace["active_physical_calls"]
                and counts["full_checkpoints"]["physical_calls"] == trace["full_calls"]
                and counts["diagnostic_active"]["physical_calls"] == 41
                and counts["diagnostic_full"]["physical_calls"] == 41, "separate counters mismatch")
        require(freeze["arms"][arm] == {"mask": summary["selected_mask"],
                                        "full_validation_wba": summary["full_validation_wba"]}, "test winner differs from freeze")
        if summary["selected_mask"] is None:
            require(summary["test_metrics"] is None and summary["test_evaluations"] == 0,
                    "missing full winner accessed test")
        else:
            validate_mask(summary["selected_mask"])
            require(summary["test_evaluations"] == 1 and sum(summary["selected_mask"]) > 0,
                    "test mask/counter mismatch")
            validate_metrics(summary["test_metrics"])
        # This report-only expansion never rewrites the authenticated source row.
        summary["diagnostic"] = diagnostic
        traces[arm] = trace
    require(row["counts"]["shared_initial_physical_calls"] == 50
            and row["counts"]["diagnostic_calls"] == 246
            and row["counts"]["test_evaluations"] == sum(a["test_evaluations"] for a in row["arms"].values()),
            "case accounting mismatch")
    return row, traces


def write_csv(path: Path, rows: list[dict]) -> None:
    require(bool(rows), "empty report table")
    fields = list(dict.fromkeys(key for row in rows for key in row))
    with path.open("x", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def describe(rows: list[dict]) -> dict:
    result = {}
    for arm in ALL_ARMS:
        available = [row["arms"][arm] for row in rows if arm in row["arms"]]
        valid = [item for item in available if item["test_metrics"] is not None]
        result[arm] = {
            "method": LABELS[arm], "registered_cases": 30, "diagnostic_cases": len(available),
            "valid_test_cases": len(valid), "not_evaluable_cases": 30 - len(available),
            "classifications": dict(Counter(item["diagnostic"]["classification"] for item in available)),
            "strict_approximate_maxima": sum(item["diagnostic"]["approximate"]["strict_local_maximum"] for item in available),
            "plateau_approximate_maxima": sum(item["diagnostic"]["approximate"]["plateau_local_maximum"] for item in available),
            "strict_full_maxima": sum(item["diagnostic"]["full"]["strict_local_maximum"] for item in available),
            "plateau_full_maxima": sum(item["diagnostic"]["full"]["plateau_local_maximum"] for item in available),
            "observed_stagnation_snapshots": sum(item["snapshot"]["reason"] == "first_whole_chunk_without_active_gain" for item in available),
            "stop_reasons": dict(Counter(item["stop_reason"] for item in available)),
            "median_test_wba": statistics.median(item["test_metrics"]["weighted"]["balanced_accuracy"] for item in valid) if valid else None,
            "feature_count_range": [min(sum(item["selected_mask"]) for item in valid),
                                    max(sum(item["selected_mask"]) for item in valid)] if valid else None,
            "active_logical_calls": sum(item["active_logical_calls"] for item in available),
            "active_physical_calls": sum(item["active_physical_calls"] for item in available),
            "full_calls": sum(item["full_calls"] for item in available),
            "diagnostic_calls": 82 * len(available), "test_evaluations": len(valid),
        }
    return {"schema": "eu26-21-qx-descriptive-summary-v1", "protocol_id": PROTOCOL_ID,
            "cases_accounted": len(rows), "arms": result, "hypothesis_tests": False,
            "claims": {"speed_superiority": False, "escape_advantage": False,
                       "global_optimality": False, "historical_results_reinterpreted": False}}


def plots(directory: Path, rows: list[dict], traces: dict) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np
    fig, ax = plt.subplots(figsize=(10, 5))
    bottoms = np.zeros(3)
    for category in CLASSES + ("not_evaluable",):
        counts = [sum(item["arms"].get(arm, {}).get("diagnostic", {}).get("classification") == category
                      for item in rows) if category != "not_evaluable" else sum(arm not in item["arms"] for item in rows)
                  for arm in ALL_ARMS]
        ax.bar([LABELS[arm] for arm in ALL_ARMS], counts, bottom=bottoms,
               label=CLASS_LABELS.get(category, "Непридатна підготовка"))
        bottoms += counts
    ax.set_ylabel("Кількість випадків із 30")
    ax.set_title("Однобітна діагностика зафіксованих станів")
    ax.legend(fontsize=8, loc="upper left", bbox_to_anchor=(1, 1))
    fig.tight_layout()
    fig.savefig(directory / "locality-types.png", dpi=180)
    plt.close(fig)
    fig, axes = plt.subplots(1, 3, figsize=(15, 5), sharey=True)
    for arm, ax in zip(ALL_ARMS, axes):
        for (seed, name), trace in traces.items():
            if name != arm:
                continue
            points = trace["active_trace"]
            ax.step([point["call"] for point in points], [point["best_so_far_wba"] for point in points],
                    where="post", color="tab:blue", alpha=.18)
            checks = trace["checkpoints"]
            ax.scatter([point["active_logical_calls"] for point in checks],
                       [point["best_full"] for point in checks], s=9, color="tab:orange", alpha=.3)
        ax.set_title(LABELS[arm])
        ax.set_xlabel("Логічні пошукові оцінювання")
    axes[0].set_ylabel("Валідаційна WBA")
    fig.suptitle("Пошукові траєкторії та повні перевірки; без подовження завершених запусків")
    fig.tight_layout()
    fig.savefig(directory / "search-and-full-checkpoints.png", dpi=180)
    plt.close(fig)
    fig, ax = plt.subplots(figsize=(10, 4))
    for (seed, name), trace in traces.items():
        if name == "lambda_adaptive_qx":
            gens = trace["generation_trace"]
            ax.plot([point["generation"] for point in gens], [point["applied_lambda_after"] for point in gens], alpha=.3)
    ax.set_xlabel("Завершене покоління")
    ax.set_ylabel("Застосоване λ")
    ax.set_title("Адаптація λ у природному пошуку")
    fig.tight_layout()
    fig.savefig(directory / "adaptive-lambda.png", dpi=180)
    plt.close(fig)


def aggregate(*, root: Path, registry_path: Path, sources_path: Path, transport_path: Path,
              output: Path, expected_sha: str) -> dict:
    _, provenance = authenticate(protocol_path=THIS_DIRECTORY / "protocol.json", expected_sha=expected_sha)
    sources, registry = read_json(sources_path), read_json(registry_path)
    require(sources["kind"] == "case" and sources["implementation_sha"] == expected_sha
            and sources["protocol_sha256"] == PROTOCOL_SHA256
            and registry["implementation_sha"] == expected_sha
            and registry["protocol_sha256"] == PROTOCOL_SHA256,
            "report source identity mismatch")
    require(registry["frozen_before_main_search"] is True and len(registry["cases"]) == 30
            and [item["seed"] for item in registry["cases"]] == list(CASE_SEEDS), "incomplete registry")
    validate_transport(sources, read_json(transport_path))
    require(len(sources["artifacts"]) == 30, "incomplete case sources")
    packed_identity = registry["frozen_preparations"]
    require(packed_identity["file"] == "frozen-preparations.json.gz", "unexpected preparation archive")
    packed_path = registry_path.parent / packed_identity["file"]
    require(packed_path.is_file() and not packed_path.is_symlink()
            and packed_path.stat().st_size == packed_identity["bytes"]
            and file_sha256(packed_path) == packed_identity["sha256"], "frozen preparation archive changed")
    with gzip.open(packed_path, "rb") as stream:
        original_bytes = stream.read(256 * 1024**2 + 1)
    require(len(original_bytes) <= 256 * 1024**2, "preparation archive expands beyond limit")
    original = json.loads(original_bytes)
    require(original["schema"] == "eu26-21-qx-original-preparations-v1"
            and [item["seed"] for item in original["records"]] == list(CASE_SEEDS), "original preparation coverage mismatch")
    preparations = {}
    for record, entry in zip(original["records"], registry["cases"]):
        raw = record["original_utf8"].encode("utf-8")
        require(len(raw) == record["bytes"] == entry["preparation"]["bytes"]
                and hashlib.sha256(raw).hexdigest() == record["original_sha256"] == entry["preparation"]["sha256"],
                "original preparation bytes cannot be authenticated")
        preparations[record["seed"]] = json.loads(raw)
    rows, traces = [], {}
    for seed, source in zip(CASE_SEEDS, sources["artifacts"]):
        row, case_traces = validate_case(root / source["name"], source, registry,
                                        file_sha256(registry_path), expected_sha=expected_sha, seed=seed,
                                        preparation=preparations[seed])
        rows.append(row)
        traces.update({(seed, arm): value for arm, value in case_traces.items()})
    output.mkdir(parents=True, exist_ok=True)
    require(not any(output.iterdir()), "report output is not empty")
    shutil.copyfile(packed_path, output / packed_path.name)
    summary = describe(rows)
    summary.update({"provenance": provenance, "source_run_id": sources["source_run_id"],
                    "registry_sha256": file_sha256(registry_path),
                    "case_sources_sha256": file_sha256(sources_path),
                    "case_transport_sha256": file_sha256(transport_path)})
    write_json(output / "summary.json", summary)
    case_rows, neighbors, checks, classes = [], [], [], []
    for row in rows:
        seed = row["seed"]
        for arm in ALL_ARMS:
            item = row["arms"].get(arm)
            if item is None:
                case_rows.append({"seed": seed, "arm": arm, "status": row["status"]})
                continue
            case_rows.append({"seed": seed, "arm": arm, "status": item["evaluation_status"],
                              "stop_reason": item["stop_reason"], "chunks": item["chunks"],
                              "snapshot_reason": item["snapshot"]["reason"],
                              "locality": item["diagnostic"]["classification"],
                              "full_validation_wba": item["full_validation_wba"],
                              "test_wba": item["test_metrics"]["weighted"]["balanced_accuracy"] if item["test_metrics"] else None,
                              "features": sum(item["selected_mask"]) if item["selected_mask"] is not None else None,
                              "mask": "".join(map(str, item["selected_mask"])) if item["selected_mask"] is not None else None,
                              "active_logical_calls": item["active_logical_calls"], "active_physical_calls": item["active_physical_calls"],
                              "full_calls": item["full_calls"], "diagnostic_calls": 82,
                              "test_evaluations": item["test_evaluations"]})
            for scope in ("approximate", "full"):
                for point in item["diagnostic"][scope]["evaluations"]:
                    neighbors.append({"seed": seed, "arm": arm, "scope": scope,
                                      **{key: value for key, value in point.items() if key != "mask"},
                                      "mask": "".join(map(str, point["mask"]))})
            for checkpoint in traces[(seed, arm)]["checkpoints"]:
                checks.append({"seed": seed, "arm": arm, **{key: value for key, value in checkpoint.items() if key != "candidate_visits"}})
            if item["test_metrics"]:
                for scale in ("weighted", "unweighted"):
                    for label, metrics in item["test_metrics"][scale]["classes"].items():
                        classes.append({"seed": seed, "arm": arm, "scale": scale, "class": label, **metrics})
    write_csv(output / "cases.csv", case_rows)
    if neighbors:
        write_csv(output / "one-bit-certificates.csv", neighbors)
        write_csv(output / "checkpoints.csv", checks)
    if classes:
        write_csv(output / "class-metrics.csv", classes)
    write_csv(output / "bit-feature-map.csv", [{"bit_index": i, "feature": name} for i, name in enumerate(TRANSFORMED_FEATURE_NAMES)])
    plots(output, rows, traces)
    text = ["# Результати діагностики CHC-QX", "", "Ураховано всі 30 зареєстрованих випадків. Серія описова; статистичних перевірок переваги не виконували.", "",
            "| Метод | Придатні сертифікати | Хибний максимум наближення | Максимум обох функцій | Обмежені запуски | Медіана тестової WBA |", "|---|---:|---:|---:|---:|---:|"]
    for arm, item in summary["arms"].items():
        quality = "Не визначено" if item["median_test_wba"] is None else f"{100 * item['median_test_wba']:.4f}%"
        text.append(f"| {LABELS[arm]} | {item['diagnostic_cases']} | {item['classifications'].get('approximate_only_false_local', 0)} | {item['classifications'].get('both_local', 0)} | {item['stop_reasons'].get('censored_safety_cap', 0)} | {quality} |")
    text += ["", "Стан фіксувався наприкінці першого цілого блоку без приросту наближеної WBA; за відсутності такого блоку перевірено кінцевий стан. Ці правила не оцінюють усі стани траєкторії.", "",
             "Повна функція означає дерево на всій внутрішній навчальній частині. Однобітний сертифікат не доводить глобальності. Хибний максимум означає, що за повною функцією є кращий однобітний сусід.", "",
             "CHC і λ мають різне число кандидатів повної перевірки й різні витрати покоління. Спільної межі 400 оцінювань немає. Перевагу за швидкістю або виходом із максимуму не заявлено.", "",
             "*Не перевірено контрольований вихід із природних максимумів, двобітну неглобальність, інші сталі λ, інші набори даних і причинний вплив ознак на дохід. Історичні висновки залишаються незмінними.*", ""]
    (output / "RESULTS_UK.md").write_text("\n".join(text), encoding="utf-8")
    write_json(output / "report-manifest.json", {"schema": "eu26-21-qx-report-manifest-v1", "provenance": provenance,
               "source_run_id": sources["source_run_id"], "files": {member.name: {"sha256": file_sha256(member), "bytes": member.stat().st_size}
               for member in sorted(output.iterdir()) if member.is_file()}, "manifest_self_hash_excluded": True})
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--registry", type=Path, required=True)
    parser.add_argument("--sources", type=Path, required=True)
    parser.add_argument("--download-ledger", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--expected-sha", required=True)
    args = parser.parse_args()
    summary = aggregate(root=args.root, registry_path=args.registry, sources_path=args.sources,
                        transport_path=args.download_ledger, output=args.output, expected_sha=args.expected_sha)
    print(f"PASS_COMPLETE_DESCRIPTIVE_QX_REPORT cases={summary['cases_accounted']}")


if __name__ == "__main__":
    main()
