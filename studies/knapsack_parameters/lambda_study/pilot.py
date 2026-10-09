"""CI-only bounded author-source probes; no paper or knapsack campaign entrypoint."""

from __future__ import annotations

import argparse
from datetime import datetime
import importlib
import io
import math
import os
from pathlib import Path, PurePosixPath
import platform
import random
import re
import resource
import signal
import subprocess
import sys
import time
import traceback
import zipfile

from .contract import (BRANCH, MODULE_ROOT, PROTOCOL_ID, REPOSITORY, ROOT, authenticate,
                       canonical_bytes, file_identity, read_json, require,
                       sha256_bytes, write_file_manifest, write_json)
from ..ga_study.transport import (api_get, download_zip,
                                 verify_artifact_identity)
from .source_audit import MAX_DOWNLOAD, extract_snapshot

SEED = 63001
CALL_CAP = 100000
GA_SECONDS = 30
CASES = {
    "onemax-100": {"language": "python", "problem": "OneMax", "n": 100, "k": 1,
                   "algorithm": "OnePlusLambdaCommaLambdaSA"},
    "jump-20-2": {"language": "python", "problem": "Jump", "n": 20, "k": 2,
                  "algorithm": "OnePlusLambdaCommaLambdaSAJUMP"},
    "maxsat-10": {"language": "cpp", "problem": "MAXSAT", "n": 10,
                  "problem_seed": 100, "algorithm": "LambdaLambda"},
}
MODULE_NAME = "studies.knapsack_parameters.lambda_study.pilot"
CPP_FLAGS = ["-std=c++11", "-O3", "-funroll-loops", "-pedantic", "-Wall", "-fmessage-length=0"]
VALID_TECHNICAL_STATUSES = {"TECHNICAL_PREFIX", "TECHNICAL_TERMINAL", "TECHNICAL_CALL_CAP", "TECHNICAL_TIME_CAP"}
FROZEN_IDENTITY_FIELDS = ("protocol_id", "protocol_sha256", "registration_commit_sha",
    "implementation_fingerprint", "author_repository", "author_commit_sha", "input_repository",
    "input_commit_sha", "python_version", "runtime_lock_sha256", "author_runtime_sha256",
    "author_requirements_sha256", "repository", "full_reproduction_authorized", "knapsack_execution_authorized")


class TechnicalStop(Exception):
    """A technical cap, never a paper stopping rule or completed replication."""


def evidence_directory(path):
    path = Path(path).resolve()
    require(not path.is_relative_to(ROOT), "evidence must be outside the checkout")
    require(not path.exists() or not any(path.iterdir()), "evidence must not be overwritten")
    path.mkdir(parents=True, exist_ok=True)
    return path


def profile(case):
    require(case in CASES, "only three registered technical cases are available")
    return {"case": case, **CASES[case], "seed": SEED, "purpose": "TECHNICAL_ONLY",
            "max_objective_calls": CALL_CAP, "max_ga_seconds": GA_SECONDS,
            "compatibility_patches": [], "author_operators_unchanged": True,
            "runtime_profile": "AUDIT_RUNTIME: CPython 3.12.14, NumPy 2.2.6, SciPy 1.15.3; "
                               "not a recovered original author environment",
            "scientific_quality_analysis": False, "published_batch_rng_replay": False,
            "python_parameters": {"lambda_cap": CASES[case]["n"], "crossover_rate": 1,
                                  "update_factor": 1.5} if CASES[case]["language"] == "python" else None,
            "cpp_flags": CPP_FLAGS if CASES[case]["language"] == "cpp" else None,
            "batch_rng_note": "Fresh technical seed; preceding published runs are not replayed. "
                              "This does not reproduce later states of a shared batch RNG."}


def rng_identity(numpy):
    state = numpy.random.get_state()
    numpy_state = [state[0], state[1].tolist(), int(state[2]), int(state[3]), float(state[4])]
    return {"python_random_sha256": sha256_bytes(repr(random.getstate()).encode()),
            "numpy_random_sha256": sha256_bytes(canonical_bytes(numpy_state))}


def evidence_member(root, relative):
    """Linux author filenames include colons; reject Windows drive paths instead."""
    pure = PurePosixPath(relative)
    require(relative and not pure.is_absolute() and ".." not in pure.parts and
            "\\" not in relative and all(not re.match(r"^[A-Za-z]:", part) for part in pure.parts),
            "unsafe ZIP member")
    require(pure.as_posix() == relative.rstrip("/"), "noncanonical ZIP member")
    target = root.joinpath(*pure.parts)
    require(target.resolve().is_relative_to(root) and not target.is_symlink(), "member escapes artifact")
    return target


