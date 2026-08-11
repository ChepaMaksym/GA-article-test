#!/usr/bin/env python3
"""Bounded diagnostic execution of the pinned author-source Colon profile.

This wrapper reuses ``run_author_colon._prepare_source`` and adds only a
fail-closed attempt ceiling around the two unbounded Algorithm-4 loops in the
published source. The ceiling does not affect runs that generate the required
repository population within the limit; it converts non-termination into an
explicit, auditable failure.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
from typing import Any

from run_author_colon import EXPECTED_COMMIT, RESULT_PREFIX, _parse_result, _prepare_source

GUARD_MARKER = "EU26_20_REPOSITORY_GUARD"


def add_repository_guards(source: str, attempt_limit: int) -> str:
    if attempt_limit <= 0:
        raise ValueError("attempt_limit must be positive")
    original = source.splitlines()
    lines: list[str] = []
    guarded = 0
    for index, line in enumerate(original):
        if line.strip() == "while (count<10):":
            indent = line[: len(line) - len(line.lstrip())]
            body_indent = None
            for following in original[index + 1 :]:
                if not following.strip():
                    continue
                candidate = following[: len(following) - len(following.lstrip())]
                if len(candidate) > len(indent):
                    body_indent = candidate
                    break
                raise RuntimeError("repository loop has no indented body")
            if body_indent is None:
                raise RuntimeError("repository loop body not found")
            stage = "initial" if guarded == 0 else "main"
            lines.extend(
                [
                    f"{indent}_eu_repository_attempts = 0",
                    line,
                    f"{body_indent}_eu_repository_attempts += 1",
                    f"{body_indent}if _eu_repository_attempts > {attempt_limit}:",
                    (
                        f"{body_indent}    raise RuntimeError("
                        f"'{GUARD_MARKER} stage={stage} iteration=' + "
                        "str(globals().get('it', 0)) + "
                        f"' attempts={attempt_limit}')"
                    ),
                ]
            )
            guarded += 1
        else:
            lines.append(line)
    if guarded != 2:
        raise RuntimeError(f"expected two repository loops, found {guarded}")
    return "\n".join(lines) + "\n"


def _stream_process(
    command: list[str], log_path: Path, quiet: bool
) -> tuple[int, str]:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    captured: list[str] = []
    with log_path.open("w", encoding="utf-8") as log:
        process = subprocess.Popen(
            command,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            bufsize=1,
        )
        assert process.stdout is not None
        for line in process.stdout:
            captured.append(line)
            log.write(line)
            log.flush()
            if not quiet:
                print(line, end="")
        return_code = process.wait()
    return return_code, "".join(captured)


def _failure_payload(
    seed: int,
    return_code: int,
    stdout: str,
    metadata: dict[str, Any],
    attempt_limit: int,
) -> dict[str, Any]:
    guard_failure = GUARD_MARKER in stdout
    tail = stdout.splitlines()[-30:]
    return {
        "schema": "eu26-20-colon-source-failure-v1",
        "profile": "author_source_compatibility_guarded",
        "seed": seed,
        "upstream_commit": EXPECTED_COMMIT,
        "status": (
            "SOURCE_REPOSITORY_NONTERMINATION"
            if guard_failure
            else "SOURCE_PROCESS_FAILURE"
        ),
        "return_code": return_code,
        "repository_attempt_limit": attempt_limit,
        "log_tail": tail,
        **metadata,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("upstream", type=Path)
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--attempt-limit", type=int, default=100_000)
    parser.add_argument("--output-json", type=Path, required=True)
    parser.add_argument("--log-file", type=Path, required=True)
    parser.add_argument("--quiet", action="store_true")
    parser.add_argument("--retain-generated", type=Path)
    args = parser.parse_args()

    root = args.upstream.resolve()
    generated, metadata = _prepare_source(root, args.seed)
    generated = add_repository_guards(generated, args.attempt_limit)
    target = (
        args.retain_generated.resolve()
        if args.retain_generated
        else Path(os.environ.get("RUNNER_TEMP", "/tmp"))
        / f"eu26-20-colon-guarded-seed-{args.seed}.py"
    )
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(generated, encoding="utf-8")

    return_code, stdout = _stream_process(
        [sys.executable, str(target)], args.log_file.resolve(), args.quiet
    )
    if return_code == 0:
        result = _parse_result(stdout)
        result.update(metadata)
        result["source_guard"] = {
            "repository_attempt_limit": args.attempt_limit,
            "triggered": False,
        }
    else:
        result = _failure_payload(
            args.seed, return_code, stdout, metadata, args.attempt_limit
        )

    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print("EU26_20_GUARDED_RESULT=" + json.dumps(result, sort_keys=True))
    if return_code != 0:
        raise SystemExit(return_code)


if __name__ == "__main__":
    main()
