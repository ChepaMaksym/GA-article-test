"""CI-only synthetic runner-to-report checks of actual persisted evidence.

No Census records, tree fitting, downloaded pickle loading, or scientific
outcomes are used. Search, certification, preparation replay, manifests,
accounting, and report validators use their production implementations.
"""
from __future__ import annotations

from contextlib import ExitStack
import copy
import csv
import gzip
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from corrected_applied.data_protocol import TRANSFORMED_FEATURE_NAMES  # noqa: E402
from chc_qx_alignment_study import aggregate, artifacts, contract, data, run_case, source_gate  # noqa: E402
from chc_qx_alignment_study.diagnostics import certify_snapshot  # noqa: E402
from local_optima_study.contract import per_class_metrics  # noqa: E402


SHA = "a" * 40
RUN_ID = 3
ATTEMPT = 1


def _native_fixture():
    """Exercise the native adapter while retaining a stable scored population."""
    from deap import base

    class ScalarFitness(base.Fitness):
        weights = (1.0,)

    class Individual(list):
        def __init__(self, values=()):
            super().__init__(values)
            self.fitness = ScalarFitness()

    def create_toolbox(*_arguments):
        toolbox = base.Toolbox()
        toolbox.register("evaluate", lambda _mask: (0.0,))
        return toolbox

    def native_chc(_dataset, toolbox, distance, population, *, max_generations, verbose):
        if max_generations != 10 or verbose != 0 or len(population) != 50:
            raise AssertionError("runner changed the registered native chunk arguments")
        if not all(individual.fitness.valid for individual in population):
            raise AssertionError("native initialization was not replayed")
        child = copy.deepcopy(population[-1])
        child[0] = 1 - child[0]
        child.fitness.values = toolbox.evaluate(child)
        # The evaluated, rejected child still has a physical ledger entry.
        return None, population, distance

    evolution = SimpleNamespace(create_toolbox=create_toolbox, CHC=native_chc)
    return SimpleNamespace(Evolution=evolution, creator=SimpleNamespace(Individual=Individual))


def _metrics():
    result = {}
    for scope, matrix in (
        ("unweighted", [[90000.0, 5000.0], [1000.0, 3762.0]]),
        ("weighted", [[90000.25, 5000.5], [1000.125, 3762.625]]),
    ):
        classes = per_class_metrics(matrix)
        result[scope] = {
            "confusion_matrix": matrix,
            "balanced_accuracy": (classes["0"]["recall"] + classes["1"]["recall"]) / 2,
            "accuracy": (matrix[0][0] + matrix[1][1]) / sum(map(sum, matrix)),
            "negative_support": sum(matrix[0]), "positive_support": sum(matrix[1]),
        }
    return result


def _sources(kind):
    rows = [{
        "id": (100000 if kind == "preparation" else 200000) + seed,
        "name": f"eu26-21-qx-{kind}-{seed}-{RUN_ID}-{ATTEMPT}",
        "digest": "sha256:" + hashlib.sha256(f"synthetic/{kind}/{seed}".encode()).hexdigest(),
        "size_in_bytes": 512, "expired": False,
        "workflow_run": {"id": RUN_ID, "head_sha": SHA},
    } for seed in contract.CASE_SEEDS]
    return artifacts.select_sources({"artifacts": rows}, run_id=RUN_ID, expected_sha=SHA, kind=kind)


def _transport(sources):
    return {"complete": True, "source_run_id": RUN_ID, "implementation_sha": SHA,
            "artifacts": [{
                "id": row["id"], "name": row["name"], "digest": row["digest"],
                "zip_verified_before_extraction": True,
                "verified_zip_sha256": row["digest"].removeprefix("sha256:"),
                "verified_zip_bytes": row["size_in_bytes"],
            } for row in sources["artifacts"]]}


def _csv(path):
    with path.open(encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream))


