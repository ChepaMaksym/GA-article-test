"""Hash, Git-identity, token, and optional CSV-dimension probes for GARBO."""

from __future__ import annotations

import csv
import hashlib
from pathlib import Path
import subprocess
from typing import Any, Mapping, Sequence

from .contract import SOURCE_MANIFEST_PATH, load_contract, sha256_file


class SourceProbeError(RuntimeError):
    """Raised when upstream source identity or required tokens drift."""


REQUIRED_GARBO_TOKENS = (
    "fv = np.arange(-0.01, 0.7, 0.001)",
    "ft = np.arange(-0.01, 0.7, 0.001)",
    "mlc = np.arange(0, 200, 1)",
    "ssc = np.arange(-0.01, 1.01, 0.01)",
    "cr = np.arange(0, 0.8, 0.01)",
    "mr = np.arange(0, 0.3, 0.01)",
    "pi = np.arange(0.1, 0.4, 0.01)",
    "pd = np.arange(0.1, 0.4, 0.01)",
    "est = np.arange(-0.12, 0.12, 0.01)",
    "FT_class = intFV(ft_input)",
    "pS = 1 - (pD + pI)",
    "fv = (max(fits) - (sum(fits) / len(population))) / max(fits)",
    "ft = abs((sum(fits) / len(population)) - crt_mean_fit)",
    "mlc = np.mean([len(i) for i in population])",
    "ssc = toolbox.get_ssc(population)",
    "if ssc > 0.75:",
    "cxpb  = 0",
    "mutpb = 1",
    "mutop = [0.9,0.1,0]",
)


def _git(source_dir: Path, arguments: Sequence[str], *, binary: bool = False):
    completed = subprocess.run(
        ["git", "-C", str(source_dir), *arguments],
        check=False,
        capture_output=True,
        text=not binary,
    )
    if completed.returncode != 0:
        stderr = completed.stderr
        if isinstance(stderr, bytes):
            stderr = stderr.decode("utf-8", errors="replace")
        raise SourceProbeError(f"git {' '.join(arguments)} failed: {stderr.strip()}")
    if binary:
        return completed.stdout
    return completed.stdout.strip()


def probe_required_tokens(source_text: str) -> dict[str, Any]:
    missing = [token for token in REQUIRED_GARBO_TOKENS if token not in source_text]
    if missing:
        raise SourceProbeError(f"required GARBO tokens missing: {missing}")
    if "FT_class = intFT(ft_input)" in source_text:
        raise SourceProbeError("source contains a corrected intFT mutation antecedent")
    numpy_calls = source_text.count("np.random.")
    numpy_seeded = "np.random.seed" in source_text
    if numpy_calls == 0:
        raise SourceProbeError("expected NumPy RNG calls were not found")
    if numpy_seeded:
        raise SourceProbeError("frozen RNG blocker changed: NumPy is now explicitly seeded")
    return {
        "required_tokens": len(REQUIRED_GARBO_TOKENS),
        "numpy_random_call_tokens": numpy_calls,
        "numpy_random_seed_present": numpy_seeded,
        "mutation_antecedent": "intFV(ft_input)",
    }


def probe_csv_dimension(
    csv_path: Path,
    contract: Mapping[str, Any] | None = None,
    *,
    source_dir: Path | None = None,
) -> dict[str, Any]:
    contract_value = load_contract() if contract is None else contract
    expected = contract_value["applied_dimension"]
    if source_dir is None:
        raise SourceProbeError(
            "CSV dimension probe requires its exact upstream Git checkout"
        )
    source_dir = source_dir.resolve()
    csv_path = csv_path.resolve()
    identity = _manifest_data_identity(contract_value)
    expected_path = (source_dir / identity["path"]).resolve()
    if csv_path != expected_path:
        raise SourceProbeError(
            f"CSV must be the manifest-bound upstream path {expected_path}"
        )
    if not csv_path.is_file():
        raise SourceProbeError(f"manifest-bound CSV is absent: {csv_path}")
    actual_bytes = csv_path.stat().st_size
    if actual_bytes != identity["bytes"]:
        raise SourceProbeError(
            f"CSV byte-length drift: expected {identity['bytes']}, got {actual_bytes}"
        )
    actual_sha256 = sha256_file(csv_path)
    if actual_sha256 != identity["sha256"]:
        raise SourceProbeError(
            f"CSV SHA-256 drift: expected {identity['sha256']}, got {actual_sha256}"
        )
    actual_blob = _git(source_dir, ["rev-parse", f"HEAD:{identity['path']}"])
    if actual_blob != identity["git_blob"]:
        raise SourceProbeError(
            f"CSV Git blob drift: expected {identity['git_blob']}, got {actual_blob}"
        )
    with csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.reader(handle)
        try:
            header = next(reader)
        except StopIteration as error:
            raise SourceProbeError("CSV has no header") from error
        row_count = 0
        for row_count, row in enumerate(reader, start=1):
            if len(row) != len(header):
                raise SourceProbeError(
                    f"CSV row {row_count + 1} has {len(row)} fields, "
                    f"expected {len(header)}"
                )
    if len(header) != expected["columns"]:
        raise SourceProbeError(
            f"CSV has {len(header)} columns, expected {expected['columns']}"
        )
    if not header or header[-1] != expected["target_column"]:
        raise SourceProbeError("CSV final target column is not class")
    if len(header) - 1 != expected["predictors"]:
        raise SourceProbeError("CSV predictor count drift")
    if row_count != expected["rows_excluding_header"]:
        raise SourceProbeError(
            f"CSV has {row_count} data rows, expected {expected['rows_excluding_header']}"
        )
    return {
        "mode": "OPTIONAL_STRUCTURE_ONLY",
        "path": str(csv_path),
        "bytes": actual_bytes,
        "git_blob": actual_blob,
        "sha256": actual_sha256,
        "rows_excluding_header": row_count,
        "columns": len(header),
        "predictors": len(header) - 1,
        "target_column": header[-1],
        "dataset_license_status": expected["dataset_license_status"],
        "license_claim": False,
    }


