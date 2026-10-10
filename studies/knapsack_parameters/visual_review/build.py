"""Authenticate frozen evidence and render it exclusively in GitHub Actions."""
from __future__ import annotations

import argparse
from collections import defaultdict
import csv
import gzip
import itertools
import json
import math
import os
from pathlib import Path
import platform
import subprocess

from ..secondary_review.contract import (file_identity, output_directory, read_json,
    require, verify_file_manifest, write_file_manifest, write_json)

ROOT = Path(__file__).resolve().parents[3]
STUDY = ROOT / "studies/knapsack_parameters"
MODULE = Path(__file__).resolve().parent
SECONDARY = STUDY / "secondary_review/evidence/run-38031512934"
MAIN = STUDY / "ga_study/evidence/run-37793424917"
PREPARATION = STUDY / "evidence/run-37637475385"
PROTOCOL_ID = "GA-KNAPSACK-QUESTION-FIGURES-V1"
REGISTRATION = "7fd38cd9df0d597c1842108fa219007f39f89ec3"
PROTOCOL_HASH = "a4bbf1e8f10daf5b7b8e9d50d275d0972a75ac6bd104c68c386590a91a080c86"
PINNED = {
    "secondary_review/evidence/run-38031512934/file_manifest.json": "7fd3bbce4bb5af348acdf115c9eb3385183f3b0cb0a098016ae7589d6f073144",
    "ga_study/evidence/run-37793424917/file_manifest.json": "3583fe289b65853b81869aa50fd7e4ddb1b5b89da353a8a22fe9043402fb424f",
    "evidence/run-37637475385/registry.json": "7e9b8fc893889426e2d3b57610e3a91c09263fcdff488cf15a2b84efe1bdc70f",
    "evidence/run-37637475385/cases/UC-s000/case.json": "0b6cebdd7dd2b7c16951b3d7d5af01a5ed33eb3536ffb6eb6a3d99a1e03d98d9",
    "evidence/run-37637475385/cases/UC-s000/neighbors.csv": "d80aa6fdd2315b4619d29a867a2c9923634a8f67d67c5f2f27561abfca0c6ec7",
    "inputs/source/00Uncorrelated/n00100/R01000/s000.kp": "e05b24ea5b60e90ad38a2e4b46c87a73f197a5828b06b8bb298c9668ecfafed5",
    "ga_study/dependencies/requirements.lock": "6818e0e12843daa10947f7554cb3edd573d9f7cdbc33e63f98f9f3a068869017",
}


def authenticate(expected_sha):
    require(os.environ.get("GITHUB_ACTIONS") == "true", "execution is CI-only")
    require(os.environ.get("GITHUB_REPOSITORY") == "ChepaMaksym/GA-article-test" and
            os.environ.get("GITHUB_REF") == "refs/heads/research/masters-ga-knapsack-parameters",
            "wrong repository or branch")
    actual = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    require(actual == expected_sha == os.environ.get("GITHUB_SHA"), "mixed implementation SHA")
    require(platform.python_version() == "3.12.14", "wrong Python patch")
    import numpy
    import matplotlib
    require(numpy.__version__ == "2.2.6" and matplotlib.__version__ == "3.10.3", "wrong runtime")
    subprocess.run(["git", "merge-base", "--is-ancestor", REGISTRATION, actual], cwd=ROOT, check=True)
    require(file_identity(MODULE / "PROTOCOL_UK.md")["sha256"] == PROTOCOL_HASH, "protocol changed")
    registered = subprocess.check_output(["git", "show", REGISTRATION +
        ":studies/knapsack_parameters/visual_review/PROTOCOL_UK.md"], cwd=ROOT)
    require(registered == (MODULE / "PROTOCOL_UK.md").read_bytes(), "registration bytes differ")
    ledger = []
    for relative, expected in PINNED.items():
        identity = file_identity(STUDY / relative)
        require(identity["sha256"] == expected, "source hash differs: " + relative)
        ledger.append({"path": relative, **identity})
    # Verify every retained historical file, not just the files used by figures.
    verify_file_manifest(SECONDARY)
    verify_file_manifest(MAIN)
    return {"protocol_id": PROTOCOL_ID, "registration_commit_sha": REGISTRATION,
        "implementation_commit_sha": actual, "run_id": int(os.environ["GITHUB_RUN_ID"]),
        "run_attempt": int(os.environ["GITHUB_RUN_ATTEMPT"]), "python_version": platform.python_version(),
        "sources": ledger, "new_search_runs": 0, "new_exact_solver_runs": 0,
        "new_bootstrap_runs": 0, "primary_results_changed": False}


