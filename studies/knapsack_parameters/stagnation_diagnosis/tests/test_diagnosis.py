"""Small independent diagnostic fixtures; scientific execution is CI-only."""

from copy import deepcopy
import unittest

import numpy as np

from studies.knapsack_parameters.feasibility.data_audit import Instance
from studies.knapsack_parameters.ga_study import engine
from studies.knapsack_parameters.stagnation_diagnosis.diagnosis import analyze_run, verify_diagnosis


def fixture(profits=(9, 5, 5), weights=(6, 5, 5), capacity=10):
    return Instance(len(profits), capacity, tuple(profits), tuple(weights),
                    "teaching.kp", "UC", "s000", 0)


def trace(instance, initial, children=(), *, elite_position=0):
    """Construct hand-auditable generation references, not a search experiment."""
    size = len(initial)
    masks = np.asarray(list(initial) + list(children), dtype=np.uint8)
    weight = np.asarray([sum(int(w) for bit, w in zip(mask, instance.weights) if bit)
                         for mask in masks], dtype=np.int64)
    profit = np.asarray([sum(int(p) for bit, p in zip(mask, instance.profits) if bit)
                         for mask in masks], dtype=np.int64)
    count = len(masks)
    population = list(range(size))
    generations = [{"generation": 0, "complete": True, "first_request": 1,
                    "last_request": size, "population_before": [],
                    "population_after": population.copy()}]
    used, ordinal = size, 0
    while used < count:
        ordinal += 1
        end = min(count, used + size - 1)
        before = population.copy()
        complete = end - used == size - 1
        elite = {"population_index": elite_position,
                 "request_ref": before[elite_position]}
        if complete:
            population = [before[elite_position]] + list(range(used, end))
        generations.append({"generation": ordinal, "complete": complete,
                            "first_request": used + 1, "last_request": end,
                            "population_before": before, "population_after": population.copy(),
                            "elite": elite})
        used = end
    return {"requests": {"masks": masks, "weight": weight, "profit": profit,
                         "feasible": weight <= instance.capacity},
            "summary": {"known_initial_requests": size, "logical_requests": count,
                        "physical_evaluations": count - size, "budget": count,
                        "population_size": size, "terminal_population_requests": population},
            "generations": generations}


