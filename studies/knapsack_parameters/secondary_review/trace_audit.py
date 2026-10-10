"""CI-only independent replay of six preregistered historical traces.

This module never invokes the search kernel, a bank generator or an exact
solver. It only reads the one frozen artifact and replays its recorded events
through the unchanged independent historical oracle.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import io
import json
import os
from pathlib import Path
import tarfile
import tempfile
from types import SimpleNamespace

import numpy as np

from ..ga_study.oracle import verify_search
from ..ga_study.transport import (api_get, download_zip, extract_bundle,
                                 verify_artifact_identity)
from .contract import (MODULE_ROOT, ROOT, SOURCE_ROOT, SOURCE_RUN, SOURCE_SHA,
                       PROTOCOL_ID, file_identity, load_context, read_json,
                       require, verify_file_manifest, write_file_manifest,
                       write_json)

REPOSITORY = "ChepaMaksym/GA-article-test"
SCHEMA = "ga-knapsack-secondary-trace-audit-v1"
RUN_FILES = ("requests.npz", "generations.jsonl.gz", "search_summary.json",
             "summary.json", "manifest.json")


def selected_identities() -> tuple[tuple[str, str], ...]:
    return tuple((profile, f"m{token}-c0p9-n30")
                 for profile in ("random", "local") for token in ("0p5", "1", "3"))


def validate_descriptor(protocol: dict, sources: dict) -> dict:
    """Bind the single named artifact to the already retained source ledger."""
    descriptor = protocol["trace"]
    require(descriptor["artifact_id"] == 11557059267 and
            descriptor["run_id"] == SOURCE_RUN and descriptor["run_attempt"] == 1 and
            descriptor["implementation_commit_sha"] == SOURCE_SHA,
            "trace source is not the preregistered historical artifact")
    matches = [row for row in sources["sources"]
               if row["artifact_id"] == descriptor["artifact_id"]]
    require(len(matches) == 1, "missing or duplicate frozen artifact in source ledger")
    source = matches[0]
    for key in ("artifact_id", "artifact_name", "run_id", "run_attempt",
                "zip_sha256", "zip_bytes", "job_manifest_sha256"):
        require(source[key] == descriptor[key], f"frozen source mismatch: {key}")
    require(sources["implementation_commit_sha"] == SOURCE_SHA and
            sources["run_id"] == SOURCE_RUN and sources["run_attempt"] == 1 and
            source["instance_id"] == "UC-s000" and source["seed_first"] == 51001 and
            source["seed_last"] == 51010,
            "historical artifact has mixed source identities")
    return descriptor


def validate_job(directory: Path, descriptor: dict, sources: dict) -> list[dict]:
    """Check all source bytes and the exact batch, not just the six samples."""
    verify_file_manifest(directory)
    require(file_identity(directory / "manifest.json")["sha256"] ==
            descriptor["job_manifest_sha256"], "job manifest hash differs from frozen source")
    manifest = read_json(directory / "manifest.json")
    require(manifest["schema_version"] == "ga-knapsack-job-v1" and
            manifest["status"] == "COMPLETE" and manifest["verified"] is True and
            manifest["phase"] == "main" and manifest["run_count"] == 540 and
            manifest["instance_id"] == "UC-s000" and
            manifest["job_key"] == "UC-s000-51001-51010" and
            manifest["seed_first"] == 51001 and manifest["seed_last"] == 51010,
            "historical batch is not complete or has wrong matrix identity")
    for key in ("protocol_id", "protocol_sha256", "registration_commit_sha",
                "implementation_commit_sha", "data_manifest_sha256", "registry_sha256",
                "implementation_fingerprint", "runtime_lock_sha256",
                "requirements_lock_sha256", "python_version", "numpy_version",
                "matplotlib_version", "run_id", "run_attempt"):
        require(manifest[key] == sources[key], f"historical batch source mismatch: {key}")
    expected_paths = set()
    for entry in manifest["files"]:
        path = entry["path"]
        require(path not in expected_paths and path not in ("manifest.json", "file_manifest.json"),
                "duplicate or self-listed historical job file")
        expected_paths.add(path)
        # The full file manifest already checked safe paths and each hash.
        require(file_identity(directory / path) ==
                {"bytes": entry["bytes"], "sha256": entry["sha256"]},
                "historical batch member checksum mismatch")
    actual_paths = {path.relative_to(directory).as_posix()
                    for path in directory.rglob("*") if path.is_file()}
    require(actual_paths == expected_paths | {"manifest.json", "file_manifest.json"},
            "historical batch contains unexpected or missing files")
    rows = read_json(directory / "summaries.json")
    require(isinstance(rows, list) and len(rows) == 540, "historical batch summaries incomplete")
    found = {(row["repeat_seed"], row["start_profile"], row["configuration_id"]) for row in rows}
    expected = {(seed, profile, f"m{m}-c{c}-n{n}")
                for seed in range(51001, 51011) for profile in ("random", "local")
                for m in ("0p5", "1", "3") for c in ("0", "0p5", "0p9")
                for n in (10, 30, 50)}
    require(found == expected and len(found) == len(rows), "historical batch identities are duplicate or incomplete")
    return rows


def load_saved_result(directory: Path, row: dict) -> dict:
    """Reject pickle/object arrays and bind each selected run's byte inventory."""
    require(row["run_directory"] ==
            f"runs/{row['repeat_seed']}/{row['start_profile']}/{row['configuration_id']}",
            "historical run directory is not its identity")
    run_directory = directory / row["run_directory"]
    manifest = read_json(run_directory / "manifest.json")
    require(manifest["schema_version"] == "ga-knapsack-run-manifest-v1" and
            manifest["verified"] is True and
            manifest["identity"] == {key: row[key] for key in
                ("instance_id", "start_profile", "repeat_seed", "configuration_id",
                 "implementation_commit_sha")}, "selected run manifest identity mismatch")
    entries = manifest["files"]
    names = [entry["path"] for entry in entries]
    require(set(names) == set(RUN_FILES) - {"manifest.json"} and len(names) == 4,
            "selected run file inventory incomplete or duplicate")
    for entry in entries:
        require(file_identity(run_directory / entry["path"]) ==
                {"bytes": entry["bytes"], "sha256": entry["sha256"]},
                "selected run member checksum mismatch")
    require(read_json(run_directory / "summary.json") == row,
            "flat and individual historical run summary disagree")
    summary = read_json(run_directory / "search_summary.json")
    require(all(row.get(key) == value for key, value in summary.items()),
            "historical search and wrapper summaries disagree")
    with np.load(run_directory / "requests.npz", allow_pickle=False) as archive:
        requests = {key: archive[key] for key in archive.files}
    require(all(value.dtype.kind != "O" for value in requests.values()), "object arrays prohibited")
    with gzip.open(run_directory / "generations.jsonl.gz", "rt", encoding="utf-8") as stream:
        generations = [json.loads(line) for line in stream]
    return {"summary": summary, "requests": requests, "generations": generations}


