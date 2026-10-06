"""Independent post-run checks of recorded QX evidence, without rerunning search.

This validator reconstructs deterministic ledger/state relationships only. It
does not refit trees, replay RNG, infer unrecorded CHC matings, or use diagnostics
to select a winner. Probability laws are tested by the separate CI unit tests;
the ledger proves only the recorded realization and scalar transitions.
"""
from __future__ import annotations

import math
from numbers import Integral, Real
from typing import Any, Mapping, Sequence


DIMENSION = 40
INITIAL_COUNT = 50
CHUNK_GENERATIONS = 10
NO_CHANGE_LIMIT = 2
MAX_CHUNKS = 20
ARMS = ("chc_qx", "lambda_adaptive_qx", "lambda_fixed1_qx")


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def _integer(value: Any, name: str, minimum: int = 0) -> int:
    _require(not isinstance(value, bool) and isinstance(value, Integral), f"{name}: integer required")
    result = int(value)
    _require(result >= minimum, f"{name}: integer below minimum")
    return result


def _number(value: Any, name: str, minimum: float = 0.0, maximum: float = 1.0) -> float:
    _require(not isinstance(value, bool) and isinstance(value, Real), f"{name}: scalar number required")
    result = float(value)
    _require(math.isfinite(result) and minimum <= result <= maximum,
             f"{name}: nonfinite or out-of-range scalar")
    return result


def _flag(value: Any, expected: bool, name: str) -> None:
    _require(isinstance(value, bool) and value is expected, f"{name}: boolean mismatch")


def _mask(value: Any) -> tuple[int, ...]:
    _require(isinstance(value, (tuple, list)) and len(value) == DIMENSION,
             "mask must contain 40 binary integers")
    _require(all(not isinstance(bit, bool) and isinstance(bit, Integral) and bit in (0, 1)
                 for bit in value), "mask contains a nonbinary integer")
    return tuple(map(int, value))


def _fitness(value: Any) -> float:
    _require(isinstance(value, (tuple, list)) and len(value) == 2,
             "recorded kernel fitness must have two components")
    primary = _number(value[0], "scalar WBA")
    _require(_number(value[1], "secondary fitness") == 0.0,
             "search success must not use feature-count fitness")
    return primary


def _same(value: Any, expected: Any, name: str) -> None:
    _require(value == expected, f"{name}: evidence does not match reconstructed state")


