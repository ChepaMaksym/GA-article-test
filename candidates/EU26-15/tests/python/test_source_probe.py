from __future__ import annotations

import csv
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from eu2615.source_probe import (
    REQUIRED_GARBO_TOKENS,
    SourceProbeError,
    _manifest_data_identity,
    probe_csv_dimension,
    probe_required_tokens,
    probe_source,
)
from eu2615 import load_contract


class SourceProbeTests(unittest.TestCase):
    def minimal_source(self) -> str:
        return "\n".join((*REQUIRED_GARBO_TOKENS, "x = np.random.choice([1])"))

    def test_required_tokens_accept_exact_quirk(self):
        report = probe_required_tokens(self.minimal_source())
        self.assertEqual(report["mutation_antecedent"], "intFV(ft_input)")
        self.assertGreater(report["numpy_random_call_tokens"], 0)
        self.assertFalse(report["numpy_random_seed_present"])

    def test_corrected_intft_token_is_rejected(self):
        mutated = self.minimal_source().replace(
            "FT_class = intFV(ft_input)", "FT_class = intFT(ft_input)"
        )
        with self.assertRaises(SourceProbeError):
            probe_required_tokens(mutated)

    def test_numpy_seed_blocker_drift_is_rejected(self):
        mutated = self.minimal_source() + "\nnp.random.seed(64)\n"
        with self.assertRaises(SourceProbeError):
            probe_required_tokens(mutated)

    def write_csv(self, path: Path, columns: int = 1600, rows: int = 217):
        header = [f"feature_{index}" for index in range(columns - 1)] + ["class"]
        row = ["0"] * columns
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(header)
            for _ in range(rows):
                writer.writerow(row)

    def test_data_manifest_binds_exact_bytes_blob_and_sha(self):
        identity = _manifest_data_identity(load_contract())
        self.assertEqual(identity["path"], "data_ccle_erl_ge.csv")
        self.assertEqual(identity["bytes"], 1761174)
        self.assertEqual(
            identity["git_blob"], "a9fe81da8bb21e487b72be849864f57cb29374e8"
        )
        self.assertEqual(
            identity["sha256"],
            "03b3f9efcbbc78c45373a310fbd1f9462618ed147d42124336b2a64e4d1ed860",
        )

    def test_shape_correct_but_unbound_csv_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            source_dir = Path(directory)
            path = source_dir / "data_ccle_erl_ge.csv"
            self.write_csv(path)
            with self.assertRaisesRegex(SourceProbeError, "byte-length drift"):
                probe_csv_dimension(path, source_dir=source_dir)

    def test_same_size_data_drift_is_rejected_by_sha(self):
        with tempfile.TemporaryDirectory() as directory:
            source_dir = Path(directory)
            path = source_dir / "data_ccle_erl_ge.csv"
            path.write_bytes(b"x" * 1761174)
            with self.assertRaisesRegex(SourceProbeError, "SHA-256 drift"):
                probe_csv_dimension(path, source_dir=source_dir)

    def test_dirty_checkout_is_rejected_before_any_source_claim(self):
        with tempfile.TemporaryDirectory() as directory:
            with mock.patch(
                "eu2615.source_probe._git", return_value=" M GARBO.py"
            ) as git_probe:
                with self.assertRaisesRegex(SourceProbeError, "dirty before"):
                    probe_source(Path(directory))
        git_probe.assert_called_once_with(
            Path(directory).resolve(),
            ["status", "--porcelain=v1", "--untracked-files=all"],
        )


if __name__ == "__main__":
    unittest.main()