def _manifest_data_identity(contract: Mapping[str, Any]) -> dict[str, Any]:
    expected_revision = contract["upstream"]["licensed_revision"]
    expected_path = contract["applied_dimension"]["observed_path"]
    with SOURCE_MANIFEST_PATH.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    matches = [
        row
        for row in rows
        if row["role"] == "dimension-evidence"
        and row["revision"] == expected_revision
        and row["path"] == expected_path
    ]
    if len(matches) != 1:
        raise SourceProbeError("source manifest must bind exactly one data identity")
    row = matches[0]
    required = ("git_blob", "bytes", "sha256")
    if any(not row[field] for field in required):
        raise SourceProbeError("data identity is incomplete in source manifest")
    return {
        "path": row["path"],
        "git_blob": row["git_blob"],
        "bytes": int(row["bytes"]),
        "sha256": row["sha256"],
    }


def probe_source(
    source_dir: Path, data_csv: Path | None = None
) -> dict[str, Any]:
    source_dir = source_dir.resolve()
    if not source_dir.is_dir():
        raise SourceProbeError(f"source directory does not exist: {source_dir}")
    status_arguments = ["status", "--porcelain=v1", "--untracked-files=all"]
    status_before = _git(source_dir, status_arguments)
    if status_before:
        raise SourceProbeError(
            f"upstream checkout is dirty before probing: {status_before!r}"
        )
    contract = load_contract()
    upstream = contract["upstream"]

    head = _git(source_dir, ["rev-parse", "HEAD"])
    tree = _git(source_dir, ["rev-parse", "HEAD^{tree}"])
    if head != upstream["licensed_revision"]:
        raise SourceProbeError(
            f"wrong upstream HEAD: expected {upstream['licensed_revision']}, got {head}"
        )
    if tree != upstream["licensed_tree"]:
        raise SourceProbeError(
            f"wrong upstream tree: expected {upstream['licensed_tree']}, got {tree}"
        )

    file_report: dict[str, Any] = {}
    for relative, expected in upstream["required_files"].items():
        path = source_dir / relative
        if not path.is_file():
            raise SourceProbeError(f"required upstream file absent: {relative}")
        size = path.stat().st_size
        digest = sha256_file(path)
        blob = _git(source_dir, ["rev-parse", f"HEAD:{relative}"])
        if size != expected["bytes"]:
            raise SourceProbeError(f"byte-length drift for {relative}")
        if digest != expected["sha256"]:
            raise SourceProbeError(f"SHA-256 drift for {relative}")
        if blob != expected["git_blob"]:
            raise SourceProbeError(f"Git blob drift for {relative}")
        file_report[relative] = {
            "bytes": size,
            "sha256": digest,
            "git_blob": blob,
        }

    source_text = (source_dir / "GARBO.py").read_text(encoding="utf-8")
    token_report = probe_required_tokens(source_text)

    paper_revision = upstream["paper_era_revision"]
    identical: dict[str, Any] = {}
    for relative in upstream["paper_era_identical_paths"]:
        historical = _git(
            source_dir, ["show", f"{paper_revision}:{relative}"], binary=True
        )
        current = (source_dir / relative).read_bytes()
        if historical != current:
            raise SourceProbeError(
                f"paper-era {relative} is not byte-identical to licensed revision"
            )
        identical[relative] = {
            "sha256": hashlib.sha256(historical).hexdigest(),
            "bytes": len(historical),
        }

    tags = _git(source_dir, ["tag", "--points-at", "HEAD"]).splitlines()
    report: dict[str, Any] = {
        "schema_version": "1.0.0",
        "candidate_id": "EU26-15",
        "candidate_status": "CONDITIONAL_NONELIGIBLE",
        "verification_scope": "FORMULA_AND_SOURCE_TRANSITION_VALIDATION_ONLY",
        "status": "PASS_SOURCE_IDENTITY",
        "pass_full": False,
        "source_native_execution": False,
        "head": head,
        "tree": tree,
        "files": file_report,
        "tokens": token_report,
        "paper_era_revision": paper_revision,
        "paper_era_identical": identical,
        "tags_at_head": tags,
        "release_status": "NO_TAG_AT_PIN" if not tags else "TAG_PRESENT",
        "rng_status": "BLOCKED_NUMPY_RNG_UNSEEDED",
        "git_status_before": "CLEAN",
    }
    if data_csv is not None:
        report["data_dimension"] = probe_csv_dimension(
            data_csv, contract, source_dir=source_dir
        )
    status_after = _git(source_dir, status_arguments)
    if status_after != status_before or status_after:
        raise SourceProbeError(
            "upstream checkout changed during probing: "
            f"before={status_before!r}, after={status_after!r}"
        )
    report["git_status_after"] = "CLEAN"
    return report
