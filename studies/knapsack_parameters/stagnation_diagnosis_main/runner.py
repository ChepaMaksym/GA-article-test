"""Authorized main-series wrapper around the unchanged search and diagnosis.

No search, replay, diagnosis, or bank generation is performed on import.
The old 903-bank artifact is consumed with its original provenance, while
each new run carries the separately preregistered main-series identity.
"""

from __future__ import annotations

import gzip
import json
from pathlib import Path
import re
import time

import numpy as np

from ..ga_study.engine import Config, make_rngs, run_search
from ..ga_study.oracle import verify_search
from ..stagnation_diagnosis import runner as technical
from ..stagnation_diagnosis.banks import verify_bank
from ..stagnation_diagnosis.diagnosis import analyze_run, verify_diagnosis
from . import contract as c


SearchProblem = technical.SearchProblem
SEEDS = tuple(range(93001, 93031))
SCIENTIFIC_PROTOCOL_ID = "GA-KNAPSACK-STAGNATION-DIAGNOSIS-V1"
TECHNICAL_FINGERPRINT = "bbe9cf6b252eca08bd40cfd1b830a3b87a94b91b33b9b0fb05a7c2daf9c72197"
BANK_REGISTRY_SHA256 = "a1d8fc9b151d4a229727cfea209bb55b9d09f592a1511c3028df55f4929eba08"
BANK_REGISTRY = (technical.ROOT / "studies/knapsack_parameters/stagnation_diagnosis"
                 / "evidence/prepare-run-39418724226-1/bank_registry.json")
MAX_WORKER_BYTES = 256 * 1024 ** 2
# Keep room for the final 30 compact rows and the nested member ledger.
METADATA_HEADROOM_BYTES = 8 * 1024 ** 2


def _protocol():
    return c.read_json(Path(__file__).with_name("protocol.json"))


def _check_identity(identity):
    protocol = _protocol()
    c.require(identity.get("protocol_id") == protocol["protocol_id"]
              and identity.get("phase") == "main"
              and protocol["authorization"]["main_series_authorized"] is True,
              "Only the separately authorized main series can execute")
    c.require(identity.get("scientific_protocol_id") == SCIENTIFIC_PROTOCOL_ID
              and identity.get("technical_fingerprint") == TECHNICAL_FINGERPRINT
              and identity.get("bank_manifest_sha256") == BANK_REGISTRY_SHA256,
              "Main provenance must retain the exact historical bank identity")
    c.require(all(key in identity for key in c.PROVENANCE_KEYS),
              "Incomplete main provenance")


def _select_instance(instance_id, seed):
    c.require(type(seed) is int and seed in SEEDS, "Unregistered main repeat seed")
    c.require(type(instance_id) is str
              and re.fullmatch(r"(?:UC|WC|SC)-s00[0-9]", instance_id),
              "Unregistered main instance")
    instances, cases, _ = technical.load_context()
    selected = [(ordinal, item) for ordinal, item in enumerate(instances)
                if item.instance_id == instance_id]
    c.require(len(selected) == 1, "Unknown immutable main instance")
    ordinal, instance = selected[0]
    c.require(instance.n == 100, "The main study requires exactly 100 items")
    return ordinal, instance, cases


def _bank_identity(identity):
    """Translate provenance only; never re-label or regenerate the old bank."""
    protocol = _protocol()
    return {"protocol_id": SCIENTIFIC_PROTOCOL_ID,
            "protocol_sha256": protocol["prior_protocol_sha256"],
            "implementation_fingerprint": TECHNICAL_FINGERPRINT,
            "data_manifest_sha256": identity["data_manifest_sha256"],
            "registry_sha256": identity["registry_sha256"],
            "bank_manifest_sha256": BANK_REGISTRY_SHA256}


def _bank_record(instance_id, ordinal, seed):
    c.require(c.identity(BANK_REGISTRY)["sha256"] == BANK_REGISTRY_SHA256,
              "Committed initial-bank ledger changed")
    registry = c.read_json(BANK_REGISTRY)
    c.require(registry.get("schema") == "knapsack-stagnation-banks-v1"
              and registry.get("protocol_id") == SCIENTIFIC_PROTOCOL_ID
              and registry.get("bank_count") == 903
              and registry.get("provenance", {}).get("implementation_fingerprint")
              == TECHNICAL_FINGERPRINT, "Wrong historical bank registry")
    keys = [(row["instance_id"], row["repeat_seed"]) for row in registry["banks"]]
    expected = {(f"{label}-s{index:03d}", repeat)
                for label in ("UC", "WC", "SC") for index in range(10)
                for repeat in SEEDS}
    expected.update((case, 92999) for case in ("UC-s000", "SC-s005", "SC-s000"))
    c.require(len(keys) == len(set(keys)) == 903 and set(keys) == expected,
              "Incomplete, extra, or duplicate historical banks")
    row = next(item for item in registry["banks"]
               if (item["instance_id"], item["repeat_seed"]) == (instance_id, seed))
    c.require(row["case_ordinal"] == ordinal, "Historical bank ordinal differs")
    return row


