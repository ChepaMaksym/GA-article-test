from __future__ import annotations

import csv
import hashlib
import json
import unittest
from pathlib import Path


CANDIDATE = Path(__file__).resolve().parents[2]


class FrozenProtocolTests(unittest.TestCase):
    def test_optimizer_configuration_is_exact(self):
        config = json.loads(
            (CANDIDATE / "config" / "ahead_deleter_optimizer_config.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(config["population_size"], 2)
        self.assertEqual(config["nb_selected"], 2)
        self.assertEqual(
            [row["pseudo"] for row in config["crossover"]],
            ["gpx_50", "gpx_75", "gpx_90"],
        )
        self.assertEqual(
            [row["pseudo"] for row in config["local_search"]],
            ["TabuColOptimized", "PartialCol"],
        )
        self.assertEqual(config["adaptive"]["name"], "deleter")
        self.assertEqual(config["adaptive"]["memory_size"], 50)

    def test_profiles_and_seed_ledger_are_exact(self):
        profiles = json.loads(
            (CANDIDATE / "config" / "protocol_profiles.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(profiles["expected_instances"], 31)
        self.assertEqual(profiles["expected_seeds"], list(range(20)))
        self.assertEqual(
            profiles["archive_sha256"],
            "1b7e8cf1ef637005bd994104f6e1ee520256ed387994b126bbe875a137632e41",
        )
        self.assertEqual(profiles["archive_bytes"], 64_960_102)
        self.assertEqual(profiles["uncompressed_tar_bytes"], 276_705_280)
        self.assertEqual(
            profiles["uncompressed_tar_sha256"],
            "a3c5893a1a7de480a05b26cbef24a2e07d161f8ed5923354444d6ea2d2fb5cf8",
        )
        self.assertEqual(
            profiles["root_payload_manifest"],
            {
                "instance_count": 31,
                "member_count": 1_143,
                "payload_bytes": 104_406_336,
                "sha256": (
                    "d50f4be5378357a45fc65047849f2ad1e99d01a8a005da42538f2d27fd585a36"
                ),
            },
        )
        self.assertEqual(
            profiles["hardware_expected_digests"],
            {
                "formula_correctness": (
                    "5e0f1346a7eb931a7c5bda08f2df082c2a0027c9b359f37c78b1be5ef5f3d61a"
                ),
                "archive_correctness": (
                    "9b0b90fca330fd89c259b907a215f9336add73f6ad599a4a94c9946d632183c9"
                ),
                "combined_timing_endpoint": (
                    "3fe3d29b882589784d4cc136dc1aced17400e86e12fd0fd0371076a865819962"
                ),
            },
        )
        self.assertEqual(
            profiles["profiles"]["artifact_actual_10800"][
                "required_header_time_limit_seconds"
            ],
            10800,
        )
        self.assertEqual(
            profiles["profiles"]["paper_claimed_3600_diagnostic"][
                "row_time_cutoff_seconds"
            ],
            3600,
        )

        with (CANDIDATE / "config" / "seed_ledger.csv").open(
            newline="", encoding="utf-8"
        ) as handle:
            rows = list(csv.DictReader(handle))
        self.assertEqual([int(row["seed"]) for row in rows], list(range(20)))
        self.assertEqual([int(row["run_index"]) for row in rows], list(range(20)))

    def test_published_target_fixture_is_frozen(self):
        with (CANDIDATE / "fixtures" / "published_table2_ahead_deleter.csv").open(
            newline="", encoding="utf-8"
        ) as handle:
            rows = list(csv.DictReader(handle))
        self.assertEqual(len(rows), 31)
        self.assertEqual(len({row["instance"] for row in rows}), 31)
        focus = next(row for row in rows if row["instance"] == "C2000.9")
        self.assertEqual(
            (focus["published_best"], focus["published_mean"], focus["published_mean_best_time_seconds"]),
            ("404", "405.6", "2988"),
        )

    def test_source_manifest_hashes_and_amendment_are_present(self):
        with (CANDIDATE / "source_manifest" / "sources.csv").open(
            newline="", encoding="utf-8"
        ) as handle:
            rows = {row["source_id"]: row for row in csv.DictReader(handle)}
        self.assertEqual(
            rows["DELETER_ARCHIVE"]["sha256"],
            "1b7e8cf1ef637005bd994104f6e1ee520256ed387994b126bbe875a137632e41",
        )
        self.assertEqual(
            rows["R250_REDUCED_INPUT"]["sha256"],
            "1589cfc27c761c6014e3e6ff108270b49392ea300e9395015e28d535def57b39",
        )
        amendment_001 = (
            CANDIDATE / "preregistration" / "amendment-001-source-audit.md"
        )
        amendment_004 = (
            CANDIDATE
            / "preregistration"
            / "amendment-004-authenticated-snapshots.md"
        )
        self.assertTrue(amendment_001.is_file())
        self.assertIn("PASS_FULL", amendment_001.read_text(encoding="utf-8"))
        self.assertTrue(amendment_004.is_file())
        authenticated_contract = amendment_004.read_text(encoding="utf-8")
        self.assertIn("superseded", authenticated_contract)
        self.assertIn("immutable member", authenticated_contract)
        self.assertIn("PASS_FULL", authenticated_contract)

    def test_transition_fixture_is_hashable_and_finite(self):
        fixture = CANDIDATE / "fixtures" / "deleter_transition_cases.json"
        value = json.loads(fixture.read_text(encoding="utf-8"))
        self.assertEqual(value["schema_version"], "1.0.0")
        self.assertGreaterEqual(len(value["cases"]), 5)
        digest = hashlib.sha256(fixture.read_bytes()).hexdigest()
        self.assertEqual(len(digest), 64)


if __name__ == "__main__":
    unittest.main()
