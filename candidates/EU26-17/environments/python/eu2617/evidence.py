"""Dependency-light parsers for EU26-17 paper, experiment, and input facts."""

from __future__ import annotations

import ast
import csv
import hashlib
import io
from pathlib import Path
import re
import subprocess
import zipfile

import numpy as np


EXPECTED_FEATURES = [
    "age",
    "sex",
    "Jitter(%)",
    "Jitter(Abs)",
    "Jitter:RAP",
    "Jitter:PPQ5",
    "Jitter:DDP",
    "Shimmer",
    "Shimmer(dB)",
    "Shimmer:APQ3",
    "Shimmer:APQ5",
    "Shimmer:APQ11",
    "Shimmer:DDA",
    "NHR",
    "HNR",
    "RPDE",
    "DFA",
    "PPE",
]


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _assignment_int(tree: ast.AST, name: str) -> int:
    matches: list[int] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign) or len(node.targets) != 1:
            continue
        target = node.targets[0]
        if isinstance(target, ast.Name) and target.id == name:
            if isinstance(node.value, ast.Constant) and isinstance(node.value.value, int):
                matches.append(node.value.value)
    if len(matches) != 1:
        raise ValueError(f"expected one integer assignment to {name}; got {matches}")
    return matches[0]


def parse_experiment_protocol(members: dict[str, bytes]) -> dict[str, object]:
    tuning_path = "runs/saga_comparison_tests/saga_comparison_tuning.py"
    shared_path = "runs/saga_comparison_tests/configurations/shared_config.py"
    tuning = ast.parse(members[tuning_path].decode("utf-8"))
    shared = ast.parse(members[shared_path].decode("utf-8"))
    master = _assignment_int(tuning, "random_state")
    if master != 42 or _assignment_int(shared, "random_state") != master:
        raise ValueError("master seed is not consistently frozen to 42")

    seed_calls = [
        node
        for node in ast.walk(tuning)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "generate_state"
    ]
    if len(seed_calls) != 1:
        raise ValueError("expected one SeedSequence.generate_state call")
    seed_call = seed_calls[0]
    if not (
        len(seed_call.args) == 1
        and isinstance(seed_call.args[0], ast.Constant)
        and seed_call.args[0].value == 8
        and isinstance(seed_call.func.value, ast.Call)
        and isinstance(seed_call.func.value.func, ast.Attribute)
        and seed_call.func.value.func.attr == "SeedSequence"
        and len(seed_call.func.value.args) == 1
        and isinstance(seed_call.func.value.args[0], ast.Name)
        and seed_call.func.value.args[0].id == "random_state"
    ):
        raise ValueError("seed derivation differs from SeedSequence(random_state).generate_state(8)")

    split_calls = [
        node
        for node in ast.walk(tuning)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "ShuffleSplit"
    ]
    if len(split_calls) != 1:
        raise ValueError("expected one ShuffleSplit call")
    keywords = {item.arg: item.value for item in split_calls[0].keywords}
    if not (
        isinstance(keywords.get("n_splits"), ast.Constant)
        and keywords["n_splits"].value == 8
        and isinstance(keywords.get("test_size"), ast.Constant)
        and keywords["test_size"].value == 0.25
        and isinstance(keywords.get("random_state"), ast.Name)
        and keywords["random_state"].id == "random_state"
    ):
        raise ValueError("ShuffleSplit protocol differs from the frozen contract")

    seeds = np.random.SeedSequence(master).generate_state(8).tolist()
    expected = [
        3444837047,
        2669555309,
        2046530742,
        3581440988,
        1691623607,
        2099784219,
        1184028159,
        862288241,
    ]
    if seeds != expected:
        raise ValueError(f"NumPy SeedSequence derivation changed: {seeds}")
    return {
        "master_seed": master,
        "derivation": "numpy.random.SeedSequence(42).generate_state(8)",
        "model_seeds": seeds,
        "splitter": {
            "kind": "ShuffleSplit",
            "n_splits": 8,
            "test_size": 0.25,
            "random_state": 42,
        },
        "nominal_model_split_fits": 64,
        "provenance_scope": "SOURCE_EXPRESSES_PROTOCOL_ONLY",
        "historical_execution_proven": False,
    }


def _literal(node: ast.AST) -> object:
    try:
        return ast.literal_eval(node)
    except (ValueError, TypeError) as exc:
        raise ValueError("loader call contains a non-literal frozen argument") from exc