def bind_initial_bank(directory: Path, rows: list[dict]) -> dict:
    """Read the saved 50-mask prefix; do not regenerate any population."""
    matches = [row for row in rows if row["repeat_seed"] == 51001 and
               row["start_profile"] == "random" and row["configuration_id"] == "m1-c0p9-n50"]
    require(len(matches) == 1, "frozen 50-mask initial prefix missing or duplicate")
    row = matches[0]
    result = load_saved_result(directory, row)
    masks = result["requests"]["masks"][:50]
    require(masks.shape == (50, 100) and masks.dtype == np.dtype("uint8") and
            np.all((masks == 0) | (masks == 1)) and np.all(masks[0] == 0),
            "saved bank must have 50 binary masks and an empty first mask")
    checksum = hashlib.sha256(masks.tobytes()).hexdigest()
    require(row["initial_identity"]["bank_seed"] == 51001 and
            row["initial_identity"]["bank_arrays_sha256"] == checksum,
            "saved bank array identity mismatch")
    descriptor = read_json(ROOT / "studies/knapsack_parameters/ga_study/frozen_banks.json")
    require(row["banks_manifest_sha256"] == descriptor["banks_manifest_sha256"] and
            row["frozen_banks_descriptor_sha256"] == file_identity(
                ROOT / "studies/knapsack_parameters/ga_study/frozen_banks.json")["sha256"],
            "saved bank is not the historical frozen bank registry")
    return {"masks": masks.copy(),
            "scores": {key: result["requests"][key][:50].copy()
                       for key in ("weight", "profit", "feasible")},
            "checksum": checksum, "metadata": row["initial_identity"],
            "rng_states": result["generations"][0]["rng_states"],
            "source_npz": {"path": row["run_directory"] + "/requests.npz",
                           **file_identity(directory / row["run_directory"] / "requests.npz")}}


