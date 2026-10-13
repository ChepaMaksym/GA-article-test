"""Run registered main/diagnostic batches and independently verify every journal."""

from __future__ import annotations

import argparse
import gzip
import itertools
import json
import os
import time
from pathlib import Path

from ..implementation.engine import make_rngs, run_search
from ..implementation.verifier import verify_journal
from .contract import (AUTHORITY, PROTOCOL_ID, authenticate, canonical_bytes,
                       ci_only, file_identity, require, source_manifest,
                       validate_tests_receipt, job_budget_preflight, write_file_manifest, write_json)
from .inputs import (BUDGET, CLONED_TASKS, DIAGNOSTIC_SEED, FROZEN_INPUTS,
                     LOCAL_TASKS, METHODS, STARTS, TASKS, diagnostic_specs,
                     job_specs, load_banks, verify_frozen_header)

RUN_SCHEMA = "diversity-main-run-v1"
JOB_SCHEMA = "diversity-main-job-v1"
ILLUSTRATIVE_TASKS = ("UC-s000", "Jump4")


class ResourceLimit(ValueError):
    pass


class _BoundedRaw:
    def __init__(self, stream, limit):
        self.stream, self.limit = stream, limit

    def write(self, data):
        if self.stream.tell() + len(data) > self.limit:
            raise ResourceLimit("compressed journal limit reached")
        return self.stream.write(data)

    def __getattr__(self, name):
        return getattr(self.stream, name)


class JournalWriter:
    """Stream deterministic gzip; enforce the remaining compressed-byte limit."""
    def __init__(self, path, limit_bytes):
        require(type(limit_bytes) is int and limit_bytes > 0, "journal space exhausted")
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.raw = self.path.open("wb")
        try:
            self.stream = gzip.GzipFile(filename="", mode="wb", mtime=0, compresslevel=6,
                                        fileobj=_BoundedRaw(self.raw, limit_bytes))
        except Exception:
            self.raw.close()
            raise
        self.events, self.evaluated_calls = 0, 0
        self.closed = False

    def __call__(self, record):
        if record.get("event") == "candidate":
            self.evaluated_calls = record["call"]
        self.stream.write(canonical_bytes(record) + b"\n")
        self.events += 1

    def close(self):
        if self.closed:
            return
        self.closed = True
        try:
            self.stream.close()
        finally:
            self.raw.close()


def journal_records(path):
    with gzip.open(path, "rt", encoding="utf-8") as stream:
        for index, line in enumerate(stream, 1):
            require(line.endswith("\n"), f"truncated journal line {index}")
            yield json.loads(line)


def write_gzip_json(path, obj):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as raw:
        with gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0) as stream:
            stream.write(canonical_bytes(obj))


def _compressed_bytes(directory):
    return sum(path.stat().st_size for path in Path(directory).rglob("*.gz"))


def _total_bytes(directory):
    return sum(path.stat().st_size for path in Path(directory).rglob("*") if path.is_file())


def run_identity(task, start, seed, method):
    return f"{task}-{start}-{seed}-{method}"


def build_summary(identity, bank, search, verified, journal, *, search_seconds=0.0,
                  verification_seconds=0.0, events=0):
    """Scientific fields are obtained only after independent journal replay."""
    require(verified["status"] == "VERIFIED" and canonical_bytes(search) ==
            canonical_bytes(verified["summary"]), "independent search reconstruction differs")
    require(search["status"] == "COMPLETE" and search["new_calls"] == search["physical_calls"] == BUDGET,
            "registered search budget incomplete")
    value = search["record"]["score"]["value"]
    initial_value = search["initial_record"]["score"]["value"]
    require(search["record"]["score"]["feasible"] is True, "record must remain feasible")
    optimum = bank["metadata"].get("posthoc_known_optimum")
    if optimum is not None:
        require(value <= optimum, "record exceeds external exact optimum")
    diagnostic = identity["series"] == "diagnostic"
    if diagnostic:
        require(initial_value == value == optimum and search["first_improvement_call"] is None,
                "global negative control improved beyond the exact optimum")
    escape_applicable = (not diagnostic and identity["start"] == "cloned" and
                         identity["task"] in ("Jump4", "Jump8", *LOCAL_TASKS))
    productivity = dict(verified["productivity"])
    productivity.update(both_parents_feasible=productivity["both_parents_feasible_candidates"],
                        U_post=productivity["post_mutation_better_than_both"],
                        U_pre=productivity["pre_mutation_better_than_both"])
    return dict(identity, status="COMPLETE", verification_status="VERIFIED", search=search,
                verification_calls=verified["verification_calls"],
                verification_call_breakdown=verified["verification_call_breakdown"],
                productivity=productivity, directed_activity=verified["directed_activity"],
                escape_applicable=escape_applicable,
                escape=(search["first_improvement_call"] is not None) if escape_applicable else None,
                escape_call=search["first_improvement_call"] if escape_applicable else None,
                initial_value=initial_value, center_type=bank["metadata"]["center_type"],
                exact_optimum=optimum,
                relative_gap=(optimum - value) / optimum if optimum is not None and optimum > 0 else None,
                search_seconds=search_seconds, verification_seconds=verification_seconds,
                journal_identity=journal, journal_event_count=events)


