from __future__ import annotations

import copy
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

from eu2616.source import (
    SourceIdentityError,
    assert_same_identity,
    authenticate_checkout,
    probe_alg_source,
    verify_member,
)

from support import CONTRACT, upstream


class SourceIdentityTests(unittest.TestCase):
    def test_exact_checkout_authenticates(self) -> None:
        identity = authenticate_checkout(upstream(), CONTRACT)
        self.assertEqual(identity["commit"], CONTRACT["upstream"]["commit"])
        self.assertEqual(identity["tree"], CONTRACT["upstream"]["tree"])
        self.assertEqual(identity["tag"], "v3.0")
        self.assertEqual(len(identity["members"]), 6)

    def test_alg_hash_is_exact(self) -> None:
        member = next(
            item for item in CONTRACT["required_members"] if item["path"].endswith("Alg.java")
        )
        observed = verify_member(upstream(), member)
        self.assertEqual(
            observed["sha256"],
            "5581a346307475f090fde878fe5c089602bde6308adba7df0016a343b191b388",
        )

    def test_license_hash_is_exact(self) -> None:
        member = next(
            item for item in CONTRACT["required_members"] if item["path"] == "LICENSE.md"
        )
        observed = verify_member(upstream(), member)
        self.assertEqual(
            observed["sha256"],
            "8646559c866597b7bf28d110cde63de18f6d97354bf22559053301bc3ca492c5",
        )

    def test_source_tokens_are_ordered(self) -> None:
        probe = probe_alg_source(upstream(), CONTRACT)
        self.assertTrue(probe["strictly_ordered"])
        self.assertTrue(probe["best_average_assignment_before_guard"])
        self.assertTrue(probe["stop_probe_after_probability_updates"])
        self.assertFalse(probe["probability_clamp_present"])

    def test_identity_stability_accepts_same_snapshot(self) -> None:
        identity = authenticate_checkout(upstream(), CONTRACT)
        assert_same_identity(identity, copy.deepcopy(identity))

    def test_identity_stability_rejects_member_change(self) -> None:
        before = authenticate_checkout(upstream(), CONTRACT)
        after = copy.deepcopy(before)
        after["members"][0]["sha256"] = "0" * 64
        with self.assertRaises(SourceIdentityError):
            assert_same_identity(before, after)

    def test_wrong_expected_hash_fails(self) -> None:
        member = copy.deepcopy(CONTRACT["required_members"][1])
        member["sha256"] = "0" * 64
        with self.assertRaises(SourceIdentityError):
            verify_member(upstream(), member)

    def test_wrong_expected_size_fails(self) -> None:
        member = copy.deepcopy(CONTRACT["required_members"][1])
        member["bytes"] += 1
        with self.assertRaises(SourceIdentityError):
            verify_member(upstream(), member)

    def test_wrong_expected_blob_fails(self) -> None:
        member = copy.deepcopy(CONTRACT["required_members"][1])
        member["git_blob"] = "0" * 40
        with self.assertRaises(SourceIdentityError):
            verify_member(upstream(), member)

    def test_missing_member_fails(self) -> None:
        member = copy.deepcopy(CONTRACT["required_members"][1])
        member["path"] = "src/g3pkemlc/Missing.java"
        with self.assertRaises(SourceIdentityError):
            verify_member(upstream(), member)

    def test_parent_member_path_fails(self) -> None:
        member = copy.deepcopy(CONTRACT["required_members"][1])
        member["path"] = "../outside"
        with self.assertRaises(SourceIdentityError):
            verify_member(upstream(), member)

    def test_non_repository_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            with self.assertRaises(SourceIdentityError):
                authenticate_checkout(Path(temporary), CONTRACT)

    def test_wrong_contract_commit_fails(self) -> None:
        changed = copy.deepcopy(CONTRACT)
        changed["upstream"]["commit"] = "0" * 40
        with self.assertRaises(SourceIdentityError):
            authenticate_checkout(upstream(), changed)

    def test_dirty_and_untracked_checkouts_fail(self) -> None:
        for mutation in ("tracked", "untracked"):
            with self.subTest(mutation=mutation), tempfile.TemporaryDirectory() as temporary:
                clone = Path(temporary) / "clone"
                subprocess.run(
                    ["git", "clone", "--quiet", "--no-hardlinks", os.fspath(upstream()), os.fspath(clone)],
                    check=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                )
                subprocess.run(
                    ["git", "-C", os.fspath(clone), "checkout", "--quiet", CONTRACT["upstream"]["commit"]],
                    check=True,
                )
                if mutation == "tracked":
                    with (clone / "src/g3pkemlc/Alg.java").open("ab") as handle:
                        handle.write(b"\n")
                else:
                    (clone / "untracked-audit-file").write_bytes(b"x")
                with self.assertRaises(SourceIdentityError):
                    authenticate_checkout(clone, CONTRACT)


if __name__ == "__main__":
    unittest.main()
