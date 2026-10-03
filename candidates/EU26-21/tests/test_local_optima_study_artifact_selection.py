"""CI-only checks for deterministic retry metadata, without scientific runs."""
from copy import deepcopy
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from local_optima_study import artifact_selection as selection  # noqa: E402
from local_optima_study.contract import (  # noqa: E402
    CASE_SEEDS, PROTOCOL_SHA256, REGISTRY_SCHEMA, file_sha256, read_json, write_json,
)

SHA = "a" * 40
RUN_ID = 77
DIGEST = "sha256:" + "b" * 64


def artifact(seed, *, attempt=1, repeat=None):
    kind = "case" if repeat is None else "escape"
    stem = f"{seed}" if repeat is None else f"{seed}-{repeat}"
    return {
        "id": seed * 1000 + (repeat or 0) * 100 + attempt,
        "name": f"eu26-21-local-{kind}-{stem}-{RUN_ID}-{attempt}",
        "digest": DIGEST, "expired": False, "size_in_bytes": 100,
        "workflow_run": {"id": RUN_ID, "head_sha": SHA},
    }


def case_ledger():
    return {"artifacts": [artifact(seed) for seed in CASE_SEEDS]}


def registry(eligible=(42001,)):
    return {
        "schema": REGISTRY_SCHEMA, "implementation_sha": SHA,
        "source_run_id": RUN_ID, "protocol_sha256": PROTOCOL_SHA256,
        "all_case_records_frozen": 30, "escape_outcomes_inspected": False,
        "cases": [{"seed": seed, "eligible": seed in eligible} for seed in CASE_SEEDS],
    }


