"""Synthetic end-to-end evidence tests. Execute only in GitHub Actions.

The scientific runner/serialization/validators are real. Only authenticated
external inputs and the expensive objective are replaced by explicit fixtures;
none of these observations is eligible for scientific aggregation.
"""
from __future__ import annotations

from contextlib import ExitStack
import copy
from dataclasses import replace
import hashlib
from io import StringIO
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

import numpy as np
import pandas as pd
from sklearn.preprocessing import StandardScaler

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from common_bridge import aggregate, model_evidence, run_seed, search, validate_workflows  # noqa: E402
from common_bridge.artifact_selection import select_seed_artifacts  # noqa: E402
from corrected_applied.data_protocol import (  # noqa: E402
    PreparedCorrectedCensus, TRANSFORMED_FEATURE_NAMES,
)


def prepared_fixture(seed: int) -> PreparedCorrectedCensus:
    rng = np.random.default_rng(seed + 91)
    raw = pd.DataFrame(rng.normal(size=(80, 40)))
    preprocessor = StandardScaler().fit(raw)
    features = preprocessor.transform(raw)
    labels = np.asarray([0, 1] * 40, dtype=np.int8)
    return PreparedCorrectedCensus(
        x_train=features, y_train=labels, weight_train=np.ones(80),
        x_validation=features[:20], y_validation=labels[:20], weight_validation=np.ones(20),
        x_test=features[20:40], y_test=labels[20:40], weight_test=np.ones(20),
        active_instances=np.arange(40), feature_names=TRANSFORMED_FEATURE_NAMES,
        metadata={
            "predictive_dimension": 40, "split_seed": 2_026_081_700 + seed,
            "train_partition_rows": 80, "validation_partition_rows": 20,
            "active_indices_sha256": hashlib.sha256(np.arange(40, dtype="<i8").tobytes()).hexdigest(),
        },
        preprocessor=preprocessor, train_probe_raw=raw.iloc[:8].copy(),
    )


def toy_objective(mask: tuple[int, ...]) -> tuple[float, float]:
    count = sum(mask)
    return (0.0, -1.0) if count == 0 else (0.2 + 0.6 * count / 40, -count / 40)


class RunnerArtifactRoundTripTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.temporary = tempfile.TemporaryDirectory(prefix="bridge-ci-fixture-")
        cls.addClassCleanup(cls.temporary.cleanup)
        cls.root = Path(cls.temporary.name)
        cls.rows_dir = cls.root / "rows"
        cls.protocol = ROOT / "common_bridge" / "protocol.json"
        cls.config = ROOT / "common_bridge" / "config.json"
        cls.sha = "a" * 40
        cls.ref = "refs/tags/eu26-21-common-bridge-evidence-v1"
        cls.source = {
            "upstream_commit": aggregate.EXPECTED_UPSTREAM_COMMIT,
            "upstream_evolution_blob_sha1": "05b0d8afc02faee688e5d1ff8e24531ae41307c7",
            "upstream_evolution_sha256": "b" * 64,
        }
        actual_hash = run_seed._file_sha256
        requirements = ROOT / "corrected_applied" / "requirements.txt"
        cls.config_hash = actual_hash(cls.config)
        cls.requirements_hash = actual_hash(requirements)
        fake_train, fake_test = cls.root / "fake-train", cls.root / "fake-test"
        def fixture_hash(path: Path) -> str:
            if path == fake_train:
                return aggregate.EXPECTED_TRAIN_SHA256
            if path == fake_test:
                return aggregate.EXPECTED_TEST_SHA256
            return actual_hash(path)
        cls.entries = []
        with ExitStack() as stack:
            stack.enter_context(patch.object(run_seed, "_file_sha256", side_effect=fixture_hash))
            stack.enter_context(patch.object(run_seed, "_git", side_effect=lambda root, *args: cls.sha if args[0] == "rev-parse" else ""))
            stack.enter_context(patch.object(run_seed, "_verify_upstream_evolution", return_value=cls.source))
            stack.enter_context(patch.object(run_seed, "validate_protocol", return_value={
                "protocol_sha256": aggregate.EXPECTED_PROTOCOL_SHA256,
                "protocol_content_freeze_commit_sha": "939914a33d21709526ef12538170ce806b45e3a3",
            }))
            stack.enter_context(patch.object(run_seed, "_requirements_environment", return_value={"fixture": "synthetic-not-scientific"}))
            stack.enter_context(patch.object(run_seed, "_validation_objective", return_value=toy_objective))
            for seed in aggregate.EXPECTED_SEEDS:
                attempt = 2 if seed == 41001 else 1
                name = f"eu26-21-common-bridge-seed-{seed}-321-{attempt}"
                output = cls.rows_dir / name
                prepared = prepared_fixture(seed)
                evaluator = model_evidence.evaluate_mask_on_official_test
                test_calls = []
                def terminal_check(data, mask, **kwargs):
                    # This is an execution-order assertion, not a trace-key heuristic.
                    for suffix in ("chc", "lambda"):
                        trace = json.loads((output / f"seed-{seed}-{suffix}-trace.json").read_text())
                        if trace["objective_calls"] != 400:
                            raise AssertionError("test accessed before both traces were frozen")
                    test_calls.append(tuple(mask))
                    return evaluator(data, mask, **kwargs)
                with (
                    patch.object(run_seed, "prepare_corrected_census", return_value=prepared),
                    patch.object(model_evidence, "evaluate_mask_on_official_test", side_effect=terminal_check),
                    patch.dict("os.environ", {"GITHUB_RUN_ID": "321", "GITHUB_RUN_ATTEMPT": str(attempt),
                                             "GITHUB_REF": cls.ref, "BRIDGE_WORKFLOW_SHA": cls.sha}),
                ):
                    run_seed.run_paired_seed(
                        protocol_path=cls.protocol, config_path=cls.config, upstream=cls.root,
                        official_train=fake_train, official_test=fake_test, seed=seed,
                        expected_sha=cls.sha, expected_protocol_sha256=aggregate.EXPECTED_PROTOCOL_SHA256,
                        expected_config_sha256=cls.config_hash, expected_requirements_sha256=cls.requirements_hash,
                        output_dir=output, artifact_name=name,
                    )
                if len(test_calls) != 2:
                    raise AssertionError("terminal test must be called once per arm")
                cls.entries.append({"seed": seed, "id": seed, "name": name,
                                    "run_attempt": attempt, "digest": "sha256:" + format(seed, "064x")})
        cls.ledger = {
            "schema": aggregate.SOURCE_LEDGER_SCHEMA, "repository": "ChepaMaksym/GA-article-test",
            "source_run_id": 321, "source_run_attempt": 2, "source_head_sha": cls.sha,
            "source_ref": cls.ref, "source_workflow_sha": cls.sha,
            "source_workflow_path": aggregate.SOURCE_WORKFLOW_PATH, "artifacts": cls.entries,
        }
        cls.ledger_path = cls.root / "source-ledger.json"
        cls.ledger_path.write_text(json.dumps(cls.ledger), encoding="utf-8")
        cls.expected = {
            "protocol_id": aggregate.PROTOCOL_ID, "implementation_sha": cls.sha,
            "config_sha256": cls.config_hash, "requirements_sha256": cls.requirements_hash,
            "run_id": 321, "run_attempt": 2, "ref": cls.ref, "workflow_sha": cls.sha,
        }

    def validate(self):
        artifacts, _, _ = aggregate._validate_source_ledger(self.ledger_path)
        return aggregate._validate_campaign(
            self.rows_dir, protocol_sha256=aggregate.EXPECTED_PROTOCOL_SHA256,
            expected_provenance=self.expected, source_artifacts=artifacts,
        )

    def test_complete_runner_artifact_chain_and_mixed_infrastructure_attempts(self) -> None:
        rows, ledger = self.validate()
        self.assertEqual(len(rows), 30)
        self.assertEqual(len(ledger), 30)
        self.assertEqual(sum(len(row["files"]) for row in ledger), 210)
        self.assertEqual(rows[0]["provenance"]["run_attempt"], 2)
        self.assertEqual(rows[1]["provenance"]["run_attempt"], 1)
        self.assertTrue(all(row["models"][arm]["reload_verification"] == "PASS_EXACT_NON_TEST_PROBE"
                            for row in rows for arm in aggregate.ARM_NAMES))

    def test_structured_environment_round_trip_and_tampering(self) -> None:
        path = self.rows_dir / self.entries[0]["name"] / "seed-41001.json"
        provenance = json.loads(path.read_text())["provenance"]
        normalized = aggregate._validate_provenance(provenance, label="row", expected={})
        self.assertEqual(aggregate._validate_provenance(provenance, label="status", expected=normalized), normalized)
        altered = copy.deepcopy(provenance)
        altered["environment"]["fixture"] = "changed"
        with self.assertRaisesRegex(aggregate.EvidenceError, "environment SHA"):
            aggregate._validate_provenance(altered, label="status", expected=normalized)

    def test_missing_duplicate_and_corrupt_model_evidence_fail_closed(self) -> None:
        directory = self.rows_dir / self.entries[0]["name"]
        path = directory / "seed-41001-chc-model.joblib"
        original = path.read_bytes()
        try:
            path.write_bytes(original + b"tampered")
            with self.assertRaisesRegex(aggregate.EvidenceError, "model byte hash"):
                self.validate()
        finally:
            path.write_bytes(original)
        duplicate = directory / "duplicate.json"
        try:
            duplicate.write_text("{}")
            with self.assertRaises(aggregate.EvidenceError):
                self.validate()
        finally:
            duplicate.unlink()
        removed = directory / "seed-41001-status.json"
        content = removed.read_bytes()
        try:
            removed.unlink()
            with self.assertRaises(aggregate.EvidenceError):
                self.validate()
        finally:
            removed.write_bytes(content)

    def test_generation_control_tampering_is_rejected_before_statistics(self) -> None:
        directory = self.rows_dir / self.entries[0]["name"]
        path = directory / "seed-41001-lambda-trace.json"
        original = path.read_bytes()
        trace = json.loads(original)
        trace["generation_trace"][0]["lambda_after"] = 39.0
        try:
            path.write_text(json.dumps(trace))
            with self.assertRaisesRegex(aggregate.EvidenceError, "generation transcript"):
                self.validate()
        finally:
            path.write_bytes(original)

    def test_cli_succeeds_and_requires_fixed_source_ledger(self) -> None:
        output = self.root / "aggregate-output"
        args = ["aggregate", str(self.rows_dir), "--protocol", str(self.protocol),
                "--expected-protocol-sha256", aggregate.EXPECTED_PROTOCOL_SHA256,
                "--expected-content-freeze-commit", "939914a33d21709526ef12538170ce806b45e3a3",
                "--expected-implementation-sha", self.sha, "--expected-config-sha256", self.config_hash,
                "--expected-requirements-sha256", self.requirements_hash, "--expected-run-id", "321",
                "--expected-run-attempt", "2", "--expected-ref", self.ref,
                "--expected-workflow-sha", self.sha, "--source-artifact-ledger", str(self.ledger_path),
                "--output-dir", str(output)]
        with patch.object(sys, "argv", args), patch("sys.stdout", new_callable=StringIO):
            aggregate.main()
        status = json.loads((output / "aggregate-status.json").read_text())
        self.assertTrue(status["protocol_valid"])
        self.assertEqual(status["exit_code"], 0)
        self.assertEqual(status["seed_count"], 30)
        original_analysis = aggregate.analyze_rows
        def negative_analysis(rows):
            changed = copy.deepcopy(rows)
            for row in changed:
                row["arms"][aggregate.CHC_ARM]["terminal"]["test_weighted_balanced_accuracy"] = 0.8
                row["arms"][aggregate.LAMBDA_ARM]["terminal"]["test_weighted_balanced_accuracy"] = 0.798
            return original_analysis(changed)
        # A deliberately negative synthetic decision must not change CLI success.
        with (patch.object(sys, "argv", args), patch("sys.stdout", new_callable=StringIO),
              patch.object(aggregate, "analyze_rows", side_effect=negative_analysis)):
            aggregate.main()
        negative = json.loads((output / "aggregate-status.json").read_text())
        self.assertEqual(negative["exit_code"], 0)
        self.assertEqual(negative["scientific_decision"], "FAIL_JOINT_BRIDGE_CLAIM_QUALITY_NONINFERIORITY")
        with self.assertRaisesRegex(aggregate.EvidenceError, "ledger is required"):
            aggregate._validate_source_ledger(None)


