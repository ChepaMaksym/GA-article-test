"""CI-only metadata, registration and exact-byte evidence tests."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from corrected_applied.data_protocol import TRANSFORMED_FEATURE_NAMES, TRANSFORMED_PREDICTIVE_RAW_INDICES  # noqa: E402
from lambda_response_study import artifacts  # noqa: E402
from lambda_response_study.contract import (  # noqa: E402
    CASE_SEEDS, PROTOCOL_ID, PROTOCOL_SHA256, REGISTRATION_SHA,
    file_sha256, read_json, validate_protocol, write_json, write_manifest,
)

SHA, RUN_ID = "a" * 40, 77
DIGEST = "sha256:" + "b" * 64


def provenance(*, attempt=1):
    return {"protocol_id": PROTOCOL_ID, "protocol_sha256": PROTOCOL_SHA256,
            "registration_sha": REGISTRATION_SHA, "implementation_sha": SHA,
            "workflow_sha": SHA, "run_id": RUN_ID, "run_attempt": attempt}


def metadata(seed):
    return {"schema": "eu26-21-qx-training-only-data-v1", "seed": seed,
            "feature_names": list(TRANSFORMED_FEATURE_NAMES),
            "transformed_raw_indices": list(TRANSFORMED_PREDICTIVE_RAW_INDICES),
            "train_file_sha256": validate_protocol()["data"]["train_sha256"],
            "train_file_rows": 199523, "train_partition_rows": 159618,
            "validation_partition_rows": 39905, "split_seed": 2026081700 + seed,
            "test_arrays_loaded": False, "instance_weight_as_predictor": False,
            "instance_weight_as_sample_weight": True, "preprocessing_fit_scope": "internal_training_only",
            "array_hashes": {key: "c" * 64 for key in ("x_train", "y_train", "weight_train", "x_validation",
                "y_validation", "weight_validation", "train_raw_indices", "validation_raw_indices")},
            "train_positive_count": 10000, "validation_positive_count": 2500}


def preparation(seed):
    rows = [{"bit_index": bit, "mask": [int(index == bit) for index in range(40)], "score": .505}
            for bit in range(40)]
    return {"schema": artifacts.PREPARATION_SCHEMA, "status": "PASS_PREPARATION", "seed": seed,
            "provenance": provenance(), "training_data": metadata(seed), "evaluations": rows,
            "initial": {**rows[0], "feature_name": TRANSFORMED_FEATURE_NAMES[0]},
            "counts": {"physical_calls": 40, "actual_tree_fits": 40}}


def api_artifact(seed, *, kind="preparation", attempt=1):
    return {"id": seed * 100 + attempt, "name": f"eu26-21-lr-{kind}-{seed}-{RUN_ID}-{attempt}",
            "digest": DIGEST, "expired": False, "size_in_bytes": 100,
            "workflow_run": {"id": RUN_ID, "head_sha": SHA}}


def sources(*, kind="preparation"):
    raw = {"total_count": 30, "artifacts": [api_artifact(seed, kind=kind) for seed in CASE_SEEDS]}
    return artifacts.select_sources(raw, run_id=RUN_ID, expected_sha=SHA, kind=kind)


def transport(selected):
    return {"complete": True, "source_run_id": RUN_ID, "implementation_sha": SHA,
            "kind": "lr-" + selected["kind"], "artifacts": [
                {"id": row["id"], "name": row["name"], "digest": row["digest"], "size_in_bytes": 100,
                 "verified_zip_sha256": "b" * 64, "verified_zip_bytes": 100,
                 "zip_verified_before_extraction": True} for row in selected["artifacts"]]}


def prepare_registry(root):
    selected = sources()
    for seed, source in zip(CASE_SEEDS, selected["artifacts"]):
        directory = root / source["name"]
        directory.mkdir()
        write_json(directory / "preparation.json", preparation(seed))
        write_manifest(directory, seed=seed, kind="preparation", provenance=provenance())
    return artifacts.build_registry(root, selected, transport(selected))


class LambdaResponseArtifactTests(unittest.TestCase):
    def test_selection_preserves_raw_and_complete_metadata_envelope(self):
        raw = {"total_count": 30, "artifacts": [api_artifact(seed) for seed in CASE_SEEDS]}
        before = deepcopy(raw)
        selected = artifacts.select_sources(raw, run_id=RUN_ID, expected_sha=SHA, kind="preparation")
        artifacts.validate_sources(selected, kind="preparation", expected_sha=SHA)
        self.assertEqual(raw, before)
        self.assertEqual([row["seed"] for row in selected["artifacts"]], list(CASE_SEEDS))
        self.assertFalse(selected["scientific_results_opened_for_selection"])

    def test_latest_attempt_not_outcome_selected(self):
        raw = sources()["raw_metadata"]
        newer = api_artifact(CASE_SEEDS[0], attempt=2)
        newer["result_hint"] = "worse-scientific-outcome-never-inspected"
        raw["artifacts"].insert(0, newer)
        selected = artifacts.select_sources(raw, run_id=RUN_ID, expected_sha=SHA, kind="preparation")
        self.assertEqual(selected["artifacts"][0]["id"], newer["id"])
        self.assertEqual(selected["artifacts"][0]["run_attempt"], 2)
        artifacts.validate_sources(selected, kind="preparation")

    def test_bad_or_missing_identity_rejected(self):
        updates = [{"id": True}, {"id": 0}, {"expired": True}, {"expired": None},
                   {"digest": None}, {"digest": "sha256:" + "b" * 63}, {"size_in_bytes": 0},
                   {"name": "eu26-21-lr-preparation-045001-77-1"},
                   {"name": "eu26-21-lr-preparation-45000-77-1"},
                   {"workflow_run": {"id": RUN_ID, "head_sha": "d" * 40}}, {"workflow_run": None}]
        for update in updates:
            with self.subTest(update=update):
                raw = deepcopy(sources()["raw_metadata"])
                raw["artifacts"][0].update(update)
                with self.assertRaises(ValueError):
                    artifacts.select_sources(raw, run_id=RUN_ID, expected_sha=SHA, kind="preparation")
        raw = sources()["raw_metadata"]
        raw["artifacts"].pop()
        with self.assertRaisesRegex(ValueError, "30/30"):
            artifacts.select_sources(raw, run_id=RUN_ID, expected_sha=SHA, kind="preparation")

    def test_duplicate_id_name_and_attempt_rejected(self):
        raw = sources()["raw_metadata"]
        raw["artifacts"].append(deepcopy(raw["artifacts"][0]))
        with self.assertRaisesRegex(ValueError, "duplicate"):
            artifacts.select_sources(raw, run_id=RUN_ID, expected_sha=SHA, kind="preparation")
        raw = sources()["raw_metadata"]
        raw["artifacts"][1]["id"] = raw["artifacts"][0]["id"]
        with self.assertRaisesRegex(ValueError, "duplicate"):
            artifacts.select_sources(raw, run_id=RUN_ID, expected_sha=SHA, kind="preparation")

    def test_changed_selected_seed_or_old_attempt_rejected(self):
        selected = sources()
        selected["artifacts"][0]["seed"] = CASE_SEEDS[1]
        with self.assertRaisesRegex(ValueError, "selection"):
            artifacts.validate_sources(selected, kind="preparation")
        selected = sources()
        selected["implementation_sha"] = "d" * 40
        with self.assertRaises(ValueError):
            artifacts.validate_sources(selected, kind="preparation")

    def test_zip_transport_bound_before_extraction(self):
        selected = sources()
        artifacts.validate_transport(selected, transport(selected))
        for field, value in (("zip_verified_before_extraction", False), ("verified_zip_sha256", "e" * 64),
                             ("verified_zip_bytes", 99), ("id", 99)):
            with self.subTest(field=field):
                ledger = transport(selected)
                ledger["artifacts"][0][field] = value
                with self.assertRaises(ValueError):
                    artifacts.validate_transport(selected, ledger)

    def test_registry_embeds_original_bytes_and_complete_states(self):
        with tempfile.TemporaryDirectory() as temporary:
            registry = prepare_registry(Path(temporary))
            records = artifacts.validate_registry(registry, expected_sha=SHA)
            self.assertEqual(set(records), set(CASE_SEEDS))
            self.assertEqual(registry["cases"][0]["payload"], preparation(CASE_SEEDS[0]))
            entry = registry["cases"][0]
            raw = entry["original_preparation_utf8"].encode("utf-8")
            self.assertEqual(hashlib.sha256(raw).hexdigest(), entry["preparation"]["sha256"])
            for problem in ("duplicate", "missing", "bytes", "payload"):
                with self.subTest(problem=problem):
                    bad = deepcopy(registry)
                    if problem == "duplicate":
                        bad["cases"][1]["source_artifact_id"] = bad["cases"][0]["source_artifact_id"]
                    elif problem == "missing":
                        bad["cases"].pop()
                    elif problem == "bytes":
                        bad["cases"][0]["original_preparation_utf8"] += " "
                    else:
                        bad["cases"][0]["payload"]["initial"]["score"] += .01
                    with self.assertRaises(ValueError):
                        artifacts.validate_registry(bad, expected_sha=SHA)

    def test_preparation_minimum_and_feature_metadata_gated(self):
        for key, value in (("feature_names", list(reversed(TRANSFORMED_FEATURE_NAMES))),
                           ("instance_weight_as_predictor", True), ("test_arrays_loaded", True),
                           ("split_seed", 1), ("train_partition_rows", 14964),
                           ("array_hashes", {}), ("train_file_sha256", "c" * 64)):
            with self.subTest(key=key):
                data = metadata(45001)
                data[key] = value
                with self.assertRaises(ValueError):
                    artifacts.validate_preparation_metadata(data, seed=45001)
        with tempfile.TemporaryDirectory() as temporary:
            registry = prepare_registry(Path(temporary))
            entry = registry["cases"][0]
            entry["payload"]["evaluations"][1]["score"] = .4
            raw = json.dumps(entry["payload"], sort_keys=True, indent=2, ensure_ascii=False).encode("utf-8")
            entry["original_preparation_utf8"] = raw.decode("utf-8")
            entry["preparation"] = {"sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw)}
            with self.assertRaisesRegex(ValueError, "minimum"):
                artifacts.validate_registry(registry, expected_sha=SHA)

    def test_registry_rejects_changed_preparation_file(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            prepare_registry(root)
            selected = sources()
            path = root / selected["artifacts"][0]["name"] / "preparation.json"
            path.write_bytes(path.read_bytes() + b" ")
            with self.assertRaisesRegex(ValueError, "checksum"):
                artifacts.build_registry(root, selected, transport(selected))

    def test_cli_is_ci_only_and_never_overwrites(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            raw, output = root / "raw.json", root / "selected.json"
            write_json(raw, sources()["raw_metadata"])
            argv = ["artifacts", "select", "--api-metadata", str(raw), "--run-id", str(RUN_ID),
                    "--expected-sha", SHA, "--kind", "preparation", "--output", str(output)]
            with patch.object(sys, "argv", argv), patch.dict("os.environ", {"GITHUB_ACTIONS": "false"}), self.assertRaisesRegex(ValueError, "CI-only"):
                artifacts.main()
            with patch.object(sys, "argv", argv), patch.dict("os.environ", {"GITHUB_ACTIONS": "true"}):
                artifacts.main()
            self.assertEqual(read_json(output)["raw_metadata_file_sha256"], file_sha256(raw))
            with patch.object(sys, "argv", argv), patch.dict("os.environ", {"GITHUB_ACTIONS": "true"}), self.assertRaisesRegex(ValueError, "immutable"):
                artifacts.main()


if __name__ == "__main__":
    unittest.main()
