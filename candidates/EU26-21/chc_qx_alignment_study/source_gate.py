"""CI-only source-controller equivalence and separate real-source smoke gates.

Fixture comparisons execute the real pinned Evolution.CHC and CHCqx without
training. Recorded synthetic clock tapes make the timing-based instance stage
auditable; they are not measurements of research performance. Real smoke must
run separately in Python 3.9 with hybrid_1/requirements.txt, never NumPy 2.x.
"""
from __future__ import annotations

import argparse
from contextlib import redirect_stdout
import copy
import hashlib
import importlib
from importlib.metadata import version as package_version
import io
import json
import os
from pathlib import Path
import platform
import random
import subprocess
import sys
from types import SimpleNamespace
from typing import Any

import numpy as np

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from chc_qx_alignment_study.reference import source_compatible_qx


THIS_DIRECTORY = Path(__file__).resolve().parent
REPOSITORY_ROOT = THIS_DIRECTORY.parents[2]
REGISTRATION_SHA = "b5c46e603838c5fbc7e35b121f757421c222046f"
PROTOCOL_SHA256 = "c51cbad33d2012b504312e70ff180f7f35cc58ffbd079882acf596b17710de40"
PROTOCOL_ID = "EU26-21-CHCQX-SOURCE-WBA-DIAG-V1"
UPSTREAM_SHA = "6ac5a7ec77f8a7c096ab4d019254fcc897988fd6"
EVOLUTION_BLOB = "05b0d8afc02faee688e5d1ff8e24531ae41307c7"


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def _digest_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _digest(value: Any) -> str:
    return _digest_bytes(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                    allow_nan=False).encode("utf-8"))


def _write(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False)
                    + "\n", encoding="utf-8")


def _git(root: Path, *arguments: str) -> str:
    return subprocess.check_output(["git", "-C", str(root), *arguments], text=True,
                                   stderr=subprocess.STDOUT).strip()


def authenticate(upstream: Path, expected_sha: str) -> dict[str, Any]:
    """Authenticate before importing the source or writing gate outputs."""
    _require(os.environ.get("GITHUB_ACTIONS") == "true", "source gate is CI-only")
    _require(len(expected_sha) == 40 and all(c in "0123456789abcdef" for c in expected_sha),
             "invalid implementation SHA")
    _require(_git(REPOSITORY_ROOT, "rev-parse", "HEAD") == expected_sha,
             "source-gate implementation SHA mismatch")
    _require(_git(REPOSITORY_ROOT, "status", "--porcelain=v1", "--untracked-files=all") == "",
             "source-gate checkout must be clean")
    subprocess.check_call(["git", "-C", str(REPOSITORY_ROOT), "merge-base", "--is-ancestor",
                           REGISTRATION_SHA, expected_sha])
    _require(os.environ.get("STUDY_WORKFLOW_SHA") == expected_sha,
             "source-gate workflow SHA mismatch")
    for name in ("GITHUB_RUN_ID", "GITHUB_RUN_ATTEMPT"):
        _require(os.environ.get(name, "").isdigit() and int(os.environ[name]) > 0,
                 "source-gate workflow identity missing")
    protocol_file = THIS_DIRECTORY / "protocol.json"
    _require(_digest_bytes(protocol_file.read_bytes()) == PROTOCOL_SHA256,
             "source-gate protocol byte digest changed")
    protocol = json.loads(protocol_file.read_text(encoding="utf-8"))
    _require(protocol["protocol_id"] == PROTOCOL_ID, "source-gate protocol ID changed")
    _require(_git(upstream, "rev-parse", "HEAD") == UPSTREAM_SHA,
             "pinned source revision mismatch")
    for relative, blob in protocol["source"]["blobs"].items():
        _require(_git(upstream, "rev-parse", f"HEAD:{relative}") == blob,
                 f"pinned source blob mismatch: {relative}")
        _require(_git(upstream, "hash-object", str(upstream / relative)) == blob,
                 f"pinned source working bytes mismatch: {relative}")
    return {
        "protocol_id": PROTOCOL_ID, "protocol_sha256": PROTOCOL_SHA256,
        "registration_sha": REGISTRATION_SHA, "implementation_sha": expected_sha,
        "workflow_sha": os.environ["STUDY_WORKFLOW_SHA"],
        "run_id": int(os.environ["GITHUB_RUN_ID"]),
        "run_attempt": int(os.environ["GITHUB_RUN_ATTEMPT"]),
        "upstream_sha": UPSTREAM_SHA,
        "evolution_blob": EVOLUTION_BLOB,
    }


