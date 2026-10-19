"""Synthetic figure-format checks, not scientific observations."""
import os
from pathlib import Path
import tempfile
import unittest

from studies.knapsack_parameters.final_study import figures as f


class FigureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if os.environ.get("GITHUB_ACTIONS") != "true":
            raise RuntimeError("Figure checks run only in CI")

    def fixture(self, method):
        masks = ["00"] * 30
        return {"problem": {"n": 2}, "budget": 1, "initial_masks": masks,
                "initial_scores": [{"weight": 0, "profit": 0, "feasible": True} for _ in masks],
                "candidates": [{"call": 1, "generation": 1, "mask": "10", "profit": 2,
                                "weight": 1, "feasible": True, "selection_event": {"singleton": True}}],
                "generations": [{"complete": False, "generation": 1, "start_call": 1,
                                 "end_call": 1, "p_m": .01, "p_c": .9,
                                 "population_after": list(range(30)),
                                 "archive_after": [{"id": "00"}],
                                 "plan": {"archive": [{"id": "00"}], "gaps": [None]}}]}

    def test_prefix_record_does_not_create_a_population_measurement(self):
        records, population = f._trace(self.fixture("classical"))
        self.assertEqual(records, [(0, 0), (1, 2)])
        self.assertEqual(len(population), 1)
        self.assertEqual(population[0]["query"], 0)

    def test_streaming_format_check_three_figures_no_titles(self):
        def stream():
            for task, start in (("UC-s000", "cloned"), ("SC-s005", "bank")):
                for method in f.METHODS:
                    yield {"task": task, "start": start, "method": method, "optimum": 4,
                           "verification_status": "VERIFIED", "log": self.fixture(method)}
        with tempfile.TemporaryDirectory() as directory:
            pictures = f.render_probe(stream(), Path(directory))
            self.assertEqual(len(pictures), 3)
            self.assertTrue(all((Path(directory)/name).stat().st_size > 0 for name in pictures))

    def test_unverified_runs_do_not_generate_a_report(self):
        row = {"task": "UC-s000", "start": "cloned", "method": "classical", "optimum": 4,
               "verification_status": "UNVERIFIED", "log": self.fixture("classical")}
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(ValueError, "unverified"):
                f.render_probe(iter([row]), Path(directory))
            self.assertFalse(list(Path(directory).glob("*.png")))

    def test_retained_speed_format_keeps_both_thresholds_and_exact_equal_values(self):
        panels = []
        for parameter in ("p_m", "p_c", "population_size"):
            panels.append({"varying_parameter": parameter, "fixed_parameters": {}, "points": [
                {parameter: i / 100 if parameter != "population_size" else i + 10,
                 "targets": {str(q): {"points": [{"request": 0, "fraction": 0},
                     {"request": 5000, "fraction": i/5}]} for q in (95, 99)},
                 "paired_results": {name: {"fraction": fraction} for name, fraction in
                                     (("lower", .25), ("equal", .5), ("higher", .25))}}
                for i in range(5)]})
        report = {"schema": "basic-parameters-speed-descriptive-v1", "scope": "DEVELOPMENT_FIXED_GRID_ONLY",
                  "runs": 37500, "budget": 5000, "conditional_panels": panels}
        with tempfile.TemporaryDirectory() as directory:
            names = f._render_speed_summary(report, Path(directory))
            self.assertEqual(names, ["fixed_speed_95.png", "fixed_speed_99.png", "fixed_same_result.png"])
            self.assertTrue(all((Path(directory)/name).stat().st_size > 0 for name in names))

    def test_incomplete_retained_speed_summary_fails_before_plotting(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(ValueError, "complete development"):
                f._render_speed_summary({"schema": "wrong"}, Path(directory))
            self.assertFalse(list(Path(directory).glob("*.png")))