def family_population_pairs(rows, cases, expected_contrasts=None):
    """Seeds/settings -> task -> family; never pool families as independent runs."""
    groups = defaultdict(list)
    paired_settings = defaultdict(set)
    identities = set()
    for row in rows:
        if row["start_profile"] != "local" or row["population_size"] not in (10, 50):
            continue
        key = (row["instance_id"], row["population_size"], row["repeat_seed"], row["configuration_id"])
        require(key not in identities, "duplicate population-pair identity")
        identities.add(key)
        require(type(row["escape_event"]) is bool, "invalid escape event")
        groups[(row["instance_id"], row["population_size"])].append(int(row["escape_event"]))
        paired_settings[(row["instance_id"], row["population_size"])].add(
            (row["repeat_seed"], row["configuration_id"].rsplit("-n", 1)[0]))
    require(groups, "no population pairs")
    tasks = sorted({name for name, _ in groups})
    families = defaultdict(lambda: {10: [], 50: []})
    for name in tasks:
        require((name, 10) in groups and (name, 50) in groups and
                len(groups[name, 10]) == len(groups[name, 50]) and
                paired_settings[name, 10] == paired_settings[name, 50], "unpaired task")
        for population in (10, 50):
            events = groups[name, population]
            families[cases[name]["family"]][population].append(sum(events) / len(events))
    result = [{"family": family, "n10": sum(values[10]) / len(values[10]),
               "n50": sum(values[50]) / len(values[50]), "instance_count": len(values[10])}
              for family, values in sorted(families.items())]
    if expected_contrasts is not None:
        require({row["family"] for row in result} == set(expected_contrasts), "missing family")
        for row in result:
            require(math.isclose(row["n50"] - row["n10"], expected_contrasts[row["family"]],
                                abs_tol=1e-15, rel_tol=1e-12), "historical family contrast differs")
    return result


def validate_compact(rows, cases):
    grid = {(m, c, n) for m in (.5, 1, 3) for c in (0, .5, .9) for n in (10, 30, 50)}
    names = set(cases)
    local_names = {name for name, case in cases.items() if case["status"].startswith("ADMITTED_")}
    expected = {(name, profile, seed, m, c, n) for profile, source in (("random", names), ("local", local_names))
                for name in source for seed in range(51001, 51031) for m, c, n in grid}
    found = set()
    for row in rows:
        key = (row["instance_id"], row["start_profile"], row["repeat_seed"], row["mutation_numerator"],
               row["crossover_probability"], row["population_size"])
        require(key in expected and key not in found, "duplicate, mixed or unauthorized compact row")
        require(row["logical_requests"] == 5000 and type(row["escape_event"]) is bool, "invalid compact count")
        found.add(key)
    require(found == expected and len(found) == 35640, "incomplete source rectangle")


def validate_neighbors(case, neighbors, values, weights):
    """Re-evaluate retained masks, not a search or an exact-solver run."""
    n, capacity = case["n"], case["capacity"]
    center = case["certificate"]["center"]
    mask = center["mask"]
    require(len(values) == len(weights) == n and len(mask) == n and set(mask) <= {"0", "1"}, "bad item/mask order")
    def evaluate(bits):
        return (sum(v for v, bit in zip(values, bits) if bit == "1"),
                sum(w for w, bit in zip(weights, bits) if bit == "1"))
    require(evaluate(mask) == (center["profit"], center["weight"]), "wrong center value")
    expected = {(i,) for i in range(n)} | set(itertools.combinations(range(n), 2))
    found = set()
    counts = dict(higher_feasible=0, equal_feasible=0, lower_feasible=0, invalid_count=0)
    for row in neighbors:
        flips = (row["flip_i"],) if row["distance"] == 1 else (row["flip_i"], row["flip_j"])
        require(row["distance"] in (1, 2) and flips in expected and flips not in found, "bad/repeated neighbor")
        found.add(flips)
        bits = list(mask)
        for index in flips:
            bits[index] = "0" if bits[index] == "1" else "1"
        profit, weight = evaluate(bits)
        require((profit, weight) == (row["profit"], row["weight"]) and
                row["feasible"] == (weight <= capacity), "corrupt neighbor evaluation")
        if not row["feasible"]:
            counts["invalid_count"] += 1
        else:
            key = "higher_feasible" if profit > center["profit"] else (
                  "equal_feasible" if profit == center["profit"] else "lower_feasible")
            counts[key] += 1
    require(found == expected, "incomplete neighborhood")
    require(all(counts[key] == case["certificate"][key] for key in counts), "certificate counts differ")
    witness = case["exact"]["capacity"]
    optimal_mask = witness["witness_mask"]
    require(len(optimal_mask) == n and set(optimal_mask) <= {"0", "1"}, "bad optimal witness")
    require(evaluate(optimal_mask) == (witness["witness_profit"], witness["witness_weight"]) and
            witness["witness_weight"] <= capacity and witness["witness_profit"] == case["exact"]["confirmed_optimum"],
            "wrong external optimum witness")
    return {**counts, "neighbors": len(found),
            "witness_distance": sum(a != b for a, b in zip(mask, optimal_mask))}