def reconstruct_trajectory(result: dict) -> list[dict]:
    """Do not advance population metrics for an incomplete last generation."""
    requests = result["requests"]
    profits, feasible = requests["profit"], requests["feasible"]
    record = []
    best = None
    for profit, valid in zip(profits.tolist(), feasible.tolist(), strict=True):
        if valid and (best is None or profit > best):
            best = int(profit)
        record.append(best)
    output = []
    for event in result["generations"]:
        end = event["last_request"]
        require(type(end) is int and 1 <= end <= len(record), "generation endpoint outside saved requests")
        metrics = event["metrics_after"]
        complete = event["complete"]
        require(type(complete) is bool, "generation completeness must be boolean")
        if not complete:
            require(event["population_after"] == event["population_before"] and
                    metrics == event["metrics_before"],
                    "partial generation changed the accepted population")
        output.append({"generation": event["generation"],
            "first_request": event["first_request"], "last_request": end,
            "complete": complete, "population_updated": complete,
            "best_profit": record[end - 1],
            "mean_feasible_profit": metrics["mean_feasible_profit"],
            "diversity": metrics["diversity"],
            "feasible_fraction": metrics["feasible_fraction"]})
    return output


def compact_matches(row: dict, compact: dict) -> None:
    require(all(row.get(key) == value for key, value in compact.items()),
            "selected full trace disagrees with immutable compact summary")


def audit_case(directory: Path, row: dict, compact: dict, instance, case: dict,
               bank: dict) -> tuple[dict, dict]:
    compact_matches(row, compact)
    require(row["instance_id"] == "UC-s000" and row["repeat_seed"] == 51001 and
            row["implementation_commit_sha"] == SOURCE_SHA and row["run_id"] == SOURCE_RUN and
            row["run_attempt"] == 1 and row["population_size"] == 30 and
            row["crossover_probability"] == 0.9 and
            (row["start_profile"], row["configuration_id"]) in selected_identities(),
            "selected trace is not a prespecified case")
    result = load_saved_result(directory, row)
    request = result["requests"]
    if row["start_profile"] == "random":
        require(row["initial_identity"]["bank_arrays_sha256"] == bank["checksum"] and
                row["initial_identity"]["bank_seed"] == 51001 and
                row["initial_identity"]["prefix"] == 30 and
                result["generations"][0]["rng_states"] == bank["rng_states"],
                "selected random start does not use the saved common bank")
        masks = bank["masks"][:30]
        scores = {key: value[:30] for key, value in bank["scores"].items()}
        center_profit = None
    else:
        center = case["payload"]["certificate"]["center"]
        masks = np.asarray([[int(bit) for bit in center["mask"]]] * 30, dtype=np.uint8)
        scores = {"weight": np.full(30, center["weight"], dtype=np.int64),
                  "profit": np.full(30, center["profit"], dtype=np.int64),
                  "feasible": np.ones(30, dtype=np.bool_)}
        require(row["initial_identity"]["center_mask"] == center["mask"] and
                row["initial_identity"]["center_profit"] == center["profit"] and
                row["initial_identity"]["center_weight"] == center["weight"],
                "selected local start does not use the frozen certified center")
        center_profit = center["profit"]
    # Only the unchanged verifier is used: no production objective/controller.
    config = SimpleNamespace(mutation_numerator=row["mutation_numerator"],
        crossover_probability=0.9, population_size=30,
        configuration_id=row["configuration_id"])
    verdict = verify_search(instance, config, result,
        initial_center_profit=center_profit, initial_masks=masks, initial_scores=scores)
    require(verdict["status"] == "PASS_REPLAY" and verdict == row["verification"],
            "fresh independent replay differs from historical verification")
    for key in ("logical_requests", "physical_evaluations", "best_mask", "best_profit",
                "best_weight", "best_request", "duplicate_count", "invalid_request_count",
                "complete_generations", "terminal_partial", "escape_event",
                "first_escape_request", "escape_time", "censored"):
        require(row.get(key) == verdict.get(key), f"fresh replay counter mismatch: {key}")
    require(int(request["request"][-1]) == 5000 and row["logical_requests"] == 5000,
            "historical trace did not include final query")
    return {"identity": {key: row[key] for key in
                    ("instance_id", "repeat_seed", "start_profile", "configuration_id")},
            "verified": True, "replay": verdict, "summary": compact,
            "trajectory": reconstruct_trajectory(result)}, result


