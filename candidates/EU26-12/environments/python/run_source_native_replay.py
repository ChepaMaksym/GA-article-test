#!/usr/bin/env python3
"""Optional modern-environment source-native replay of the frozen first run."""

from __future__ import annotations

import argparse
import importlib.metadata
import io
import platform
import sys
import tempfile
import time
import zipfile
from pathlib import Path


PYTHON_ENV = Path(__file__).resolve().parent
sys.path.insert(0, str(PYTHON_ENV))

from eu2612.canonical import bind_report, write_new_json  # noqa: E402
from eu2612.code import validate_code_archive  # noqa: E402
from eu2612.contract import load_contract  # noqa: E402
from eu2612.http_range import fetch_small_https  # noqa: E402


class TrackingProblem:
    """Forward IOH calls while retaining the evaluation of every new strict best."""

    def __init__(self, problem: object) -> None:
        self.problem = problem
        self.meta_data = problem.meta_data
        self.best_evaluation: int | None = None
        self.best_y = float("inf")

    @property
    def state(self):
        return self.problem.state

    def __call__(self, x):
        value = self.problem(x)
        best = float(self.problem.state.current_best_internal.y)
        if best < self.best_y:
            self.best_y = best
            self.best_evaluation = int(self.problem.state.evaluations)
        return value


def _versions() -> dict[str, str]:
    result = {"python": platform.python_version(), "platform": platform.platform()}
    for name in ("numpy", "scipy", "ioh", "numba"):
        try:
            result[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            result[name] = "MISSING"
    return result


def _write_source_tree(archive_payload: bytes, destination: Path) -> None:
    archive = zipfile.ZipFile(io.BytesIO(archive_payload), "r")
    for info in archive.infolist():
        if not info.filename.startswith("modde/") or info.is_dir() or not info.filename.endswith(".py"):
            continue
        relative = Path(*info.filename.split("/"))
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(archive.read(info))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--code-archive", type=Path)
    args = parser.parse_args()
    if args.output.exists() or args.output.is_symlink():
        parser.error("--output must be a new path")
    contract = load_contract()
    if args.code_archive is None:
        payload = fetch_small_https(
            contract["zenodo_files"]["ModDE.zip"]["url"], maximum_bytes=100_000
        )
    else:
        payload = args.code_archive.read_bytes()
    code = validate_code_archive(payload, contract)
    versions = _versions()
    missing = [name for name in ("numpy", "scipy", "ioh", "numba") if versions[name] == "MISSING"]
    status: str
    observed: dict[str, object] = {}
    runtime = 0.0
    if missing:
        status = "SOURCE_NATIVE_BLOCKED_MISSING_DEPENDENCIES"
        observed = {"missing": missing}
    else:
        started = time.perf_counter()
        try:
            with tempfile.TemporaryDirectory(prefix="eu2612-source-") as temporary:
                root = Path(temporary)
                _write_source_tree(payload, root)
                sys.path.insert(0, str(root))
                try:
                    import ioh
                    import numpy as np
                    from modde import ModularDE

                    np.random.seed(0)
                    native = ioh.get_problem(1, dimension=20, instance=0)
                    tracked = TrackingProblem(native)
                    parameters = {
                        "mutation_base": "target",
                        "mutation_reference": "pbest",
                        "lpsr": True,
                        "lambda_": 360,
                        "use_archive": True,
                        "adaptation_method_F": "shade",
                        "adaptation_method_CR": "shade",
                        "budget": 50000,
                    }
                    ModularDE(tracked, **parameters).run()
                    observed = {
                        "logged_evaluations": int(native.state.evaluations),
                        "best_evaluation": tracked.best_evaluation,
                        "best_y_decimal": repr(float(native.state.current_best_internal.y)),
                    }
                finally:
                    sys.path.remove(str(root))
            expected = {
                "logged_evaluations": contract["endpoint"]["logged_evaluations"],
                "best_evaluation": contract["endpoint"]["best_evaluation"],
                "best_y_decimal": contract["endpoint"]["best_y_decimal"],
            }
            status = (
                "PASS_SOURCE_NATIVE_ENDPOINT_REPLAY"
                if observed == expected
                else "SOURCE_NATIVE_MISMATCH"
            )
        except Exception as error:  # evidence records an optional diagnostic blocker
            status = "SOURCE_NATIVE_BLOCKED_EXECUTION_ERROR"
            observed = {"error_type": type(error).__name__, "error": str(error)[:500]}
        runtime = time.perf_counter() - started
    report = bind_report(
        {
            "schema_version": "1.0.0",
            "candidate_id": "EU26-12",
            "status": "TARGETED_ARTIFACT_REPLAY_ONLY",
            "paper_mapping": contract["paper_mapping"],
            "source_native_gate": status,
            "historical_environment_proven": False,
            "dependency_lock_in_upstream": False,
            "versions": versions,
            "observed": observed,
            "expected": {
                "logged_evaluations": contract["endpoint"]["logged_evaluations"],
                "best_evaluation": contract["endpoint"]["best_evaluation"],
                "best_y_decimal": contract["endpoint"]["best_y_decimal"],
            },
            "runtime_seconds": runtime,
            "code": code,
            "forbidden_claims": contract["forbidden_claims"],
        },
        domain=b"EU26-12-SOURCE-NATIVE-REPORT-V1",
    )
    write_new_json(args.output, report)
    print(status)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