class DiagnosisTests(unittest.TestCase):
    def read(self, instance, result, optimum, checkpoints=(0,), threshold=2):
        diagnosis = analyze_run(instance, result, optimum, checkpoints=checkpoints, threshold=threshold)
        verdict = verify_diagnosis(instance, result, optimum, diagnosis,
                                   checkpoints=checkpoints, threshold=threshold)
        self.assertEqual(verdict["status"], "PASS_DIAGNOSIS")
        return diagnosis

    def test_all_four_states(self):
        strict = fixture()
        nonstrict = fixture((9, 9, 5, 5), (6, 6, 5, 5))
        for instance, mask, optimum, expected in (
                (strict, [1, 0, 0], 10, "N2_STRICT_NONGLOBAL"),
                (strict, [0, 1, 0], 10, "N2_NOT_LOCAL"),
                (strict, [0, 1, 1], 10, "GLOBAL_OPTIMUM"),
                (nonstrict, [1, 0, 0, 0], 10, "N2_NONSTRICT_NONGLOBAL")):
            with self.subTest(state=expected):
                result = trace(instance, [mask, [0] * instance.n])
                value = self.read(instance, result, optimum)
                self.assertEqual(value["checkpoints"][0]["state"], expected)

    def test_full_neighbor_order_scores_and_infeasible_reason(self):
        instance = fixture()
        result = trace(instance, [[1, 0, 0], [0, 0, 0]])
        diagnosis = self.read(instance, result, 10)
        certificate = next(iter(diagnosis["certificates"].values()))
        self.assertEqual([row["flips"] for row in certificate["neighbors"]],
                         [[0], [1], [2], [0, 1], [0, 2], [1, 2]])
        self.assertEqual(certificate["neighbors"][1]["mask"], "110")
        self.assertEqual(certificate["neighbors"][1]["weight"], 11)
        self.assertEqual(certificate["neighbors"][1]["infeasibility_reason"], "CAPACITY_EXCEEDED")
        self.assertIsNone(certificate["neighbors"][1]["relation"])
        self.assertEqual(certificate["summary"]["better_feasible_count"], 0)
        self.assertEqual(certificate["summary"]["equal_feasible_count"], 0)

    def test_initial_ties_first_attainment_and_record_absent_final_population(self):
        instance = fixture((1, 1), (1, 1), 1)
        result = trace(instance, [[1, 0], [0, 1]], [[0, 1]], elite_position=1)
        diagnosis = self.read(instance, result, 1, checkpoints=(0, 1))
        for row in diagnosis["checkpoints"]:
            self.assertEqual(row["mask"], "10")
            self.assertEqual(row["record_request_ref"], 0)
            self.assertEqual(row["last_improvement_q"], 0)
        terminal = diagnosis["checkpoints"][-1]
        self.assertNotIn(terminal["record_request_ref"], terminal["population_refs"])
        self.assertEqual(len(diagnosis["certificates"]), 1)

    def test_initial_best_at_last_initial_request_still_q_zero(self):
        instance = fixture()
        result = trace(instance, [[0, 0, 0], [1, 0, 0]], [[0, 0, 0]])
        diagnosis = self.read(instance, result, 10, checkpoints=(0, 1))
        self.assertEqual(diagnosis["checkpoints"][0]["record_request_ref"], 1)
        self.assertEqual(diagnosis["checkpoints"][0]["last_improvement_q"], 0)

    def test_checkpoint_midgeneration_and_exact_commit_boundary(self):
        instance = fixture()
        result = trace(instance, [[0, 0, 0]] * 3,
                       [[1, 0, 0], [0, 1, 0], [0, 0, 1]])
        diagnosis = self.read(instance, result, 10, checkpoints=(0, 1, 2, 3))
        rows = diagnosis["checkpoints"]
        self.assertEqual(rows[1]["population_refs"], [0, 1, 2])
        self.assertEqual(rows[1]["pending_refs"], [3])
        self.assertEqual(rows[2]["population_refs"], [0, 3, 4])
        self.assertEqual(rows[2]["pending_refs"], [])
        self.assertEqual(rows[3]["population_refs"], [0, 3, 4])
        self.assertEqual(rows[3]["pending_refs"], [5])

    def test_terminal_twelve_never_commits_and_last_request_updates_record(self):
        instance = fixture()
        result = trace(instance, [[0, 0, 0]] * 30,
                       [[0, 0, 0]] * 4999 + [[1, 0, 0]])
        diagnosis = self.read(instance, result, 10, checkpoints=(0, 1000, 2500, 5000), threshold=1000)
        row = diagnosis["checkpoints"][-1]
        self.assertEqual(len(row["pending_refs"]), 12)
        self.assertEqual(row["pending_refs"], list(range(5018, 5030)))
        self.assertEqual(row["last_improvement_q"], 5000)
        self.assertEqual(row["stagnation_age"], 0)
        self.assertFalse(row["stagnant"])
        self.assertEqual(row["record_request_ref"], 5029)
        self.assertNotIn(5029, row["population_refs"])
        self.assertEqual(diagnosis["population_trajectory"][-1]["best_profit"], 9)
        self.assertEqual(diagnosis["population_trajectory"][-1]["mean_feasible_profit"], 0)
        self.assertFalse(diagnosis["population_trajectory"][-1]["complete"])
        self.assertEqual(diagnosis["accounting"]["search_new_evaluations"], 5000)

    def test_stagnation_threshold_inclusive_and_equal_values_do_not_reset(self):
        instance = fixture((1, 1), (1, 1), 1)
        result = trace(instance, [[1, 0], [0, 0]], [[0, 1], [0, 1], [0, 1]])
        diagnosis = self.read(instance, result, 1, checkpoints=(0, 1, 2, 3), threshold=2)
        self.assertEqual([r["stagnation_age"] for r in diagnosis["checkpoints"]], [0, 1, 2, 3])
        self.assertEqual([r["stagnant"] for r in diagnosis["checkpoints"]], [False, False, True, True])

    def test_diversity_includes_duplicates_and_unordered_position_pairs(self):
        instance = fixture((1, 1), (1, 1), 2)
        result = trace(instance, [[0, 0], [0, 0], [1, 1]])
        diagnosis = self.read(instance, result, 2)
        row = diagnosis["checkpoints"][0]
        self.assertAlmostEqual(row["unique_fraction"], 2 / 3)
        self.assertAlmostEqual(row["mean_pairwise_hamming"], 4 / 3)
        self.assertAlmostEqual(diagnosis["population_trajectory"][0]["mean_feasible_profit"], 2 / 3)

    def test_cache_identity_covers_source_and_mask_and_costs(self):
        instance = fixture()
        result = trace(instance, [[1, 0, 0], [0, 0, 0]], [[1, 0, 0]] * 3)
        diagnosis = self.read(instance, result, 10, checkpoints=(0, 1, 3))
        self.assertEqual(len(diagnosis["certificates"]), 1)
        self.assertEqual(diagnosis["accounting"], {"known_initial_evaluations": 2,
            "search_new_evaluations": 3, "diagnostic_center_evaluations": 1,
            "diagnostic_neighbor_evaluations": 6, "diagnostic_total_evaluations": 7})
        verdict = verify_diagnosis(instance, result, 10, diagnosis, checkpoints=(0, 1, 3), threshold=2)
        self.assertEqual(verdict["verification_total_evaluations"], 12)
        other = Instance(3, 10, instance.profits, instance.weights, "other.kp", "UC", "s000", 0)
        changed = self.read(other, result, 10, checkpoints=(0, 1, 3))
        self.assertNotEqual(set(changed["certificates"]), set(diagnosis["certificates"]))

    def test_independent_verifier_rejects_certificate_corruption(self):
        instance = fixture()
        result = trace(instance, [[1, 0, 0], [0, 0, 0]])
        original = self.read(instance, result, 10)
        for field, value in (("weight", 999), ("profit", 999), ("mask", "111"),
                             ("flips", [2]), ("infeasibility_reason", "UNKNOWN")):
            corrupted = deepcopy(original)
            next(iter(corrupted["certificates"].values()))["neighbors"][0][field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                verify_diagnosis(instance, result, 10, corrupted, checkpoints=(0,), threshold=2)
        for action in ("remove", "duplicate", "summary", "extra"):
            corrupted = deepcopy(original)
            certificate = next(iter(corrupted["certificates"].values()))
            if action == "remove":
                certificate["neighbors"].pop()
            elif action == "duplicate":
                certificate["neighbors"][1] = deepcopy(certificate["neighbors"][0])
            elif action == "summary":
                certificate["summary"]["state"] = "GLOBAL_OPTIMUM"
            else:
                corrupted["certificates"]["extra"] = deepcopy(certificate)
            with self.subTest(action=action), self.assertRaises(ValueError):
                verify_diagnosis(instance, result, 10, corrupted, checkpoints=(0,), threshold=2)

    def test_independent_verifier_rejects_future_pending_metrics_and_scores(self):
        instance = fixture()
        result = trace(instance, [[0, 0, 0]] * 3, [[1, 0, 0], [0, 1, 0], [0, 0, 1]])
        diagnosis = self.read(instance, result, 10, checkpoints=(0, 1, 2, 3))
        for field, value in (("population_refs", [0, 3, 4]), ("pending_refs", [3, 4]),
                             ("unique_fraction", .2), ("mean_pairwise_hamming", 99),
                             ("last_improvement_q", 0), ("mask", "000")):
            corrupted = deepcopy(diagnosis)
            corrupted["checkpoints"][1][field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                verify_diagnosis(instance, result, 10, corrupted, checkpoints=(0, 1, 2, 3), threshold=2)
        corrupted_result = deepcopy(result)
        corrupted_result["requests"]["profit"][0] = 7
        with self.assertRaises(ValueError):
            verify_diagnosis(instance, corrupted_result, 10, diagnosis, checkpoints=(0, 1, 2, 3), threshold=2)
        corrupted_trajectory = deepcopy(diagnosis)
        corrupted_trajectory["population_trajectory"][-1]["best_profit"] = 0
        with self.assertRaises(ValueError):
            verify_diagnosis(instance, result, 10, corrupted_trajectory, checkpoints=(0, 1, 2, 3), threshold=2)

    def test_bad_optimum_infeasible_center_and_malformed_generations(self):
        instance = fixture()
        result = trace(instance, [[1, 0, 0], [0, 0, 0]])
        with self.assertRaises(ValueError):
            analyze_run(instance, result, 8, checkpoints=(0,))
        invalid = trace(instance, [[1, 1, 1], [1, 1, 0]])
        with self.assertRaises(ValueError):
            analyze_run(instance, invalid, 10, checkpoints=(0,))
        better_neighbor = trace(instance, [[0, 1, 0], [0, 0, 0]])
        with self.assertRaises(ValueError):
            analyze_run(instance, better_neighbor, 9, checkpoints=(0,))
        full = trace(instance, [[0, 0, 0]] * 3, [[1, 0, 0], [0, 1, 0], [0, 0, 1]])
        corrupted = deepcopy(full)
        corrupted["generations"][-1]["population_after"] = [3, 4, 5]
        with self.assertRaises(ValueError):
            analyze_run(instance, corrupted, 10, checkpoints=(0, 3))
        for checkpoints in ((1, 0), (0, 0), (-1,), (0, 4)):
            with self.subTest(checkpoints=checkpoints), self.assertRaises(ValueError):
                analyze_run(instance, full, 10, checkpoints=checkpoints)

    def test_actual_unchanged_kernel_and_deterministic_diagnosis(self):
        instance = fixture()
        bits = np.asarray([[0, 0, 0], [1, 0, 0], [0, 0, 0]], dtype=np.uint8)
        result = engine.run_search(instance, engine.Config(1., .9, 3), bits,
            engine.evaluate_masks(instance, bits), engine.make_rngs(0, 0, 92999), budget=14)
        before = deepcopy(result)
        first = self.read(instance, result, 10, checkpoints=(0, 1, 5, 11))
        second = self.read(instance, result, 10, checkpoints=(0, 1, 5, 11))
        self.assertEqual(first, second)
        for name in result["requests"]:
            np.testing.assert_array_equal(result["requests"][name], before["requests"][name])
        self.assertEqual(result["generations"], before["generations"])
        self.assertEqual(result["summary"], before["summary"])


if __name__ == "__main__":
    unittest.main()
