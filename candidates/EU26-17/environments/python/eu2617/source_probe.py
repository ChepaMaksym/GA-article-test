"""Authenticate Git objects and execute the frozen SAGA1 method bodies."""

from __future__ import annotations

import ast
import copy
from dataclasses import asdict
import hashlib
import io
import json
from pathlib import Path
import subprocess
from types import SimpleNamespace
import tokenize
import warnings

import numpy as np

from .formula import RateState, SAGA1Config


CORE_FILES = {
    "suprb/optimizer/solution/saga1/base.py": {
        "bytes": 5585,
        "blob": "1f92f468fc2e48f802a2c9f67caf1831694130ab",
        "sha256": "25ee2543b4133f7095ce4e951d42f3530ddeaa24ae735e77750e802f97a8f879",
    },
    "LICENSE": {
        "bytes": 35149,
        "blob": "f288702d2fa16d3cdf0035b15a9fcbc552cd88e7",
        "sha256": "3972dc9744f6499f0f9b2dbf76696f2ae7ad8af9b23dde66d6af86c9dfb36986",
    },
    "pyproject.toml": {
        "bytes": 104,
        "blob": "158a5387a77d5e86f751921cfa7fc4bda4457afc",
        "sha256": "5e9404f616bc429668d9e4a9704cd817ca41500ffd49d6cdd64bfa5ecddf3e80",
    },
}

EXPERIMENT_FILES = {
    "requirements.txt": {
        "bytes": 1337,
        "blob": "5628ca6e725917d767683937196527840b92a7d8",
        "sha256": "2e6e375b3143241c04a7461c7e39bac295964ea95832a68317cbdfd972d49dc8",
    },
    ".gitignore": {
        "bytes": 1943,
        "blob": "15d4675845c010fd83743959416a17abfe323b64",
        "sha256": "7a8825b24b6408a74b391d4e2cff2b087cbadfb0cad9eb7eddaf5140a2c06e31",
    },
    "runs/saga_comparison_tests/configurations/shared_config.py": {
        "bytes": 1377,
        "blob": "b712e451d64e81368a9d2af4df3162b6d67f3f03",
        "sha256": "edc152e0a0ef7ff6e4b7ee489233103af509243a4957f2dd66178e0ec2a149de",
    },
    "runs/saga_comparison_tests/saga_comparison_tuning.py": {
        "bytes": 10700,
        "blob": "50d13a87f5f04f90b657b48a974753a665867e60",
        "sha256": "e02168ea5f79c2831cb078f88ee75707316ff52258a59a9509231484949c593e",
    },
    "problems/datasets/base.py": {
        "bytes": 6920,
        "blob": "4940b9d38a84b7f79fe670252e08c284cfd979a6",
        "sha256": "6e339a4433ee4c2ab583633e013e2f1e9c3d75e875ac9fbad78fabc6c62d3104",
    },
    "problems/datasets/data/parkinson.csv": {
        "bytes": 911261,
        "blob": "30a906e0369dda8c666ad1cb715b68ca9f560741",
        "sha256": "f2c7d5025dec4e92e7feae367a5f7ccf58789a10ac6b54bdf15976c599f9dd39",
    },
    "LICENSE": CORE_FILES["LICENSE"],
}


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _git(repo: Path, *arguments: str, text: bool = False) -> bytes | str:
    if not (repo / ".git").exists():
        raise ValueError(f"not a Git checkout: {repo}")
    completed = subprocess.run(
        ["git", "-C", str(repo), *arguments],
        check=False,
        capture_output=True,
    )
    if completed.returncode != 0:
        stderr = completed.stderr.decode("utf-8", errors="replace").strip()
        raise ValueError(f"git {' '.join(arguments)} failed in {repo}: {stderr}")
    if text:
        return completed.stdout.decode("utf-8").strip()
    return completed.stdout


def git_member(repo: Path, revision: str, path: str) -> bytes:
    return _git(repo, "show", f"{revision}:{path}")  # type: ignore[return-value]


def _verify_revision(repo: Path, commit: str, expected_tree: str) -> dict[str, str]:
    actual_commit = _git(repo, "rev-parse", f"{commit}^{{commit}}", text=True)
    actual_tree = _git(repo, "rev-parse", f"{commit}^{{tree}}", text=True)
    if not (
        actual_commit == commit
        or (12 <= len(commit) < 40 and actual_commit.startswith(commit))
    ):
        raise ValueError(f"commit identity mismatch: {actual_commit} != {commit}")
    if actual_tree != expected_tree:
        raise ValueError(f"tree identity mismatch: {actual_tree} != {expected_tree}")
    return {
        "requested_revision": commit,
        "commit": actual_commit,
        "tree": actual_tree,
    }