def verify_evidence(directory):
    directory = Path(directory).resolve()
    manifest = read_json(directory / "file_manifest.json")
    require(manifest["schema_version"] == "ga-knapsack-files-v1" and manifest["excludes_self"] is True,
            "unexpected evidence manifest")
    seen = set()
    for row in manifest["files"]:
        require(row["path"] not in seen and row["path"] != "file_manifest.json", "duplicate or self manifest member")
        seen.add(row["path"])
        require(file_identity(evidence_member(directory, row["path"])) ==
                {"bytes": row["bytes"], "sha256": row["sha256"]}, "artifact member hash or length differs")
    require({path.relative_to(directory).as_posix() for path in directory.rglob("*") if path.is_file()} ==
            seen | {"file_manifest.json"}, "unexpected or missing artifact file")


def extract_evidence(raw, directory):
    """Reuse authenticated transport while retaining valid Linux corpus names."""
    directory = Path(directory).resolve()
    directory.mkdir(parents=True, exist_ok=False)
    seen = set()
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        require(sum(row.file_size for row in archive.infolist()) <= 8 * 1024 ** 3, "ZIP exceeds extraction guard")
        for row in archive.infolist():
            require(row.filename not in seen and ((row.external_attr >> 16) & 0o170000) != 0o120000,
                    "duplicate ZIP entry or symbolic link")
            seen.add(row.filename)
            target = evidence_member(directory, row.filename)
            if row.is_dir():
                target.mkdir(parents=True, exist_ok=True)
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                with archive.open(row) as source, target.open("wb") as output:
                    for block in iter(lambda: source.read(1024 * 1024), b""):
                        output.write(block)
    verify_evidence(directory)
    return directory


class BoundedEvaluator:
    """Pass every query unchanged to the author objective; count calls independently."""

    def __init__(self, original, *, cap=CALL_CAP, seconds=GA_SECONDS, clock=time.monotonic):
        require(0 < cap <= CALL_CAP and 0 < seconds <= GA_SECONDS, "technical caps cannot increase")
        self.original, self.cap, self.seconds, self.clock = original, cap, seconds, clock
        self.calls = 0
        self.started = clock()

    def __getattr__(self, name):
        return getattr(self.original, name)

    def evaluate(self, bit_string):
        if self.clock() - self.started >= self.seconds:
            raise TechnicalStop("TECHNICAL_TIME_CAP")
        if self.calls >= self.cap:
            raise TechnicalStop("TECHNICAL_CALL_CAP")
        self.calls += 1
        return self.original.evaluate(bit_string)


def bounded_iterations(evaluator, factory, args):
    algorithm = None
    status = "TECHNICAL_PREFIX"
    error = None
    try:
        algorithm = factory(evaluator, *args)
        while not algorithm.solved:
            if evaluator.clock() - evaluator.started >= evaluator.seconds:
                raise TechnicalStop("TECHNICAL_TIME_CAP")
            next(algorithm)
        status = "TECHNICAL_TERMINAL"
    except TechnicalStop as stopped:
        status = str(stopped)
    except Exception:
        status, error = "TECHNICAL_FAILURE", traceback.format_exc()
    summary = {"status": status, "objective_calls": evaluator.calls, "failure": error,
               "ga_wall_seconds": evaluator.clock() - evaluator.started,
               "paper_reproduction": "NOT_RUN", "full_gate": "BLOCKED_NOT_AUTHORIZED",
               "incomplete_generation_committed_as_result": False}
    if algorithm is not None:
        summary["author_state"] = {"generations": int(algorithm.generations),
             "reported_evaluations": int(algorithm.evaluations),
             "reported_evaluations_are_objective_calls": False,
             "lambda": float(algorithm.offspring_size), "solved_flag": bool(algorithm.solved),
             "parent_mask_sha256": sha256_bytes(str(algorithm.parent[1]).encode()),
             "fitness_log_entries": len(algorithm.fit_gen), "lambda_log_entries": len(algorithm.lambda_gen)}
    return summary


