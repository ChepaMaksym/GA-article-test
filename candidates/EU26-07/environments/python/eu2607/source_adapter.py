"""Fail-closed adapter for an external GPL-3.0 author checkout.

No upstream source or result data is imported into this repository.  The
adapter authenticates the external checkout first and then invokes the exact
problem-specific class used to generate the published raw ledger.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import importlib.util
from pathlib import Path
import random
import subprocess
from types import ModuleType
from typing import Any

import numpy as np

from .core import RunRow
from .published import BASE_SEED


EXPECTED_COMMIT = "49949a55208359ac93b7110afb23ed276bda158d"
EXPECTED_TREE = "a9d1a04fbbafbb114585ff7caf10bddc6381755a"
REQUIRED_FILES: dict[str, tuple[int, str]] = {
    "README.md": (
        1_789,
        "542db3cc40002aed7f44bb710855421563fd980d21eed24f616c75514d9879ba",
    ),
    "LICENSE": (
        35_149,
        "3972dc9744f6499f0f9b2dbf76696f2ae7ad8af9b23dde66d6af86c9dfb36986",
    ),
    "Python-code/utils/journalalgorithms.py": (
        81_176,
        "845f1a196f58682de6b40f39e5495e00814f2921cbd4bbc744d169975c577192",
    ),
    "Python-code/master.py": (
        7_849,
        "d1fb4f9e2c2c305936d2c078e2f40a43303e588f1a672d5de28c1dc8084ec71b",
    ),
    "Python-code/utils/functions.py": (
        11_928,
        "0aabfa6d3dcd490f0b4be763f0fda2e098deaed78cd2fbc59d39b05a0cfa9b05",
    ),
    "Python-code/utils/outputs.py": (
        1_034,
        "fb8d30d2e8291bca6742bc6e10ecdb8e72c21d6e1c5fad331bd4284a9dbac19d",
    ),
    "processed-results/SA (1+(λ,λ)) GA Reset_Jump_n20_k4_"
    "λ20_p1:20_c1_F1.5_extra-None": (
        48_980,
        "2dc530fa995c6980fd064f422b97e15db967aaee2ed5625be43b4fc5e10e21ab",
    ),
    "Raw/results_20-09-28_08:20:44_Jump_n20_"
    "JA.OnePlusLambdaCommaLambdaSAResetJUMP_λ20.txt": (
        48_505,
        "b2ac8c81efaf786823d49dcef26eeb20f0257ca7fe9e1e2394d02ca5e26dd9a6",
    ),
    "Results.ods": (
        41_052,
        "1d3b117c769662f7b47afda1e3c179cf189969f7b61ff257cf8ae77c70a62f05",
    ),
}


class SourceAdapterError(ValueError):
    """Raised before execution if provenance or source semantics are invalid."""


@dataclass(frozen=True)
class SourceIdentity:
    root: str
    commit: str
    tree: str
    required_files: int
    worktree_clean_for_required_files: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


_MODULE_CACHE: dict[str, tuple[ModuleType, ModuleType]] = {}


def _git(root: Path, *arguments: str) -> str:
    try:
        completed = subprocess.run(
            ["git", "-C", str(root), *arguments],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        raise SourceAdapterError(f"cannot authenticate Git checkout at {root}") from exc
    return completed.stdout.strip()


def authenticate_checkout(repository: Path) -> SourceIdentity:
    root = Path(repository).resolve()
    if not root.is_dir():
        raise SourceAdapterError(f"author checkout is not a directory: {root}")
    commit = _git(root, "rev-parse", "HEAD")
    tree = _git(root, "rev-parse", "HEAD^{tree}")
    if commit != EXPECTED_COMMIT:
        raise SourceAdapterError(f"commit mismatch: {commit} != {EXPECTED_COMMIT}")
    if tree != EXPECTED_TREE:
        raise SourceAdapterError(f"tree mismatch: {tree} != {EXPECTED_TREE}")

    for relative, (expected_bytes, expected_hash) in REQUIRED_FILES.items():
        path = root / relative
        try:
            payload = path.read_bytes()
        except OSError as exc:
            raise SourceAdapterError(f"cannot read required source: {relative}") from exc
        if len(payload) != expected_bytes:
            raise SourceAdapterError(
                f"byte-count mismatch for {relative}: {len(payload)} != {expected_bytes}"
            )
        observed_hash = hashlib.sha256(payload).hexdigest()
        if observed_hash != expected_hash:
            raise SourceAdapterError(
                f"SHA-256 mismatch for {relative}: {observed_hash} != {expected_hash}"
            )

    required_paths = list(REQUIRED_FILES)
    status = _git(root, "status", "--porcelain", "--", *required_paths)
    if status:
        raise SourceAdapterError("required author files have uncommitted changes")
    return SourceIdentity(
        root=str(root),
        commit=commit,
        tree=tree,
        required_files=len(REQUIRED_FILES),
        worktree_clean_for_required_files=True,
    )


def _load_module(name: str, path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise SourceAdapterError(f"cannot construct module loader for {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _author_modules(repository: Path) -> tuple[ModuleType, ModuleType]:
    root = Path(repository).resolve()
    key = str(root)
    cached = _MODULE_CACHE.get(key)
    if cached is not None:
        return cached
    authenticate_checkout(root)
    functions = _load_module(
        "eu2607_author_functions", root / "Python-code/utils/functions.py"
    )
    algorithms = _load_module(
        "eu2607_author_journalalgorithms",
        root / "Python-code/utils/journalalgorithms.py",
    )
    _MODULE_CACHE[key] = (functions, algorithms)
    return functions, algorithms


def run_author_artifact(
    repository: Path,
    run: int,
    *,
    base_seed: int = BASE_SEED,
    max_generations: int | None = None,
) -> RunRow:
    """Invoke the exact published Jump-specialized class directly."""

    if isinstance(run, bool) or not isinstance(run, int) or run < 1:
        raise SourceAdapterError("run must be a positive integer")
    functions, algorithms = _author_modules(repository)
    effective_seed = int(base_seed) + run
    np.random.seed(effective_seed)
    random.seed(effective_seed)
    problem = functions.Jump(20, 4)
    algorithm = algorithms.OnePlusLambdaCommaLambdaSAResetJUMP(
        problem,
        20,
        0.05,
        20,
        1.0,
        2,
        1.5,
        1,
    )
    while not algorithm.solved:
        if max_generations is not None and algorithm.generations >= max_generations:
            raise SourceAdapterError("max_generations reached before the optimum")
        next(algorithm)
    if not algorithm.lambda_gen or not algorithm.mut_prob_gen:
        raise SourceAdapterError("author run terminated without generation history")
    return RunRow(
        run=run,
        effective_seed=effective_seed,
        generations=int(algorithm.generations),
        evaluations=int(algorithm.evaluations),
        final_lambda=int(algorithm.lambda_gen[-1]),
        last_mutation_probability=float(algorithm.mut_prob_gen[-1]),
        solved=bool(algorithm.solved),
    )
