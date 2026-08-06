"""Fail-closed unit tests for the frozen hardware-portability harness."""

from __future__ import annotations

import copy
import importlib.util
from pathlib import Path
from types import SimpleNamespace
import unittest

import numpy as np


TESTS = Path(__file__).resolve().parents[1]


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


RUNNER = _load("hardware_runner", TESTS / "hardware" / "run_portability_suite.py")
COMPARE = _load("hardware_compare", TESTS / "hardware" / "compare_portability_reports.py")


class HardwareContractTests(unittest.TestCase):
    def test_matrix_is_exactly_frozen(self) -> None:
        correctness, throughput = RUNNER._load_matrix(
            TESTS.parents[0] / "config" / "hardware_smoke_matrix.csv"
        )
        self.assertEqual(len(correctness), 40)
        self.assertEqual(len(throughput), 40)
        self.assertEqual({row["seed"] for row in correctness}, set(range(40)))
        self.assertEqual(
            {row["function"] for row in throughput},
            {"ackley", "griewank", "rastrigin", "rosenbrock", "sphere"},
        )

    def test_v1_hash_covers_arithmetic_history_and_accounting(self) -> None:
        case = {
            "function": "sphere",
            "dimension": 1,
            "initial_std": 1.0,
            "generations": 1,
            "seed": 0,
        }
        base = SimpleNamespace(
            final_population=np.array([[1.0]]),
            final_fitness=np.array([1.0]),
            final_sigmas=np.array([1.0]),
            best_fitness_history=np.array([2.0, 1.0]),
            geometric_mean_sigma_history=np.array([1.0, 1.1]),
            arithmetic_mean_sigma_history=np.array([1.0, 1.2]),
            sigma_history=np.array([[1.0], [1.1]]),
            objective_call_count=2,
            objective_row_evaluation_count=202,
        )
        original = RUNNER._result_hash(case, base)
        changed_history = copy.deepcopy(base)
        changed_history.arithmetic_mean_sigma_history[1] = 1.3
        changed_accounting = copy.deepcopy(base)
        changed_accounting.objective_row_evaluation_count = 203
        self.assertNotEqual(original, RUNNER._result_hash(case, changed_history))
        self.assertNotEqual(original, RUNNER._result_hash(case, changed_accounting))

    def test_source_mismatch_cannot_pass_pairwise_gate(self) -> None:
        row = {
            "case_id": "case",
            "sha256_v1": "a" * 64,
            "numeric_signature": {"value": 1.0},
        }
        left = {
            "profile_label": "left",
            "source_sha256": {"core.py": "b" * 64},
            "correctness": {"cases": [row]},
        }
        right = copy.deepcopy(left)
        right["profile_label"] = "right"
        right["source_sha256"]["core.py"] = "c" * 64
        result = COMPARE._compare_pair(left, right)
        self.assertEqual(result["status"], "INCONCLUSIVE_SOURCE_MISMATCH")
        self.assertFalse(result["source_hashes_match"])


if __name__ == "__main__":
    unittest.main()