def python_worker(case, author, output, identity):
    """Import the unchanged complete module, including its original dependencies."""
    require(CASES[case]["language"] == "python", "wrong worker case")
    author = Path(author).resolve()
    bundle = author.parents[1]
    require(author == bundle / "source/author", "worker must read the authenticated source tree")
    descriptor = committed_descriptor(identity)
    for filename, field in (("source_manifest.json", "source_manifest_sha256"),
                            ("audit-report.json", "audit_report_sha256")):
        require(file_identity(bundle / filename)["sha256"] == descriptor[field], "worker source differs from frozen descriptor")
    verify_evidence(bundle)
    p = profile(case)
    report = {"schema_version": "ga-lambda-python-probe-v1", "profile": p,
              "profile_sha256": sha256_bytes(canonical_bytes(p)), "seed": SEED,
              "paper_reproduction": "NOT_RUN", "full_gate": "BLOCKED_NOT_AUTHORIZED"}
    algorithm_started = None
    before_cpu = resource.getrusage(resource.RUSAGE_SELF)
    try:
        import numpy
        import scipy
        require(numpy.__version__ == "2.2.6" and scipy.__version__ == "1.15.3", "audit dependency profile differs")
        random.seed(SEED)
        numpy.random.seed(SEED)
        report["rng_initial"] = rng_identity(numpy)
        sys.path.insert(0, str(Path(author) / "Python-code"))
        algorithms = importlib.import_module("utils.journalalgorithms")
        functions = importlib.import_module("utils.functions")
        require(Path(algorithms.__file__).resolve() == author / "Python-code/utils/journalalgorithms.py" and
                Path(functions.__file__).resolve() == author / "Python-code/utils/functions.py",
                "author import resolved outside frozen source")
        original = getattr(functions, p["problem"])(p["n"], p["k"])
        evaluator = BoundedEvaluator(original)
        def alarm(signum, frame):
            raise TechnicalStop("TECHNICAL_TIME_CAP")
        signal.signal(signal.SIGALRM, alarm)
        signal.setitimer(signal.ITIMER_REAL, GA_SECONDS)
        algorithm_started = time.monotonic()
        try:
            report.update(bounded_iterations(evaluator, getattr(algorithms, p["algorithm"]),
                           (p["n"], None, p["n"], 1, None, 1.5, None)))
        finally:
            signal.setitimer(signal.ITIMER_REAL, 0)
        report["rng_final"] = rng_identity(numpy)
    except Exception:
        report.update(status="TECHNICAL_DEPENDENCY_OR_RUNTIME_FAILURE", failure=traceback.format_exc(),
                      objective_calls=0 if algorithm_started is None else None)
    usage = resource.getrusage(resource.RUSAGE_SELF)
    report["resources"] = {"peak_rss_kib": usage.ru_maxrss,
         "cpu_seconds": usage.ru_utime + usage.ru_stime - before_cpu.ru_utime - before_cpu.ru_stime,
         "python_version": platform.python_version(), "platform": platform.platform()}
    write_json(Path(output) / "worker-result.json", report)
    return report


PROBE_SOURCE = '''#include "Configuration.h"
#include "Util.h"
#include <iostream>
#include <limits>
int main(int argc, char* argv[]) {
  Configuration config; config.parse(argc, argv);
  int actual = config.get<int>("eval_limit");
  std::cout << "declared " << config.get<std::string>("eval_limit") << "\\n"
            << "actual_int " << actual << "\\n"
            << "actual_size_t " << static_cast<size_t>(actual) << "\\n"
            << "int_max " << std::numeric_limits<int>::max() << "\\n";
  Random random(63001); std::cout << "rng_initial " << random << "\\n";
}
'''


def captured_process(command, cwd, output, stem, *, timeout, env=None):
    """Keep partial stdout/stderr on timeout and all nonzero exit diagnostics."""
    started = time.monotonic()
    before = resource.getrusage(resource.RUSAGE_CHILDREN)
    status, returncode = "COMPLETED", None
    with (output / f"{stem}.stdout.txt").open("wb") as stdout, (output / f"{stem}.stderr.txt").open("wb") as stderr:
        process = subprocess.Popen(command, cwd=cwd, stdout=stdout, stderr=stderr,
                                   env=env, start_new_session=True)
        try:
            returncode = process.wait(timeout=timeout)
            if returncode:
                status = "PROCESS_FAILED"
        except subprocess.TimeoutExpired:
            status = "PROCESS_TIMEOUT"
            os.killpg(process.pid, signal.SIGKILL)
            returncode = process.wait()
    usage = resource.getrusage(resource.RUSAGE_CHILDREN)
    counts = {}
    for kind in ("stdout", "stderr"):
        path = output / f"{stem}.{kind}.txt"
        with path.open("rb") as stream:
            counts[kind] = {**file_identity(path), "lines": sum(1 for _ in stream)}
    return {"command": [str(part) for part in command], "timeout_seconds": timeout,
            "status": status, "returncode": returncode, "wall_seconds": time.monotonic() - started,
            "child_cpu_seconds": usage.ru_utime + usage.ru_stime - before.ru_utime - before.ru_stime,
            "child_peak_rss_kib_cumulative_observation": usage.ru_maxrss, **counts}


