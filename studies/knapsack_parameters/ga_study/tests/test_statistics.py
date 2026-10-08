"""CI-only fixtures for the frozen family estimand and BCa specification."""

import unittest

import numpy as np

from studies.knapsack_parameters.ga_study.statistics import (
    CONTRAST_IDS,
    bca_family_intervals,
    factorial_contrasts,
    grouped_family_contrasts,
)


class FactorialContrastTests(unittest.TestCase):
    @staticmethod
    def rate_fixture():
        # Hand calculation: mutation .13, crossover .16, population .04,
        # interaction .06. Indices stand for the three registered levels.
        return np.asarray([
            [[.1 + .1*m + .05*c + .02*p + .03*m*c for p in range(3)]
             for c in range(3)]
            for m in range(3)
        ])

    def test_four_hand_calculated_contrasts(self):
        np.testing.assert_allclose(
            factorial_contrasts(self.rate_fixture()), [.13, .16, .04, .06],
            atol=1e-14, rtol=0,
        )

    def test_equal_family_weight_not_equal_instance_weight(self):
        fixture = self.rate_fixture()
        memberships, values = grouped_family_contrasts(
            {"UC-s000": fixture, "WC-s000": fixture*.5, "UC-s001": fixture*.25},
            {"UC-s000": {"family": "s000", "class_label": "UC"},
             "WC-s000": {"family": "s000", "class_label": "WC"},
             "UC-s001": {"family": "s001", "class_label": "UC"}},
        )
        np.testing.assert_allclose(values.mean(axis=0), [.065, .08, .02, .03])
        self.assertEqual(memberships[0]["admitted_class_count"], 2)
        self.assertEqual(memberships[1]["admitted_class_count"], 1)

    def test_invalid_rates_are_rejected(self):
        for rates in (np.zeros((27,)), np.full((3,3,3), np.nan), np.full((3,3,3), 1.1)):
            with self.assertRaises(ValueError):
                factorial_contrasts(rates)


class BootstrapTests(unittest.TestCase):
    def test_constant_contrast_remains_descriptive(self):
        result = bca_family_intervals(np.ones((10,4))*.2, replicates=100)
        self.assertTrue(all(row["status"] == "DESCRIPTIVE_ONLY" for row in result["intervals"]))
        self.assertTrue(all(row["lower"] is None for row in result["intervals"]))
        self.assertTrue(all(not row["positive_effect_supported"] for row in result["intervals"]))

    def test_fewer_than_five_whole_families_no_inference(self):
        result = bca_family_intervals(np.arange(16).reshape(4,4)/20, replicates=100)
        self.assertIsNone(result["resample_index_sha256"])
        self.assertEqual({row["reason"] for row in result["intervals"]}, {"fewer_than_five_families"})

    def test_seed_replay_shared_indices_and_bonferroni_level(self):
        values = np.asarray([
            [a, 2*a, -a, 0.0] for a in [-.1, 0, .05, .1, .15, .2, .3, .4, .5, .6]
        ])
        result = bca_family_intervals(values, replicates=2_000)
        self.assertEqual(result, bca_family_intervals(values, replicates=2_000))
        self.assertEqual(result["confidence_level_each"], .9875)
        self.assertAlmostEqual(result["nominal_joint_confidence"], .95)
        self.assertEqual([r["contrast_id"] for r in result["intervals"]], list(CONTRAST_IDS))
        self.assertEqual(len(result["resample_index_sha256"]), 64)
        first, second, third, fourth = result["intervals"]
        self.assertEqual(first["status"], "INFERENTIAL_BCA")
        self.assertAlmostEqual(second["lower"], 2*first["lower"])
        self.assertAlmostEqual(second["upper"], 2*first["upper"])
        self.assertAlmostEqual(third["lower"], -first["upper"])
        self.assertAlmostEqual(third["upper"], -first["lower"])
        self.assertEqual(fourth["status"], "DESCRIPTIVE_ONLY")

    def test_half_ties_bias_correction(self):
        values = np.asarray([[0.,0.,0.,0.], [.25,.25,.25,.25], [.5,.5,.5,.5],
                             [.75,.75,.75,.75], [1.,1.,1.,1.]])
        result = bca_family_intervals(values, replicates=1_000)
        rng = np.random.Generator(np.random.PCG64(np.random.SeedSequence([51031])))
        draws = rng.integers(0,5,size=(1_000,5))
        samples = values[draws,0].mean(axis=1)
        expected_fraction = (np.count_nonzero(samples < .5)
                             + .5*np.count_nonzero(samples == .5))/1_000
        self.assertEqual(result["intervals"][0]["bias_fraction"], expected_fraction)


if __name__ == "__main__":
    unittest.main()
