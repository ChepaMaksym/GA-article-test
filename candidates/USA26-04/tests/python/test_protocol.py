from __future__ import annotations

import csv
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest import mock


CANDIDATE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(CANDIDATE / "environments" / "python"))

from banditverify.cases import EXPECTED_CASE_IDS, load_matrix  # noqa: E402
import banditverify.protocol as protocol_module  # noqa: E402
from banditverify.protocol import validate_protocol  # noqa: E402


class ProtocolTests(unittest.TestCase):
    def test_frozen_protocol_and_absence_manifest(self) -> None:
        result = validate_protocol()
        self.assertEqual(result["paper_level_status"], "BLOCKED_G5_G9")
        self.assertEqual(
            result["published_result_status"], "INCONCLUSIVE_PUBLISHED_RESULT"
        )
        self.assertEqual(result["registry_status"], "conditional_noneligible")
        self.assertEqual(result["descriptive_target_count"], 6)
        self.assertEqual(result["executable_target_count"], 0)
        self.assertEqual(result["absence_count"], 15)

    def test_hardware_matrix_is_exact(self) -> None:
        cases = load_matrix(CANDIDATE / "config" / "hardware_formula_matrix.csv")
        self.assertEqual({case["case_id"] for case in cases}, EXPECTED_CASE_IDS)
        self.assertTrue(all(case["iterations"] == 20000 for case in cases))

    def test_freeze_commit_must_be_ancestor_of_current_head(self) -> None:
        original_run = protocol_module.subprocess.run

        def reject_only_ancestry(*args, **kwargs):
            command = args[0] if args else kwargs.get("args", [])
            if command[:3] == ["git", "merge-base", "--is-ancestor"]:
                return protocol_module.subprocess.CompletedProcess(command, 1)
            return original_run(*args, **kwargs)

        with mock.patch.object(
            protocol_module.subprocess,
            "run",
            side_effect=reject_only_ancestry,
        ):
            with self.assertRaisesRegex(AssertionError, "exactly one"):
                protocol_module._validate_git_binding()

    def test_published_remote_freeze_resolves_and_is_the_unique_twin_ancestor(self) -> None:
        remap = protocol_module.EXPECTED_BINDING["publication_remap"]
        remote = remap["published_remote_commit"]
        repository = protocol_module.repository_root(CANDIDATE)
        resolved = protocol_module.subprocess.check_output(
            ["git", "rev-parse", f"{remote}^{{commit}}"],
            cwd=repository,
            text=True,
        ).strip()
        self.assertEqual(resolved, remote)
        self.assertEqual(
            protocol_module.subprocess.run(
                ["git", "merge-base", "--is-ancestor", remote, "HEAD"],
                cwd=repository,
                check=False,
            ).returncode,
            0,
        )
        protocol_module._validate_git_binding()

    def test_publication_remap_is_exact_and_cannot_mutate(self) -> None:
        expected = protocol_module.EXPECTED_BINDING["publication_remap"]
        self.assertEqual(
            expected,
            {
                "prepublication_local_commit": "a8322b17dcd8e6f722b6d70390f24262f5bcbff2",
                "published_remote_commit": "c76c7ebf26777c52f2ff9a78482d894534dfb94b",
                "shared_tree": "f836090953f8b70374495c78f57dc009e455316a",
                "shared_parent": "eeac926e15107503377cbe09cdc8e830a6607fa5",
                "mapping_scope": "PROVENANCE_ONLY_NO_SCOPE_OR_TARGET_CHANGES",
            },
        )
        for field in expected:
            with self.subTest(field=field), tempfile.TemporaryDirectory() as directory:
                clone = Path(directory) / "candidate"
                shutil.copytree(CANDIDATE, clone)
                path = clone / "config" / "protocol.json"
                protocol = json.loads(path.read_text())
                protocol["preregistration_binding"]["publication_remap"][field] = "forged"
                path.write_text(json.dumps(protocol), encoding="utf-8")
                with self.assertRaisesRegex(AssertionError, "preregistration binding"):
                    validate_protocol(clone)

    def test_both_freeze_twins_as_ancestors_fail_closed(self) -> None:
        remap = protocol_module.EXPECTED_BINDING["publication_remap"]
        twins = [
            remap["prepublication_local_commit"],
            remap["published_remote_commit"],
        ]
        with self.assertRaisesRegex(AssertionError, "exactly one"):
            protocol_module._require_unique_published_ancestor(twins, twins)

    def test_absence_cannot_be_silently_promoted(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            clone = Path(directory) / "candidate"
            shutil.copytree(CANDIDATE, clone)
            path = clone / "config" / "protocol.json"
            protocol = json.loads(path.read_text())
            protocol["required_absences"]["seed_ledger"] = True
            path.write_text(json.dumps(protocol), encoding="utf-8")
            with self.assertRaisesRegex(AssertionError, "absence manifest"):
                validate_protocol(clone)

    def test_descriptive_target_cannot_become_executable(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            clone = Path(directory) / "candidate"
            shutil.copytree(CANDIDATE, clone)
            path = clone / "fixtures" / "published_table1_descriptive.csv"
            with path.open(encoding="utf-8", newline="") as handle:
                rows = list(csv.DictReader(handle))
                fields = list(rows[0])
            rows[2]["executable_target"] = "true"
            with path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=fields)
                writer.writeheader()
                writer.writerows(rows)
            with self.assertRaisesRegex(AssertionError, "frozen byte identity"):
                validate_protocol(clone)

    def test_nested_protocol_fields_and_boolean_types_are_exact(self) -> None:
        mutations = (
            ("frozen_date", "2026-08-08"),
            ("pass_full_forbidden", 1),
            ("controller_constants_reported", {}),
            ("hardware", {"timing_repeats": 5}),
        )
        for key, value in mutations:
            with self.subTest(key=key), tempfile.TemporaryDirectory() as directory:
                clone = Path(directory) / "candidate"
                shutil.copytree(CANDIDATE, clone)
                path = clone / "config" / "protocol.json"
                protocol = json.loads(path.read_text())
                protocol[key] = value
                path.write_text(json.dumps(protocol), encoding="utf-8")
                with self.assertRaises(AssertionError):
                    validate_protocol(clone)

    def test_every_source_identity_field_is_byte_pinned(self) -> None:
        for field, value in (
            ("url", "https://example.invalid/forged"),
            ("revision_or_path", "commit forged"),
            ("bytes", "1"),
            ("sha256", "0" * 64),
            ("license_status", "MIT"),
        ):
            with self.subTest(field=field), tempfile.TemporaryDirectory() as directory:
                clone = Path(directory) / "candidate"
                shutil.copytree(CANDIDATE, clone)
                path = clone / "source_manifest" / "sources.csv"
                with path.open(encoding="utf-8", newline="") as handle:
                    rows = list(csv.DictReader(handle))
                    fields = list(rows[0])
                rows[0][field] = value
                with path.open("w", encoding="utf-8", newline="") as handle:
                    writer = csv.DictWriter(handle, fieldnames=fields)
                    writer.writeheader()
                    writer.writerows(rows)
                with self.assertRaisesRegex(AssertionError, "frozen byte identity"):
                    validate_protocol(clone)

    def test_source_duplicate_and_table_value_mutation_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            clone = Path(directory) / "candidate"
            shutil.copytree(CANDIDATE, clone)
            source = clone / "source_manifest" / "sources.csv"
            source.write_text(source.read_text() + source.read_text().splitlines()[1] + "\n")
            with self.assertRaises(AssertionError):
                validate_protocol(clone)

        with tempfile.TemporaryDirectory() as directory:
            clone = Path(directory) / "candidate"
            shutil.copytree(CANDIDATE, clone)
            table = clone / "fixtures" / "published_table1_descriptive.csv"
            table.write_text(table.read_text().replace(",3686,", ",3687,"))
            with self.assertRaisesRegex(AssertionError, "frozen byte identity"):
                validate_protocol(clone)

    def test_candidate_contains_no_full_ga_entrypoint(self) -> None:
        package = CANDIDATE / "environments" / "python" / "banditverify"
        names = {path.name for path in package.glob("*.py")}
        self.assertFalse({"ga.py", "experiment.py", "reproduce_table1.py"} & names)
        protocol = json.loads((CANDIDATE / "config" / "protocol.json").read_text())
        self.assertTrue(protocol["full_ga_forbidden"])
        self.assertTrue(protocol["table1_execution_forbidden"])


if __name__ == "__main__":
    unittest.main()