def load_evolution(upstream: Path) -> Any:
    """Reject stale imports; inspect the pinned blob before importing Evolution."""
    root = upstream.resolve()
    _require(_git(root, "rev-parse", "HEAD") == UPSTREAM_SHA, "upstream revision mismatch")
    source = root / "code" / "Evolution.py"
    _require(_git(root, "hash-object", str(source)) == EVOLUTION_BLOB,
             "Evolution working-file blob mismatch")
    existing = sys.modules.get("Evolution")
    if existing is not None:
        _require(Path(existing.__file__).resolve() == source.resolve(),
                 "another Evolution module is already imported")
        return existing
    sys.path.insert(0, str(root / "code"))
    return importlib.import_module("Evolution")


class ClockTape:
    """Record deterministic fixture costs, then replay every timestamp exactly."""

    def __init__(self, tape: list[float] | None = None) -> None:
        self.tape = [] if tape is None else list(tape)
        self.replaying = tape is not None
        self.cursor = 0
        self.current = 100.0

    def advance_fixture_cost(self, value: float) -> None:
        self.current += value

    def time(self) -> float:
        if self.replaying:
            _require(self.cursor < len(self.tape), "clock replay exhausted")
            value = self.tape[self.cursor]
            self.current = value
        else:
            self.current += 0.001
            value = self.current
            self.tape.append(value)
        self.cursor += 1
        return value

    def complete(self) -> None:
        _require(self.cursor == len(self.tape), "clock replay did not consume the complete tape")


class FixtureRecorder:
    def __init__(self, clock: ClockTape, constant: bool = False) -> None:
        self.clock, self.constant = clock, constant
        self.phase = "instance_selection"
        self.evaluations: list[dict[str, Any]] = []
        self.predictions: list[dict[str, Any]] = []
        self.chunks: list[dict[str, Any]] = []
        self.selected_rows: list[int] | None = None
        self.terminal: dict[str, Any] | None = None


class FakeDataset:
    """Source-shaped deterministic fixture; no tree, Census records, or test data.

    Copying preserves the observer only, not mutable features/row identifiers.
    Clock advances represent manufactured fixture costs, never runtime evidence.
    """

    def __init__(self, recorder: FixtureRecorder, rows: int = 48000, dimension: int = 12) -> None:
        self.recorder = recorder
        self.X_train = SimpleNamespace(shape=(rows, dimension))
        self.features = list(range(dimension))
        self.instances = list(range(rows))
        self.clf = SimpleNamespace(fixture_only=True)
        self._score = 0.0

    def __deepcopy__(self, memo: dict[int, Any]) -> Any:
        result = copy.copy(self)
        result.features = list(self.features)
        result.instances = list(self.instances)
        memo[id(self)] = result
        return result

    def divide_dataset(self, classifier: Any, *, normalize: bool, shuffle: bool,
                       all_features: bool, all_instances: bool, evaluate: bool,
                       partial_sample: Any) -> None:
        _require(normalize and not shuffle and all_instances,
                 "fixture received unexpected source preprocessing options")
        self.clf = copy.copy(classifier)
        dimension = self.X_train.shape[1]
        if all_features:
            self.features = list(range(dimension))
        else:
            mask = np.zeros(dimension, dtype=int)
            while int(np.sum(mask)) == 0:
                zero_p = random.uniform(0, 1)
                mask = np.random.choice([0, 1], size=dimension, p=[zero_p, 1-zero_p])
            self.features = list(map(int, np.flatnonzero(mask)))
        self.instances = list(range(self.X_train.shape[0]))
        if partial_sample:
            self.instances = list(map(int, np.random.choice(
                self.X_train.shape[0], int(partial_sample), replace=False,
            )))
        if evaluate:
            self.fit_classifier()
            self.set_validation_accuracy()
            self.set_test_accuracy()

    def set_features(self, values: Any) -> None:
        self.features = list(map(int, values))

    def set_instances(self, values: Any) -> None:
        self.instances = list(map(int, values))

    def fit_classifier(self) -> None:
        dimension = self.X_train.shape[1]
        fraction = sum(index + 1 for index in self.features) / (dimension*(dimension+1)/2)
        self._score = (0.5 if self.recorder.constant else
                       0.5 + 0.4*fraction - 0.05*(1-len(self.instances)/self.X_train.shape[0]))
        self.recorder.clock.advance_fixture_cost(
            0.001*len(self.instances)/self.X_train.shape[0] * (1+len(self.features))
        )

    def _prediction(self, target: str) -> None:
        self.recorder.predictions.append({
            "phase": self.recorder.phase, "target": target,
            "features": list(self.features), "rows": len(self.instances),
        })
        self.recorder.clock.advance_fixture_cost(0.0002)

    def set_validation_accuracy(self) -> None:
        self._prediction("validation")
        self.ValidationAccuracy = self._score

    def set_test_accuracy(self) -> None:
        self._prediction("source_fixture_test_call")
        self.TestAccuracy = self._score

    def get_validation_accuracy(self) -> float:
        return self.ValidationAccuracy

    def get_test_accuracy(self) -> float:
        return self.TestAccuracy


