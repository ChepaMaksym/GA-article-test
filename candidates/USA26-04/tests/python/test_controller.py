from __future__ import annotations

import copy
import json
import math
from pathlib import Path
import sys
import unittest


CANDIDATE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(CANDIDATE / "environments" / "python"))

from banditverify.controller import (  # noqa: E402
    FIXTURE_STATE_PROVENANCE,
    nesterov_update,
    paper_tile_index,
    run_fixed_controller_tape,
    standard_deviation_witness,
    tile_boundary_witness,
    tie_ambiguity_witness,
)


class ControllerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.oracles = json.loads(
            (CANDIDATE / "fixtures" / "formula_oracles.json").read_text()
        )
        cls.fixture = json.loads(
            (CANDIDATE / "fixtures" / "fixed_controller_tape.json").read_text()
        )

    def test_nesterov_micro_oracle_and_opposite_reward(self) -> None:
        oracle = self.oracles["nesterov"]
        actual = nesterov_update(
            oracle["value"],
            oracle["momentum"],
            oracle["reward"],
            oracle["learning_rate"],
            oracle["momentum_factor"],
        )
        self.assertEqual(actual["gradient"], oracle["expected_gradient"])
        self.assertEqual(actual["momentum"], oracle["expected_momentum"])
        self.assertAlmostEqual(actual["value"], oracle["expected_value"], delta=1e-16)
        opposite = nesterov_update(0.0, 0.0, -1.0, 0.001, 0.9)
        self.assertAlmostEqual(opposite["value"], -0.0038, delta=1e-16)

    def test_tile_index_uses_paper_one_based_formula(self) -> None:
        self.assertEqual(paper_tile_index(-1.0, -1.0, 0.0, 0.5), 1)
        self.assertEqual(paper_tile_index(-0.5, -1.0, 0.0, 0.5), 2)
        self.assertEqual(paper_tile_index(-0.375, -1.0, 0.0, 0.5), 2)

    def test_upper_boundary_conflict_is_not_resolved(self) -> None:
        witness = tile_boundary_witness()
        self.assertEqual(witness["status"], "AMBIGUITY_CONFIRMED")
        self.assertFalse(witness["resolution_chosen"])
        self.assertEqual(witness["floor_tile_count"], 6666)
        self.assertEqual(witness["last_clamped_tile"], 6665)
        self.assertAlmostEqual(witness["uncovered_width_if_clamped"], 0.02)
        self.assertAlmostEqual(witness["overshoot_width_if_next_tile"], 0.01)

    def test_equal_weight_tie_is_not_resolved(self) -> None:
        oracle = self.oracles["tie"]
        witness = tie_ambiguity_witness(oracle["weights"], oracle["epsilon"])
        self.assertEqual(witness["status"], "AMBIGUITY_CONFIRMED")
        self.assertFalse(witness["resolution_chosen"])
        self.assertIsNone(witness["selected_tile"])
        self.assertEqual(witness["maximizer_tiles"], [0, 1, 2, 3])

    def test_standard_deviation_conflict(self) -> None:
        witness = standard_deviation_witness()
        self.assertEqual(witness["status"], "AMBIGUITY_CONFIRMED")
        self.assertTrue(witness["all_distinct_at_1e-3"])
        self.assertAlmostEqual(
            witness["actual_sd_log_two_to_uniform"], math.log(2) / math.sqrt(3)
        )

    def test_fixed_tape_transition_and_provenance(self) -> None:
        actual = run_fixed_controller_tape(self.fixture)
        expected = self.fixture["expected"]
        self.assertEqual(actual["state_provenance"], FIXTURE_STATE_PROVENANCE)
        self.assertEqual(actual["paper_level_status"], "BLOCKED_G5_G9")
        self.assertEqual(
            actual["published_result_status"], "INCONCLUSIVE_PUBLISHED_RESULT"
        )
        self.assertEqual(actual["branch"], expected["branch"])
        self.assertEqual(actual["argmax_tile"], expected["argmax_tile"])
        self.assertEqual(actual["selected_tile"], expected["selected_tile"])
        for key in ("log_rate", "rate", "immediate_reward"):
            self.assertAlmostEqual(actual[key], expected[key], delta=1e-15)
        for left, right in zip(actual["base_weights"], expected["base_weights"]):
            self.assertAlmostEqual(left, right, delta=1e-15)
        for result, oracle in zip(actual["updates"], expected["updates"]):
            self.assertEqual(result["paper_index"], oracle["paper_index"])
            self.assertEqual(result["history"], oracle["history"])
            for key in ("max_reward", "gradient", "momentum", "value"):
                self.assertAlmostEqual(result[key], oracle[key], delta=1e-15)

    def test_history_window_retains_only_last_entries(self) -> None:
        fixture = copy.deepcopy(self.fixture)
        fixture["codings"][0]["histories_by_paper_index"][1] = [-9, -8, -7]
        actual = run_fixed_controller_tape(fixture)
        self.assertEqual(actual["updates"][0]["history"], [-8.0, -7.0, 6.0])

    def test_missing_provenance_and_source_ambiguous_tie_fail(self) -> None:
        missing = copy.deepcopy(self.fixture)
        missing["description"] = "ordinary fixture"
        with self.assertRaisesRegex(ValueError, "not article state"):
            run_fixed_controller_tape(missing)
        tied = copy.deepcopy(self.fixture)
        tied["codings"][0]["values_by_paper_index"] = [None, 0.0, 0.0]
        tied["codings"][1]["values_by_paper_index"] = [None, 0.0, 0.0, 0.0, 0.0]
        with self.assertRaisesRegex(ValueError, "tie is source-ambiguous"):
            run_fixed_controller_tape(tied)

    def test_invalid_update_and_tile_inputs_fail_closed(self) -> None:
        with self.assertRaises(ValueError):
            paper_tile_index(0, -1, 0, 0)
        with self.assertRaises(ValueError):
            nesterov_update(0, 0, 1, 0, 0.9)
        with self.assertRaises(ValueError):
            nesterov_update(0, 0, 1, 0.001, 1.0)


if __name__ == "__main__":
    unittest.main()
