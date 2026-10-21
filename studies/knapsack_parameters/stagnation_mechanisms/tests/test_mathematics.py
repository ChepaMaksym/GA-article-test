"""Independent enumerable fixtures; execute only in the CI test phase."""

from copy import deepcopy
from itertools import combinations, product
import math
import unittest

from ..mathematics import (certificate_features, detection_probability,
                          mutation_probability)


def fixture_certificate(weights, profits, capacity, center, optimum):
    """A separate bit-string enumeration, not production certificate code."""
    n = len(weights)
    def score(bits):
        selected = [i for i in range(n) if bits[i] == "1"]
        return sum(weights[i] for i in selected), sum(profits[i] for i in selected)
    cw, cv = score(center)
    rows = []
    for distance in (1, 2):
        for positions in combinations(range(n), distance):
            bits = list(center)
            for index in positions:
                bits[index] = "1" if bits[index] == "0" else "0"
            mask = "".join(bits)
            weight, profit = score(mask)
            feasible = weight <= capacity
            rows.append({"flips": list(positions), "mask": mask,
                         "weight": weight, "profit": profit, "feasible": feasible,
                         "infeasibility_reason": None if feasible else "CAPACITY_EXCEEDED",
                         "relation": (1 if profit > cv else -1 if profit < cv else 0)
                         if feasible else None})
    better = sum(row["feasible"] and row["profit"] > cv for row in rows)
    equal = sum(row["feasible"] and row["profit"] == cv for row in rows)
    feasible_count = sum(row["feasible"] for row in rows)
    state = ("GLOBAL_OPTIMUM" if cv == optimum else "N2_NOT_LOCAL" if better
             else "N2_NONSTRICT_NONGLOBAL" if equal else "N2_STRICT_NONGLOBAL")
    return {"summary": {"n": n, "center_mask": center, "center_weight": cw,
                        "center_profit": cv, "optimum": optimum,
                        "neighbor_count": len(rows),
                        "feasible_neighbor_count": feasible_count,
                        "infeasible_neighbor_count": len(rows) - feasible_count,
                        "better_feasible_count": better,
                        "equal_feasible_count": equal, "state": state},
            "neighbors": rows}


class ProbabilityTests(unittest.TestCase):
    def test_mutation_formula_matches_full_small_binary_enumeration(self):
        n = 5
        targets = {(0,), (3,), (0, 2), (1, 4), (2, 3)}
        for p in (0, .005, .01, .02, .03, .08, .5, 1):
            expected = 0.0
            for bits in product((0, 1), repeat=n):
                flipped = tuple(i for i, bit in enumerate(bits) if bit)
                if flipped in targets:
                    probability = 1.0
                    for bit in bits:
                        probability *= p if bit else 1 - p
                    expected += probability
            self.assertAlmostEqual(mutation_probability(n, 2, 3, p), expected, places=14)

    def test_mutation_endpoints_and_all_radius_two_neighbors(self):
        self.assertEqual(mutation_probability(2, 2, 1, 0), 0)
        self.assertEqual(mutation_probability(2, 2, 1, 1), 1)
        self.assertEqual(mutation_probability(100, 100, 4950, 1), 0)
        self.assertEqual(mutation_probability(100, 0, 0, .01), 0)
        p = .13
        expected = 4 * p * (1 - p) ** 3 + 6 * p ** 2 * (1 - p) ** 2
        self.assertAlmostEqual(mutation_probability(4, 4, 6, p), expected)

    def test_invalid_mutation_inputs_rejected(self):
        bad = ((1, 0, 0, .01), (True, 0, 0, .01), (100., 0, 0, .01),
               (100, -1, 0, .01), (100, 101, 0, .01), (100, 0, 4951, .01),
               (100, 0, False, .01), (100, 0, 1.5, .01),
               (100, 0, 0, True), (100, 0, 0, float("nan")),
               (100, 0, 0, float("inf")), (100, 0, 0, -.1), (100, 0, 0, 1.1))
        for values in bad:
            with self.subTest(values=values), self.assertRaises(ValueError):
                mutation_probability(*values)

    def test_detection_matches_enumerated_samples_without_replacement(self):
        for total in range(1, 8):
            for better in range(total + 1):
                for sample in range(total + 1):
                    draws = list(combinations(range(total), sample))
                    detected = sum(any(i < better for i in draw) for draw in draws)
                    expected = detected / len(draws)
                    self.assertAlmostEqual(detection_probability(total, better, sample), expected)

    def test_real_neighborhood_counts_and_monotone_sample_sizes(self):
        probabilities = [detection_probability(5050, 1, s) for s in (50, 100, 250)]
        self.assertEqual(probabilities, sorted(probabilities))
        for sample, probability in zip((50, 100, 250), probabilities):
            self.assertAlmostEqual(probability, sample / 5050)
        for sample in (50, 100, 250):
            self.assertEqual(detection_probability(5050, 0, sample), 0)
            self.assertEqual(detection_probability(5050, 5050, sample), 1)
            self.assertTrue(math.isfinite(detection_probability(5050, 1, sample)))
        self.assertEqual(detection_probability(5050, 5050, 0), 0)
        self.assertEqual(detection_probability(5050, 1, 5050), 1)

    def test_invalid_sampling_inputs_rejected(self):
        for values in ((0, 0, 0), (True, 0, 0), (5, -1, 2), (5, 6, 2),
                       (5, 1, 6), (5, 1, -.1), (5, True, 1), (5, 1, False)):
            with self.subTest(values=values), self.assertRaises(ValueError):
                detection_probability(*values)


