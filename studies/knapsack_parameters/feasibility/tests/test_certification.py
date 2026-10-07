"""CI-only independent certificate fixtures; synthetic, not KPLIB results."""

from copy import deepcopy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from studies.knapsack_parameters.feasibility import certification as cert
from studies.knapsack_parameters.feasibility.data_audit import Instance


def instance(profits, weights, capacity):
    return Instance(len(profits), capacity, tuple(profits), tuple(weights), "fixture.kp", "UC", "s000", 0)


class CertificationTests(unittest.TestCase):
    def test_strict_nonglobal_teaching_center_with_fresh_sums(self):
        data = instance((10, 8, 8), (6, 5, 5), 10)
        with patch("studies.knapsack_parameters.feasibility.ascent._best_neighbor", side_effect=AssertionError("ascent must not be reused")):
            summary, rows = cert.certify_center(data, "100")
        self.assertTrue(summary["strict"])
        self.assertEqual(summary["higher_feasible"], 0)
        self.assertEqual(summary["neighbor_count"], 6)
        self.assertEqual(cert.evaluate_mask(data, "011")["profit"], 16)
        for row in rows:
            bits = [1, 0, 0]
            for index in row["flips"]:
                bits[index] ^= 1
            self.assertEqual(row["weight"], sum(w * x for w, x in zip(data.weights, bits)))
            self.assertEqual(row["profit"], sum(p * x for p, x in zip(data.profits, bits)))
            self.assertEqual(row["reason"], "FEASIBLE" if row["weight"] <= 10 else "CAPACITY_EXCEEDED")

    def test_plateau_and_global_are_distinguished(self):
        plateau, _ = cert.certify_center(instance((10, 8, 8, 10), (6, 5, 5, 6), 10), "1000")
        self.assertTrue(plateau["plateau"])
        self.assertFalse(plateau["strict"])
        self.assertEqual(plateau["equal_feasible"], 1)
        global_summary, _ = cert.certify_center(instance((1, 2), (1, 1), 1), "01")
        self.assertTrue(global_summary["strict"])
        nonlocal_summary, _ = cert.certify_center(instance((1, 2), (1, 1), 1), "00")
        self.assertFalse(nonlocal_summary["local_maximum"])

    def test_exact_5050_unique_source_order_neighbors(self):
        summary, rows = cert.certify_center(instance((1,) * 100, (1,) * 100, 50), "1" * 50 + "0" * 50)
        self.assertEqual(summary["neighbor_count"], 5050)
        self.assertEqual(sum(row["distance"] == 1 for row in rows), 100)
        self.assertEqual(sum(row["distance"] == 2 for row in rows), 4950)
        self.assertEqual(len({tuple(row["flips"]) for row in rows}), 5050)
        self.assertTrue(all(len(set(row["flips"])) == row["distance"] for row in rows))
        self.assertEqual(rows[0]["flips"], [0])
        self.assertEqual(rows[-1]["flips"], [98, 99])

    def test_missing_duplicate_and_corrupt_neighbors_are_rejected(self):
        data = instance((10, 8, 8), (6, 5, 5), 10)
        summary, rows = cert.certify_center(data, "100")
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "neighbors.csv"
            cert.write_certificate_csv(path, rows)
            self.assertEqual(cert.validate_certificate(data, summary, path), summary)
            original = path.read_bytes()
            lines = original.splitlines(keepends=True)
            for damaged in (b"".join(lines[:-1]), b"".join([*lines[:2], lines[1], *lines[3:]]), original.replace(b",10,1,", b",11,1,", 1)):
                # The known row-pattern replacement is supplemented by an
                # explicit profit tamper so this fixture cannot be a no-op.
                if damaged == original:
                    damaged = original.replace(b",8,1,", b",9,1,", 1)
                self.assertNotEqual(damaged, original)
                path.write_bytes(damaged)
                with self.assertRaises(ValueError):
                    cert.validate_certificate(data, summary, path)

    def test_types_masks_and_witnesses_are_strict(self):
        data = instance((10, 8, 8), (6, 5, 5), 10)
        for mask in ("10", "10x", [1, 0, 0]):
            with self.assertRaises(ValueError):
                cert.evaluate_mask(data, mask)
        with self.assertRaises(ValueError):
            cert.validate_witness(data, {"optimum_profit": 16, "witness_mask": "111", "witness_profit": 26, "witness_weight": 16})
        summary, rows = cert.certify_center(data, "100")
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "neighbors.csv"
            cert.write_certificate_csv(path, rows)
            for field, value in (("strict", 1), ("neighbor_count", 6.0), ("higher_feasible", False)):
                damaged = deepcopy(summary)
                damaged[field] = value
                with self.assertRaises(ValueError):
                    cert.validate_certificate(data, damaged, path)


if __name__ == "__main__":
    unittest.main()