def _verify_file(
    repo: Path,
    revision: str,
    path: str,
    expected: dict[str, object],
) -> tuple[bytes, dict[str, object]]:
    value = git_member(repo, revision, path)
    blob = _git(repo, "rev-parse", f"{revision}:{path}", text=True)
    actual = {
        "path": path,
        "bytes": len(value),
        "blob": blob,
        "sha256": sha256_bytes(value),
    }
    for key in ("bytes", "blob", "sha256"):
        if actual[key] != expected[key]:
            raise ValueError(
                f"{revision}:{path} {key} mismatch: "
                f"{actual[key]} != {expected[key]}"
            )
    return value, actual


def _method_node(tree: ast.AST, name: str) -> ast.FunctionDef:
    matches = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef) and node.name == name
    ]
    if len(matches) != 1:
        raise ValueError(f"expected exactly one {name} method; found {len(matches)}")
    return matches[0]


def method_identity(source: str, name: str) -> tuple[ast.FunctionDef, dict[str, object]]:
    node = _method_node(ast.parse(source), name)
    segment = ast.get_source_segment(source, node)
    if segment is None:
        raise ValueError(f"could not extract source for {name}")
    ignored = {
        tokenize.ENCODING,
        tokenize.NL,
        tokenize.NEWLINE,
        tokenize.INDENT,
        tokenize.DEDENT,
        tokenize.ENDMARKER,
    }
    token_strings = [
        token.string
        for token in tokenize.generate_tokens(io.StringIO(segment).readline)
        if token.type not in ignored
    ]
    token_json = json.dumps(token_strings, separators=(",", ":"))
    ast_dump = ast.dump(node, annotate_fields=True, include_attributes=False)
    return node, {
        "source_sha256": sha256_bytes(segment.encode("utf-8")),
        "token_count": len(token_strings),
        "tokens_sha256": sha256_bytes(token_json.encode("utf-8")),
        "ast_sha256": sha256_bytes(ast_dump.encode("utf-8")),
    }


def _compile_source_methods(source: str) -> type:
    tree = ast.parse(source)
    originals = [_method_node(tree, "calc_gdm"), _method_node(tree, "adjust_rates")]
    copies = copy.deepcopy(originals)
    for original, cloned in zip(originals, copies, strict=True):
        if ast.dump(original, include_attributes=False) != ast.dump(
            cloned, include_attributes=False
        ):
            raise AssertionError("source method changed during AST copy")
        for node in ast.walk(cloned):
            for attribute in ("lineno", "col_offset", "end_lineno", "end_col_offset"):
                if hasattr(node, attribute):
                    delattr(node, attribute)
    scaffold = ast.parse("class AuthenticatedSourceProbe:\n    pass\n")
    class_node = scaffold.body[0]
    if not isinstance(class_node, ast.ClassDef):
        raise AssertionError("invalid AST scaffold")
    class_node.body = copies
    ast.fix_missing_locations(scaffold)
    namespace: dict[str, object] = {"np": np}
    exec(compile(scaffold, "<authenticated-saga1-methods>", "exec"), namespace)
    return namespace["AuthenticatedSourceProbe"]  # type: ignore[return-value]


def execute_source_methods(
    source: str,
    fitness: list[float],
    state: RateState = RateState(),
    config: SAGA1Config = SAGA1Config(),
) -> dict[str, object]:
    """Execute only the authenticated upstream method AST bodies."""

    probe_class = _compile_source_methods(source)
    probe = probe_class()
    probe.population_ = [SimpleNamespace(fitness_=float(item)) for item in fitness]
    for name, value in asdict(config).items():
        setattr(probe, name, value)
    probe.mutation_rate = float(state.mutation_rate)
    probe.crossover_rate = float(state.crossover_rate)
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        gdm = float(probe.calc_gdm())
        probe.adjust_rates()
    return {
        "gdm": gdm,
        "mutation_rate": float(probe.mutation_rate),
        "crossover_rate": float(probe.crossover_rate),
        "warnings": [str(item.message) for item in caught],
    }


def _verify_update_timing(source: str) -> dict[str, object]:
    tree = ast.parse(source)
    optimize = _method_node(tree, "_optimize")
    loops = [node for node in optimize.body if isinstance(node, ast.For)]
    if len(loops) != 1:
        raise ValueError("SAGA1 _optimize must contain one generation loop")
    loop = loops[0]
    if not loop.body or not isinstance(loop.body[0], ast.Expr):
        raise ValueError("generation loop does not begin with an expression")
    first_call = loop.body[0].value
    if not (
        isinstance(first_call, ast.Call)
        and isinstance(first_call.func, ast.Attribute)
        and isinstance(first_call.func.value, ast.Name)
        and first_call.func.value.id == "self"
        and first_call.func.attr == "adjust_rates"
    ):
        raise ValueError("adjust_rates is not the first executable loop statement")
    loop_source = ast.get_source_segment(source, loop)
    if loop_source is None:
        raise ValueError("could not extract SAGA1 generation loop")
    markers = [
        "self.adjust_rates()",
        "elitists =",
        "parents =",
        "parent_pairs =",
        "children =",
        "mutated_children =",
        "self.population_ = elitists",
        "self.population_.extend",
        "self.fit_population(X, y)",
    ]
    positions = [loop_source.find(marker) for marker in markers]
    if any(position < 0 for position in positions) or positions != sorted(positions):
        raise ValueError("generation operation order does not match the frozen contract")
    return {
        "update_frequency": "once_per_generation",
        "first_loop_statement": "adjust_rates",
        "subsequent_order": [
            "elitism",
            "selection",
            "parent_pairing",
            "crossover",
            "mutation",
            "replacement",
            "population_refit",
        ],
    }