def cpp_probe(author, output):
    source = author / "Goldman-modified/src"
    program = output / "author-P3"
    cpp = sorted(source.glob("*.cpp"))
    require(cpp and (source / "main.cpp") in cpp, "missing original C++ sources")
    report = {"source_files": [{"path": path.relative_to(author).as_posix(), **file_identity(path)} for path in cpp]}
    report["compiler"] = captured_process(["g++", "--version"], output, output, "compiler", timeout=5)
    (output / "configuration-probe.cpp").write_text(PROBE_SOURCE, encoding="utf-8")
    probe = output / "configuration-probe"
    report["probe_build"] = captured_process(["g++", *CPP_FLAGS, "-I", str(source),
           str(source / "Configuration.cpp"), str(output / "configuration-probe.cpp"), "-o", str(probe)],
           output, output, "probe-build", timeout=30)
    if report["probe_build"]["status"] != "COMPLETED":
        return {**report, "status": "TECHNICAL_PROBE_BUILD_FAILURE", "objective_calls": 0}
    report["configuration_conversion_probes"] = []
    for declared in ("100000", "2147483647", "10000000000", "100000000000"):
        capture = captured_process([str(probe), "-eval_limit", declared], output, output,
                                   f"configuration-{declared}", timeout=2)
        lines = (output / f"configuration-{declared}.stdout.txt").read_text().splitlines()
        fields = dict(line.split(" ", 1) for line in lines if " " in line)
        rng = fields.pop("rng_initial", None)
        report["configuration_conversion_probes"].append({"declared": declared, "observed": fields, **capture})
        if rng is not None:
            report["rng_initial"] = {"engine": "std::mt19937", "seed": SEED,
                                     "serialized_state_sha256": sha256_bytes(rng.encode())}
    report["build"] = captured_process(["g++", *CPP_FLAGS, *map(str, cpp), "-o", str(program)],
                                       output, output, "build", timeout=120)
    if report["build"]["status"] != "COMPLETED":
        return {**report, "status": "TECHNICAL_BUILD_FAILURE", "objective_calls": 0}
    # The original driver checks the limit only between complete generations.
    # LambdaLambda caps lambda at n=10, hence at most 20 queries per generation.
    # Starting below 99980 permits at most 99999 calls, including initialization.
    declared_limit = CALL_CAP - 2 * CASES["maxsat-10"]["n"]
    command = [str(program), str(author / "Goldman-modified/config/default.cfg"),
               str(author / "Goldman-modified/config/MAXSAT.0010.LambdaLambda.cfg"),
               "-experiment", "singlerun", "-runs", "1", "-seed", str(SEED),
               "-problem", "MAXSAT", "-length", "10", "-optimizer", "LambdaLambda", "-problem_seed", "100",
               "-eval_limit", str(declared_limit), "-verbosity", "0", "-disable_metadata", "1",
               "-cfg_file", str(output / "actual-configuration.cfg"),
               "-dat_file", str(output / "author-progression.dat")]
    report["execution"] = captured_process(command, output, output, "author", timeout=GA_SECONDS)
    report.update(status="TECHNICAL_PREFIX" if report["execution"]["status"] == "COMPLETED" else
                  "TECHNICAL_TIME_CAP" if report["execution"]["status"] == "PROCESS_TIMEOUT" else "TECHNICAL_RUNTIME_FAILURE",
                  declared_eval_limit=declared_limit, objective_calls=None,
                  objective_calls_upper_bound=CALL_CAP - 1, final_rng_state="NOT_EXPOSED_BY_ORIGINAL_DRIVER",
                  counter_note="Original .dat contains best-found calls, not total calls. The cap is bounded "
                               "using n=10 and at most 2*n calls in each unchanged LambdaLambda generation.")
    try:
        actual = dict(line.split(maxsplit=1) for line in (output / "actual-configuration.cfg").read_text().splitlines())
        expected = {"problem": "MAXSAT", "length": "10", "optimizer": "LambdaLambda", "problem_seed": "100",
                    "seed": str(SEED), "eval_limit": str(declared_limit), "experiment": "singlerun", "runs": "1"}
        require(all(actual.get(key) == value for key, value in expected.items()), "actual C++ configuration differs from profile")
        report["actual_configuration"] = actual
        report["configuration_verified_against_profile"] = True
    except Exception:
        report["status"] = "TECHNICAL_CONFIGURATION_FAILURE"
        report["configuration_failure"] = traceback.format_exc()
    return report


def validate_descriptor(descriptor, identity):
    for field in FROZEN_IDENTITY_FIELDS:
        require(field in descriptor and descriptor[field] == identity[field], f"frozen source identity differs: {field}")
    require(type(descriptor.get("run_id")) is int and descriptor["run_id"] > 0 and
            type(descriptor.get("run_attempt")) is int and descriptor["run_attempt"] > 0,
            "frozen source requires exact run and attempt IDs")
    require(descriptor.get("artifact_name") == f"lambda-paper-audit-{descriptor['run_id']}-{descriptor['run_attempt']}",
            "frozen source artifact has another audit attempt name")
    validate_packet_reference(descriptor.get("source_packet_reference"))


def validate_packet_reference(reference):
    """Bind the portable wrapper to one bounded, manifested source tarball."""
    require(isinstance(reference, dict) and reference.get("path") == "full-source.tar.gz" and
            reference.get("prefix") == "bundle", "unexpected frozen source packet layout")
    require(type(reference.get("bytes")) is int and 0 < reference["bytes"] <= MAX_DOWNLOAD,
            "frozen source packet exceeds download guard")
    for field in ("sha256", "full_file_manifest_sha256"):
        require(re.fullmatch(r"[0-9a-f]{64}", reference.get(field, "")) is not None,
                "frozen source packet lacks an exact digest")
    return reference


