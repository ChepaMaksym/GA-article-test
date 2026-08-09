from __future__ import annotations

import copy
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from eu2614.canonical import bind_report
from eu2614.contract import load_contract
from eu2614.errors import VerificationError
from finalize_cross_language import (
    _expected_octave,
    _expected_python_projection,
    _object,
    finalize_reports,
)


def _valid_python_report() -> dict[str, object]:
    contract = load_contract()
    expected = _expected_python_projection(contract)
    report: dict[str, object] = {
        "schema_version": expected["schema_version"],
        "candidate_id": expected["candidate_id"],
        "status": expected["status"],
        "paper_mapping": expected["paper_mapping"],
        "contract": expected["contract"],
        "overall_gate": expected["overall_gate"],
        "source_native_gate": expected["source_native_gate"],
        "zenodo": expected["zenodo"],
        "checksum_manifest": {
            "gate": expected["checksum_manifest"]["gate"],
            "identity": expected["checksum_manifest"]["identity"],
            "entries": {
                "msc_cec2020.tar.zst": expected["checksum_manifest"]["result_sha256"]
            },
        },
        "source": expected["source"],
        "result_archive": expected["result_archive"],
        "safe_endpoint": {
            "safe_pickle_gate": expected["safe_endpoint"]["safe_pickle_gate"],
            "endpoint_gate": expected["safe_endpoint"]["endpoint_gate"],
            "symbolic_globals": expected["safe_endpoint"]["symbolic_globals"],
            "protocol": {
                "runs_checked": expected["safe_endpoint"]["runs_checked"],
                "seeds_contiguous": expected["safe_endpoint"]["seeds_contiguous"],
                "cycles_contiguous": expected["safe_endpoint"]["cycles_contiguous"],
            },
        },
        "fixture": expected["fixture"],
        "frozen_endpoint": expected["frozen_endpoint"],
        "documented_conflicts": expected["documented_conflicts"],
        "forbidden_claims": expected["forbidden_claims"],
    }
    return bind_report(
        report,
        domain=contract["cross_language"]["python_report_domain"].encode("ascii"),
    )


def _rebind(report: dict[str, object]) -> dict[str, object]:
    contract = load_contract()
    unbound = copy.deepcopy(report)
    unbound.pop("report_digest", None)
    return bind_report(
        unbound,
        domain=contract["cross_language"]["python_report_domain"].encode("ascii"),
    )


def _finalize(
    python_report: dict[str, object], octave_report: dict[str, object]
) -> dict[str, object]:
    return finalize_reports(
        python_report,
        octave_report,
        python_report_sha256="a" * 64,
        octave_report_sha256="b" * 64,
        contract=load_contract(),
    )


