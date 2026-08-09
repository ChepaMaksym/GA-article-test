#!/usr/bin/env python3
"""Bind an Octave fixture audit to the authenticated Python artifact report."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import stat
import sys
from pathlib import Path
from typing import Any


PYTHON_ENV = Path(__file__).resolve().parent
sys.path.insert(0, str(PYTHON_ENV))

from eu2614.canonical import (  # noqa: E402
    bind_report,
    verify_report_digest,
    write_new_json,
)
from eu2614.contract import CONTRACT_SHA256, load_contract  # noqa: E402
from eu2614.errors import VerificationError  # noqa: E402
from eu2614.hashing import open_parent_nofollow  # noqa: E402


_MAX_REPORT_BYTES = 2 * 1024 * 1024
_PYTHON_TOP_LEVEL = {
    "schema_version",
    "candidate_id",
    "status",
    "paper_mapping",
    "contract",
    "overall_gate",
    "source_native_gate",
    "zenodo",
    "checksum_manifest",
    "source",
    "result_archive",
    "safe_endpoint",
    "fixture",
    "frozen_endpoint",
    "documented_conflicts",
    "forbidden_claims",
    "report_digest",
}


def _payload(path: Path) -> bytes:
    """Read one bounded regular report through a retained no-symlink path."""
    flags = (
        os.O_RDONLY
        | getattr(os, "O_CLOEXEC", 0)
        | getattr(os, "O_NOFOLLOW", 0)
        | getattr(os, "O_NONBLOCK", 0)
    )
    with open_parent_nofollow(path, label="report input") as (absolute, parent_fd, leaf):
        try:
            before = os.stat(leaf, dir_fd=parent_fd, follow_symlinks=False)
            if stat.S_ISLNK(before.st_mode) or not stat.S_ISREG(before.st_mode):
                raise VerificationError(
                    f"report {path} must be a regular non-symlink file"
                )
            descriptor = os.open(leaf, flags, dir_fd=parent_fd)
        except OSError as error:
            raise VerificationError(f"cannot securely open report {path}: {error}") from error
        try:
            opened = os.fstat(descriptor)
            if not stat.S_ISREG(opened.st_mode):
                raise VerificationError(f"report {path} must be a regular non-symlink file")
            if (before.st_dev, before.st_ino) != (opened.st_dev, opened.st_ino):
                raise VerificationError(f"report {path} changed during open")
            with os.fdopen(descriptor, "rb", closefd=False) as stream:
                payload = stream.read(_MAX_REPORT_BYTES + 1)
            if len(payload) > _MAX_REPORT_BYTES:
                raise VerificationError(f"report {path} exceeds the byte limit")
            after = os.fstat(descriptor)
            if (
                opened.st_dev,
                opened.st_ino,
                opened.st_mode,
                opened.st_size,
                opened.st_mtime_ns,
                opened.st_ctime_ns,
            ) != (
                after.st_dev,
                after.st_ino,
                after.st_mode,
                after.st_size,
                after.st_mtime_ns,
                after.st_ctime_ns,
            ):
                raise VerificationError(f"report {path} changed during read")
            current = os.stat(leaf, dir_fd=parent_fd, follow_symlinks=False)
            if stat.S_ISLNK(current.st_mode) or (current.st_dev, current.st_ino) != (
                opened.st_dev,
                opened.st_ino,
            ):
                raise VerificationError(f"report {path} path was replaced")
            with open_parent_nofollow(absolute, label="report input") as (
                _,
                resolved_parent_fd,
                resolved_leaf,
            ):
                retained_parent = os.fstat(parent_fd)
                resolved_parent = os.fstat(resolved_parent_fd)
                if (retained_parent.st_dev, retained_parent.st_ino) != (
                    resolved_parent.st_dev,
                    resolved_parent.st_ino,
                ):
                    raise VerificationError(f"report {path} parent path was replaced")
                resolved = os.stat(
                    resolved_leaf,
                    dir_fd=resolved_parent_fd,
                    follow_symlinks=False,
                )
                if stat.S_ISLNK(resolved.st_mode) or (
                    resolved.st_dev,
                    resolved.st_ino,
                ) != (opened.st_dev, opened.st_ino):
                    raise VerificationError(f"report {path} path was replaced")
            return payload
        except VerificationError:
            raise
        except OSError as error:
            raise VerificationError(f"cannot read report {path}: {error}") from error
        finally:
            os.close(descriptor)


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            raise VerificationError(f"report contains duplicate JSON key: {key}")
        value[key] = item
    return value


def _reject_json_constant(value: str) -> Any:
    raise VerificationError(f"report contains non-standard JSON constant: {value}")


def _object(path: Path) -> tuple[dict[str, Any], str]:
    payload = _payload(path)
    try:
        value = json.loads(
            payload.decode("utf-8"),
            object_pairs_hook=_unique_object,
            parse_constant=_reject_json_constant,
        )
    except (UnicodeError, json.JSONDecodeError) as error:
        raise VerificationError(f"cannot read report {path}: {error}") from error
    if not isinstance(value, dict):
        raise VerificationError(f"report {path} must be an object")
    return value, hashlib.sha256(payload).hexdigest()


def _field(value: dict[str, Any], *path: str) -> Any:
    current: Any = value
    try:
        for component in path:
            if not isinstance(current, dict):
                raise KeyError(component)
            current = current[component]
    except KeyError as error:
        raise VerificationError(f"report field is missing: {'.'.join(path)}") from error
    return current


def _same_json(actual: Any, expected: Any, *, label: str) -> None:
    """Compare JSON values without Python bool/int/float type confusion."""
    if type(actual) is not type(expected):
        raise VerificationError(f"{label} type differs")
    if isinstance(expected, dict):
        if set(actual) != set(expected):
            raise VerificationError(f"{label} schema differs")
        for key in expected:
            _same_json(actual[key], expected[key], label=f"{label}.{key}")
    elif isinstance(expected, list):
        if len(actual) != len(expected):
            raise VerificationError(f"{label} length differs")
        for index, (observed, frozen) in enumerate(zip(actual, expected, strict=True)):
            _same_json(observed, frozen, label=f"{label}[{index}]")
    elif actual != expected:
        raise VerificationError(f"{label} differs")


def _python_projection(report: dict[str, Any]) -> dict[str, Any]:
    try:
        zenodo_files = _field(report, "zenodo", "files")
        return {
            "schema_version": report["schema_version"],
            "candidate_id": report["candidate_id"],
            "status": report["status"],
            "paper_mapping": report["paper_mapping"],
            "contract": report["contract"],
            "overall_gate": report["overall_gate"],
            "source_native_gate": report["source_native_gate"],
            "zenodo": {
                "gate": _field(report, "zenodo", "gate"),
                "record_id": _field(report, "zenodo", "record_id"),
                "doi": _field(report, "zenodo", "doi"),
                "version": _field(report, "zenodo", "version"),
                "license": _field(report, "zenodo", "license"),
                "files": {
                    name: zenodo_files[name]
                    for name in ("SHA256SUMS", "source.tar.gz", "msc_cec2020.tar.zst")
                },
            },
            "checksum_manifest": {
                "gate": _field(report, "checksum_manifest", "gate"),
                "identity": _field(report, "checksum_manifest", "identity"),
                "result_sha256": _field(
                    report, "checksum_manifest", "entries", "msc_cec2020.tar.zst"
                ),
            },
            "source": {
                "gate": _field(report, "source", "gate"),
                "identity": _field(report, "source", "identity"),
                "archive_root": _field(report, "source", "archive_root"),
                "upstream_commit": _field(report, "source", "upstream_commit"),
            },
            "result_archive": {
                "gate": _field(report, "result_archive", "gate"),
                "identity": _field(report, "result_archive", "identity"),
                "member": {
                    "path": _field(report, "result_archive", "member", "path"),
                    "data_offset": _field(
                        report, "result_archive", "member", "data_offset"
                    ),
                    "bytes": _field(report, "result_archive", "member", "bytes"),
                    "sha256": _field(report, "result_archive", "member", "sha256"),
                },
            },
            "safe_endpoint": {
                "safe_pickle_gate": _field(report, "safe_endpoint", "safe_pickle_gate"),
                "endpoint_gate": _field(report, "safe_endpoint", "endpoint_gate"),
                "symbolic_globals": _field(report, "safe_endpoint", "symbolic_globals"),
                "runs_checked": _field(report, "safe_endpoint", "protocol", "runs_checked"),
                "seeds_contiguous": _field(
                    report, "safe_endpoint", "protocol", "seeds_contiguous"
                ),
                "cycles_contiguous": _field(
                    report, "safe_endpoint", "protocol", "cycles_contiguous"
                ),
            },
            "fixture": report["fixture"],
            "frozen_endpoint": report["frozen_endpoint"],
            "documented_conflicts": report["documented_conflicts"],
            "forbidden_claims": report["forbidden_claims"],
        }
    except (KeyError, TypeError) as error:
        raise VerificationError(f"Python report schema differs: {error}") from error


def _expected_python_projection(contract: dict[str, Any]) -> dict[str, Any]:
    files = contract["files"]
    member = contract["member"]
    run0 = contract["endpoint"]["run0"]
    identities = {
        name: {key: files[name][key] for key in ("bytes", "md5", "sha256")}
        for name in ("SHA256SUMS", "source.tar.gz", "msc_cec2020.tar.zst")
    }
    return {
        "schema_version": "1.0.0",
        "candidate_id": "EU26-14",
        "status": contract["status"],
        "paper_mapping": contract["paper_mapping"],
        "contract": {
            "schema_version": contract["schema_version"],
            "sha256": CONTRACT_SHA256,
            "amendments": contract["amendments"],
        },
        "overall_gate": "PASS_TARGETED_ARTIFACT_REPLAY",
        "source_native_gate": "NOT_ATTEMPTED_OUT_OF_SCOPE",
        "zenodo": {
            "gate": "PASS_ZENODO_METADATA",
            "record_id": contract["zenodo"]["record_id"],
            "doi": contract["zenodo"]["doi"],
            "version": contract["zenodo"]["version"],
            "license": contract["zenodo"]["license"],
            "files": {
                name: {key: files[name][key] for key in ("bytes", "md5", "url")}
                for name in ("SHA256SUMS", "source.tar.gz", "msc_cec2020.tar.zst")
            },
        },
        "checksum_manifest": {
            "gate": "PASS_CHECKSUM_MANIFEST",
            "identity": identities["SHA256SUMS"],
            "result_sha256": files["msc_cec2020.tar.zst"]["sha256"],
        },
        "source": {
            "gate": "PASS_SOURCE_IDENTITY",
            "identity": identities["source.tar.gz"],
            "archive_root": contract["upstream"]["archive_root"],
            "upstream_commit": contract["upstream"]["commit"],
        },
        "result_archive": {
            "gate": "PASS_FULL_ARCHIVE_IDENTITY",
            "identity": identities["msc_cec2020.tar.zst"],
            "member": {
                "path": member["path"],
                "data_offset": member["tar_data_offset"],
                "bytes": member["bytes"],
                "sha256": member["sha256"],
            },
        },
        "safe_endpoint": {
            "safe_pickle_gate": "PASS_SAFE_PICKLE_PARSE",
            "endpoint_gate": "PASS_FROZEN_ENDPOINT",
            "symbolic_globals": contract["safe_pickle"]["allowed_globals"],
            "runs_checked": contract["endpoint"]["n_runs"],
            "seeds_contiguous": True,
            "cycles_contiguous": True,
        },
        "fixture": {
            "gate": "PASS_COMMITTED_FIXTURE",
            "json_path": "fixtures/frozen_endpoint.json",
            "csv_path": "fixtures/run0_cycles.csv",
            "digest": contract["cross_language"]["fixture_digest"],
        },
        "frozen_endpoint": {
            "seed": 0,
            "error": run0["error"],
            "improvements_shape": run0["improvements_shape"],
            "first_improvement": run0["first_improvement"],
            "last_improvement": run0["last_improvement"],
            "cycles": run0["cycle_count"],
            "pre_refine_error": run0["pre_refine_error"],
            "nfev_pre_refine": run0["nfev_pre_refine"],
            "nfev_total": run0["nfev_total"],
        },
        "documented_conflicts": contract["documented_conflicts"],
        "forbidden_claims": contract["forbidden_claims"],
    }


def _expected_octave(contract: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": "1.0.0",
        "candidate_id": "EU26-14",
        "status": contract["status"],
        "paper_mapping": contract["paper_mapping"],
        "cross_language_gate": "PASS_CROSS_LANGUAGE_CONTROLS",
        "seed_count": 51,
        "cycle_count": 30,
        "reused_cycle_count": 15,
        "zero_eval_reused_cycle_count": 1,
        "final_cycle_nfev": "2876679",
        "run0_nfev_total": "2893419",
        "unspent_evaluations": "106581",
        "static_assert_call_sites": contract["cross_language"][
            "octave_static_assert_call_sites"
        ],
        "fixture_json_sha256": contract["cross_language"]["fixture_json_sha256"],
        "fixture_csv_sha256": contract["cross_language"]["fixture_csv_sha256"],
        "source_archive_sha256": contract["files"]["source.tar.gz"]["sha256"],
        "result_archive_sha256": contract["files"]["msc_cec2020.tar.zst"]["sha256"],
        "member_sha256": contract["member"]["sha256"],
        "member_bytes": str(contract["member"]["bytes"]),
        "member_data_offset": str(contract["member"]["tar_data_offset"]),
        "forbidden_claim_count": len(contract["forbidden_claims"]),
    }


def finalize_reports(
    python_report: dict[str, Any],
    octave_report: dict[str, Any],
    *,
    python_report_sha256: str,
    octave_report_sha256: str,
    contract: dict[str, Any],
) -> dict[str, Any]:
    for label, digest in (
        ("Python report SHA-256", python_report_sha256),
        ("Octave report SHA-256", octave_report_sha256),
    ):
        if (
            type(digest) is not str
            or len(digest) != 64
            or any(character not in "0123456789abcdef" for character in digest)
        ):
            raise VerificationError(f"{label} format differs")
    if set(python_report) != _PYTHON_TOP_LEVEL:
        raise VerificationError("Python report top-level schema differs")
    verify_report_digest(
        python_report,
        domain=contract["cross_language"]["python_report_domain"].encode("ascii"),
    )
    _same_json(
        _python_projection(python_report),
        _expected_python_projection(contract),
        label="Python report",
    )
    expected_octave = _expected_octave(contract)
    _same_json(octave_report, expected_octave, label="Octave report")
    return bind_report(
        {
            "schema_version": "1.0.0",
            "candidate_id": "EU26-14",
            "status": contract["status"],
            "paper_mapping": contract["paper_mapping"],
            "contract_sha256": python_report["contract"]["sha256"],
            "cross_language_gate": "PASS_CROSS_LANGUAGE_CONTROLS",
            "python_report_digest": python_report["report_digest"],
            "python_report_sha256": python_report_sha256,
            "octave_report_sha256": octave_report_sha256,
            "octave_static_assert_call_sites": octave_report[
                "static_assert_call_sites"
            ],
            "fixture_json_sha256": octave_report["fixture_json_sha256"],
            "fixture_csv_sha256": octave_report["fixture_csv_sha256"],
            "fixture_digest": contract["cross_language"]["fixture_digest"],
            "seed_count": 51,
            "cycle_count": 30,
            "run0_nfev_total": 2893419,
            "unspent_evaluations": 106581,
            "source_native_gate": "NOT_ATTEMPTED_OUT_OF_SCOPE",
            "forbidden_claims": contract["forbidden_claims"],
        },
        domain=contract["cross_language"]["cross_language_report_domain"].encode(
            "ascii"
        ),
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--python-report", required=True, type=Path)
    parser.add_argument("--octave-report", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if args.output.exists() or args.output.is_symlink():
        parser.error("--output must be a new path")
    contract = load_contract()
    python_report, python_sha256 = _object(args.python_report)
    octave_report, octave_sha256 = _object(args.octave_report)
    report = finalize_reports(
        python_report,
        octave_report,
        python_report_sha256=python_sha256,
        octave_report_sha256=octave_sha256,
        contract=contract,
    )
    write_new_json(args.output, report)
    print(report["cross_language_gate"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
