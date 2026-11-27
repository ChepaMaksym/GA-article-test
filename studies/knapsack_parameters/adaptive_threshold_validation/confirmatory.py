"""Compute the registered contrasts from paired, verified, physical-case endpoints.

roles maps (base, metric, role) to a frozen physical configuration ID. None
is permitted only for an inapplicable historical threshold. Read role maps
from the frozen experiment manifest, never infer candidates from outcomes.
"""
from statistics import mean

from .analysis import bca, endpoint
from .design import BASES, CONTROLS, METRICS, TOTAL


def compare(rows, roles, clusters, seeds, *, parcels=False):
    expected_roles = {(pc, metric, role) for pc in BASES for metric in METRICS
                      for role in ("candidate", *CONTROLS)}
    if set(roles) != expected_roles:
        raise ValueError("Incomplete frozen role mapping")
    if any(value is None and role != "same_mechanism_H145"
           for (_, _, role), value in roles.items()):
        raise ValueError("Unexpected inapplicable comparison")
    seeds = tuple(seeds)
    if len(set(seeds)) != 10 or len(seeds) != 10:
        raise ValueError("Expected ten distinct paired seeds")
    if len(clusters) != (30 if parcels else 10):
        raise ValueError("Invalid number of independent units")
    tasks = [task for members in clusters.values() for task in members]
    if len(tasks) != 30 or len(set(tasks)) != 30 or any(
            len(members) != (1 if parcels else 3) for members in clusters.values()):
        raise ValueError("Invalid independent-unit membership")
    physical = set(roles.values()) - {None}
    expected = {(task, seed, cfg) for task in tasks for seed in seeds for cfg in physical}
    indexed = {}
    optima = {}
    for row in rows:
        key = (row["task"], row["seed"], row["configuration"])
        if key not in expected or row["verified"] is not True or row["total"] != TOTAL:
            raise ValueError("Unexpected, duplicate or unverified physical case")
        expected.remove(key)
        opt = row["optimum"]
        if opt != optima.setdefault(row["task"], opt) or not 0 <= row["best"] <= opt or opt <= 0:
            raise ValueError("Inconsistent optimum or final score")
        hits = row["hits"]
        previous = 0
        for goal in (93,95,99):
            hit = hits[str(goal)]
            if (hit is not None) != (100*row["best"] >= goal*opt):
                raise ValueError("Threshold and record disagree")
            q = TOTAL+1 if hit is None else hit
            if type(q) is not int or not 1 <= q <= TOTAL+(hit is None) or q < previous:
                raise ValueError("Invalid first attainment")
            previous = q
        indexed[key] = row
    if expected:
        raise ValueError("Missing paired cases")
    results = []
    for pc in BASES:
        for metric in METRICS:
            candidate = roles[pc, metric, "candidate"]
            for role in CONTROLS:
                control = roles[pc, metric, role]
                result = dict(base=pc, metric=metric, control_role=role, candidate=candidate,
                              control=control, confidence=.9975)
                if control is None or control == candidate:
                    result.update(status="NOT_APPLICABLE" if control is None else "IDENTICAL")
                else:
                    effects = {}
                    for cluster in sorted(clusters):
                        differences = [mean(endpoint(indexed[task,seed,control],metric) -
                                            endpoint(indexed[task,seed,candidate],metric)
                                            for seed in seeds) for task in clusters[cluster]]
                        effects[cluster] = float(mean(differences))
                    stats = bca(list(effects.values()))
                    interval = stats["interval"]
                    result.update(stats, cluster_effects=effects,
                                  supported=bool(stats["status"]=="ESTIMATED" and interval[0]>0))
                    for name, cfg in (("candidate",candidate),("control",control)):
                        subset = [indexed[t,s,cfg] for t in tasks for s in seeds]
                        result[name+"_mean"] = float(mean(endpoint(r,metric) for r in subset))
                        result[name+"_misses93"] = sum(r["hits"]["93"] is None for r in subset)
                results.append(result)
    return results
