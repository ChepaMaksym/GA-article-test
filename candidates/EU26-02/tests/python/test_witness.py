from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from aheadverify.witness import (
    EXPECTED_PRE_COUNTS,
    EXPECTED_PRE_SUMS,
    OPERATOR_NAMES,
    WitnessValidationError,
    _parse_tbt,
    parse_dimacs_graph,
    validate_coloring,
)


def synthetic_turn_30_tbt() -> bytes:
    observations: list[tuple[int, int]] = []
    for operator, (count, total) in enumerate(
        zip(EXPECTED_PRE_COUNTS, EXPECTED_PRE_SUMS)
    ):
        observations.extend([(operator, total)] + [(operator, 0)] * (count - 1))
    if len(observations) != 60:
        raise AssertionError("frozen pre-turn counts must encode 30 selections")
    lines = [
        "#operators",
        "#" + ":".join(OPERATOR_NAMES),
        "turn,selected,fitness_post_mutation",
    ]
    for turn in range(30):
        left = observations[2 * turn]
        right = observations[2 * turn + 1]
        lines.append(f"{turn},{left[0]}:{right[0]},{left[1]}:{right[1]}")
    lines.append("30,0:5,2:2")
    return ("\n".join(lines) + "\n").encode("utf-8")


class SelectedWitnessTests(unittest.TestCase):
    def test_legal_coloring_checks_every_edge(self):
        graph = {"vertices": 3, "edges": [(0, 1), (1, 2)]}
        legal = validate_coloring([0, 1, 0], graph, 2)
        self.assertTrue(legal["legal"])
        self.assertEqual(legal["conflicts"], 0)
        self.assertEqual(legal["edge_count_checked"], 2)

        conflict = validate_coloring([0, 0, 1], graph, 2)
        self.assertFalse(conflict["legal"])
        self.assertEqual(conflict["conflicts"], 1)

    def test_coloring_shape_and_range_fail_closed(self):
        graph = {"vertices": 3, "edges": [(0, 1), (1, 2)]}
        for colors, declared in (([0, 1], 2), ([0, 1, 2], 2), ([0, -1, 0], 2)):
            with self.subTest(colors=colors, declared=declared):
                with self.assertRaises(WitnessValidationError):
                    validate_coloring(colors, graph, declared)

    def test_turn_30_archive_transition_is_recomputed(self):
        report = _parse_tbt(synthetic_turn_30_tbt())
        self.assertEqual(report["row_count"], 31)
        transition = report["turn_30"]
        self.assertEqual(transition["pre_counts"], EXPECTED_PRE_COUNTS)
        self.assertEqual(transition["pre_sums"], EXPECTED_PRE_SUMS)
        self.assertEqual(transition["post_counts"], [16, 9, 10, 10, 11, 6])
        self.assertEqual(transition["post_sums"], [33, 26, 24, 19, 28, 13])
        self.assertEqual(transition["removed_operator"], 1)

    def test_tbt_turn_gap_fails_closed(self):
        raw = synthetic_turn_30_tbt().replace(b"\n10,", b"\n11,", 1)
        with self.assertRaisesRegex(WitnessValidationError, "not contiguous"):
            _parse_tbt(raw)

    def test_unpinned_dimacs_file_is_rejected_before_parsing(self):
        with tempfile.TemporaryDirectory() as directory:
            graph = Path(directory) / "wrong.col"
            graph.write_text("p edge 2 1\ne 1 2\n", encoding="utf-8")
            with self.assertRaisesRegex(
                WitnessValidationError, "(?:byte count|SHA-256) mismatch"
            ):
                parse_dimacs_graph(graph)


if __name__ == "__main__":
    unittest.main()
