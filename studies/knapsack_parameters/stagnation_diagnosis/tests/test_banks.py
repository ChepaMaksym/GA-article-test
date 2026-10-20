"""Small bank mechanism fixtures; execution belongs exclusively to CI."""

from copy import deepcopy
import unittest

import numpy as np

from studies.knapsack_parameters.feasibility.data_audit import Instance
from studies.knapsack_parameters.stagnation_diagnosis.banks import prepare_bank, verify_bank


def fixture(n=3):
    return Instance(n, 5, tuple(range(1, n + 1)), tuple(range(1, n + 1)),
                    "teaching.kp", "UC", "s000", 0)


class BankTests(unittest.TestCase):
    def test_registered_seed_and_independent_reconstruction(self):
        instance = fixture()
        bank, metadata = prepare_bank(instance, 0, 92999)
        expected = np.random.Generator(np.random.PCG64(np.random.SeedSequence([93000, 0, 92999])))
        self.assertEqual(bank["masks"].shape, (30, 3))
        self.assertEqual(bank["masks"][0].tolist(), [0, 0, 0])
        np.testing.assert_array_equal(bank["masks"][1:], expected.random((29, 3)) < .5)
        self.assertEqual(metadata["physical_initial_evaluations"], 30)
        verdict = verify_bank(instance, 0, 92999, bank, metadata)
        self.assertEqual(verdict["status"], "PASS_BANK")
        self.assertEqual(verdict["verified_initial_evaluations"], 30)

    def test_deterministic_and_separated_ordinal_and_seed(self):
        instance = fixture(20)
        bank, metadata = prepare_bank(instance, 2, 93001)
        repeat, repeated_metadata = prepare_bank(instance, 2, 93001)
        for key in bank:
            np.testing.assert_array_equal(bank[key], repeat[key])
        self.assertEqual(metadata, repeated_metadata)
        for ordinal, seed in ((3, 93001), (2, 93002)):
            other, _ = prepare_bank(instance, ordinal, seed)
            self.assertFalse(np.array_equal(bank["masks"], other["masks"]))

    def test_duplicates_preserved_and_ordered_scores(self):
        instance = fixture(1)
        bank, metadata = prepare_bank(instance, 0, 93001)
        self.assertLessEqual(len({row.tobytes() for row in bank["masks"]}), 2)
        self.assertEqual(len(bank["masks"]), 30)
        np.testing.assert_array_equal(bank["weight"], bank["masks"][:, 0])
        self.assertEqual(verify_bank(instance, 0, 93001, bank, metadata)["status"], "PASS_BANK")

    def test_corrupt_scores_masks_rng_and_identity_rejected(self):
        instance = fixture()
        bank, metadata = prepare_bank(instance, 0, 93001)
        for field in ("weight", "profit", "feasible", "masks"):
            corrupted = deepcopy(bank)
            if field == "masks":
                corrupted[field][0, 0] = 1
            elif field == "feasible":
                corrupted[field][0] = False
            else:
                corrupted[field][0] = 1
            with self.subTest(field=field), self.assertRaises(ValueError):
                verify_bank(instance, 0, 93001, corrupted, metadata)
        wrong_metadata = deepcopy(metadata)
        wrong_metadata["rng_state_terminal"]["state"]["state"] += 1
        with self.assertRaises(ValueError):
            verify_bank(instance, 0, 93001, bank, wrong_metadata)
        with self.assertRaises(ValueError):
            verify_bank(instance, 1, 93001, bank, metadata)
        with self.assertRaises(ValueError):
            verify_bank(instance, 0, 93002, bank, metadata)

    def test_malformed_bank_metadata_and_bit_values_rejected(self):
        instance = fixture()
        bank, metadata = prepare_bank(instance, 0, 93001)
        for value in (-1, True, 1.5):
            with self.subTest(value=value), self.assertRaises(ValueError):
                prepare_bank(instance, value, 93001)
        corrupt = deepcopy(bank)
        corrupt["masks"][0, 1] = 2
        with self.assertRaises(ValueError):
            verify_bank(instance, 0, 93001, corrupt, metadata)
        wrong = deepcopy(metadata)
        wrong["physical_initial_evaluations"] = 29
        with self.assertRaises(ValueError):
            verify_bank(instance, 0, 93001, bank, wrong)
        overflow = Instance(1, 1, (1 << 64,), (1,), "big.kp", "UC", "s000", 0)
        with self.assertRaises(ValueError):
            prepare_bank(overflow, 0, 93001)


if __name__ == "__main__":
    unittest.main()
