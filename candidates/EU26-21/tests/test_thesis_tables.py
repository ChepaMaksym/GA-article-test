"""Synthetic, CI-only checks for immutable descriptive thesis reporting."""
from __future__ import annotations

import copy
import csv
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from evidence_audit import thesis_tables as report  # noqa: E402


class ThesisTablesTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.rows = self.root / "rows"
        self.rows.mkdir()
        self.expected = self.root / "expected.json"
        self.verified = self.root / "verified.json"
        self.environment = mock.patch.dict("os.environ", {
            "GITHUB_REPOSITORY": "fixture/repository", "GITHUB_RUN_ID": "9",
            "GITHUB_RUN_ATTEMPT": "1", "GITHUB_SHA": "a" * 40,
            "GITHUB_REF": "refs/heads/report", "THESIS_WORKFLOW_SHA": "a" * 40,
        })
        self.environment.start()
        self.addCleanup(self.environment.stop)
        identity = {"schema": report.source.EXPECTED_SCHEMA, "repository": "fixture/repository",
                    "source_run_id": report.RUN_ID, "source_run_attempt": 1,
                    "source_head_sha": report.SOURCE_SHA, "source_workflow_sha": report.SOURCE_SHA,
                    "source_ref": report.SOURCE_REF, "source_workflow_path": report.source.SOURCE_WORKFLOW_PATH}
        entries, verified = [], []
        for seed in report.source.EXPECTED_SEEDS:
            name = f"eu26-21-common-bridge-seed-{seed}-{report.RUN_ID}-1"
            entry = {"seed": seed, "id": seed, "name": name,
                     "digest": "sha256:" + "f" * 64, "run_attempt": 1}
            folder = self.rows / name
            folder.mkdir()
            provenance = {"run_id": report.RUN_ID, "run_attempt": 1,
                          "implementation_sha": report.SOURCE_SHA, "workflow_sha": report.SOURCE_SHA,
                          "ref": report.SOURCE_REF, "protocol_sha256": report.PROTOCOL_SHA,
                          "artifact_name": name}
            arms = {}
            for arm, suffix in zip(report.ARMS, ("chc", "lambda")):
                terminal = {"call": 1, "mask": [1] + [0] * 39, "fitness": [0.7, -0.025],
                            "selected_feature_count": 1}
                trace = {"schema": "eu26-21-common-bridge-trace-v1", "seed": seed,
                         "arm": arm, "provenance": provenance, "objective_calls": 400,
                         "terminal": terminal, "evaluations": [
                             {"call": call, "validation_weighted_balanced_accuracy": 0.7,
                              "best_so_far_weighted_balanced_accuracy": 0.7}
                             for call in range(1, 401)]}
                trace_path = folder / f"seed-{seed}-{suffix}-trace.json"
                self.write(trace_path, trace)
                arms[arm] = {"terminal": {**terminal, "test_weighted_balanced_accuracy": 0.68},
                             "trace_file": trace_path.name,
                             "trace_sha256": report.source._file_sha256(trace_path),
                             "objective_calls": 400, report.AUC_KEY: 0.7}
                (folder / f"seed-{seed}-{suffix}-model.joblib").write_bytes(b"opaque model bytes")
            self.write(folder / f"seed-{seed}.json", {
                "schema": "eu26-21-common-bridge-row-v1", "seed": seed,
                "protocol_id": report.PROTOCOL_ID, "provenance": provenance, "arms": arms})
            for suffix in ("status", "manifest"):
                self.write(folder / f"seed-{seed}-{suffix}.json", {"synthetic": True})
            entries.append(entry)
            verified.append({**entry, "api_run_id": report.RUN_ID, "api_head_sha": report.SOURCE_SHA,
                             "downloaded_zip_sha256": "f" * 64, "extracted_files": [
                                 {"path": path.relative_to(self.rows).as_posix(),
                                  "bytes": path.stat().st_size, "sha256": report.source._file_sha256(path)}
                                 for path in sorted(folder.iterdir())]})
        self.write(self.expected, {**identity, "artifacts": entries})
        self.verification = {**identity, "schema": report.source.OUTPUT_SCHEMA,
                             "verification_status": "PASS", "artifacts": verified,
                             "expected_ledger_sha256": report.source._file_sha256(self.expected)}
        self.write(self.verified, self.verification)

    @staticmethod
    def write(path, value):
        path.write_text(json.dumps(value, sort_keys=True), encoding="utf-8")

    def load(self):
        return report.load_pairs(self.rows, self.expected, self.verified)

    def test_all_pairs_outputs_and_decisions_are_preserved_without_execution(self):
        pairs, curves, provenance = self.load()
        analysis = {endpoint: {"paired_values": [0.0] * 30, "decision": decision}
                    for endpoint, decision in (
                        ("quality_noninferiority", "FAIL_NONINFERIORITY"),
                        ("auc_superiority", "BLOCKED_BY_QUALITY_NONINFERIORITY"),
                        ("feature_count_secondary", "BLOCKED_BY_QUALITY_NONINFERIORITY"))}
        before = copy.deepcopy(analysis)
        output = self.root / "report"
        with mock.patch("common_bridge.search.run_harmonized_chc", side_effect=AssertionError), \
                mock.patch("common_bridge.search.run_lambda_no_reset", side_effect=AssertionError), \
                mock.patch("joblib.load", side_effect=AssertionError), \
                mock.patch("common_bridge.aggregate.analyze_rows", side_effect=AssertionError), \
                mock.patch("common_bridge.aggregate._paired_median_bca", side_effect=AssertionError):
            report.write_report(pairs, curves, provenance, analysis, output)
        self.assertEqual(analysis, before)
        with (output / "paired-seeds.csv").open(encoding="utf-8", newline="") as handle:
            rows = list(csv.DictReader(handle))
        self.assertEqual([int(row["seed"]) for row in rows], list(report.source.EXPECTED_SEEDS))
        manifest = report.source._load_json(output / "report-manifest.json")
        self.assertEqual(manifest["preserved_analysis"], before)
        self.assertEqual(manifest["seed_ledger"], list(report.source.EXPECTED_SEEDS))
        self.assertEqual(manifest["source"]["source_run_id"], report.RUN_ID)
        self.assertFalse(manifest["scientific_decisions_recomputed"])
        self.assertFalse(manifest["scientific_decisions_changed"])
        self.assertEqual(len(manifest["outputs"]), 4)
        for name, entry in manifest["outputs"].items():
            self.assertEqual(report.source._file_sha256(output / name), entry["sha256"])
        self.assertIn("BLOCKED_BY_QUALITY_NONINFERIORITY", (output / "report.md").read_text(encoding="utf-8"))
        changed = copy.deepcopy(analysis)
        changed["quality_noninferiority"]["paired_values"][0] = 0.5
        with self.assertRaisesRegex(ValueError, "preserved analysis pairs"):
            report.write_report(pairs, curves, provenance, changed, self.root / "invalid-report")
        self.assertFalse((self.root / "invalid-report").exists())

    def test_missing_and_duplicate_seeds_rejected(self):
        for mode in ("missing", "duplicate"):
            altered = copy.deepcopy(self.verification)
            if mode == "missing":
                altered["artifacts"].pop()
            else:
                altered["artifacts"][-1] = altered["artifacts"][0]
            self.write(self.verified, altered)
            with self.subTest(mode=mode), self.assertRaises(ValueError):
                self.load()

    def test_corrupt_bytes_rejected(self):
        path = self.rows / self.verification["artifacts"][0]["extracted_files"][0]["path"]
        path.write_bytes(path.read_bytes() + b" ")
        with self.assertRaisesRegex(ValueError, "byte/hash"):
            self.load()

    def test_invalid_row_seed_rejected_even_with_updated_file_hash(self):
        artifact = self.verification["artifacts"][0]
        entry = next(item for item in artifact["extracted_files"] if item["path"].endswith("seed-41001.json"))
        path = self.rows / entry["path"]
        row = report.source._load_json(path)
        row["seed"] = 42001
        self.write(path, row)
        entry.update(bytes=path.stat().st_size, sha256=report.source._file_sha256(path))
        self.write(self.verified, self.verification)
        with self.assertRaisesRegex(ValueError, "row schema/seed"):
            self.load()

    def test_dual_report_hashes_and_identical_analysis(self):
        evidence = self.root / "evidence"
        evidence.mkdir()
        hashes = {}
        for name in report.REPORT_HASHES:
            path = evidence / name
            self.write(path, {"schema": "eu26-21-common-bridge-report-v1", "analysis": {"decision": "FAIL"}})
            hashes[name] = report.source._file_sha256(path)
        with mock.patch.object(report, "REPORT_HASHES", hashes):
            self.assertEqual(report.preserved_analysis(evidence), {"decision": "FAIL"})
            changed = evidence / "reaggregated-report.json"
            self.write(changed, {"schema": "eu26-21-common-bridge-report-v1", "analysis": {"decision": "PASS"}})
            with self.assertRaisesRegex(ValueError, "byte SHA"):
                report.preserved_analysis(evidence)
            hashes[changed.name] = report.source._file_sha256(changed)
            with self.assertRaisesRegex(ValueError, "disagree"):
                report.preserved_analysis(evidence)


if __name__ == "__main__":
    unittest.main()
