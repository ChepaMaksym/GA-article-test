"""Authorized CI preparation and the eighteen fixed technical searches only."""
from __future__ import annotations

from copy import deepcopy
import gzip
import io
import json
from pathlib import Path
import shutil
from time import monotonic, perf_counter_ns

from . import authority
from .exact import certify_problem
from .inputs import audit_corpus, make_bank, problem_sha256, task_specs, validate_bank
from .observations import extract
from .verification import verify_log
from ..presentation_package.program.ga_core import (
    create_random_generators, parameter_controller, run_ga,
)


TOTAL_EVALUATIONS = 50000
PILOT_POPULATIONS = (2, 25000)
PILOT_SEARCH_SEED = 129999
PILOT_PREPARATION_SEED = 129998
PREPARATION_TOTAL_SECONDS = 15 * 60
EXACT_CASE_SECONDS = 90
REGISTRY_SCHEMA = "population-size-pilot-preparation-v1"
ENVELOPE_SCHEMA = "population-size-run-v1"


def _fresh_output(output):
    path = Path(output).resolve()
    authority.require(not path.is_relative_to(authority.ROOT.resolve()), "Evidence output must be outside the checkout")
    authority.require(not path.exists() or not any(path.iterdir()), "Existing evidence is never overwritten")
    path.mkdir(parents=True, exist_ok=True)
    return path


def _descriptor(root, path):
    return {"path": Path(path).relative_to(root).as_posix(), **authority.identity(path)}


class _LimitedWriter:
    """Stop compressed writes at the worker's remaining registered byte limit."""
    def __init__(self, stream, byte_limit):
        self.stream = stream
        self.byte_limit = byte_limit
        self.written = 0

    def write(self, value):
        if self.written + len(value) > self.byte_limit:
            raise ValueError("Registered compressed evidence limit reached")
        written = self.stream.write(value)
        self.written += written
        return written

    def tell(self):
        return self.stream.tell()

    def flush(self):
        self.stream.flush()


def _write_gzip_json(path, value, *, byte_limit):
    authority.require(type(byte_limit) is int and byte_limit > 0, "No remaining compressed output allowance")
    path = Path(path)
    authority.require(not path.exists(), "A compressed evidence file already exists")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as raw:
        limited = _LimitedWriter(raw, byte_limit)
        with gzip.GzipFile(filename="", mode="wb", fileobj=limited, compresslevel=6, mtime=0) as compressed:
            with io.TextIOWrapper(compressed, encoding="utf-8", newline="\n") as text:
                # Streaming avoids one enormous additional JSON string in memory.
                json.dump(value, text, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)
                text.write("\n")


def _read_gzip_json(path):
    with gzip.open(path, "rt", encoding="utf-8") as stream:
        return json.load(stream)


def _assert_deadline(deadline):
    if monotonic() >= deadline:
        raise TimeoutError("Registered pilot preparation deadline reached")


def _output_bytes(directory):
    return sum(path.stat().st_size for path in Path(directory).rglob("*") if path.is_file())


