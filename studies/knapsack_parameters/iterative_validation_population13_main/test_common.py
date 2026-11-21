"""CI-only admission checks, without full scientific search runs."""
from __future__ import annotations

from copy import deepcopy
import hashlib
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from . import common


class MainAdmissionChecks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.protocol, cls.authorization = common.guard_main()

    def test_exact_ninety_case_task_seed_and_shard_inventory(self):
        rows = common.registered_cases()
        self.assertEqual(len(rows), 90)
        self.assertEqual(len({row["case_id"] for row in rows}), 90)
        self.assertEqual({row["task_index"] for row in rows}, set(range(3, 33)))
        self.assertEqual({row["seed"] for row in rows}, {150001, 150002, 150003})
        shards = common.registered_shards()
        self.assertEqual([row["shard_id"] for row in shards], [f"{i:03d}" for i in range(30)])
        self.assertEqual([case for row in shards for case in row["case_ids"]],
                         [row["case_id"] for row in rows])
        for shard in shards:
            selected = [row for row in rows if row["case_id"] in shard["case_ids"]]
            self.assertEqual(len({row["task"] for row in selected}), 1)
            self.assertEqual({row["seed"] for row in selected}, {150001, 150002, 150003})

    def test_local_execution_fails_before_reading_a_source_or_token(self):
        with patch.dict(os.environ, {"GITHUB_ACTIONS": "false"}), patch.object(common, "read_json") as read:
            with self.assertRaises(ValueError):
                common.guard_main()
            read.assert_not_called()

    def test_other_repository_ref_event_and_native_rerun_are_rejected(self):
        for key, value in (("GITHUB_REPOSITORY", "other/repository"),
                           ("GITHUB_REF", "refs/heads/main"),
                           ("GITHUB_EVENT_NAME", "push"), ("GITHUB_RUN_ATTEMPT", "2")):
            with self.subTest(key=key), patch.dict(os.environ, {key: value}), \
                    patch.object(common, "read_json") as read:
                with self.assertRaises(ValueError):
                    common.guard_main()
                read.assert_not_called()

    def test_resource_or_publication_permission_cannot_be_inherited(self):
        variants = (("status", "CONSUMED_SUCCESS"), ("fresh_approval", False),
                    ("public_release_approved", False), ("historical_budgets_inherited", True),
                    ("runner_minutes", 40), ("artifact_bytes", 1073741824))
        for key, value in variants:
            authorization = deepcopy(self.authorization)
            authorization[key] = value
            with self.subTest(key=key), patch.object(common, "read_json",
                    side_effect=[deepcopy(self.protocol), authorization]), \
                    patch.object(common, "verify_source") as source:
                with self.assertRaises(ValueError):
                    common.guard_main(self.authorization["authorization_id"])
                source.assert_not_called()

    def test_timeout_room_is_checked_before_source_or_search_access(self):
        authorization = deepcopy(self.authorization)
        authorization["remaining_runner_minutes"] = 16
        authorization["maximum_shards_this_dispatch"] = 0
        with patch.object(common, "read_json", side_effect=[deepcopy(self.protocol), authorization]), \
                patch.object(common, "verify_source") as source:
            with self.assertRaises(ValueError):
                common.guard_main(self.authorization["authorization_id"])
            source.assert_not_called()

    def test_unknown_request_identity_is_rejected(self):
        with self.assertRaises(ValueError):
            common.guard_main("unapproved-main-grant")

    def test_descriptor_rejects_escape_alias_and_modified_bytes(self):
        content = b"retained-source\r\n"
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / "retained.bin"
            target.write_bytes(content)
            entry = {"path": "retained.bin", "bytes": len(content),
                     "sha256": hashlib.sha256(content).hexdigest()}
            self.assertEqual(common.descriptor(root, entry), target.resolve())
            for name in ("../retained.bin", "/retained.bin", "a/../retained.bin", "a//b", "C:/x", "a\\b"):
                with self.subTest(name=name), self.assertRaises(ValueError):
                    common.descriptor(root, {**entry, "path": name})
            target.write_bytes(content.replace(b"\r\n", b"\n"))
            with self.assertRaises(ValueError):
                common.descriptor(root, entry)

    def test_current_origin_requires_the_real_commit_and_authorization(self):
        record = {"workflow_run_id": os.environ["GITHUB_RUN_ID"],
                  "workflow_commit": os.environ["GITHUB_SHA"],
                  "authorization_id": self.authorization["authorization_id"],
                  "source_manifest_sha256": self.authorization["source_manifest_sha256"],
                  "inputs_manifest_sha256": "1" * 64}
        self.assertEqual(common.validate_case_origin(record, self.authorization), record)
        for key, value in (("workflow_commit", "f" * 40), ("authorization_id", "another-origin"),
                           ("source_manifest_sha256", "f" * 64)):
            with self.subTest(key=key), self.assertRaises(ValueError):
                common.validate_case_origin({**record, key: value}, self.authorization)

    def test_prior_origin_is_exact_pinned_and_not_implicitly_current(self):
        authorization = deepcopy(self.authorization)
        record = {"workflow_run_id": "123456789", "workflow_commit": "a" * 40,
                  "authorization_id": "prior-admitted-main-grant",
                  "source_manifest_sha256": authorization["source_manifest_sha256"],
                  "inputs_manifest_sha256": "2" * 64}
        if record["workflow_run_id"] == os.environ["GITHUB_RUN_ID"]:
            record["workflow_run_id"] = "123456788"
        authorization["allowed_resume_runs"] = []
        with self.assertRaises(ValueError):
            common.validate_case_origin(record, authorization)
        authorization["allowed_resume_runs"] = [deepcopy(record)]
        self.assertEqual(common.validate_case_origin(record, authorization), record)
        with self.assertRaises(ValueError):
            common.validate_case_origin({**record, "inputs_manifest_sha256": "3" * 64}, authorization)
        authorization["allowed_resume_runs"].append(deepcopy(record))
        with self.assertRaises(ValueError):
            common.validate_case_origin(record, authorization)


if __name__ == "__main__":
    unittest.main()