def unpack_frozen_packet(packet, descriptor, destination):
    """Unwrap portable artifact bytes without changing any author filename."""
    packet = Path(packet).resolve()
    reference = validate_packet_reference(descriptor.get("source_packet_reference"))
    metadata = read_json(packet / "source_packet_manifest.json")
    require(metadata.get("schema_version") == "ga-lambda-source-packet-v1" and
            metadata.get("source_packet_reference") == reference, "source packet metadata differs from frozen descriptor")
    source_identity = metadata.get("identity", {})
    require(all(source_identity.get(field) == descriptor[field] for field in FROZEN_IDENTITY_FIELDS) and
            source_identity.get("implementation_commit_sha") == descriptor["implementation_commit_sha"] and
            source_identity.get("run_id") == descriptor["run_id"] and
            source_identity.get("run_attempt") == descriptor["run_attempt"], "source packet has mixed source identity")
    for field in ("source_manifest_sha256", "audit_report_sha256"):
        require(metadata.get(field) == descriptor[field], "source packet has mixed report hashes")
    require(metadata.get("full_file_manifest_sha256", reference["full_file_manifest_sha256"]) ==
            reference["full_file_manifest_sha256"], "source packet has mixed full-file manifest hash")
    source = packet / reference["path"]
    require(file_identity(source) == {"bytes": reference["bytes"], "sha256": reference["sha256"]},
            "source tarball hash or length differs")
    destination = Path(destination).resolve()
    extract_snapshot(source.read_bytes(), destination, reference["prefix"])
    require(file_identity(destination / "file_manifest.json")["sha256"] == reference["full_file_manifest_sha256"],
            "full source file manifest differs")
    verify_evidence(destination)
    return destination


def committed_descriptor(identity):
    descriptor_path = MODULE_ROOT / "frozen_sources.json"
    require(descriptor_path.is_file(), "pilot requires a committed frozen_sources.json descriptor")
    committed = subprocess.check_output(["git", "show", f"{identity['implementation_commit_sha']}:"
                         "studies/knapsack_parameters/lambda_study/frozen_sources.json"], cwd=ROOT)
    require(committed == descriptor_path.read_bytes(), "frozen source descriptor must be committed unchanged")
    descriptor = read_json(descriptor_path)
    validate_descriptor(descriptor, identity)
    return descriptor


def frozen_source(destination, identity):
    descriptor = committed_descriptor(identity)
    source_run = api_get(f"https://api.github.com/repos/{REPOSITORY}/actions/runs/{descriptor['run_id']}/attempts/{descriptor['run_attempt']}")
    require(source_run["id"] == descriptor["run_id"] and source_run["run_attempt"] == descriptor["run_attempt"] and
            source_run["head_sha"] == descriptor["implementation_commit_sha"] and source_run["head_branch"] == BRANCH and
            source_run["status"] == "completed" and source_run["event"] == "push" and
            source_run["path"].split("@")[0] == ".github/workflows/knapsack-lambda-study.yml",
            "frozen source run/attempt/SHA/branch/workflow differs")
    metadata = api_get(f"https://api.github.com/repos/{REPOSITORY}/actions/artifacts/{descriptor['artifact_id']}")
    verify_artifact_identity(metadata, artifact_id=descriptor["artifact_id"], source_run_id=descriptor["run_id"],
             source_sha=descriptor["implementation_commit_sha"], zip_sha256=descriptor["zip_sha256"])
    require(metadata["name"] == descriptor["artifact_name"] and metadata["size_in_bytes"] == descriptor["zip_bytes"],
            "frozen source artifact name or size differs")
    destination = Path(destination).resolve()
    packet = extract_evidence(download_zip(metadata), destination)
    bundle = unpack_frozen_packet(packet, descriptor, destination.with_name(destination.name + "-bundle"))
    for filename, field in (("source_manifest.json", "source_manifest_sha256"),
                            ("audit-report.json", "audit_report_sha256")):
        require(file_identity(bundle / filename)["sha256"] == descriptor[field], "frozen source report differs")
    audit = read_json(bundle / "audit-report.json")
    source_identity = audit.get("identity", audit.get("provenance", {}))
    require(all(source_identity.get(field) == descriptor[field] for field in FROZEN_IDENTITY_FIELDS) and
            source_identity.get("implementation_commit_sha") == descriptor["implementation_commit_sha"] and
            source_identity.get("run_id") == descriptor["run_id"] and source_identity.get("run_attempt") == descriptor["run_attempt"],
            "audit source used another protocol, runtime, implementation, run or attempt")
    require(audit.get("availability", {}).get("author_sources_verified") is True,
            "author-source availability is not verified")
    return bundle, descriptor


