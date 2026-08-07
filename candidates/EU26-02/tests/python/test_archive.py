from __future__ import annotations

import io
import copy
import csv
import json
import statistics
import tarfile
import tempfile
import unittest
from fractions import Fraction
from pathlib import Path

from aheadverify.archive import (
    ArchiveValidationError,
    aggregate_results,
    validate_instance,
)
from aheadverify.canonical import canonical_sha256


METADATA_HEADER = (
    "#date,problem,instance,nb_colors,use_target,rand_seed,objective,"
    "time_limit,max_iterations,parameters"
)
CANDIDATE = Path(__file__).resolve().parents[2]
PARAMETERS = json.loads(
    (CANDIDATE / "config" / "ahead_deleter_optimizer_config.json").read_text(
        encoding="utf-8"
    )
)


def csv_payload(
    instance: str,
    seed: int,
    colors: int,
    time_seconds: int,
    *,
    time_limit: int = 10800,
    legal: bool = True,
    restart: bool = False,
) -> bytes:
    penalty = 0 if legal else 1
    lines = [
        METADATA_HEADER,
        (
            f"#2023-10-17 00:00:00,gcp,{instance},{colors},true,{seed},"
            f"{time_limit},3600,{json.dumps(PARAMETERS, separators=(',', ':'))}"
        ),
        "turn,time,nb_uncolored,penalty,nb_colors,solution",
        f"0,0,0,1,{colors},0:1:2",
    ]
    if restart:
        lines.append("restart")
    lines.extend(
        [
            f"10,{time_seconds},0,{penalty},{colors},0:1:2",
            "#2023-10-17 01:00:00",
        ]
    )
    return ("\n".join(lines) + "\n").encode("utf-8")


def add_bytes(archive: tarfile.TarFile, name: str, payload: bytes) -> None:
    info = tarfile.TarInfo(name)
    info.size = len(payload)
    archive.addfile(info, io.BytesIO(payload))


def make_archive(
    directory: Path,
    instance: str = "C2000.9",
    *,
    duplicate_seed: bool = False,
    wrong_time_limit: bool = False,
    over_cutoff_seed: int | None = None,
    unsafe_member: bool = False,
    rounding_boundary: bool = False,
) -> Path:
    path = directory / "synthetic.tgz"
    if instance == "C2000.9":
        colors = [404, 404] + [405] * 4 + [406] * 14
        times = [2987, 2989] + [100] * 18
    elif instance == "r250.5":
        colors = [66] * 20
        times = [550] * 19 + ([549] if rounding_boundary else [546])
    else:
        raise AssertionError(instance)
    with tarfile.open(path, "w:gz") as archive:
        for seed, (score, elapsed) in enumerate(zip(colors, times)):
            if over_cutoff_seed == seed:
                elapsed = 4001
            add_bytes(
                archive,
                f"root/deleter/{instance}_{seed}_{score}.csv",
                csv_payload(
                    instance,
                    seed,
                    score,
                    elapsed,
                    time_limit=3600 if wrong_time_limit and seed == 0 else 10800,
                    restart=seed == 0,
                ),
            )
        if duplicate_seed:
            add_bytes(
                archive,
                f"root/deleter/{instance}_0_{colors[0]}_duplicate.csv",
                csv_payload(instance, 0, colors[0], times[0]),
            )
        if unsafe_member:
            add_bytes(archive, "../escape.csv", b"unsafe")
    return path


