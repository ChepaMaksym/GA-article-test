"""Independent integer evaluator and RNG/controller replay of stored GA logs.

No production objective, comparison, selection or controller function is used.
This verifier is invoked only by CI drivers or CI unit tests.
"""

from __future__ import annotations

from copy import deepcopy
import hashlib
import json

import numpy as np

_CHANNEL_NAMES = ("initialization", "selection", "crossover", "mutation", "tie")
_REQUEST_KEYS = {"masks", "weight", "profit", "feasible", "request", "generation",
                 "phase", "duplicate", "parents", "tournaments",
                 "crossover_applied", "crossover_bits", "mutation_bits"}


def _require(value: bool, message: str) -> None:
    if not value:
        raise ValueError(message)


def _state_hash(value) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
        ensure_ascii=False, allow_nan=False).encode("utf-8")).hexdigest()


def _independent_evaluations(instance, masks) -> tuple[list[int], list[int], list[bool]]:
    profits, weights, feasible = [], [], []
    w, v = tuple(map(int, instance.weights)), tuple(map(int, instance.profits))
    _require(len(w) == len(v) == instance.n, "independent instance dimension mismatch")
    for row in masks:
        bits = row.tobytes()
        total_w = sum(item_w for bit, item_w in zip(bits, w) if bit)
        total_v = sum(item_v for bit, item_v in zip(bits, v) if bit)
        weights.append(total_w)
        profits.append(total_v)
        feasible.append(total_w <= instance.capacity)
    return weights, profits, feasible


def _population_statistics(refs, raw_masks, exact_profits, exact_feasible) -> dict:
    valid = [exact_profits[ref] for ref in refs if exact_feasible[ref]]
    return {"diversity": len({raw_masks[ref] for ref in refs}) / len(refs),
            "mean_feasible_profit": sum(valid) / len(valid) if valid else None,
            "feasible_fraction": len(valid) / len(refs)}


