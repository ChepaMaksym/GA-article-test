from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path

from eu2611.report import compose_report, load_json, write_new_json


CANDIDATE = Path(__file__).resolve().parents[2]
CONTRACT_PATH = CANDIDATE / "config" / "verification_contract.json"
CONTRACT = load_json(CONTRACT_PATH)


class ProtocolTests(unittest.TestCase):
    def test_contract_freezes_literal_figure_cell(self) -> None:
        endpoint = CONTRACT["endpoint"]
        self.assertEqual(
            (endpoint["figure"], endpoint["algorithm"], endpoint["dimension"], endpoint["paper_display"]),
            (1, "OPT-128", 20, "-4.16"),
        )
        self.assertEqual(endpoint["seed_policy"], "not_applicable_deterministic_point_set_formula")

    def test_claim_boundary_forbids_full_and_empirical_passes(self) -> None:
        self.assertEqual(CONTRACT["status"], "TARGETED_DETERMINISTIC_FIGURE1_REPLAY_ONLY")
        self.assertIn("PASS_FULL", CONTRACT["forbidden_claims"])
        self.assertIn("PASS_BBOB_EMPIRICAL", CONTRACT["forbidden_claims"])
        self.assertNotEqual(CONTRACT["paper_level_status"], "PASS_FULL")

    def test_artifacts_have_independent_immutable_identities(self) -> None:
        for name in ("point_set", "numeric_block"):
            artifact = CONTRACT[name]
            self.assertGreater(artifact["bytes"], 0)
            self.assertEqual(len(artifact["md5"]), 32)
            self.assertEqual(len(artifact["sha256"]), 64)
            self.assertTrue(artifact["url"].startswith("https://zenodo.org/"))

    def test_verifier_forbids_executable_pickle_loading(self) -> None:
        self.assertTrue(CONTRACT["verification_execution"]["pickle_execution_forbidden"])
        source = (CANDIDATE / "environments" / "python" / "eu2611" / "artifact.py").read_text(encoding="utf-8")
        forbidden = ("pickle.load(", "pickle.loads(", "pandas.read_pickle", "pd.read_pickle")
        for marker in forbidden:
            with self.subTest(marker=marker):
                self.assertNotIn(marker, source)

    def test_output_writer_is_create_only(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "report.json"
            write_new_json(output, {"finite": 1.0})
            with self.assertRaises(ValueError):
                write_new_json(output, {"finite": 2.0})

    @unittest.skipUnless(
        all(os.environ.get(name) for name in ("EU2611_POINT_SET", "EU2611_PICKLE", "EU2611_SOURCE")),
        "authenticated EU26-11 inputs not set",
    )
    def test_formal_composition_retains_narrow_status(self) -> None:
        report = compose_report(
            contract=CONTRACT,
            point_path=Path(os.environ["EU2611_POINT_SET"]),
            numeric_path=Path(os.environ["EU2611_PICKLE"]),
            source_checkout=Path(os.environ["EU2611_SOURCE"]),
        )
        self.assertEqual(report["status"], "PASS_TARGET_ARTIFACT_REPLAY")
        self.assertEqual(report["observed"]["display_two_decimals"], "-4.16")
        self.assertIn("PASS_FULL", report["forbidden_claims"])
        self.assertNotEqual(report["paper_level_status"], "PASS_FULL")


if __name__ == "__main__":
    unittest.main()
