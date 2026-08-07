from __future__ import annotations

from pathlib import Path
import sys
import unittest

import numpy as np

CANDIDATE_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(CANDIDATE_ROOT / "environments" / "python"))

from gesmr.benchmarks import (  # noqa: E402
    ackley,
    get_benchmark,
    griewank,
    rastrigin,
    rosenbrock,
    sphere,
)


class BenchmarkTests(unittest.TestCase):
    def test_known_global_minima(self) -> None:
        zeros = np.zeros((3, 12), dtype=np.float64)
        ones = np.ones((3, 12), dtype=np.float64)
        np.testing.assert_allclose(sphere(zeros), 0.0, atol=0.0, rtol=0.0)
        np.testing.assert_allclose(ackley(zeros), 0.0, atol=1e-14, rtol=0.0)
        np.testing.assert_allclose(griewank(zeros), 0.0, atol=0.0, rtol=0.0)
        np.testing.assert_allclose(rastrigin(zeros), 0.0, atol=0.0, rtol=0.0)
        np.testing.assert_allclose(rosenbrock(ones), 0.0, atol=0.0, rtol=0.0)

    def test_batch_shape_and_finiteness(self) -> None:
        population = np.linspace(-2.0, 2.0, 84).reshape(7, 12)
        for name in ("ackley", "griewank", "rastrigin", "rosenbrock", "sphere"):
            values = get_benchmark(name)(population)
            self.assertEqual(values.shape, (7,))
            self.assertTrue(np.all(np.isfinite(values)), name)

    def test_invalid_shape_fails_closed(self) -> None:
        with self.assertRaises(ValueError):
            sphere(np.zeros(12))
        with self.assertRaises(ValueError):
            rosenbrock(np.zeros((1, 1)))


if __name__ == "__main__":
    unittest.main()
