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
    CORRECTED_SECURE_WORKFLOW,
    HYBRID_WORKFLOW,
    MUTATION_WORKFLOW,
    OLD_WORKFLOW,
    QUALITY_WORKFLOW,
    RETIRED_WORKFLOWS,
    audit,
)


AUDITED_FILES = (
    CANONICAL_MATRIX,
    AUDIT_WORKFLOW,
    MUTATION_WORKFLOW,
    OLD_WORKFLOW,
    HYBRID_WORKFLOW,
    CORRECTED_SECURE_WORKFLOW,
    QUALITY_WORKFLOW,
    "candidates/EU26-21/hybrid_1/aggregate_old_hybrid_v2.py",
)


class CiAuditTests(unittest.TestCase):
    def test_repository_ci_topology_passes_without_mutable_action_warnings(self) -> None:
        report = audit(REPO_ROOT)
        self.assertTrue(report["pass"], report)
        self.assertTrue(all(report["critical_gates"].values()))
        self.assertEqual(report["warnings"], [])

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
                report["critical_gates"][
                    "C1_MATRIX_COVERS_ALL_SCIENTIFIC_PATHS"
                ]
            )

    def test_reintroduced_retired_workflow_is_detected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self._copy_audited_files(root)
            retired_path = root / RETIRED_WORKFLOWS[0]
            retired_path.parent.mkdir(parents=True, exist_ok=True)
            retired_path.write_text(
                "name: obsolete\non:\n  workflow_dispatch:\n",
                encoding="utf-8",
            )
            report = audit(root)
            self.assertFalse(report["pass"])
            self.assertFalse(
                report["critical_gates"][
                    "C8_RETIRED_PLACEHOLDER_WORKFLOWS_REMOVED"
                ]
            )

    def test_pull_request_trigger_on_expensive_matrix_is_detected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self._copy_audited_files(root)
            matrix_path = root / CANONICAL_MATRIX
            text = matrix_path.read_text(encoding="utf-8")
            text = text.replace(
                "on:\n  workflow_dispatch:\n",
                "on:\n  workflow_dispatch:\n  pull_request:\n",
            )
            matrix_path.write_text(text, encoding="utf-8")
            report = audit(root)
            self.assertFalse(report["pass"])
            self.assertFalse(report["critical_gates"]["C0_MATRIX_IS_PUSH_ONLY"])

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

    def test_corrected_workflow_must_use_both_official_files(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self._copy_audited_files(root)
            workflow_path = root / CORRECTED_SECURE_WORKFLOW
            text = workflow_path.read_text(encoding="utf-8")
            text = text.replace("census-income.test", "removed-test-file")
            workflow_path.write_text(text, encoding="utf-8")
            report = audit(root)
            self.assertFalse(report["pass"])
            self.assertFalse(
                report["critical_gates"][
                    "C16_CORRECTED_SECURE_USES_OFFICIAL_TRAIN_AND_TEST"
                ]
            )

    def test_quality_workflow_must_preserve_all_auditors(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self._copy_audited_files(root)
            workflow_path = root / QUALITY_WORKFLOW
            text = workflow_path.read_text(encoding="utf-8")
            text = text.replace("vulture", "removed-unused-code-tool")
            workflow_path.write_text(text, encoding="utf-8")
            report = audit(root)
            self.assertFalse(report["pass"])
            self.assertFalse(
                report["critical_gates"][
                    "C20_QUALITY_WORKFLOW_RUNS_COMPLETE_AUDIT"
                ]
            )


if __name__ == "__main__":
    unittest.main()
