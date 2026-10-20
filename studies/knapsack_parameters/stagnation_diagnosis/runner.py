"""CI-only orchestration of frozen starts, unchanged GA and post-search audits."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import gzip
import os
import time

import numpy as np

from ..ga_study.engine import Config, make_rngs, run_search
from ..ga_study.oracle import verify_search
from .banks import prepare_bank, verify_bank
from .contract import (ROOT, PROTOCOL_ID, canonical, identity as file_identity,
                       PROVENANCE_KEYS, load_context, read_json, require,
                       verify_manifest, write_json, write_manifest)
from .diagnosis import analyze_run, verify_diagnosis


@dataclass(frozen=True)
class SearchProblem:
    """Only the objective inputs, with no optimum, witnesses or certificates."""

    n: int
    capacity: int
    weights: tuple[int, ...]
    profits: tuple[int, ...]


def expected_banks(instances):
    rows = [(item.instance_id, seed) for item in instances
            for seed in range(93001, 93031)]
    rows.extend((case, 92999) for case in ("UC-s000", "SC-s005", "SC-s000"))
    return rows


def _new_output(output):
    require(os.environ.get("GITHUB_ACTIONS") == "true", "scientific execution is CI-only")
    output = Path(output).resolve()
    require(not output.is_relative_to(ROOT.resolve()), "outputs must be outside checkout")
    require(not output.exists() or not any(output.iterdir()), "do not overwrite evidence")
    output.mkdir(parents=True, exist_ok=True)
    return output


def _jsonl(path, rows):
    with Path(path).open("wb") as raw:
        with gzip.GzipFile(fileobj=raw, mode="wb", filename="", mtime=0) as stream:
            for row in rows:
                stream.write(canonical(row) + b"\n")


def _bytes(directory):
    return sum(path.stat().st_size for path in Path(directory).rglob("*") if path.is_file())


def prepare_inputs(output, identity):
    started = time.monotonic()
    output = _new_output(output)
    instances, _, _ = load_context()
    lookup = {item.instance_id: (ordinal, item) for ordinal, item in enumerate(instances)}
    rows = []
    for instance_id, seed in expected_banks(instances):
        ordinal, instance = lookup[instance_id]
        bank, metadata = prepare_bank(instance, ordinal, seed)
        verified = verify_bank(instance, ordinal, seed, bank, metadata)
        directory = output / "banks" / instance_id / str(seed)
        directory.mkdir(parents=True)
        np.savez_compressed(directory / "bank.npz", **bank)
        write_json(directory / "bank.json", metadata)
        rows.append({"instance_id": instance_id, "repeat_seed": seed,
                     "case_ordinal": ordinal,
                     "arrays_path": (directory / "bank.npz").relative_to(output).as_posix(),
                     "metadata_path": (directory / "bank.json").relative_to(output).as_posix(),
                     "arrays": file_identity(directory / "bank.npz"),
                     "metadata": file_identity(directory / "bank.json"),
                     "verification": verified})
    require(len(rows) == 903, "exactly 900 main and three technical starts required")
    registry = {"schema": "knapsack-stagnation-banks-v1", "protocol_id": PROTOCOL_ID,
                "provenance": identity, "bank_count": len(rows), "instance_count": 30,
                "physical_initial_evaluations": 903 * 30,
                "independent_preparation_verification_evaluations": 903 * 30,
                "banks": rows}
    write_json(output / "bank_registry.json", registry)
    receipt = {**identity, "schema": "knapsack-stagnation-preparation-v1",
               "status": "COMPLETE_VERIFIED_INPUTS", "provenance": identity,
               "bank_count": len(rows), "main_bank_count": 900, "probe_bank_count": 3,
               "bank_manifest_sha256": file_identity(output / "bank_registry.json")["sha256"],
               "initial_evaluations": 27090, "verification_evaluations": 27090,
               "search_evaluations": 0, "elapsed_seconds": time.monotonic() - started}
    write_json(output / "preparation_receipt.json", receipt)
    write_manifest(output)
    return receipt


def _load_bank(bundle, instance, ordinal, seed, provenance):
    bundle = Path(bundle)
    registry_path = bundle / "bank_registry.json"
    registry = read_json(registry_path)
    require(registry.get("schema") == "knapsack-stagnation-banks-v1"
            and registry.get("protocol_id") == PROTOCOL_ID, "wrong bank registry")
    require(file_identity(registry_path)["sha256"] == provenance["bank_manifest_sha256"],
            "bank registry differs from committed freeze")
    instances, _, _ = load_context()
    expected = set(expected_banks(instances))
    keys = [(row["instance_id"], row["repeat_seed"]) for row in registry["banks"]]
    require(len(keys) == len(set(keys)) == 903 and set(keys) == expected,
            "missing, extra or duplicate banks")
    old = registry["provenance"]
    for field in ("protocol_id", "protocol_sha256", "implementation_fingerprint",
                  "data_manifest_sha256", "registry_sha256"):
        require(old[field] == provenance[field], f"mixed bank provenance: {field}")
    match = next(row for row in registry["banks"]
                 if (row["instance_id"], row["repeat_seed"]) == (instance.instance_id, seed))
    require(match["case_ordinal"] == ordinal, "bank case ordinal mismatch")
    paths = []
    for field, digest_field in (("arrays_path", "arrays"), ("metadata_path", "metadata")):
        path = bundle / match[field]
        require(path.resolve().is_relative_to(bundle.resolve()) and not path.is_symlink(),
                "bank path escapes bundle")
        require(file_identity(path) == match[digest_field], "bank member hash mismatch")
        paths.append(path)
    with np.load(paths[0], allow_pickle=False) as stored:
        bank = {name: stored[name].copy() for name in stored.files}
    metadata = read_json(paths[1])
    verify_bank(instance, ordinal, seed, bank, metadata)
    return bank, metadata


def execute_case(instance_id, seed, bankbundle, output, identity):
    """One full raw journal is persisted before replay and locality evaluation."""
    started = time.monotonic()
    output = _new_output(output)
    instances, cases, _ = load_context()
    phase = identity.get("phase", "probe")
    require(phase == "probe" and seed == 92999
            and instance_id in ("UC-s000", "SC-s005", "SC-s000"),
            "only the three authorized technical probes can execute")
    selected = [(i, item) for i, item in enumerate(instances) if item.instance_id == instance_id]
    require(len(selected) == 1, "unknown immutable instance")
    ordinal, instance = selected[0]
    bank, metadata = _load_bank(bankbundle, instance, ordinal, seed, identity)
    source_sha = file_identity(ROOT / "studies/knapsack_parameters/inputs/source"
                               / instance.source_path)["sha256"]
    summary = {**identity, "phase": phase, "instance_id": instance_id,
               "class_label": instance.class_label, "family": instance.family,
               "repeat_seed": seed, "source_sha256": source_sha,
               "logical_requests": 5030, "new_evaluations": 5000,
               "initial_evaluations": 30, "status": "INCOMPLETE", "verified": False,
               "timings": {}, "output_bytes": 0}
    timings = summary["timings"]
    try:
        problem = SearchProblem(instance.n, instance.capacity, instance.weights, instance.profits)
        scores = {name: bank[name] for name in ("weight", "profit", "feasible")}
        config = Config(1.0, 0.9, 30)
        rngs = make_rngs({"UC": 0, "WC": 1, "SC": 2}[instance.class_label], instance.index, seed)
        mark = time.monotonic()
        result = run_search(problem, config, bank["masks"], scores, rngs, budget=5030)
        timings["search_seconds"] = time.monotonic() - mark
        mark = time.monotonic()
        raw = output / "raw"
        raw.mkdir()
        np.savez_compressed(raw / "requests.npz", **result["requests"])
        _jsonl(raw / "generations.jsonl.gz", result["generations"])
        write_json(raw / "search_summary.json", result["summary"])
        write_json(raw / "initial_metadata.json", metadata)
        write_json(raw / "provenance.json", identity)
        write_manifest(raw)
        timings["save_seconds"] = time.monotonic() - mark
        mark = time.monotonic()
        summary["search_verification"] = verify_search(
            problem, config, result, initial_masks=bank["masks"], initial_scores=scores)
        require(summary["search_verification"]["status"] == "PASS_REPLAY", "independent replay failed")
        timings["replay_seconds"] = time.monotonic() - mark
        optimum = cases[instance_id]["payload"]["exact"]["confirmed_optimum"]
        mark = time.monotonic()
        diagnosis = analyze_run(instance, result, optimum)
        timings["diagnosis_seconds"] = time.monotonic() - mark
        directory = output / "certificates"
        directory.mkdir()
        mark = time.monotonic()
        for certificate_id, certificate in diagnosis["certificates"].items():
            _jsonl(directory / f"{certificate_id}.jsonl.gz", certificate["neighbors"])
            write_json(directory / f"{certificate_id}.json", certificate["summary"])
        write_json(output / "diagnosis.json", diagnosis)
        timings["save_seconds"] += time.monotonic() - mark
        mark = time.monotonic()
        verdict = verify_diagnosis(instance, result, optimum, diagnosis)
        require(verdict["status"] == "PASS_DIAGNOSIS", "independent diagnosis rejected")
        timings["certification_verification_seconds"] = time.monotonic() - mark
        summary.update(status="COMPLETE", verified=True, checkpoints=diagnosis["checkpoints"],
                       population_trajectory=diagnosis["population_trajectory"],
                       accounting={**diagnosis["accounting"], "independent_verification": verdict,
                                   "bank_revalidation_evaluations": 30,
                                   "search_replay_evaluations": 5030,
                                   "worker_verification_total_evaluations":
                                       30 + 5030 + verdict["verification_total_evaluations"]},
                       optimum=optimum, diagnosis_verification=verdict)
        require(_bytes(output) < 512 * 1024 ** 2, "compressed worker evidence exceeds 512 MiB")
    except Exception as error:
        summary["failure"] = {"type": type(error).__name__, "message": str(error)}
        raise
    finally:
        timings["total_seconds"] = time.monotonic() - started
        summary["output_bytes"] = _bytes(output)
        write_json(output / "worker_summary.json", summary)
        write_manifest(output)
    return summary


def verify_saved_case(directory, identity):
    """Reconstruct a transported journal; never perform a new search or DP."""
    require(os.environ.get("GITHUB_ACTIONS") == "true", "independent replay is CI-only")
    directory = Path(directory)
    verify_manifest(directory)
    verify_manifest(directory / "raw")
    summary = read_json(directory / "worker_summary.json")
    require(all(summary.get(key) == identity[key] for key in PROVENANCE_KEYS),
            "saved worker provenance differs from aggregation")
    require(summary.get("bank_manifest_sha256") == identity["bank_manifest_sha256"],
            "saved worker used a different initial bank registry")
    require(summary.get("status") == "COMPLETE" and summary.get("verified") is True,
            "cannot certify an incomplete worker as complete")
    raw = directory / "raw"
    require(all(read_json(raw / "provenance.json").get(key) == identity[key]
                for key in PROVENANCE_KEYS), "raw journal provenance mismatch")
    require(read_json(raw / "provenance.json").get("bank_manifest_sha256")
            == identity["bank_manifest_sha256"], "raw journal bank registry mismatch")
    with np.load(raw / "requests.npz", allow_pickle=False) as stored:
        requests = {name: stored[name].copy() for name in stored.files}
    with gzip.open(raw / "generations.jsonl.gz", "rt", encoding="utf-8") as stream:
        import json
        generations = [json.loads(line) for line in stream]
    result = {"summary": read_json(raw / "search_summary.json"),
              "requests": requests, "generations": generations}
    instances, cases, _ = load_context()
    choices = [(i, item) for i, item in enumerate(instances)
               if item.instance_id == summary["instance_id"]]
    require(len(choices) == 1, "unknown replay instance")
    ordinal, instance = choices[0]
    source = ROOT / "studies/knapsack_parameters/inputs/source" / instance.source_path
    require(summary.get("source_sha256") == file_identity(source)["sha256"],
            "saved worker source bytes differ from immutable input")
    require(summary["repeat_seed"] == 92999 and summary["phase"] == "probe"
            and instance.instance_id in ("UC-s000", "SC-s005", "SC-s000"),
            "unregistered saved run")
    metadata = read_json(raw / "initial_metadata.json")
    bank = {"masks": requests["masks"][:30],
            **{name: requests[name][:30] for name in ("weight", "profit", "feasible")}}
    verify_bank(instance, ordinal, summary["repeat_seed"], bank, metadata)
    problem = SearchProblem(instance.n, instance.capacity, instance.weights, instance.profits)
    verdict = verify_search(problem, Config(1.0, 0.9, 30), result,
                            initial_masks=bank["masks"],
                            initial_scores={name: bank[name] for name in ("weight", "profit", "feasible")})
    require(verdict["status"] == "PASS_REPLAY", "transported search replay failed")
    optimum = cases[instance.instance_id]["payload"]["exact"]["confirmed_optimum"]
    diagnosis = read_json(directory / "diagnosis.json")
    diagnostic_verdict = verify_diagnosis(instance, result, optimum, diagnosis)
    require(diagnostic_verdict["status"] == "PASS_DIAGNOSIS", "transported diagnosis failed")
    require(summary["checkpoints"] == diagnosis["checkpoints"]
            and summary["population_trajectory"] == diagnosis["population_trajectory"],
            "compact observations differ from independently verified raw readout")
    for certificate_id, certificate in diagnosis["certificates"].items():
        path = directory / "certificates"
        require(read_json(path / f"{certificate_id}.json") == certificate["summary"],
                "transported certificate summary mismatch")
        with gzip.open(path / f"{certificate_id}.jsonl.gz", "rt", encoding="utf-8") as stream:
            rows = [json.loads(line) for line in stream]
        require(rows == certificate["neighbors"], "transported neighborhood differs")
    summary["aggregate_independent_verification"] = {
        "search": verdict, "diagnosis": diagnostic_verdict,
        "bank_revalidation_evaluations": 30,
        "aggregate_verification_total_evaluations":
            30 + 5030 + diagnostic_verdict["verification_total_evaluations"]}
    return summary
