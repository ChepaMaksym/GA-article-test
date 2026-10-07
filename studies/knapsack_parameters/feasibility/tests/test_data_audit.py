"""Synthetic parser and evidence fixtures; executed only by GitHub Actions."""

import json
from pathlib import Path
import tempfile
import unittest

from studies.knapsack_parameters.feasibility import data_audit as audit


def fixture_bytes(n=100):
    return (f"{n}\n10\n\n" + "\n".join(f"{index + 1} {index + 2}" for index in range(n)) + "\n").encode()


class SourceAuditTests(unittest.TestCase):
    def test_exact_original_item_order_and_immutable_instance(self):
        instance = audit.parse_instance(b"3\n10\n\n10 6\n8 5\n8 5\n", "fixture.kp", class_label="UC", family="s000", index=0, expected_n=3)
        self.assertEqual(instance.profits, (10, 8, 8))
        self.assertEqual(instance.weights, (6, 5, 5))
        self.assertEqual(instance.instance_id, "UC-s000")
        with self.assertRaises(AttributeError):
            instance.n = 2

    def test_parser_rejects_invalid_sources(self):
        valid = fixture_bytes()
        malformed = [valid.replace(b"100\n", b"99\n", 1), valid + b"1 1\n",
                     valid.replace(b"1 2\n", b"0 2\n", 1), valid.replace(b"1 2\n", b"1 -2\n", 1),
                     valid.replace(b"1 2\n", b"1.0 2\n", 1), valid.replace(b"1 2\n", b"1 2 3\n", 1),
                     valid.replace(b"10\n", b"0\n", 1), b"\xff" + valid]
        for raw in malformed:
            with self.subTest(raw=raw[:30]), self.assertRaises((ValueError, UnicodeError)):
                audit.parse_instance(raw, "fixture.kp", class_label="UC", family="s000", index=0)

    def test_license_requires_the_pinned_declaration(self):
        self.assertEqual(audit.check_license(b"Creative Commons Attribution 4.0 International License")["identifier"], "CC-BY-4.0")
        with self.assertRaises(ValueError):
            audit.check_license(b"All rights reserved")

    def test_source_set_is_exactly_thirty_plus_readme(self):
        specs = audit.source_specs()
        self.assertEqual(len(specs), 31)
        self.assertEqual(len({row["path"] for row in specs}), 31)
        self.assertEqual(specs[1]["path"], "00Uncorrelated/n00100/R01000/s000.kp")
        self.assertEqual(specs[-1]["path"], "02StronglyCorrelated/n00100/R01000/s009.kp")

    def test_complete_offline_audit_retains_and_hashes_every_original(self):
        def fetch(path):
            raw = b"Creative Commons Attribution 4.0 International License\n" if path == "README.md" else fixture_bytes()
            return raw, [{"attempt": 1, "status": "DOWNLOADED", "bytes": len(raw)}]
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "audit"
            report = audit.audit_sources(output, {"fixture": True}, fetcher=fetch)
            self.assertEqual(report["status"], "PASS_AUDIT")
            self.assertEqual(len(report["family_comparisons"]), 30)
            self.assertTrue(all(row["weights_equal"] and row["profits_equal"] and row["capacity_equal"] for row in report["family_comparisons"]))
            self.assertEqual(report["instances"][0]["original_positions"], list(range(100)))
            self.assertFalse(report["scientific_python_patch_frozen"])
            identities = json.loads((output / "file_manifest.json").read_text())["files"]
            self.assertEqual(sum(row["path"].startswith("source/") for row in identities), 31)
            self.assertFalse(any(row["path"] == "file_manifest.json" for row in identities))
            for row in identities:
                raw = (output / row["path"]).read_bytes()
                self.assertEqual(len(raw), row["bytes"])
                self.assertEqual(audit.sha256_bytes(raw), row["sha256"])
            with self.assertRaises(ValueError):
                audit.audit_sources(output, {}, fetcher=fetch)

    def test_negative_source_is_retained_and_never_replaced(self):
        seen = []
        def fetch(path):
            seen.append(path)
            raw = b"Creative Commons Attribution 4.0 International License\n" if path == "README.md" else fixture_bytes()
            if path.endswith("s003.kp") and path.startswith("00"):
                raw = b"invalid source\n"
            return raw, [{"attempt": 1, "status": "DOWNLOADED"}]
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "audit"
            report = audit.audit_sources(output, {}, fetcher=fetch)
            self.assertEqual(report["status"], "INCOMPLETE_AUDIT")
            self.assertEqual(report["instance_count"], 29)
            self.assertEqual(len(seen), 31)
            self.assertEqual(len(set(seen)), 31)
            self.assertEqual((output / "source/00Uncorrelated/n00100/R01000/s003.kp").read_bytes(), b"invalid source\n")


if __name__ == "__main__":
    unittest.main()
