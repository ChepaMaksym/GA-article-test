from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from support import CANDIDATE, upstream


class VerificationCliTests(unittest.TestCase):
    def test_cli_emits_formula_only_report(self) -> None:
        script = CANDIDATE / "environments" / "python" / "run_verification.py"
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "report.json"
            process = subprocess.run(
                [sys.executable, str(script), "--checkout", str(upstream()), "--output", str(output)],
                check=False,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
            )
            self.assertEqual(process.returncode, 0, process.stderr)
            report = json.loads(output.read_text(encoding="ascii"))
            self.assertEqual(report["status"], "PASS_FORMULA_AND_SOURCE_TRANSITION_ONLY")
            self.assertEqual(report["readiness"], "CONDITIONAL_NONELIGIBLE")
            self.assertEqual(report["table_7_gate"]["status"], "BLOCKED_AS_PREREGISTERED")
            self.assertFalse(report["empirical_claim_made"])
            self.assertIn("PASS_FULL", report["forbidden_claims"])

    def test_cli_refuses_to_overwrite_report(self) -> None:
        script = CANDIDATE / "environments" / "python" / "run_verification.py"
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "report.json"
            output.write_text("sentinel", encoding="ascii")
            process = subprocess.run(
                [sys.executable, str(script), "--checkout", str(upstream()), "--output", str(output)],
                check=False,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            self.assertNotEqual(process.returncode, 0)
            self.assertEqual(output.read_text(encoding="ascii"), "sentinel")


if __name__ == "__main__":
    unittest.main()
