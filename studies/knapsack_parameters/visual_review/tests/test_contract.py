"""Run only in CI: prove figure inputs and descriptions preserve their scope."""
from copy import deepcopy
import itertools
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from studies.knapsack_parameters.visual_review.build import (
    authenticate, family_population_pairs, load_data, population_points,
    validate_compact, validate_neighbors,
)


def pair_row(name, population, event, seed=51001, mutation=1, crossover=.9):
    return {
        "instance_id": name, "population_size": population,
        "escape_event": event, "repeat_seed": seed, "start_profile": "local",
        "mutation_numerator": mutation, "crossover_probability": crossover,
        "configuration_id": f"m{mutation}-c{crossover}-n{population}",
    }


def small_certificate():
    # Explicitly retained educational example, not an experimental result.
    # The center 100 has value 10; all six N2 neighbors fail to improve it.
    case = {
        "n": 3, "capacity": 10,
        "certificate": {
            "center": {"mask": "100", "profit": 10, "weight": 6},
            "higher_feasible": 0, "equal_feasible": 0,
            "lower_feasible": 3, "invalid_count": 3,
        },
        "exact": {
            "confirmed_optimum": 16,
            "capacity": {"witness_mask": "011", "witness_profit": 16,
                         "witness_weight": 10},
        },
    }
    # Independent literal expectations: no call to the production evaluator.
    neighbors = [
        {"distance": 1, "flip_i": 0, "flip_j": None,
         "profit": 0, "weight": 0, "feasible": True},
        {"distance": 1, "flip_i": 1, "flip_j": None,
         "profit": 18, "weight": 11, "feasible": False},
        {"distance": 1, "flip_i": 2, "flip_j": None,
         "profit": 18, "weight": 11, "feasible": False},
        {"distance": 2, "flip_i": 0, "flip_j": 1,
         "profit": 8, "weight": 5, "feasible": True},
        {"distance": 2, "flip_i": 0, "flip_j": 2,
         "profit": 8, "weight": 5, "feasible": True},
        {"distance": 2, "flip_i": 1, "flip_j": 2,
         "profit": 26, "weight": 16, "feasible": False},
    ]
    return case, neighbors, [10, 8, 8], [6, 5, 5]


class PopulationPairsTests(unittest.TestCase):
    def test_task_then_family_means_not_pooled_runs(self):
        cases = {"A": {"family": "s000"}, "B": {"family": "s000"},
                 "C": {"family": "s001"}}
        rows = [pair_row("A", 10, False), pair_row("A", 50, True)]
        for seed in (51001, 51002, 51003):
            rows.extend([pair_row("B", 10, False, seed),
                         pair_row("B", 50, False, seed)])
        rows.extend([pair_row("C", 10, True), pair_row("C", 50, True)])
        pairs = family_population_pairs(rows, cases, {"s000": .5, "s001": 0})
        self.assertEqual(pairs, [
            {"family": "s000", "n10": 0, "n50": .5, "instance_count": 2},
            {"family": "s001", "n10": 1, "n50": 1, "instance_count": 1},
        ])
        # Equal family weights give .25, not a pooled .20 or task-weighted 1/3.
        self.assertEqual(sum(row["n50"] - row["n10"] for row in pairs) / 2, .25)

    def test_duplicate_identity_rejected(self):
        row = pair_row("A", 10, False)
        with self.assertRaisesRegex(ValueError, "duplicate"):
            family_population_pairs([row, deepcopy(row)], {"A": {"family": "s000"}})

    def test_unpaired_population_rejected(self):
        with self.assertRaisesRegex(ValueError, "unpaired"):
            family_population_pairs([pair_row("A", 10, False)],
                                    {"A": {"family": "s000"}})

    def test_equal_counts_but_unpaired_seeds_rejected(self):
        with self.assertRaisesRegex(ValueError, "unpaired"):
            family_population_pairs([
                pair_row("A", 10, False, 51001), pair_row("A", 50, False, 51002)
            ], {"A": {"family": "s000"}})

    def test_equal_counts_but_unpaired_operators_rejected(self):
        with self.assertRaisesRegex(ValueError, "unpaired"):
            family_population_pairs([
                pair_row("A", 10, False, mutation=1),
                pair_row("A", 50, False, mutation=3),
            ], {"A": {"family": "s000"}})

    def test_independent_historical_contrast_mismatch_rejected(self):
        rows = [pair_row("A", 10, False), pair_row("A", 50, True)]
        with self.assertRaisesRegex(ValueError, "contrast differs"):
            family_population_pairs(rows, {"A": {"family": "s000"}}, {"s000": .5})

    def test_missing_historical_family_rejected(self):
        rows = [pair_row("A", 10, False), pair_row("A", 50, True)]
        with self.assertRaisesRegex(ValueError, "missing family"):
            family_population_pairs(rows, {"A": {"family": "s000"}},
                                    {"s000": 1, "s001": 0})

    def test_numeric_escape_flag_is_not_accepted_as_boolean(self):
        rows = [pair_row("A", 10, False), pair_row("A", 50, True)]
        rows[0]["escape_event"] = 0
        with self.assertRaisesRegex(ValueError, "escape event"):
            family_population_pairs(rows, {"A": {"family": "s000"}})


