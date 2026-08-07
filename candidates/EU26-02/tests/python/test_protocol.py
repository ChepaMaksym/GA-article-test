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
        amendment = CANDIDATE / "preregistration" / "amendment-001-source-audit.md"
        self.assertTrue(amendment.is_file())
        self.assertIn("PASS_FULL", amendment.read_text(encoding="utf-8"))

    def test_transition_fixture_is_hashable_and_finite(self):
        fixture = CANDIDATE / "fixtures" / "deleter_transition_cases.json"
        value = json.loads(fixture.read_text(encoding="utf-8"))
        self.assertEqual(value["schema_version"], "1.0.0")
        self.assertGreaterEqual(len(value["cases"]), 5)
        digest = hashlib.sha256(fixture.read_bytes()).hexdigest()
        self.assertEqual(len(digest), 64)


if __name__ == "__main__":
    unittest.main()