def run_case(case, expected_sha, output):
    identity = authenticate(expected_sha)
    p = profile(case)
    output = evidence_directory(output)
    report = {"schema_version": "ga-lambda-pilot-v1", "identity": identity,
              "case": case, "profile": p, "profile_sha256": sha256_bytes(canonical_bytes(p)),
              "status": "TECHNICAL_FAILURE", "paper_reproduction": "NOT_RUN",
              "full_gate": "BLOCKED_NOT_AUTHORIZED", "knapsack_execution": "NOT_IMPLEMENTED"}
    started = time.monotonic()
    try:
        bundle, frozen = frozen_source(output.parent / f"lambda-frozen-{case}", identity)
        report["frozen_source"] = frozen
        report["released_workload"] = released_workload(read_json(bundle / "audit-report.json"))
        author = bundle / "source/author"
        if p["language"] == "python":
            worker = output / "worker"
            worker.mkdir()
            environment = os.environ.copy()
            environment["PYTHONPATH"] = str(ROOT)
            environment["PYTHONDONTWRITEBYTECODE"] = "1"
            # Repository imports come from PYTHONPATH; the author's code imports
            # directly from its immutable source while cwd is isolated scratch.
            report["execution"] = captured_process([sys.executable, "-m", MODULE_NAME, "worker",
                    "--case", case, "--expected-sha", expected_sha, "--author", str(author),
                    "--output", str(worker)], worker, output, "author", timeout=GA_SECONDS + 15, env=environment)
            if (worker / "worker-result.json").exists():
                report["probe"] = read_json(worker / "worker-result.json")
                require(report["probe"]["seed"] == SEED and report["probe"]["profile_sha256"] ==
                        report["profile_sha256"], "worker seed or profile differs")
                report["status"] = report["probe"]["status"]
            else:
                report["status"] = "TECHNICAL_PROCESS_TIMEOUT_OR_FAILURE"
        else:
            report["probe"] = cpp_probe(author, output)
            report["status"] = report["probe"]["status"]
        verify_evidence(bundle)
        report["author_source_unchanged_after_pilot"] = True
    except Exception:
        report["status"] = "TECHNICAL_FAILURE"
        report["failure"] = traceback.format_exc()
    report["wall_seconds_including_transport_build"] = time.monotonic() - started
    report["child_peak_rss_kib_observed"] = resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss
    write_json(output / "pilot-result.json", report)
    write_file_manifest(output)
    return report


def record_tests(expected_sha, output, outcome):
    identity = authenticate(expected_sha)
    output = Path(output).resolve()
    require(not output.is_relative_to(ROOT), "fixture evidence must be outside checkout")
    output.mkdir(parents=True, exist_ok=True)
    write_json(output / "tests-result.json", {"schema_version": "ga-lambda-tests-v1", "identity": identity,
               "fixture_outcome": outcome, "paper_reproduction": "NOT_RUN", "full_gate": "BLOCKED_NOT_AUTHORIZED"})
    write_file_manifest(output)


def collect_artifacts(identity):
    artifacts = []
    page = 1
    while True:
        result = api_get(f"https://api.github.com/repos/{REPOSITORY}/actions/runs/{identity['run_id']}/artifacts?per_page=100&page={page}")
        artifacts.extend(result["artifacts"])
        if len(result["artifacts"]) < 100:
            return artifacts
        page += 1


def technical_projection(case_reports, released_workload=None):
    observations = []
    for report in case_reports:
        probe = report.get("probe", {})
        calls, seconds = probe.get("objective_calls"), probe.get("ga_wall_seconds")
        rate = calls / seconds if isinstance(calls, int) and calls > 0 and seconds and seconds > 0 else None
        reported_calls = (released_workload or {}).get("python_reported_evaluations_total")
        normalization = reported_calls / rate / 60 if rate and reported_calls is not None else None
        observations.append({"case": report["case"], "observed_calls": calls, "observed_ga_seconds": seconds,
                             "observed_calls_per_second": rate, "status": report["status"],
                             "released_python_reported_calls_at_this_tiny_case_rate_minutes": normalization,
                             "normalization_is_full_reproduction_estimate": False})
    return {"classification": "ROUGH_TECHNICAL_OBSERVATIONS_ONLY", "observations": observations,
            "released_workload": released_workload, "full_reproduction_runner_minutes": None,
            "long_profiles": "UNKNOWN: tiny bounded prefixes cannot establish long-profile throughput",
            "projection_rule": "Count verified released runs and objective calls, then divide each compatible "
                               "profile by its own measured throughput. Missing exact counts or throughput stay unknown.",
            "full_reproduction_authorized": False, "quality_comparisons": "FORBIDDEN"}


def released_workload(audit):
    catalog = audit.get("results_catalog", {})
    python_logs, cpp_batches = catalog.get("python_logs", []), catalog.get("cpp_batches", [])
    counters = [sum(row["reported_evaluations_by_run"]) if "reported_evaluations_by_run" in row else
                sum(run["evaluations"] for run in row["runs"]) if "runs" in row else None for row in python_logs]
    counter_total = sum(counters) if "python_logs" in catalog and all(value is not None for value in counters) else None
    return {"python_log_count": len(python_logs), "python_retained_runs": sum(row["retained_runs"] for row in python_logs),
            "python_reported_evaluations_total": counter_total,
            "cpp_batch_count": len(cpp_batches), "cpp_retained_runs": sum(row["retained_rows"] for row in cpp_batches),
            "cpp_analyzed_runs": sum(row["analysis_rows"] for row in cpp_batches),
            "cpp_discarded_runs_still_required_for_batch_rng": sum(row["discarded_rows"] for row in cpp_batches),
            "cpp_censored_analyzed_runs": sum(row["censored_rows"] for row in cpp_batches),
            "catalog_errors": catalog.get("errors", []),
            "count_note": "Retained released profiles include source counters and best-found/censored observations; "
                          "they are not an exact total of executed objective queries or the complete paper workload."}


