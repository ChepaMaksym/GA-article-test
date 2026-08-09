from __future__ import annotations

import copy
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

from eu2609.source import (
    SourceIdentityError,
    assert_same_identity,
    authenticate_checkout,
    verify_member,
)

from test_support import CONTRACT, upstream


class SourceIdentityTests(unittest.TestCase):
    def test_authenticates_exact_checkout(self) -> None:
        identity = authenticate_checkout(upstream(), CONTRACT)
        self.assertEqual(identity["commit"], CONTRACT["upstream"]["commit"])
        self.assertEqual(identity["tree"], CONTRACT["upstream"]["tree"])
        self.assertTrue(identity["clean"])
        self.assertEqual(identity["member_count"], 8)

    def test_raw_member_identity(self) -> None:
        observed = verify_member(upstream(), CONTRACT["raw_member"])
        self.assertEqual(observed["sha256"], CONTRACT["raw_member"]["sha256"])
        self.assertEqual(observed["git_blob"], CONTRACT["raw_member"]["git_blob"])

    def test_rejects_wrong_expected_hash(self) -> None:
        member = dict(CONTRACT["raw_member"])
        member["sha256"] = "0" * 64
        with self.assertRaises(SourceIdentityError):
            verify_member(upstream(), member)

    def test_rejects_wrong_expected_size(self) -> None:
        member = dict(CONTRACT["raw_member"])
        member["bytes"] += 1
        with self.assertRaises(SourceIdentityError):
            verify_member(upstream(), member)

    def test_rejects_wrong_expected_blob(self) -> None:
        member = dict(CONTRACT["raw_member"])
        member["git_blob"] = "0" * 40
        with self.assertRaises(SourceIdentityError):
            verify_member(upstream(), member)

    def test_rejects_missing_member(self) -> None:
        member = dict(CONTRACT["raw_member"])
        member["path"] = "Raw/not-present.txt"
        with self.assertRaises(SourceIdentityError):
            verify_member(upstream(), member)

    def test_rejects_parent_path(self) -> None:
        member = dict(CONTRACT["raw_member"])
        member["path"] = "../outside"
        with self.assertRaises(SourceIdentityError):
            verify_member(upstream(), member)

    def test_rejects_wrong_commit_contract(self) -> None:
        contract = copy.deepcopy(CONTRACT)
        contract["upstream"]["commit"] = "0" * 40
        with self.assertRaises(SourceIdentityError):
            authenticate_checkout(upstream(), contract)

    def test_rejects_wrong_tree_contract(self) -> None:
        contract = copy.deepcopy(CONTRACT)
        contract["upstream"]["tree"] = "0" * 40
        with self.assertRaises(SourceIdentityError):
            authenticate_checkout(upstream(), contract)

    def test_identity_stability_accepts_same_values(self) -> None:
        identity = authenticate_checkout(upstream(), CONTRACT)
        assert_same_identity(identity, copy.deepcopy(identity))

    def test_identity_stability_rejects_changed_member(self) -> None:
        before = authenticate_checkout(upstream(), CONTRACT)
        after = copy.deepcopy(before)
        after["members"][0]["sha256"] = "0" * 64
        with self.assertRaises(SourceIdentityError):
            assert_same_identity(before, after)

    def test_rejects_non_repository(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            with self.assertRaises(SourceIdentityError):
                authenticate_checkout(Path(temporary), CONTRACT)

    def test_rejects_dirty_and_untracked_checkout(self) -> None:
        for mutation in ("tracked", "untracked"):
            with self.subTest(mutation=mutation), tempfile.TemporaryDirectory() as temporary:
                clone = Path(temporary) / "clone"
                subprocess.run(
                    ["git", "clone", "--quiet", "--no-hardlinks", os.fspath(upstream()), os.fspath(clone)],
                    check=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                )
                if mutation == "tracked":
                    with (clone / "README.md").open("ab") as handle:
                        handle.write(b"\n")
                else:
                    (clone / "untracked-audit-file").write_bytes(b"x")
                with self.assertRaises(SourceIdentityError):
                    authenticate_checkout(clone, CONTRACT)


if __name__ == "__main__":
    unittest.main()
