"""CI-only rendering smoke test with synthetic, non-scientific fixtures.

The fixture has the registered identity grid but contains no measured result.
Its temporary report is deleted after the test and is not research evidence.
"""
import hashlib
import json
import os
from pathlib import Path
import re
from tempfile import TemporaryDirectory
import unittest

from ...stagnation_mechanisms import analysis
from ...stagnation_mechanisms.tests.test_analysis import feature_row


class RenderingSmokeTests(unittest.TestCase):
    def test_registered_report_and_three_figures_render_on_complete_fixture(self):
        self.assertEqual(os.environ.get("GITHUB_ACTIONS"), "true", "Rendering checks are CI-only")
        scientific_directory = Path(analysis.__file__).resolve().parent
        source_paths = [scientific_directory / name for name in
                        ("analysis.py", "mathematics.py", "operators.py", "execution.py")]
        before = {path: hashlib.sha256(path.read_bytes()).hexdigest() for path in source_paths}
        rows = []
        for ordinal, (instance, seed) in enumerate(sorted(analysis.expected_identities())):
            # Retain eight zero-improvement stagnant fixtures and all 690
            # non-stagnant fixtures; include the fixed UC-s000/93001 example.
            better = 1 if ordinal < 202 else 0 if ordinal < 210 else 2
            rows.append(feature_row(instance, seed, b2=better, stagnant=ordinal < 210))
        summary = analysis.summarize_features(rows)
        self.assertEqual(summary["status"], "COMPLETE_EXPLORATORY")
        self.assertEqual(summary["counts"], {
            "runs": 900, "stagnant": 210, "stagnant_with_improvement": 202})
        self.assertEqual((summary["fixed_example"]["instance_id"], summary["fixed_example"]["repeat_seed"]),
                         ("UC-s000", 93001))
        with TemporaryDirectory(prefix="synthetic-secondary-render-smoke-") as temporary:
            output = Path(temporary).resolve()
            self.assertFalse(output.is_relative_to(analysis.ROOT))
            receipt = analysis.write_report(output, rows, summary)
            self.assertEqual(set(receipt["figures"]), {
                "availability.png", "operator_events.png", "sampling_detection.png"})
            self.assertEqual(len(receipt["figures"]), 3)
            for name in receipt["figures"]:
                content = (output / name).read_bytes()
                self.assertTrue(content.startswith(b"\x89PNG\r\n\x1a\n"), name)
                self.assertGreater(len(content), 1000, name)
            report = (output / receipt["report"]).read_text(encoding="utf-8")
            self.assertEqual(re.findall(r"^Таблиця ([1-6])\.", report, flags=re.MULTILINE),
                             ["1", "2", "3", "4", "5", "6"])
            self.assertEqual(re.findall(r"^Рисунок ([1-3])\.", report, flags=re.MULTILINE), ["1", "2", "3"])
            self.assertIn("UC-s000", report)
            self.assertIn("93001", report)
            self.assertNotIn("\u2014", report)
            saved = json.loads((output / "summary.json").read_text(encoding="utf-8"))
            self.assertEqual(saved["counts"], summary["counts"])
            self.assertEqual(saved["new_search_evaluations"], 0)
            self.assertEqual(saved["new_exact_solves"], 0)
            self.assertTrue(all((output / name).is_file() for name in receipt["tables"].values()))
        self.assertEqual({path: hashlib.sha256(path.read_bytes()).hexdigest() for path in source_paths}, before)


if __name__ == "__main__":
    unittest.main()
