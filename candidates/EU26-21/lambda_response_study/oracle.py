"""Independent scalar-event oracle: no production update or operator imports."""
from __future__ import annotations

import math
from numbers import Integral, Real

import numpy as np

TOL = 1e-12

def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)

def close(first: float, second: float) -> bool:
    return math.isclose(first, second, rel_tol=TOL, abs_tol=TOL)

def score(value) -> float:
    require(not isinstance(value, bool) and isinstance(value, Real)
            and math.isfinite(float(value)) and 0 <= float(value) <= 1, "score must be finite scalar in [0,1]")
    return float(value)

def mask(value) -> tuple:
    require(len(value) == 40 and all(not isinstance(bit, bool) and isinstance(bit, Integral)
                                   and bit in (0, 1) for bit in value), "forty binary integer bits required")
    return tuple(int(bit) for bit in value)

def expected_lambda(before: float, *, strict_success: bool, arm: str) -> float:
    require(not isinstance(before, bool) and isinstance(before, Real)
            and math.isfinite(float(before)) and 1 <= before <= 40
            and type(strict_success) is bool and arm in ("adaptive", "fixed10"), "invalid lambda event")
    if arm == "fixed10":
        require(before == 10, "fixed lambda drifted")
        return 10.0
    return max(1.0, before / 1.5) if strict_success else min(40.0, before * math.pow(1.5, 0.25))

def replay_generation(rng, *, parent, event, rows, m, p, c) -> None:
    """Replay the published random operations without importing the kernel."""
    strength = int(rng.binomial(40, p))
    require(event["mutation_strength"] == strength, "binomial draw differs from registered RNG")
    for row in rows[:m]:
        positions = [] if strength == 0 else rng.choice(40, size=strength, replace=False).tolist()
        child = list(parent)
        for position in positions:
            child[position] = 1 - child[position]
        require(row["mask"] == child, "mutation differs from registered random tape")
    maximum = max(row["score"] for row in rows[:m])
    tied = np.asarray([i for i, row in enumerate(rows[:m]) if row["score"] == maximum], dtype=int)
    chosen_index = int(rng.choice(tied))
    require(event["selected_mutant_index"] == chosen_index, "mutant was selected again or wrong tie draw")
    chosen = rows[chosen_index]
    for row in rows[m:]:
        take = rng.random(40) < c
        child = [chosen["mask"][i] if take[i] else parent[i] for i in range(40)]
        require(row["mask"] == child, "crossover differs from registered random tape")
    eligible = [row for row in [chosen] + rows[m:] if tuple(row["mask"]) != parent]
    if eligible:
        maximum = max(row["score"] for row in eligible)
        tied = np.asarray([i for i, row in enumerate(eligible) if row["score"] == maximum], dtype=int)
        candidate = eligible[int(rng.choice(tied))]
        require(event["candidate_mask"] == candidate["mask"]
                and event["candidate_phase"] == candidate["phase"]
                and event["candidate_phase_index"] == candidate["phase_index"], "final tie draw differs")
    require(event["RNG_state_after"] == rng.bit_generator.state, "terminal RNG state differs from replay")