class CrossLanguageBindingTests(unittest.TestCase):
    def test_exact_reports_bind(self) -> None:
        report = _finalize(_valid_python_report(), _expected_octave(load_contract()))
        self.assertEqual(report["cross_language_gate"], "PASS_CROSS_LANGUAGE_CONTROLS")
        self.assertEqual(report["octave_static_assert_call_sites"], 48)
        self.assertEqual(report["python_report_sha256"], "a" * 64)
        self.assertTrue(str(report["report_digest"]).startswith("sha256:"))

    def test_forged_python_digest_is_rejected(self) -> None:
        report = _valid_python_report()
        report["report_digest"] = "NOT_A_DIGEST"
        with self.assertRaisesRegex(VerificationError, "digest format"):
            _finalize(report, _expected_octave(load_contract()))

    def test_recomputed_digest_cannot_hide_missing_nested_gate(self) -> None:
        report = _valid_python_report()
        report["source"]["gate"] = "PASS_SOURCE_IDENTITY_FORGED"  # type: ignore[index]
        with self.assertRaisesRegex(VerificationError, "Python report.source.gate"):
            _finalize(_rebind(report), _expected_octave(load_contract()))

    def test_recomputed_digest_cannot_remove_forbidden_claim(self) -> None:
        report = _valid_python_report()
        report["forbidden_claims"] = report["forbidden_claims"][:-1]  # type: ignore[index]
        with self.assertRaisesRegex(VerificationError, "forbidden_claims"):
            _finalize(_rebind(report), _expected_octave(load_contract()))

    def test_octave_wrong_static_assert_count_is_rejected(self) -> None:
        octave = _expected_octave(load_contract())
        octave["static_assert_call_sites"] = 0
        with self.assertRaisesRegex(
            VerificationError, "Octave report.static_assert_call_sites"
        ):
            _finalize(_valid_python_report(), octave)

    def test_octave_static_assert_count_matches_source(self) -> None:
        source = (
            Path(__file__).resolve().parents[1] / "octave" / "eu2614_verify_fixture.m"
        ).read_text(encoding="utf-8")
        expected = load_contract()["cross_language"]["octave_static_assert_call_sites"]
        self.assertEqual(source.count("assert("), expected)

    def test_octave_fixture_identity_is_bound(self) -> None:
        octave = _expected_octave(load_contract())
        octave["fixture_json_sha256"] = "0" * 64
        with self.assertRaisesRegex(VerificationError, "fixture_json_sha256"):
            _finalize(_valid_python_report(), octave)

    def test_octave_numeric_type_confusion_is_rejected(self) -> None:
        octave = _expected_octave(load_contract())
        octave["member_bytes"] = False
        with self.assertRaisesRegex(VerificationError, "member_bytes type"):
            _finalize(_valid_python_report(), octave)

    def test_octave_extra_field_is_rejected(self) -> None:
        octave = _expected_octave(load_contract())
        octave["forged"] = "PASS"
        with self.assertRaisesRegex(VerificationError, "schema differs"):
            _finalize(_valid_python_report(), octave)

    def test_report_read_rejects_symlinked_parent(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            real = root / "real"
            real.mkdir()
            report = real / "report.json"
            report.write_text("{}", encoding="utf-8")
            via = root / "via"
            via.symlink_to(real, target_is_directory=True)
            with self.assertRaisesRegex(VerificationError, "traverse parent"):
                _object(via / "report.json")

    def test_report_read_rejects_top_level_duplicate_key(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "duplicate.json"
            path.write_text('{"status":"PASS_FULL","status":"safe"}', encoding="utf-8")
            with self.assertRaisesRegex(VerificationError, "duplicate JSON key: status"):
                _object(path)

    def test_report_read_rejects_nested_duplicate_key(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "duplicate.json"
            path.write_text(
                '{"nested":{"gate":"PASS_FULL","gate":"safe"}}',
                encoding="utf-8",
            )
            with self.assertRaisesRegex(VerificationError, "duplicate JSON key: gate"):
                _object(path)

    def test_report_read_rejects_nonstandard_json_constant(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "nan.json"
            path.write_text('{"value":NaN}', encoding="utf-8")
            with self.assertRaisesRegex(VerificationError, "non-standard JSON constant"):
                _object(path)

    def test_report_read_rejects_fifo_before_open(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "report.fifo"
            os.mkfifo(path)
            with self.assertRaisesRegex(VerificationError, "regular non-symlink"):
                _object(path)

    def test_report_read_rejects_regular_to_fifo_open_race(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "report.json"
            path.write_text("{}", encoding="utf-8")
            real_open = os.open
            swapped = False

            def replace_before_leaf_open(
                target: str | bytes | os.PathLike[str] | os.PathLike[bytes],
                flags: int,
                mode: int = 0o777,
                *,
                dir_fd: int | None = None,
            ) -> int:
                nonlocal swapped
                if target == "report.json" and dir_fd is not None and not swapped:
                    os.unlink(target, dir_fd=dir_fd)
                    os.mkfifo(target, dir_fd=dir_fd)
                    swapped = True
                return real_open(target, flags, mode, dir_fd=dir_fd)

            with mock.patch("finalize_cross_language.os.open", replace_before_leaf_open):
                with self.assertRaisesRegex(VerificationError, "regular non-symlink"):
                    _object(path)
            self.assertTrue(swapped)

    def test_report_read_rejects_device_before_open(self) -> None:
        device = Path("/dev/null")
        if not device.exists():
            self.skipTest("/dev/null is unavailable")
        with self.assertRaisesRegex(VerificationError, "regular non-symlink"):
            _object(device)


if __name__ == "__main__":
    unittest.main()