def _same_identity(value, expected):
    c.require(all(value.get(key) == expected[key] for key in c.PROVENANCE_KEYS)
              and value.get("phase") == "main"
              and value.get("bank_manifest_sha256") == BANK_REGISTRY_SHA256,
              "Mixed main-run provenance")


def execute_case(instance_id, seed, bankbundle, output, identity):
    """Persist every raw request before consulting the independent diagnosis."""
    _check_identity(identity)
    ordinal, instance, cases = _select_instance(instance_id, seed)
    output = technical._new_output(output)
    started = time.monotonic()
    reference = _bank_record(instance_id, ordinal, seed)
    bank, metadata = technical._load_bank(
        bankbundle, instance, ordinal, seed, _bank_identity(identity))
    source = c.ROOT / "studies/knapsack_parameters/inputs/source" / instance.source_path
    summary = {**identity, "schema": "knapsack-stagnation-main-run-v1",
               "instance_id": instance_id, "class_label": instance.class_label,
               "family": instance.family, "repeat_seed": seed,
               "source_sha256": c.identity(source)["sha256"],
               "logical_requests": 5030, "new_evaluations": 5000,
               "initial_evaluations": 30, "status": "INCOMPLETE", "verified": False,
               "timings": {}, "output_bytes": 0}
    timings = summary["timings"]
    try:
        problem = SearchProblem(instance.n, instance.capacity, instance.weights, instance.profits)
        scores = {name: bank[name] for name in ("weight", "profit", "feasible")}
        config = Config(1.0, 0.9, 30)
        rngs = make_rngs({"UC": 0, "WC": 1, "SC": 2}[instance.class_label],
                         instance.index, seed)
        mark = time.monotonic()
        result = run_search(problem, config, bank["masks"], scores, rngs, budget=5030)
        timings["search_seconds"] = time.monotonic() - mark
        mark = time.monotonic()
        raw = output / "raw"
        raw.mkdir()
        np.savez_compressed(raw / "requests.npz", **result["requests"])
        technical._jsonl(raw / "generations.jsonl.gz", result["generations"])
        c.write_json(raw / "search_summary.json", result["summary"])
        c.write_json(raw / "initial_metadata.json", metadata)
        c.write_json(raw / "bank_reference.json", reference)
        c.write_json(raw / "provenance.json", identity)
        c.write_manifest(raw)
        timings["save_seconds"] = time.monotonic() - mark
        mark = time.monotonic()
        summary["search_verification"] = verify_search(
            problem, config, result, initial_masks=bank["masks"], initial_scores=scores)
        c.require(summary["search_verification"]["status"] == "PASS_REPLAY",
                  "Independent search replay failed")
        timings["replay_seconds"] = time.monotonic() - mark
        # Neither this reference nor any neighbor exists in the search interface.
        optimum = cases[instance_id]["payload"]["exact"]["confirmed_optimum"]
        mark = time.monotonic()
        diagnosis = analyze_run(instance, result, optimum)
        timings["diagnosis_seconds"] = time.monotonic() - mark
        mark = time.monotonic()
        certificates = output / "certificates"
        certificates.mkdir()
        for certificate_id, certificate in diagnosis["certificates"].items():
            technical._jsonl(certificates / f"{certificate_id}.jsonl.gz", certificate["neighbors"])
            c.write_json(certificates / f"{certificate_id}.json", certificate["summary"])
        c.write_json(output / "diagnosis.json", diagnosis)
        timings["save_seconds"] += time.monotonic() - mark
        mark = time.monotonic()
        verdict = verify_diagnosis(instance, result, optimum, diagnosis)
        c.require(verdict["status"] == "PASS_DIAGNOSIS", "Independent diagnosis failed")
        timings["certification_verification_seconds"] = time.monotonic() - mark
        summary.update(status="COMPLETE", verified=True,
                       checkpoints=diagnosis["checkpoints"],
                       population_trajectory=diagnosis["population_trajectory"],
                       accounting={**diagnosis["accounting"],
                                   "independent_verification": verdict,
                                   "bank_revalidation_evaluations": 30,
                                   "search_replay_evaluations": 5030,
                                   "worker_verification_total_evaluations":
                                       30 + 5030 + verdict["verification_total_evaluations"]},
                       optimum=optimum, diagnosis_verification=verdict)
    except Exception as error:
        summary["failure"] = {"type": type(error).__name__, "message": str(error)}
        raise
    finally:
        timings["total_seconds"] = time.monotonic() - started
        summary["output_bytes"] = technical._bytes(output)
        c.write_json(output / "worker_summary.json", summary)
        c.write_manifest(output)
    return summary