def prepare_pilot(source_root, output, permit):
    """Audit nine cases, certify exact optima and freeze each common bank once."""
    provenance = authority.check_permit(permit, "prepare-pilot")
    output = _fresh_output(output)
    started = perf_counter_ns()
    deadline = monotonic() + PREPARATION_TOTAL_SECONDS
    authority.write_json(output / "preparation_progress.json", {
        "status": "INCOMPLETE", "expected_cases": 9, "completed_cases": 0,
        "provenance": provenance, "new_search_runs": 0})
    cases = []
    try:
        corpus_started = perf_counter_ns()
        corpus = audit_corpus(source_root, "pilot", provenance=provenance)
        corpus_ns = perf_counter_ns() - corpus_started
        authority.write_json(output / "corpus.json", corpus)
        # Retain the small audited source inputs with the prepared evidence.
        for row in corpus["source_files"]:
            source = Path(source_root) / row["source_path"]
            destination = output / "source" / row["source_path"]
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, destination)
        shutil.copyfile(Path(source_root) / "source_snapshot.json", output / "source" / "source_snapshot.json")
        _assert_deadline(deadline)
        for case in corpus["cases"]:
            _assert_deadline(deadline)
            folder = output / "cases" / case["task_id"]
            folder.mkdir(parents=True)
            problem = deepcopy(case["problem"])
            authority.write_json(folder / "problem.json", problem)
            certificate_started = perf_counter_ns()
            certificate = certify_problem(problem, deadline=min(deadline, monotonic() + EXACT_CASE_SECONDS))
            certificate_ns = perf_counter_ns() - certificate_started
            authority.require(certificate["optimum"] > 0, "Relative quality requires a positive exact optimum")
            certificate.update(problem_sha256=case["problem_sha256"], source_sha256=case["source_sha256"])
            authority.write_json(folder / "certificate.json", certificate)
            _assert_deadline(deadline)
            bank_started = perf_counter_ns()
            bank, metadata = make_bank(problem, PILOT_PREPARATION_SEED, case["task_index"], bank_size=25000)
            bank_preparation_ns = perf_counter_ns() - bank_started
            verification_started = perf_counter_ns()
            verification = validate_bank(problem, bank, metadata)
            bank_verification_ns = perf_counter_ns() - verification_started
            metadata.update(provenance=provenance, source_sha256=case["source_sha256"],
                            preparation_seed=PILOT_PREPARATION_SEED)
            authority.write_json(folder / "bank_metadata.json", metadata)
            serialization_started = perf_counter_ns()
            remaining_bytes = authority.BYTE_RESERVATIONS["prepare-pilot"] - _output_bytes(output) - 1024 * 1024
            _write_gzip_json(folder / "bank.json.gz", bank, byte_limit=remaining_bytes)
            serialization_ns = perf_counter_ns() - serialization_started
            cases.append({key: case[key] for key in ("task_id", "n", "class_label", "family", "index", "task_index",
                                                     "source_path", "source_sha256", "problem_sha256")})
            cases[-1].update(
                files={"problem": _descriptor(output, folder / "problem.json"),
                       "certificate": _descriptor(output, folder / "certificate.json"),
                       "bank": _descriptor(output, folder / "bank.json.gz"),
                       "bank_metadata": _descriptor(output, folder / "bank_metadata.json")},
                physical_preparation_evaluations=25000,
                independent_verification_evaluations=verification["independent_verification_evaluations"],
                timing_ns={"certification": certificate_ns, "bank_preparation": bank_preparation_ns,
                           "bank_verification": bank_verification_ns, "bank_serialization": serialization_ns})
            del bank
            authority.write_json(output / "preparation_progress.json", {
                "status": "INCOMPLETE", "expected_cases": 9, "completed_cases": len(cases),
                "provenance": provenance, "new_search_runs": 0})
            _assert_deadline(deadline)
        authority.require(len(cases) == 9, "Prepared pilot case set is incomplete")
        registry = {"schema": REGISTRY_SCHEMA, "status": "PREPARED_CERTIFIED_PILOT_INPUTS", "mode": "pilot",
                    "provenance": provenance, "search_seed": PILOT_SEARCH_SEED,
                    "preparation_seed": PILOT_PREPARATION_SEED, "bank_size": 25000,
                    "total_evaluations_per_run": TOTAL_EVALUATIONS,
                    "populations": list(PILOT_POPULATIONS), "cases": cases,
                    "corpus": _descriptor(output, output / "corpus.json"),
                    "physical_preparation_evaluations": 9 * 25000,
                    "independent_bank_verification_evaluations": 9 * 25000,
                    "timing_ns": {"corpus_audit": corpus_ns, "total": perf_counter_ns() - started},
                    "new_search_runs": 0}
        authority.write_json(output / "registry.json", registry)
        authority.write_json(output / "preparation_progress.json", {
            "status": "COMPLETE", "expected_cases": 9, "completed_cases": 9,
            "provenance": provenance, "new_search_runs": 0})
        authority.write_manifest(output)
        authority.require(_output_bytes(output) <= authority.BYTE_RESERVATIONS["prepare-pilot"],
                          "Prepared evidence exceeds the registered byte allowance")
        return registry
    except Exception as error:
        authority.write_json(output / "preparation_progress.json", {
            "status": "FAILED", "expected_cases": 9, "completed_cases": len(cases),
            "error_type": type(error).__name__, "error": str(error),
            "provenance": provenance, "new_search_runs": 0})
        authority.write_manifest(output)
        raise


def _load_member(root, descriptor, *, compressed=False):
    authority.require(type(descriptor) is dict and set(descriptor) == {"path", "bytes", "sha256"},
                      "Wrong prepared member descriptor")
    path = authority.safe_child(root, descriptor["path"])
    authority.require(path.is_file() and not path.is_symlink()
                      and authority.identity(path) == {"bytes": descriptor["bytes"], "sha256": descriptor["sha256"]},
                      "Prepared input member checksum differs")
    return _read_gzip_json(path) if compressed else authority.read_json(path)


