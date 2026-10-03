"""CI-only byte/provenance checks; never rerun the retained scientific series."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import unittest


EVIDENCE = Path(__file__).resolve().parents[1] / "local_optima_study/evidence/2026-10-02"
RUN_ID = 37028835773
IMPLEMENTATION_SHA = "97ffc89e36402711ba5d662869f2bd0783ff2a76"
PROTOCOL_SHA = "8167f46a1adce8d759404d9577101befa183756ca92230e4ac3718c9f46d2ca7"
REPORT_MANIFEST_SHA = "20ab85a9c75d62d86f7ff8228a5b1626c68e8709479b91e6192fee913a8c37d2"
REGISTRY_SHA = "ebcd7cf271620fbd0099fa7fbd79b4f2b8bc6f9951c700a9e25aaf86f06ab757"
RETAINED_FILES = {
    "report/certified-neighborhood.png", "report/comparison.csv",
    "report/comparison-trajectories.png", "report/confusion-matrices-42001.png",
    "report/escape-case-clusters.csv", "report/escape-rates-by-case.png",
    "report/escape-repetitions.csv", "report/feature-ablations.csv",
    "report/per-class-metrics.csv", "report/prepared-cases.csv",
    "report/report-manifest.json", "report/report.md", "report/summary.json",
    "registry/case-attempt-ledger.json", "registry/case-ledger.json",
    "registry/freeze-summary.json", "registry/matrix.json", "registry/registry.json",
    "escape-attempt-ledger.json", "escape-ledger.json",
}


def read_json(relative: str):
    return json.loads((EVIDENCE / relative).read_text(encoding="utf-8"))


def digest(relative: str) -> str:
    return hashlib.sha256((EVIDENCE / relative).read_bytes()).hexdigest()


class RetainedLocalOptimaEvidenceTests(unittest.TestCase):
    def test_complete_inventory_preserves_exact_ci_bytes(self):
        source = read_json("SOURCE.json")
        self.assertEqual(source["schema"], "eu26-21-local-optima-retained-source-v1")
        self.assertEqual(source["source_run_id"], RUN_ID)
        self.assertEqual(source["implementation_sha"], IMPLEMENTATION_SHA)
        self.assertEqual(source["protocol_sha256"], PROTOCOL_SHA)
        self.assertEqual(source["report_manifest_sha256"], REPORT_MANIFEST_SHA)
        self.assertEqual(source["registry_sha256"], REGISTRY_SHA)
        self.assertEqual(set(source["files"]), RETAINED_FILES)
        actual = {path.relative_to(EVIDENCE).as_posix()
                  for path in EVIDENCE.rglob("*") if path.is_file()}
        self.assertEqual(actual, RETAINED_FILES | {"SOURCE.json", "README_UK.md"})
        for relative, identity in source["files"].items():
            with self.subTest(file=relative):
                self.assertEqual((EVIDENCE / relative).stat().st_size, identity["bytes"])
                self.assertEqual(digest(relative), identity["sha256"])

    def test_original_report_manifest_and_registry_are_unchanged(self):
        self.assertEqual(digest("report/report-manifest.json"), REPORT_MANIFEST_SHA)
        self.assertEqual(digest("registry/registry.json"), REGISTRY_SHA)
        protocol = EVIDENCE.parents[1] / "protocol.json"
        self.assertEqual(hashlib.sha256(protocol.read_bytes()).hexdigest(), PROTOCOL_SHA)
        manifest = read_json("report/report-manifest.json")
        self.assertEqual(manifest["schema"], "eu26-21-local-optima-report-manifest-v1")
        self.assertEqual(manifest["source_run_id"], RUN_ID)
        self.assertEqual(manifest["implementation_sha"], IMPLEMENTATION_SHA)
        self.assertEqual(manifest["protocol_sha256"], PROTOCOL_SHA)
        self.assertEqual(manifest["registry_sha256"], REGISTRY_SHA)
        source = read_json("SOURCE.json")
        expected = {path.removeprefix("report/") for path in RETAINED_FILES
                    if path.startswith("report/") and path != "report/report-manifest.json"}
        self.assertEqual(set(manifest["files"]), expected)
        for relative, identity in manifest["files"].items():
            self.assertEqual(identity, source["files"]["report/" + relative])

    def test_frozen_registry_and_pair_matrix_are_complete_without_replacement(self):
        registry = read_json("registry/registry.json")
        self.assertEqual(registry["schema"], "eu26-21-local-optima-frozen-registry-v1")
        self.assertEqual(registry["source_run_id"], RUN_ID)
        self.assertEqual(registry["implementation_sha"], IMPLEMENTATION_SHA)
        self.assertEqual(registry["protocol_sha256"], PROTOCOL_SHA)
        self.assertIs(registry["escape_outcomes_inspected"], False)
        self.assertEqual(registry["all_case_records_frozen"], 30)
        cases = registry["cases"]
        self.assertEqual([row["seed"] for row in cases], list(range(42001, 42031)))
        self.assertEqual({row["seed"] for row in cases if not row["eligible"]},
                         {42001, 42004, 42011, 42016, 42017})
        expected = {(row["seed"], repeat) for row in cases if row["eligible"]
                    for repeat in range(1, 6)}
        matrix = read_json("registry/matrix.json")["include"]
        self.assertEqual(len(matrix), 125)
        self.assertEqual({(row["seed"], row["repeat"]) for row in matrix}, expected)
        freeze = read_json("registry/freeze-summary.json")
        self.assertEqual((freeze["case_count"], freeze["eligible_count"],
                          freeze["escape_pair_count"]), (30, 25, 125))
        self.assertEqual(freeze["registry_sha256"], REGISTRY_SHA)
        self.assertIs(freeze["hypothesis_analysis_performed"], False)

    def test_selected_artifacts_and_scientific_decisions_keep_source_bindings(self):
        registry = read_json("registry/registry.json")
        summary = read_json("report/summary.json")
        for relative, rows, count in (
            ("registry/case-ledger.json", registry["cases"], 30),
            ("escape-ledger.json", summary["escape_source_artifacts"], 125),
        ):
            artifacts = read_json(relative)["artifacts"]
            ids = {item["id"] for item in artifacts}
            self.assertEqual(len(artifacts), count)
            self.assertEqual(len(ids), count)
            expected = {row.get("source_artifact_id", row.get("id")): row for row in rows}
            self.assertEqual(ids, set(expected))
            for item in artifacts:
                with self.subTest(ledger=relative, artifact=item["id"]):
                    self.assertEqual(item["workflow_run"]["id"], RUN_ID)
                    self.assertEqual(item["workflow_run"]["head_sha"], IMPLEMENTATION_SHA)
                    row = expected[item["id"]]
                    self.assertEqual(item["digest"], row.get("source_artifact_digest", row.get("digest")))
                    self.assertEqual(item["name"], row.get("source_artifact_name", row.get("name")))
        self.assertEqual(summary["source_run_id"], RUN_ID)
        self.assertEqual(summary["implementation_sha"], IMPLEMENTATION_SHA)
        self.assertIs(summary["confusion_matrices_pooled_across_models"], False)
        self.assertEqual(summary["historical_noninferiority_status"], "FAIL_NONINFERIORITY_UNCHANGED")
        primary = summary["primary_escape_analysis"]
        self.assertEqual(primary["bootstrap_unit"], "entire_case")
        self.assertEqual(primary["bootstrap_resamples"], 50000)
        self.assertEqual(primary["analysis_seed"], 42031)
        self.assertEqual((primary["eligible_case_count"], primary["paired_repeat_count"]), (25, 125))
        self.assertEqual(primary["estimate"], 0.2)
        self.assertEqual(primary["interval"], [0.128, 0.30400000000000005])
        self.assertEqual(primary["status"], "ADVANTAGE_CONFIRMED")
        self.assertIsNone(summary["comparison_summary"]["full40"]["median_bsf_auc"])


if __name__ == "__main__":
    unittest.main()
