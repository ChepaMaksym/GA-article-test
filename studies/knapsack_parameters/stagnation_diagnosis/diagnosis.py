"""Post-search records, exact radius-two certificates and independent audit.

The search kernel imports none of this module. No exact solver or production
selection/evaluation routine is used here. Execution is restricted to CI.
"""

from __future__ import annotations

import hashlib
import itertools
import json
import math

import numpy as np

CHECKPOINTS = (0, 1000, 2500, 5000)
THRESHOLD = 1000
STATES = ("N2_NOT_LOCAL", "N2_STRICT_NONGLOBAL",
          "N2_NONSTRICT_NONGLOBAL", "GLOBAL_OPTIMUM")


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False).encode("utf-8")


def _source(instance):
    return {"n": int(instance.n), "capacity": int(instance.capacity),
            "weights": [int(x) for x in instance.weights],
            "profits": [int(x) for x in instance.profits],
            "source_path": str(getattr(instance, "source_path", "")),
            "class_label": str(getattr(instance, "class_label", "")),
            "family": str(getattr(instance, "family", "")),
            "index": int(getattr(instance, "index", 0))}


def _text(mask):
    return "".join(str(int(bit)) for bit in mask)


def _sums(instance, bits):
    return (sum(int(w) for w, bit in zip(instance.weights, bits) if bit),
            sum(int(v) for v, bit in zip(instance.profits, bits) if bit))


def _extract(instance, result, optimum, checkpoints, threshold):
    if not isinstance(optimum, int) or isinstance(optimum, bool) or optimum < 0:
        raise ValueError("exact optimum must be a nonnegative integer")
    if not isinstance(threshold, int) or isinstance(threshold, bool) or threshold < 1:
        raise ValueError("positive integer stagnation threshold required")
    if (not checkpoints or any(not isinstance(q, int) or isinstance(q, bool) or q < 0
                               for q in checkpoints)
            or tuple(sorted(set(checkpoints))) != tuple(checkpoints)):
        raise ValueError("ordered distinct nonnegative checkpoints required")
    requests, summary = result["requests"], result["summary"]
    masks = np.asarray(requests["masks"])
    if masks.ndim != 2 or masks.shape[1] != instance.n or not np.all((masks == 0) | (masks == 1)):
        raise ValueError("request masks have wrong shape or nonbinary bits")
    count = len(masks)
    size = summary["known_initial_requests"]
    if not isinstance(size, int) or isinstance(size, bool) or not 2 <= size <= count:
        raise ValueError("invalid known initial population size")
    if any(summary.get(key, expected) != expected for key, expected in (
            ("logical_requests", count), ("budget", count),
            ("population_size", size), ("N", size),
            ("physical_evaluations", count - size))):
        raise ValueError("request accounting differs from recorded arrays")
    if checkpoints[-1] > count - size:
        raise ValueError("checkpoint exceeds evaluated prefix")
    for key in ("weight", "profit", "feasible"):
        if np.asarray(requests[key]).shape != (count,):
            raise ValueError("request score dimension mismatch")
    if any(np.asarray(requests[key]).dtype.kind not in "iu" for key in ("weight", "profit")):
        raise ValueError("request objective scores must be integer")
    if np.asarray(requests["feasible"]).dtype.kind != "b":
        raise ValueError("request feasibility must be Boolean")
    return requests, masks, size, count