def authenticate_sources(
    core_repo: Path,
    experiment_repo: Path,
    contract: dict[str, object],
) -> tuple[dict[str, object], str, dict[str, bytes]]:
    """Authenticate revisions and every required source member."""

    revisions = contract["source_revisions"]
    if not isinstance(revisions, dict):
        raise ValueError("contract source_revisions must be an object")
    freeze = revisions["core_publication_era_auditor_freeze"]
    addition = revisions["core_algorithm_addition"]
    experiment = revisions["experiment"]
    if not all(isinstance(item, dict) for item in (freeze, addition, experiment)):
        raise ValueError("malformed source revision contract")

    freeze_revision = _verify_revision(
        core_repo, str(freeze["commit"]), str(freeze["tree"])
    )
    addition_revision = _verify_revision(
        core_repo, str(addition["commit"]), str(addition["tree"])
    )
    experiment_revision = _verify_revision(
        experiment_repo, str(experiment["commit"]), str(experiment["tree"])
    )

    core_members: dict[str, bytes] = {}
    core_evidence: list[dict[str, object]] = []
    for path, expected in CORE_FILES.items():
        value, evidence = _verify_file(core_repo, str(freeze["commit"]), path, expected)
        core_members[path] = value
        core_evidence.append(evidence)

    addition_source, addition_evidence = _verify_file(
        core_repo,
        str(addition["commit"]),
        "suprb/optimizer/solution/saga1/base.py",
        CORE_FILES["suprb/optimizer/solution/saga1/base.py"],
    )
    if addition_source != core_members["suprb/optimizer/solution/saga1/base.py"]:
        raise ValueError("SAGA1 source changed between addition and auditor freeze")

    experiment_members: dict[str, bytes] = {}
    experiment_evidence: list[dict[str, object]] = []
    for path, expected in EXPERIMENT_FILES.items():
        value, evidence = _verify_file(
            experiment_repo, str(experiment["commit"]), path, expected
        )
        experiment_members[path] = value
        experiment_evidence.append(evidence)

    license_text = core_members["LICENSE"].decode("utf-8")
    if "GNU GENERAL PUBLIC LICENSE" not in license_text or "Version 3" not in license_text:
        raise ValueError("authenticated core license is not GPL version 3 text")
    if experiment_members["LICENSE"] != core_members["LICENSE"]:
        raise ValueError("core and experiment license objects differ")

    source = core_members["suprb/optimizer/solution/saga1/base.py"].decode("utf-8")
    expected_methods = contract["authenticated_methods"]["methods"]
    method_evidence: dict[str, object] = {}
    for name in ("calc_gdm", "adjust_rates"):
        _, actual = method_identity(source, name)
        expected = expected_methods[name]
        if actual != expected:
            raise ValueError(f"{name} identity mismatch: {actual} != {expected}")
        method_evidence[name] = actual

    requirements = experiment_members["requirements.txt"].decode("utf-8")
    mutable_requirement = "-e git+https://github.com/heidmic/suprb@main#egg=suprb"
    if mutable_requirement not in requirements.splitlines():
        raise ValueError("experiment no longer contains the frozen suprb@main line")

    paths = str(
        _git(
            experiment_repo,
            "ls-tree",
            "-r",
            "--name-only",
            str(experiment["commit"]),
            text=True,
        )
    ).splitlines()
    raw_paths = [
        path
        for path in paths
        if any(part.lower().startswith("mlruns") for part in Path(path).parts)
    ]
    if raw_paths:
        raise ValueError(f"unexpected tracked mlruns paths: {raw_paths}")
    ignore_lines = {
        line.strip()
        for line in experiment_members[".gitignore"].decode("utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    }
    required_ignores = {"**/mlruns/**", "mlruns/**", "mlruns_pt/**"}
    if not required_ignores.issubset(ignore_lines):
        raise ValueError("frozen mlruns ignore patterns are missing")

    evidence = {
        "status": "PASS_SOURCE_IDENTITY",
        "core_auditor_freeze": freeze_revision,
        "core_algorithm_addition": addition_revision,
        "experiment": experiment_revision,
        "core_files": core_evidence,
        "algorithm_addition_source": addition_evidence,
        "experiment_files": experiment_evidence,
        "methods": method_evidence,
        "timing": _verify_update_timing(source),
        "license": "GPL-3.0",
        "experiment_core_dependency": "suprb@main",
        "author_pinned_experiment_core": False,
        "tracked_mlruns_paths": raw_paths,
        "required_mlruns_ignore_patterns": sorted(required_ignores),
    }
    return evidence, source, experiment_members