def parse_parkinson_loader(loader_bytes: bytes) -> dict[str, object]:
    tree = ast.parse(loader_bytes.decode("utf-8"))
    functions = [
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "load_parkinson_total"
    ]
    if len(functions) != 1:
        raise ValueError("expected one load_parkinson_total function")
    returns = [node for node in ast.walk(functions[0]) if isinstance(node, ast.Return)]
    if len(returns) != 1 or not isinstance(returns[0].value, ast.Call):
        raise ValueError("Parkinson loader must contain one return call")
    call = returns[0].value
    if not (isinstance(call.func, ast.Name) and call.func.id == "load_dataset"):
        raise ValueError("Parkinson loader no longer delegates to load_dataset")
    keywords = {item.arg: item.value for item in call.keywords}
    filename = _literal(keywords["filename"])
    target = _literal(keywords["target_column"])
    removed = _literal(keywords["remove_columns"])
    expected_removed = ["subject#", "test_time", "motor_UPDRS"]
    if filename != "parkinson.csv" or target != "total_UPDRS":
        raise ValueError("Parkinson total-UPDRS loader target changed")
    if removed != expected_removed:
        raise ValueError(f"Parkinson removed columns changed: {removed}")
    return {"filename": filename, "target": target, "removed_columns": removed}


def parse_parkinson_csv(
    csv_bytes: bytes,
    loader: dict[str, object],
) -> dict[str, object]:
    if len(csv_bytes) != 911261 or _sha256(csv_bytes) != (
        "f2c7d5025dec4e92e7feae367a5f7ccf58789a10ac6b54bdf15976c599f9dd39"
    ):
        raise ValueError("Parkinson CSV identity mismatch")
    rows = list(csv.reader(io.StringIO(csv_bytes.decode("utf-8"))))
    if not rows:
        raise ValueError("Parkinson CSV is empty")
    header = rows[0]
    data_rows = rows[1:]
    if len(header) != 22 or len(data_rows) != 5875:
        raise ValueError(
            f"Parkinson shape mismatch: columns={len(header)}, rows={len(data_rows)}"
        )
    if any(len(row) != len(header) for row in data_rows):
        raise ValueError("Parkinson CSV contains a ragged row")
    excluded = {str(loader["target"]), *map(str, loader["removed_columns"])}
    features = [name for name in header if name not in excluded]
    if features != EXPECTED_FEATURES:
        raise ValueError(f"Parkinson feature list changed: {features}")
    return {
        "csv_columns": len(header),
        "rows": len(data_rows),
        "target": loader["target"],
        "removed_columns": loader["removed_columns"],
        "input_dimension": len(features),
        "features": features,
        "sha256": _sha256(csv_bytes),
        "bytes": len(csv_bytes),
    }


def authenticate_uci_archive(archive_path: Path, repository_csv: bytes) -> dict[str, object]:
    if not archive_path.is_file():
        raise ValueError(f"UCI archive does not exist: {archive_path}")
    with zipfile.ZipFile(archive_path) as archive:
        names = archive.namelist()
        if names.count("parkinsons_updrs.data") != 1:
            raise ValueError("UCI archive must contain one parkinsons_updrs.data member")
        member = archive.read("parkinsons_updrs.data")
    if len(member) != 911261 or _sha256(member) != (
        "f2c7d5025dec4e92e7feae367a5f7ccf58789a10ac6b54bdf15976c599f9dd39"
    ):
        raise ValueError("UCI Parkinson member identity mismatch")
    if member != repository_csv:
        raise ValueError("UCI member and repository Parkinson CSV are not byte-identical")
    archive_bytes = archive_path.read_bytes()
    return {
        "doi": "10.24432/C5ZS3N",
        "license": "CC-BY-4.0",
        "archive_bytes": len(archive_bytes),
        "archive_sha256": _sha256(archive_bytes),
        "member": "parkinsons_updrs.data",
        "member_bytes": len(member),
        "member_sha256": _sha256(member),
        "repository_byte_identity": True,
        "status": "PASS_LAWFUL_INPUT",
    }


def parse_paper_table(paper_path: Path) -> dict[str, object]:
    if not paper_path.is_file():
        raise ValueError(f"paper PDF does not exist: {paper_path}")
    value = paper_path.read_bytes()
    expected_sha = "f55862101aaf771c3ccedcbc98d66c57d41903a89eabaebf8bed3903c1044fa0"
    if len(value) != 3303306 or _sha256(value) != expected_sha:
        raise ValueError("institutional paper PDF identity mismatch")
    completed = subprocess.run(
        ["pdftotext", "-layout", str(paper_path), "-"],
        check=False,
        capture_output=True,
    )
    if completed.returncode != 0:
        raise ValueError(
            "pdftotext failed: "
            + completed.stderr.decode("utf-8", errors="replace").strip()
        )
    text = completed.stdout.decode("utf-8", errors="replace")
    if "10.1109/CEC60901.2024.10612101" not in text:
        raise ValueError("paper DOI is absent from authenticated extracted text")
    pattern = re.compile(
        r"Parkinson(?:['’]s|.s)\s+Telemonitoring\s+PT\s+18\s+5875",
        flags=re.IGNORECASE,
    )
    matches = pattern.findall(text)
    if len(matches) != 1:
        raise ValueError(f"expected one PT Table I row; found {len(matches)}")
    return {
        "paper_sha256": expected_sha,
        "paper_bytes": len(value),
        "table": "Table I",
        "dataset": "Parkinson's Telemonitoring",
        "abbreviation": "PT",
        "input_dimension": 18,
        "sample_count": 5875,
        "optimizer_numeric_endpoint": None,
    }