class NeighborhoodTests(unittest.TestCase):
    def test_literal_six_neighbors_certify_nonglobal_center(self):
        case, neighbors, values, weights = small_certificate()
        self.assertEqual(validate_neighbors(case, neighbors, values, weights), {
            "higher_feasible": 0, "equal_feasible": 0, "lower_feasible": 3,
            "invalid_count": 3, "neighbors": 6, "witness_distance": 3,
        })

    def test_missing_neighbor_rejected(self):
        case, neighbors, values, weights = small_certificate()
        with self.assertRaisesRegex(ValueError, "incomplete"):
            validate_neighbors(case, neighbors[:-1], values, weights)

    def test_duplicate_neighbor_rejected(self):
        case, neighbors, values, weights = small_certificate()
        with self.assertRaisesRegex(ValueError, "repeated"):
            validate_neighbors(case, neighbors + [deepcopy(neighbors[0])], values, weights)

    def test_out_of_range_or_repeated_flip_rejected(self):
        for replacement in ((3, None, 1), (1, 1, 2)):
            with self.subTest(replacement=replacement):
                case, neighbors, values, weights = small_certificate()
                neighbors[0].update(zip(("flip_i", "flip_j", "distance"), replacement))
                with self.assertRaisesRegex(ValueError, "neighbor"):
                    validate_neighbors(case, neighbors, values, weights)

    def test_corrupt_weight_profit_or_feasibility_rejected(self):
        for key, replacement in (("weight", 1), ("profit", 1), ("feasible", False)):
            with self.subTest(key=key):
                case, neighbors, values, weights = small_certificate()
                neighbors[0][key] = replacement
                with self.assertRaisesRegex(ValueError, "corrupt neighbor"):
                    validate_neighbors(case, neighbors, values, weights)

    def test_corrupt_center_or_count_rejected(self):
        case, neighbors, values, weights = small_certificate()
        case["certificate"]["center"]["weight"] = 7
        with self.assertRaisesRegex(ValueError, "center"):
            validate_neighbors(case, neighbors, values, weights)
        case, neighbors, values, weights = small_certificate()
        case["certificate"]["lower_feasible"] = 4
        with self.assertRaisesRegex(ValueError, "counts differ"):
            validate_neighbors(case, neighbors, values, weights)

    def test_wrong_bit_order_and_witness_rejected(self):
        case, neighbors, values, weights = small_certificate()
        with self.assertRaises(ValueError):
            validate_neighbors(case, neighbors, list(reversed(values)), weights)
        case["exact"]["capacity"]["witness_mask"] = "111"
        with self.assertRaisesRegex(ValueError, "optimum witness"):
            validate_neighbors(case, neighbors, values, weights)


class CompactSourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        names = [f"{kind}-s{index:03d}" for kind in ("UC", "WC", "SC")
                 for index in range(10)]
        cls.cases = {name: {"status": "ADMITTED_NONGLOBAL" if index < 14 else "GLOBAL_CENTER"}
                     for index, name in enumerate(names)}
        cls.rows = []
        for profile, source in (("random", names), ("local", names[:14])):
            for name, seed, mutation, crossover, population in itertools.product(
                    source, range(51001, 51031), (.5, 1, 3), (0, .5, .9), (10, 30, 50)):
                cls.rows.append({
                    "instance_id": name, "start_profile": profile, "repeat_seed": seed,
                    "mutation_numerator": mutation, "crossover_probability": crossover,
                    "population_size": population, "logical_requests": 5000,
                    "escape_event": False,
                })

    def test_entire_35640_source_rectangle(self):
        self.assertEqual(len(self.rows), 35640)
        validate_compact(self.rows, self.cases)

    def test_missing_or_duplicate_row_rejected(self):
        for rows in (self.rows[:-1], self.rows + [self.rows[0]]):
            with self.subTest(length=len(rows)), self.assertRaises(ValueError):
                validate_compact(rows, self.cases)

    def test_changed_seed_parameter_count_or_boolean_rejected(self):
        for key, replacement in (("repeat_seed", 52001), ("population_size", 20),
                                 ("logical_requests", 4999), ("escape_event", 1)):
            with self.subTest(key=key):
                row = {**self.rows[0], key: replacement}
                with self.assertRaises(ValueError):
                    validate_compact([row] + self.rows[1:], self.cases)


