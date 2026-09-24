#!/usr/bin/env python3
"""Verify that focused Hybrid 1 tests kill deliberate critical-code mutants."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from typing import Dict, List, Tuple


TESTS = (
    "candidates/EU26-21/tests/test_hybrid_1_core.py",
    "candidates/EU26-21/tests/test_hybrid_1_core_semantics_extended.py",
)

MUTANTS: Tuple[Tuple[str, str, str], ...] = (
    (
        "M1_MUTATION_PROBABILITY_NOT_LAMBDA_OVER_N",
        "mutation_probability=numeric / float(dimension),",
        "mutation_probability=1.0 / float(dimension),",
    ),
    (
        "M2_CROSSOVER_PROBABILITY_NOT_ONE_OVER_LAMBDA",
        "crossover_probability=1.0 / numeric,",
        "crossover_probability=0.5,",
    ),
    (
        "M3_RESET_DISABLED_AT_CAP",
        "if reset and ctl.lambda_real == float(dimension):\n        return 1.0, True",
        "if reset and ctl.lambda_real == float(dimension):\n        return float(dimension), False",
    ),
    (
        "M4_PARENT_COPIES_ELIGIBLE",
        "        if mask != parent\n",
        "        if True\n",
    ),
    (
        "M5_NEUTRAL_CANDIDATE_REJECTED",
        "accepted = selection.candidate_fitness >= parent_fitness",
        "accepted = selection.candidate_fitness > parent_fitness",
    ),
    (
        "M6_LOGICAL_NFE_UNDERCOUNTED",
        "logical_cost = 2 * offspring_count",
        "logical_cost = offspring_count",
    ),
)


def _run_tests(root: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "unittest", *TESTS, "-v"],
        cwd=root,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )


def _copy_candidate(source_root: Path, destination_root: Path) -> None:
    destination = destination_root / "candidates" / "EU26-21"
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source_root / "candidates" / "EU26-21", destination)


def audit(root: Path) -> Dict[str, object]:
    root = root.resolve()
    source_core = root / "candidates" / "EU26-21" / "hybrid_1" / "core.py"
    if not source_core.is_file():
        raise FileNotFoundError(source_core)

    baseline = _run_tests(root)
    report: Dict[str, object] = {
        "schema": "eu26-21-test-mutation-audit-v1",
        "baseline_exit_code": baseline.returncode,
        "baseline_pass": baseline.returncode == 0,
        "mutants": [],
    }
    results: List[Dict[str, object]] = []
    if baseline.returncode != 0:
        report["pass"] = False
        report["baseline_log_tail"] = baseline.stdout.splitlines()[-80:]
        return report

    original = source_core.read_text(encoding="utf-8")
    for name, needle, replacement in MUTANTS:
        if original.count(needle) != 1:
            results.append({
                "name": name,
                "killed": False,
                "error": f"expected exactly one mutation site, found {original.count(needle)}",
            })
            continue
        with tempfile.TemporaryDirectory(prefix="eu26-21-mutant-") as directory:
            mutant_root = Path(directory)
            _copy_candidate(root, mutant_root)
            mutant_core = mutant_root / "candidates" / "EU26-21" / "hybrid_1" / "core.py"
            mutant_core.write_text(
                original.replace(needle, replacement, 1),
                encoding="utf-8",
            )
            completed = _run_tests(mutant_root)
            results.append({
                "name": name,
                "killed": completed.returncode != 0,
                "exit_code": completed.returncode,
                "log_tail": completed.stdout.splitlines()[-25:],
            })

    report["mutants"] = results
    report["killed"] = sum(bool(result.get("killed")) for result in results)
    report["total"] = len(results)
    report["pass"] = (
        report["baseline_pass"]
        and len(results) == len(MUTANTS)
        and all(bool(result.get("killed")) for result in results)
    )
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--output-json", type=Path)
    parser.add_argument("--enforce", action="store_true")
    args = parser.parse_args()

    report = audit(args.root)
    payload = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.output_json:
        args.output_json.parent.mkdir(parents=True, exist_ok=True)
        args.output_json.write_text(payload, encoding="utf-8")
    print(payload, end="")
    if args.enforce and not report["pass"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