class ArtifactSelectionTests(unittest.TestCase):
    def test_complete_case_ledger_retained_without_mutating_raw(self):
        raw = case_ledger()
        before = deepcopy(raw)
        result = selection.select_artifacts(raw, kind="case", expected_sha=SHA, source_run_id=RUN_ID)
        self.assertEqual(result["artifacts"], raw["artifacts"])
        self.assertEqual(raw, before)
        self.assertEqual(result["selection"]["selected_count"], 30)
        self.assertEqual(result["selection"]["superseded_artifacts"], [])
        self.assertFalse(result["selection"]["scientific_artifacts_opened"])

    def test_highest_attempt_selected_independently_of_input_order_or_outcome(self):
        raw = case_ledger()
        newer = artifact(42001, attempt=3)
        newer["content_hint"] = "failure-status-or-scientific-nonexit-not-inspected"
        raw["artifacts"] = [newer, artifact(42001, attempt=2)] + list(reversed(raw["artifacts"]))
        result = selection.select_artifacts(raw, kind="case", expected_sha=SHA, source_run_id=RUN_ID)
        self.assertEqual(result["artifacts"][0], newer)
        self.assertEqual(len(result["artifacts"]), 30)
        self.assertEqual(result["selection"]["raw_upload_count"], 32)
        self.assertEqual(len(result["selection"]["superseded_artifacts"]), 2)
        self.assertTrue(result["selection"]["latest_artifact_still_requires_manifest_validation"])

    def test_escape_selection_uses_exact_frozen_eligible_pairs(self):
        frozen = registry((42001, 42003))
        raw = {"artifacts": [artifact(seed, repeat=repeat) for seed in (42001, 42003) for repeat in range(1, 6)]}
        newer = artifact(42003, repeat=4, attempt=2)
        raw["artifacts"].append(newer)
        result = selection.select_artifacts(raw, kind="escape", expected_sha=SHA, source_run_id=RUN_ID, registry=frozen)
        self.assertEqual(len(result["artifacts"]), 10)
        self.assertEqual(result["artifacts"][8], newer)
        self.assertEqual(result["selection"]["expected_key_count"], 10)

    def test_empty_registry_produces_empty_escape_selection(self):
        result = selection.select_artifacts({"artifacts": []}, kind="escape", expected_sha=SHA,
                                            source_run_id=RUN_ID, registry=registry(()))
        self.assertEqual(result["artifacts"], [])
        self.assertEqual(result["selection"]["selected_artifact_ids"], [])
        self.assertEqual(result["selection"]["expected_key_count"], 0)

    def test_missing_case_or_repeat_fails_not_excluded_from_count(self):
        raw = case_ledger()
        raw["artifacts"].pop()
        with self.assertRaisesRegex(ValueError, "missing expected"):
            selection.select_artifacts(raw, kind="case", expected_sha=SHA, source_run_id=RUN_ID)
        raw = {"artifacts": [artifact(42001, repeat=repeat) for repeat in range(1, 5)]}
        with self.assertRaisesRegex(ValueError, "missing expected"):
            selection.select_artifacts(raw, kind="escape", expected_sha=SHA, source_run_id=RUN_ID, registry=registry())

    def test_duplicate_name_id_or_key_attempt_is_rejected(self):
        for duplicate in (deepcopy(artifact(42001)), {**artifact(42001), "id": 999999}):
            with self.subTest(duplicate=duplicate):
                raw = case_ledger()
                raw["artifacts"].append(duplicate)
                with self.assertRaises(ValueError):
                    selection.select_artifacts(raw, kind="case", expected_sha=SHA, source_run_id=RUN_ID)
        raw = case_ledger()
        raw["artifacts"][1]["id"] = raw["artifacts"][0]["id"]
        with self.assertRaisesRegex(ValueError, "duplicate"):
            selection.select_artifacts(raw, kind="case", expected_sha=SHA, source_run_id=RUN_ID)

    def test_invalid_identity_expiry_digest_and_name_fail_closed(self):
        updates = [
            {"id": True}, {"id": 0}, {"expired": True}, {"expired": None},
            {"digest": None}, {"digest": "sha256:" + "c" * 63},
            {"digest": "sha512:" + "c" * 64}, {"size_in_bytes": 0},
            {"workflow_run": {"id": RUN_ID, "head_sha": "c" * 40}},
            {"workflow_run": {"id": RUN_ID + 1, "head_sha": SHA}},
            {"workflow_run": None}, {"name": "eu26-21-local-case-42001-77-0"},
            {"name": "eu26-21-local-case-42001-78-1"},
            {"name": "eu26-21-local-case-42000-77-1"},
            {"name": "eu26-21-local-case-042001-77-1"},
            {"name": "eu26-21-local-case-42001-77-1-extra"},
        ]
        for update in updates:
            with self.subTest(update=update):
                raw = case_ledger()
                raw["artifacts"][0].update(update)
                with self.assertRaises(ValueError):
                    selection.select_artifacts(raw, kind="case", expected_sha=SHA, source_run_id=RUN_ID)

    def test_escape_artifact_for_ineligible_case_is_rejected(self):
        raw = {"artifacts": [artifact(42001, repeat=repeat) for repeat in range(1, 6)]}
        raw["artifacts"].append(artifact(42002, repeat=1))
        with self.assertRaisesRegex(ValueError, "not an expected"):
            selection.select_artifacts(raw, kind="escape", expected_sha=SHA, source_run_id=RUN_ID, registry=registry())

    def test_unfrozen_wrong_sha_duplicate_registry_fails(self):
        updates = [
            {"implementation_sha": "c" * 40}, {"source_run_id": RUN_ID + 1},
            {"protocol_sha256": "d" * 64}, {"all_case_records_frozen": 29},
            {"escape_outcomes_inspected": True}, {"schema": "wrong"},
        ]
        for update in updates:
            with self.subTest(update=update):
                frozen = registry(())
                frozen.update(update)
                with self.assertRaises(ValueError):
                    selection.select_artifacts({"artifacts": []}, kind="escape", expected_sha=SHA,
                                                source_run_id=RUN_ID, registry=frozen)
        for problem in ("duplicate", "boolean_eligibility", "missing"):
            with self.subTest(problem=problem):
                frozen = registry(())
                if problem == "duplicate":
                    frozen["cases"][1]["seed"] = 42001
                elif problem == "boolean_eligibility":
                    frozen["cases"][0]["eligible"] = 0
                else:
                    frozen["cases"].pop()
                with self.assertRaises(ValueError):
                    selection.select_artifacts({"artifacts": []}, kind="escape", expected_sha=SHA,
                                                source_run_id=RUN_ID, registry=frozen)

    def test_cli_outputs_fixed_ids_and_preserves_raw_bytes(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            raw_path, selected_path, ids_path = root / "raw.json", root / "selected.json", root / "ids.txt"
            raw = case_ledger()
            raw["artifacts"].append(artifact(42001, attempt=2))
            write_json(raw_path, raw)
            original_bytes = raw_path.read_bytes()
            args = ["artifact_selection", "--raw-ledger", str(raw_path), "--kind", "case",
                    "--expected-sha", SHA, "--source-run-id", str(RUN_ID),
                    "--output-ledger", str(selected_path), "--output-ids", str(ids_path)]
            with patch.object(sys, "argv", args):
                selection.main()
            selected = read_json(selected_path)
            expected_ids = ",".join(str(row["id"]) for row in selected["artifacts"])
            self.assertEqual(ids_path.read_text(encoding="utf-8").strip(), expected_ids)
            self.assertEqual(raw_path.read_bytes(), original_bytes)
            self.assertEqual(selected["selection"]["raw_ledger_file_sha256"], file_sha256(raw_path))

    def test_cli_rejects_registry_digest_mismatch_before_writing(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            raw_path, frozen_path = root / "raw.json", root / "registry.json"
            output, ids = root / "selected.json", root / "ids.txt"
            write_json(raw_path, {"artifacts": []})
            write_json(frozen_path, registry(()))
            args = ["artifact_selection", "--raw-ledger", str(raw_path), "--kind", "escape",
                    "--expected-sha", SHA, "--source-run-id", str(RUN_ID),
                    "--output-ledger", str(output), "--output-ids", str(ids),
                    "--registry", str(frozen_path), "--registry-sha256", "c" * 64]
            with patch.object(sys, "argv", args), self.assertRaisesRegex(ValueError, "byte digest mismatch"):
                selection.main()
            self.assertFalse(output.exists())
            self.assertFalse(ids.exists())


if __name__ == "__main__":
    unittest.main()