@unittest.skipUnless(os.environ.get("GITHUB_ACTIONS") == "true", "synthetic end-to-end execution is CI-only")
class RunnerReportRoundtripTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.temporary.cleanup)
        cls.directory = Path(cls.temporary.name)
        cls.stack = ExitStack()
        cls.addClassCleanup(cls.stack.close)
        cls.protocol = contract.validate_protocol(contract.THIS_DIRECTORY / "protocol.json")
        environment = {"synthetic_fixture": True}
        inventory = {"synthetic-fixture.py": "d" * 64}
        registration = {"content_freeze_commit_sha": contract.CONTENT_FREEZE_SHA,
                        "registration_protocol_blob_sha256": contract.PROTOCOL_SHA256,
                        "reused_kernel_revision": contract.REUSED_KERNEL_SHA,
                        "reused_files": inventory,
                        "reused_files_sha256": contract.canonical_sha256(inventory)}
        cls.provenance = {
            "protocol_id": contract.PROTOCOL_ID, "protocol_sha256": contract.PROTOCOL_SHA256,
            **registration, "implementation_sha": SHA, "workflow_sha": SHA,
            "run_id": RUN_ID, "run_attempt": ATTEMPT, "ref": "refs/heads/synthetic-ci-fixture",
            "environment": environment, "environment_sha256": contract.canonical_sha256(environment),
            "implementation_files": inventory,
            "implementation_files_sha256": contract.canonical_sha256(inventory),
            "data_sha256": {key: cls.protocol["data"][f"{key}_sha256"] for key in ("archive", "train", "test")},
        }
        # Keep real manifest flat-file, byte, schema and producer checks. Only
        # the enclosing machine/checkout authentication is synthetic.
        for name, value in (("runtime_environment", environment),
                            ("implementation_inventory", inventory),
                            ("verify_registration", registration)):
            cls.stack.enter_context(patch.object(contract, name, return_value=value))
        cls.stack.enter_context(patch.object(run_case, "authenticate", return_value=(cls.protocol, cls.provenance)))
        cls.stack.enter_context(patch.object(aggregate, "authenticate", return_value=(cls.protocol, cls.provenance)))
        cls.stack.enter_context(patch.object(source_gate, "load_evolution", return_value=_native_fixture()))

        cls.train = cls.directory / "synthetic-train.txt"
        cls.train.write_bytes(b"synthetic training identity; no Census records\n")
        cls.test = cls.directory / "synthetic-test.txt"
        cls.test.write_bytes(b"synthetic terminal identity; no Census records\n")
        original_hash = contract.file_sha256

        def train_hash(path):
            return cls.protocol["data"]["train_sha256"] if path == cls.train else original_hash(path)

        cls.stack.enter_context(patch.object(run_case, "file_sha256", side_effect=train_hash))
        cls.preparations, cls.prepared, cls.objectives = {}, {}, {}
        cls.preparation_root = cls.directory / "preparations"
        cls.preparation_root.mkdir()
        cls.preparation_sources = _sources("preparation")
        cls.case_sources = _sources("case")
        cls.case_transport = _transport(cls.case_sources)
        cls.case_root = cls.directory / "cases"
        cls.case_root.mkdir()
        cls.holdout_events, cls.model_events = [], []
        arrays = {
            "x_train": np.zeros((6000, 40)), "y_train": np.arange(6000, dtype=np.int64) % 2,
            "weight_train": np.ones(6000), "x_validation": np.zeros((20, 40)),
            "y_validation": np.arange(20, dtype=np.int64) % 2, "weight_validation": np.ones(20),
            "train_raw_indices": np.arange(6000, dtype=np.int64) + 10000,
            "validation_raw_indices": np.arange(20, dtype=np.int64),
        }
        array_hashes = {name: data.array_sha256(value) for name, value in arrays.items()}
        for seed, source in zip(contract.CASE_SEEDS, cls.preparation_sources["artifacts"]):
            masks = data.source_density_masks(50, seed=seed + 3000003, nonempty=False)
            center = next(mask for mask in masks if any(mask))

            def score(mask, center=center):
                mask = tuple(mask)
                return 0.0 if not any(mask) else (0.9 if mask == center else 0.5 + 0.001 * sum(mask))

            cls.objectives[seed] = score
            metadata = {
                "schema": "eu26-21-qx-training-only-data-v1", "seed": seed,
                "feature_names": list(TRANSFORMED_FEATURE_NAMES), "synthetic_fixture": True,
                "train_file_sha256": cls.protocol["data"]["train_sha256"],
                "train_file_rows": 6020, "train_partition_rows": 6000, "validation_partition_rows": 20,
                "array_hashes": array_hashes, "test_arrays_loaded": False,
                "preprocessing_fit_scope": "internal_training_only",
                "instance_weight_as_predictor": False, "instance_weight_as_sample_weight": True,
            }
            cls.prepared[seed] = data.TrainingPrepared(
                **arrays, feature_names=TRANSFORMED_FEATURE_NAMES, preprocessor=None,
                train_probe_raw=None, metadata=metadata,
            )
            positions = np.arange(5501, dtype=np.int64)[::-1].copy()
            initial_masks, initial_scores = [list(mask) for mask in masks], [score(mask) for mask in masks]
            preparation = {
                "schema": contract.PREPARATION_SCHEMA, "seed": seed, "status": "PASS_PREPARATION",
                "protocol_id": contract.PROTOCOL_ID, "protocol_sha256": contract.PROTOCOL_SHA256,
                "provenance": cls.provenance, "training_data": metadata,
                "initial_masks": initial_masks, "initial_scores": initial_scores,
                "initial_masks_sha256": contract.canonical_sha256(initial_masks),
                "initial_scores_sha256": contract.canonical_sha256(initial_scores),
                "sampling": {"status": "PASS_PREPARATION", "selected_rows": positions.tolist(),
                             "selected_raw_row_ids": arrays["train_raw_indices"][positions].tolist(),
                             "selected_rows_sha256": data.array_sha256(positions),
                             "selected_row_count": len(positions), "synthetic_fixture": True},
                "counts": {"shared_initial_actual_tree_fits": sum(bool(sum(mask)) for mask in masks)},
                "frozen_before_search": True, "test_arrays_loaded": False,
            }
            cls.preparations[seed] = preparation
            directory = cls.preparation_root / source["name"]
            directory.mkdir()
            contract.write_json(directory / "preparation.json", preparation)
            contract.write_manifest(directory, seed=seed, artifact_name=source["name"],
                                    provenance=cls.provenance, row_file="preparation.json")
        cls.registry = artifacts.build_registry(cls.preparation_root, cls.preparation_sources,
                                                _transport(cls.preparation_sources))
        records = []
        for seed, source in zip(contract.CASE_SEEDS, cls.preparation_sources["artifacts"]):
            path = cls.preparation_root / source["name"] / "preparation.json"
            content = path.read_bytes()
            records.append({"seed": seed, "original_sha256": contract.file_sha256(path),
                            "bytes": len(content), "original_utf8": content.decode("utf-8")})
        packed = cls.directory / "frozen-preparations.json.gz"
        payload = json.dumps({"schema": "eu26-21-qx-original-preparations-v1", "records": records},
                             sort_keys=True, ensure_ascii=False, allow_nan=False).encode("utf-8")
        packed.write_bytes(gzip.compress(payload, compresslevel=9, mtime=0))
        cls.registry["frozen_preparations"] = {"file": packed.name, "sha256": contract.file_sha256(packed),
                                               "bytes": packed.stat().st_size}
        cls.registry_path = cls.directory / "registry.json"
        contract.write_json(cls.registry_path, cls.registry)
        cls.registry_sha = contract.file_sha256(cls.registry_path)
        cls.sources_path, cls.transport_path = cls.directory / "sources.json", cls.directory / "transport.json"
        contract.write_json(cls.sources_path, cls.case_sources)
        contract.write_json(cls.transport_path, cls.case_transport)

        def objective_for(prepared, rows=None):
            seed = prepared.metadata["seed"]
            if rows is not None and rows != cls.preparations[seed]["sampling"]["selected_rows"]:
                raise AssertionError("runner changed the frozen active row order")
            return cls.objectives[seed]

        def holdout(prepared, _path, *, expected_test_sha256):
            seed = prepared.metadata["seed"]
            directory = cls.case_root / f"eu26-21-qx-case-{seed}-{RUN_ID}-{ATTEMPT}"
            freeze = contract.read_json(directory / "terminal-masks.json")
            if (set(freeze["arms"]) != set(contract.SEARCH_ARMS)
                    or freeze["test_evaluations_so_far"] != 0
                    or expected_test_sha256 != cls.protocol["data"]["test_sha256"]):
                raise AssertionError("holdout was loaded before all three masks were frozen")
            for arm in contract.SEARCH_ARMS:
                if not (directory / f"trace-{arm}.json").is_file() or (directory / f"model-{arm}.joblib").exists():
                    raise AssertionError("holdout ordering differs from the registered runner")
            cls.holdout_events.append(seed)
            return SimpleNamespace(seed=seed, feature_names=TRANSFORMED_FEATURE_NAMES)

        def evaluate(prepared, mask, *, path, seed, arm, provenance):
            if prepared.seed != seed or seed not in cls.holdout_events:
                raise AssertionError("terminal evaluation lacks its late-loaded holdout")
            content = f"inert synthetic model bytes/{seed}/{arm}\n".encode()
            path.write_bytes(content)
            cls.model_events.append((seed, arm))
            return _metrics(), {
                "file": path.name, "sha256": hashlib.sha256(content).hexdigest(), "bytes": len(content),
                "seed": seed, "arm": arm, "mask": list(mask),
                "selected_feature_names": [name for name, bit in zip(prepared.feature_names, mask) if bit],
                "reload_verification": "PASS_EXACT_NON_TEST_PROBE", "test_access_during_reload": False,
            }

        cls.stack.enter_context(patch.object(run_case, "prepare_training", side_effect=lambda _path, *, seed: cls.prepared[seed]))
        cls.stack.enter_context(patch.object(run_case, "objective_for", side_effect=objective_for))
        cls.stack.enter_context(patch.object(run_case, "load_terminal_holdout", side_effect=holdout))
        cls.stack.enter_context(patch.object(run_case, "evaluate_and_persist", side_effect=evaluate))
        cls.rows = {}
        for seed, preparation_source, case_source in zip(contract.CASE_SEEDS,
                                                        cls.preparation_sources["artifacts"], cls.case_sources["artifacts"]):
            cls.rows[seed] = run_case.run_case(
                train=cls.train, test=cls.test, upstream=cls.directory / "synthetic-upstream", seed=seed,
                expected_sha=SHA, preparation_path=cls.preparation_root / preparation_source["name"] / "preparation.json",
                registry_path=cls.registry_path, output=cls.case_root / case_source["name"], artifact_name=case_source["name"],
            )

    def _validate(self, directory=None, seed=44001):
        source = self.case_sources["artifacts"][seed - contract.CASE_SEEDS[0]]
        return aggregate.validate_case(directory or self.case_root / source["name"], source,
                                       self.registry, self.registry_sha, expected_sha=SHA, seed=seed,
                                       preparation=self.preparations[seed])

    def _tamper(self, mutate, pattern):
        with tempfile.TemporaryDirectory() as temporary:
            source = self.case_sources["artifacts"][0]
            directory = Path(temporary) / source["name"]
            shutil.copytree(self.case_root / source["name"], directory)
            row = contract.read_json(directory / "case.json")
            mutate(directory, row)
            contract.write_json(directory / "case.json", row)
            contract.write_manifest(directory, seed=row["seed"], artifact_name=source["name"], provenance=row["provenance"])
            with self.assertRaisesRegex(ValueError, pattern):
                self._validate(directory)

    def test_actual_runner_files_validate_and_test_follows_all_three_freezes(self):
        row, traces = self._validate()
        self.assertEqual(row["status"], "PASS_CASE_COMPLETE")
        self.assertEqual(set(traces), set(contract.SEARCH_ARMS))
        self.assertEqual(self.holdout_events, list(contract.CASE_SEEDS))
        self.assertEqual(set(self.model_events), {(seed, arm) for seed in contract.CASE_SEEDS for arm in contract.SEARCH_ARMS})
        for arm, item in row["arms"].items():
            self.assertEqual((item["chunks"], item["stop_reason"]), (3, "full_no_change"))
            self.assertEqual(item["active_logical_calls"], item["active_physical_calls"] + 50)
            self.assertEqual(item["counts"]["diagnostic_active"]["physical_calls"], 41)
            self.assertEqual(item["counts"]["diagnostic_full"]["physical_calls"], 41)
            self.assertEqual(item["diagnostic"]["classification"], "both_local")
            self.assertTrue(item["diagnostic"]["approximate"]["strict_local_maximum"])
            matrix = item["test_metrics"]["unweighted"]["confusion_matrix"]
            self.assertEqual(sum(map(sum, matrix)), 99762)
            self.assertTrue(all(type(value) is int for line in matrix for value in line))
            self.assertIs(type(item["test_metrics"]["weighted"]["confusion_matrix"][0][0]), float)
            self.assertEqual(item["test_evaluations"], 1)
            self.assertEqual(traces[arm]["preparation"], row["preparation"])

    def test_all_thirty_cases_roundtrip_to_complete_tables_and_report_manifest(self):
        output = self.directory / "positive-report"
        # Rendering is omitted from this schema roundtrip; inspect the exact
        # rows and unextended trace lengths passed to it here.
        with patch.object(aggregate, "plots") as plotter, patch("joblib.load", side_effect=AssertionError("report loaded model bytes")):
            summary = aggregate.aggregate(root=self.case_root, registry_path=self.registry_path,
                                          sources_path=self.sources_path, transport_path=self.transport_path,
                                          output=output, expected_sha=SHA)
        self.assertEqual(summary["cases_accounted"], 30)
        self.assertFalse(summary["hypothesis_tests"])
        self.assertFalse(any(summary["claims"].values()))
        plotter.assert_called_once()
        self.assertEqual(len(plotter.call_args.args[1]), 30)
        self.assertEqual(set(plotter.call_args.args[2]), {(seed, arm) for seed in contract.CASE_SEEDS for arm in contract.SEARCH_ARMS})
        for item in summary["arms"].values():
            self.assertEqual((item["diagnostic_cases"], item["valid_test_cases"], item["not_evaluable_cases"]), (30, 30, 0))
            self.assertEqual(item["diagnostic_calls"], 30 * 82)
            self.assertEqual(item["test_evaluations"], 30)
        expected_pairs = {(str(seed), arm) for seed in contract.CASE_SEEDS for arm in contract.SEARCH_ARMS}
        for filename, length in (("cases.csv", 90), ("one-bit-certificates.csv", 7380),
                                 ("checkpoints.csv", 270), ("class-metrics.csv", 360)):
            rows = _csv(output / filename)
            self.assertEqual(len(rows), length, filename)
            self.assertEqual({(row["seed"], row["arm"]) for row in rows}, expected_pairs, filename)
        self.assertEqual(len(_csv(output / "bit-feature-map.csv")), 40)
        self.assertEqual((output / "frozen-preparations.json.gz").read_bytes(),
                         (self.directory / "frozen-preparations.json.gz").read_bytes())
        report = contract.read_json(output / "report-manifest.json")
        self.assertEqual(set(report["files"]), {path.name for path in output.iterdir()} - {"report-manifest.json"})
        for filename, identity in report["files"].items():
            self.assertEqual(identity, {"sha256": contract.file_sha256(output / filename),
                                        "bytes": (output / filename).stat().st_size})

    def test_rehashed_trace_cannot_change_preparation_identity(self):
        def mutate(directory, row):
            identity = row["arms"]["chc_qx"]["trace"]
            trace = contract.read_json(directory / identity["file"])
            trace["preparation"]["source_artifact_id"] += 1
            identity.update(contract.write_json(directory / identity["file"], trace))
        self._tamper(mutate, "search trace identity mismatch")

    def test_rehashed_terminal_freeze_cannot_claim_selection_after_test(self):
        def mutate(directory, row):
            identity = row["terminal_masks_freeze"]
            freeze = contract.read_json(directory / identity["file"])
            freeze["test_evaluations_so_far"] = 1
            identity.update(contract.write_json(directory / identity["file"], freeze))
        self._tamper(mutate, "terminal masks were not frozen before test")

    def test_rehashed_case_cannot_invent_duplicate_query_counts(self):
        self._tamper(lambda _directory, row: row["arms"]["lambda_fixed1_qx"]["counts"]["active"].update(duplicate_queries=0),
                     "physical calls, actual fits or duplicate counters")

    def test_rehashed_model_metadata_cannot_change_selected_feature_names(self):
        self._tamper(lambda _directory, row: row["models"]["chc_qx"].update(selected_feature_names=[]),
                     "terminal model identity, selected features or reload evidence")

    def test_rehashed_valid_certificate_cannot_change_a_known_full_score_across_arms(self):
        def mutate(directory, row):
            arm = "lambda_adaptive_qx"
            item = row["arms"][arm]
            center = tuple(item["snapshot"]["mask"])
            bit = next((index for index, value in enumerate(center) if value == 0), 0)
            neighbor = center[:bit] + (1 - center[bit],) + center[bit + 1:]
            score = self.objectives[row["seed"]]
            diagnostic = certify_snapshot(snapshot=item["snapshot"], active_objective=score,
                                          full_objective=lambda mask: score(mask) + (0.001 if tuple(mask) == neighbor else 0.0))
            diagnostic.update(seed=row["seed"], arm=arm, provenance=row["provenance"])
            identity = item["diagnostics"]
            identity.update(contract.write_json(directory / identity["file"], diagnostic))
        self._tamper(mutate, "same mask has conflicting deterministic scores")

    def test_complete_series_rejects_missing_case_before_creating_report(self):
        sources = copy.deepcopy(self.case_sources)
        sources["artifacts"].pop()
        path = self.directory / "missing-case-sources.json"
        contract.write_json(path, sources)
        output = self.directory / "missing-case-report"
        with self.assertRaises(ValueError):
            aggregate.aggregate(root=self.case_root, registry_path=self.registry_path,
                                sources_path=path, transport_path=self.transport_path, output=output, expected_sha=SHA)
        self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main()