def verify_search(instance, config, result: dict, *, initial_center_profit: int | None = None,
                  initial_masks=None, initial_scores=None) -> dict:
    """Fail closed on any corrupted request, controller event or RNG state.

    The optional center threshold is held by this after-search verifier only.
    It is never passed to the genetic search kernel. One-based exit/request
    times include logical initial requests; event at budget is not censoring.
    """
    _require(set(result) == {"summary", "requests", "generations"}, "unexpected search result envelope")
    summary, rows, events = result["summary"], result["requests"], result["generations"]
    _require(set(rows) == _REQUEST_KEYS, "request schema mismatch")
    _require(all(isinstance(value, np.ndarray) and value.dtype.kind != "O" for value in rows.values()), "object/pickle arrays prohibited")
    count = int(summary["budget"])
    n, size = int(instance.n), int(config.population_size)
    _require(count >= size >= 2, "invalid run request bounds")
    expected_shapes = {"masks": (count, n), "parents": (count, 2),
                       "tournaments": (count, 2, 2),
                       "crossover_bits": (count, (n + 7) // 8),
                       "mutation_bits": (count, (n + 7) // 8)}
    dtypes = {"masks": np.dtype("uint8"), "weight": np.dtype("int64"),
              "profit": np.dtype("int64"), "feasible": np.dtype("bool"),
              "request": np.dtype("int32"), "generation": np.dtype("int32"),
              "phase": np.dtype("uint8"), "duplicate": np.dtype("bool"),
              "parents": np.dtype("int16"), "tournaments": np.dtype("int16"),
              "crossover_applied": np.dtype("bool"), "crossover_bits": np.dtype("uint8"),
              "mutation_bits": np.dtype("uint8")}
    for key, value in rows.items():
        _require(value.shape == expected_shapes.get(key, (count,)), f"wrong array shape: {key}")
        _require(value.dtype == dtypes[key], f"wrong array dtype: {key}")
    masks = rows["masks"]
    _require(np.all((masks == 0) | (masks == 1)), "nonbinary saved mask")
    _require(np.array_equal(rows["request"], np.arange(1, count + 1)), "nonconsecutive request indices")
    _require(np.all(rows["phase"][:size] == 0) and np.all(rows["phase"][size:] == 1), "initial/search phase boundary mismatch")
    _require(np.all(rows["generation"][:size] == 0), "initial request generation is not zero")
    _require(np.all(rows["parents"][:size] == -1) and np.all(rows["tournaments"][:size] == -1), "initial parent metadata must be absent")
    _require(not np.any(rows["crossover_applied"][:size]) and not np.any(rows["crossover_bits"][:size]) and not np.any(rows["mutation_bits"][:size]), "initial rows contain operator draws")
    exact_w, exact_v, exact_f = _independent_evaluations(instance, masks)
    for name, expected in (("weight", exact_w), ("profit", exact_v), ("feasible", exact_f)):
        _require(rows[name].tolist() == expected, f"independent exact {name} mismatch")
    if initial_masks is not None:
        _require(np.array_equal(masks[:size], initial_masks), "initial mask provenance mismatch")
    if initial_scores is not None:
        _require(set(initial_scores) == {"weight", "profit", "feasible"}, "known initial score schema mismatch")
        for key in initial_scores:
            _require(np.array_equal(rows[key][:size], initial_scores[key]), f"known initial score mismatch: {key}")
    raw_masks = [row.tobytes() for row in masks]
    seen, duplicates, best = set(), 0, None
    first_escape = None
    if initial_center_profit is not None:
        _require(isinstance(initial_center_profit, int) and not isinstance(initial_center_profit, bool), "center threshold must be exact integer")
        _require(all(exact_f[i] and exact_v[i] == initial_center_profit and raw_masks[i] == raw_masks[0] for i in range(size)), "local start is not known equal center clones")
    for ref, identity in enumerate(raw_masks):
        duplicate = identity in seen
        _require(bool(rows["duplicate"][ref]) == duplicate, f"duplicate ledger mismatch at {ref + 1}")
        seen.add(identity)
        duplicates += int(duplicate)
        if exact_f[ref] and (best is None or exact_v[ref] > exact_v[best]):
            best = ref
        if initial_center_profit is not None and first_escape is None and exact_f[ref] and exact_v[ref] > initial_center_profit:
            first_escape = ref + 1
    _require(isinstance(events, list) and len(events) >= 1, "missing generation checkpoints")
    first = events[0]
    expected_event_keys = {"generation", "complete", "first_request", "last_request",
                           "population_before", "population_after", "elite",
                           "metrics_before", "metrics_after", "rng_states", "rng_state_sha256"}
    _require(set(first) == expected_event_keys, "initial checkpoint schema mismatch")
    _require(first["generation"] == 0 and first["complete"] is True and first["first_request"] == 1 and first["last_request"] == size, "initial checkpoint bounds mismatch")
    population = list(range(size))
    _require(first["population_before"] == [] and first["population_after"] == population and first["elite"] is None and first["metrics_before"] is None, "initial checkpoint population mismatch")
    _require(first["metrics_after"] == _population_statistics(population, raw_masks, exact_v, exact_f), "initial population statistics mismatch")
    _require(set(first["rng_states"]) == set(_CHANNEL_NAMES), "five initial RNG states required")
    _require(first["rng_state_sha256"] == _state_hash(first["rng_states"]), "initial RNG state checksum mismatch")
    replay = {}
    for name in _CHANNEL_NAMES:
        state = first["rng_states"][name]
        _require(state.get("bit_generator") == "PCG64", "unregistered RNG generator")
        generator = np.random.Generator(np.random.PCG64(0))
        generator.bit_generator.state = deepcopy(state)
        replay[name] = generator
    cursor, complete_count, partial = size, 0, False
    for number, event in enumerate(events[1:], start=1):
        _require(set(event) == expected_event_keys, "generation checkpoint schema mismatch")
        _require(cursor < count and event["generation"] == number, "extra/nonconsecutive generation")
        _require(event["population_before"] == population and event["first_request"] == cursor + 1, "generation start references mismatch")
        old_population = population.copy()
        # Independent preference representation: feasible flag then profit,
        # otherwise negative violation. Infeasible profit is never used.
        preference = [(1, exact_v[ref]) if exact_f[ref] else
                      (0, -(exact_w[ref] - instance.capacity)) for ref in population]
        top = max(preference)
        tied_positions = [i for i in range(size) if preference[i] == top]
        selected_elite = tied_positions[int(replay["tie"].integers(0, len(tied_positions)))] if len(tied_positions) > 1 else tied_positions[0]
        elite_ref = population[selected_elite]
        _require(event["elite"] == {"population_index": selected_elite, "request_ref": elite_ref}, "elite replay mismatch")
        generated = []
        children = min(size - 1, count - cursor)
        for _ in range(children):
            ref = cursor
            parents = []
            for role in range(2):
                drawn = replay["selection"].integers(0, size, size=2).tolist()
                _require(rows["tournaments"][ref, role].tolist() == drawn, "tournament RNG draws mismatch")
                left, right = drawn
                if preference[left] == preference[right]:
                    winner = drawn[int(replay["tie"].integers(0, 2))]
                else:
                    winner = left if preference[left] > preference[right] else right
                parents.append(winner)
            _require(rows["parents"][ref].tolist() == parents, "tournament winner mismatch")
            crossover = bool(replay["crossover"].random() < config.crossover_probability)
            _require(bool(rows["crossover_applied"][ref]) == crossover, "crossover application replay mismatch")
            first_bits, second_bits = raw_masks[population[parents[0]]], raw_masks[population[parents[1]]]
            if crossover:
                choose_first = replay["crossover"].random(n) < 0.5
                predicted = bytearray(first_bits[i] if choose_first[i] else second_bits[i] for i in range(n))
                saved_choice = np.packbits(choose_first, bitorder="big")
            else:
                predicted = bytearray(first_bits)
                saved_choice = np.zeros((n + 7) // 8, dtype=np.uint8)
            _require(np.array_equal(rows["crossover_bits"][ref], saved_choice), "crossover bit draws/padding mismatch")
            mutations = replay["mutation"].random(n) < config.mutation_numerator / n
            _require(np.array_equal(rows["mutation_bits"][ref], np.packbits(mutations, bitorder="big")), "mutation bit draws/padding mismatch")
            for index in np.flatnonzero(mutations):
                predicted[int(index)] ^= 1
            _require(bytes(predicted) == raw_masks[ref], f"operator mask replay mismatch at {ref + 1}")
            _require(int(rows["generation"][ref]) == number, "offspring generation mismatch")
            generated.append(ref)
            cursor += 1
        completed = children == size - 1
        _require(event["complete"] is completed and event["last_request"] == cursor, "terminal generation completeness mismatch")
        if completed:
            population = [elite_ref] + generated
            complete_count += 1
        else:
            partial = True
        _require(event["population_after"] == population, "elite/replacement or partial population mismatch")
        _require(event["metrics_before"] == _population_statistics(old_population, raw_masks, exact_v, exact_f), "pre-generation population statistics mismatch")
        _require(event["metrics_after"] == _population_statistics(population, raw_masks, exact_v, exact_f), "post-generation population statistics mismatch")
        actual_states = {name: deepcopy(replay[name].bit_generator.state) for name in _CHANNEL_NAMES}
        _require(event["rng_states"] == actual_states, "generation RNG checkpoint mismatch")
        _require(event["rng_state_sha256"] == _state_hash(actual_states), "generation RNG checksum mismatch")
    _require(cursor == count, "missing final generation/candidate records")
    expected_summary = {"schema_version": "ga-knapsack-search-v1", "status": "COMPLETE",
        "mutation_numerator": float(config.mutation_numerator),
        "crossover_probability": float(config.crossover_probability), "population_size": size,
        "configuration_id": config.configuration_id, "n": n,
        "p_m": config.mutation_numerator / n, "p_c": config.crossover_probability, "N": size,
        "budget": count, "logical_requests": count, "physical_evaluations": count - size,
        "known_initial_requests": size, "complete_generations": complete_count,
        "terminal_partial": partial, "terminal_population_requests": population,
        "best_mask": "".join(str(bit) for bit in raw_masks[best]) if best is not None else None,
        "best_profit": exact_v[best] if best is not None else None,
        "best_weight": exact_w[best] if best is not None else None,
        "best_request": best + 1 if best is not None else None,
        "duplicate_count": duplicates, "invalid_request_count": sum(not value for value in exact_f),
        "rng_states_start": first["rng_states"], "rng_states_terminal": events[-1]["rng_states"],
        "rng_state_sha256_start": first["rng_state_sha256"],
        "rng_state_sha256_terminal": events[-1]["rng_state_sha256"]}
    _require(set(summary) == set(expected_summary), "search summary schema mismatch")
    for key, value in expected_summary.items():
        _require(summary[key] == value, f"independent summary mismatch: {key}")
    return {"status": "PASS_REPLAY", "logical_requests": count,
            "physical_evaluations": count - size,
            "best_mask": expected_summary["best_mask"], "best_profit": expected_summary["best_profit"],
            "best_weight": expected_summary["best_weight"], "best_request": expected_summary["best_request"],
            "duplicate_count": duplicates, "invalid_request_count": expected_summary["invalid_request_count"],
            "complete_generations": complete_count, "terminal_partial": partial,
            "escape_event": first_escape is not None if initial_center_profit is not None else None,
            "first_escape_request": first_escape,
            "escape_time": first_escape if first_escape is not None else count if initial_center_profit is not None else None,
            "censored": first_escape is None if initial_center_profit is not None else None,
            "exact_requests_verified": count, "rng_and_operator_replay_verified": True}