def execute_batch(instance_id, bankbundle, output, identity):
    """One immutable case and all 30 seeds; failures are retained, never retried."""
    _check_identity(identity)
    _select_instance(instance_id, SEEDS[0])
    output = technical._new_output(output)
    started, rows = time.monotonic(), []
    batch = {**identity, "schema": "knapsack-stagnation-main-worker-v1",
             "instance_id": instance_id, "expected_seeds": list(SEEDS),
             "status": "INCOMPLETE", "completed_count": 0,
             "failed_count": 0, "runs": rows, "payload_bytes": 0}
    try:
        for seed in SEEDS:
            directory = output / "runs" / str(seed)
            try:
                c.require(technical._bytes(output) < MAX_WORKER_BYTES - METADATA_HEADROOM_BYTES,
                          "Worker evidence limit reached; no new search may start")
                row = execute_case(instance_id, seed, bankbundle, directory, identity)
            except Exception as error:
                # If execution got as far as writing its raw journal, preserve it.
                path = directory / "worker_summary.json"
                row = c.read_json(path) if path.exists() else {
                    **identity, "schema": "knapsack-stagnation-main-run-v1",
                    "instance_id": instance_id, "repeat_seed": seed,
                    "class_label": instance_id[:2], "family": instance_id[3:],
                    "status": "INCOMPLETE", "verified": False,
                    "failure": {"type": type(error).__name__, "message": str(error)}}
            rows.append({**row, "run_path": f"runs/{seed}"})
        batch["completed_count"] = sum(row.get("status") == "COMPLETE"
                                       and row.get("verified") is True for row in rows)
        batch["failed_count"] = len(SEEDS) - batch["completed_count"]
        batch["status"] = "COMPLETE" if batch["completed_count"] == 30 else "INCOMPLETE"
    finally:
        batch["elapsed_seconds"] = time.monotonic() - started
        batch["payload_bytes"] = technical._bytes(output)
        c.write_json(output / "worker_summary.json", batch)
        c.write_manifest(output)
    c.require(technical._bytes(output) <= MAX_WORKER_BYTES,
              "Worker materialized evidence exceeds 256 MiB")
    return batch


