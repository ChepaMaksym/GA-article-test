from __future__ import annotations

import copy
import unittest

from eu2613.contract import load_contract, validate_contract
from eu2613.errors import VerificationError


class ContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.contract = load_contract()

    def reject(self, mutator) -> None:
        candidate = copy.deepcopy(self.contract)
        mutator(candidate)
        with self.assertRaises(VerificationError):
            validate_contract(candidate)

    def test_valid_contract(self) -> None:
        validate_contract(copy.deepcopy(self.contract))

    def test_mutation_status(self) -> None:
        self.reject(lambda c: c.__setitem__("status", "PASS_FULL"))

    def test_mutation_readiness(self) -> None:
        self.reject(lambda c: c.__setitem__("readiness", "PASS"))

    def test_mutation_paper_mapping(self) -> None:
        self.reject(lambda c: c.__setitem__("paper_mapping", "LITERAL"))

    def test_mutation_source_native_status(self) -> None:
        self.reject(lambda c: c.__setitem__("source_native_status", "PASS"))

    def test_mutation_remove_forbidden_claim(self) -> None:
        self.reject(lambda c: c["forbidden_claims"].remove("PASS_FULL"))

    def test_mutation_range_cap(self) -> None:
        self.reject(lambda c: c["verification_execution"].__setitem__("maximum_range_bytes_per_request", 5_000_000))

    def test_mutation_allow_outer_download(self) -> None:
        self.reject(lambda c: c["verification_execution"].__setitem__("full_outer_archive_download_forbidden", False))

    def test_mutation_allow_source_execution(self) -> None:
        self.reject(lambda c: c["verification_execution"].__setitem__("source_native_execution_forbidden_under_v1", False))

    def test_mutation_large_archive_size(self) -> None:
        self.reject(lambda c: c["zenodo_files"]["repelling.zip"].__setitem__("bytes", 17_573_142_425))

    def test_mutation_large_archive_md5(self) -> None:
        self.reject(lambda c: c["zenodo_files"]["repelling.zip"].__setitem__("md5", "0" * 32))

    def test_mutation_large_archive_md5_status(self) -> None:
        self.reject(lambda c: c["zenodo_files"]["repelling.zip"].__setitem__("md5_status", "RECOMPUTED"))

    def test_mutation_git_revision(self) -> None:
        self.reject(lambda c: c["source_snapshot"].__setitem__("git_revision", "deadbeef"))

    def test_mutation_git_mapping(self) -> None:
        self.reject(lambda c: c["source_snapshot"].__setitem__("archive_maps_to_public_git_commit", True))

    def test_mutation_dimension(self) -> None:
        self.reject(lambda c: c["endpoint"].__setitem__("dimension", 10))

    def test_mutation_endpoint_decimal(self) -> None:
        self.reject(lambda c: c["endpoint"].__setitem__("best_y_decimal", "7.38e-09"))


if __name__ == "__main__":
    unittest.main()