def _population(population: Any) -> list[dict[str, Any]]:
    return [{"mask": list(map(int, individual)),
             "approximate_fitness": list(map(float, individual.fitness.values))
             if individual.fitness.valid else None} for individual in population]


def _outer(frame: Any) -> dict[str, Any]:
    values = frame.f_locals
    return {"best": float(values["best"]), "no_change": int(values["no_change"]),
            "generation": int(values["generation"]),
            "full_archive": [list(map(int, mask)) for mask in values["evaluated_population"]]}


def run_fixture(module: Any, *, wrapped: bool, seed: int = 1,
                tape: list[float] | None = None, constant: bool = False) -> dict[str, Any]:
    """Run a fixture, restoring source methods, tracing and global RNG afterwards."""
    clock = ClockTape(tape)
    recorder = FixtureRecorder(clock, constant)
    evolution = module.Evolution
    old_methods = {name: getattr(evolution, name)
                   for name in ("CHC", "evaluate", "select_instances")}
    old_time, old_trace = module.time, sys.gettrace()
    old_python, old_numpy = random.getstate(), np.random.get_state()
    target = source_compatible_qx if wrapped else evolution.CHCqx

    def capture_select(*arguments: Any, **keywords: Any) -> Any:
        selected, models = old_methods["select_instances"](*arguments, **keywords)
        recorder.selected_rows = list(map(int, selected))
        recorder.phase = "full_controller"
        return selected, models

    def capture_chc(dataset: Any, toolbox: Any, d: Any, population: Any,
                    *arguments: Any, **keywords: Any) -> Any:
        caller = sys._getframe(1)
        snapshot = {"index": len(recorder.chunks)+1, "outer_before": _outer(caller),
                    "distance_before": int(d), "population_before": _population(population),
                    "native_generation_limit": int(keywords["max_generations"]),
                    "evaluation_offset": len(recorder.evaluations)}
        recorder.phase = "approximate_search"
        log, result, distance = old_methods["CHC"](
            dataset, toolbox, d, population, *arguments, **keywords
        )
        recorder.phase = "full_controller"
        snapshot.update({"distance_after": int(distance), "population_after": _population(result),
                         "evaluation_end": len(recorder.evaluations)})
        recorder.chunks.append(snapshot)
        return log, result, distance

    def capture_evaluate(individual: Any, task: Any, target_dataset: Any,
                         baseline_individual: Any) -> Any:
        result = old_methods["evaluate"](individual, task, target_dataset, baseline_individual)
        recorder.evaluations.append({
            "phase": recorder.phase, "mask": list(map(int, individual)),
            "rows": len(baseline_individual.instances), "target": target_dataset,
            "score": float(result[0]),
        })
        return result

    def trace(frame: Any, event: str, value: Any) -> Any:
        if frame.f_code is target.__code__ and event == "return" and "evaluated_population" in frame.f_locals:
            recorder.terminal = _outer(frame)
        return trace

    error = None
    rows: list[dict[str, Any]] = []
    controls: list[list[int]] = []
    rng_end: dict[str, Any] = {}
    try:
        module.time = SimpleNamespace(time=clock.time)
        for name, method in (("CHC", capture_chc), ("evaluate", capture_evaluate),
                             ("select_instances", capture_select)):
            setattr(evolution, name, staticmethod(method))
        random.seed(seed)
        np.random.seed(seed)
        sys.settrace(trace)
        baseline = FakeDataset(recorder)
        with redirect_stdout(io.StringIO()):
            if wrapped:
                log, models = source_compatible_qx(
                    evolution, baseline, population_size=8, clock=clock.time,
                )
            else:
                log, models = evolution.CHCqx(baseline, 10, 10, 2, population_size=8, verbose=0)
        rows = [{"mask": list(map(int, row["ind"])), "time": float(row["time"]),
                 "fitness": float(row["fitness"])} for _, row in log.iterrows()]
        controls = [list(map(int, model.features)) for model in models]
    except Exception as exception:
        error = {"type": type(exception).__name__, "message": str(exception)}
    finally:
        numpy_state = np.random.get_state()
        rng_end = {"python": random.getstate(), "numpy": [
            numpy_state[0], list(map(int, numpy_state[1])), int(numpy_state[2]),
            int(numpy_state[3]), float(numpy_state[4]),
        ]}
        sys.settrace(old_trace)
        module.time = old_time
        for name, method in old_methods.items():
            setattr(evolution, name, staticmethod(method))
        random.setstate(old_python)
        np.random.set_state(old_numpy)
    clock.complete()
    return {"seed": seed, "error": error, "clock_tape": clock.tape,
            "selected_rows": recorder.selected_rows, "controls": controls,
            "predictions": recorder.predictions, "evaluations": recorder.evaluations,
            "chunks": recorder.chunks, "terminal": recorder.terminal, "improvement_log": rows,
            "rng_end_sha256": _digest(rng_end)}