class LeakageAndInputTests(unittest.TestCase):
    def test_registration_push_cannot_authorize_scientific_execution(self) -> None:
        repository = ROOT.parents[1]
        guard = "    if: ${{ github.event_name == 'workflow_dispatch' }}\n"
        for key, label in (("campaign", "protected campaign"),
                           ("reaggregate", "reaggregation")):
            text = (repository / validate_workflows.WORKFLOW_PATHS[key]).read_text()
            with self.subTest(workflow=key):
                validate_workflows._require_dispatch_only(text, label)
                with self.assertRaisesRegex(ValueError, "outside manual dispatch"):
                    validate_workflows._require_dispatch_only(text.replace(guard, ""), label)
                with self.assertRaisesRegex(ValueError, "escaped the PR19 branch"):
                    validate_workflows._require_dispatch_only(
                        text.replace("branches: [research/EU26-21-chcqx-census-old-first]",
                                     "branches: [main]"), label)

    def test_workflow_action_blocks_stop_at_job_boundaries(self) -> None:
        action = validate_workflows.UPLOAD_ARTIFACT
        text = ("jobs:\n  fixture:\n    steps:\n      - uses: " + action +
                "\n        with:\n          name: fixture\n  seed:\n    name: ${{ matrix.seed }}\n"
                "    steps:\n      - uses: " + action + "\n        with:\n          name: seed\n")
        blocks = validate_workflows._action_blocks(text, action)
        self.assertEqual(len(blocks), 2)
        self.assertNotIn("matrix.seed", blocks[0])
        self.assertTrue(validate_workflows.validate(ROOT.parents[1])["pass"])

    def test_objective_cannot_access_test_and_ignores_test_label_changes(self) -> None:
        data = prepared_fixture(41001)
        class NoTestAccess:
            def __getattr__(self, name):
                if "test" in name:
                    raise AssertionError("search touched test")
                return getattr(data, name)
        objective = run_seed._validation_objective(NoTestAccess())
        changed = replace(data, y_test=1-data.y_test, x_test=np.full_like(data.x_test, 9999))
        mask = (1,) * 40
        self.assertEqual(objective(mask), run_seed._validation_objective(changed)(mask))
        self.assertFalse(any("test" in field for field in vars(objective)))

    def test_binary_input_types_are_not_silently_coerced(self) -> None:
        for value in (0.5, "1", True, np.float64(1)):
            with self.subTest(value=value), self.assertRaises(ValueError):
                search.BudgetLedger(toy_objective).evaluate([value] + [0] * 39)
        self.assertEqual(search.validate_mask([np.int64(1)] * 40), (1,) * 40)

    def test_latest_attempt_selection_keeps_prior_successful_seeds_and_history(self) -> None:
        available = [{"id": seed, "name": f"eu26-21-common-bridge-seed-{seed}-321-1",
                      "digest": "sha256:" + "a" * 64, "expired": False}
                     for seed in range(41001, 41031)]
        retry = {**available[0], "id": 99999, "name": "eu26-21-common-bridge-seed-41001-321-2"}
        selected, history = select_seed_artifacts([*available, retry], run_id=321, run_attempt=2)
        self.assertEqual(selected[0]["run_attempt"], 2)
        self.assertEqual(selected[1]["run_attempt"], 1)
        self.assertEqual(len(history), 31)
        with self.assertRaises(ValueError):
            select_seed_artifacts([*available, retry, dict(retry)], run_id=321, run_attempt=2)


if __name__ == "__main__":
    unittest.main()