def _validate_lambda_generation(
    row: Mapping[str, Any], active: list[Any], *, parent: tuple[int, ...],
    parent_wba: float, lambda_before: float, offset: int, generation: int,
    arm: str,
) -> tuple[tuple[int, ...], float, float, int]:
    _same(_integer(row["generation"], "generation", 1), generation, "generation order")
    _same(_integer(row["chunk"], "generation chunk", 1), (generation-1)//CHUNK_GENERATIONS+1,
          "generation chunk")
    _same(_mask(row["parent_before"]), parent, "parent continuity")
    _same(_fitness(row["parent_fitness_before"]), parent_wba, "parent score continuity")
    _same(_number(row["lambda_before"], "lambda", 1.0, float(DIMENSION)), lambda_before,
          "lambda continuity")
    count = int(math.floor(lambda_before + 0.5))
    _same(_integer(row["offspring_count"], "offspring count", 1), count, "half-up offspring count")
    _same(_number(row["mutation_probability"], "mutation probability"), lambda_before/DIMENSION,
          "mutation probability")
    crossover_probability = 1.0/lambda_before
    _same(_number(row["crossover_probability"], "crossover probability"), crossover_probability,
          "crossover probability")
    strength = _integer(row["mutation_strength"], "mutation strength")
    _require(strength <= DIMENSION, "mutation strength exceeds dimension")
    if lambda_before == DIMENSION:
        _same(strength, DIMENSION, "p=1 mutation strength")
    _same(_integer(row["call_offset"], "call offset"), offset, "generation call offset")
    after = offset + 2*count
    _same(_integer(row["calls_after"], "calls after"), after, "complete generation calls")
    _same(_integer(row["objective_calls"], "objective calls"), 2*count, "generation query count")
    queries = active[offset:after]
    _require(len(queries) == 2*count, "incomplete mutation/crossover query ledger")
    mutants, crossovers = queries[:count], queries[count:]
    for child in mutants:
        _same(child["phase"], "mutation", "mutation query phase")
        _same(sum(a != b for a, b in zip(parent, _mask(child["mask"]))), strength,
              "shared exact mutation strength")
    selected = row["selection"]
    chosen_index = _integer(selected["selected_mutant_index"], "chosen mutant index")
    _require(chosen_index < count, "chosen mutant index outside pool")
    chosen = _mask(mutants[chosen_index]["mask"])
    chosen_wba = mutants[chosen_index]["wba"]
    _same(chosen_wba, max(child["wba"] for child in mutants), "chosen mutant maximizer")
    _same(_mask(selected["selected_mutant"]), chosen, "chosen mutant reuse")
    _same(_fitness(selected["selected_mutant_fitness"]), chosen_wba, "chosen mutant fitness")
    for child in crossovers:
        _same(child["phase"], "crossover", "crossover query phase")
        child_mask = _mask(child["mask"])
        _require(all(bit in (old, new) for bit, old, new in zip(child_mask, parent, chosen)),
                 "crossover has an allele absent from parent and chosen mutant")
        if crossover_probability == 1.0:
            _same(child_mask, chosen, "c=1 crossover must be the chosen mutant")
    pool = [(chosen, chosen_wba, "mutation", chosen_index)] + [
        (_mask(child["mask"]), child["wba"], "crossover", index)
        for index, child in enumerate(crossovers)
    ]
    eligible = [item for item in pool if item[0] != parent]
    _same(_integer(selected["eligible_count"], "eligible count"), len(eligible),
          "parent exclusion with nonparent duplicate multiplicities")
    candidate, candidate_wba = _mask(selected["candidate"]), _fitness(selected["candidate_fitness"])
    phase, index = selected["candidate_phase"], selected["candidate_phase_index"]
    if eligible:
        index = _integer(index, "candidate phase index")
        _require((candidate, candidate_wba, phase, index) in eligible,
                 "final candidate is not the recorded chosen-mutant/crossover pool member")
        _same(candidate_wba, max(item[1] for item in eligible), "final candidate maximizer")
    else:
        _same((candidate, candidate_wba, phase, index), (parent, parent_wba, "parent", None),
              "empty eligible pool fallback")
    success, accepted = candidate_wba > parent_wba, candidate_wba >= parent_wba
    _flag(row["strict_success"], success, "strict scalar success")
    _flag(row["accepted"], accepted, "non-strict scalar acceptance")
    next_parent, next_score = (candidate, candidate_wba) if accepted else (parent, parent_wba)
    _same(_mask(row["parent_after"]), next_parent, "accepted parent transition")
    _same(_fitness(row["parent_fitness_after"]), next_score, "accepted parent score")
    _flag(row["parent_changed"], next_parent != parent, "parent change")
    _flag(row["reset_event"], False, "reset must remain disabled")
    proposed = max(1.0, lambda_before/1.5) if success else min(
        float(DIMENSION), lambda_before*1.5**0.25,
    )
    _same(_number(row["proposed_lambda_after"], "proposed lambda", 1.0, float(DIMENSION)),
          proposed, "adaptive proposal")
    applied = proposed if arm == "lambda_adaptive_qx" else 1.0
    for name in ("applied_lambda_after", "lambda_after"):
        _same(_number(row[name], name, 1.0, float(DIMENSION)), applied, name)
    first_gain = next((query["call"] for query in queries if query["wba"] > parent_wba), None)
    _same(row["first_strict_improvement_call"], first_gain, "first improving objective query")
    _same(row["accepted_at_call"], after if accepted and eligible else None, "acceptance query")
    return next_parent, next_score, applied, after