def validate_trace(trace: dict) -> dict:
    require(trace["schema"] == "eu26-21-lambda-response-search-v1", "wrong trace schema")
    problem, arm = trace["problem"], trace["arm"]
    require(problem in ("onemax", "census") and arm in ("adaptive", "fixed10"), "wrong problem/arm")
    parent, parent_score = mask(trace["initial"]["mask"]), score(trace["initial"]["score"])
    require(trace["initial"]["lambda"] == 10 and trace["initial"]["call"] == 0, "initial state invalid")
    if problem == "onemax":
        require(sum(parent) == 0 and parent_score == 0, "OneMax must start at actual zero fitness")
    else:
        require(sum(parent) == 1, "Census starts from one real feature")
    evaluations, generations = trace["evaluations"], trace["generation_trace"]
    require(len(generations) == 20 and len(evaluations) <= 1600, "twenty full generations required")
    lam, cursor, best = 10.0, 0, parent_score
    known, observed, residuals = {parent: parent_score}, set(), []
    previous_rng = trace["rng_initial_state"]
    require(type(trace["search_seed"]) is int and trace["search_seed"] >= 0, "invalid search seed")
    rng = np.random.default_rng(trace["search_seed"])
    require(previous_rng == rng.bit_generator.state, "initial RNG state does not match seed")
    for number, event in enumerate(generations, 1):
        require(type(event["generation"]) is int and type(event["calls_before"]) is int
                and type(event["calls_after"]) is int and type(event["offspring_count"]) is int,
                "generation counters must be integer, not boolean")
        require(event["generation"] == number and event["calls_before"] == cursor
                and event["parent_before"] == list(parent)
                and event["parent_score_before"] == parent_score
                and event["lambda_before"] == lam
                and event["RNG_state_before"] == previous_rng, "broken state continuity")
        m, p, c = math.floor(lam + 0.5), lam / 40, 1 / lam
        require(event["offspring_count"] == m and close(event["mutation_probability"], p)
                and close(event["crossover_probability"], c)
                and event["calls_after"] == cursor + 2 * m, "incomplete generation or wrong controls")
        rows = evaluations[cursor:cursor + 2 * m]
        require(len(rows) == 2 * m and type(event["mutation_strength"]) is int
                and 0 <= event["mutation_strength"] <= 40, "generation ledger incomplete")
        for offset, row in enumerate(rows):
            child, value = mask(row["mask"]), score(row["score"])
            require(type(row["call"]) is int and type(row["generation"]) is int
                    and type(row["phase_index"]) is int and type(row["feature_count"]) is int,
                    "evaluation counters must be integer, not boolean")
            require(row["call"] == cursor + offset + 1 and row["generation"] == number
                    and row["phase"] == ("mutation" if offset < m else "crossover")
                    and row["phase_index"] == offset % m
                    and row["feature_count"] == sum(child), "raw ledger chronology or mask invalid")
            kind = "onemax" if problem == "onemax" else ("classification" if sum(child) else "empty_penalty")
            require(row["kind"] == kind, "empty penalty confused with measured accuracy")
            if problem == "onemax":
                require(value == sum(child) / 40, "OneMax score mismatch")
            elif not sum(child):
                require(value == 0, "empty-mask penalty mismatch")
            require(child not in known or known[child] == value, "deterministic objective changed")
            known[child] = value
            observed.add(child)
            best = max(best, value)
            require(row["best_so_far_score"] == best, "record curve hides or changes evaluations")
            if offset < m:
                require(sum(a != b for a, b in zip(child, parent)) == event["mutation_strength"],
                        "mutation did not use common exact strength")
        index = event["selected_mutant_index"]
        require(type(index) is int and 0 <= index < m, "chosen mutant index invalid")
        chosen = rows[index]
        require(chosen["score"] == max(r["score"] for r in rows[:m])
                and event["selected_mutant_mask"] == chosen["mask"]
                and event["selected_mutant_score"] == chosen["score"], "selected mutant changed")
        for row in rows[m:]:
            require(all(bit in (a, b) for bit, a, b in zip(row["mask"], parent, chosen["mask"])),
                    "crossover introduced an unrelated bit")
        pool = [chosen] + rows[m:]
        eligible = [r for r in pool if tuple(r["mask"]) != parent]
        candidate, candidate_score = mask(event["candidate_mask"]), score(event["candidate_score"])
        require(event["eligible_count"] == len(eligible), "candidate multiplicities changed")
        if eligible:
            require(any(r["mask"] == list(candidate) and r["score"] == candidate_score
                        and r["phase"] == event["candidate_phase"]
                        and r["phase_index"] == event["candidate_phase_index"] for r in eligible)
                    and candidate_score == max(r["score"] for r in eligible), "incorrect final candidate")
        else:
            require(candidate == parent and candidate_score == parent_score
                    and event["candidate_phase"] == "parent" and event["candidate_phase_index"] is None,
                    "all-parent fallback incorrect")
        replay_generation(rng, parent=parent, event=event, rows=rows, m=m, p=p, c=c)
        success, accepted = candidate_score > parent_score, candidate_score >= parent_score
        expected = expected_lambda(lam, strict_success=success, arm=arm)
        applied = event["applied_lambda_after"]
        require(not isinstance(applied, bool) and isinstance(applied, Real)
                and math.isfinite(float(applied)) and 1 <= applied <= 40, "invalid applied lambda")
        residual = applied - expected
        residuals.append(abs(residual))
        proposal = max(1, lam / 1.5) if success else min(40, lam * math.pow(1.5, 0.25))
        require(type(event["strict_success"]) is bool and event["strict_success"] == success
                and type(event["accepted"]) is bool and event["accepted"] == accepted
                and event["reset_event"] is False and close(event["proposed_lambda_after"], proposal),
                "success, acceptance or proposal invalid")
        require(close(applied, expected) and close(event["expected_lambda_after"], expected)
                and close(event["lambda_residual"], residual), "lambda model mismatch")
        require(close(event["score_delta_pp"], 100 * (candidate_score - parent_score))
                and close(event["lambda_delta_percent"], 100 * (applied / lam - 1)), "percent units mixed")
        after_parent, after_score = (candidate, candidate_score) if accepted else (parent, parent_score)
        require(event["parent_after"] == list(after_parent) and event["parent_score_after"] == after_score
                and event["parent_changed"] == (after_parent != parent), "acceptance state mismatch")
        parent, parent_score, lam = after_parent, after_score, applied
        previous_rng = event["RNG_state_after"]
        cursor += 2 * m
    require(cursor == len(evaluations) and trace["final"] == {"mask": list(parent), "score": parent_score, "lambda": lam}
            and trace["rng_final_state"] == previous_rng, "terminal state mismatch")
    if arm == "fixed10":
        require(cursor == 400, "fixed10 must perform 400 calls")
    tree_fits = sum(bool(sum(r["mask"])) for r in evaluations) if problem == "census" else 0
    require(all(type(value) is int for value in trace["counts"].values()), "physical counters must be integers")
    require(trace["counts"] == {"physical_calls": cursor, "actual_tree_fits": tree_fits,
                               "unique_masks": len(observed), "duplicate_queries": cursor - len(observed)},
            "physical counters mismatch")
    result = {"generation_count": 20, "mismatches": 0, "max_abs_residual": max(residuals, default=0)}
    require(trace["model_check"] == result, "model-check summary inconsistent")
    return result
