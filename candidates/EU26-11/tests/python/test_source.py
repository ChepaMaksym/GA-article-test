from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path

from eu2611.source import SourceIdentityError, verify_source_checkout


CANDIDATE = Path(__file__).resolve().parents[2]
CONTRACT = json.loads(
    (CANDIDATE / "config" / "verification_contract.json").read_text(encoding="utf-8")
)


class SourceTests(unittest.TestCase):
    def test_rejects_a_non_git_directory(self) -> None:
        with tempfile.TemporaryDirectory() as directory, self.assertRaises(SourceIdentityError):
            verify_source_checkout(Path(directory), CONTRACT["source"])

    def test_rejects_a_symbolic_link_checkout(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / "target"
            target.mkdir()
            link = root / "link"
            link.symlink_to(target, target_is_directory=True)
            with self.assertRaises(SourceIdentityError):
                verify_source_checkout(link, CONTRACT["source"])

    def test_source_contract_pins_tag_commit_tree_license_and_members(self) -> None:
        source = CONTRACT["source"]
        self.assertEqual(source["tag"], "v1.0.8")
        self.assertEqual(len(source["commit"]), 40)
        self.assertEqual(len(source["tree"]), 40)
        self.assertEqual(source["license"], "MIT")
        self.assertEqual(
            set(source["members"]),
            {"modcma/modularcmaes.py", "modcma/parameters.py", "LICENSE"},
        )

    @unittest.skipUnless(os.environ.get("EU2611_SOURCE"), "EU2611_SOURCE not set")
    def test_authenticated_source_passes_adaptation_gate(self) -> None:
        observed = verify_source_checkout(
            Path(os.environ["EU2611_SOURCE"]), CONTRACT["source"]
        )
        self.assertEqual(observed["status"], "PASS_SOURCE_ADAPTATION_GATE")
        self.assertEqual(observed["generation_order"], ["mutate", "select", "recombine", "adapt"])
        self.assertIn("covariance_matrix", observed["adaptation_order"])


if __name__ == "__main__":
    unittest.main()
