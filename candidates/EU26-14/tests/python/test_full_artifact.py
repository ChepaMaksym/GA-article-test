from __future__ import annotations

import os
import unittest
from pathlib import Path

from eu2614.pipeline import verify_artifacts


@unittest.skipUnless(os.environ.get("EU2614_ARTIFACT_DIR"), "full artifact directory not supplied")
class FullArtifactTests(unittest.TestCase):
    def test_complete_zenodo_artifact(self) -> None:
        root = Path(os.environ["EU2614_ARTIFACT_DIR"])
        report = verify_artifacts(
            record_json=root / "record.json",
            checksum_manifest=root / "SHA256SUMS",
            source_archive=root / "source.tar.gz",
            result_archive=root / "msc_cec2020.tar.zst",
        )
        self.assertEqual(report["overall_gate"], "PASS_TARGETED_ARTIFACT_REPLAY")
        self.assertEqual(report["status"], "TARGETED_ARTIFACT_REPLAY_ONLY")
        self.assertEqual(report["source_native_gate"], "NOT_ATTEMPTED_OUT_OF_SCOPE")
        self.assertEqual(report["frozen_endpoint"]["nfev_total"], 2893419)


if __name__ == "__main__":
    unittest.main()
