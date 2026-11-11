"""Small provenance and archive-safety checks; executed only by the CI suite."""
from copy import deepcopy
from io import BytesIO
from pathlib import Path
import tempfile
import unittest
from zipfile import ZipFile, ZipInfo

from ..common import HERE
from ..retained import validate_members, validate_registry
from ..preparation import authenticate_reference
from studies.knapsack_parameters.population_validation_100.common import read_json, sha


class RetainedPreparationTests(unittest.TestCase):
    def test_registered_reference_inventory_and_duplicate_identity(self):
        registry = read_json(HERE / "data/retained_registry.json")
        self.assertEqual(len(validate_registry(registry)), 9)
        broken = deepcopy(registry)
        references = [r for r in broken["archives"] if r["role"] == "compatibility"]
        references[-1]["selected"][0] = deepcopy(references[0]["selected"][0])
        with self.assertRaises(ValueError):
            validate_registry(broken)

    def test_archive_traversal_duplicate_and_symlink_are_rejected(self):
        for name, symlink in (("../journal.json.gz", False), ("safe\\journal.json.gz", False),
                              ("C:/journal.json.gz", False), ("/journal.json.gz", False),
                              ("journal.json.gz", True)):
            raw = BytesIO()
            with ZipFile(raw, "w") as archive:
                item = ZipInfo(name)
                if symlink:
                    item.create_system = 3
                    item.external_attr = 0o120777 << 16
                archive.writestr(item, b"content")
            raw.seek(0)
            with ZipFile(raw) as archive, self.assertRaises(ValueError):
                validate_members(archive)
        raw = BytesIO()
        with ZipFile(raw, "w") as archive:
            archive.writestr("same", b"a")
            archive.writestr("same", b"b")
        raw.seek(0)
        with ZipFile(raw) as archive, self.assertRaises(ValueError):
            validate_members(archive)

    def test_substituted_raw_reference_is_rejected_before_replay(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for name in ("journal.json.gz", "record.json", "verification.json"):
                (root / name).write_bytes(b"fixture")
            expected = {"task": "n00100-UC-s050", "mu": 10, "seed": 150001,
                        "pc_percentage": 100, "mutation_basis_points": 100,
                        "artifact_hashes": {name: sha(root / name)
                                            for name in ("journal.json.gz", "record.json", "verification.json")}}
            (root / "journal.json.gz").write_bytes(b"corrupt")
            with self.assertRaises(ValueError):
                authenticate_reference(root, expected, "n00100-UC-s050", 10)


if __name__ == "__main__":
    unittest.main()