def completed_job_minutes(jobs):
    total = 0
    unfinished = []
    for job in jobs:
        if job.get("conclusion") == "skipped":
            continue
        if not job.get("started_at") or not job.get("completed_at"):
            unfinished.append({"job_id": job.get("id"), "name": job.get("name"), "status": job.get("status")})
            continue
        started = datetime.fromisoformat(job["started_at"].replace("Z", "+00:00"))
        completed = datetime.fromisoformat(job["completed_at"].replace("Z", "+00:00"))
        total += max(1, math.ceil(max(0, (completed - started).total_seconds()) / 60))
    return total, unfinished


def current_attempt_jobs(identity):
    jobs, page = [], 1
    while True:
        payload = api_get(f"https://api.github.com/repos/{REPOSITORY}/actions/runs/{identity['run_id']}/"
                          f"attempts/{identity['run_attempt']}/jobs?per_page=100&page={page}")
        jobs.extend(payload["jobs"])
        if len(payload["jobs"]) < 100:
            return {"run_id": identity["run_id"], "run_attempt": identity["run_attempt"], "jobs": jobs}
        page += 1


def technical_failures(case_reports, fixture_outcome=None):
    failures = [f"{item['case']}: {item['status']}" for item in case_reports if item["status"] not in VALID_TECHNICAL_STATUSES]
    if fixture_outcome is not None and fixture_outcome != "success":
        failures.append(f"CI fixtures did not succeed: {fixture_outcome}")
    return failures


