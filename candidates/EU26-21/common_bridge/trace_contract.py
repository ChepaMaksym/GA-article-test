"""Independent transcript checks; no optimizer, dataset or classifier execution."""
from __future__ import annotations

import math
from typing import Any, Mapping, Sequence


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def _integer(value: Any, minimum: int = 0) -> int:
    _require(type(value) is int and value >= minimum, "invalid generation integer")
    return value


def _fitness(row: Mapping[str, Any]) -> tuple[float, float]:
    return (
        row["validation_weighted_balanced_accuracy"],
        row["negative_selected_feature_fraction"],
    )


def _binary(value: Any) -> list[int]:
    _require(isinstance(value, list) and len(value) == 40, "invalid generation mask")
    _require(all(type(bit) is int and bit in (0, 1) for bit in value), "nonbinary mask")
    return value


def validate_generations(
    arm: str,
    generations: Sequence[Mapping[str, Any]],
    evaluations: Sequence[Mapping[str, Any]],
    state: Mapping[str, Any],
) -> None:
    """Bind generation transitions and operator invariants to the query ledger."""
    _require(bool(generations), "empty generation ledger")
    _require(state["generation_count"] == len(generations), "generation count mismatch")
    calls = 50
    lam = 1.0
    distance = 10
    population = list(evaluations[:50])
    history = {tuple(row["mask"]) for row in population}
    parent: list[int] | None = None
    parent_fitness = max(_fitness(row) for row in population)
    for number, row in enumerate(generations, 1):
        _require(isinstance(row, Mapping), "generation must be an object")
        _require(_integer(row["generation"], 1) == number, "generation order mismatch")
        _require(_integer(row["calls_before"]) == calls, "generation call gap")
        after = _integer(row["calls_after"])
        _require(calls <= after <= 400, "generation exceeds budget")
        batch = evaluations[calls:after]
        last = number == len(generations)
        if arm == "lambda_no_reset":
            _require(row["lambda_before"] == lam, "lambda continuity mismatch")
            planned = int(math.floor(lam + 0.5))
            count = min(planned, (400 - calls) // 2)
            _require(_integer(row["planned_offspring_count_per_phase"], 1) == planned,
                     "offspring rounding mismatch")
            _require(_integer(row["evaluated_offspring_count_per_phase"], 1) == count,
                     "lambda tail count mismatch")
            _require(after - calls == 2 * count, "unpaired mutation/crossover calls")
            _require(row["mutation_probability"] == lam / 40, "mutation probability drift")
            _require(row["crossover_probability"] == 1 / lam, "crossover probability drift")
            strength = _integer(row["mutation_strength"])
            _require(strength <= 40, "mutation strength out of range")
            before = _binary(row["parent_before"])
            if parent is None:
                _require(any(before == item["mask"] and _fitness(item) == parent_fitness
                             for item in population), "initial parent is not an initial best")
            else:
                _require(before == parent, "parent continuity mismatch")
            _require(tuple(row["parent_fitness_before"]) == parent_fitness,
                     "parent fitness continuity mismatch")
            mutants, crossovers = batch[:count], batch[count:]
            for mutant in mutants:
                _require(sum(a != b for a, b in zip(before, mutant["mask"])) == strength,
                         "mutant Hamming distance mismatch")
            chosen = _integer(row["selected_mutant_index"])
            _require(chosen < count, "selected mutant index out of range")
            mutant = mutants[chosen]
            _require(_fitness(mutant) == max(_fitness(item) for item in mutants),
                     "selected mutant is not best")
            for child in crossovers:
                _require(all(bit in (p, m) for bit, p, m in
                             zip(child["mask"], before, mutant["mask"])),
                         "crossover contains an impossible allele")
                if lam == 1:
                    _require(child["mask"] == mutant["mask"], "c=1 crossover mismatch")
            pool = [item for item in [mutant, *crossovers] if item["mask"] != before]
            candidate = _binary(row["candidate_mask"])
            candidate_fitness = tuple(row["candidate_fitness"])
            if pool:
                best = max(_fitness(item) for item in pool)
                _require(candidate_fitness == best and any(
                    item["mask"] == candidate and _fitness(item) == best for item in pool
                ), "candidate is not an eligible best offspring")
            else:
                _require(candidate == before and candidate_fitness == parent_fitness,
                         "empty offspring pool must keep parent")
            success = candidate_fitness > parent_fitness
            accepted = candidate_fitness >= parent_fitness
            _require(row["strict_success"] is success, "strict-success flag mismatch")
            _require(row["accepted"] is accepted, "acceptance flag mismatch")
            parent = candidate if accepted else before
            if accepted:
                parent_fitness = candidate_fitness
            _require(_binary(row["parent_after"]) == parent, "parent replacement mismatch")
            lam = max(1.0, lam / 1.5) if success else min(40.0, lam * 1.5**0.25)
            _require(row["lambda_after"] == lam, "one-fifth update mismatch")
            truncated = count < planned
            _require(row["tail_truncated"] is truncated, "tail flag mismatch")
            _require(not truncated or last, "truncation before terminal generation")
        else:
            _require(_integer(row["distance_before"]) == distance, "CHC distance gap")
            catastrophe = distance == 0
            expected_phase = "cataclysmic_mutation" if catastrophe else "hux"
            _require(row["phase"] == expected_phase, "CHC phase mismatch")
            generated = _integer(row["generated_fresh_offspring"])
            _require(generated <= 50, "too many CHC offspring")
            if catastrophe:
                _require(generated == 50, "cataclysm must generate 50 offspring")
            count = min(generated, 400 - calls)
            _require(_integer(row["evaluated_fresh_offspring"]) == count,
                     "CHC prefix count mismatch")
            _require(after - calls == count, "CHC evaluation count mismatch")
            if not catastrophe:
                for item in batch:
                    mask = tuple(item["mask"])
                    _require(mask not in history, "CHC HUX reevaluates historical mask")
                    history.add(mask)
            else:
                history.update(tuple(item["mask"]) for item in batch)
            partial = count < generated
            _require(row["partial_population_update_skipped"] is partial,
                     "CHC partial-update flag mismatch")
            if partial:
                _require(last and after == 400, "partial CHC generation is not terminal")
            else:
                old_masks = [item["mask"] for item in population]
                if catastrophe:
                    best_parent = sorted(population, key=_fitness, reverse=True)[0]
                    population = sorted([best_parent, *batch], key=_fitness, reverse=True)[:50]
                    distance = 10
                else:
                    population = sorted([*population, *batch], key=_fitness, reverse=True)[:50]
                    if [item["mask"] for item in population] == old_masks:
                        distance -= 1
            _require(_integer(row["distance_after"]) == distance, "CHC distance update mismatch")
        calls = after
    _require(calls == 400, "generation ledger is incomplete")
    if arm == "lambda_no_reset":
        _require(state["final_lambda"] == lam, "terminal lambda mismatch")
        _require(tuple(state["parent_fitness"]) == parent_fitness, "terminal parent fitness mismatch")
        # Hash identity is checked by the caller using the canonical encoder.
        from .aggregate import canonical_sha256

        _require(state["parent_mask_sha256"] == canonical_sha256(parent),
                 "terminal parent mask mismatch")
        _require(state["tail_truncated"] is generations[-1]["tail_truncated"],
                 "terminal lambda tail mismatch")
    else:
        _require(state["final_distance"] == distance, "terminal CHC distance mismatch")
        _require(state["partial_population_update_skipped"] is
                 generations[-1]["partial_population_update_skipped"], "terminal CHC prefix mismatch")
