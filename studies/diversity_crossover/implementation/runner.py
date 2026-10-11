"""Run exactly eight registered pilot searches for one task, in GitHub Actions."""

from __future__ import annotations

import argparse
import gzip
import itertools
import json
import os
import time
from pathlib import Path

from .banks import METHODS, PROTOCOL, SEED, STARTS, TASKS, load_banks
from .contract import (AUTHORITY, authenticate, canonical_bytes, ci_only,
                       file_identity, require, source_manifest,
                       write_file_manifest, write_json)
from .engine import make_rngs, run_search
from .verifier import verify_frozen_header, verify_journal

JOB_SCHEMA = "diversity-pilot-task-v1"
RUN_SCHEMA = "diversity-pilot-run-v1"


class JournalWriter:
    """Streaming, deterministic gzip; do not hold candidate journals in RAM."""

    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.raw = self.path.open("wb")
        self.stream = gzip.GzipFile(filename="", mode="wb", fileobj=self.raw, mtime=0, compresslevel=6)
        self.events = 0

    def __call__(self, record):
        self.stream.write(canonical_bytes(record).rstrip(b"\n") + b"\n")
        self.events += 1

    def close(self):
        if not self.stream.closed:
            self.stream.close()
        if not self.raw.closed:
            self.raw.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()


def journal_records(path):
    with gzip.open(path, "rt", encoding="utf-8") as stream:
        for line_index, line in enumerate(stream, 1):
            require(line.endswith("\n"), f"truncated journal line {line_index}")
            yield json.loads(line)


def write_gzip_json(path, obj):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as raw:
        with gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0) as stream:
            stream.write(canonical_bytes(obj))


def _compressed_bytes(output):
    return sum(p.stat().st_size for p in Path(output).rglob("*.gz"))


