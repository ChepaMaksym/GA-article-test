#!/usr/bin/env python3
"""Run the frozen author command in a disposable authenticated checkout."""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import os
import platform
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any


PYTHON_ENV = Path(__file__).resolve().parent
sys.path.insert(0, str(PYTHON_ENV))

from eu2609.archive import ArtifactError, first_run_difference, parse_artifact  # noqa: E402
from eu2609.canonical import bind_report, write_new_json  # noqa: E402
from eu2609.contract import load_contract, load_environment_contract  # noqa: E402
from eu2609.source import assert_same_identity, authenticate_checkout  # noqa: E402


def _run(command: list[str], *, cwd: Path | None = None, timeout: int = 1200) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(
        command,
        cwd=cwd,
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=timeout,
        env={
            **os.environ,
            "LC_ALL": "C.UTF-8",
            "TZ": "UTC",
            "PYTHONDONTWRITEBYTECODE": "1",
            "PYTHONHASHSEED": "0",
            "MPLBACKEND": "Agg",
        },
    )


def _git(checkout: Path, *args: str) -> str:
    process = _run(["git", "-C", os.fspath(checkout), *args], timeout=120)
    if process.returncode:
        detail = process.stderr.decode("utf-8", errors="replace").strip()
        raise RuntimeError(f"git {' '.join(args)} failed: {detail}")
    return process.stdout.decode("ascii", errors="strict").strip()


def _environment() -> dict[str, str]:
    return {
        "python": platform.python_version(),
        "numpy": importlib.metadata.version("numpy"),
        "scipy": importlib.metadata.version("scipy"),
        "matplotlib": importlib.metadata.version("matplotlib"),
        "platform": platform.platform(),
    }


def _base_report(contract: dict[str, Any], source: dict[str, Any], environment: dict[str, str]) -> dict[str, Any]:
    return {
        "schema_version": "1.0.0",
        "candidate_id": "EU26-09",
        "status": "TARGETED_ARTIFACT_REPLAY",
        "paper_mapping": "PAPER_FIGURE_CONTEXT_ONLY",
        "forbidden_claims": contract["forbidden_claims"],
        "historical_environment_proven": False,
        "upstream_dependency_lock_present": False,
        "source": source,
        "environment": environment,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--checkout", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--timeout-seconds", type=int, default=1200)
    args = parser.parse_args()
    if args.output.exists() or args.output.is_symlink():
        parser.error("--output must be a new path")
    if not 30 <= args.timeout_seconds <= 3600:
        parser.error("--timeout-seconds must be in 30..3600")

    contract = load_contract()
    environment_contract = load_environment_contract()
    before = authenticate_checkout(args.checkout, contract)
    environment = _environment()
    expected_environment = environment_contract["local_audit_profile"]
    observed_versions = {key: environment[key] for key in expected_environment}
    if observed_versions != expected_environment:
        report = bind_report(
            {
                **_base_report(contract, before, environment),
                "source_native_gate": "SOURCE_NATIVE_BLOCKED_ENVIRONMENT_MISMATCH",
                "expected_environment": expected_environment,
                "observed_environment": observed_versions,
            },
            domain=b"EU26-09-SOURCE-REPLAY-REPORT-V1",
        )
        write_new_json(args.output, report)
        print(report["source_native_gate"])
        return 2

    reference_path = args.checkout.resolve() / contract["raw_member"]["path"]
    reference_payload = reference_path.read_bytes()
    reference = parse_artifact(reference_payload, contract)
    started = time.monotonic()
    execution: dict[str, Any]
    replay_payload: bytes | None = None
    parse_error: str | None = None
    first_difference: dict[str, Any] | None = None

    with tempfile.TemporaryDirectory(prefix="eu26-09-source-replay-") as temporary:
        clone = Path(temporary) / "upstream"
        clone_process = _run(
            [
                "git",
                "clone",
                "--quiet",
                "--no-hardlinks",
                "--no-checkout",
                os.fspath(args.checkout.resolve()),
                os.fspath(clone),
            ],
            timeout=120,
        )
        if clone_process.returncode:
            detail = clone_process.stderr.decode("utf-8", errors="replace").strip()
            raise RuntimeError(f"disposable clone failed: {detail}")
        _git(clone, "checkout", "--quiet", "--detach", contract["upstream"]["commit"])
        if _git(clone, "rev-parse", "HEAD^{tree}") != contract["upstream"]["tree"]:
            raise RuntimeError("disposable source tree differs after checkout")
        python_code = clone / "Python-code"
        results_dir = python_code / "results"
        results_dir.mkdir()
        frozen_command = list(contract["source_native"]["command"])
        command = [sys.executable, *frozen_command[1:]]
        process = _run(command, cwd=python_code, timeout=args.timeout_seconds)
        execution = {
            "command": frozen_command,
            "returncode": process.returncode,
            "stdout_bytes": len(process.stdout),
            "stdout_sha256": hashlib.sha256(process.stdout).hexdigest(),
            "stderr_bytes": len(process.stderr),
            "stderr_sha256": hashlib.sha256(process.stderr).hexdigest(),
            "tracked_diff_after": _git(clone, "diff", "--no-ext-diff", "--binary", "HEAD"),
        }
        if process.returncode == 0:
            outputs = sorted(results_dir.glob("results_*.txt"))
            if len(outputs) != 1:
                parse_error = f"expected one generated result, observed {len(outputs)}"
            else:
                replay_payload = outputs[0].read_bytes()
                execution["generated_filename"] = outputs[0].name
                try:
                    replay = parse_artifact(
                        replay_payload,
                        contract,
                        require_frozen_container=False,
                        require_frozen_endpoint=False,
                    )
                except ArtifactError as error:
                    parse_error = str(error)
                else:
                    difference = first_run_difference(reference, replay)
                    first_difference = dict(difference) if difference is not None else None

    after = authenticate_checkout(args.checkout, contract)
    assert_same_identity(before, after)
    elapsed = time.monotonic() - started
    exact_bytes = replay_payload == reference_payload if replay_payload is not None else False
    passed = (
        execution["returncode"] == 0
        and execution["tracked_diff_after"] == ""
        and parse_error is None
        and first_difference is None
        and exact_bytes
    )
    if passed:
        gate = "PASS_SOURCE_NATIVE_RAW_REPLAY"
    elif execution["returncode"] != 0:
        gate = "SOURCE_NATIVE_BLOCKED_EXECUTION_FAILED"
    elif execution["tracked_diff_after"]:
        gate = "SOURCE_NATIVE_BLOCKED_TRACKED_SOURCE_MUTATION"
    elif parse_error is not None:
        gate = "SOURCE_NATIVE_BLOCKED_OUTPUT_PROTOCOL"
    else:
        gate = "SOURCE_NATIVE_BLOCKED_RESULT_MISMATCH"
    generated = None
    if replay_payload is not None:
        generated = {
            "bytes": len(replay_payload),
            "sha256": hashlib.sha256(replay_payload).hexdigest(),
            "exact_byte_match": exact_bytes,
        }
    report = bind_report(
        {
            **_base_report(contract, before, environment),
            "source_native_gate": gate,
            "elapsed_seconds": round(elapsed, 6),
            "execution": execution,
            "reference": {
                "bytes": len(reference_payload),
                "sha256": hashlib.sha256(reference_payload).hexdigest(),
                "runs": len(reference.runs),
            },
            "generated": generated,
            "parse_error": parse_error,
            "first_difference": first_difference,
        },
        domain=b"EU26-09-SOURCE-REPLAY-REPORT-V1",
    )
    write_new_json(args.output, report)
    print(gate)
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