def fixture_gate(upstream: Path) -> dict[str, Any]:
    module = load_evolution(upstream)
    cases = []
    for seed, constant in ((1, False), (2, False), (1, True)):
        reference = run_fixture(module, wrapped=False, seed=seed, constant=constant)
        actual = run_fixture(module, wrapped=True, seed=seed, constant=constant,
                             tape=reference["clock_tape"])
        _require(actual == reference, f"source-controller fixture mismatch: seed={seed}, constant={constant}")
        if constant:
            _require(reference["error"] is not None
                     and reference["error"]["type"] == "UnboundLocalError",
                     "degenerate Spearman source failure was not retained")
        else:
            _require(reference["error"] is None and bool(reference["chunks"]),
                     "nondegenerate source fixture did not complete")
            _require(reference["terminal"]["no_change"] == 2,
                     "source fixture did not naturally stop")
        cases.append({"seed": seed, "constant_control_scores": constant,
                      "trace_sha256": _digest(reference),
                      "native_chunks": len(reference["chunks"]),
                      "evaluation_calls": len(reference["evaluations"]),
                      "clock_reads": len(reference["clock_tape"]),
                      "selected_rows": len(reference["selected_rows"] or []),
                      "error": reference["error"]})
    return {"schema": "eu26-21-chc-qx-source-fixture-gate-v1",
            "status": "PASS_SOURCE_CONTROLLER_EQUIVALENCE", "cases": cases,
            "fixture_scope": "synthetic_evaluator_real_pinned_native_CHC_no_classifier_training",
            "source_and_wrapper_compared": ["masks_and_evaluation_scopes", "selected_row_ids",
                "controlled_masks", "population_and_distance_per_native_chunk", "persistent_full_archive",
                "no_change_and_stop", "approximate_fitness_unchanged_by_full_checkpoint",
                "clock_read_tape", "final_rng_states", "degenerate_source_failure"],
            "classifier_training": False, "historical_numeric_reproduction": False}


