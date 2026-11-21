"""CI-only synthetic transport, resume, and dispatch-boundary checks."""
from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch
from zipfile import ZipFile, ZipInfo

from . import dispatch, runner
from .common import guard_main, registered_cases, registered_shards


def json_bytes(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")


def write_zip(path, rows):
    with ZipFile(path, "w") as archive:
        for name, content in rows:
            item = ZipInfo(name)
            item.external_attr = 0o100644 << 16
            archive.writestr(item, content)


class MainDispatchChecks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Synthetic mocks are admitted only after the real CI stage guard.
        cls.protocol, cls.admitted = guard_main()

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.authorization = deepcopy(self.admitted)
        self.authorization["allowed_resume_runs"] = []
        self.authorization["maximum_shards_this_dispatch"] = 30
        self.cases = {row["case_id"]: deepcopy(row) for row in registered_cases()}
        for case in self.cases.values():
            for index, key in enumerate(dispatch.INPUTS, 1):
                case[key] = {"path": key + ".json", "bytes": 2,
                             "sha256": sha256((key + str(index)).encode()).hexdigest()}
        self.shards = registered_shards()

    def record(self, case, *, origin=None):
        fields = {"workflow_run_id": os.environ["GITHUB_RUN_ID"],
                  "workflow_commit": os.environ["GITHUB_SHA"],
                  "authorization_id": self.authorization["authorization_id"],
                  "source_manifest_sha256": self.authorization["source_manifest_sha256"],
                  "inputs_manifest_sha256": "1" * 64}
        if origin is not None:
            fields.update(origin)
        return {**{key: case[key] for key in registered_cases()[0]}, **fields,
                "schema": "population13-main-case-v1", "status": "VERIFIED",
                "artifact_hashes": {name: sha256(name.encode()).hexdigest() for name in dispatch.PAYLOADS},
                **{key + "_sha256": case[key]["sha256"] for key in dispatch.INPUTS}}

    def metadata(self, kind="raw", shard="000", *, artifact_id=1):
        return {"id": artifact_id, "name": f"population13-main-{kind}-{shard}-12345",
                "expired": False, "size_in_bytes": 128, "digest": "sha256:" + "a" * 64,
                "workflow_run": {"id": 12345, "head_sha": "b" * 40}}

    def case_files(self, parent, case):
        folder = parent / case["case_id"]
        folder.mkdir(parents=True)
        record = self.record(case)
        for name in dispatch.PAYLOADS:
            content = (json_bytes({"verification_status": "VERIFIED"})
                       if name == "verification.json" else b"synthetic canonical payload")
            (folder / name).write_bytes(content)
            record["artifact_hashes"][name] = sha256(content).hexdigest()
        (folder / "record.json").write_bytes(json_bytes(record))
        return folder, record

    def test_artifact_pairs_require_both_exact_immutable_artifacts(self):
        rows = [self.metadata(artifact_id=1), self.metadata("index", artifact_id=2)]
        with patch.object(dispatch, "api_json", return_value={"artifacts": rows, "total_count": 2}):
            result = dispatch.artifact_pairs("12345", "b" * 40, "synthetic-token")
        self.assertEqual(set(result), {"000"})
        self.assertEqual(result["000"]["raw"]["sha256"], "a" * 64)
        for incomplete in ([rows[0]], [rows[1]]):
            with self.subTest(kind=incomplete[0]["name"]), \
                    patch.object(dispatch, "api_json", return_value={"artifacts": incomplete, "total_count": 1}):
                with self.assertRaises(ValueError):
                    dispatch.artifact_pairs("12345", "b" * 40, "synthetic-token")

    def test_paginated_duplicate_and_unknown_artifacts_are_not_missing_results(self):
        raw = self.metadata()
        variants = ({"artifacts": [], "total_count": 1},
                    {"artifacts": [raw, deepcopy(raw)], "total_count": 2},
                    {"artifacts": [{**raw, "name": "population13-main-raw-999-12345"}], "total_count": 1})
        for value in variants:
            with self.subTest(value=value), patch.object(dispatch, "api_json", return_value=value):
                with self.assertRaises(ValueError):
                    dispatch.artifact_pairs("12345", "b" * 40, "synthetic-token")

    def test_artifact_origin_digest_expiry_and_bound_are_required(self):
        base = self.metadata()
        variants = ({**base, "expired": True}, {**base, "digest": "sha256:bad"},
                    {**base, "size_in_bytes": dispatch.RAW_CAP + 1},
                    {**base, "workflow_run": {"id": 999, "head_sha": "b" * 40}},
                    {**base, "workflow_run": {"id": 12345, "head_sha": "c" * 40}})
        for value in variants:
            with self.subTest(value=value), self.assertRaises(ValueError):
                dispatch._artifact_entry(value, "raw", "000", "12345", "b" * 40)

    def test_index_keeps_exact_case_paths_and_current_input_hashes(self):
        cases = [self.cases[key] for key in self.shards[0]["case_ids"]]
        rows = [(case["case_id"] + "/record.json", json_bytes(self.record(case))) for case in cases]
        rows.append(("shard.json", json_bytes({"shard_id": "000"})))
        archive = self.root / "index.zip"
        write_zip(archive, rows)
        result = dispatch._index_records(archive, "000", self.authorization, self.cases)
        self.assertEqual(set(result), set(self.shards[0]["case_ids"]))
        changed = deepcopy(self.cases)
        changed[cases[0]["case_id"]]["bank"]["sha256"] = "f" * 64
        with self.assertRaises(ValueError):
            dispatch._index_records(archive, "000", self.authorization, changed)

    def test_index_cannot_alias_a_case_include_payload_or_substitute_origin(self):
        case = self.cases[self.shards[0]["case_ids"][0]]
        record = self.record(case)
        other = self.cases[self.shards[1]["case_ids"][0]]
        invalid_rows = (
            [("../escape", b"bad")],
            [(case["case_id"] + "/journal.json.gz", b"not index metadata")],
            [("wrong-case/record.json", json_bytes(record))],
            [(other["case_id"] + "/record.json", json_bytes(self.record(other)))],
            [(case["case_id"] + "/record.json", json_bytes({**record, "workflow_commit": "f" * 40}))],
        )
        for index, rows in enumerate(invalid_rows):
            archive = self.root / f"bad-index-{index}.zip"
            write_zip(archive, rows)
            with self.subTest(index=index), self.assertRaises(ValueError):
                dispatch._index_records(archive, "000", self.authorization, self.cases)

    def test_index_copies_canonical_metadata_and_detects_payload_corruption(self):
        raw = self.root / "raw"
        case = self.cases[self.shards[0]["case_ids"][0]]
        folder, record = self.case_files(raw, case)
        with patch.object(dispatch, "guard_main", return_value=(self.protocol, self.authorization)):
            result = dispatch.make_index(raw, self.root / "index", "000", self.authorization["authorization_id"])
        self.assertEqual(result["verified_cases"], 1)
        self.assertEqual((self.root / "index" / case["case_id"] / "record.json").read_bytes(),
                         (folder / "record.json").read_bytes())
        self.assertEqual({p.name for p in (self.root / "index" / case["case_id"]).iterdir()}, {"record.json"})
        (folder / "journal.json.gz").write_bytes(b"changed canonical bytes")
        with patch.object(dispatch, "guard_main", return_value=(self.protocol, self.authorization)):
            with self.assertRaises(ValueError):
                dispatch.make_index(raw, self.root / "changed-index", "000", self.authorization["authorization_id"])

    def test_late_failure_disqualifies_an_earlier_verified_record(self):
        raw = self.root / "raw"
        case = self.cases[self.shards[0]["case_ids"][0]]
        folder, _ = self.case_files(raw, case)
        failure = folder / "failure.json"
        failure.write_bytes(json_bytes({"status": "FAILED_OR_INTERRUPTED", "case_id": case["case_id"]}))
        with patch.object(dispatch, "guard_main", return_value=(self.protocol, self.authorization)):
            result = dispatch.make_index(raw, self.root / "index", "000", self.authorization["authorization_id"])
        self.assertEqual(result["verified_cases"], 0)
        self.assertEqual(runner._retained_index(raw), {})
        self.assertTrue(failure.exists())
        self.assertTrue((folder / "record.json").exists())
        failure.write_bytes(json_bytes({"status": "FAILED_OR_INTERRUPTED", "case_id": "different-case"}))
        with self.assertRaises(ValueError):
            runner._retained_index(raw)

    def test_extraction_checks_traversal_aliases_and_total_expansion_before_writing(self):
        archive = self.root / "valid.zip"
        write_zip(archive, [("case/member.bin", b"1234")])
        budget = {"used": 0, "limit": 4}
        dispatch._extract(archive, self.root / "expanded", budget)
        self.assertEqual((self.root / "expanded/case/member.bin").read_bytes(), b"1234")
        self.assertEqual(budget["used"], 4)
        with self.assertRaises(ValueError):
            dispatch._extract(archive, self.root / "expanded", {"used": 0, "limit": 4})
        with self.assertRaises(ValueError):
            dispatch._extract(archive, self.root / "too-small", {"used": 0, "limit": 3})
        bad = self.root / "bad.zip"
        write_zip(bad, [("../escape", b"bad")])
        with self.assertRaises(ValueError):
            dispatch._extract(bad, self.root / "unsafe", {"used": 0, "limit": 10})
        self.assertFalse((self.root / "escape").exists())

    def test_initial_plan_registers_thirty_shards_and_no_search_or_token_access(self):
        with (patch.object(dispatch, "guard_main", return_value=(self.protocol, self.authorization)),
              patch.object(dispatch, "_prepared", return_value=(self.cases, "1" * 64)),
              patch.object(dispatch, "_token") as token,
              patch.dict(os.environ, {"GITHUB_OUTPUT": ""})):
            result = dispatch.plan(self.root / "inputs", self.root / "plan", "",
                                   self.authorization["authorization_id"])
        self.assertEqual(len(result["active_shards"]), 30)
        self.assertEqual(result["completed_prior_shards"], [])
        self.assertTrue(result["has_cases"])
        self.assertEqual(result["ga_runs_started_by_planning"], 0)
        token.assert_not_called()

    def test_unadmitted_resume_cannot_turn_into_an_empty_prior_run(self):
        with (patch.object(dispatch, "guard_main", return_value=(self.protocol, self.authorization)),
              patch.object(dispatch, "_prepared", return_value=(self.cases, "1" * 64)),
              patch.object(dispatch, "_token") as token):
            with self.assertRaises(ValueError):
                dispatch.plan(self.root / "inputs", self.root / "plan", "12345",
                              self.authorization["authorization_id"])
            token.assert_not_called()

    def test_full_resume_omits_all_search_jobs_but_retains_thirty_raw_origins(self):
        previous = {"workflow_run_id": "12345", "workflow_commit": "b" * 40,
                    "authorization_id": "previous-main-grant",
                    "source_manifest_sha256": self.authorization["source_manifest_sha256"],
                    "inputs_manifest_sha256": "2" * 64}
        self.authorization["allowed_resume_runs"] = [previous]
        pairs = {row["shard_id"]: {"raw": {"id": index * 2 + 1}, "index": {"id": index * 2 + 2}}
                 for index, row in enumerate(self.shards)}

        def records(path, shard_id, authorization, cases):
            selected = next(row for row in self.shards if row["shard_id"] == shard_id)
            return {key: self.record(cases[key], origin=previous) for key in selected["case_ids"]}

        with (patch.object(dispatch, "guard_main", return_value=(self.protocol, self.authorization)),
              patch.object(dispatch, "_prepared", return_value=(self.cases, "1" * 64)),
              patch.object(dispatch, "_token", return_value="synthetic-token"),
              patch.object(dispatch, "_run") as origin_check,
              patch.object(dispatch, "artifact_pairs", return_value=pairs),
              patch.object(dispatch, "download_archive") as download,
              patch.object(dispatch, "_index_records", side_effect=records),
              patch.dict(os.environ, {"GITHUB_OUTPUT": ""})):
            result = dispatch.plan(self.root / "inputs", self.root / "plan", "12345",
                                   self.authorization["authorization_id"])
        self.assertFalse(result["has_cases"])
        self.assertEqual(result["active_shards"], [])
        self.assertEqual(len(result["completed_prior_shards"]), 30)
        self.assertEqual(result["ga_runs_started_by_planning"], 0)
        self.assertEqual(download.call_count, 30)
        origin_check.assert_called_once_with("12345", previous, "synthetic-token", completed=True)

    def test_restore_without_prior_evidence_does_not_contact_github_or_overwrite(self):
        value = {"schema": "population13-main-dispatch-v1", **dispatch._current_origin(self.authorization),
                 "inputs_manifest_sha256": "1" * 64,
                 "active_shards": [{"shard_id": row["shard_id"], "prior_raw": None} for row in self.shards],
                 "completed_prior_shards": []}
        plan = self.root / "dispatch.json"
        plan.write_bytes(json_bytes(value))
        with (patch.object(dispatch, "guard_main", return_value=(self.protocol, self.authorization)),
              patch.object(dispatch, "_token") as token):
            result = dispatch.restore(plan, "000", self.root / "restored", self.authorization["authorization_id"])
            self.assertFalse(result["restored"])
            token.assert_not_called()
            with self.assertRaises(ValueError):
                dispatch.restore(plan, "000", self.root / "restored", self.authorization["authorization_id"])

    def test_missing_current_raw_artifact_blocks_collection_before_any_download(self):
        value = {"active_shards": [{"shard_id": "000", "prior_raw": None}], "completed_prior_shards": []}
        with (patch.object(dispatch, "guard_main", return_value=(self.protocol, self.authorization)),
              patch.object(dispatch, "_dispatch", return_value=value),
              patch.object(dispatch, "_token", return_value="synthetic-token"),
              patch.object(dispatch, "_run"),
              patch.object(dispatch, "api_json", return_value={"artifacts": [], "total_count": 0}),
              patch.object(dispatch, "download_archive") as download):
            with self.assertRaises(ValueError):
                dispatch.collect(self.root / "plan", self.root / "collected", self.authorization["authorization_id"])
            download.assert_not_called()
        self.assertFalse((self.root / "collected").exists())

    def test_real_admission_precedes_preparation_and_network(self):
        with (patch.object(dispatch, "guard_main", side_effect=ValueError("not admitted")),
              patch.object(dispatch, "_prepared") as prepared,
              patch.object(dispatch, "_token") as token):
            with self.assertRaises(ValueError):
                dispatch.plan(self.root / "inputs", self.root / "plan", "", "unapproved-main")
            prepared.assert_not_called()
            token.assert_not_called()


if __name__ == "__main__":
    unittest.main()
