"""Independent, post-search reconstruction of crossover and mutation effects.

This module neither imports nor invokes the search, its evaluator, selection,
adaptation or an exact solver. All intermediate scores are retrospective.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import numpy as np


SCHEMA = "knapsack-stagnation-operator-mechanisms-v1"
EVENTS = ("created", "preserved", "lost", "neither")


def _require(condition, message):
    if not condition:
        raise ValueError(message)


def _integer(value):
    return isinstance(value, (int, np.integer)) and not isinstance(value, (bool, np.bool_))


def _scores(instance, masks):
    """Python-integer sums in original item order, independent of GA helpers."""
    return [(sum(int(w) for w, bit in zip(instance.weights, mask) if int(bit)),
             sum(int(v) for v, bit in zip(instance.profits, mask) if int(bit)))
            for mask in masks]


def _groups(payload, select):
    def count(field):
        return int(np.count_nonzero(payload[field][select]))

    applied = select & payload["crossover_applied"]
    defined = applied & payload["feasible_parent_baseline"]
    transitions = {}
    for before, after, label in ((False, False, "infeasible_to_infeasible"),
                                  (False, True, "infeasible_to_feasible"),
                                  (True, False, "feasible_to_infeasible"),
                                  (True, True, "feasible_to_feasible")):
        transitions[label] = int(np.count_nonzero(
            select & (payload["premutation_feasible"] == before)
            & (payload["final_feasible"] == after)))
    return {"candidate_count": int(np.count_nonzero(select)),
            "crossover_applied_count": int(np.count_nonzero(applied)),
            "crossover_skipped_count": int(np.count_nonzero(select & ~payload["crossover_applied"])),
            "premutation_better_count": count("premutation_better_than_record"),
            "final_record_count": count("final_better_than_record"),
            **{f"mutation_{event}_count": count(f"mutation_{event}") for event in EVENTS},
            "premutation_feasible_count": count("premutation_feasible"),
            "final_feasible_count": count("final_feasible"),
            "feasibility_transitions": transitions,
            "zero_mutation_count": int(np.count_nonzero(select & (payload["mutation_flip_count"] == 0))),
            "duplicate_count": count("duplicate"),
            "record_present_in_population_count": count("record_present_in_population"),
            "record_selected_candidate_count": int(np.count_nonzero(
                select & (payload["record_selected_parent_slots"] > 0))),
            "record_selected_parent_slots": int(payload["record_selected_parent_slots"][select].sum()),
            "record_pending_count": count("record_ref_is_pending"),
            "record_absent_from_population_and_pending_count": count("record_absent_from_population_and_pending"),
            "crossover_actual_change_from_first_parent_count": int(np.count_nonzero(
                applied & (payload["crossover_distance_parent_a"] > 0))),
            "crossover_novel_to_both_parents_count": int(np.count_nonzero(
                applied & (payload["crossover_distance_parent_a"] > 0)
                & (payload["crossover_distance_parent_b"] > 0))),
            "crossover_conditioned": {
                "candidate_count": int(np.count_nonzero(applied)),
                "feasible_parent_baseline_count": int(np.count_nonzero(defined)),
                "undefined_parent_baseline_count": int(np.count_nonzero(applied & ~payload["feasible_parent_baseline"])),
                "premutation_better_than_parent_count": int(np.count_nonzero(
                    defined & (payload["premutation_better_than_best_feasible_parent"] == 1))),
                "final_better_than_parent_count": int(np.count_nonzero(
                    defined & (payload["final_better_than_best_feasible_parent"] == 1)))}}


def analyze_operators(instance, result, diagnosis, per_candidate_output_optional=None):
    """Audit saved operators and return JSON-safe counts, never alter search.

    A strict feasible record is updated after each final evaluated candidate,
    including candidates still pending in an incomplete generation. Equal
    scores retain the first-attainment record mask. For parent-relative fields,
    -1 in the optional audit arrays means neither selected parent is feasible.
    The late window is q=4001..5000, not an outcome-dependent subset.
    """
    raw, summary = result["requests"], result["summary"]
    masks = np.asarray(raw["masks"])
    n = instance.n
    _require(_integer(n) and n > 0 and _integer(instance.capacity) and instance.capacity >= 0,
             "Invalid source dimensions or capacity")
    _require(len(instance.weights) == len(instance.profits) == n
             and all(_integer(v) and v > 0 for v in tuple(instance.weights) + tuple(instance.profits)),
             "Positive original integer items required")
    _require(max(sum(map(int, instance.weights)), sum(map(int, instance.profits)),
                 int(instance.capacity)) <= np.iinfo(np.int64).max,
             "Exact audit-array integer bound exceeded")
    _require(masks.ndim == 2 and masks.shape[1] == n and np.all((masks == 0) | (masks == 1)),
             "Invalid request masks")
    size, count = summary["known_initial_requests"], len(masks)
    _require(_integer(size) and 2 <= size < count, "Invalid initial/new evaluation accounting")
    new_count, width = count - size, (n + 7) // 8
    for key, expected in (("logical_requests", count), ("budget", count),
                          ("physical_evaluations", new_count), ("population_size", size)):
        _require(summary.get(key, expected) == expected, "Summary request accounting mismatch")
    for field in ("weight", "profit", "feasible", "duplicate", "generation", "crossover_applied"):
        _require(np.asarray(raw[field]).shape == (count,), "Invalid request field dimensions")
    for field in ("weight", "profit", "generation", "parents", "crossover_bits", "mutation_bits"):
        _require(np.asarray(raw[field]).dtype.kind in "iu", "Integer request fields required")
    for field in ("feasible", "duplicate", "crossover_applied"):
        _require(np.asarray(raw[field]).dtype.kind == "b", "Boolean request fields required")
    _require(np.asarray(raw["parents"]).shape == (count, 2), "Invalid parent dimensions")
    unpacked = {}
    for field in ("crossover_bits", "mutation_bits"):
        packed = np.asarray(raw[field])
        _require(packed.shape == (count, width) and np.all(packed >= 0)
                 and np.all(packed <= 255), "Invalid packed operator bits")
        bits = np.unpackbits(packed.astype(np.uint8), axis=1, bitorder="big")
        _require(not np.any(bits[:, n:]), "Nonzero operator padding bits")
        unpacked[field] = bits[:, :n]
    scores = _scores(instance, masks)
    for ref, (weight, profit) in enumerate(scores):
        _require(int(raw["weight"][ref]) == weight and int(raw["profit"][ref]) == profit
                 and bool(raw["feasible"][ref]) == (weight <= instance.capacity),
                 "Final request integer score mismatch")
    mask_keys = [bytes(int(bit) for bit in mask) for mask in masks]
    seen, best = set(), None
    for ref in range(size):
        _require(bool(raw["duplicate"][ref]) == (mask_keys[ref] in seen), "Initial duplicate flag mismatch")
        seen.add(mask_keys[ref])
        if scores[ref][0] <= instance.capacity and (best is None or scores[ref][1] > scores[best][1]):
            best = ref
    _require(best is not None, "No initial feasible record")
    initial_record = best
    integer_fields = ("q", "request_ref", "generation", "parent_a_ref", "parent_b_ref",
                      "record_before_ref", "record_before_profit", "premutation_weight",
                      "premutation_profit", "final_weight", "final_profit", "mutation_flip_count",
                      "parent_hamming", "crossover_distance_parent_a", "crossover_distance_parent_b",
                      "record_selected_parent_slots")
    boolean_fields = ("crossover_applied", "premutation_feasible", "final_feasible", "duplicate",
                      "premutation_better_than_record", "final_better_than_record", "feasible_parent_baseline",
                      "record_present_in_population", "record_ref_is_pending",
                      "record_absent_from_population_and_pending", "generation_complete")
    payload = {name: np.zeros(new_count, dtype=np.int64) for name in integer_fields}
    payload.update({name: np.zeros(new_count, dtype=np.bool_) for name in boolean_fields})
    payload.update({f"mutation_{event}": np.zeros(new_count, dtype=np.bool_) for event in EVENTS})
    for name in ("premutation_better_than_best_feasible_parent", "final_better_than_best_feasible_parent"):
        payload[name] = np.full(new_count, -1, dtype=np.int8)
    generations = result["generations"]
    population, used = list(range(size)), size
    _require(bool(generations) and generations[0]["generation"] == 0
             and generations[0]["complete"] is True and generations[0]["first_request"] == 1
             and generations[0]["last_request"] == size and generations[0]["population_before"] == []
             and generations[0]["population_after"] == population, "Initial generation provenance mismatch")
    committed = [(0, population.copy())]
    record_after = [initial_record]
    for ordinal, generation in enumerate(generations[1:], 1):
        _require(generation["generation"] == ordinal and generation["population_before"] == population
                 and generation["first_request"] == used + 1, "Generation population/continuity mismatch")
        end = generation["last_request"]
        _require(_integer(end) and used < end <= count and end - used <= size - 1,
                 "Invalid generation request range")
        complete = end - used == size - 1
        _require(generation["complete"] is complete and (complete or ordinal == len(generations) - 1),
                 "Incomplete generation must be terminal")
        position = generation["elite"]["population_index"]
        _require(_integer(position) and 0 <= position < size
                 and generation["elite"]["request_ref"] == population[position], "Invalid elite reference")
        before = population.copy()
        for ref in range(used, end):
            index, q = ref - size, ref - size + 1
            _require(int(raw["generation"][ref]) == ordinal, "Candidate generation mismatch")
            positions = [int(value) for value in raw["parents"][ref]]
            _require(all(0 <= value < size for value in positions), "Parent outside current population")
            a_ref, b_ref = (before[value] for value in positions)
            a, b = masks[a_ref], masks[b_ref]
            applied = bool(raw["crossover_applied"][ref])
            choice, flips = unpacked["crossover_bits"][ref], unpacked["mutation_bits"][ref]
            if applied:
                pre = [int(a[j]) if choice[j] else int(b[j]) for j in range(n)]
            else:
                _require(not np.any(choice), "Skipped crossover has nonzero choices")
                pre = [int(bit) for bit in a]
            final = [bit ^ int(flips[j]) for j, bit in enumerate(pre)]
            _require(final == [int(bit) for bit in masks[ref]], "Crossover/mutation reconstruction mismatch")
            pre_weight, pre_profit = _scores(instance, [pre])[0]
            pre_feasible, final_feasible = pre_weight <= instance.capacity, scores[ref][0] <= instance.capacity
            pre_better = pre_feasible and pre_profit > scores[best][1]
            final_better = final_feasible and scores[ref][1] > scores[best][1]
            duplicate = mask_keys[ref] in seen
            _require(bool(raw["duplicate"][ref]) == duplicate, "Final duplicate flag mismatch")
            best_key = mask_keys[best]
            present = any(mask_keys[item] == best_key for item in before)
            pending_present = any(mask_keys[item] == best_key for item in range(used, ref))
            values = {"q": q, "request_ref": ref, "generation": ordinal,
                      "parent_a_ref": a_ref, "parent_b_ref": b_ref, "record_before_ref": best,
                      "record_before_profit": scores[best][1], "premutation_weight": pre_weight,
                      "premutation_profit": pre_profit, "final_weight": scores[ref][0],
                      "final_profit": scores[ref][1], "mutation_flip_count": int(flips.sum()),
                      "parent_hamming": sum(int(x) != int(y) for x, y in zip(a, b)),
                      "crossover_distance_parent_a": sum(x != int(y) for x, y in zip(pre, a)),
                      "crossover_distance_parent_b": sum(x != int(y) for x, y in zip(pre, b)),
                      "record_selected_parent_slots": int(mask_keys[a_ref] == best_key) + int(mask_keys[b_ref] == best_key),
                      "crossover_applied": applied, "premutation_feasible": pre_feasible,
                      "final_feasible": final_feasible, "duplicate": duplicate,
                      "premutation_better_than_record": pre_better, "final_better_than_record": final_better,
                      "record_present_in_population": present, "record_ref_is_pending": used <= best < ref,
                      "record_absent_from_population_and_pending": not present and not pending_present,
                      "generation_complete": complete,
                      "mutation_created": not pre_better and final_better,
                      "mutation_preserved": pre_better and final_better,
                      "mutation_lost": pre_better and not final_better,
                      "mutation_neither": not pre_better and not final_better}
            parent_profits = [scores[item][1] for item in (a_ref, b_ref)
                              if scores[item][0] <= instance.capacity]
            values["feasible_parent_baseline"] = bool(parent_profits)
            if parent_profits:
                parent_best = max(parent_profits)
                values["premutation_better_than_best_feasible_parent"] = int(pre_feasible and pre_profit > parent_best)
                values["final_better_than_best_feasible_parent"] = int(final_feasible and scores[ref][1] > parent_best)
            for field, value in values.items():
                payload[field][index] = value
            seen.add(mask_keys[ref])
            if final_better:
                best = ref
            record_after.append(best)
        expected = [before[position]] + list(range(used, end)) if complete else before
        _require(generation["population_after"] == expected, "Wrong population commit or terminal prefix")
        population = expected
        if complete:
            committed.append((end - size, population.copy()))
        used = end
    _require(used == count and len(record_after) == new_count + 1, "Operator coverage incomplete")
    _require(summary.get("terminal_population_requests", population) == population, "Terminal population mismatch")
    checkpoints = []
    _require(bool(diagnosis["checkpoints"]), "Checkpoint evidence missing")
    for row in diagnosis["checkpoints"]:
        q = row["q"]
        _require(_integer(q) and 0 <= q <= new_count, "Checkpoint outside evaluated prefix")
        record_ref = record_after[q]
        mask = "".join(str(int(bit)) for bit in masks[record_ref])
        commit_q, refs = next((cq, pop) for cq, pop in reversed(committed) if cq <= q)
        pending = list(range(size + commit_q, size + q))
        _require(row["record_request_ref"] == record_ref and row["mask"] == mask
                 and row["population_refs"] == refs and row["pending_refs"] == pending,
                 "Checkpoint record/population differs from raw reconstruction")
        copies = sum(mask_keys[item] == mask_keys[record_ref] for item in refs)
        checkpoints.append({"q": int(q), "record_request_ref": int(record_ref), "record_mask": mask,
                            "committed_population_q": int(commit_q), "population_refs": refs.copy(),
                            "pending_refs": pending, "record_mask_present_in_population": copies > 0,
                            "record_mask_copy_count": int(copies), "record_request_ref_in_population": record_ref in refs,
                            "record_mask_present_in_pending": any(mask_keys[item] == mask_keys[record_ref] for item in pending),
                            "record_ref_is_pending": record_ref in pending})
    all_new = np.ones(new_count, dtype=np.bool_)
    late = (payload["q"] >= 4001) & (payload["q"] <= 5000)
    answer = {"schema_version": SCHEMA, "known_initial_evaluations": int(size),
              "new_evaluations": int(new_count), "late_window": {"first_q": 4001, "last_q": 5000},
              "groups": {"all_new": _groups(payload, all_new), "late_1000": _groups(payload, late)},
              "checkpoints": checkpoints,
              "accounting": {"verification_final_mask_evaluations": int(count),
                             "counterfactual_premutation_evaluations": int(new_count),
                             "new_search_evaluations": 0}}
    if per_candidate_output_optional is not None:
        path = Path(per_candidate_output_optional)
        _require(path.suffix == ".npz" and not path.exists(), "New NPZ audit path required")
        path.parent.mkdir(parents=True, exist_ok=True)
        np.savez_compressed(path, **payload)
        answer["per_candidate_evidence"] = {"name": path.name, "rows": int(new_count),
                                            "bytes": path.stat().st_size,
                                            "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
    return answer
