#!/usr/bin/env python3
"""Process-worker determinism checks for EU26-18 formula probes."""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


VERIFICATION_ROOT = Path(__file__).resolve().parents[1] / "verification"
sys.path.insert(0, str(VERIFICATION_ROOT))

from reference_sa_plm import (  # noqa: E402
    canonical_probe_digests,
    evaluate_probe_case,
    run_probe_suite,
)


class WorkerDeterminismTests(unittest.TestCase):
    def test_serial_one_two_and_four_processes_are_bitwise_identical(self) -> None:
        # Invoke the guarded CLI in a fresh interpreter. This is safe under the
        # Windows spawn model and avoids recursively importing the test runner.
        runner = VERIFICATION_ROOT / "run_verification.py"
        with tempfile.TemporaryDirectory() as temporary_directory:
            report_path = Path(temporary_directory) / "machine-report.json"
            completed = subprocess.run(
                [
                    sys.executable,
                    str(runner),
                    "--workers",
                    "1",
                    "2",
                    "4",
                    "--cases",
                    "96",
                    "--output",
                    str(report_path),
                ],
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            report = json.loads(report_path.read_text(encoding="utf-8"))
        self.assertTrue(report["exact_worker_invariance"])
        self.assertEqual(
            {run["exact_digest"] for run in report["worker_runs"]},
            {"a991ade8a5b84bd0f433dbdc59c0a8383c96fdc8fc23a6dc08061544b664bf16"},
        )
        self.assertEqual(
            {run["quantized_digest"] for run in report["worker_runs"]},
            {"811f44a8851b568af13561aa95ac104cd01cab2e855558d2a47507626eb67b22"},
        )

    def test_completion_order_cannot_change_digest(self) -> None:
        results = [evaluate_probe_case(run_id, 20260810) for run_id in range(32)]
        forward = canonical_probe_digests(results)
        reverse = canonical_probe_digests(reversed(results))
        self.assertEqual(forward, reverse)

    def test_master_seed_changes_scientific_digest(self) -> None:
        first = run_probe_suite(1, 16, 20260810)
        second = run_probe_suite(1, 16, 20260811)
        self.assertNotEqual(first["exact_digest"], second["exact_digest"])
        self.assertNotEqual(first["quantized_digest"], second["quantized_digest"])


if __name__ == "__main__":
    unittest.main()
