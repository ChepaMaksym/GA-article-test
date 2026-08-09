#!/usr/bin/env python3
"""Run the EU26-11 fail-closed Python suite."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path


CANDIDATE = Path(__file__).resolve().parents[1]
PYTHON_ENV = CANDIDATE / "environments" / "python"
TESTS = Path(__file__).resolve().parent / "python"
sys.path.insert(0, str(PYTHON_ENV))


def source_manifest_digest() -> tuple[int, int, str]:
    paths = sorted(
        [
            *PYTHON_ENV.rglob("*.py"),
            *TESTS.rglob("*.py"),
            Path(__file__).resolve(),
            CANDIDATE / "config" / "verification_contract.json",
        ],
        key=lambda path: path.relative_to(CANDIDATE).as_posix(),
    )
    unique_paths = list(dict.fromkeys(paths))
    digest = hashlib.sha256(b"EU26-11-FAIL-CLOSED-SUITE-V1\0")
    total_bytes = 0
    for path in unique_paths:
        payload = path.read_bytes()
        total_bytes += len(payload)
        relative = path.relative_to(CANDIDATE).as_posix()
        digest.update(
            f"{relative},{len(payload)},{hashlib.sha256(payload).hexdigest()}\n".encode("ascii")
        )
    return len(unique_paths), total_bytes, digest.hexdigest()


def write_new_json(path: Path, value: dict) -> None:
    if path.exists() or path.is_symlink():
        raise ValueError("--output must be a new path")
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(value, allow_nan=False, indent=2, sort_keys=True) + "\n"
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="ascii") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    except BaseException:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass
        raise


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.output is not None and (args.output.exists() or args.output.is_symlink()):
        parser.error("--output must be a new path")

    suite = unittest.defaultTestLoader.discover(str(TESTS), pattern="test_*.py")
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    contract = json.loads(
        (CANDIDATE / "config" / "verification_contract.json").read_text(encoding="utf-8")
    )
    member_count, source_bytes, source_digest = source_manifest_digest()
    complete = (
        result.wasSuccessful()
        and result.testsRun >= contract["verification_execution"]["minimum_python_tests"]
        and len(result.skipped) == 0
    )
    report = {
        "schema_version": "1.0.0",
        "candidate_id": "EU26-11",
        "status": "PASS_FAIL_CLOSED_SUITE" if complete else "FAIL_OR_INCOMPLETE",
        "tests_run": result.testsRun,
        "failures": len(result.failures),
        "errors": len(result.errors),
        "skipped": len(result.skipped),
        "source_manifest": {
            "member_count": member_count,
            "bytes": source_bytes,
            "digest": source_digest,
        },
    }
    report_payload = json.dumps(
        report, allow_nan=False, ensure_ascii=True, separators=(",", ":"), sort_keys=True
    ).encode("ascii")
    report["report_digest"] = hashlib.sha256(
        b"EU26-11-FAIL-CLOSED-REPORT-V1\0" + report_payload
    ).hexdigest()
    if args.output is not None:
        write_new_json(args.output.resolve(), report)
    return 0 if complete else 1


if __name__ == "__main__":
    raise SystemExit(main())
