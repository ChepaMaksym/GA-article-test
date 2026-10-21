"""Hand-built operator traces; executed exclusively by GitHub Actions."""

from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest

import numpy as np

from ..operators import analyze_operators


def problem(n=4, capacity=3, profits=(8, 5, 4, 1), weights=None):
    return SimpleNamespace(n=n, capacity=capacity, profits=tuple(profits),
                           weights=tuple(weights or [1] * n))


def trace(instance, initial, children, checkpoints=None, elite_positions=None):
    """Build a small trace from explicit parents, choices and mutation flips."""
    size, n = len(initial), instance.n
    masks = [list(row) for row in initial]
    parent_rows = [[-1, -1] for _ in initial]
    applied_rows = [False] * size
    choice_rows = [[0] * n for _ in initial]
    flip_rows = [[0] * n for _ in initial]
    generation_rows = [0] * size
    pop = list(range(size))
    generations = [{"generation": 0, "complete": True, "first_request": 1,
                    "last_request": size, "population_before": [], "population_after": pop.copy()}]
    cursor = 0
    ordinal = 0
    while cursor < len(children):
        ordinal += 1
        before = pop.copy()
        batch = children[cursor:cursor + size - 1]
        start = len(masks)
        for child in batch:
            parents = child.get("parents", (0, 0))
            applied = child.get("cross", False)
            choices = list(child.get("choices", [0] * n))
            flips = list(child.get("flips", [0] * n))
            a, b = (masks[before[position]] for position in parents)
            intermediate = [a[j] if choices[j] else b[j] for j in range(n)] if applied else a.copy()
            masks.append([bit ^ flips[j] for j, bit in enumerate(intermediate)])
            parent_rows.append(list(parents))
            applied_rows.append(applied)
            choice_rows.append(choices)
            flip_rows.append(flips)
            generation_rows.append(ordinal)
        position = 0 if elite_positions is None else elite_positions[ordinal - 1]
        complete = len(batch) == size - 1
        if complete:
            pop = [before[position]] + list(range(start, len(masks)))
        generations.append({"generation": ordinal, "complete": complete,
                            "first_request": start + 1, "last_request": len(masks),
                            "population_before": before, "population_after": pop.copy(),
                            "elite": {"population_index": position, "request_ref": before[position]}})
        cursor += len(batch)
    matrix = np.asarray(masks, dtype=np.uint8)
    weight = np.asarray([sum(w for bit, w in zip(mask, instance.weights) if bit) for mask in masks], dtype=np.int64)
    profit = np.asarray([sum(v for bit, v in zip(mask, instance.profits) if bit) for mask in masks], dtype=np.int64)
    duplicates, seen = [], set()
    for mask in masks:
        key = tuple(mask)
        duplicates.append(key in seen)
        seen.add(key)
    result = {"summary": {"known_initial_requests": size, "logical_requests": len(masks),
                           "budget": len(masks), "physical_evaluations": len(children),
                           "population_size": size, "terminal_population_requests": pop},
              "requests": {"masks": matrix, "weight": weight, "profit": profit,
                           "feasible": weight <= instance.capacity,
                           "parents": np.asarray(parent_rows, dtype=np.int16),
                           "generation": np.asarray(generation_rows, dtype=np.int32),
                           "crossover_applied": np.asarray(applied_rows, dtype=bool),
                           "crossover_bits": np.packbits(np.asarray(choice_rows, dtype=np.uint8), axis=1, bitorder="big"),
                           "mutation_bits": np.packbits(np.asarray(flip_rows, dtype=np.uint8), axis=1, bitorder="big"),
                           "duplicate": np.asarray(duplicates, dtype=bool)},
              "generations": generations}
    chosen = checkpoints if checkpoints is not None else (0, len(children))
    rows = []
    for q in chosen:
        best = None
        for ref in range(size + q):
            if weight[ref] <= instance.capacity and (best is None or profit[ref] > profit[best]):
                best = ref
        committed_q, committed = 0, list(range(size))
        for generation in generations[1:]:
            end_q = generation["last_request"] - size
            if generation["complete"] and end_q <= q:
                committed_q, committed = end_q, generation["population_after"]
        rows.append({"q": q, "record_request_ref": best,
                     "mask": "".join(map(str, masks[best])), "population_refs": committed.copy(),
                     "pending_refs": list(range(size + committed_q, size + q))})
    return result, {"checkpoints": rows}