def run_task(task, output, expected_sha):
    ci_only()
    require(task in TASKS, "unregistered pilot task")
    provenance = authenticate(expected_sha)
    from .contract import validate_tests_receipt
    validate_tests_receipt()
    output = Path(output)
    require(not output.exists() or not any(output.iterdir()), "pilot output must be empty")
    output.mkdir(parents=True, exist_ok=True)
    before_setup = time.perf_counter()
    banks, bank_manifest = load_banks()
    source = source_manifest()
    task_index = TASKS.index(task)
    bank_manifest_sha256 = file_identity(Path(__file__).resolve().parent.parent / "pilot_inputs/banks_manifest.json")["sha256"]
    results = []
    stopped = False
    for start_index, start in enumerate(STARTS):
        bank = banks[(task, start)]
        # Metadata stays outside the search interface.
        problem, masks, scores = bank["problem"], bank["masks"], bank["scores"]
        for method in METHODS:
            relative = f"runs/{task}-{start}-{method}"
            directory = output / relative
            directory.mkdir(parents=True, exist_ok=True)
            identity = {"schema_version": RUN_SCHEMA, "protocol_id": PROTOCOL,
                        "implementation_sha": expected_sha, "task": task, "task_index": task_index,
                        "start": start, "start_index": start_index, "method": method, "seed": SEED,
                        "bank_manifest_sha256": bank_manifest_sha256,
                        "preparation_sha": bank_manifest["preparation_sha"],
                        "run_id": os.environ.get("GITHUB_RUN_ID"),
                        "run_attempt": os.environ.get("GITHUB_RUN_ATTEMPT")}
            entry = dict(identity, path=relative)
            if stopped:
                summary = dict(identity, status="RESOURCE_STOP", reason="compressed output limit reached", search=None)
                write_json(directory / "summary.json", summary)
                results.append(dict(entry, status=summary["status"]))
                continue
            writer = JournalWriter(directory / "journal.jsonl.gz")
            wall_start = time.perf_counter()
            try:
                rngs = make_rngs(task_index, start_index, seed=SEED,
                                 initialization_state=bank["initialization_after"])
                actual_method = "baseline" if method == "mutation_control" else method
                pc = 0.0 if method == "mutation_control" else 0.9
                search = run_search(problem, masks, scores, actual_method, rngs, writer,
                                    budget=5000, pc=pc)
                writer.close()
                search_seconds = time.perf_counter() - wall_start
                verify_start = time.perf_counter()
                records = journal_records(directory / "journal.jsonl.gz")
                header = next(records)
                verify_frozen_header(problem, header, bank, actual_method, pc, budget=5000)
                verified = verify_journal(problem, itertools.chain((header,), records))
                require(verified["status"] == "VERIFIED" and
                        canonical_bytes(verified["summary"]) == canonical_bytes(search),
                        "independent reconstruction differs from production result")
                require(search["new_calls"] == search["physical_calls"] == 5000 and
                        search["status"] == "COMPLETE", "search did not complete registered budget")
                trace = verified.pop("trace")
                write_gzip_json(directory / "trace.json.gz", trace)
                write_json(directory / "verification.json", verified)
                initial = search["initial_record"]["score"]["value"]
                optimum = bank["metadata"].get("posthoc_known_optimum")
                # Comparing against an exact oracle occurs only after search/verification.
                if optimum is not None:
                    require(search["record"]["score"]["value"] <= optimum, "record exceeds external exact optimum")
                escape_applicable = start == "cloned" and bool(bank["metadata"]["escape_applicable"])
                summary = dict(identity, status="COMPLETE", search=search,
                               search_seconds=search_seconds,
                               verification_seconds=time.perf_counter() - verify_start,
                               verification_calls=verified["verification_calls"],
                               productivity=verified["productivity"],
                               directed_activity=verified.get("directed_activity", {}),
                               escape_applicable=escape_applicable,
                               escape=(search["first_improvement_call"] is not None) if escape_applicable else None,
                               initial_value=initial, center_type=bank["metadata"]["center_type"],
                               posthoc_known_optimum=optimum,
                               journal_identity=file_identity(directory / "journal.jsonl.gz"),
                               trace_identity=file_identity(directory / "trace.json.gz"),
                               journal_event_count=writer.events)
            except Exception as exc:
                writer.close()
                summary = dict(identity, status="INCOMPLETE_TECHNICAL", search=None,
                               exception_type=type(exc).__name__, reason=str(exc),
                               journal_identity=file_identity(directory / "journal.jsonl.gz"),
                               journal_event_count=writer.events,
                               elapsed_seconds=time.perf_counter() - wall_start)
            write_json(directory / "summary.json", summary)
            results.append(dict(entry, status=summary["status"]))
            if _compressed_bytes(output) > int(AUTHORITY["compressed_job_bytes_limit"]):
                stopped = True
    complete = sum(row["status"] == "COMPLETE" for row in results)
    report = {"schema_version": JOB_SCHEMA, "protocol_id": PROTOCOL,
              "implementation_sha": expected_sha, "task": task, "task_index": task_index,
              "seed": SEED, "run_id": os.environ.get("GITHUB_RUN_ID"),
              "run_attempt": os.environ.get("GITHUB_RUN_ATTEMPT"),
              "status": "COMPLETE" if complete == 8 and not stopped else "INCOMPLETE_TECHNICAL",
              "expected_runs": 8, "complete_runs": complete, "runs": results,
              "compressed_bytes": _compressed_bytes(output),
              "compressed_limit": int(AUTHORITY["compressed_job_bytes_limit"]),
              "bank_manifest_sha256": bank_manifest_sha256,
              "preparation_sha": bank_manifest["preparation_sha"],
              "bank_integrity_verification_calls": 16 * 30,
              "initial_preparation_physical_calls_charged_this_job": 0,
              "initial_preparation_physical_calls_all_banks": bank_manifest["physical_preparation_evaluations"],
              "total_wall_seconds": time.perf_counter() - before_setup}
    write_json(output / "task_results.json", report)
    write_json(output / "source_manifest.json", source)
    write_json(output / "provenance.json", provenance)
    write_file_manifest(output)
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--task", choices=TASKS, required=True)
    parser.add_argument("--expected-sha", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    result = run_task(args.task, args.output, args.expected_sha)
    if result["status"] != "COMPLETE":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
