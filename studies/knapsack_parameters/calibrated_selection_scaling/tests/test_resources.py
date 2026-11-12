"""CI-only fixtures for aggregate kernel CPU/RAM enforcement and its launcher."""
from copy import deepcopy
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from .. import resources


IMAGE = "python@sha256:" + "a" * 64


class ResourceFixtures(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if os.environ.get("GITHUB_ACTIONS") != "true":
            raise RuntimeError("Resource fixtures execute only in GitHub Actions")

    def fixture(self, temporary):
        root = Path(temporary)
        proc, cgroup = root / "proc", root / "cgroup"
        (proc / "self").mkdir(parents=True)
        (proc / "self/cgroup").write_text("0::/worker\n", encoding="ascii")
        (proc / "meminfo").write_text("MemTotal: 8388608 kB\n", encoding="ascii")
        worker = cgroup / "worker"
        worker.mkdir(parents=True)
        for folder, cpu, memory in ((cgroup, "600000 100000", 6 * resources.GIB),
                                    (worker, "400000 100000", 4 * resources.GIB)):
            (folder / "cpu.max").write_text(cpu, encoding="ascii")
            (folder / "memory.max").write_text(str(memory), encoding="ascii")
            (folder / "memory.swap.max").write_text("0", encoding="ascii")
        return proc, cgroup, worker

    def limits(self, proc, cgroup):
        with patch.object(resources.platform, "system", return_value="Linux"), \
                patch.object(resources.os, "cpu_count", return_value=8):
            return resources.host_limits(proc_root=proc, cgroup_root=cgroup, affinity=range(8))

    def test_host_limits_respect_enclosing_quotas_and_affinity_before_halving(self):
        with tempfile.TemporaryDirectory() as temporary:
            proc, cgroup, _ = self.fixture(temporary)
            limits = self.limits(proc, cgroup)
        self.assertEqual(limits["cpu_micros"], 2_000_000)
        self.assertEqual(limits["memory_bytes"], 2 * resources.GIB)
        self.assertEqual(limits["maximum_workers"], 2)
        self.assertEqual(limits["scope"], "parent_and_all_descendants_one_cgroup")

    def test_genuine_host_root_without_limit_files_uses_physical_memory_and_affinity(self):
        with tempfile.TemporaryDirectory() as temporary:
            proc, cgroup, _ = self.fixture(temporary)
            (proc / "self/cgroup").write_text("0::/\n", encoding="ascii")
            (cgroup / "cpu.max").unlink()
            (cgroup / "memory.max").unlink()
            limits = self.limits(proc, cgroup)
            self.assertEqual(limits["cpu_micros"], 4_000_000)
            self.assertEqual(limits["memory_bytes"], 4 * resources.GIB)
            # The constrained worker check still rejects this uncapped root.
            limits["cpuset_cpus"] = [0, 1, 2, 3]
            with patch.dict(os.environ, {"GITHUB_ACTIONS": "true", resources.ENVIRONMENT: json.dumps(limits)}, clear=True), \
                    patch.object(resources.platform, "system", return_value="Linux"):
                with self.assertRaisesRegex(ValueError, "controllers"):
                    resources.require_enclosure(proc_root=proc, cgroup_root=cgroup)

    def test_container_command_encloses_parent_and_descendants_with_no_swap(self):
        with tempfile.TemporaryDirectory() as temporary, patch.dict(os.environ, {}, clear=True):
            proc, cgroup, _ = self.fixture(temporary)
            limits = self.limits(proc, cgroup)
            command = resources.launch_command(["sh", "-ec", "python -m study"], temporary, limits, image=IMAGE)
        self.assertEqual(command[command.index("--cpus") + 1], "2.000000")
        self.assertEqual(command[command.index("--cpuset-cpus") + 1], "0,1")
        self.assertEqual(command[command.index("--memory") + 1], str(2 * resources.GIB))
        self.assertEqual(command[command.index("--memory-swap") + 1], str(2 * resources.GIB))
        self.assertIn("--init", command)
        self.assertEqual(command[-4:], [IMAGE, "sh", "-ec", "python -m study"])
        receipt = next(value.split("=", 1)[1] for value in command if value.startswith(resources.ENVIRONMENT + "="))
        self.assertEqual(json.loads(receipt)["cpuset_cpus"], [0, 1])

    def test_pinned_digest_and_half_resource_ceilings_are_required(self):
        with tempfile.TemporaryDirectory() as temporary, patch.dict(os.environ, {}, clear=True):
            proc, cgroup, _ = self.fixture(temporary)
            limits = self.limits(proc, cgroup)
            with self.assertRaises(ValueError):
                resources.launch_command(["python"], temporary, limits, image="python:latest")
            for field in ("cpu_micros", "memory_bytes"):
                changed = deepcopy(limits)
                changed[field] *= 2
                with self.subTest(field=field), self.assertRaises(ValueError):
                    resources.launch_command(["python"], temporary, changed, image=IMAGE)

    def test_enclosure_checks_kernel_controllers_instead_of_trusting_environment(self):
        with tempfile.TemporaryDirectory() as temporary:
            proc, cgroup, worker = self.fixture(temporary)
            limits = self.limits(proc, cgroup)
            limits["cpuset_cpus"] = [0, 1]
            (worker / "cpu.max").write_text("200000 100000", encoding="ascii")
            (worker / "memory.max").write_text(str(resources.GIB), encoding="ascii")
            environment = {"GITHUB_ACTIONS": "true", resources.ENVIRONMENT: json.dumps(limits)}
            with patch.dict(os.environ, environment, clear=True), \
                    patch.object(resources.platform, "system", return_value="Linux"), \
                    patch.object(resources.os, "sched_getaffinity", return_value={0, 1}):
                receipt = resources.require_enclosure(workers=2, proc_root=proc, cgroup_root=cgroup)
                self.assertEqual(receipt["status"], "VERIFIED_KERNEL_PROCESS_TREE_LIMITS")
                (worker / "cpu.max").write_text("300000 100000", encoding="ascii")
                with self.assertRaises(ValueError):
                    resources.require_enclosure(proc_root=proc, cgroup_root=cgroup)
                (worker / "cpu.max").write_text("200000 100000", encoding="ascii")
                (worker / "memory.swap.max").write_text("1024", encoding="ascii")
                with self.assertRaises(ValueError):
                    resources.require_enclosure(proc_root=proc, cgroup_root=cgroup)

    def test_missing_receipt_and_more_than_two_workers_fail_closed(self):
        with patch.dict(os.environ, {"GITHUB_ACTIONS": "true"}, clear=True), \
                patch.object(resources.platform, "system", return_value="Linux"):
            with self.assertRaisesRegex(ValueError, "receipt is absent"):
                resources.require_enclosure()
            with self.assertRaisesRegex(ValueError, "at most two"):
                resources.require_enclosure(workers=3)


if __name__ == "__main__":
    unittest.main()
