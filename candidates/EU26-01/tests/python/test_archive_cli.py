from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch


CANDIDATE = Path(__file__).resolve().parents[2]
RUNNER_PATH = CANDIDATE / "environments" / "python" / "run_archive_validation.py"
SPEC = importlib.util.spec_from_file_location("eu26_01_archive_cli", RUNNER_PATH)
assert SPEC and SPEC.loader
runner = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(runner)


class ArchiveCliTests(unittest.TestCase):
    def test_both_path_arguments_parse_and_auth_failure_leaves_no_output(self):
        with tempfile.TemporaryDirectory(dir="/tmp") as directory:
            root = Path(directory)
            archive = root / "invalid.zip"
            archive.write_bytes(b"not a ZIP archive")
            output = root / "must-not-exist.json"
            arguments = [
                str(RUNNER_PATH),
                "--archive",
                str(archive),
                "--output",
                str(output),
            ]
            with patch.object(sys, "argv", arguments):
                self.assertEqual(runner.main(), 2)
            self.assertFalse(output.exists())

    def test_repository_output_is_rejected_during_parse_without_creation(self):
        output = CANDIDATE / "must-not-create-archive-cli-regression.json"
        self.assertFalse(output.exists())
        arguments = [
            str(RUNNER_PATH),
            "--archive",
            "/tmp/does-not-matter.zip",
            "--output",
            str(output),
        ]
        with patch.object(sys, "argv", arguments), self.assertRaises(SystemExit) as raised:
            runner.main()
        self.assertEqual(raised.exception.code, 2)
        self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main()