class OperatorMechanismTests(unittest.TestCase):
    def analyze(self, instance, initial, children, **kwargs):
        result, diagnosis = trace(instance, initial, children, **kwargs)
        return analyze_operators(instance, result, diagnosis)

    def test_crossover_improvement_lost_by_mutation(self):
        value = self.analyze(problem(), [[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 0, 0]],
                             [{"parents": (0, 1), "cross": True, "choices": [1, 0, 0, 0],
                               "flips": [1, 0, 0, 0]}])
        group = value["groups"]["all_new"]
        self.assertEqual(group["mutation_lost_count"], 1)
        self.assertEqual(group["premutation_better_count"], 1)
        self.assertEqual(group["final_record_count"], 0)
        self.assertEqual(group["crossover_conditioned"]["premutation_better_than_parent_count"], 1)

    def test_mutation_creates_and_preserves_threshold_improvements(self):
        initial = [[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 0, 0]]
        created = self.analyze(problem(), initial, [{"flips": [0, 1, 0, 0]}])
        self.assertEqual(created["groups"]["all_new"]["mutation_created_count"], 1)
        preserved = self.analyze(problem(), initial, [{"parents": (0, 1), "cross": True,
                                                     "choices": [1, 0, 0, 0], "flips": [0, 0, 0, 1]}])
        self.assertEqual(preserved["groups"]["all_new"]["mutation_preserved_count"], 1)

    def test_equal_score_is_neither_not_new_record(self):
        value = self.analyze(problem(profits=(1, 1, 1, 1)),
                             [[1, 0, 0, 0], [0, 0, 0, 0]], [{"flips": [1, 1, 0, 0]}])
        group = value["groups"]["all_new"]
        self.assertEqual(group["mutation_neither_count"], 1)
        self.assertEqual(group["final_record_count"], 0)
        self.assertEqual(value["checkpoints"][-1]["record_request_ref"], 0)

    def test_infeasible_higher_profit_is_not_record(self):
        value = self.analyze(problem(capacity=1),
                             [[1, 0, 0, 0], [0, 0, 0, 0]], [{"flips": [0, 1, 0, 0]}])
        group = value["groups"]["all_new"]
        self.assertEqual(group["final_record_count"], 0)
        self.assertEqual(group["feasibility_transitions"]["feasible_to_infeasible"], 1)

    def test_no_feasible_selected_parent_is_explicitly_undefined(self):
        value = self.analyze(problem(capacity=1),
                             [[0, 0, 0, 0], [1, 1, 0, 0], [0, 0, 1, 1]],
                             [{"parents": (1, 2), "cross": True, "choices": [0, 0, 1, 1]}])
        condition = value["groups"]["all_new"]["crossover_conditioned"]
        self.assertEqual(condition["candidate_count"], 1)
        self.assertEqual(condition["feasible_parent_baseline_count"], 0)
        self.assertEqual(condition["undefined_parent_baseline_count"], 1)
        self.assertEqual(value["groups"]["all_new"]["feasibility_transitions"]["feasible_to_feasible"], 1)

    def test_parent_baseline_is_best_feasible_of_both_parents(self):
        value = self.analyze(problem(), [[0, 1, 0, 0], [1, 0, 0, 0], [0, 0, 0, 0]],
                             [{"parents": (0, 1), "cross": True, "choices": [0, 0, 0, 0]}])
        condition = value["groups"]["all_new"]["crossover_conditioned"]
        self.assertEqual(condition["premutation_better_than_parent_count"], 0)

    def test_terminal_partial_prefix_updates_record_not_population(self):
        value = self.analyze(problem(), [[0, 0, 0, 0]] * 3,
                             [{}, {}, {"flips": [1, 0, 0, 0]}], checkpoints=(0, 2, 3))
        final = value["checkpoints"][-1]
        self.assertEqual(final["record_request_ref"], 5)
        self.assertEqual(final["committed_population_q"], 2)
        self.assertFalse(final["record_mask_present_in_population"])
        self.assertTrue(final["record_ref_is_pending"])
        self.assertTrue(final["record_mask_present_in_pending"])
        self.assertEqual(final["pending_refs"], [5])

    def test_within_generation_new_record_pending_not_lost(self):
        value = self.analyze(problem(), [[0, 0, 0, 0]] * 3,
                             [{"flips": [1, 0, 0, 0]}, {}], checkpoints=(0, 1, 2))
        group = value["groups"]["all_new"]
        self.assertEqual(group["record_pending_count"], 1)
        self.assertEqual(group["record_absent_from_population_and_pending_count"], 0)

    def test_mask_presence_does_not_require_first_request_reference(self):
        value = self.analyze(problem(), [[1, 0, 0, 0], [1, 0, 0, 0]], [{}], elite_positions=(1,))
        final = value["checkpoints"][-1]
        self.assertEqual(final["record_request_ref"], 0)
        self.assertFalse(final["record_request_ref_in_population"])
        self.assertTrue(final["record_mask_present_in_population"])

    def test_equal_quality_other_genotype_is_not_record_mask_presence(self):
        value = self.analyze(problem(profits=(1, 1, 1, 1)),
                             [[1, 0, 0, 0], [0, 1, 0, 0]],
                             [{"parents": (1, 1)}], elite_positions=(1,))
        self.assertFalse(value["checkpoints"][-1]["record_mask_present_in_population"])

    def test_audit_arrays_preserve_big_bit_order_and_exact_scores(self):
        instance = problem(n=5, profits=(10, 2, 3, 4, 5), capacity=5)
        result, diagnosis = trace(instance, [[0] * 5] * 3,
                                  [{"flips": [1, 0, 0, 0, 1]}])
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "operators.npz"
            value = analyze_operators(instance, result, diagnosis, path)
            with np.load(path, allow_pickle=False) as arrays:
                self.assertEqual(arrays["mutation_flip_count"].tolist(), [2])
                self.assertEqual(arrays["final_profit"].tolist(), [15])
                self.assertEqual(arrays["premutation_profit"].tolist(), [0])
                self.assertEqual(arrays["mutation_created"].tolist(), [True])
            self.assertEqual(value["per_candidate_evidence"]["rows"], 1)
            with self.assertRaises(ValueError):
                analyze_operators(instance, result, diagnosis, path)

    def test_partition_and_feasibility_counts_have_explicit_denominators(self):
        value = self.analyze(problem(), [[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 0, 0]],
                             [{}, {"flips": [0, 1, 0, 0]}, {}])
        group = value["groups"]["all_new"]
        self.assertEqual(sum(group[f"mutation_{event}_count"] for event in ("created", "preserved", "lost", "neither")), 3)
        self.assertEqual(sum(group["feasibility_transitions"].values()), 3)
        self.assertEqual(group["crossover_applied_count"] + group["crossover_skipped_count"], 3)
        self.assertEqual(group["duplicate_count"], 2)
        self.assertEqual(group["zero_mutation_count"], 2)
        self.assertEqual(value["groups"]["late_1000"]["candidate_count"], 0)

    def test_last_1000_window_has_fixed_query_bounds(self):
        instance = problem(n=1, profits=(1,), capacity=1)
        result, diagnosis = trace(instance, [[0], [0]], [{}] * 5000)
        value = analyze_operators(instance, result, diagnosis)
        self.assertEqual(value["groups"]["all_new"]["candidate_count"], 5000)
        self.assertEqual(value["groups"]["late_1000"]["candidate_count"], 1000)
        self.assertEqual(value["late_window"], {"first_q": 4001, "last_q": 5000})

    def test_corrupt_operator_score_duplicate_or_parent_is_rejected(self):
        instance = problem()
        original, diagnosis = trace(instance, [[0, 0, 0, 0]] * 3,
                                    [{"flips": [1, 0, 0, 0]}])
        for corruption in ("mutation", "score", "duplicate", "parent", "generation", "padding", "cross"):
            value = deepcopy(original)
            raw = value["requests"]
            if corruption == "mutation":
                raw["mutation_bits"][-1, 0] = 0
            elif corruption == "score":
                raw["profit"][-1] += 1
            elif corruption == "duplicate":
                raw["duplicate"][-1] = True
            elif corruption == "parent":
                raw["parents"][-1, 0] = 3
            elif corruption == "generation":
                value["generations"][-1]["population_before"] = [1, 0, 2]
            elif corruption == "padding":
                raw["mutation_bits"][-1, 0] |= 1
            else:
                raw["crossover_bits"][-1, 0] = 128
            with self.subTest(corruption=corruption), self.assertRaises(ValueError):
                analyze_operators(instance, value, diagnosis)

    def test_corrupt_checkpoint_or_pending_commit_is_rejected(self):
        instance = problem()
        result, diagnosis = trace(instance, [[0, 0, 0, 0]] * 3,
                                  [{"flips": [1, 0, 0, 0]}])
        wrong = deepcopy(diagnosis)
        wrong["checkpoints"][-1]["pending_refs"] = []
        with self.assertRaises(ValueError):
            analyze_operators(instance, result, wrong)
        wrong = deepcopy(result)
        wrong["generations"][-1]["population_after"] = [0, 3, 2]
        with self.assertRaises(ValueError):
            analyze_operators(instance, wrong, diagnosis)


if __name__ == "__main__":
    unittest.main()