def source_smoke(upstream: Path, output: Path) -> dict[str, Any]:
    _require(sys.version_info[:2] == (3, 9), "real source smoke requires Python 3.9 frozen environment")
    requirements = REPOSITORY_ROOT / "candidates" / "EU26-21" / "hybrid_1" / "requirements.txt"
    frozen_requirements = subprocess.check_output([
        "git", "-C", str(REPOSITORY_ROOT), "show",
        "05b2514d0a17bb8165f7d0388a96e9771e339284:candidates/EU26-21/hybrid_1/requirements.txt",
    ])
    _require(requirements.read_bytes() == frozen_requirements, "source-smoke requirements changed")
    packages = {}
    for raw in requirements.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if line and not line.startswith("#"):
            name, expected_version = line.split("==")
            actual_version = package_version(name)
            _require(actual_version == expected_version, f"source-smoke package pin mismatch: {name}")
            packages[name] = actual_version
    environment = {"python_implementation": platform.python_implementation(),
                   "python_version": platform.python_version(), "packages": packages,
                   "requirements_sha256": _digest_bytes(frozen_requirements)}
    _require(environment["python_implementation"] == "CPython", "source-smoke Python implementation differs")
    script = REPOSITORY_ROOT / "candidates" / "EU26-21" / "old" / "run_source_census.py"
    result_file = output / "source-integration-seed1.json"
    subprocess.check_call([sys.executable, str(script), str(upstream), "--seed", "1",
                           "--output-json", str(result_file), "--log-file",
                           str(output / "source-integration-seed1.log")])
    result = json.loads(result_file.read_text(encoding="utf-8"))
    _require(result["seed"] == 1 and result["upstream_commit"] == UPSTREAM_SHA,
             "real-source smoke identity differs")
    return {"schema": "eu26-21-chc-qx-source-integration-gate-v1",
            "status": "PASS_SOURCE_INTEGRATION_SMOKE", "seed": 1,
            "classifier_training": True,
            "environment": environment, "environment_sha256": _digest(environment),
            "result_sha256": _digest_bytes(result_file.read_bytes()),
            "historical_numeric_gate_changed": False, "table2_reproduction": False,
            "source_profile_known_limitations_retained": True,
            "exact_historical_sample_size_or_mask_required": False}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--upstream", type=Path, required=True)
    parser.add_argument("--expected-sha", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--phase", choices=("fixture", "real-smoke"), default="fixture")
    args = parser.parse_args()
    provenance = authenticate(args.upstream.resolve(), args.expected_sha)
    _require(not args.output.is_symlink(), "source-gate output may not be a symlink")
    _require(not args.output.exists() or (args.output.is_dir() and not any(args.output.iterdir())),
             "source-gate output must be empty")
    args.output.mkdir(parents=True, exist_ok=True)
    subprocess.check_call([sys.executable, str(REPOSITORY_ROOT / "candidates" / "EU26-21"
                                              / "old" / "source_audit.py"), str(args.upstream.resolve())])
    try:
        report = (fixture_gate(args.upstream.resolve()) if args.phase == "fixture"
                  else source_smoke(args.upstream.resolve(), args.output))
        report["provenance"] = provenance
        filename = "source-gate-fixture.json" if args.phase == "fixture" else "source-gate-smoke.json"
        _write(args.output / filename, report)
    except Exception as exception:
        _write(args.output / "source-gate-failure.json", {
            "schema": "eu26-21-chc-qx-source-gate-failure-v1", "phase": args.phase,
            "status": "FAIL_SOURCE_GATE", "provenance": provenance,
            "error_type": type(exception).__name__, "error": str(exception),
        })
        raise
    print(report["status"])


if __name__ == "__main__":
    main()