def run_batch(output, expected_sha, *, task=None, block=None, diagnostic_block=None):
    ci_only()
    require((diagnostic_block is None and task is not None and block is not None) or
            (diagnostic_block is not None and task is None and block is None), "mixed or absent job selection")
    specs = job_specs(task, block) if diagnostic_block is None else diagnostic_specs(diagnostic_block)
    provenance = authenticate(expected_sha)
    validate_tests_receipt()
    budget_job_id = f"{task}-b{block}" if diagnostic_block is None else f"global-b{diagnostic_block}"
    budget_receipt = job_budget_preflight(budget_job_id, diagnostic=diagnostic_block is not None)
    output = Path(output)
    require(not output.exists() or not any(output.iterdir()), "batch output must be empty")
    full, compact = output / "full", output / "compact"
    full.mkdir(parents=True, exist_ok=True)
    compact.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()
    identities = {(t, s, seed) for t, s, seed, _ in specs}
    banks, manifest = load_banks(identities=identities)
    source = source_manifest()
    bank_manifest_identity = file_identity(FROZEN_INPUTS / "banks_manifest.json")
    series = "main" if diagnostic_block is None else "diagnostic"
    job_key = f"{task}-block{block}" if series == "main" else f"diagnostic-block{diagnostic_block}"
    results, traces = [], []
    stopped = False
    limit = int(AUTHORITY["resources"]["compressed_journal_limit_bytes_per_job"])
    for current_task, start, seed, method in specs:
        identity = {"schema_version": RUN_SCHEMA, "protocol_id": PROTOCOL_ID,
                    "implementation_sha": expected_sha, "task": current_task,
                    "task_index": TASKS.index(current_task), "start": start,
                    "start_index": STARTS.index(start), "seed": seed, "method": method,
                    "series": series, "job_key": job_key,
                    "run_id": int(os.environ["GITHUB_RUN_ID"]),
                    "run_attempt": int(os.environ.get("GITHUB_RUN_ATTEMPT", "1")),
                    "preparation_sha": manifest["preparation_sha"],
                    "bank_manifest_sha256": bank_manifest_identity["sha256"],
                    "source_fingerprint": manifest["source_fingerprint"]}
        relative = f"runs/{run_identity(current_task, start, seed, method)}"
        identity["full_path"] = relative
        directory = full / relative
        directory.mkdir(parents=True, exist_ok=True)
        write_json(directory / "identity.json", identity)
        if stopped:
            summary = dict(identity, status="RESOURCE_STOP", verification_status="NOT_VERIFIED",
                           search=None, reason="compressed journal limit reached")
            write_json(directory / "summary.json", summary)
            results.append(summary)
            continue
        bank = banks[(current_task, start, seed)]
        problem = bank["problem"]
        writer = None
        before = time.perf_counter()
        try:
            remaining = limit - _compressed_bytes(full)
            writer = JournalWriter(directory / "journal.jsonl.gz", remaining)
            rngs = make_rngs(TASKS.index(current_task), STARTS.index(start), seed=seed,
                             initialization_state=bank["initialization_after"])
            kernel_method = "baseline" if method == "mutation_control" else method
            pc = 0.0 if method == "mutation_control" else 0.9
            search = run_search(problem, bank["masks"], bank["scores"], kernel_method,
                                rngs, writer, budget=BUDGET, pc=pc)
            writer.close()
            search_seconds = time.perf_counter() - before
            verification_started = time.perf_counter()
            records = journal_records(directory / "journal.jsonl.gz")
            header = next(records)
            verify_frozen_header(problem, header, bank, kernel_method, pc)
            verified = verify_journal(problem, itertools.chain((header,), records))
            summary = build_summary(identity, bank, search, verified,
                                    file_identity(directory / "journal.jsonl.gz"),
                                    search_seconds=search_seconds,
                                    verification_seconds=time.perf_counter() - verification_started,
                                    events=writer.events)
            if current_task in ILLUSTRATIVE_TASKS and seed == 71001:
                traces.append({"task": current_task, "start": start, "method": method,
                               "seed": seed, "points": verified["trace"]})
            write_json(directory / "verification.json", {key: value for key, value in verified.items()
                                                         if key != "trace"})
        except Exception as error:
            if writer is not None:
                try:
                    writer.close()
                except Exception:
                    pass  # Preserve the original failure and the bounded partial journal.
            path = directory / "journal.jsonl.gz"
            summary = dict(identity, status="INCOMPLETE_TECHNICAL", verification_status="NOT_VERIFIED",
                           search=None, exception_type=type(error).__name__, reason=str(error),
                           journal_identity=file_identity(path) if path.exists() else None,
                           journal_event_count=writer.events if writer is not None else 0,
                           physical_queries_observed=writer.evaluated_calls if writer is not None else 0,
                           elapsed_seconds=time.perf_counter() - before)
            stopped = isinstance(error, ResourceLimit)
        write_json(directory / "summary.json", summary)
        results.append(summary)
        if _compressed_bytes(full) >= limit:
            stopped = True
    complete = sum(row["status"] == "COMPLETE" for row in results)
    report = {"schema_version": JOB_SCHEMA, "protocol_id": PROTOCOL_ID,
              "implementation_sha": expected_sha, "job_key": job_key, "series": series,
              "task": task, "block": block, "diagnostic_block": diagnostic_block,
              "run_id": int(os.environ["GITHUB_RUN_ID"]),
              "run_attempt": int(os.environ.get("GITHUB_RUN_ATTEMPT", "1")),
              "status": "COMPLETE" if complete == len(specs) and not stopped else "INCOMPLETE_TECHNICAL",
              "expected_runs": len(specs), "complete_runs": complete, "runs": results,
              "compressed_bytes": _compressed_bytes(full), "compressed_limit": limit,
              "bank_manifest_sha256": bank_manifest_identity["sha256"],
              "preparation_sha": manifest["preparation_sha"],
              "source_fingerprint": manifest["source_fingerprint"],
              "bank_integrity_verification_calls": len(identities) * 30,
              "initial_preparation_physical_calls_charged_this_job": 0,
              "initial_preparation_physical_calls_all_banks": manifest["physical_preparation_evaluations"],
              "search_calls_complete_runs": BUDGET * complete,
              "verification_calls_complete_runs": sum(row.get("verification_calls", 0) for row in results),
              "total_wall_seconds": time.perf_counter() - started}
    write_json(compact / "task_results.json", report)
    if traces:
        write_gzip_json(compact / "verified_traces.json.gz", traces)
    for directory in (full, compact):
        write_json(directory / "budget-preflight.json", budget_receipt)
        write_json(directory / "source_manifest.json", source)
        write_json(directory / "provenance.json", provenance)
        write_file_manifest(directory)
    require(_compressed_bytes(full) <= limit, "full journal byte limit exceeded")
    require(_total_bytes(compact) <= int(AUTHORITY["resources"]["compact_limit_bytes_per_job"]),
            "compact artifact byte limit exceeded")
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--task", choices=TASKS)
    parser.add_argument("--block", type=int)
    parser.add_argument("--diagnostic-block", type=int)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--expected-sha", required=True)
    args = parser.parse_args(argv)
    report = run_batch(args.output, args.expected_sha, task=args.task,
                       block=args.block, diagnostic_block=args.diagnostic_block)
    if report["status"] != "COMPLETE":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
