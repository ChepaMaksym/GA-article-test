#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import shutil
import tempfile
import unittest

REPO_ROOT = Path(__file__).resolve().parents[3]

import sys
sys.path.insert(0, str(REPO_ROOT / "candidates" / "EU26-21"))

from hybrid_1.ci_audit import (  # noqa: E402
    AUDIT_WORKFLOW,
    CANONICAL_MATRIX,
    HYBRID_WORKFLOW,
    OLD_WORKFLOW,
    RETIRED_WORKFLOWS,
    audit,
)


AUDITED_FILES = (
    CANONICAL_MATRIX,
    AUDIT_WORKFLOW,
    OLD_WORKFLOW,
    HYBRID_WORKFLOW,
    *RETIRED_WORKFLOWS,
    "candidates/EU26-21/hybrid_1/aggregate_old_hybrid_v2.py",
)


class CiAuditTests(unittest.TestCase):
    def test_repository_ci_topology_passes(self) -> None:
        report = audit(REPO_ROOT)
        self.assertTrue(report["pass"], report)
        self.assertTrue(all(report["critical_gates"].values()))

    def _copy_audited_files(self, destination: Path) -> None:
        for relative in AUDITED_FILES:
            source = REPO_ROOT / relative
            target = destination / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)

    def test_missing_scientific_path_is_detected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self._copy_audited_files(root)
            matrix_path = root / CANONICAL_MATRIX
            text = matrix_path.read_text(encoding="utf-8")
            text = text.replace(
                "      - 'candidates/EU26-21/hybrid_1/core.py'\n",
                "",
            )
            matrix_path.write_text(text, encoding="utf-8")
            report = audit(root)
            self.assertFalse(report["pass"])
            self.assertFalse(
                report["critical_gates"]["C1_MATRIX_COVERS_ALL_SCIENTIFIC_PATHS"]
            )

    def test_automatic_trigger_on_retired_workflow_is_detected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self._copy_audited_files(root)
            retired_path = root / RETIRED_WORKFLOWS[0]
            text = retired_path.read_text(encoding="utf-8")
            text = text.replace(
                "on:\n  workflow_dispatch:\n",
                "on:\n  workflow_dispatch:\n  pull_request:\n",
            )
            retired_path.write_text(text, encoding="utf-8")
            report = audit(root)
            gate = f"C8_MANUAL_ONLY_{retired_path.stem}"
            self.assertFalse(report["pass"])
            self.assertFalse(report["critical_gates"][gate])

    def test_mutable_action_ref_is_detected_in_canonical_matrix(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self._copy_audited_files(root)
            matrix_path = root / CANONICAL_MATRIX
            text = matrix_path.read_text(encoding="utf-8")
            text = text.replace(
                "actions/checkout@11d5960a326750d5838078e36cf38b85af677262",
                "actions/checkout@v4",
                1,
            )
            matrix_path.write_text(text, encoding="utf-8")
            report = audit(root)
            self.assertFalse(report["pass"])
            self.assertFalse(report["critical_gates"]["C4_MATRIX_ACTIONS_PINNED"])


if __name__ == "__main__":
    unittest.main()