def _timeline(result, size, count):
    """Validate committed references without evaluating selection/operators."""
    generations = result["generations"]
    if not generations or generations[0]["generation"] != 0:
        raise ValueError("initial generation is missing")
    initial = generations[0]
    population = list(range(size))
    if (initial["complete"] is not True or initial["first_request"] != 1
            or initial["last_request"] != size
            or initial["population_before"] != []
            or initial["population_after"] != population):
        raise ValueError("initial population provenance mismatch")
    committed = [(0, population.copy())]
    endpoints = [(0, True, population.copy())]
    used = size
    for ordinal, generation in enumerate(generations[1:], 1):
        if (generation["generation"] != ordinal
                or generation["first_request"] != used + 1
                or generation["population_before"] != population):
            raise ValueError("noncontiguous generation or wrong prior population")
        end = generation["last_request"]
        if not isinstance(end, int) or isinstance(end, bool) or not used < end <= count:
            raise ValueError("invalid generation request range")
        offspring = list(range(used, end))
        complete = len(offspring) == size - 1
        if len(offspring) > size - 1 or generation["complete"] is not complete:
            raise ValueError("incorrect completed-generation flag")
        if not complete and ordinal != len(generations) - 1:
            raise ValueError("incomplete generation must be terminal")
        elite = generation["elite"]
        position = elite["population_index"]
        if not isinstance(position, int) or isinstance(position, bool) or not 0 <= position < size:
            raise ValueError("elite position outside current population")
        if elite["request_ref"] != population[position]:
            raise ValueError("elite reference does not identify current population")
        if complete:
            population = [population[position]] + offspring
            committed.append((end - size, population.copy()))
        if generation["population_after"] != population:
            raise ValueError("future or incorrectly applied generation population")
        endpoints.append((end - size, complete, population.copy()))
        used = end
    if used != count:
        raise ValueError("generation evidence does not cover all requests")
    if result["summary"].get("terminal_population_requests", population) != population:
        raise ValueError("terminal population disagrees with reconstruction")
    return committed, endpoints


def _metrics(masks, requests, refs):
    selected = masks[refs]
    length = len(refs)
    counts = selected.astype(np.int64).sum(axis=0)
    diversity = (float(sum(int(c) * (length - int(c)) for c in counts))
                 / (length * (length - 1) / 2))
    acceptable = [int(requests["profit"][ref]) for ref in refs if requests["feasible"][ref]]
    return {"unique_fraction": len({row.tobytes() for row in selected}) / length,
            "mean_pairwise_hamming": diversity,
            "mean_feasible_profit": sum(acceptable) / len(acceptable) if acceptable else None,
            "feasible_fraction": len(acceptable) / length}


def _certificate(instance, mask, optimum):
    bits = [int(bit) for bit in mask]
    center_weight, center_profit = _sums(instance, bits)
    if center_weight > instance.capacity or center_profit > optimum:
        raise ValueError("infeasible center or center exceeds confirmed optimum")
    source_hash = hashlib.sha256(_canonical(_source(instance))).hexdigest()
    center_text = _text(bits)
    identity = hashlib.sha256(_canonical(
        {"source_identity_sha256": source_hash, "mask": center_text})).hexdigest()
    neighbors, better, equal, feasible_count = [], 0, 0, 0
    flips = itertools.chain(((i,) for i in range(instance.n)),
                            itertools.combinations(range(instance.n), 2))
    for positions in flips:
        candidate = bits.copy()
        for position in positions:
            candidate[position] ^= 1
        weight, profit = _sums(instance, candidate)
        feasible = weight <= instance.capacity
        if feasible and profit > optimum:
            raise ValueError("neighbor exceeds confirmed exact optimum")
        feasible_count += int(feasible)
        better += int(feasible and profit > center_profit)
        equal += int(feasible and profit == center_profit)
        relation = ((profit > center_profit) - (profit < center_profit)) if feasible else None
        neighbors.append({"flips": list(positions), "mask": _text(candidate),
                          "weight": weight, "profit": profit, "feasible": feasible,
                          "infeasibility_reason": None if feasible else "CAPACITY_EXCEEDED",
                          "relation": relation})
    if center_profit == optimum:
        if better:
            raise ValueError("global center has an improving neighbor")
        state = "GLOBAL_OPTIMUM"
    elif better:
        state = "N2_NOT_LOCAL"
    elif equal:
        state = "N2_NONSTRICT_NONGLOBAL"
    else:
        state = "N2_STRICT_NONGLOBAL"
    summary = {"certificate_id": identity, "source_identity_sha256": source_hash,
               "n": instance.n, "center_mask": center_text,
               "center_weight": center_weight, "center_profit": center_profit,
               "optimum": optimum, "neighbor_count": len(neighbors),
               "feasible_neighbor_count": feasible_count,
               "infeasible_neighbor_count": len(neighbors) - feasible_count,
               "better_feasible_count": better, "equal_feasible_count": equal,
               "state": state}
    return identity, {"summary": summary, "neighbors": neighbors}


