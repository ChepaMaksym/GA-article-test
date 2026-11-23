"""CI regression checks for independent paired analysis, frozen roles and exports."""

import unittest
from copy import deepcopy
from fractions import Fraction

from . import analysis as a
from . import report


def make_case(config, family_index, kind, seed, *, best=999, first=1000):
    mu, pc, bp = config
    family = a.FAMILIES[family_index]
    task = f"n00100-{kind}-{family}"
    events = [[1, 0]]
    if first is not None and first != a.TOTAL:
        events.append([first, 930])
    events.append([a.TOTAL, best])
    row = {"task": task, "seed": seed, "family": family, "class_label": kind,
           "task_index": 33 + family_index * 3 + a.historic.TYPES.index(kind),
           "mu": mu, "pc_percentage": pc, "mutation_basis_points": bp,
           "schema": "independent-validation100-case-v1", "status": "VERIFIED",
           "case_id": f"{task}-seed-{seed}-mu{mu}-pc{pc}-pm{bp}bp",
           "bank_sha256": "a" * 64, "certificate_sha256": "b" * 64,
           "artifact_prefix": f"{task}/seed-{seed}/mu{mu}-pc{pc}-pm{bp}bp",
           "artifact_hashes": {key: "a" * 64 for key in a.historic.RAW_FILES},
           "optimum": 1000, "best": best, "events": events,
           "completed_generations": (a.TOTAL-mu)//(mu-1), "duplicates": 0,
           "timing": {"search_seconds": 0.1, "log_write_seconds": 0, "verification_seconds": 0,
                      "observations_seconds": 0, "case_seconds": 0.12, "artifact_bytes": 100}}
    row["checkpoints"] = [{"q": q, "record_profit": next(v for t, v in reversed(events) if t <= q),
        "completed_generations": (q-mu)//(mu-1), "population_metrics": {"population_size": mu,
        "unique_fraction": 1, "feasible_fraction": 1, "mean_pairwise_hamming": 3}}
        for q in a.historic.CHECKPOINTS]
    row["targets"] = {}
    for target in a.TARGETS:
        hit = a.historic.threshold(row, target)
        row["targets"][str(target)] = {"attained": hit is not None,
            "first_total_evaluation": hit, "restricted_evaluations": a.TOTAL if hit is None else hit}
    return row


def fixture():
    rows = []
    for family_index in range(10):
        for cfg_index, config in enumerate(a.PROFILES):
            for kind in a.historic.TYPES:
                for seed in a.SEEDS:
                    rows.append(make_case(config, family_index, kind, seed,
                        best=998 - cfg_index * (1 + family_index % 3),
                        first=1000 + (cfg_index - 1)**2 * (family_index+1)))
    return rows


class AnalysisTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows = fixture()
        cls.summaries, cls.families, cls.vectors = a.summarize(cls.rows)

    def validate(self, rows):
        return a.historic._validate_collection(rows, a.PROFILES, a.FAMILIES, a.SEEDS, "validation")

    def test_all_matched_physical_cases(self):
        self.assertEqual(len(self.validate(self.rows)), 1200)
        self.assertEqual([p["runs"] for p in self.summaries], [300] * 4)
        self.assertEqual(len(self.families), 40)

    def test_incomplete_duplicate_and_mixed_bank(self):
        for data in (self.rows[:-1], self.rows[:-1] + [self.rows[0]]):
            with self.assertRaises(ValueError):
                self.validate(data)
        data = list(self.rows)
        data[0] = {**data[0], "bank_sha256": "f" * 64}
        with self.assertRaises(ValueError):
            self.validate(data)

    def test_threshold_at_initial_prefix_final_and_miss(self):
        for first, best, expected in ((2, 990, 2), (100000, 930, 100000), (None, 929, None)):
            row = make_case(a.QUALITY, 0, "SC", 160001, first=first, best=best)
            a.historic.validate_row(row, "validation")
            self.assertEqual(expected, a.historic.threshold(row, 93))
            self.assertEqual(row["targets"]["93"]["restricted_evaluations"], expected or a.TOTAL)

    def test_tampered_checkpoint_or_attainment_is_rejected(self):
        row = deepcopy(self.rows[0])
        row["targets"]["93"]["attained"] = False
        with self.assertRaises(ValueError):
            a.historic.validate_row(row, "validation")
        row = deepcopy(self.rows[0])
        row["checkpoints"][-1]["record_profit"] -= 1
        with self.assertRaises(ValueError):
            a.historic.validate_row(row, "validation")

    def test_monotone_curves_and_table_totals(self):
        finals = {}
        for target in a.TARGETS:
            curves = a.attainment(self.rows, target)
            for profile in self.summaries:
                values = [r for r in curves if r["configuration"] == profile["configuration"]]
                self.assertEqual([values[0]["evaluations"], values[-1]["evaluations"]], [0, a.TOTAL])
                counts = [r["reached"] for r in values]
                self.assertEqual(counts, sorted(counts))
                self.assertEqual(values[-1]["reached"], profile[f"attained_{target}"])
                self.assertTrue(all(x["denominator"] == 300 for x in values))
                finals.setdefault(profile["configuration"], []).append(counts[-1])
        self.assertTrue(all(counts == sorted(counts, reverse=True) for counts in finals.values()))

    def test_six_registered_contrasts_and_secondary_separation(self):
        six, fams, base, draw = a.primary_comparisons(self.vectors)
        self.assertEqual(len(six), 6)
        self.assertEqual(len(fams), 60)
        self.assertEqual(sum(s["status"] == "IDENTICAL" for s in six), 2)
        self.assertTrue(all(s["control"] != a.profile_name(a.SECONDARY) for s in six))
        self.assertTrue(base)
        self.assertEqual(len(draw), 64)
        for row in six:
            if row["status"] == "IDENTICAL":
                self.assertEqual((row["estimate"], row["lower"], row["upper"]), (0, None, None))
            else:
                self.assertGreater(row["estimate"], 0)
                self.assertEqual(row["conclusion"], "FAVOURS_CANDIDATE")

    def test_constant_low_variance_does_not_establish_superiority(self):
        const = {cfg: {metric: (Fraction(i + 1),)*10 for metric in ("final_gap", "t93")}
                 for i, cfg in enumerate(a.PROFILES)}
        six, _, confirmed, _ = a.primary_comparisons(const)
        self.assertFalse(confirmed)
        self.assertTrue(all(r["lower"] is None and r["upper"] is None for r in six))
        self.assertEqual(sum(r["conclusion"] == "DESCRIPTIVE" for r in six), 4)

    def test_separate_diagnostic_retains_sign_pair_counts_and_families(self):
        secondary = a.secondary_diagnostic(self.rows, self.vectors)
        self.assertEqual(secondary["mean_t93_mu15_minus_mu10"], 22)
        self.assertEqual((secondary["mu10_faster"], secondary["mu15_faster"], secondary["ties"]), (300, 0, 0))
        self.assertEqual([x["family"] for x in secondary["families"]], list(a.FAMILIES))
        self.assertEqual(secondary["families"][0]["without_family"], 24)
        self.assertEqual(secondary["analysis"], "PRESPECIFIED_SECONDARY_DESCRIPTIVE")

    def test_interval_covering_zero_and_opposite_direction(self):
        interval = {"status": "INFERENTIAL_BCA", "lower": -2., "upper": 0.}
        self.assertEqual(a.conclusion(interval), "DIRECTION_UNRESOLVED")
        self.assertEqual(a.conclusion({**interval, "upper": -.01}), "FAVOURS_CONTROL")

    def test_report_marks_unconfirmed_base(self):
        six, _, _, _ = a.primary_comparisons(self.vectors)
        data = {"profiles": self.summaries, "secondary": a.secondary_diagnostic(self.rows, self.vectors),
                "primary": six, "quality_base_confirmed_against_both_distinct_controls": False}
        self.assertIn("умову не виконано", report.markdown(data, []))


if __name__ == "__main__":
    unittest.main()
