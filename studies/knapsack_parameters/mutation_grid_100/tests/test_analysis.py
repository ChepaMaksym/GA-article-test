"""Synthetic tests only; run through the registered CI technical workflow."""
from copy import deepcopy
from fractions import Fraction
import unittest

from studies.knapsack_parameters.mutation_grid_100 import analysis as a


def make_row(config=(15, 100, 100), family="s050", kind="UC", seed=150001,
             hit=1000, best=990):
    mu, pc, bp = config
    events = [[1, 0]]
    if hit is not None:
        events.append([hit, 930])
        if best > 930:
            events.append([100000, best])
    else:
        events.append([100000, best])
    row = {"task": f"n00100-{kind}-{family}", "family": family, "class_label": kind,
           "seed": seed, "task_index": 3 + (int(family[1:]) - 50) * 3 + a.TYPES.index(kind),
           "mu": mu, "pc_percentage": pc, "mutation_basis_points": bp, "optimum": 1000,
           "best": best, "events": events, "duplicates": 0,
           "completed_generations": (a.TOTAL - mu) // (mu - 1),
           "bank_sha256": "a" * 64, "certificate_sha256": "b" * 64,
           "artifact_prefix": f"n00100-{kind}-{family}/seed-{seed}/mu{mu}-pc{pc}-pm{bp}bp",
           "artifact_hashes": {name: "c" * 64 for name in a.RAW_FILES},
           "timing": {"search_seconds": 1, "log_write_seconds": 1, "verification_seconds": 1,
                      "observations_seconds": 1, "case_seconds": 4, "artifact_bytes": 1}}
    row["targets"] = {}
    for target in a.TARGETS:
        first = a.threshold(row, target)
        row["targets"][str(target)] = {"attained": first is not None, "first_total_evaluation": first,
                                       "restricted_evaluations": first if first is not None else a.TOTAL}
    row["checkpoints"] = [{"q": q, "record_profit": next(v for t, v in reversed(events) if t <= q),
                            "completed_generations": (q - mu) // (mu - 1),
                            "population_metrics": {"population_size": mu, "unique_fraction": 1,
                                                   "feasible_fraction": 1, "mean_pairwise_hamming": 10}}
                           for q in a.CHECKPOINTS]
    return row


def make_union():
    return [make_row(config, family, kind, seed)
            for config in a.CONFIGS for family in a.TUNING_FAMILIES
            for kind in a.TYPES for seed in a.TUNING_SEEDS]


class AnalysisTests(unittest.TestCase):
    def test_inventory_is_31_configurations_and_2790_rows(self):
        self.assertEqual(len(a.CONFIGS), 31)
        self.assertEqual(len(a.MUTATION_CONFIGS), 18)
        rows = make_union()
        self.assertEqual(len(a.validate_union(rows)), 2790)

    def test_missing_and_duplicate_fail_closed(self):
        rows = make_union()
        with self.assertRaises(ValueError):
            a.validate_union(rows[:-1])
        with self.assertRaises(ValueError):
            a.validate_union(rows[:-1] + [rows[0]])

    def test_initial_last_equal_and_nonattainment(self):
        for hit in (2, 100000):
            row = make_row(hit=hit, best=930)
            a.validate_row(row)
            self.assertEqual(row["targets"]["93"]["first_total_evaluation"], hit)
            self.assertTrue(row["targets"]["93"]["attained"])
            self.assertFalse(row["targets"]["95"]["attained"])
        row = make_row(hit=None, best=929)
        a.validate_row(row)
        self.assertIsNone(row["targets"]["93"]["first_total_evaluation"])
        self.assertEqual(row["targets"]["93"]["restricted_evaluations"], 100000)

    def test_corrupted_target_history_generation_and_bank_fail(self):
        row = make_row()
        changed = deepcopy(row)
        changed["targets"]["93"]["first_total_evaluation"] += 1
        with self.assertRaises(ValueError):
            a.validate_row(changed)
        changed = deepcopy(row)
        changed["events"].append([100000, 995])
        with self.assertRaises(ValueError):
            a.validate_row(changed)
        changed = deepcopy(row)
        changed["checkpoints"][0]["completed_generations"] += 1
        with self.assertRaises(ValueError):
            a.validate_row(changed)
        rows = make_union()
        rows[0]["bank_sha256"] = "d" * 64
        with self.assertRaises(ValueError):
            a.validate_union(rows)

    def test_nested_targets_are_derived_from_exact_record_events(self):
        row = make_row(hit=2, best=990)
        a.validate_row(row)
        hits = [row["targets"][str(t)]["first_total_evaluation"] for t in a.TARGETS]
        self.assertEqual(hits, [2, 100000, 100000])
        self.assertLessEqual(hits[0], hits[1])
        self.assertLessEqual(hits[1], hits[2])

    def test_exact_family_means_and_two_objectives(self):
        rows = make_union()
        quality_config, speed_config = (15, 100, 75), (10, 100, 50)
        for index, row in enumerate(rows):
            config = a.configuration(row)
            rows[index] = make_row(config, row["family"], row["class_label"], row["seed"],
                                   hit=100 if config == speed_config else 1000,
                                   best=1000 if config == quality_config else 990)
        metrics = a.summarize(rows)
        selected = a.choose_recommendations(metrics)
        self.assertEqual(selected, {"quality": quality_config, "speed": speed_config})
        self.assertEqual(metrics[quality_config]["mean_gap_100000_percent"], Fraction(0))
        self.assertEqual(metrics[speed_config]["mean_restricted_t93"], Fraction(100))

    def test_ties_use_registered_parameter_preferences(self):
        metrics = a.summarize(make_union())
        selected = a.choose_recommendations(metrics)
        self.assertEqual(selected, {"quality": (10, 90, 100), "speed": (10, 90, 100)})

    def test_retained_normalization_requires_historical_configuration(self):
        row = make_row()
        del row["mutation_basis_points"]
        self.assertEqual(a.normalize_retained(row)["mutation_basis_points"], 100)
        row["mutation_basis_points"] = 25
        with self.assertRaises(ValueError):
            a.normalize_retained(row)


if __name__ == "__main__":
    unittest.main()