def verify_saved_case(directory, identity):
    """Replay persisted requests and certificates without any new search or DP."""
    _check_identity(identity)
    c.require(technical.os.environ.get("GITHUB_ACTIONS") == "true", "Replay is CI-only")
    directory = Path(directory)
    c.verify_manifest(directory)
    raw = directory / "raw"
    c.verify_manifest(raw)
    summary = c.read_json(directory / "worker_summary.json")
    _same_identity(summary, identity)
    c.require(summary.get("schema") == "knapsack-stagnation-main-run-v1"
              and summary.get("status") == "COMPLETE" and summary.get("verified") is True,
              "An incomplete saved run cannot be certified as complete")
    _same_identity(c.read_json(raw / "provenance.json"), identity)
    ordinal, instance, cases = _select_instance(summary["instance_id"], summary["repeat_seed"])
    c.require(summary.get("class_label") == instance.class_label
              and summary.get("family") == instance.family,
              "Saved case class or family differs")
    source = c.ROOT / "studies/knapsack_parameters/inputs/source" / instance.source_path
    c.require(summary.get("source_sha256") == c.identity(source)["sha256"],
              "Saved input source bytes changed")
    reference = _bank_record(instance.instance_id, ordinal, summary["repeat_seed"])
    c.require(c.read_json(raw / "bank_reference.json") == reference,
              "Saved start differs from the frozen bank record")
    c.require(c.identity(raw / "initial_metadata.json") == reference["metadata"],
              "Saved initial metadata differs from frozen bytes")
    with np.load(raw / "requests.npz", allow_pickle=False) as stored:
        requests = {name: stored[name].copy() for name in stored.files}
    with gzip.open(raw / "generations.jsonl.gz", "rt", encoding="utf-8") as stream:
        generations = [json.loads(line) for line in stream]
    result = {"summary": c.read_json(raw / "search_summary.json"),
              "requests": requests, "generations": generations}
    bank = {"masks": requests["masks"][:30],
            **{name: requests[name][:30] for name in ("weight", "profit", "feasible")}}
    metadata = c.read_json(raw / "initial_metadata.json")
    verify_bank(instance, ordinal, summary["repeat_seed"], bank, metadata)
    problem = SearchProblem(instance.n, instance.capacity, instance.weights, instance.profits)
    verdict = verify_search(problem, Config(1.0, 0.9, 30), result,
                            initial_masks=bank["masks"],
                            initial_scores={name: bank[name] for name in ("weight", "profit", "feasible")})
    c.require(verdict["status"] == "PASS_REPLAY", "Transported search replay failed")
    optimum = cases[instance.instance_id]["payload"]["exact"]["confirmed_optimum"]
    diagnosis = c.read_json(directory / "diagnosis.json")
    diagnostic_verdict = verify_diagnosis(instance, result, optimum, diagnosis)
    c.require(diagnostic_verdict["status"] == "PASS_DIAGNOSIS", "Transported diagnosis failed")
    c.require(summary["checkpoints"] == diagnosis["checkpoints"]
              and summary["population_trajectory"] == diagnosis["population_trajectory"]
              and summary["optimum"] == optimum
              and summary["diagnosis_verification"] == diagnostic_verdict
              and summary["search_verification"] == verdict,
              "Compact run observations differ from independently replayed raw data")
    c.require(all(summary.get(key) == value for key, value in
                  (("logical_requests", 5030), ("new_evaluations", 5000), ("initial_evaluations", 30))),
              "Saved search accounting differs")
    expected_accounting = {**diagnosis["accounting"],
                           "independent_verification": diagnostic_verdict,
                           "bank_revalidation_evaluations": 30,
                           "search_replay_evaluations": 5030,
                           "worker_verification_total_evaluations":
                               30 + 5030 + diagnostic_verdict["verification_total_evaluations"]}
    c.require(summary["accounting"] == expected_accounting, "Saved diagnosis accounting differs")
    for certificate_id, certificate in diagnosis["certificates"].items():
        path = directory / "certificates"
        c.require(c.read_json(path / f"{certificate_id}.json") == certificate["summary"],
                  "Transported certificate summary differs")
        with gzip.open(path / f"{certificate_id}.jsonl.gz", "rt", encoding="utf-8") as stream:
            neighbors = [json.loads(line) for line in stream]
        c.require(neighbors == certificate["neighbors"], "Transported neighborhood differs")
    summary["aggregate_independent_verification"] = {
        "search": verdict, "diagnosis": diagnostic_verdict,
        "bank_revalidation_evaluations": 30,
        "aggregate_verification_total_evaluations":
            30 + 5030 + diagnostic_verdict["verification_total_evaluations"]}
    return summary


def verify_saved_batch(directory, identity):
    """Return 30 independently reconstructed rows from one transported worker."""
    _check_identity(identity)
    directory = Path(directory)
    c.require(technical._bytes(directory) <= MAX_WORKER_BYTES, "Worker exceeds registered byte limit")
    c.verify_manifest(directory)
    batch = c.read_json(directory / "worker_summary.json")
    _same_identity(batch, identity)
    c.require(batch.get("schema") == "knapsack-stagnation-main-worker-v1"
              and batch.get("status") == "COMPLETE"
              and batch.get("expected_seeds") == list(SEEDS)
              and batch.get("completed_count") == 30 and batch.get("failed_count") == 0,
              "Incomplete or unregistered main worker")
    rows = batch.get("runs")
    c.require(type(rows) is list and len(rows) == 30
              and [row.get("repeat_seed") for row in rows] == list(SEEDS),
              "Missing, duplicate, or reordered main repeats")
    c.require({path.name for path in (directory / "runs").iterdir()}
              == {str(seed) for seed in SEEDS}, "Extra or missing saved run directory")
    verified = []
    for row in rows:
        seed = row["repeat_seed"]
        c.require(row.get("instance_id") == batch["instance_id"]
                  and row.get("run_path") == f"runs/{seed}", "Mixed worker instance or run path")
        saved = c.read_json(directory / "runs" / str(seed) / "worker_summary.json")
        c.require({key: value for key, value in row.items() if key != "run_path"} == saved,
                  "Batch compact row differs from persisted per-run summary")
        started = time.monotonic()
        result = verify_saved_case(directory / "runs" / str(seed), identity)
        result["timings"]["aggregate_reverification_seconds"] = time.monotonic() - started
        verified.append(result)
    return verified