def population_points(trajectory):
    return [row for row in trajectory if row["generation"] == 0 or row["complete"]]


def load_data():
    require(os.environ.get("GITHUB_ACTIONS") == "true", "source verification is CI-only")
    analysis = read_json(SECONDARY / "analysis.json")
    trace = read_json(SECONDARY / "trace-audit.json")
    require(analysis["status"] == "COMPLETE_COMPACT_ANALYSIS" and analysis["run_id"] == 38031512934,
            "wrong secondary analysis")
    require(trace["status"] == "COMPLETE_TRACE_AUDIT" and trace["verified_case_count"] == 6,
            "missing verified trajectories")
    registry = read_json(PREPARATION / "registry.json")
    cases = {row["instance_id"]: row["payload"] for row in registry["cases"]}
    with gzip.open(MAIN / "run-summaries.jsonl.gz", "rt", encoding="utf-8") as stream:
        rows = [json.loads(line) for line in stream]
    validate_compact(rows, cases)
    contrasts = {row["family"]: row["contrasts"]["population_50_over_10"] for row in analysis["family_contrasts"]}
    pairs = family_population_pairs(rows, cases, contrasts)
    case = read_json(PREPARATION / "cases/UC-s000/case.json")
    with (PREPARATION / "cases/UC-s000/neighbors.csv").open(encoding="utf-8", newline="") as stream:
        neighbors = [{key: (row[key] == "1" if key == "feasible" else int(row[key]) if row[key] else None)
            for key in ("distance", "flip_i", "flip_j", "weight", "profit", "feasible")}
            for row in csv.DictReader(stream)]
    tokens = (STUDY / "inputs/source/00Uncorrelated/n00100/R01000/s000.kp").read_text().split()
    n, capacity = map(int, tokens[:2])
    require(n == 100 and capacity == case["capacity"] and len(tokens) == 2 + 2*n, "wrong instance format")
    values, weights = list(map(int, tokens[2::2])), list(map(int, tokens[3::2]))
    checks = validate_neighbors(case, neighbors, values, weights)
    require(checks == {"higher_feasible": 0, "equal_feasible": 0, "lower_feasible": 2670,
                      "invalid_count": 2380, "neighbors": 5050, "witness_distance": 3}, "wrong UC-s000 scope")
    require(len(pairs) == 10 and sum(row["n50"] != row["n10"] for row in pairs) == 3,
            "population support scope changed")
    identities = {(item["identity"]["start_profile"], item["identity"]["configuration_id"]) for item in trace["cases"]}
    require(identities == {(start, config) for start in ("random", "local")
            for config in ("m0p5-c0p9-n30", "m1-c0p9-n30", "m3-c0p9-n30")}, "substituted trace")
    for item in trace["cases"]:
        require(item["identity"]["instance_id"] == "UC-s000" and item["identity"]["repeat_seed"] == 51001
                and item["verified"] is True, "unverified trace")
        trajectory = item["trajectory"]
        require(trajectory[0]["last_request"] == 30 and trajectory[-1]["last_request"] == 5000,
                "wrong trace request scale")
        require(all(a["best_profit"] <= b["best_profit"] for a, b in zip(trajectory, trajectory[1:])),
                "nonmonotone best-so-far")
    return {"analysis": analysis, "trace": trace, "case": case, "neighbors": neighbors,
            "population_pairs": pairs, "checks": checks}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--expected-sha", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    provenance = authenticate(args.expected_sha)
    data = load_data()
    output = output_directory(args.output)
    from .figures import render
    passports = render(data, output)
    write_json(output / "plot-data.json", data)
    write_json(output / "figure-passports.json", {"provenance": provenance, "figures": passports})
    lines = ["# Рисунки: питання та відповіді", "", "Нових експериментів або статистичних перевірок не виконано.", ""]
    for index, item in enumerate(passports, 1):
        lines.extend([f"## {index}. {item['question']}", "", item["answer"], "",
                      f"![{item['question']}]({item['png']})", "", f"*{item['limitation']}*", ""])
    (output / "ПИТАННЯ_ТА_ВІДПОВІДІ.md").write_text("\n".join(lines), encoding="utf-8")
    write_file_manifest(output)
    print("COMPLETE_QUESTION_FIGURES", len(passports), "figures; no new search or bootstrap")


if __name__ == "__main__":
    main()
