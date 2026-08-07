from __future__ import annotations

import json
import math
import unittest
from pathlib import Path

from aheadverify.deleter import (
    DeleterState,
    DeleterValidationError,
    simulate_deleter,
)


CANDIDATE = Path(__file__).resolve().parents[2]
FIXTURE = CANDIDATE / "fixtures" / "deleter_transition_cases.json"


class DeleterTransitionTests(unittest.TestCase):
    def test_shared_transition_fixture(self):
        cases = json.loads(FIXTURE.read_text(encoding="utf-8"))["cases"]
        self.assertGreaterEqual(len(cases), 5)
        for case in cases:
            with self.subTest(case=case["name"]):
                state = DeleterState.from_dict(case["state"])
                event = state.advance(case["selected_operators"], case["scores"])
                self.assertEqual(
                    event["deleted_operator"], case["expected_deleted_operator"]
                )
                self.assertEqual(state.turn, case["expected_turn"])
                self.assertEqual(state.surviving, case["expected_surviving"])
                self.assertEqual(state.counts, case["expected_counts"])
                self.assertEqual(state.means, case["expected_means"])

    def test_same_seed_is_byte_stable_and_adapts(self):
        first = simulate_deleter(seed=2602001, turns=80)
        second = simulate_deleter(seed=2602001, turns=80)
        self.assertEqual(first, second)
        self.assertTrue(all(first["invariants"].values()))
        self.assertTrue(first["deletion_events"])
        self.assertEqual(first["final_state"]["turn"], 80)
        self.assertEqual(sum(first["final_state"]["counts"]), 160)

    def test_different_seed_changes_history(self):
        first = simulate_deleter(seed=1, turns=80)
        second = simulate_deleter(seed=2, turns=80)
        self.assertNotEqual(
            first["selection_history_digest"], second["selection_history_digest"]
        )

    def test_one_survivor_is_absorbing(self):
        state = DeleterState.from_dict(
            {
                "nb_operators": 2,
                "nb_selected": 1,
                "turn": 50,
                "counts": [5, 5],
                "means": [10, 1],
                "surviving": [1],
                "removed": [0],
            }
        )
        for _ in range(20):
            event = state.advance([1], [1])
            self.assertIsNone(event["deleted_operator"])
            self.assertEqual(state.surviving, [1])

    def test_invalid_inputs_fail_closed(self):
        invalid_states = [
            {"nb_operators": 0},
            {
                "nb_operators": 2,
                "nb_selected": 1,
                "turn": -1,
                "counts": [0, 0],
                "means": [0, 0],
                "surviving": [0, 1],
                "removed": [],
            },
            {
                "nb_operators": 2,
                "nb_selected": 1,
                "turn": 0,
                "counts": [0, 0],
                "means": [0, math.inf],
                "surviving": [0, 1],
                "removed": [],
            },
            {
                "nb_operators": 2,
                "nb_selected": 1,
                "turn": 0,
                "counts": [0, 0],
                "means": [1, 0],
                "surviving": [0, 1],
                "removed": [],
            },
        ]
        for value in invalid_states:
            with self.subTest(value=value), self.assertRaises(DeleterValidationError):
                DeleterState.from_dict(value)

        state = DeleterState.initialize()
        with self.assertRaises(DeleterValidationError):
            state.advance([0], [1])
        with self.assertRaises(DeleterValidationError):
            state.advance([0, 7], [1, 2])
        with self.assertRaises(DeleterValidationError):
            state.advance([0, 1], [1, math.nan])
        with self.assertRaises(DeleterValidationError):
            state.advance([0, 1], [1, -1])
        with self.assertRaises(DeleterValidationError):
            state.advance([0, 1], [1, 1.5])
        with self.assertRaises(DeleterValidationError):
            simulate_deleter(seed=-1, turns=10)


if __name__ == "__main__":
    unittest.main()
