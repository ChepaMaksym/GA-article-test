"""CI-only report fixtures; no real Census training or scientific claims."""
from copy import deepcopy
import inspect
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from lambda_response_study import aggregate as reporting  # noqa: E402
from lambda_response_study import artifacts  # noqa: E402
from lambda_response_study.contract import ARMS, CASE_SEEDS, PROBLEMS, file_sha256, read_json, write_json, write_manifest  # noqa: E402
from lambda_response_study.search import run_search  # noqa: E402
from local_optima_study.contract import per_class_metrics  # noqa: E402
from test_lambda_response_artifacts import (  # noqa: E402
    SHA, RUN_ID, metadata, preparation, prepare_registry, provenance, sources, transport,
)


def metrics():
    result = {}
    for scale in ("weighted", "unweighted"):
        matrix = [[85000, 5000], [4000, 5762]]
        if scale == "weighted":
            matrix = [[float(value) * 2 for value in row] for row in matrix]
        classes = per_class_metrics(matrix)
        result[scale] = {"confusion_matrix": matrix, "classes": classes,
                         "balanced_accuracy": sum(item["recall"] for item in classes.values()) / 2,
                         "accuracy": (matrix[0][0] + matrix[1][1]) / sum(map(sum, matrix))}
    return result


def fixture_traces():
    result = {}
    for problem in PROBLEMS:
        objective = (lambda mask: sum(mask) / 40) if problem == "onemax" else (lambda mask: .5 + .005 * sum(mask) if sum(mask) else 0)
        initial = [0] * 40 if problem == "onemax" else preparation(45001)["initial"]["mask"]
        initial_score = 0 if problem == "onemax" else .505
        result[problem] = {"arms": {arm: run_search(objective, problem=problem, arm=arm,
            initial_mask=initial, initial_score=initial_score,
            search_seed=45001 + (1000003 if problem == "onemax" else 2000003)) for arm in ARMS}}
    return result


def write_case(directory, registry, registry_path, problems):
    seed = 45001
    directory.mkdir()
    entry = registry["cases"][0]
    source_preparation = {"registry_sha256": file_sha256(registry_path), **{key: entry[key]
        for key in ("preparation", "source_run_id", "source_artifact_id", "source_artifact_name", "source_artifact_digest")}}
    traces = {}
    for problem in PROBLEMS:
        traces[problem] = {}
        for arm in ARMS:
            name = f"trace-{problem}-{arm}.json"
            traces[problem][arm] = {"file": name, **write_json(directory / name, problems[problem]["arms"][arm])}
    final = {arm: problems["census"]["arms"][arm]["final"] for arm in ARMS}
    freeze = {"schema": "eu26-21-lr-terminal-freeze-v1", "seed": seed, "provenance": provenance(),
              "preparation": source_preparation, "parents": final,
              "selected_by": "accepted_parent_after_generation_20", "test_evaluations_so_far": 0}
    freeze_identity = {"file": "terminal-masks.json", **write_json(directory / "terminal-masks.json", freeze)}
    models = {}
    for arm in ARMS:
        path = directory / f"model-{arm}.joblib"
        path.write_bytes(b"fixture-not-a-model-never-deserialized")
        models[arm] = {"file": path.name, "sha256": file_sha256(path), "bytes": path.stat().st_size,
                       "seed": seed, "arm": arm, "mask": final[arm]["mask"],
                       "selected_feature_names": [name for name, bit in zip(reporting.TRANSFORMED_FEATURE_NAMES, final[arm]["mask"]) if bit],
                       "classifier": "DecisionTreeClassifier(random_state=0)",
                       "preprocessing_fit_partition": "internal_training_only", "terminal_fit_partition": "internal_training_only",
                       "reload_verification": "PASS_EXACT_NON_TEST_PROBE", "test_access_during_reload": False}
    row = {"schema": "eu26-21-lr-case-v1", "status": "PASS_CASE", "seed": seed,
           "provenance": provenance(), "preparation": source_preparation, "training_data": metadata(seed),
           "initial": preparation(seed)["initial"], "problems": problems, "traces": traces,
           "final_masks_freeze": freeze_identity, "models": models, "test_metrics": {arm: metrics() for arm in ARMS},
           "test_evaluations": {arm: 1 for arm in ARMS},
           "counts": {"preparation_calls": 40,
                      "search_calls": sum(trace["counts"]["physical_calls"] for problem in problems.values() for trace in problem["arms"].values()),
                      "search_tree_fits": sum(trace["counts"]["actual_tree_fits"] for trace in problems["census"]["arms"].values()),
                      "test_evaluations": 2}}
    write_json(directory / "case.json", row)
    write_manifest(directory, seed=seed, kind="case", provenance=provenance())
    return row


class LambdaResponseAggregateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.problems = fixture_traces()

    def test_confusion_metrics_recomputed_and_integer_records_required(self):
        reporting.validate_metrics(metrics())
        for change in ("precision", "rows", "fractional", "negative"):
            with self.subTest(change=change):
                bad = metrics()
                if change == "precision":
                    bad["weighted"]["classes"]["1"]["precision"] += .01
                elif change == "rows":
                    bad["unweighted"]["confusion_matrix"][0][0] -= 1
                elif change == "fractional":
                    bad["unweighted"]["confusion_matrix"][0][0] = 85000.0
                else:
                    bad["weighted"]["confusion_matrix"][0][0] = -1
                with self.assertRaises(ValueError):
                    reporting.validate_metrics(bad)

    def test_case_bytes_traces_masks_and_freeze_authenticated(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            preps = root / "preps"
            preps.mkdir()
            registry = prepare_registry(preps)
            registry_path = root / "registry.json"
            write_json(registry_path, registry)
            source = sources(kind="case")["artifacts"][0]
            directory = root / source["name"]
            row = write_case(directory, registry, registry_path, deepcopy(self.problems))
            result = reporting.validate_case(directory, source, registry, file_sha256(registry_path),
                expected_sha=SHA, seed=45001, preparation=registry["cases"][0]["payload"])
            self.assertEqual(result, row)
            self.assertEqual(result["counts"]["test_evaluations"], 2)
            # These bytes are not a joblib object; successful validation proves that
            # downloaded model bytes are authenticated, not deserialized.
            (directory / "model-adaptive.joblib").write_bytes(b"changed")
            with self.assertRaisesRegex(ValueError, "checksum"):
                reporting.validate_case(directory, source, registry, file_sha256(registry_path),
                    expected_sha=SHA, seed=45001, preparation=registry["cases"][0]["payload"])

    def test_wrong_preparation_or_duplicate_test_count_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            preps = root / "preps"
            preps.mkdir()
            registry = prepare_registry(preps)
            registry_path = root / "registry.json"
            write_json(registry_path, registry)
            source = sources(kind="case")["artifacts"][0]
            directory = root / source["name"]
            row = write_case(directory, registry, registry_path, deepcopy(self.problems))
            for problem in ("registry", "test_count", "trace_summary", "first_generation"):
                with self.subTest(problem=problem):
                    bad = deepcopy(row)
                    if problem == "registry":
                        bad["preparation"]["registry_sha256"] = "d" * 64
                    elif problem == "test_count":
                        bad["test_evaluations"]["adaptive"] = 2
                    elif problem == "trace_summary":
                        bad["problems"]["census"]["arms"]["adaptive"]["final"]["score"] += .01
                    else:
                        bad["problems"]["onemax"]["arms"]["fixed10"]["rng_initial_state"]["state"]["state"] += 1
                    write_json(directory / "case.json", bad)
                    (directory / "manifest.json").unlink()
                    write_manifest(directory, seed=45001, kind="case", provenance=provenance())
                    with self.assertRaises(ValueError):
                        reporting.validate_case(directory, source, registry, file_sha256(registry_path),
                            expected_sha=SHA, seed=45001, preparation=registry["cases"][0]["payload"])

    def test_all_thirty_and_flat_runs_retained_descriptively(self):
        rows = [{"seed": seed, "problems": deepcopy(self.problems), "test_metrics": {arm: metrics() for arm in ARMS},
                 "counts": {"preparation_calls": 40, "test_evaluations": 2}} for seed in CASE_SEEDS]
        # Descriptive function is separate from proof validation. A flat outcome
        # is deliberately injected here to test counting, not claimed as evidence.
        rows[-1]["problems"]["census"]["arms"]["adaptive"]["final"]["score"] = .505
        summary = reporting.describe(rows)
        self.assertEqual(summary["cases_accounted"], 30)
        self.assertEqual(summary["test_evaluations"], 60)
        self.assertEqual(summary["preparation_calls"], 1200)
        self.assertEqual(summary["problems"]["census"]["arms"]["adaptive"]["cases_without_parent_improvement"], 1)
        self.assertFalse(summary["hypothesis_tests"])
        self.assertFalse(summary["equal_objective_budget"])
        self.assertFalse(any(summary["claims"].values()))
        self.assertEqual(summary["example_seed"], 45001)

    def test_complete_report_outputs_and_byte_manifest(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            preps = root / "preps"
            preps.mkdir()
            registry = prepare_registry(preps)
            registry_path, source_path, ledger_path = root / "registry.json", root / "sources.json", root / "transport.json"
            write_json(registry_path, registry)
            selected = sources(kind="case")
            write_json(source_path, selected)
            write_json(ledger_path, transport(selected))
            def validated_fixture(directory, source, frozen, frozen_sha, *, expected_sha, seed, preparation):
                return {"seed": seed, "status": "PASS_CASE", "problems": deepcopy(self.problems),
                        "test_metrics": {arm: metrics() for arm in ARMS},
                        "counts": {"preparation_calls": 40, "test_evaluations": 2}}
            output = root / "report"
            with patch.object(reporting, "authenticate", return_value=({}, provenance())), \
                 patch.object(reporting, "validate_case", side_effect=validated_fixture) as case_check:
                summary = reporting.aggregate(root=root / "cases", registry_path=registry_path, sources_path=source_path,
                    transport_path=ledger_path, expected_sha=SHA, output=output)
            self.assertEqual(case_check.call_count, 30)
            self.assertEqual(summary["cases_accounted"], 30)
            self.assertEqual(len(list(output.glob("*.png"))), 8)
            self.assertEqual((output / "registry.json").read_bytes(), registry_path.read_bytes())
            manifest = read_json(output / "report-manifest.json")
            self.assertNotIn("report-manifest.json", manifest["files"])
            self.assertEqual(len(manifest["source_case_artifact_ids"]), 30)
            self.assertEqual(len(manifest["source_preparation_artifact_ids"]), 30)
            for name, identity in manifest["files"].items():
                self.assertEqual(identity["sha256"], file_sha256(output / name))
                self.assertEqual(identity["bytes"], (output / name).stat().st_size)
            text = (output / "RESULTS_UK.md").read_text(encoding="utf-8")
            self.assertIn("не є виміряною WBA", text)
            self.assertIn("не встановлює статистичної переваги", text)
            self.assertEqual(len((output / "cases.csv").read_text(encoding="utf-8").splitlines()), 121)
            self.assertEqual(len((output / "events.csv").read_text(encoding="utf-8").splitlines()), 2401)

    def test_plot_does_not_hide_adverse_or_call_penalty_measured_wba(self):
        row = {"problems": deepcopy(self.problems)}
        trace = row["problems"]["census"]["arms"]["adaptive"]
        trace["evaluations"][0].update({"kind": "empty_penalty", "score": 0, "mask": [0] * 40})
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary)
            reporting.plot_example(output, row, problem="census")
            self.assertEqual(len(list(output.glob("*.png"))), 3)
        source = inspect.getsource(reporting.plot_example)
        self.assertIn('point["kind"] != "empty_penalty"', source)
        self.assertIn("Порожня маска: штраф, не WBA", source)
        self.assertIn('trace["evaluations"]', source)
        self.assertIn("OUTCOME_COLORS[outcome(event)]", source)

    def test_incomplete_case_sources_rejected_before_report_written(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            selected = sources(kind="case")
            selected["artifacts"].pop()
            source_path = root / "sources.json"
            registry_path = root / "registry.json"
            write_json(source_path, selected)
            write_json(registry_path, {})
            output = root / "report"
            with patch.object(reporting, "authenticate", return_value=({}, provenance())), self.assertRaises(ValueError):
                reporting.aggregate(root=root, registry_path=registry_path, sources_path=source_path,
                    transport_path=root / "absent.json", expected_sha=SHA, output=output)
            self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main()