def _check_certificate(problem, certificate, source_case):
    authority.require(certificate.get("status") == "CERTIFIED_TWO_INDEPENDENT_EXACT_ORACLES"
                      and certificate.get("problem_sha256") == source_case["problem_sha256"]
                      and certificate.get("source_sha256") == source_case["source_sha256"],
                      "Prepared exact reference belongs to another problem")
    optimum = certificate.get("optimum")
    authority.require(type(optimum) is int and optimum > 0, "Exact optimum must be a positive integer")
    for field in ("capacity_certificate", "profit_certificate"):
        value = certificate[field]
        mask = value.get("witness_mask")
        authority.require(type(mask) is str and len(mask) == problem["n"] and set(mask) <= {"0", "1"},
                          "Malformed prepared exact witness")
        weight = sum(w for w, bit in zip(problem["weights"], mask, strict=True) if bit == "1")
        profit = sum(v for v, bit in zip(problem["profits"], mask, strict=True) if bit == "1")
        authority.require(value.get("optimum_profit") == value.get("witness_profit") == profit == optimum
                          and value.get("witness_weight") == weight <= problem["capacity"],
                          "A retained exact witness is not feasible or has the wrong value")
    return optimum


def _peak_rss_bytes():
    import resource
    # The authorized environment is Linux, where ru_maxrss is measured in KiB.
    return int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss) * 1024