class CertificateFeatureTests(unittest.TestCase):
    weights = (1, 2, 3, 4)
    profits = (2, 3, 4, 5)
    capacity = 7

    def extract(self, certificate, **kwargs):
        return certificate_features(certificate, weights=kwargs.get("weights", self.weights),
                                    profits=kwargs.get("profits", self.profits),
                                    capacity=kwargs.get("capacity", self.capacity))

    def certificate(self):
        return fixture_certificate(self.weights, self.profits, self.capacity, "0100", 10)

    def test_features_separate_radii_types_gains_and_slack(self):
        certificate = self.certificate()
        before = deepcopy(certificate)
        result = self.extract(certificate)
        self.assertEqual(certificate, before)
        self.assertEqual((result["b1"], result["b2"], result["total_better"]), (3, 4, 7))
        self.assertEqual(result["slack"], 5)
        self.assertEqual((result["min_positive_gain"], result["max_positive_gain"]), (1, 7))
        self.assertEqual(result["sum_positive_gain"], 27)
        self.assertEqual(result["improvement_types"],
                         {"add_one": 3, "remove_one": 0, "swap_one": 2,
                          "add_two": 2, "remove_two": 0})

    def test_no_better_neighbors_preserves_null_gains_and_zero_counts(self):
        weights, profits = (6, 5, 5), (10, 8, 8)
        certificate = fixture_certificate(weights, profits, 10, "100", 16)
        result = self.extract(certificate, weights=weights, profits=profits, capacity=10)
        self.assertEqual((result["b1"], result["b2"], result["total_better"]), (0, 0, 0))
        self.assertIsNone(result["min_positive_gain"])
        self.assertIsNone(result["max_positive_gain"])
        self.assertEqual(result["sum_positive_gain"], 0)
        self.assertEqual(certificate["summary"]["state"], "N2_STRICT_NONGLOBAL")

    def test_complete_hundred_bit_neighborhood_has_exactly_5050_rows(self):
        weights = profits = (1,) * 100
        certificate = fixture_certificate(weights, profits, 100, "0" * 100, 100)
        result = self.extract(certificate, weights=weights, profits=profits, capacity=100)
        self.assertEqual(result["neighbor_count"], 5050)
        self.assertEqual((result["b1"], result["b2"]), (100, 4950))
        self.assertEqual(result["improvement_types"]["add_two"], 4950)

    def test_global_and_plateau_certificates_are_not_confused(self):
        weights, profits = (2, 2, 1, 1), (2, 2, 2, 2)
        global_cert = fixture_certificate(weights, profits, 2, "0011", 4)
        plateau_cert = fixture_certificate(weights, profits, 2, "1000", 4)
        for certificate in (global_cert, plateau_cert):
            result = self.extract(certificate, weights=weights, profits=profits, capacity=2)
            self.assertEqual(result["total_better"], 0)
        self.assertEqual(global_cert["summary"]["state"], "GLOBAL_OPTIMUM")
        self.assertEqual(plateau_cert["summary"]["state"], "N2_NONSTRICT_NONGLOBAL")

    def test_partial_duplicate_reordered_and_wrong_masks_rejected(self):
        corruptions = []
        missing = self.certificate()
        missing["neighbors"].pop()
        corruptions.append(missing)
        duplicate = self.certificate()
        duplicate["neighbors"][1] = deepcopy(duplicate["neighbors"][0])
        corruptions.append(duplicate)
        reordered = self.certificate()
        reordered["neighbors"][0:2] = reversed(reordered["neighbors"][0:2])
        corruptions.append(reordered)
        wrong = self.certificate()
        wrong["neighbors"][0]["mask"] = "0000"
        corruptions.append(wrong)
        repeated_index = self.certificate()
        repeated_index["neighbors"][4]["flips"] = [0, 0]
        corruptions.append(repeated_index)
        missing_field = self.certificate()
        missing_field["neighbors"][0].pop("relation")
        corruptions.append(missing_field)
        for certificate in corruptions:
            with self.subTest(certificate=certificate), self.assertRaises(ValueError):
                self.extract(certificate)

    def test_scores_feasibility_relations_and_summary_rechecked(self):
        for field, wrong in (("weight", 1000), ("profit", 1000), ("feasible", False),
                             ("relation", True), ("infeasibility_reason", "wrong")):
            certificate = self.certificate()
            certificate["neighbors"][0][field] = wrong
            with self.subTest(field=field), self.assertRaises(ValueError):
                self.extract(certificate)
        for field, wrong in (("better_feasible_count", 0), ("center_profit", 4),
                             ("n", 100), ("state", "GLOBAL_OPTIMUM"),
                             ("neighbor_count", True)):
            certificate = self.certificate()
            certificate["summary"][field] = wrong
            with self.subTest(field=field), self.assertRaises(ValueError):
                self.extract(certificate)

    def test_source_dimensions_values_and_optimum_consistency_required(self):
        for overrides in ({"weights": (1, 2)}, {"profits": (0, 3, 4, 5)},
                          {"weights": (True, 2, 3, 4)}, {"capacity": 1}):
            with self.subTest(overrides=overrides), self.assertRaises(ValueError):
                self.extract(self.certificate(), **overrides)
        certificate = self.certificate()
        certificate["summary"]["optimum"] = 3
        with self.assertRaisesRegex(ValueError, "neighbor exceeds"):
            self.extract(certificate)


if __name__ == "__main__":
    unittest.main()