class ExecutionAndTrajectoryTests(unittest.TestCase):
    def test_authentication_rejects_local_execution_before_any_subprocess(self):
        with patch.dict(os.environ, {}, clear=True), patch(
                "studies.knapsack_parameters.visual_review.build.subprocess.check_output") as command:
            with self.assertRaisesRegex(ValueError, "CI-only"):
                authenticate("0" * 40)
            command.assert_not_called()

    def test_authentication_rejects_wrong_ci_branch(self):
        with patch.dict(os.environ, {
                "GITHUB_ACTIONS": "true", "GITHUB_REPOSITORY": "ChepaMaksym/GA-article-test",
                "GITHUB_REF": "refs/heads/main"}, clear=True):
            with self.assertRaisesRegex(ValueError, "repository or branch"):
                authenticate("0" * 40)

    def test_population_points_omit_terminal_partial_but_keep_initial(self):
        initial = {"generation": 0, "complete": False, "last_request": 30}
        full = {"generation": 1, "complete": True, "last_request": 59}
        partial = {"generation": 2, "complete": False, "last_request": 70}
        self.assertEqual(population_points([initial, full, partial]), [initial, full])
        self.assertEqual([row["last_request"] for row in (initial, full, partial)], [30, 59, 70])

    @unittest.skipUnless(os.environ.get("GITHUB_ACTIONS") == "true", "render only in CI")
    def test_frozen_sources_render_seven_question_answer_exports(self):
        from matplotlib.colors import to_rgba
        from matplotlib.text import Text
        from studies.knapsack_parameters.visual_review import figures
        self.assertEqual(figures.WIDTH_INCHES, 6.8)
        self.assertGreaterEqual(figures.MIN_FONT_POINTS, 11)
        data = load_data()
        self.assertEqual(data["checks"]["neighbors"], 5050)
        self.assertEqual(data["checks"]["witness_distance"], 3)
        original_save = figures._save
        inspected = []

        def inspect_and_save(plt, figure, *args):
            self.assertAlmostEqual(figure.get_size_inches()[0], 6.8)
            self.assertLessEqual(len(figure.axes), 3)
            self.assertEqual(to_rgba(figure.get_facecolor()), (1, 1, 1, 1))
            for text in figure.findobj(match=Text):
                if text.get_visible() and text.get_text():
                    self.assertGreaterEqual(text.get_fontsize(), 11)
            for axis in figure.axes:
                for line in axis.lines:
                    red, green, blue, _ = to_rgba(line.get_color())
                    self.assertAlmostEqual(red, green)
                    self.assertAlmostEqual(green, blue)
            inspected.append(figure)
            return original_save(plt, figure, *args)

        with tempfile.TemporaryDirectory(prefix="knapsack-question-figures-") as directory:
            root = Path(directory)
            with patch.object(figures, "_save", side_effect=inspect_and_save):
                passports = figures.render(data, root)
            self.assertEqual(len(passports), 7)
            self.assertEqual(len(inspected), 7)
            names = set()
            for passport in passports:
                for key in ("question", "answer", "limitation"):
                    self.assertTrue(isinstance(passport[key], str) and passport[key].strip())
                for key, extension in (("png", ".png"), ("pdf", ".pdf")):
                    relative = passport[key]
                    self.assertNotIn(relative, names)
                    names.add(relative)
                    path = root / relative
                    self.assertEqual(path.suffix, extension)
                    self.assertTrue(path.is_file())
                    self.assertGreater(path.stat().st_size, 1000)
            self.assertEqual(len(names), 14)


if __name__ == "__main__":
    unittest.main()
