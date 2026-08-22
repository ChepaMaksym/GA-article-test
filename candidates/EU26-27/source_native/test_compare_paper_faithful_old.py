from __future__ import annotations

import unittest

import compare_paper_faithful_old as candidate
import compare_source_native_old as old


class PaperFaithfulOldTests(unittest.TestCase):
    def make_complete_runs(self):
        runs = []
        for run in range(old.RUNS):
            events = []
            for point in range(old.DIMENSION + 1):
                events.append((run * 1000 + point + 1, point, old.DIMENSION - point))
            runs.append(events)
        return runs

    def test_complete_runs_are_recognized(self):
        matrix, endpoints, incomplete = candidate.extract_first_hits(self.make_complete_runs())
        self.assertEqual(incomplete, [])
        self.assertEqual(len(endpoints), old.RUNS)
        self.assertTrue(all(value is not None for value in endpoints))
        self.assertEqual(matrix[0][0], 1)
        self.assertEqual(matrix[old.DIMENSION][0], old.DIMENSION + 1)

    def test_missing_pareto_point_is_fail_closed(self):
        runs = self.make_complete_runs()
        runs[7] = runs[7][:-1]
        matrix, endpoints, incomplete = candidate.extract_first_hits(runs)
        self.assertEqual(incomplete, [7])
        self.assertIsNone(endpoints[7])
        self.assertEqual(matrix[old.DIMENSION][7], -1)

    def test_matrix_diff_detects_one_value_change(self):
        source, _, _ = candidate.extract_first_hits(self.make_complete_runs())
        reference = [row[:] for row in source]
        reference[12][4] += 1
        diff = candidate.matrix_diff(source, reference)
        self.assertEqual(diff["mismatch_count"], 1)
        self.assertEqual(diff["missing_count"], 0)

    def test_matrix_diff_detects_missing_cell(self):
        source, _, _ = candidate.extract_first_hits(self.make_complete_runs())
        reference = [row[:] for row in source]
        source[15][9] = -1
        diff = candidate.matrix_diff(source, reference)
        self.assertEqual(diff["mismatch_count"], 1)
        self.assertEqual(diff["missing_count"], 1)


if __name__ == "__main__":
    unittest.main()
