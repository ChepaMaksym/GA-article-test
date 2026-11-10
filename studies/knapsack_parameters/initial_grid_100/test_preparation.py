"""CI-only checks of source admission and duplicate/reference validation."""
from copy import deepcopy
from hashlib import sha1, sha256
import unittest

from .common import guard_stage
from .preparation import admit_new_problem, verify_certificate
from studies.knapsack_parameters.population_validation_100.preparation import validate_source
from studies.knapsack_parameters.population_size_study.inputs import problem_sha256, unordered_problem_sha256


class PreparationChecks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        guard_stage("technical")

    def test_source_byte_change_is_rejected(self):
        raw = ("100\n50\n" + "2 1\n" * 100).encode("ascii")
        entry = {"source_path": "00Uncorrelated/n00100/R01000/s060.kp", "source_bytes": len(raw),
                 "git_blob_sha1": sha1(b"blob " + str(len(raw)).encode("ascii") + b"\0" + raw).hexdigest()}
        self.assertEqual(validate_source(raw, entry)["n"], 100)
        changed = raw.replace(b"2 1", b"3 1", 1)
        with self.assertRaises(ValueError):
            validate_source(changed, entry)

    def test_permuted_historical_problem_is_rejected(self):
        original = {"n": 3, "capacity": 3, "profits": [3, 5, 7], "weights": [1, 2, 3]}
        permuted = {"n": 3, "capacity": 3, "profits": [7, 3, 5], "weights": [3, 1, 2]}
        history = {unordered_problem_sha256(original)}
        with self.assertRaises(ValueError):
            admit_new_problem(permuted, history, set())

    def test_repeated_validation_problem_is_rejected(self):
        problem = {"n": 2, "capacity": 2, "profits": [2, 4], "weights": [1, 1]}
        admitted = set()
        admit_new_problem(problem, set(), admitted)
        with self.assertRaises(ValueError):
            admit_new_problem(problem, set(), admitted)

    def test_changed_exact_witness_is_rejected(self):
        problem = {"n": 2, "capacity": 2, "profits": [2, 4], "weights": [1, 1]}
        raw = b"2\n2\n2 1\n4 1\n"
        witness = {"optimum_profit": 6, "witness_mask": "11", "witness_profit": 6, "witness_weight": 2}
        certificate = {"status": "CERTIFIED_TWO_INDEPENDENT_EXACT_ORACLES", "search_uses_optimum": False,
                       "optimum": 6, "problem_sha256": problem_sha256(problem), "source_sha256": sha256(raw).hexdigest(),
                       "capacity_certificate": {**witness, "method": "capacity_max_profit_dp_packed_witness"},
                       "profit_certificate": {**witness, "method": "profit_min_weight_dp_independent_packed_witness"}}
        verify_certificate(problem, certificate, raw)
        damaged = deepcopy(certificate)
        damaged["profit_certificate"]["witness_mask"] = "10"
        with self.assertRaises(ValueError):
            verify_certificate(problem, damaged, raw)


if __name__ == "__main__":
    unittest.main()
