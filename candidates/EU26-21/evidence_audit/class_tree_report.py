"""Descriptive class metrics and excerpts of two authenticated saved trees.

This reporting command is CI-only. It neither fits a model nor loads census
records, predicts labels, recomputes inference, or changes historical decisions.
Unlike reaggregation, it may deserialize exactly the two preselected seed-41001
bundles. The immutable row's independently retained SHA-256 authenticates the
model digests; hashing metadata alone would not make arbitrary pickle safe.
Run this step without a GitHub token on the disposable read-only CI runner.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
from io import BytesIO
import math
import os
from pathlib import Path
import statistics

from evidence_audit import thesis_tables as tables

EXAMPLE_SEED = 41001
REPOSITORY = "ChepaMaksym/GA-article-test"
EXPECTED_LEDGER_SHA = "819d19681a05946a330bc87c07947acd61abd67bf729b618d9483f02880e4680"
EXAMPLE_ROW_SHA = "559de79c7520895567ccba3a8a2205b37def620a9608c39f1efee1c77d4e7dc0"
ARM_LABELS = {"chc_harmonized": "Базовий CHC", "lambda_no_reset": "Адаптивний алгоритм"}
CLASS_LABELS = ("Клас 0: дохід до порога", "Клас 1: дохід понад поріг")
METRIC_FIELDS = ("precision", "recall", "f1", "support")
NOTE = (
    "Опис збережених результатів усіх 30 пар без повторного навчання або "
    "прогнозування. Матриці різних моделей не об'єднано в одну вибірку. "
    "Зважені елементи є сумами ваг, а не кількістю людей. Історичний "
    "висновок FAIL_NONINFERIORITY та обмеження подальших заяв не змінено."
)
RAW_NAMES_UK = (
    "Вік", "Категорія працівника", "Детальний код галузі", "Детальний код професії",
    "Освіта", "Погодинна оплата", "Навчання попереднього тижня", "Сімейний стан",
    "Укрупнена галузь", "Укрупнена професія", "Расова категорія", "Іспаномовне походження",
    "Стать", "Членство у профспілці", "Причина безробіття", "Статус зайнятості",
    "Прибуток від капіталу", "Збитки від капіталу", "Дивіденди", "Статус податкової декларації",
    "Регіон попереднього проживання", "Штат попереднього проживання", "Детальний сімейний статус",
    "Узагальнений статус у домогосподарстві", "Вага спостереження",
    "Переміщення між агломераціями", "Зміна регіону", "Переміщення в межах регіону",
    "Проживання в тому самому житлі рік тому", "Попереднє проживання в Сонячному поясі",
    "Кількість осіб у роботодавця", "Сімейна категорія для осіб до 18 років",
    "Країна народження батька", "Країна народження матері", "Країна народження особи",
    "Громадянство", "Власна справа або самозайнятість", "Участь в опитуванні щодо виплат ветеранам",
    "Ветеранські пільги", "Тижні роботи протягом року", "Рік спостереження",
)


def _require(condition, message):
    if not condition:
        raise ValueError(message)


def _number(value):
    _require(type(value) in (int, float) and math.isfinite(value) and value >= 0,
             "matrix/support must be finite nonnegative numbers")
    return float(value)


def _close(left, right, message):
    _require(math.isclose(left, right, rel_tol=1e-10, abs_tol=1e-9), message)


def class_metrics(block, *, weighted):
    """Derive both classes from [[TN, FP], [FN, TP]], zero_division=0."""
    matrix = block["confusion_matrix"]
    _require(isinstance(matrix, list) and len(matrix) == 2
             and all(isinstance(row, list) and len(row) == 2 for row in matrix),
             "confusion matrix must have shape 2 by 2")
    tn, fp, fn, tp = [_number(value) for row in matrix for value in row]
    if not weighted:
        _require(all(value.is_integer() for value in (tn, fp, fn, tp)),
                 "unweighted confusion matrix must contain record counts")
        _require(tn + fp + fn + tp == 99762, "unweighted official-test total mismatch")
    _require(tn + fp > 0 and fn + tp > 0, "both true classes require positive support")
    _close(tn + fp, _number(block["negative_support"]), "class-0 support mismatch")
    _close(fn + tp, _number(block["positive_support"]), "class-1 support mismatch")
    rows = []
    for label, correct, false_positive, false_negative in ((0, tn, fn, fp), (1, tp, fp, fn)):
        predicted = correct + false_positive
        support = correct + false_negative
        denominator = 2 * correct + false_positive + false_negative
        rows.append({
            "class": label, "precision": correct / predicted if predicted else 0.0,
            "recall": correct / support if support else 0.0,
            "f1": 2 * correct / denominator if denominator else 0.0, "support": support,
        })
    for key, observed in (("precision_positive", rows[1]["precision"]),
                          ("recall_positive", rows[1]["recall"]), ("f1_positive", rows[1]["f1"]),
                          ("balanced_accuracy", (rows[0]["recall"] + rows[1]["recall"]) / 2),
                          ("accuracy", (tn + tp) / (tn + fp + fn + tp))):
        _close(tables._score(block[key]), observed, f"saved {key} disagrees with matrix")
    return rows


def feature_mapping():
    """One mask bit maps to one transformed variable, not one category."""
    from corrected_applied import data_protocol as data
    _require(len(RAW_NAMES_UK) == len(data.RAW_FEATURE_NAMES), "translated feature map mismatch")
    _require(len(data.TRANSFORMED_FEATURE_NAMES) == 40
             and set(data.TRANSFORMED_PREDICTIVE_RAW_INDICES) == set(data.PREDICTIVE_RAW_INDICES),
             "canonical transformed feature map mismatch")
    return [{
        "mask_bit_1_based": index + 1, "mask_index_0_based": index,
        "raw_index_0_based": raw, "predictor_number_raw_order_1_based": data.PREDICTIVE_RAW_INDICES.index(raw) + 1,
        "feature_name": name, "feature_name_uk": RAW_NAMES_UK[raw],
        "encoding": "standardized_numeric" if raw in data.NUMERIC_RAW_INDICES else "ordinal_category",
    } for index, (raw, name) in enumerate(zip(data.TRANSFORMED_PREDICTIVE_RAW_INDICES,
                                             data.TRANSFORMED_FEATURE_NAMES))]


def load_class_data(rows_dir, expected_path, verified_path):
    """Authenticate every campaign input before interpreting class matrices."""
    _require(tables.source._file_sha256(expected_path) == EXPECTED_LEDGER_SHA,
             "frozen expected artifact ledger SHA mismatch")
    _, _, provenance = tables.load_pairs(rows_dir, expected_path, verified_path)
    paths = {Path(item["path"]).name: rows_dir / item["path"] for item in provenance["inputs"]}
    mapping = feature_mapping()
    names = [item["feature_name"] for item in mapping]
    metrics, examples, supports = [], {}, {}
    for seed in tables.source.EXPECTED_SEEDS:
        row = tables.source._load_json(paths[f"seed-{seed}.json"])
        if seed == EXAMPLE_SEED:
            _require(tables.source._file_sha256(paths[f"seed-{seed}.json"]) == EXAMPLE_ROW_SHA,
                     "preselected immutable example row SHA mismatch")
        for arm, suffix in zip(tables.ARMS, ("chc", "lambda")):
            terminal = row["arms"][arm]["terminal"]
            mask = terminal["mask"]
            _require(isinstance(mask, list) and len(mask) == 40
                     and all(type(bit) is int and bit in (0, 1) for bit in mask)
                     and sum(mask) == terminal["selected_feature_count"], "terminal mask mismatch")
            model = row["models"][arm]
            model_path = paths[f"seed-{seed}-{suffix}-model.joblib"]
            _require(model["schema"] == "eu26-21-common-bridge-model-evidence-v1"
                     and model["seed"] == seed and model["arm"] == arm and model["mask"] == mask
                     and model["file"] == model_path.name
                     and model["bytes"] == model_path.stat().st_size
                     and model["sha256"] == tables.source._file_sha256(model_path),
                     "saved model identity/bytes mismatch")
            _require(model["selected_feature_names"] == [name for bit, name in zip(mask, names) if bit],
                     "saved selected feature names mismatch")
            _require(row["arms"][arm]["test_evaluations"] == 1, "historical test-call contract mismatch")
            blocks = terminal["test_metrics"]
            _require(set(blocks) == {"weighted", "unweighted", "selected_feature_count",
                                    "selected_predictive_indices", "selected_raw_indices", "selected_feature_names"},
                     "test metric blocks mismatch")
            selected = [index for index, bit in enumerate(mask) if bit]
            _require(blocks["selected_feature_count"] == sum(mask)
                     and blocks["selected_predictive_indices"] == selected
                     and blocks["selected_raw_indices"] == [mapping[index]["raw_index_0_based"] for index in selected]
                     and blocks["selected_feature_names"] == model["selected_feature_names"],
                     "test metric selected feature mapping mismatch")
            _close(terminal["test_weighted_balanced_accuracy"], blocks["weighted"]["balanced_accuracy"],
                   "terminal WBA mismatch")
            for weighting in ("weighted", "unweighted"):
                derived = class_metrics(blocks[weighting], weighted=weighting == "weighted")
                for item in derived:
                    key = weighting, item["class"]
                    if key in supports:
                        _close(supports[key], item["support"], "official-test support changes across models")
                    else:
                        supports[key] = item["support"]
                    metrics.append({"seed": seed, "arm": arm, "weighting": weighting, **item})
            if seed == EXAMPLE_SEED:
                examples[arm] = {"row": row, "row_path": paths[f"seed-{seed}.json"],
                                 "model_path": model_path, "model_metadata": model,
                                 "test_metrics": blocks}
    _require(len(metrics) == 240, "all 30 pairs and both classes/weightings are required")
    return metrics, examples, mapping, provenance


def _load_authenticated_model(example, arm):
    """The only deserialization boundary: two independently pinned CI inputs."""
    _require(os.environ.get("GITHUB_ACTIONS") == "true"
             and os.environ.get("GITHUB_REPOSITORY") == REPOSITORY,
             "saved-tree deserialization is restricted to the named repository's CI")
    row, metadata = example["row"], example["model_metadata"]
    _require(tables.source._file_sha256(example["row_path"]) == EXAMPLE_ROW_SHA
             and tables.source._load_json(example["row_path"]) == row,
             "immutable model-authenticating row changed")
    _require(row["seed"] == EXAMPLE_SEED and arm in tables.ARMS
             and row["models"][arm] == metadata, "preselected model mismatch")
    provenance = row["provenance"]
    for key, expected in {"run_id": tables.RUN_ID, "run_attempt": 1,
                          "implementation_sha": tables.SOURCE_SHA, "workflow_sha": tables.SOURCE_SHA,
                          "protocol_sha256": tables.PROTOCOL_SHA, "ref": tables.SOURCE_REF}.items():
        _require(provenance.get(key) == expected, f"model source {key} mismatch")
    # Read once and deserialize those exact hashed bytes, preventing a path swap
    # between verification and joblib.load. Never accept arbitrary pickle paths.
    content = example["model_path"].read_bytes()
    _require(len(content) == metadata["bytes"]
             and hashlib.sha256(content).hexdigest() == metadata["sha256"],
             "model bytes changed before deserialization")
    import joblib
    bundle = joblib.load(BytesIO(content))  # nosec B301: two immutable, pinned producer artifacts only
    _require(bundle["schema"] == "eu26-21-common-bridge-model-evidence-v1"
             and bundle["seed"] == EXAMPLE_SEED and bundle["arm"] == arm
             and bundle["mask"] == metadata["mask"], "deserialized model identity mismatch")
    for key, expected in {"implementation_sha": tables.SOURCE_SHA, "protocol_sha256": tables.PROTOCOL_SHA,
                          "run_id": tables.RUN_ID, "workflow_sha": tables.SOURCE_SHA}.items():
        _require(bundle["provenance"].get(key) == expected, f"bundle source {key} mismatch")
    return bundle


def describe_tree(bundle, mapping, *, compressed_bytes):
    """Inspect saved arrays and preprocessing parameters; do not call predict."""
    from sklearn.compose import ColumnTransformer
    from sklearn.tree import DecisionTreeClassifier
    model, preprocessor = bundle["classifier"], bundle["preprocessor"]
    _require(type(model) is DecisionTreeClassifier and type(preprocessor) is ColumnTransformer,
             "unexpected saved estimator types")
    selected = bundle["selected_indices"]
    _require(selected == [index for index, bit in enumerate(bundle["mask"]) if bit]
             and model.n_features_in_ == len(selected)
             and bundle["feature_names"] == [item["feature_name"] for item in mapping],
             "tree/selected feature mapping mismatch")
    _require(model.classes_.tolist() == [0, 1], "tree class ordering mismatch")
    tree, nodes = model.tree_, []
    queue = [(0, 0)]
    while queue:
        node, depth = queue.pop(0)
        left, right = int(tree.children_left[node]), int(tree.children_right[node])
        values = tree.value[node].reshape(-1).tolist()
        payload = {"node": node, "depth": depth, "left": left, "right": right,
                   "leaf": left == -1, "gini": float(tree.impurity[node]),
                   "training_records": int(tree.n_node_samples[node]),
                   "training_weight_sum": float(tree.weighted_n_node_samples[node]),
                   "stored_class_values": values,
                   "prediction_class": model.classes_[max(range(len(values)), key=values.__getitem__)].item()}
        if left != -1:
            local = int(tree.feature[node])
            feature = mapping[selected[local]]
            threshold = float(tree.threshold[node])
            payload.update(feature, classifier_feature_index_0_based=local, threshold_processed=threshold)
            if feature["encoding"] == "standardized_numeric":
                numeric_index = feature["mask_index_0_based"]
                scaler = preprocessor.named_transformers_["numeric"].named_steps["scale"]
                payload["threshold_original_numeric"] = float(
                    threshold * scaler.scale_[numeric_index] + scaler.mean_[numeric_index])
            else:
                category_index = feature["mask_index_0_based"] - 7
                encoder = preprocessor.named_transformers_["categorical"].named_steps["ordinal"]
                categories = encoder.categories_[category_index].tolist()
                payload["categories_left"] = [str(value) for index, value in enumerate(categories) if index <= threshold]
                payload["categories_right"] = [str(value) for index, value in enumerate(categories) if index > threshold]
                payload["unknown_category_code"] = -1
            if depth < 2:
                queue.extend(((left, depth + 1), (right, depth + 1)))
        nodes.append(payload)
    state = tree.__getstate__()
    array_bytes = {key: int(state[key].nbytes) for key in ("nodes", "values")}
    return {
        "schema": "eu26-21-saved-tree-description-v1", "seed": EXAMPLE_SEED, "arm": bundle["arm"],
        "mask": bundle["mask"], "selected_indices": selected,
        "selected_feature_names": [mapping[index]["feature_name"] for index in selected],
        "selected_feature_names_uk": [mapping[index]["feature_name_uk"] for index in selected],
        "classifier_parameters": model.get_params(deep=False), "node_count": int(tree.node_count),
        "max_depth": int(tree.max_depth), "leaf_count": int(model.get_n_leaves()),
        "tree_state_array_bytes": array_bytes, "tree_state_arrays_total_bytes": sum(array_bytes.values()),
        "compressed_bundle_bytes": compressed_bytes, "is_process_rss_measurement": False,
        "shown_depths": [0, 1, 2], "top_three_levels": nodes,
        "categorical_threshold_interpretation": "Codes encode categories, not a natural semantic ordering; unknown code -1 goes left at nonnegative thresholds.",
        "numeric_threshold_interpretation": "Raw numeric thresholds invert the saved scaler; training imputation still applies.",
        "tree_arrays_memory_interpretation": "Nodes and values arrays only; excludes Python objects, preprocessor, training matrices and temporary memory.",
    }


def summarize_metrics(metrics):
    summary = []
    for arm in tables.ARMS:
        for weighting in ("weighted", "unweighted"):
            for label in (0, 1):
                rows = [row for row in metrics if row["arm"] == arm
                        and row["weighting"] == weighting and row["class"] == label]
                _require([row["seed"] for row in rows] == list(tables.source.EXPECTED_SEEDS),
                         "class summary must retain every ordered seed")
                summary.append({"arm": arm, "weighting": weighting, "class": label, "models": len(rows),
                                **{key: {"median": statistics.median(row[key] for row in rows),
                                         "minimum": min(row[key] for row in rows),
                                         "maximum": max(row[key] for row in rows)} for key in METRIC_FIELDS}})
    return summary


def _csv(path, rows):
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def _plot_confusion(examples, weighting, output):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(1, 2, figsize=(10, 4.8), layout="constrained")
    unit = "суми ваг" if weighting == "weighted" else "кількість записів"
    for axis, arm in zip(axes, tables.ARMS):
        matrix = examples[arm]["test_metrics"][weighting]["confusion_matrix"]
        axis.imshow(matrix, cmap="Blues")
        for actual in range(2):
            for predicted in range(2):
                value = matrix[actual][predicted]
                label = f"{value:,.1f}" if weighting == "weighted" else f"{value:,.0f}"
                axis.text(predicted, actual, label.replace(",", " "), ha="center", va="center",
                          color="white" if value > max(max(row) for row in matrix) / 2 else "black")
        axis.set(xticks=[0, 1], yticks=[0, 1], xticklabels=["Клас 0", "Клас 1"],
                 yticklabels=["Клас 0", "Клас 1"], xlabel="Прогнозований клас",
                 ylabel="Відомий клас", title=ARM_LABELS[arm])
    fig.suptitle(f"Пара 41001: матриці помилок ({unit})")
    fig.savefig(output, dpi=170)
    plt.close(fig)


def _plot_tree(bundle, description, output):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, axis = plt.subplots(figsize=(16, 8), layout="constrained")
    nodes = {node["node"]: node for node in description["top_three_levels"]}
    positions = {0: (0.5, 0.85)}
    for node in description["top_three_levels"]:
        index, depth = node["node"], node["depth"]
        x, y = positions[index]
        if node["leaf"]:
            title = f"Листок: клас {node['prediction_class']}"
        elif node["encoding"] == "standardized_numeric":
            threshold_label = f"{node['threshold_original_numeric']:.3f}".rstrip("0").rstrip(".").replace(".", ",")
            title = f"{node['feature_name_uk']}\n≤ {threshold_label}"
        else:
            threshold_label = f"{node['threshold_processed']:.3f}".rstrip("0").rstrip(".").replace(".", ",")
            title = f"{node['feature_name_uk']}\nкод ≤ {threshold_label}"
        text = f"{title}\nНавчальних записів: {node['training_records']}"
        axis.text(x, y, text, ha="center", va="center", fontsize=9,
                  bbox={"boxstyle": "round,pad=0.6", "facecolor": "#deebf7", "edgecolor": "#52718d"})
        if node["leaf"]:
            continue
        for child, direction, label in ((node["left"], -1, "так"), (node["right"], 1, "ні")):
            child_x, child_y = x + direction / 2 ** (depth + 2), y - 0.26
            if child in nodes:
                positions[child] = child_x, child_y
                axis.annotate("", xy=(child_x, child_y + 0.07), xytext=(x, y - 0.07),
                              arrowprops={"arrowstyle": "->", "color": "#52718d"})
                if depth == 0:
                    axis.text((x + child_x) / 2, (y + child_y) / 2, label, fontsize=9)
            else:
                axis.text(x + direction * 0.035, y - 0.14, "…", ha="center", va="center", fontsize=18)
    axis.set(xlim=(0, 1), ylim=(0, 1))
    axis.axis("off")
    axis.set_title(f"{ARM_LABELS[bundle['arm']]}: перші три рівні навченого дерева, пара 41001")
    fig.text(0.5, 0.02, "Числові пороги повернуто до вихідної шкали й округлено; коди категорій не означають природного порядку.",
             ha="center", fontsize=10)
    fig.savefig(output, dpi=160)
    plt.close(fig)


def write_report(metrics, examples, mapping, provenance, output_dir):
    """Require authentication before loading bundles or creating outputs."""
    summary = summarize_metrics(metrics)
    bundles, trees = {}, {}
    for arm in tables.ARMS:
        bundles[arm] = _load_authenticated_model(examples[arm], arm)
        trees[arm] = describe_tree(bundles[arm], mapping, compressed_bytes=examples[arm]["model_metadata"]["bytes"])
        _require(trees[arm]["classifier_parameters"] == examples[arm]["model_metadata"]["classifier_parameters"],
                 "saved classifier parameters mismatch")
    output_dir.mkdir(parents=True, exist_ok=False)
    _csv(output_dir / "per-class-metrics.csv", metrics)
    _csv(output_dir / "feature-map.csv", mapping)
    tables.source._write_json(output_dir / "class-summary.json", {
        "schema": "eu26-21-descriptive-class-summary-v1", "metric_scale": "0_to_1",
        "zero_division": 0, "confusion_matrix_order": "rows=true, columns=predicted, classes=[0,1]",
        "class_labels": list(CLASS_LABELS), "summaries": summary,
        "example_seed": EXAMPLE_SEED,
        "example_confusion_matrices": {arm: {weighting: examples[arm]["test_metrics"][weighting]["confusion_matrix"]
                                            for weighting in ("weighted", "unweighted")} for arm in tables.ARMS},
        "matrices_pooled": False, "interpretation": NOTE,
    })
    tables.source._write_json(output_dir / "tree-details.json", trees)
    for weighting in ("weighted", "unweighted"):
        _plot_confusion(examples, weighting, output_dir / f"sample-confusion-{weighting}.png")
    for arm, suffix in zip(tables.ARMS, ("chc", "lambda")):
        _plot_tree(bundles[arm], trees[arm], output_dir / f"tree-{suffix}-41001.png")
    lines = ["# Покласові показники та фактичні дерева рішень", "", NOTE, "",
             "Нижче наведено медіани показників 30 окремих моделей кожного методу, а не показники об'єднаної матриці.", "",
             "| Метод | Урахування ваг | Клас | Точність прогнозів класу | Повнота | F1 |",
             "| --- | --- | ---: | ---: | ---: | ---: |"]
    for row in summary:
        lines.append(f"| {ARM_LABELS[row['arm']]} | {'Зважено' if row['weighting'] == 'weighted' else 'Без ваг'} | {row['class']} | "
                     + " | ".join(f"{100 * row[key]['median']:.4f}%" for key in ("precision", "recall", "f1")) + " |")
    lines += ["", "Точність прогнозів класу показує частку правильних відповідей серед прогнозів цього класу. "
              "Повнота показує частку знайдених записів серед усіх записів цього класу. F1 є їх гармонійним середнім. "
              "WBA є середнім двох зважених значень повноти; вона не дорівнює загальній частці правильних прогнозів.", "",
              "## Пара 41001, обрана до підготовки зображень", "",
              "![Матриці: кількість записів](sample-confusion-unweighted.png)", "",
              "![Матриці: суми ваг](sample-confusion-weighted.png)", "",
              "Ці рисунки описують одну наперед визначену пару. Порівняння методів ґрунтується на всіх 30 парах; "
              "приклад не відібрано за найкращим результатом.", "",
              "## Фактичні фінальні дерева", "",
              "Показано корінь і два наступні рівні. Нижні гілки продовжуються; це не повне дерево й не навчальна схема. "
              "Дерева вже навчено на внутрішній навчальній вибірці. Для цих рисунків моделі не навчали й тестових записів не читали.", "",
              "| Метод | Ознак у масці | Вузлів | Листків | Глибина | Масиви дерева, байт | Стиснений комплект, байт |",
              "| --- | ---: | ---: | ---: | ---: | ---: | ---: |"]
    for arm in tables.ARMS:
        tree = trees[arm]
        lines.append(f"| {ARM_LABELS[arm]} | {sum(tree['mask'])} | {tree['node_count']} | {tree['leaf_count']} | "
                     f"{tree['max_depth']} | {tree['tree_state_arrays_total_bytes']} | {tree['compressed_bundle_bytes']} |")
    lines += ["", "Обсяг масивів стосується лише структури вузлів і значень класів. "
              "Стиснений комплект містить також перетворення ознак і метадані. Жоден показник не є вимірюванням повної оперативної пам'яті процесу.", "",
              "![Фактичне дерево CHC](tree-chc-41001.png)", "",
              "![Фактичне дерево адаптивного алгоритму](tree-lambda-41001.png)", "",
              "Числові пороги на рисунках повернуто до вихідної шкали за збереженими параметрами перетворення й округлено. "
              "Точні пороги обох шкал збережено в tree-details.json. Категоріальні пороги розділяють порядкові коди, а не природно впорядковані категорії. "
              "Відповідність усіх 40 бітів назвам і вихідним стовпцям наведено у feature-map.csv.", "",
              "*Покласові показники є описовим доповненням завершеної серії. Вони не змінюють перевірки непоступливості "
              "й не підтверджують причинного впливу адаптації або виходу з локального оптимуму.*", ""]
    (output_dir / "report.md").write_text("\n".join(lines), encoding="utf-8")
    tables.source._write_json(output_dir / "class-tree-manifest.json", {
        "schema": "eu26-21-descriptive-class-tree-report-v1", **provenance,
        "protocol_id": tables.PROTOCOL_ID, "example_seed": EXAMPLE_SEED,
        "authenticated_example_row_sha256": EXAMPLE_ROW_SHA,
        "model_load_policy": "Only two seed-41001 bundles bound by a separately pinned source-row SHA and complete authenticated artifact ledger, on disposable named-repository CI without a token in this step.",
        "model_fit_calls": 0, "model_predict_calls": 0, "test_dataset_reads": 0,
        "model_bundles_deserialized": 2, "seed_ledger": list(tables.source.EXPECTED_SEEDS),
        "scientific_decisions_changed": False, "scientific_decisions_recomputed": False,
        "matrices_pooled": False, "interpretation": NOTE,
        "report_run": {key: os.environ[key] for key in (
            "GITHUB_REPOSITORY", "GITHUB_RUN_ID", "GITHUB_RUN_ATTEMPT", "GITHUB_SHA",
            "GITHUB_REF", "THESIS_WORKFLOW_SHA")},
        "outputs": {path.name: {"bytes": path.stat().st_size, "sha256": tables.source._file_sha256(path)}
                    for path in sorted(output_dir.iterdir())},
    })


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("rows-dir", "expected-ledger", "verified-ledger", "output-dir"):
        parser.add_argument(f"--{name}", type=Path, required=True)
    args = parser.parse_args()
    _require(os.environ.get("GITHUB_ACTIONS") == "true"
             and os.environ.get("GITHUB_REPOSITORY") == REPOSITORY,
             "historical class/tree reporting is CI-only")
    values = load_class_data(args.rows_dir, args.expected_ledger, args.verified_ledger)
    write_report(*values, args.output_dir)


if __name__ == "__main__":
    main()