def analyze_run(instance, result, optimum: int, *, checkpoints=CHECKPOINTS,
                threshold=THRESHOLD):
    """Read only evaluated prefixes; certificates are produced after search."""
    requests, masks, size, count = _extract(instance, result, optimum, checkpoints, threshold)
    commits, endpoints = _timeline(result, size, count)
    records, best_ref, last_q = [], None, 0
    for ref in range(count):
        if requests["feasible"][ref] and (best_ref is None
                or int(requests["profit"][ref]) > int(requests["profit"][best_ref])):
            best_ref = ref
            last_q = max(0, ref + 1 - size)
        records.append((best_ref, last_q))
    certificates, rows = {}, []
    mask_certificates = {}
    for q in checkpoints:
        prefix = size + q
        ref, last_improvement = records[prefix - 1]
        if ref is None:
            raise ValueError("checkpoint has no feasible record")
        text = _text(masks[ref])
        if text not in mask_certificates:
            certificate_id, certificate = _certificate(instance, masks[ref], optimum)
            certificates[certificate_id] = certificate
            mask_certificates[text] = certificate_id
        certificate_id = mask_certificates[text]
        commit_q, population = next((cq, pop) for cq, pop in reversed(commits) if cq <= q)
        pending = list(range(size + commit_q, prefix))
        age = q - last_improvement
        metrics = _metrics(masks, requests, population)
        rows.append({"q": q, "mask": text,
                     "best_profit": int(requests["profit"][ref]),
                     "best_weight": int(requests["weight"][ref]),
                     "last_improvement_q": last_improvement,
                     "stagnation_age": age, "stagnant": age >= threshold,
                     "record_request_ref": ref, "population_refs": population.copy(),
                     "pending_refs": pending,
                     "unique_fraction": metrics["unique_fraction"],
                     "mean_pairwise_hamming": metrics["mean_pairwise_hamming"],
                     "state": certificates[certificate_id]["summary"]["state"],
                     "certificate_id": certificate_id})
    trajectory = []
    for q, complete, refs in endpoints:
        record_ref, _ = records[size + q - 1]
        trajectory.append({"q": q, "complete": complete,
                           **_metrics(masks, requests, refs),
                           "best_profit": int(requests["profit"][record_ref])
                           if record_ref is not None else None})
    centers = len(certificates)
    neighbors = centers * (instance.n + instance.n * (instance.n - 1) // 2)
    return {"schema_version": "knapsack-stagnation-diagnosis-v1",
            "threshold": threshold, "checkpoints": rows,
            "population_trajectory": trajectory, "certificates": certificates,
            "accounting": {"known_initial_evaluations": size,
                           "search_new_evaluations": count - size,
                           "diagnostic_center_evaluations": centers,
                           "diagnostic_neighbor_evaluations": neighbors,
                           "diagnostic_total_evaluations": centers + neighbors}}


def verify_diagnosis(instance, result, optimum: int, diagnosis, *,
                     checkpoints=CHECKPOINTS, threshold=THRESHOLD):
    """Independent Python-integer scores, pairwise distances and snapshots.

    This verifier deliberately does not call the producer's readout,
    certificate, timeline or population metric functions. Operator and RNG
    replay is separately performed by the historical independent GA oracle.
    """
    def require(condition, message):
        if not condition:
            raise ValueError(message)

    def close(actual, expected, label):
        if expected is None:
            require(actual is None, label)
        else:
            require(isinstance(actual, (int, float)) and not isinstance(actual, bool)
                    and math.isfinite(actual) and math.isclose(actual, expected,
                    rel_tol=1e-12, abs_tol=1e-12), label)

    require(isinstance(optimum, int) and not isinstance(optimum, bool) and optimum >= 0,
            "invalid exact optimum")
    require(isinstance(threshold, int) and not isinstance(threshold, bool) and threshold > 0,
            "invalid threshold")
    require(bool(checkpoints) and tuple(sorted(set(checkpoints))) == tuple(checkpoints)
            and all(isinstance(q, int) and not isinstance(q, bool) and q >= 0
                    for q in checkpoints), "invalid checkpoint schedule")
    raw, summary = result["requests"], result["summary"]
    masks = np.asarray(raw["masks"])
    require(masks.ndim == 2 and masks.shape[1] == instance.n
            and np.all((masks == 0) | (masks == 1)), "invalid masks")
    count = len(masks)
    size = summary["known_initial_requests"]
    require(isinstance(size, int) and not isinstance(size, bool) and 2 <= size <= count,
            "invalid initial size")
    require(checkpoints[-1] <= count - size, "checkpoint exceeds requests")
    for field, expected in (("logical_requests", count), ("budget", count),
                            ("population_size", size), ("N", size),
                            ("physical_evaluations", count - size)):
        require(summary.get(field, expected) == expected, "incorrect accounting")
    for field in ("weight", "profit", "feasible"):
        require(np.asarray(raw[field]).shape == (count,), "score dimensions")
    require(all(np.asarray(raw[k]).dtype.kind in "iu" for k in ("weight", "profit")),
            "noninteger objective scores")
    require(np.asarray(raw["feasible"]).dtype.kind == "b", "nonboolean feasibility")
    strings, packed, scores = [], [], []
    for ref, mask in enumerate(masks):
        selected = [j for j, bit in enumerate(mask) if int(bit) == 1]
        weight = sum(int(instance.weights[j]) for j in selected)
        profit = sum(int(instance.profits[j]) for j in selected)
        feasible = weight <= instance.capacity
        require(int(raw["weight"][ref]) == weight and int(raw["profit"][ref]) == profit
                and bool(raw["feasible"][ref]) == feasible, "request score mismatch")
        require(not feasible or profit <= optimum, "request exceeds exact optimum")
        text = "".join("1" if int(bit) else "0" for bit in mask)
        strings.append(text)
        packed.append(int(text, 2))
        scores.append((weight, profit, feasible))
    initial = result["generations"][0]
    current, end_count = list(range(size)), size
    require(initial["generation"] == 0 and initial["complete"] is True
            and initial["first_request"] == 1 and initial["last_request"] == size
            and initial["population_before"] == []
            and initial["population_after"] == current, "initial provenance")
    independent_commits = [(0, current.copy())]
    independent_endpoints = [(0, True, current.copy())]
    for ordinal, generation in enumerate(result["generations"][1:], 1):
        require(generation["generation"] == ordinal
                and generation["first_request"] == end_count + 1
                and generation["population_before"] == current, "generation continuity")
        finish = generation["last_request"]
        require(isinstance(finish, int) and not isinstance(finish, bool)
                and end_count < finish <= count, "generation range")
        children = list(range(end_count, finish))
        complete = len(children) == size - 1
        require(len(children) <= size - 1 and generation["complete"] is complete,
                "generation completion")
        require(complete or ordinal == len(result["generations"]) - 1,
                "nonterminal incomplete generation")
        position = generation["elite"]["population_index"]
        require(isinstance(position, int) and not isinstance(position, bool)
                and 0 <= position < size, "elite index")
        require(generation["elite"]["request_ref"] == current[position], "elite reference")
        if complete:
            current = [current[position]] + children
            independent_commits.append((finish - size, current.copy()))
        require(generation["population_after"] == current, "applied future population")
        independent_endpoints.append((finish - size, complete, current.copy()))
        end_count = finish
    require(end_count == count, "incomplete request coverage")
    require(summary.get("terminal_population_requests", current) == current,
            "terminal population mismatch")

    def independent_metrics(refs):
        profits = [scores[ref][1] for ref in refs if scores[ref][2]]
        distance_sum = sum((packed[refs[a]] ^ packed[refs[b]]).bit_count()
                           for a in range(len(refs)) for b in range(a + 1, len(refs)))
        return {"unique_fraction": len({strings[ref] for ref in refs}) / len(refs),
                "mean_pairwise_hamming": distance_sum / (len(refs) * (len(refs) - 1) / 2),
                "mean_feasible_profit": sum(profits) / len(profits) if profits else None,
                "feasible_fraction": len(profits) / len(refs)}

    require(diagnosis.get("schema_version") == "knapsack-stagnation-diagnosis-v1"
            and diagnosis.get("threshold") == threshold, "diagnosis schema or threshold")
    rows = diagnosis["checkpoints"]
    require(len(rows) == len(checkpoints), "checkpoint count")
    certificates = diagnosis["certificates"]
    used_ids = set()
    source = {"n": int(instance.n), "capacity": int(instance.capacity),
              "weights": [int(x) for x in instance.weights],
              "profits": [int(x) for x in instance.profits],
              "source_path": str(getattr(instance, "source_path", "")),
              "class_label": str(getattr(instance, "class_label", "")),
              "family": str(getattr(instance, "family", "")),
              "index": int(getattr(instance, "index", 0))}
    source_hash = hashlib.sha256(json.dumps(source, sort_keys=True, separators=(",", ":"),
        ensure_ascii=False, allow_nan=False).encode("utf-8")).hexdigest()
    verified_certificates, neighbor_evaluations = {}, 0

    def independently_check_certificate(identity, text):
        nonlocal neighbor_evaluations
        if identity in verified_certificates:
            require(verified_certificates[identity][0] == text, "certificate reused for wrong mask")
            return verified_certificates[identity][1]
        identity_data = {"source_identity_sha256": source_hash, "mask": text}
        expected_id = hashlib.sha256(json.dumps(identity_data, sort_keys=True,
            separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode("utf-8")).hexdigest()
        require(identity == expected_id and identity in certificates, "certificate identity")
        evidence = certificates[identity]
        bits = [int(bit) for bit in text]
        cw = sum(int(instance.weights[j]) for j in range(instance.n) if bits[j])
        cv = sum(int(instance.profits[j]) for j in range(instance.n) if bits[j])
        require(cw <= instance.capacity and cv <= optimum, "invalid certified center")
        pairs = [(j,) for j in range(instance.n)]
        pairs += [(a, b) for a in range(instance.n) for b in range(a + 1, instance.n)]
        require(len(evidence["neighbors"]) == len(pairs), "neighbor completeness")
        acceptable = improving = equal = 0
        for positions, row in zip(pairs, evidence["neighbors"]):
            candidate = [1 - bit if j in positions else bit for j, bit in enumerate(bits)]
            weight = sum(int(instance.weights[j]) for j in range(instance.n) if candidate[j])
            profit = sum(int(instance.profits[j]) for j in range(instance.n) if candidate[j])
            feasible = weight <= instance.capacity
            require(not feasible or profit <= optimum, "neighbor contradicts exact optimum")
            expected = {"flips": list(positions), "mask": "".join(map(str, candidate)),
                        "weight": weight, "profit": profit, "feasible": feasible,
                        "infeasibility_reason": None if feasible else "CAPACITY_EXCEEDED",
                        "relation": (1 if profit > cv else -1 if profit < cv else 0)
                        if feasible else None}
            require(row == expected and type(row["weight"]) is int
                    and type(row["profit"]) is int and type(row["feasible"]) is bool,
                    "neighbor mask, position, score or infeasibility mismatch")
            acceptable += int(feasible)
            improving += int(feasible and profit > cv)
            equal += int(feasible and profit == cv)
            neighbor_evaluations += 1
        state = ("GLOBAL_OPTIMUM" if cv == optimum else "N2_NOT_LOCAL" if improving
                 else "N2_NONSTRICT_NONGLOBAL" if equal else "N2_STRICT_NONGLOBAL")
        expected_summary = {"certificate_id": identity, "source_identity_sha256": source_hash,
                            "n": instance.n, "center_mask": text,
                            "center_weight": cw, "center_profit": cv, "optimum": optimum,
                            "neighbor_count": len(pairs), "feasible_neighbor_count": acceptable,
                            "infeasible_neighbor_count": len(pairs) - acceptable,
                            "better_feasible_count": improving, "equal_feasible_count": equal,
                            "state": state}
        require(evidence["summary"] == expected_summary, "certificate summary mismatch")
        verified_certificates[identity] = (text, state)
        return state

    for q, row in zip(checkpoints, rows):
        eligible = [ref for ref in range(size + q) if scores[ref][2]]
        require(bool(eligible), "no feasible record")
        best_value = max(scores[ref][1] for ref in eligible)
        ref = next(ref for ref in eligible if scores[ref][1] == best_value)
        last_q = max(0, ref + 1 - size)
        committed_q, refs = next((cq, p) for cq, p in reversed(independent_commits) if cq <= q)
        pending = list(range(size + committed_q, size + q))
        identity = row["certificate_id"]
        used_ids.add(identity)
        state = independently_check_certificate(identity, strings[ref])
        expected_fields = {"q": q, "mask": strings[ref], "best_profit": best_value,
                           "best_weight": scores[ref][0], "last_improvement_q": last_q,
                           "stagnation_age": q - last_q, "stagnant": q - last_q >= threshold,
                           "record_request_ref": ref, "population_refs": refs,
                           "pending_refs": pending, "state": state}
        for key, value in expected_fields.items():
            require(row.get(key) == value, "checkpoint mismatch: " + key)
        expected_metrics = independent_metrics(refs)
        for key in ("unique_fraction", "mean_pairwise_hamming"):
            close(row.get(key), expected_metrics[key], "checkpoint diversity mismatch: " + key)
    require(used_ids == set(certificates), "unused, duplicate or missing certificates")
    trajectory = diagnosis["population_trajectory"]
    require(len(trajectory) == len(independent_endpoints), "trajectory endpoint count")
    for row, (q, complete, refs) in zip(trajectory, independent_endpoints):
        require(row["q"] == q and row["complete"] is complete, "trajectory endpoint identity")
        eligible = [scores[ref][1] for ref in range(size + q) if scores[ref][2]]
        require(row["best_profit"] == (max(eligible) if eligible else None), "trajectory prefix record")
        for key, value in independent_metrics(refs).items():
            close(row.get(key), value, "trajectory metric: " + key)
    centers = len(verified_certificates)
    expected_accounting = {"known_initial_evaluations": size,
                           "search_new_evaluations": count - size,
                           "diagnostic_center_evaluations": centers,
                           "diagnostic_neighbor_evaluations": neighbor_evaluations,
                           "diagnostic_total_evaluations": centers + neighbor_evaluations}
    require(diagnosis["accounting"] == expected_accounting, "diagnostic accounting mismatch")
    return {"status": "PASS_DIAGNOSIS", "verified_checkpoints": len(rows),
            "verified_certificates": centers,
            "verification_request_evaluations": count,
            "verification_center_evaluations": centers,
            "verification_neighbor_evaluations": neighbor_evaluations,
            "verification_total_evaluations": count + centers + neighbor_evaluations}
