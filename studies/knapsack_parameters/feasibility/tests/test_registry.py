"""CI-only adversarial registry fixtures; no GA or KPLIB preparation runs."""

from copy import deepcopy
import hashlib
from pathlib import Path
import tempfile
import unittest

from studies.knapsack_parameters.feasibility import registry
from studies.knapsack_parameters.feasibility.data_audit import parse_instance, write_json
from studies.knapsack_parameters.feasibility.prepare_case import member_manifest, prepare_instance


SHA = "a" * 40
DATA_SHA = "b" * 64


def transport_fixture():
    ids = [f"{label}-s{index:03d}" for label in ("UC", "WC", "SC") for index in range(10)]
    common = {"protocol_id": registry.PROTOCOL_ID, "implementation_sha": SHA, "source_run_id": 999, "run_attempt": 1}
    sources = {"schema_version": "knapsack-feasibility-case-sources-v1", **common, "artifacts": []}
    ledger = {"schema_version": "knapsack-feasibility-case-transport-v1", **common, "downloads": []}
    api = {"source_run_id": 999, "run_attempt": 1, "artifacts": []}
    for index, instance_id in enumerate(ids, 1):
        name = f"knapsack-feasibility-case-{instance_id}-999-1"
        sources["artifacts"].append({"id": index, "name": name, "digest": "sha256:" + "c" * 64, "instance_id": instance_id, **common})
        ledger["downloads"].append({"artifact_id": index, "name": name, "sha256": "c" * 64, "bytes": 100, "instance_id": instance_id, **common})
        api["artifacts"].append({"id": index, "name": name, "digest": "sha256:" + "c" * 64, "size_in_bytes": 100, "expired": False,
                                 "workflow_run": {"id": 999, "head_sha": SHA, "head_branch": "research/masters-ga-knapsack-parameters"}})
    return ids, sources, ledger, api


class RegistryTests(unittest.TestCase):
    def test_transport_requires_complete_unique_exact_sha_sources(self):
        ids, sources, ledger, api = transport_fixture()
        self.assertEqual(list(registry._transport(sources, ledger, ids, SHA, api)), ids)
        for change in ("missing", "duplicate", "mixed_sha", "receipt_identity", "wrong_digest"):
            selected, receipts, metadata = deepcopy(sources), deepcopy(ledger), deepcopy(api)
            if change == "missing":
                selected["artifacts"].pop()
            elif change == "duplicate":
                selected["artifacts"][1]["id"] = selected["artifacts"][0]["id"]
            elif change == "mixed_sha":
                selected["artifacts"][0]["implementation_sha"] = "d" * 40
            elif change == "receipt_identity":
                receipts["downloads"][0]["instance_id"] = ids[1]
            else:
                metadata["artifacts"][0]["digest"] = "sha256:" + "e" * 64
            with self.subTest(change=change), self.assertRaises(ValueError):
                registry._transport(selected, receipts, ids, SHA, metadata)

    def test_family_gate_does_not_count_three_classes_as_three_families(self):
        entries = [{"family": f"s{i:03d}", "status": "ADMITTED_STRICT_LOCAL", "technically_complete": True} for i in range(4) for _ in range(3)]
        self.assertEqual(registry._decision(entries)["decision"], "LOCAL_SERIES_NOT_READY")
        entries.append({"family": "s004", "status": "ADMITTED_PLATEAU_LOCAL", "technically_complete": True})
        self.assertEqual(registry._decision(entries)["decision"], "MINIMUM_FEASIBILITY_MET")
        entries.append({"family": "s009", "status": "RESOURCE_NOT_EVALUATED", "technically_complete": False})
        self.assertEqual(registry._decision(entries)["decision"], "TECHNICALLY_INCOMPLETE")

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.folder = Path(self.temporary.name) / "case"
        raw = ("100\n10\n10 6\n8 5\n8 5\n" + "1 100\n" * 97).encode()
        self.instance = parse_instance(raw, "fixture.kp", class_label="UC", family="s000", index=0)
        self.source_file = {"sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw)}
        self.provenance = {"protocol_id": registry.PROTOCOL_ID, "protocol_sha256": registry.PROTOCOL_SHA256,
                           "registration_commit_sha": registry.REGISTRATION_SHA, "source_commit_sha": registry.SOURCE_SHA,
                           "implementation_sha": SHA, "workflow_sha": SHA, "data_freeze_commit_sha": registry.FREEZE_SHA,
                           "data_manifest_sha256": DATA_SHA, "run_id": 999, "run_attempt": 1,
                           "input_file_manifest_sha256": "c" * 64, "runtime_lock_sha256": "d" * 64,
                           "audit_transport_sha256": "e" * 64, "python_version": "3.12.14",
                           "source_audit_run_id": 37576847587, "source_audit_artifact_id": 11463057072,
                           "artifact_name": "knapsack-feasibility-case-UC-s000-999-1"}
        self.source = {"source_run_id": 999, "run_attempt": 1, "name": self.provenance["artifact_name"]}
        identity = {"source_path": "fixture.kp", **self.source_file, "data_manifest_sha256": DATA_SHA, "source_commit_sha": registry.SOURCE_SHA}
        self.case = prepare_instance(self.instance, self.provenance, identity, self.folder, deadline=None)

    def validate(self):
        return registry._validate_case(self.folder, self.instance, self.source_file, self.source, SHA, self.provenance)

    def refresh(self):
        write_json(self.folder / "case.json", self.case)
        terminal = registry.read_json(self.folder / "execution-status.json")
        terminal["status"] = self.case["status"]
        write_json(self.folder / "execution-status.json", terminal)
        member_manifest(self.folder, self.provenance)

    def test_complete_case_revalidates_every_neighbor(self):
        case, complete = self.validate()
        self.assertTrue(complete)
        self.assertEqual(case["status"], "ADMITTED_STRICT_LOCAL")
        self.assertEqual(case["certificate"]["neighbor_count"], 5050)

    def test_corrupt_member_and_unlisted_nested_manifest_are_rejected(self):
        path = self.folder / "case.json"
        path.write_bytes(path.read_bytes() + b" ")
        with self.assertRaises(ValueError):
            self.validate()
        self.refresh()
        nested = self.folder / "nested/file_manifest.json"
        nested.parent.mkdir()
        nested.write_bytes(b"{}")
        with self.assertRaises(ValueError):
            self.validate()

    def test_rehashed_wrong_admission_or_boolean_counter_still_rejected(self):
        self.case["status"] = "EXCLUDED_GLOBAL_CENTER"
        self.refresh()
        with self.assertRaises(ValueError):
            self.validate()
        self.case["status"] = "ADMITTED_STRICT_LOCAL"
        self.case["preparation"]["pass_trace"][0]["pass"] = True
        self.refresh()
        with self.assertRaises(ValueError):
            self.validate()

    def test_mixed_sha_even_with_new_member_hashes_rejected(self):
        self.case["provenance"] = {**self.provenance, "implementation_sha": "f" * 40}
        self.refresh()
        with self.assertRaises(ValueError):
            self.validate()

    def test_duplicate_json_keys_and_nonfinite_values_rejected(self):
        path = Path(self.temporary.name) / "invalid.json"
        for raw in (b'{"status":1,"status":2}', b'{"number":NaN}'):
            path.write_bytes(raw)
            with self.assertRaises(ValueError):
                registry.read_json(path)


if __name__ == "__main__":
    unittest.main()
