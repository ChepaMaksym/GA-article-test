from __future__ import annotations

import os
from pathlib import Path
import unittest

from eu2607.core import run_artifact_jump_optimized
from eu2607.source_adapter import (
    EXPECTED_COMMIT,
    EXPECTED_TREE,
    SourceAdapterError,
    authenticate_checkout,
    run_author_artifact,
)


UPSTREAM = os.environ.get("EU2607_UPSTREAM")


@unittest.skipUnless(UPSTREAM, "set EU2607_UPSTREAM for source-native tests")
class SourceNativeTests(unittest.TestCase):
    def test_checkout_identity_and_required_hashes(self):
        identity = authenticate_checkout(Path(UPSTREAM or ""))
        self.assertEqual(identity.commit, EXPECTED_COMMIT)
        self.assertEqual(identity.tree, EXPECTED_TREE)
        self.assertEqual(identity.required_files, 9)
        self.assertTrue(identity.worktree_clean_for_required_files)

    def test_first_two_native_and_cleanroom_rows_are_identical(self):
        root = Path(UPSTREAM or "")
        for run in (1, 2):
            with self.subTest(run=run):
                self.assertEqual(
                    run_author_artifact(root, run),
                    run_artifact_jump_optimized(run),
                )

    def test_invalid_run_fails_before_execution(self):
        with self.assertRaises(SourceAdapterError):
            run_author_artifact(Path(UPSTREAM or ""), 0)


if __name__ == "__main__":
    unittest.main()