def retain_selected_traces(directory: Path, output: Path, rows: list[dict], bank: dict) -> dict:
    """Deterministic portable TAR with the six original raw trace payloads."""
    require(len(rows) == 6 and len({row["run_directory"] for row in rows}) == 6,
            "retention requires six distinct original trace identities")
    members = [(row["run_directory"] + "/" + name,
                (directory / row["run_directory"] / name).read_bytes())
               for row in rows for name in RUN_FILES]
    bank_record = {"masks": ["".join(map(str, bits.tolist())) for bits in bank["masks"]],
        "scores": {key: value.tolist() for key, value in bank["scores"].items()},
        "sha256": bank["checksum"], "metadata": bank["metadata"],
        "rng_states": bank["rng_states"], "source_npz": bank["source_npz"]}
    bank_bytes = json.dumps(bank_record, sort_keys=True, separators=(",", ":"),
                           allow_nan=False).encode("utf-8")
    members.append(("saved-initial-bank.json", bank_bytes))
    require(len({name for name, _ in members}) == len(members),
            "retained archive contains duplicate paths")
    member_inventory = [{"path": name, "bytes": len(raw),
                         "sha256": hashlib.sha256(raw).hexdigest()}
                        for name, raw in sorted(members)]
    members.append(("retained_manifest.json", json.dumps({
        "schema_version": "ga-knapsack-secondary-retained-traces-v1",
        "source_run_id": SOURCE_RUN, "source_implementation_commit_sha": SOURCE_SHA,
        "files": member_inventory}, sort_keys=True, separators=(",", ":")).encode("utf-8")))
    destination = output / "retained-traces.tar.gz"
    with destination.open("wb") as target:
        with gzip.GzipFile(fileobj=target, mode="wb", filename="", mtime=0) as compressed:
            with tarfile.open(fileobj=compressed, mode="w", format=tarfile.PAX_FORMAT) as archive:
                for name, raw in sorted(members):
                    info = tarfile.TarInfo(name)
                    info.size, info.mtime, info.mode = len(raw), 0, 0o644
                    info.uid = info.gid = 0
                    info.uname = info.gname = ""
                    archive.addfile(info, io.BytesIO(raw))
    return {"path": destination.name, **file_identity(destination),
            "run_count": 6, "source_run_id": SOURCE_RUN,
            "source_implementation_commit_sha": SOURCE_SHA,
            "member_count": len(members), "files": member_inventory}