def run_worker(prepared_root, worker_index, output, permit):
    """Execute the two registered populations for exactly one prepared case."""
    provenance = authority.check_permit(permit, "pilot")
    authority.require(type(worker_index) is int and worker_index in authority.PILOT_WORKERS, "Unregistered pilot worker")
    prepared_root = Path(prepared_root).resolve()
    validation_started = perf_counter_ns()
    authority.verify_manifest(prepared_root)
    registry = authority.read_json(prepared_root / "registry.json")
    authority.require(registry.get("schema") == REGISTRY_SCHEMA
                      and registry.get("status") == "PREPARED_CERTIFIED_PILOT_INPUTS"
                      and registry.get("mode") == "pilot" and len(registry.get("cases", [])) == 9
                      and registry.get("total_evaluations_per_run") == TOTAL_EVALUATIONS
                      and registry.get("populations") == list(PILOT_POPULATIONS)
                      and registry.get("bank_size") == 25000
                      and registry.get("search_seed") == PILOT_SEARCH_SEED,
                      "Unexpected or incomplete pilot registry")
    # Freezing the prepared artifact adds a receipt commit before the pilot.
    # Scientific files must remain identical; the two commit IDs may differ.
    authority.require(registry["provenance"].get("protocol_id") == provenance.get("protocol_id")
                      and registry["provenance"]["source_manifest"] == provenance["source_manifest"],
                      "Preparation and search use different scientific sources")
    expected_specs = task_specs("pilot")
    for expected, actual in zip(expected_specs, registry["cases"], strict=True):
        authority.require(all(actual.get(key) == expected[key] for key in
                              ("task_id", "n", "class_label", "family", "index", "task_index", "source_path")),
                          "Pilot task order or identity differs")
    case = registry["cases"][worker_index]
    problem = _load_member(prepared_root, case["files"]["problem"])
    authority.require(problem_sha256(problem) == case["problem_sha256"] and problem["n"] == case["n"],
                      "Prepared problem vectors differ")
    certificate = _load_member(prepared_root, case["files"]["certificate"])
    optimum = _check_certificate(problem, certificate, case)
    bank = _load_member(prepared_root, case["files"]["bank"], compressed=True)
    metadata = _load_member(prepared_root, case["files"]["bank_metadata"])
    authority.require(metadata.get("provenance") == registry["provenance"]
                      and metadata.get("source_sha256") == case["source_sha256"]
                      and metadata.get("seed") == metadata.get("preparation_seed") == PILOT_PREPARATION_SEED
                      and metadata.get("task_index") == case["task_index"] and metadata.get("bank_size") == 25000,
                      "Wrong or mixed initial bank identity")
    bank_verification = validate_bank(problem, bank, metadata)
    input_validation_ns = perf_counter_ns() - validation_started
    output = _fresh_output(output)
    records = []
    authority.write_json(output / "worker_progress.json", {"status": "INCOMPLETE", "worker_index": worker_index,
                         "task_id": case["task_id"], "expected_runs": 2, "completed_runs": 0, "provenance": provenance})
    try:
        for population_size in PILOT_POPULATIONS:
            initial_population = {"masks": bank["masks"][:population_size], "scores": bank["scores"][:population_size]}
            initial_parameters = {"p_m": 1 / problem["n"], "p_c": 0.9, "target_mu": population_size,
                                  "tournament_size": 2, "elite_count": 1}
            generators = create_random_generators(PILOT_SEARCH_SEED, case["task_index"], 0)
            log = run_ga(problem, initial_population, parameter_controller(0), generators,
                         budget=TOTAL_EVALUATIONS - population_size, initial_parameters=initial_parameters)
            verification_started = perf_counter_ns()
            verification = verify_log(log)
            verification_ns = perf_counter_ns() - verification_started
            compact_verification = {key: value for key, value in verification.items() if key != "derived_metrics"}
            del verification
            observation_started = perf_counter_ns()
            observations = extract(log, TOTAL_EVALUATIONS, optimum)
            observation_ns = perf_counter_ns() - observation_started
            run_identity = {"task_id": case["task_id"], "n": case["n"], "class_label": case["class_label"],
                            "family": case["family"], "seed": PILOT_SEARCH_SEED, "mu": population_size,
                            "total_evaluations": TOTAL_EVALUATIONS}
            source = {"provenance": provenance, "prepared_registry": authority.identity(prepared_root / "registry.json"),
                      "prepared_file_manifest": authority.identity(prepared_root / "file_manifest.json"),
                      "source_sha256": case["source_sha256"], "problem_sha256": case["problem_sha256"],
                      "bank": case["files"]["bank"], "bank_metadata": case["files"]["bank_metadata"],
                      "certificate": case["files"]["certificate"]}
            envelope = {"schema": ENVELOPE_SCHEMA, "identity": run_identity, "source": source, "core_log": log,
                        "verification": compact_verification, "analysis": observations,
                        "accounting": {"logical_initial_evaluations": population_size,
                                       "logical_new_evaluations": TOTAL_EVALUATIONS - population_size,
                                       "logical_total_evaluations": TOTAL_EVALUATIONS,
                                       "known_score_validation_evaluations": log["summary"]["known_score_validation_evaluations"],
                                       "independent_score_checks": compact_verification["independent_score_checks"]}}
            filename = f"{case['task_id']}-mu{population_size:05d}.json.gz"
            file = output / filename
            used_bytes = _output_bytes(output)
            remaining_bytes = authority.MAX_WORKER_COMPRESSED_BYTES - used_bytes - 1024 * 1024
            serialization_started = perf_counter_ns()
            _write_gzip_json(file, envelope, byte_limit=remaining_bytes)
            serialization_ns = perf_counter_ns() - serialization_started
            records.append({"identity": run_identity, "file": _descriptor(output, file),
                            "verification_status": compact_verification["verification_status"],
                            "final_best_profit": observations["final_best_profit"],
                            "final_gap_percent": observations["final_gap_percent"],
                            "completed_generations": observations["completed_generations"],
                            "terminal_partial_offspring": observations["terminal_partial_offspring"],
                            "timing_ns": {"core": deepcopy(log["timing_ns"]), "verification": verification_ns,
                                          "observations": observation_ns, "serialization": serialization_ns},
                            "peak_rss_bytes": _peak_rss_bytes(), "accounting": envelope["accounting"]})
            del envelope, log, observations
            authority.write_json(output / "worker_progress.json", {"status": "INCOMPLETE", "worker_index": worker_index,
                                 "task_id": case["task_id"], "expected_runs": 2, "completed_runs": len(records),
                                 "provenance": provenance})
        receipt = {"schema": "population-size-pilot-worker-v1", "status": "VERIFIED_TECHNICAL_WORKER",
                   "worker_index": worker_index, "task_id": case["task_id"], "provenance": provenance,
                   "prepared_registry": authority.identity(prepared_root / "registry.json"), "records": records,
                   "physical_bank_preparation_evaluations": 0,
                   "independent_bank_verification_evaluations": bank_verification["independent_verification_evaluations"],
                   "input_validation_ns": input_validation_ns, "peak_rss_bytes": _peak_rss_bytes(),
                   "logical_total_evaluations": 2 * TOTAL_EVALUATIONS,
                   "new_search_evaluations": sum(record["accounting"]["logical_new_evaluations"] for record in records)}
        authority.write_json(output / "worker_receipt.json", receipt)
        authority.write_json(output / "worker_progress.json", {"status": "COMPLETE", "worker_index": worker_index,
                             "task_id": case["task_id"], "expected_runs": 2, "completed_runs": 2,
                             "provenance": provenance})
        authority.write_manifest(output)
        total_bytes = _output_bytes(output)
        authority.require(total_bytes <= authority.MAX_WORKER_COMPRESSED_BYTES, "Worker output exceeds the registered byte allowance")
        return receipt
    except Exception as error:
        authority.write_json(output / "worker_progress.json", {"status": "FAILED", "worker_index": worker_index,
                             "task_id": case["task_id"], "expected_runs": 2, "completed_runs": len(records),
                             "error_type": type(error).__name__, "error": str(error), "provenance": provenance})
        authority.write_manifest(output)
        raise