def aggregate(phase, expected_sha, output):
    identity = authenticate(expected_sha)
    require(phase in ("audit", "tests", "pilot"), "full reproduction and knapsack phases are unavailable")
    output = evidence_directory(output)
    report = {"schema_version": "ga-lambda-report-v1", "identity": identity, "phase": phase,
              "source_status": "UNKNOWN", "completion": "INCOMPLETE", "paper_reproduction": "NOT_RUN",
              "full_gate": "BLOCKED_NOT_AUTHORIZED", "knapsack_gate": "BLOCKED_NOT_AUTHORIZED",
              "quality_analysis": "NOT_PERFORMED", "sources": [], "failures": []}
    case_reports = []
    expected_source_count = None
    try:
        artifacts = collect_artifacts(identity)
        write_json(output / "artifact-api-metadata.json", artifacts)
        stems = ([f"lambda-paper-pilot-{case}" for case in CASES] if phase == "pilot" else
                 ["lambda-paper-audit-compact" if phase == "audit" else "lambda-paper-tests"])
        if phase == "pilot":
            stems.insert(0, "lambda-paper-tests")
        stems.insert(0, "lambda-paper-budget")
        expected_source_count = len(stems)
        for stem in stems:
            name = f"{stem}-{identity['run_id']}-{identity['run_attempt']}"
            matches = [row for row in artifacts if row["name"] == name]
            if len(matches) != 1:
                report["failures"].append(f"Missing or duplicate exact-attempt artifact: {name}")
                continue
            metadata = matches[0]
            try:
                verify_artifact_identity(metadata, artifact_id=metadata["id"], source_run_id=identity["run_id"], source_sha=expected_sha)
                directory = extract_evidence(download_zip(metadata), output / "jobs" / stem)
                report["sources"].append({"artifact_id": metadata["id"], "artifact_name": name,
                         "run_id": identity["run_id"], "run_attempt": identity["run_attempt"],
                         "zip_sha256": metadata["digest"][7:], "zip_bytes": metadata["size_in_bytes"]})
                if stem.startswith("lambda-paper-pilot-"):
                    item = read_json(directory / "pilot-result.json")
                    require(item["identity"] == identity and item["case"] == stem.removeprefix("lambda-paper-pilot-"),
                            "pilot artifact has mixed run, case or implementation")
                    require(item["full_gate"] == "BLOCKED_NOT_AUTHORIZED" and
                            item["profile"] == profile(item["case"]) and
                            item["profile_sha256"] == sha256_bytes(canonical_bytes(item["profile"])),
                            "pilot changed registered technical profile or full gate")
                    case_reports.append(item)
                elif stem == "lambda-paper-budget":
                    report["budget_preflight"] = read_json(directory / "budget-preflight.json")
                elif stem == "lambda-paper-audit-compact":
                    audit = read_json(directory / "audit-report.json")
                    require(audit.get("identity", audit.get("provenance")) == identity, "audit has mixed run identity")
                    report["source_status"] = audit.get("availability", {})
                    report["released_workload"] = released_workload(audit)
                    full_name = f"lambda-paper-audit-{identity['run_id']}-{identity['run_attempt']}"
                    full_matches = [row for row in artifacts if row["name"] == full_name]
                    require(len(full_matches) == 1, "full source snapshot metadata is missing or duplicated")
                    full = full_matches[0]
                    verify_artifact_identity(full, artifact_id=full["id"], source_run_id=identity["run_id"], source_sha=expected_sha)
                    require(re.fullmatch(r"sha256:[0-9a-f]{64}", full.get("digest", "")) is not None,
                            "full source snapshot has no ZIP digest")
                    report["full_source_artifact"] = {**{field: identity[field] for field in FROZEN_IDENTITY_FIELDS},
                              "artifact_id": full["id"], "artifact_name": full_name,
                              "run_id": identity["run_id"], "run_attempt": identity["run_attempt"],
                              "implementation_commit_sha": expected_sha, "zip_sha256": full["digest"][7:],
                              "zip_bytes": full["size_in_bytes"], "bytes_not_downloaded_by_aggregate": True,
                              "audit_report_sha256": audit["full_evidence_reference"]["sha256"],
                              "source_manifest_sha256": file_identity(directory / "source_manifest.json")["sha256"],
                              "source_packet_reference": validate_packet_reference(audit.get("source_packet_reference"))}
                else:
                    fixtures = read_json(directory / "tests-result.json")
                    require(fixtures["identity"] == identity, "fixture artifact has mixed identity")
                    report["fixture_outcome"] = fixtures["fixture_outcome"]
            except Exception:
                report["failures"].append(traceback.format_exc())
        report["failures"].extend(technical_failures(case_reports, report.get("fixture_outcome")))
        if phase == "pilot" and len(case_reports) != len(CASES):
            report["failures"].append("Three authenticated technical case reports are required")
        if phase in ("tests", "pilot") and "fixture_outcome" not in report:
            report["failures"].append("Authenticated fixture outcome is missing")
        report["pilot_cases"] = [{"case": item["case"], "status": item["status"]} for item in case_reports]
        workload = case_reports[0].get("released_workload") if case_reports else report.get("released_workload")
        report["resources"] = technical_projection(case_reports, workload)
        if phase == "pilot" and len(case_reports) == len(CASES) and all(item.get("author_source_unchanged_after_pilot") is True for item in case_reports):
            report["source_status"] = "FROZEN_SOURCE_VERIFIED_PER_CASE"
        jobs = current_attempt_jobs(identity)
        write_json(output / "jobs-api-metadata.json", jobs)
        current_used, unfinished = completed_job_minutes(jobs["jobs"])
        report["budget"] = {"authorized_cumulative_runner_minutes": 60,
                            "new_workflow_ceiling_minutes": {"phase": 1, "audit": 12, "tests": 10,
                                                            "pilot_jobs": 18, "aggregate": 5},
                            "new_workflow_worst_case_minutes": 46,
                            "two_existing_selector_jobs_ceiling_minutes": 10,
                            "combined_single_run_worst_case_minutes": 56,
                            "previous_rounded_runner_minutes": report.get("budget_preflight", {}).get("previous_rounded_runner_minutes"),
                            "current_completed_rounded_runner_minutes": current_used,
                            "unfinished_jobs": unfinished,
                            "current_aggregate_job_still_running": True,
                            "final_cumulative_usage": "Must be finalized from completed API jobs; current report excludes its own unfinished duration."}
    except Exception:
        report["failures"].append(traceback.format_exc())
    report["completion"] = "COMPLETE_TECHNICAL_EVIDENCE" if expected_source_count is not None and \
        len(report["sources"]) == expected_source_count and not report["failures"] else "INCOMPLETE"
    write_json(output / "technical-report.json", report)
    write_file_manifest(output)
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=("run", "worker", "aggregate", "record-tests"))
    parser.add_argument("--expected-sha", required=True)
    parser.add_argument("--case", choices=tuple(CASES))
    parser.add_argument("--phase", choices=("audit", "tests", "pilot"))
    parser.add_argument("--author", type=Path)
    parser.add_argument("--outcome", choices=("success", "failure", "cancelled", "skipped"))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.operation == "run":
        require(args.case is not None, "bounded case required")
        result = run_case(args.case, args.expected_sha, args.output)
        print(f"{args.case}: {result['status']}; paper reproduction NOT_RUN; full gate BLOCKED")
        require(result["status"] in VALID_TECHNICAL_STATUSES, "technical pilot failed; archived evidence is retained")
    elif args.operation == "worker":
        identity = authenticate(args.expected_sha)
        require(args.case in CASES and args.author is not None, "worker requires original source and case")
        require(not args.output.resolve().is_relative_to(ROOT), "worker evidence outside checkout required")
        result = python_worker(args.case, args.author, args.output, identity)
        require(result["status"] in VALID_TECHNICAL_STATUSES, "author probe failed; worker evidence is retained")
    elif args.operation == "record-tests":
        require(args.outcome is not None, "fixture outcome required")
        record_tests(args.expected_sha, args.output, args.outcome)
    else:
        require(args.phase is not None, "only bounded phase may be aggregated")
        result = aggregate(args.phase, args.expected_sha, args.output)
        print(f"{result['completion']}; paper reproduction NOT_RUN; full gate BLOCKED")
        require(result["completion"] == "COMPLETE_TECHNICAL_EVIDENCE", "technical report incomplete or failed; archived evidence is retained")


if __name__ == "__main__":
    main()
