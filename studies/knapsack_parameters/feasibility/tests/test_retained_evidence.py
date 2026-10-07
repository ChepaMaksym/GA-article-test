"""CI-only replay of the exact retained run, never a new preparation series."""

import os
from pathlib import Path
import unittest

from studies.knapsack_parameters.feasibility import registry
from studies.knapsack_parameters.feasibility.data_audit import sha256_bytes
from studies.knapsack_parameters.feasibility.frozen_inputs import STUDY_ROOT, load_frozen_inputs, verify_file_manifest


class RetainedEvidenceTests(unittest.TestCase):
    def test_exact_thirty_case_source_ids_member_bytes_and_scientific_proofs(self):
        retained = STUDY_ROOT / "evidence/run-37637475385"
        self.assertTrue(retained.is_dir(), "the permanent retained proof package is required")
        instances, current_provenance = load_frozen_inputs(os.environ["GITHUB_SHA"])
        verify_file_manifest(retained)
        transport = registry.read_json(STUDY_ROOT / "preparation_transport.json")
        old_sha = "6d008b3444a22585dde2c25c0027779549fddc48"
        self.assertEqual(transport["implementation_sha"], old_sha)
        self.assertEqual(transport["artifact_api_metadata"]["id"], 11490302101)
        self.assertEqual(transport["artifact_api_metadata"]["digest"], "sha256:" + transport["downloaded_zip_sha256"])
        self.assertEqual(sha256_bytes((retained / "registry.json").read_bytes()), transport["registry_sha256"])
        self.assertEqual(sha256_bytes((retained / "file_manifest.json").read_bytes()), transport["member_manifest_sha256"])
        source_map = {row["source_path"]: row for row in registry.read_json(STUDY_ROOT / "inputs/data_manifest.json")["source_files"]}
        ids = [instance.instance_id for instance in instances]
        selected = registry._transport(registry.read_json(retained / "sources.json"), registry.read_json(retained / "transport-ledger.json"), ids,
                                       old_sha, registry.read_json(retained / "artifact-api-metadata.json"))
        stored = registry.read_json(retained / "registry.json")
        self.assertEqual(stored["case_count"], 30)
        self.assertEqual(stored["case_order"], ids)
        self.assertEqual(stored["source_run_id"], 37637475385)
        self.assertEqual(stored["source_run_attempt"], 1)
        self.assertEqual(len(stored["cases"]), 30)
        verified = []
        for instance, entry in zip(instances, stored["cases"], strict=True):
            case, complete = registry._validate_case(retained / "cases" / instance.instance_id, instance, source_map[instance.source_path],
                                                      selected[instance.instance_id], old_sha, current_provenance)
            self.assertEqual(entry["payload"], case)
            self.assertEqual(entry["status"], case["status"])
            self.assertIs(entry["technically_complete"], complete)
            verified.append({"family": instance.family, "status": case["status"], "technically_complete": complete})
        for field, value in registry._decision(verified).items():
            self.assertEqual(stored[field], value)
        first = next((entry["instance_id"] for entry in stored["cases"] if entry["status"].startswith("ADMITTED_")), ids[0])
        self.assertEqual(stored["selected_document_case"], first)


if __name__ == "__main__":
    unittest.main()
