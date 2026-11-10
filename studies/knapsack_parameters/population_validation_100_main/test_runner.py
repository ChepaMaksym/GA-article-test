"""Fast CI-only tests for main-stage input identity and hard artifact limits.

No registered scientific instance or full GA run is performed by these tests.
They may run in the separately authorized technical test-only CI stage.
"""
from copy import deepcopy
import hashlib
import os
from pathlib import Path
import random
import tempfile
import unittest
from unittest.mock import patch

from .common import guard_main
from .runner import _safe_file, _used_bytes, _validate_protocol, _verify_files, _write_bounded
from studies.knapsack_parameters.population_validation_100.common import guard_technical, read_json
from studies.knapsack_parameters.population_validation_100.preparation import make_bank, score


class MainRunnerChecks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        guard_technical()
        cls.protocol = read_json(Path(__file__).resolve().parent / "protocol.json")

    def test_bounded_json_preserves_completed_receipt_and_emergency_space(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            raw, compact = root / "raw", root / "compact"
            raw.mkdir()
            compact.mkdir()
            budget = {"limit": 128 * 1024 + 128, "used": 0}
            previous = compact / "previous.json"
            _write_bounded(previous, {"status": "VERIFIED"}, budget)
            retained = previous.read_bytes()
            with self.assertRaises(ValueError):
                _write_bounded(raw / "too-large.json", {"payload": "x" * 10000}, budget)
            self.assertTrue((raw / "too-large.json.pending").is_file())
            self.assertFalse((raw / "too-large.json").exists())
            self.assertEqual(previous.read_bytes(), retained)
            _write_bounded(compact / "failure.json", {"status": "FAILED_OR_INTERRUPTED"}, budget, emergency=True)
            self.assertEqual(_used_bytes(raw, compact), budget["used"])
            self.assertLessEqual(budget["used"], budget["limit"])

    def test_bounded_gzip_never_exceeds_combined_ceiling(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            raw, compact = root / "raw", root / "compact"
            raw.mkdir()
            compact.mkdir()
            budget = {"limit": 128 * 1024 + 512, "used": 0}
            generator = random.Random(150031)
            values = [generator.getrandbits(32) for _ in range(10000)]
            with self.assertRaises(ValueError):
                _write_bounded(raw / "large.json.gz", {"values": values}, budget)
            self.assertTrue((raw / "large.json.gz.pending").is_file())
            self.assertFalse((raw / "large.json.gz").exists())
            _write_bounded(compact / "failure.json", {"status": "FAILED"}, budget, emergency=True)
            self.assertEqual(_used_bytes(raw, compact), budget["used"])
            self.assertLessEqual(budget["used"], budget["limit"])

    def test_atomic_publication_never_replaces_existing_evidence(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            budget = {"limit": 128 * 1024 + 4096, "used": 0}
            destination = root / "race.json"
            real_link = os.link

            def concurrent_create(source, target):
                Path(target).write_bytes(b"EXISTING")
                return real_link(source, target)

            with patch("studies.knapsack_parameters.population_validation_100_main.runner.os.link", side_effect=concurrent_create):
                with self.assertRaises(FileExistsError):
                    _write_bounded(destination, {"status": "VERIFIED"}, budget)
            self.assertEqual(destination.read_bytes(), b"EXISTING")
            self.assertTrue((root / "race.json.pending").is_file())

    def test_input_inventory_rejects_duplicates_changed_bytes_and_unsafe_paths(self):
        with tempfile.TemporaryDirectory() as temporary:
            outer = Path(temporary)
            root = outer / "prepared"
            root.mkdir()
            good = root / "problem.json"
            good.write_bytes(b"input")
            outside = outer / "outside.json"
            outside.write_bytes(b"input")
            entry = {"path": "problem.json", "bytes": 5, "sha256": hashlib.sha256(b"input").hexdigest()}
            _verify_files(root, [entry])
            with self.assertRaises(ValueError):
                _verify_files(root, [entry, entry])
            with self.assertRaises(ValueError):
                _safe_file(root, "../outside.json")
            with self.assertRaises(ValueError):
                _safe_file(root, "nested/../problem.json")
            good.write_bytes(b"other")
            with self.assertRaises(ValueError):
                _verify_files(root, [entry])

    def test_registered_plan_rejects_dimension_population_seed_and_resource_changes(self):
        _validate_protocol(self.protocol)
        for mutation in (lambda p: p.update(item_count=500),
                         lambda p: p.update(populations=[10, 20, 25]),
                         lambda p: p.update(search_seeds=[150001] * 10),
                         lambda p: p.update(total_evaluations=99999),
                         lambda p: p["fixed_parameters"].update(p_c=1.0),
                         lambda p: p["shard_limits"].update(reserve_bytes=p["shard_limits"]["bytes"])):
            changed = deepcopy(self.protocol)
            mutation(changed)
            with self.assertRaises(ValueError):
                _validate_protocol(changed)

    def test_initial_bank_has_exact_shared_prefix_and_registered_identity(self):
        problem = {"n": 100, "capacity": 100, "weights": [1] * 100, "profits": [1] * 100}
        bank = make_bank(problem, 3, 150001, 150000)
        self.assertEqual((bank["task_index"], bank["search_seed"], bank["preparation_seed"]), (3, 150001, 150000))
        self.assertEqual(len(bank["masks"]), 30)
        self.assertEqual(bank["masks"][0], "0" * 100)
        self.assertEqual(bank["masks"][:10], bank["masks"][:20][:10])
        self.assertEqual(bank["masks"][:20], bank["masks"][:30][:20])
        self.assertEqual(bank["scores"], [score(problem, mask) for mask in bank["masks"]])

    def test_main_guard_rejects_non_ci_environment(self):
        with patch.dict(os.environ, {"GITHUB_ACTIONS": "false"}):
            with self.assertRaises((ValueError, RuntimeError)):
                guard_main()


if __name__ == "__main__":
    unittest.main()