class ArchiveParserTests(unittest.TestCase):
    def test_focus_cell_exact_and_restart_is_reported(self):
        with tempfile.TemporaryDirectory() as directory:
            archive = make_archive(Path(directory))
            row = validate_instance(archive, "C2000.9")
        self.assertEqual(row["calculated"]["best"], 404)
        self.assertEqual(row["calculated"]["mean"], 405.6)
        self.assertEqual(
            row["calculated"]["displayed_mean_best_time_seconds"], 2988
        )
        self.assertTrue(all(row["published_cell_matches"].values()))
        self.assertEqual(row["retained_seeds"], list(range(20)))
        self.assertEqual(row["files_with_restart"], 1)
        self.assertEqual(row["restart_lines"], 1)
        self.assertEqual(row["metadata_shifted_header_files"], 20)

    def test_article_time_rounds_then_converts_to_integer(self):
        with tempfile.TemporaryDirectory() as directory:
            archive = make_archive(Path(directory), "r250.5")
            row = validate_instance(archive, "r250.5")
        exact = row["calculated"]["mean_best_time_exact"]
        self.assertEqual((exact["numerator"], exact["denominator"]), (2749, 5))
        self.assertEqual(row["calculated"]["mean_best_time_rounded_one_decimal"], 549.8)
        self.assertEqual(row["calculated"]["displayed_mean_best_time_seconds"], 549)
        self.assertTrue(all(row["published_cell_matches"].values()))

    def test_rounding_precedes_integer_conversion(self):
        with tempfile.TemporaryDirectory() as directory:
            archive = make_archive(
                Path(directory), "r250.5", rounding_boundary=True
            )
            row = validate_instance(archive, "r250.5")
        exact = row["calculated"]["mean_best_time_exact"]
        self.assertEqual((exact["numerator"], exact["denominator"]), (10999, 20))
        self.assertEqual(
            row["calculated"]["mean_best_time_rounded_one_decimal"], 550.0
        )
        self.assertEqual(row["calculated"]["displayed_mean_best_time_seconds"], 550)
        self.assertNotEqual(
            row["calculated"]["displayed_mean_best_time_seconds"],
            int(exact["numerator"] / exact["denominator"]),
        )

    def test_cutoff_profile_is_diagnostic_and_can_drop_a_seed(self):
        with tempfile.TemporaryDirectory() as directory:
            archive = make_archive(Path(directory), over_cutoff_seed=0)
            row = validate_instance(
                archive, "C2000.9", "paper_claimed_3600_diagnostic"
            )
        self.assertEqual(row["retained_run_count"], 19)
        self.assertEqual(row["missing_seeds"], [0])
        self.assertEqual(
            row["published_cell_matches"], "NOT_APPLICABLE_DIAGNOSTIC"
        )

    def test_duplicate_legal_seed_fails(self):
        with tempfile.TemporaryDirectory() as directory:
            archive = make_archive(Path(directory), duplicate_seed=True)
            with self.assertRaisesRegex(ArchiveValidationError, "duplicate legal"):
                validate_instance(archive, "C2000.9")

    def test_wrong_header_budget_fails(self):
        with tempfile.TemporaryDirectory() as directory:
            archive = make_archive(Path(directory), wrong_time_limit=True)
            with self.assertRaisesRegex(ArchiveValidationError, "time_limit=10800"):
                validate_instance(archive, "C2000.9")

    def test_wrong_optimizer_configuration_fails(self):
        with tempfile.TemporaryDirectory() as directory:
            altered = dict(PARAMETERS)
            altered["population_size"] = 3
            path = Path(directory) / "wrong-config.tgz"
            with tarfile.open(path, "w:gz") as archive:
                payload = csv_payload("C2000.9", 0, 404, 10).replace(
                    json.dumps(PARAMETERS, separators=(",", ":")).encode(),
                    json.dumps(altered, separators=(",", ":")).encode(),
                )
                add_bytes(archive, "root/deleter/C2000.9_0_404.csv", payload)
            with self.assertRaisesRegex(
                ArchiveValidationError, "frozen Deleter configuration"
            ):
                validate_instance(path, "C2000.9")

    def test_filename_seed_mismatch_fails(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "wrong-seed.tgz"
            with tarfile.open(path, "w:gz") as archive:
                add_bytes(
                    archive,
                    "root/deleter/C2000.9_1_404.csv",
                    csv_payload("C2000.9", 0, 404, 10),
                )
            with self.assertRaisesRegex(ArchiveValidationError, "filename seed"):
                validate_instance(path, "C2000.9")

    def test_legal_row_must_match_declared_target(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "wrong-target.tgz"
            payload = csv_payload("C2000.9", 0, 404, 10).replace(
                b",C2000.9,404,true,0,", b",C2000.9,405,true,0,", 1
            )
            with tarfile.open(path, "w:gz") as archive:
                add_bytes(archive, "root/deleter/C2000.9_0_405.csv", payload)
            with self.assertRaisesRegex(ArchiveValidationError, "differs from its target"):
                validate_instance(path, "C2000.9")

    def test_unsafe_member_fails(self):
        with tempfile.TemporaryDirectory() as directory:
            archive = make_archive(Path(directory), unsafe_member=True)
            with self.assertRaisesRegex(ArchiveValidationError, "unsafe archive member"):
                validate_instance(archive, "C2000.9")

    def test_partial_aggregate_cannot_pass(self):
        with tempfile.TemporaryDirectory() as directory:
            archive = make_archive(Path(directory))
            row = validate_instance(archive, "C2000.9")
        report = aggregate_results([row])
        self.assertFalse(report["complete_31_instance_set"])
        self.assertEqual(report["status"], "FAIL_ARCHIVE_REPLAY")

    def test_aggregate_recomputes_statistics_even_with_a_fresh_digest(self):
        with tempfile.TemporaryDirectory() as directory:
            archive = make_archive(Path(directory))
            row = validate_instance(archive, "C2000.9")
        forged = copy.deepcopy(row)
        forged["calculated"]["best"] = 1
        forged.pop("canonical_digest")
        forged["canonical_digest"] = canonical_sha256(
            forged, domain="EU26-02-INSTANCE-RESULT-V1"
        )
        with self.assertRaisesRegex(ArchiveValidationError, "statistics mismatch"):
            aggregate_results([forged])

    def test_synthetic_complete_aggregate_cannot_claim_archive_identity(self):
        with (CANDIDATE / "fixtures" / "published_table2_ahead_deleter.csv").open(
            newline="", encoding="utf-8"
        ) as handle:
            targets = list(csv.DictReader(handle))
        rows = []
        for target in targets:
            best = int(target["published_best"])
            published_mean = float(target["published_mean"])
            displayed_time = int(target["published_mean_best_time_seconds"])
            excess = int(round(published_mean * 20)) - 20 * best
            quotient, remainder = divmod(excess, 19)
            colors = [best] + [
                best + quotient + (1 if index < remainder else 0)
                for index in range(19)
            ]
            self.assertEqual(round(statistics.mean(colors), 1), published_mean)
            per_seed = [
                {
                    "seed": seed,
                    "nb_colors": color,
                    "time_seconds": displayed_time,
                    "turn": 1,
                    "solution_length": 1,
                    "target_colors": color,
                    "member": f"synthetic/{target['instance']}_{seed}.csv",
                }
                for seed, color in enumerate(colors)
            ]
            exact_time = Fraction(displayed_time, 1)
            row = {
                "schema_version": "1.0.0",
                "profile": "artifact_actual_10800",
                "instance": target["instance"],
                "attempt_files": 20,
                "files_with_restart": 0,
                "restart_lines": 0,
                "metadata_shifted_header_files": 20,
                "retained_run_count": 20,
                "retained_seeds": list(range(20)),
                "missing_seeds": [],
                "per_seed": per_seed,
                "calculated": {
                    "best": best,
                    "mean": published_mean,
                    "mean_best_time_exact": {
                        "numerator": exact_time.numerator,
                        "denominator": exact_time.denominator,
                        "decimal": format(float(exact_time), ".12g"),
                    },
                    "mean_best_time_rounded_one_decimal": float(displayed_time),
                    "displayed_mean_best_time_seconds": displayed_time,
                },
                "published": {
                    "best": best,
                    "mean": published_mean,
                    "displayed_mean_best_time_seconds": displayed_time,
                },
                "published_cell_matches": {
                    "best": True,
                    "mean": True,
                    "displayed_mean_best_time": True,
                },
                "claim": "archive_to_published_table_provenance",
            }
            row["canonical_digest"] = canonical_sha256(
                row, domain="EU26-02-INSTANCE-RESULT-V1"
            )
            rows.append(row)
        result = aggregate_results(rows)
        self.assertEqual(result["status"], "PASS_AGGREGATE_EXACT")
        self.assertNotEqual(result["status"], "PASS_ARCHIVE_EXACT")


if __name__ == "__main__":
    unittest.main()