def audit(expected_sha: str, output: Path) -> dict:
    instances, cases, _, identity = load_context(expected_sha)
    output = Path(output).resolve()
    require(not output.is_relative_to(ROOT) and
            (not output.exists() or not any(output.iterdir())),
            "trace output must be a new directory outside checkout")
    output.mkdir(parents=True, exist_ok=True)
    protocol = read_json(MODULE_ROOT / "protocol.json")
    descriptor = validate_descriptor(protocol, read_json(SOURCE_ROOT / "sources.json"))
    report = {"schema_version": SCHEMA, "protocol_id": PROTOCOL_ID,
        "provenance": identity, "source": descriptor,
        "status": "PARTIAL_TRACE_AUDIT", "expected_case_count": 6,
        "verified_case_count": 0, "cases": [], "fault": None,
        "retained_traces": None, "new_search_runs": 0, "new_exact_solver_runs": 0}
    try:
        metadata = api_get(f"https://api.github.com/repos/{REPOSITORY}/actions/artifacts/{descriptor['artifact_id']}")
        verify_artifact_identity(metadata, artifact_id=descriptor["artifact_id"],
            source_run_id=SOURCE_RUN, source_sha=SOURCE_SHA,
            zip_sha256=descriptor["zip_sha256"])
        require(metadata["name"] == descriptor["artifact_name"] and
                metadata["size_in_bytes"] == descriptor["zip_bytes"],
                "frozen artifact name or ZIP length changed")
        report["artifact_metadata"] = {key: metadata.get(key) for key in
            ("id", "name", "digest", "size_in_bytes", "expired", "expires_at")}
        raw = download_zip(metadata)
        require(hashlib.sha256(raw).hexdigest() == descriptor["zip_sha256"] and
                len(raw) == descriptor["zip_bytes"], "frozen ZIP checksum or length changed")
        with tempfile.TemporaryDirectory(prefix="knapsack-review-source-",
                dir=os.environ.get("RUNNER_TEMP")) as temporary:
            directory = extract_bundle(raw, Path(temporary) / "source")
            del raw
            source_rows = validate_job(directory, descriptor, read_json(SOURCE_ROOT / "sources.json"))
            bank = bind_initial_bank(directory, source_rows)
            compact_rows = {}
            with gzip.open(SOURCE_ROOT / "run-summaries.jsonl.gz", "rt", encoding="utf-8") as stream:
                for line in stream:
                    row = json.loads(line)
                    if row["instance_id"] == "UC-s000" and row["repeat_seed"] == 51001:
                        key = (row["start_profile"], row["configuration_id"])
                        require(key not in compact_rows, "duplicate compact example identity")
                        compact_rows[key] = row
            instance = next(item for item in instances if item.instance_id == "UC-s000")
            selected = []
            for key in selected_identities():
                matches = [row for row in source_rows if row["repeat_seed"] == 51001 and
                           (row["start_profile"], row["configuration_id"]) == key]
                require(len(matches) == 1 and key in compact_rows,
                        "prespecified trace missing or duplicate; substitutions forbidden")
                row = matches[0]
                case_report, _ = audit_case(directory, row, compact_rows[key], instance,
                                           cases["UC-s000"], bank)
                report["cases"].append(case_report)
                report["verified_case_count"] += 1
                selected.append(row)
            require(report["verified_case_count"] == 6, "not all six traces verified")
            report["retained_traces"] = retain_selected_traces(directory, output, selected, bank)
            report["verified_requests"] = sum(row["replay"]["exact_requests_verified"]
                                              for row in report["cases"])
            report["status"] = "COMPLETE_TRACE_AUDIT"
    except Exception as error:
        # An unavailable/corrupted historical artifact cannot authorize replacement.
        report["fault"] = {"type": type(error).__name__, "message": str(error),
                           "replacement_selected": False}
        report["status"] = "PARTIAL_TRACE_AUDIT"
    write_json(output / "trace-audit.json", report)
    write_file_manifest(output)
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--expected-sha", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    report = audit(args.expected_sha, args.output)
    print(f"{report['status']}: {report['verified_case_count']}/6 historical traces; no new GA runs")


if __name__ == "__main__":
    main()
