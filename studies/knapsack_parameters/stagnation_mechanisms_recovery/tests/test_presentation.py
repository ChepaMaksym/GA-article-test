import unittest

from ..presentation import annotation_series


class PresentationTests(unittest.TestCase):
    def test_labels_away_from_other_curve_and_data_coordinates_unchanged(self):
        summary = {"availability": {name: {"detection": [
            {"sample_size": sample, "value": probability} for sample, probability in zip(
                [50, 100, 250], values)]} for name, values in (
                ("all_stagnant", [.209, .3519, .5949]),
                ("stagnant_with_improvement", [.2173, .3658, .6185]))}}
        rows = annotation_series(summary)
        self.assertLess(rows[0]["offset"], 0)
        self.assertGreater(rows[1]["offset"], 0)
        for row in rows:
            source = summary["availability"][row["subset"]]["detection"]
            self.assertEqual(row["x"], [item["sample_size"] for item in source])
            self.assertEqual(row["y"], [100 * item["value"] for item in source])
