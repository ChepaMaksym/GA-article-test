"""Small trace-envelope fixtures; scientific execution belongs to CI only."""

from __future__ import annotations

from copy import deepcopy
import gzip
import json
from pathlib import Path
import tarfile
import tempfile
import unittest
from unittest.mock import patch

import numpy as np

from studies.knapsack_parameters.secondary_review import trace_audit as trace
from studies.knapsack_parameters.secondary_review.contract import file_identity, write_json


class TraceFixtures(unittest.TestCase):
    def descriptor_fixture(self):
        descriptor = {"artifact_id": 11557059267, "artifact_name": "frozen-UC-s000",
            "run_id": trace.SOURCE_RUN, "run_attempt": 1,
            "implementation_commit_sha": trace.SOURCE_SHA,
            "zip_sha256": "a" * 64, "zip_bytes": 109579341,
            "job_manifest_sha256": "b" * 64}
        source = {**descriptor, "instance_id": "UC-s000", "seed_first": 51001,
                  "seed_last": 51010}
        sources = {"implementation_commit_sha": trace.SOURCE_SHA,
                   "run_id": trace.SOURCE_RUN, "run_attempt": 1, "sources": [source]}
        return {"trace": descriptor}, sources

    def saved_fixture(self, root, *, object_arrays=False, profile="random", config="m1-c0p9-n30"):
        row = {"instance_id": "UC-s000", "repeat_seed": 51001,
               "start_profile": profile, "configuration_id": config,
               "implementation_commit_sha": trace.SOURCE_SHA,
               "run_directory": f"runs/51001/{profile}/{config}", "budget": 2}
        run = root / row["run_directory"]
        run.mkdir(parents=True)
        np.savez_compressed(run / "requests.npz", request=np.asarray(
            [1, 2], dtype=object if object_arrays else np.int32))
        with gzip.open(run / "generations.jsonl.gz", "wt", encoding="utf-8") as stream:
            stream.write(json.dumps({"generation": 0}) + "\n")
        write_json(run / "summary.json", row)
        write_json(run / "search_summary.json", {"budget": 2})
        files = [{"path": name, **file_identity(run / name)} for name in trace.RUN_FILES
                 if name != "manifest.json"]
        write_json(run / "manifest.json", {"schema_version": "ga-knapsack-run-manifest-v1",
            "verified": True, "identity": {key: row[key] for key in
                ("instance_id", "start_profile", "repeat_seed", "configuration_id",
                 "implementation_commit_sha")}, "files": files})
        return row, run

    def trajectory_fixture(self):
        metrics = {"mean_feasible_profit": 4.0, "diversity": 0.5,
                   "feasible_fraction": 1.0}
        return {"requests": {"profit": np.asarray([3, 4, 100, 9], dtype=np.int64),
                             "feasible": np.asarray([True, True, False, True])},
                "generations": [
                    {"generation": 0, "complete": True, "first_request": 1,
                     "last_request": 2, "population_before": [], "population_after": [0, 1],
                     "metrics_before": None, "metrics_after": metrics},
                    {"generation": 1, "complete": False, "first_request": 3,
                     "last_request": 4, "population_before": [0, 1], "population_after": [0, 1],
                     "metrics_before": metrics, "metrics_after": metrics}]}

    def test_exact_six_selection_not_result_dependent(self):
        expected = {(profile, f"m{m}-c0p9-n30") for profile in ("random", "local")
                    for m in ("0p5", "1", "3")}
        self.assertEqual(set(trace.selected_identities()), expected)
        self.assertEqual(len(trace.selected_identities()), 6)

    def test_exact_descriptor_matches_retained_ledger(self):
        protocol, sources = self.descriptor_fixture()
        self.assertEqual(trace.validate_descriptor(protocol, sources), protocol["trace"])

    def test_no_replacement_when_artifact_id_changes(self):
        protocol, sources = self.descriptor_fixture()
        protocol["trace"]["artifact_id"] += 1
        with self.assertRaisesRegex(ValueError, "preregistered"):
            trace.validate_descriptor(protocol, sources)

    def test_mixed_source_sha_and_zip_corruption_fail(self):
        protocol, sources = self.descriptor_fixture()
        sources["implementation_commit_sha"] = "0" * 40
        with self.assertRaises(ValueError):
            trace.validate_descriptor(protocol, sources)
        protocol, sources = self.descriptor_fixture()
        sources["sources"][0]["zip_sha256"] = "c" * 64
        with self.assertRaisesRegex(ValueError, "zip_sha256"):
            trace.validate_descriptor(protocol, sources)

    def test_duplicate_exact_artifact_fails(self):
        protocol, sources = self.descriptor_fixture()
        sources["sources"].append(deepcopy(sources["sources"][0]))
        with self.assertRaisesRegex(ValueError, "duplicate"):
            trace.validate_descriptor(protocol, sources)

    def test_missing_artifact_is_partial_not_success_or_replacement(self):
        protocol, _ = self.descriptor_fixture()
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "output"
            with patch.object(trace, "load_context", return_value=([], {}, {}, {"run_id": 1})), \
                 patch.object(trace, "read_json", return_value={}), \
                 patch.object(trace, "validate_descriptor", return_value=protocol["trace"]), \
                 patch.object(trace, "api_get", side_effect=ValueError("frozen artifact expired")):
                result = trace.audit("0" * 40, output)
            self.assertEqual(result["status"], "PARTIAL_TRACE_AUDIT")
            self.assertEqual(result["verified_case_count"], 0)
            self.assertIsNone(result["retained_traces"])
            self.assertFalse(result["fault"]["replacement_selected"])
            self.assertTrue((output / "trace-audit.json").is_file())
            self.assertTrue((output / "file_manifest.json").is_file())

    def test_stored_trace_loads_without_pickle(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            row, _ = self.saved_fixture(root)
            result = trace.load_saved_result(root, row)
            self.assertEqual(result["requests"]["request"].tolist(), [1, 2])
            self.assertEqual(result["summary"], {"budget": 2})

    def test_object_arrays_are_not_deserialized(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            row, _ = self.saved_fixture(root, object_arrays=True)
            with self.assertRaisesRegex(ValueError, "Object arrays cannot be loaded"):
                trace.load_saved_result(root, row)

    def test_corrupt_member_rejected_before_loading(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            row, run = self.saved_fixture(root)
            (run / "requests.npz").write_bytes(b"not original")
            with self.assertRaisesRegex(ValueError, "checksum"):
                trace.load_saved_result(root, row)

    def test_missing_and_duplicate_run_inventory_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            row, run = self.saved_fixture(root)
            manifest = trace.read_json(run / "manifest.json")
            manifest["files"].append(deepcopy(manifest["files"][0]))
            write_json(run / "manifest.json", manifest)
            with self.assertRaisesRegex(ValueError, "inventory"):
                trace.load_saved_result(root, row)

    def test_compact_disagreement_rejected(self):
        trace.compact_matches({"best_profit": 9, "extra": True}, {"best_profit": 9})
        with self.assertRaisesRegex(ValueError, "compact"):
            trace.compact_matches({"best_profit": 9}, {"best_profit": 10})

    def test_final_partial_candidate_can_set_record_not_population(self):
        trajectory = trace.reconstruct_trajectory(self.trajectory_fixture())
        self.assertEqual([point["best_profit"] for point in trajectory], [4, 9])
        self.assertFalse(trajectory[-1]["population_updated"])
        self.assertFalse(trajectory[-1]["complete"])
        self.assertEqual(trajectory[-1]["mean_feasible_profit"], 4.0)
        self.assertEqual(trajectory[-1]["last_request"], 4)

    def test_infeasible_candidate_is_not_record(self):
        result = self.trajectory_fixture()
        result["requests"]["feasible"][-1] = False
        self.assertEqual(trace.reconstruct_trajectory(result)[-1]["best_profit"], 4)

    def test_partial_population_change_is_invalid(self):
        result = self.trajectory_fixture()
        result["generations"][-1]["population_after"] = [0, 3]
        with self.assertRaisesRegex(ValueError, "partial"):
            trace.reconstruct_trajectory(result)

    def test_generation_endpoint_outside_trace_rejected(self):
        result = self.trajectory_fixture()
        result["generations"][-1]["last_request"] = 5
        with self.assertRaisesRegex(ValueError, "endpoint"):
            trace.reconstruct_trajectory(result)

    def test_negative_zero_and_empty_record_remain_distinct(self):
        result = self.trajectory_fixture()
        result["requests"]["profit"][:] = 0
        self.assertEqual(trace.reconstruct_trajectory(result)[-1]["best_profit"], 0)
        result["requests"]["feasible"][:] = False
        self.assertIsNone(trace.reconstruct_trajectory(result)[-1]["best_profit"])

    def test_retained_archive_reproducible_and_has_source_identity(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            selected = [self.saved_fixture(root / "source", profile=profile, config=config)[0]
                        for profile, config in trace.selected_identities()]
            bank = {"masks": np.zeros((50, 100), dtype=np.uint8),
                    "scores": {"weight": np.zeros(50, dtype=np.int64),
                               "profit": np.zeros(50, dtype=np.int64),
                               "feasible": np.ones(50, dtype=np.bool_)},
                    "checksum": "0" * 64, "metadata": {}, "rng_states": {}, "source_npz": {}}
            left, right = root / "left", root / "right"
            left.mkdir()
            right.mkdir()
            first = trace.retain_selected_traces(root / "source", left, selected, bank)
            second = trace.retain_selected_traces(root / "source", right, selected, bank)
            self.assertEqual(first["sha256"], second["sha256"])
            with tarfile.open(left / "retained-traces.tar.gz", "r:gz") as archive:
                manifest = json.load(archive.extractfile("retained_manifest.json"))
                self.assertEqual(manifest["source_run_id"], trace.SOURCE_RUN)
                self.assertEqual(manifest["source_implementation_commit_sha"], trace.SOURCE_SHA)


if __name__ == "__main__":
    unittest.main()
