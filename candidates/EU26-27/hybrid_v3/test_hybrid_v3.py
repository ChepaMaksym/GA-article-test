from __future__ import annotations

import csv
import tempfile
import unittest
from pathlib import Path

import analyze_holdout as holdout
import patch_upstream as patcher
import select_cap as selector


class HybridV3ModuleTests(unittest.TestCase):
    def _write_complete_dat(self, root: Path, endpoint_offset: int = 0, missing: int | None = None) -> None:
        root.mkdir(parents=True, exist_ok=True)
        lines = ["evaluations f1 f2"]
        evaluation = 1 + endpoint_offset
        for i in range(holdout.DIMENSION + 1):
            if i == missing:
                continue
            lines.append(f"{evaluation} {i} {holdout.DIMENSION - i}")
            evaluation += 1
        (root / "run.dat").write_text("\n".join(lines) + "\n")

    def test_cap_grid_is_single_frozen_definition(self) -> None:
        self.assertEqual(selector.CAPS, patcher.CAPS)
        self.assertEqual(selector.CAPS, (15, 20, 30, 40, 60, 100))

    def test_selection_uses_real_selector_and_tie_break(self) -> None:
        scores = {15: 0.01, 20: 0.03, 30: 0.02, 40: -0.01, 60: 0.0, 100: 0.01}
        self.assertEqual(selector.choose_cap(scores), 20)
        tied = {cap: 0.0 for cap in selector.CAPS}
        tied[20] = tied[30] = 0.05
        self.assertEqual(selector.choose_cap(tied), 20)

    def test_paired_statistic_comes_from_real_selector(self) -> None:
        self.assertEqual(selector.paired_median_reduction([100, 100, 100], [50, 100, 200]), 0.0)

    def test_real_endpoint_parser_accepts_complete_front(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write_complete_dat(root, endpoint_offset=10)
            self.assertEqual(holdout.parse_single_endpoint(root), 111)
            self.assertEqual(selector.parse_single_endpoint(root), 111)

    def test_real_endpoint_parser_fails_closed_on_incomplete_front(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write_complete_dat(root, missing=50)
            with self.assertRaises(RuntimeError):
                holdout.parse_single_endpoint(root)
            with self.assertRaises(RuntimeError):
                selector.parse_single_endpoint(root)

    def test_real_endpoint_parser_rejects_multiple_runs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "run.dat"
            path.write_text("evaluations f1 f2\n1 0 100\nevaluations f1 f2\n2 1 99\n")
            with self.assertRaises(RuntimeError):
                holdout.parse_single_endpoint(Path(tmp))

    def test_holdout_reader_accepts_only_frozen_ledger(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "seeds.csv"
            with path.open("w", newline="") as stream:
                writer = csv.DictWriter(stream, fieldnames=["run", "seed"])
                writer.writeheader()
                for run, seed in enumerate(range(29001, 29031), start=1):
                    writer.writerow({"run": run, "seed": seed})
            self.assertEqual(holdout.read_holdout(path), list(range(29001, 29031)))

            rows = path.read_text().splitlines()
            rows[-1] = "30,28001"
            path.write_text("\n".join(rows) + "\n")
            with self.assertRaises(RuntimeError):
                holdout.read_holdout(path)

    def test_bootstrap_is_deterministic_in_real_analyzer(self) -> None:
        values = [0.1, 0.2, 0.3, 0.4, 0.5]
        self.assertEqual(holdout.bootstrap_median_ci(values), holdout.bootstrap_median_ci(values))

    def test_patch_is_fail_closed_on_wrong_upstream_preimage(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "gsemo.hpp"
            path.write_text("not the frozen upstream source")
            with self.assertRaises(RuntimeError):
                patcher.patch_gsemo(path)


if __name__ == "__main__":
    unittest.main()