def _validate_search(trace: Mapping[str, Any], initial_masks: Sequence[Any],
                     initial_scores: Sequence[Any]) -> None:
    _same(trace["schema"], "eu26-21-chc-qx-search-v1", "search schema")
    arm = trace["arm"]
    _require(arm in ARMS, "unknown search arm")
    seed = _integer(trace["seed"], "case seed", 44001)
    _require(seed <= 44030, "case seed outside preregistered campaign")
    _same(_integer(trace["search_seed"], "search seed"), seed+1000003, "search RNG identity")
    _flag(trace["reset"], False, "reset")
    _flag(trace["equal_objective_budget"], False, "unequal objective-cost disclosure")
    masks, scores = list(map(_mask, initial_masks)), [
        _number(score, "initial WBA") for score in initial_scores
    ]
    _require(len(masks) == INITIAL_COUNT and len(scores) == INITIAL_COUNT,
             "exactly 50 frozen ordered initial masks/scores required")
    active, full, checkpoints, generations = [trace[key] for key in (
        "active_trace", "full_evaluations", "checkpoints", "generation_trace",
    )]
    _require(all(isinstance(rows, list) for rows in (active, full, checkpoints, generations)),
             "query and state ledgers must be lists")
    _require(len(active) >= INITIAL_COUNT, "missing initial logical calls")
    observed: dict[tuple[int, ...], float] = {}
    first_observed: dict[tuple[int, ...], int] = {}
    best_active = 0.0
    for call, query in enumerate(active, 1):
        mask, score = _mask(query["mask"]), _number(query["wba"], "active WBA")
        _same(_integer(query["call"], "active call", 1), call, "contiguous active call numbering")
        _require(mask not in observed or observed[mask] == score,
                 "duplicate active mask has conflicting deterministic WBA")
        _require(any(mask) or score == 0.0, "empty feature mask has a nonzero active score")
        observed[mask] = score
        first_observed.setdefault(mask, call)
        best_active = max(best_active, score)
        _same(_number(query["best_so_far_wba"], "best active WBA"), best_active,
              "best-so-far active trajectory")
        initial = call <= INITIAL_COUNT
        _flag(query["physical"], not initial, "physical/logical initialization accounting")
        if initial:
            _same((mask, score, query["phase"], query["chunk"]),
                  (masks[call-1], scores[call-1], "initial_replay", 0), "frozen ordered initialization")
        else:
            _require(query["phase"] in (("chc_offspring",) if arm == "chc_qx" else ("mutation", "crossover")),
                     "unexpected active evaluation phase")
            _integer(query["chunk"], "active query chunk", 1)
    _same(_integer(trace["active_logical_calls"], "active logical calls"), len(active), "active logical total")
    _same(_integer(trace["active_physical_calls"], "active physical calls"), len(active)-INITIAL_COUNT,
          "active physical total")
    _same(_integer(trace["initial_logical_calls"], "initial logical calls"), INITIAL_COUNT, "initial logical total")
    _same(_integer(trace["initial_physical_calls"], "initial physical calls"), 0, "initial physical total")
    chunks = _integer(trace["chunks"], "completed chunks", 1)
    _require(chunks <= MAX_CHUNKS and len(checkpoints) == chunks, "invalid checkpoint completeness")
    terminal = trace["terminal_state"]
    _same(_integer(terminal["generation_count"], "terminal generations"), chunks*CHUNK_GENERATIONS,
          "only whole 10-generation chunks permitted")
    if arm == "chc_qx":
        _same(len(generations), chunks, "native CHC chunk ledger completeness")
        _same(terminal["initial_parent_index"], None, "CHC has no lambda parent index")
        for name in ("parent_mask", "parent_active_wba", "final_lambda"):
            _same(terminal[name], None, f"CHC terminal {name}")
        parent, parent_wba, lambda_value = None, None, None
    else:
        _same(len(generations), chunks*CHUNK_GENERATIONS, "lambda complete generation ledger")
        parent_index = _integer(terminal["initial_parent_index"], "initial parent index")
        _require(parent_index < INITIAL_COUNT and scores[parent_index] == max(scores),
                 "initial lambda parent must maximize scalar WBA")
        parent, parent_wba, lambda_value = masks[parent_index], scores[parent_index], 1.0
        _same(terminal["population"], [], "lambda checkpoint must not fabricate CHC population")
        _same(terminal["final_distance"], None, "lambda has no CHC distance")
    full_cache: dict[tuple[int, ...], tuple[float, int]] = {}
    selected, selected_call, best_full = None, None, 0.0
    no_change = visits_total = full_cursor = 0
    active_cursor, distance = INITIAL_COUNT, DIMENSION//4
    expected_snapshot = last_snapshot = None
    for chunk, checkpoint in enumerate(checkpoints, 1):
        _same(_integer(checkpoint["chunk"], "checkpoint chunk", 1), chunk, "checkpoint order")
        _same(_integer(checkpoint["generation"], "checkpoint generation"), chunk*CHUNK_GENERATIONS,
              "native checkpoint cadence")
        before = active[active_cursor-1]["best_so_far_wba"]
        if arm == "chc_qx":
            row = generations[chunk-1]
            _same(row["phase"], "native_chc_chunk", "native source CHC identity")
            _same(_integer(row["chunk"], "native chunk", 1), chunk, "native CHC chunk order")
            _same(_integer(row["generation"], "native generations"), chunk*CHUNK_GENERATIONS, "native CHC generations")
            _same(_integer(row["completed_generations"], "completed native generations"),
                  CHUNK_GENERATIONS, "native CHC whole chunk")
            _same(_integer(row["calls_before"], "native call offset"), active_cursor, "native CHC call offset")
            _same(_integer(row["distance_before"], "native distance before"), distance, "persistent CHC distance")
            distance = _integer(row["distance_after"], "CHC distance")
            _require(distance <= DIMENSION//4, "CHC distance exceeds source restart threshold")
            active_cursor = _integer(row["calls_after"], "native calls after", active_cursor)
            _require(active_cursor <= len(active), "CHC calls exceed ledger")
            _same(row["best_active_before"], before, "native chunk best before")
            _same(row["best_active_after"], active[active_cursor-1]["best_so_far_wba"], "native chunk best after")
        else:
            for generation in range((chunk-1)*CHUNK_GENERATIONS+1, chunk*CHUNK_GENERATIONS+1):
                parent, parent_wba, lambda_value, active_cursor = _validate_lambda_generation(
                    generations[generation-1], active, parent=parent, parent_wba=parent_wba,
                    lambda_before=lambda_value, offset=active_cursor, generation=generation, arm=arm,
                )
        after = active[active_cursor-1]["best_so_far_wba"]
        offset = INITIAL_COUNT if chunk == 1 else checkpoints[chunk-2]["active_logical_calls"]
        _require(all(query["chunk"] == chunk for query in active[offset:active_cursor]),
                 "active query assigned to wrong native chunk")
        _same(checkpoint["best_active_before"], before, "checkpoint active best before")
        _same(checkpoint["best_active"], after, "checkpoint active best after")
        _same(_integer(checkpoint["active_logical_calls"], "checkpoint logical calls"),
              active_cursor, "checkpoint logical query count")
        _same(_integer(checkpoint["active_physical_calls"], "checkpoint physical calls"),
              active_cursor-INITIAL_COUNT, "checkpoint physical query count")
        candidates = checkpoint["candidate_visits"]
        _require(isinstance(candidates, list) and len(candidates) == (INITIAL_COUNT if arm == "chc_qx" else 1),
                 "checkpoint must expose current CHC population or single lambda parent")
        candidate_masks = [_mask(visit["mask"]) for visit in candidates]
        _require(all(mask in first_observed and first_observed[mask] <= active_cursor for mask in candidate_masks),
                 "checkpoint mask lacks prior active objective evidence")
        if arm == "chc_qx":
            # No mating/population journal exists inside native source CHC. This
            # verifies candidate scores and center, not unrecorded selection.
            candidate_scores = [observed[mask] for mask in candidate_masks]
            center_index = candidate_scores.index(max(candidate_scores))
            center, center_score = candidate_masks[center_index], candidate_scores[center_index]
        else:
            _same(candidate_masks, [parent], "lambda checkpoint parent identity")
            center, center_score = parent, parent_wba
        last_snapshot = {
            "mask": list(center), "active_wba": center_score, "chunk": chunk,
            "generation": chunk*CHUNK_GENERATIONS, "whole_chunk_generations": CHUNK_GENERATIONS,
            "best_active_before": before, "best_active_after": after,
            "reason": "stagnation_not_observed",
        }
        if expected_snapshot is None and after <= before:
            expected_snapshot = {**last_snapshot, "reason": "first_whole_chunk_without_active_gain"}
        no_change += 1
        previous_full = full_cursor
        for visit, mask in zip(candidates, candidate_masks):
            visits_total += 1
            score = _number(visit["wba"], "checkpoint full WBA")
            _require(any(mask) or score == 0.0, "empty feature mask has a nonzero full score")
            cache_hit = mask in full_cache
            _flag(visit["cache_hit"], cache_hit, "persistent full-mask cache")
            if not cache_hit:
                _require(full_cursor < len(full), "missing full objective query")
                query = full[full_cursor]
                full_cursor += 1
                _same(_integer(query["call"], "full call", 1), full_cursor, "contiguous full call numbering")
                _same(_mask(query["mask"]), mask, "full query mask follows checkpoint visit")
                _same(_number(query["wba"], "full WBA"), score, "full query scalar score")
                _same(query["phase"], "full_checkpoint", "full objective scope")
                _same(query["chunk"], chunk, "full query checkpoint")
                full_cache[mask] = score, full_cursor
            cached_score, full_call = full_cache[mask]
            _same(score, cached_score, "cached full score")
            _same(_integer(visit["full_call"], "visit full call", 1), full_call, "cached full call identity")
            strict_gain = score > best_full
            _flag(visit["strict_full_gain"], strict_gain, "strict full checkpoint gain")
            if strict_gain:
                selected, selected_call, best_full = mask, full_call, score
                no_change = 0
            elif selected is not None and score == best_full and (sum(mask), full_call) < (sum(selected), selected_call):
                selected, selected_call = mask, full_call
        _same(_number(checkpoint["best_full"], "checkpoint best full WBA"), best_full, "checkpoint best full WBA")
        for name, expected in (("no_change", no_change), ("full_calls", full_cursor),
                               ("new_full_calls", full_cursor-previous_full),
                               ("checkpoint_visits", visits_total)):
            _same(_integer(checkpoint[name], name), expected, f"checkpoint {name}")
        _require(chunk == chunks or no_change < NO_CHANGE_LIMIT,
                 "recorded search continued after the natural source stop")
    _same(active_cursor, len(active), "no trailing active query outside whole chunks")
    _same(full_cursor, len(full), "no initial/control/trailing full query outside checkpoints")
    _same(_integer(trace["full_calls"], "full total"), full_cursor, "full total")
    _same(_integer(trace["checkpoint_visits"], "visit total"), visits_total, "checkpoint visit total")
    _same(trace["snapshot"], expected_snapshot if expected_snapshot is not None else last_snapshot,
          "first complete no-gain chunk snapshot or explicitly labeled terminal snapshot")
    _same(_integer(terminal["no_change"], "terminal no change"), no_change, "terminal no change")
    for name, expected in (("best_active_wba", best_active),
                           ("best_full_wba", best_full), ("selected_full_call", selected_call)):
        _same(terminal[name], expected, f"terminal {name}")
    if arm == "chc_qx":
        _same(terminal["final_distance"], distance, "terminal CHC distance")
        _same(len(terminal["population"]), INITIAL_COUNT, "terminal CHC population size")
        _same([_mask(row["mask"]) for row in terminal["population"]], candidate_masks,
              "terminal CHC current population")
        for row, mask in zip(terminal["population"], candidate_masks):
            _same(_number(row["active_wba"], "terminal population WBA"), observed[mask],
                  "terminal active population score")
    else:
        _same(_mask(terminal["parent_mask"]), parent, "terminal parent")
        _same(terminal["parent_active_wba"], parent_wba, "terminal parent active score")
        _same(terminal["final_lambda"], lambda_value, "terminal persistent lambda")
    stop = "full_no_change" if no_change >= NO_CHANGE_LIMIT else "censored_safety_cap"
    _require(stop != "censored_safety_cap" or chunks == MAX_CHUNKS,
             "safety censoring before the preregistered 20-chunk cap")
    _same(terminal["outer_stop_reason"], stop, "natural stop priority at safety cap")
    missing = selected is None
    _same(trace["status"], "no_full_winner" if missing else "evaluable", "winner status")
    _same(trace["stop_reason"], "no_full_winner" if missing else stop, "reported stop reason")
    _same(trace["selected_mask"], None if missing else list(selected), "terminal full-objective mask")
    _same(trace["full_validation_wba"], None if missing else best_full, "terminal full validation WBA")


def validate_search(trace: Mapping[str, Any], initial_masks: Sequence[Any],
                    initial_scores: Sequence[Any]) -> None:
    """Reject malformed or inconsistent preregistered search evidence."""
    try:
        _validate_search(trace, initial_masks, initial_scores)
    except (KeyError, TypeError, IndexError, AttributeError, OverflowError) as error:
        raise ValueError(f"malformed search evidence: {error}") from error


def _validate_diagnostic(diag: Mapping[str, Any], snapshot: Mapping[str, Any]) -> None:
    _same(diag["schema"], "eu26-21-chc-qx-diagnostic-v1", "diagnostic schema")
    center = _mask(snapshot["mask"])
    _same(_mask(diag["center_mask"]), center, "diagnostic center mask")
    _same(diag["snapshot"], snapshot, "diagnostic frozen snapshot")
    _flag(diag["independent_center_reevaluation"], True, "independent center reevaluation")
    for name in ("feed_back_to_search", "two_bit_audit", "controlled_escape"):
        _flag(diag[name], False, name)
    for name in ("active_objective_calls", "full_objective_calls"):
        _same(_integer(diag[name], name), DIMENSION+1, name)
    _same(_integer(diag["objective_calls"], "diagnostic calls"), 2*(DIMENSION+1), "total diagnostic calls")
    local_flags = []
    for name, scope in (("approximate", "active_training_validation_WBA"),
                        ("full", "full_internal_training_validation_WBA")):
        certificate = diag[name]
        _same(certificate["scope"], scope, "diagnostic objective scope")
        _same(_number(certificate["numerical_tolerance"], "numerical tolerance"), 0.0,
              "zero local comparison tolerance")
        _same(_integer(certificate["objective_calls"], "certificate calls"), DIMENSION+1,
              "certificate calls")
        for claim in ("global_optimality", "non_globality"):
            _same(certificate[claim], "not_assessed", "one-bit audit must not imply a global claim")
        evaluations = certificate["evaluations"]
        _require(isinstance(evaluations, list) and len(evaluations) == DIMENSION+1,
                 "certificate requires an independent center and all 40 ordered neighbors")
        center_wba = _number(certificate["center_wba"], "diagnostic center WBA")
        if name == "approximate":
            _same(center_wba, _number(snapshot["active_wba"], "frozen active center WBA"),
                  "independent active center reproduces the frozen score")
        first = evaluations[0]
        _same((_integer(first["call"], "center call", 1), first["bit"],
               _mask(first["mask"]), _number(first["wba"], "independent center WBA")),
              (1, None, center, center_wba), "independent center query")
        higher = equal = lower = 0
        for bit, query in enumerate(evaluations[1:]):
            neighbor = list(center)
            neighbor[bit] = 1-neighbor[bit]
            _same(_integer(query["call"], "diagnostic call", 1), bit+2, "ordered diagnostic calls")
            _same(_integer(query["bit"], "diagnostic bit"), bit, "ascending bit audit")
            _same(_mask(query["mask"]), tuple(neighbor), "exact one-bit neighbor")
            score = _number(query["wba"], "neighbor WBA")
            relation = "higher" if score > center_wba else "equal" if score == center_wba else "lower"
            _same(_number(query["difference_from_center"], "neighbor difference", -1.0, 1.0),
                  score-center_wba, "neighbor difference")
            _same(query["relation"], relation, "zero-tolerance neighbor comparison")
            higher += int(relation == "higher")
            equal += int(relation == "equal")
            lower += int(relation == "lower")
        local = higher == 0
        for flag, expected in (("local_maximum", local), ("strict_local_maximum", local and equal == 0),
                               ("plateau_local_maximum", local and equal > 0)):
            _flag(certificate[flag], expected, f"{name} {flag}")
        for count, expected in (("higher_neighbors", higher), ("equal_neighbors", equal), ("lower_neighbors", lower)):
            _same(_integer(certificate[count], count), expected, f"{name} {count}")
        local_flags.append(local)
    classification = {
        (False, False): "neither_local", (True, False): "approximate_only_false_local",
        (True, True): "both_local", (False, True): "full_only_local",
    }[tuple(local_flags)]
    _same(diag["classification"], classification, "approximate/full local classification")


def validate_diagnostic(diag: Mapping[str, Any], snapshot: Mapping[str, Any]) -> None:
    """Independently reconstruct local certificates from their recorded rows."""
    try:
        _validate_diagnostic(diag, snapshot)
    except (KeyError, TypeError, IndexError, AttributeError, OverflowError) as error:
        raise ValueError(f"malformed diagnostic evidence: {error}") from error
