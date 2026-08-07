"""Fail-closed parser for the pinned EU26-02 Deleter result archive."""

from __future__ import annotations

import csv
import gzip
import hashlib
import io
import json
import math
import shutil
import statistics
import tarfile
import tempfile
from fractions import Fraction
from functools import lru_cache
from pathlib import Path, PurePosixPath
from typing import Any, Iterable

from .canonical import canonical_sha256


class ArchiveValidationError(ValueError):
    """Raised when an archive violates the preregistered schema or protocol."""


CANDIDATE_DIR = Path(__file__).resolve().parents[3]
PROFILES_PATH = CANDIDATE_DIR / "config" / "protocol_profiles.json"
TARGETS_PATH = CANDIDATE_DIR / "fixtures" / "published_table2_ahead_deleter.csv"
OPTIMIZER_CONFIG_PATH = CANDIDATE_DIR / "config" / "ahead_deleter_optimizer_config.json"

METADATA_HEADER = (
    "#date,problem,instance,nb_colors,use_target,rand_seed,objective,"
    "time_limit,max_iterations,parameters"
)
DATA_HEADER = ["turn", "time", "nb_uncolored", "penalty", "nb_colors", "solution"]


@lru_cache(maxsize=1)
def _load_profiles() -> dict[str, Any]:
    with PROFILES_PATH.open(encoding="utf-8") as handle:
        value = json.load(handle)
    if value.get("schema_version") != "1.0.0":
        raise ArchiveValidationError("unsupported protocol profile schema")
    return value


@lru_cache(maxsize=1)
def _load_targets() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with TARGETS_PATH.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        expected = {
            "instance",
            "bks",
            "bks_optimal",
            "published_best",
            "published_mean",
            "published_mean_best_time_seconds",
        }
        if set(reader.fieldnames or []) != expected:
            raise ArchiveValidationError("published target columns do not match v1")
        for row in reader:
            try:
                rows.append(
                    {
                        "instance": row["instance"],
                        "bks": int(row["bks"]),
                        "bks_optimal": row["bks_optimal"].lower() == "true",
                        "published_best": int(row["published_best"]),
                        "published_mean": float(row["published_mean"]),
                        "published_mean_best_time_seconds": int(
                            row["published_mean_best_time_seconds"]
                        ),
                    }
                )
            except (TypeError, ValueError) as error:
                raise ArchiveValidationError("invalid published target value") from error
    instances = [row["instance"] for row in rows]
    if len(rows) != 31 or len(set(instances)) != 31:
        raise ArchiveValidationError("published target fixture must contain 31 instances")
    return rows


@lru_cache(maxsize=1)
def _load_optimizer_config() -> dict[str, Any]:
    with OPTIMIZER_CONFIG_PATH.open(encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise ArchiveValidationError("frozen optimizer configuration must be an object")
    return value


def _profile(name: str) -> tuple[dict[str, Any], dict[str, Any]]:
    profiles = _load_profiles()
    try:
        selected = profiles["profiles"][name]
    except KeyError as error:
        raise ArchiveValidationError(f"unknown profile: {name}") from error
    return profiles, selected


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _is_sha256(value: Any) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def _safe_member_name(name: str) -> PurePosixPath:
    path = PurePosixPath(name)
    if path.is_absolute() or not path.parts or ".." in path.parts:
        raise ArchiveValidationError(f"unsafe archive member path: {name!r}")
    return path


def _root_csv_members(archive: tarfile.TarFile) -> list[tarfile.TarInfo]:
    members: list[tarfile.TarInfo] = []
    for member in archive.getmembers():
        path = _safe_member_name(member.name)
        if member.issym() or member.islnk():
            raise ArchiveValidationError(f"archive links are forbidden: {member.name!r}")
        if member.isfile() and path.suffix == ".csv" and "tbt" not in path.parts:
            members.append(member)
    if not members:
        raise ArchiveValidationError("archive contains no root result CSV files")
    return sorted(members, key=lambda item: item.name)


def _target_map() -> dict[str, dict[str, Any]]:
    return {row["instance"]: row for row in _load_targets()}


def _match_instance(filename: str, expected: Iterable[str]) -> str | None:
    matches = [name for name in expected if filename.startswith(f"{name}_")]
    if not matches:
        return None
    return max(matches, key=len)


def _group_members(
    members: Iterable[tarfile.TarInfo], expected: list[str]
) -> dict[str, list[tarfile.TarInfo]]:
    groups = {name: [] for name in expected}
    for member in members:
        name = _match_instance(PurePosixPath(member.name).name, expected)
        if name is None:
            raise ArchiveValidationError(
                f"unexpected root result filename: {member.name!r}"
            )
        groups[name].append(member)
    missing = [name for name in expected if not groups[name]]
    if missing:
        raise ArchiveValidationError(f"archive is missing instances: {', '.join(missing)}")
    return groups


def list_instances(archive_path: str | Path) -> list[str]:
    """Return the frozen 31-instance order after checking archive membership."""

    path = Path(archive_path)
    expected = list(_target_map())
    with tarfile.open(path, "r:*") as archive:
        _group_members(_root_csv_members(archive), expected)
    return expected


def _parse_int(value: str, context: str) -> int:
    try:
        result = int(value)
    except (TypeError, ValueError) as error:
        raise ArchiveValidationError(f"{context} must be an integer") from error
    return result


def _parse_metadata(lines: list[str], member_name: str) -> dict[str, Any]:
    if len(lines) < 3 or lines[0].strip() != METADATA_HEADER:
        raise ArchiveValidationError(f"{member_name}: malformed metadata header")
    if not lines[1].startswith("#"):
        raise ArchiveValidationError(f"{member_name}: missing metadata values")

    # The frozen source prints nine values below a ten-column header: the
    # declared ``objective`` field is absent.  Parsing this known shift is part
    # of the provenance evidence, not a silent correction.
    parts = lines[1][1:].strip().split(",", 8)
    if len(parts) != 9:
        raise ArchiveValidationError(f"{member_name}: malformed shifted metadata row")
    try:
        parameters = json.loads(parts[8])
    except json.JSONDecodeError as error:
        raise ArchiveValidationError(f"{member_name}: invalid parameter JSON") from error

    metadata = {
        "date": parts[0],
        "problem": parts[1],
        "instance": parts[2],
        "target_colors": _parse_int(parts[3], f"{member_name}: target_colors"),
        "use_target": parts[4].lower() == "true",
        "seed": _parse_int(parts[5], f"{member_name}: seed"),
        "time_limit_seconds": _parse_int(parts[6], f"{member_name}: time_limit"),
        "max_iterations": _parse_int(parts[7], f"{member_name}: max_iterations"),
        "parameters": parameters,
        "objective_header_value_missing": True,
    }
    if metadata["problem"] != "gcp" or not metadata["use_target"]:
        raise ArchiveValidationError(f"{member_name}: not a target-mode GCP result")
    if parameters != _load_optimizer_config():
        raise ArchiveValidationError(
            f"{member_name}: parameters differ from the frozen Deleter configuration"
        )
    if metadata["target_colors"] < 1 or metadata["seed"] < 0:
        raise ArchiveValidationError(f"{member_name}: invalid target or seed")
    if metadata["time_limit_seconds"] < 1 or metadata["max_iterations"] < 1:
        raise ArchiveValidationError(f"{member_name}: invalid budget metadata")
    return metadata


def _parse_attempt(
    raw: bytes,
    member_name: str,
    cutoff_seconds: int | None,
) -> dict[str, Any]:
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as error:
        raise ArchiveValidationError(f"{member_name}: non-UTF-8 CSV") from error
    lines = text.splitlines()
    metadata = _parse_metadata(lines, member_name)

    try:
        header_index = next(
            index
            for index, line in enumerate(lines)
            if line.strip().split(",") == DATA_HEADER
        )
    except StopIteration as error:
        raise ArchiveValidationError(f"{member_name}: missing result header") from error

    rows: list[dict[str, Any]] = []
    restart_lines = 0
    for line_number, raw_line in enumerate(lines[header_index + 1 :], header_index + 2):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line == "restart":
            restart_lines += 1
            continue
        values = next(csv.reader([line]))
        if len(values) != len(DATA_HEADER):
            raise ArchiveValidationError(
                f"{member_name}:{line_number}: malformed result row"
            )
        nb_colors = _parse_int(values[4], f"{member_name}:{line_number}: nb_colors")
        try:
            colors = [int(value) for value in values[5].split(":")] if values[5] else []
        except ValueError as error:
            raise ArchiveValidationError(
                f"{member_name}:{line_number}: non-integer solution label"
            ) from error
        row = {
            "turn": _parse_int(values[0], f"{member_name}:{line_number}: turn"),
            "time": _parse_int(values[1], f"{member_name}:{line_number}: time"),
            "nb_uncolored": _parse_int(
                values[2], f"{member_name}:{line_number}: nb_uncolored"
            ),
            "penalty": _parse_int(values[3], f"{member_name}:{line_number}: penalty"),
            "nb_colors": nb_colors,
            "solution_length": len(colors),
        }
        if (
            row["turn"] < 0
            or row["time"] < 0
            or row["nb_uncolored"] < 0
            or row["penalty"] < 0
            or row["nb_colors"] < 1
        ):
            raise ArchiveValidationError(f"{member_name}:{line_number}: negative field")
        if row["solution_length"] < 1:
            raise ArchiveValidationError(f"{member_name}:{line_number}: empty solution")
        if any(color < 0 or color >= nb_colors for color in colors):
            raise ArchiveValidationError(
                f"{member_name}:{line_number}: solution label is out of range"
            )
        if cutoff_seconds is None or row["time"] <= cutoff_seconds:
            rows.append(row)
    if not rows:
        raise ArchiveValidationError(f"{member_name}: no row survives the time profile")
    return {
        "member": member_name,
        "metadata": metadata,
        "final_row": rows[-1],
        "restart_lines": restart_lines,
    }


def _read_member(archive: tarfile.TarFile, member: tarfile.TarInfo) -> bytes:
    handle = archive.extractfile(member)
    if handle is None:
        raise ArchiveValidationError(f"cannot read archive member: {member.name}")
    return handle.read()


def _validate_open_instance(
    archive: tarfile.TarFile,
    members: list[tarfile.TarInfo],
    instance: str,
    profile: str,
    profiles: dict[str, Any],
    profile_config: dict[str, Any],
    targets: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    """Parse one member group while reusing an already indexed tar file."""

    expected_seeds = list(profiles["expected_seeds"])
    cutoff = profile_config["row_time_cutoff_seconds"]
    required_time_limit = profile_config["required_header_time_limit_seconds"]
    attempts: list[dict[str, Any]] = []
    for member in members:
        attempt = _parse_attempt(_read_member(archive, member), member.name, cutoff)
        metadata = attempt["metadata"]
        if metadata["instance"] != instance:
            raise ArchiveValidationError(
                f"{member.name}: path instance and metadata instance disagree"
            )
        if metadata["seed"] not in expected_seeds:
            raise ArchiveValidationError(f"{member.name}: seed is outside 0..19")
        filename = PurePosixPath(member.name).stem
        suffix_parts = filename[len(instance) + 1 :].split("_")
        if suffix_parts[0] != str(metadata["seed"]):
            raise ArchiveValidationError(
                f"{member.name}: filename seed and metadata seed disagree"
            )
        if len(suffix_parts) > 1 and suffix_parts[1] != str(metadata["target_colors"]):
            raise ArchiveValidationError(
                f"{member.name}: filename target and metadata target disagree"
            )
        if metadata["time_limit_seconds"] != required_time_limit:
            raise ArchiveValidationError(
                f"{member.name}: expected header time_limit={required_time_limit}"
            )
        attempts.append(attempt)

    retained: dict[int, dict[str, Any]] = {}
    for attempt in attempts:
        row = attempt["final_row"]
        if row["penalty"] == 0 and row["nb_uncolored"] == 0:
            seed = attempt["metadata"]["seed"]
            if row["nb_colors"] != attempt["metadata"]["target_colors"]:
                raise ArchiveValidationError(
                    f"{instance}: legal row color count differs from its target"
                )
            if seed in retained:
                raise ArchiveValidationError(
                    f"{instance}: duplicate legal retained result for seed {seed}"
                )
            retained[seed] = {
                "seed": seed,
                "nb_colors": row["nb_colors"],
                "time_seconds": row["time"],
                "turn": row["turn"],
                "solution_length": row["solution_length"],
                "target_colors": attempt["metadata"]["target_colors"],
                "member": attempt["member"],
            }

    retained_seeds = sorted(retained)
    missing_seeds = [seed for seed in expected_seeds if seed not in retained]
    if profile == "artifact_actual_10800" and retained_seeds != expected_seeds:
        raise ArchiveValidationError(
            f"{instance}: P1 retained seeds are not exactly 0..19; missing={missing_seeds}"
        )
    if not retained:
        raise ArchiveValidationError(f"{instance}: profile retains no legal results")

    per_seed = [retained[seed] for seed in retained_seeds]
    colors = [row["nb_colors"] for row in per_seed]
    best = min(colors)
    mean_colors = round(statistics.mean(colors), 1)
    best_times = [row["time_seconds"] for row in per_seed if row["nb_colors"] == best]
    exact_time = Fraction(sum(best_times), len(best_times))
    rounded_time = round(float(exact_time), 1)
    displayed_time = int(rounded_time)

    target = targets[instance]
    cells_match = {
        "best": best == target["published_best"],
        "mean": math.isclose(
            mean_colors, target["published_mean"], rel_tol=0.0, abs_tol=1e-12
        ),
        "displayed_mean_best_time": displayed_time
        == target["published_mean_best_time_seconds"],
    }
    result: dict[str, Any] = {
        "schema_version": "1.0.0",
        "profile": profile,
        "instance": instance,
        "attempt_files": len(attempts),
        "files_with_restart": sum(1 for attempt in attempts if attempt["restart_lines"]),
        "restart_lines": sum(attempt["restart_lines"] for attempt in attempts),
        "metadata_shifted_header_files": len(attempts),
        "retained_run_count": len(per_seed),
        "retained_seeds": retained_seeds,
        "missing_seeds": missing_seeds,
        "per_seed": per_seed,
        "calculated": {
            "best": best,
            "mean": mean_colors,
            "mean_best_time_exact": {
                "numerator": exact_time.numerator,
                "denominator": exact_time.denominator,
                "decimal": format(float(exact_time), ".12g"),
            },
            "mean_best_time_rounded_one_decimal": rounded_time,
            "displayed_mean_best_time_seconds": displayed_time,
        },
        "published": {
            "best": target["published_best"],
            "mean": target["published_mean"],
            "displayed_mean_best_time_seconds": target[
                "published_mean_best_time_seconds"
            ],
        },
        "published_cell_matches": cells_match
        if profile == "artifact_actual_10800"
        else "NOT_APPLICABLE_DIAGNOSTIC",
        "claim": profile_config["claim"],
    }
    result["canonical_digest"] = canonical_sha256(
        result, domain="EU26-02-INSTANCE-RESULT-V1"
    )
    return result


def validate_instance(
    archive_path: str | Path,
    instance: str,
    profile: str = "artifact_actual_10800",
) -> dict[str, Any]:
    """Validate and aggregate one instance from the pinned archive schema."""

    profiles, profile_config = _profile(profile)
    targets = _target_map()
    if instance not in targets:
        raise ArchiveValidationError(f"instance is not in the frozen Table 2 set: {instance}")
    path = Path(archive_path)
    with tarfile.open(path, "r:*") as archive:
        members = [
            member
            for member in _root_csv_members(archive)
            if PurePosixPath(member.name).name.startswith(f"{instance}_")
        ]
        if not members:
            raise ArchiveValidationError(f"archive has no files for {instance}")
        return _validate_open_instance(
            archive,
            members,
            instance,
            profile,
            profiles,
            profile_config,
            targets,
        )


def _verify_instance_result(
    row: dict[str, Any],
    profile: str,
    profiles: dict[str, Any],
    profile_config: dict[str, Any],
    target: dict[str, Any],
) -> None:
    """Recompute an exported instance result before accepting aggregation."""

    if not isinstance(row, dict) or row.get("schema_version") != "1.0.0":
        raise ArchiveValidationError("instance result has an unsupported schema")
    if row.get("profile") != profile or row.get("claim") != profile_config["claim"]:
        raise ArchiveValidationError("instance result profile/claim mismatch")
    supplied_digest = row.get("canonical_digest")
    unsigned = dict(row)
    unsigned.pop("canonical_digest", None)
    if not _is_sha256(supplied_digest) or supplied_digest != canonical_sha256(
        unsigned, domain="EU26-02-INSTANCE-RESULT-V1"
    ):
        raise ArchiveValidationError("instance result canonical digest mismatch")

    per_seed = row.get("per_seed")
    if not isinstance(per_seed, list) or not per_seed:
        raise ArchiveValidationError("instance result has no retained per-seed rows")
    parsed: list[dict[str, int]] = []
    for index, value in enumerate(per_seed):
        if not isinstance(value, dict):
            raise ArchiveValidationError("per-seed result must be an object")
        required_ints = (
            "seed",
            "nb_colors",
            "time_seconds",
            "turn",
            "solution_length",
            "target_colors",
        )
        values: dict[str, int] = {}
        for name in required_ints:
            raw = value.get(name)
            if isinstance(raw, bool) or not isinstance(raw, int):
                raise ArchiveValidationError(
                    f"per-seed result {index} field {name} must be an integer"
                )
            values[name] = raw
        if (
            values["seed"] not in profiles["expected_seeds"]
            or values["nb_colors"] < 1
            or values["time_seconds"] < 0
            or values["turn"] < 0
            or values["solution_length"] < 1
            or values["target_colors"] != values["nb_colors"]
            or not isinstance(value.get("member"), str)
            or not value["member"]
        ):
            raise ArchiveValidationError("per-seed result contains an invalid value")
        parsed.append(values)

    seeds = [value["seed"] for value in parsed]
    if seeds != sorted(seeds) or len(seeds) != len(set(seeds)):
        raise ArchiveValidationError("retained per-seed rows must be unique and sorted")
    expected_seeds = list(profiles["expected_seeds"])
    missing = [seed for seed in expected_seeds if seed not in seeds]
    if profile == "artifact_actual_10800" and seeds != expected_seeds:
        raise ArchiveValidationError("P1 instance result must retain seeds 0..19")
    if (
        row.get("retained_seeds") != seeds
        or row.get("missing_seeds") != missing
        or row.get("retained_run_count") != len(parsed)
    ):
        raise ArchiveValidationError("instance retained-seed accounting mismatch")

    colors = [value["nb_colors"] for value in parsed]
    best = min(colors)
    mean_colors = round(statistics.mean(colors), 1)
    best_times = [
        value["time_seconds"] for value in parsed if value["nb_colors"] == best
    ]
    exact_time = Fraction(sum(best_times), len(best_times))
    rounded_time = round(float(exact_time), 1)
    expected_calculated = {
        "best": best,
        "mean": mean_colors,
        "mean_best_time_exact": {
            "numerator": exact_time.numerator,
            "denominator": exact_time.denominator,
            "decimal": format(float(exact_time), ".12g"),
        },
        "mean_best_time_rounded_one_decimal": rounded_time,
        "displayed_mean_best_time_seconds": int(rounded_time),
    }
    expected_published = {
        "best": target["published_best"],
        "mean": target["published_mean"],
        "displayed_mean_best_time_seconds": target[
            "published_mean_best_time_seconds"
        ],
    }
    expected_matches = {
        "best": best == target["published_best"],
        "mean": math.isclose(
            mean_colors, target["published_mean"], rel_tol=0.0, abs_tol=1e-12
        ),
        "displayed_mean_best_time": int(rounded_time)
        == target["published_mean_best_time_seconds"],
    }
    if row.get("calculated") != expected_calculated:
        raise ArchiveValidationError("instance calculated statistics mismatch")
    if row.get("published") != expected_published:
        raise ArchiveValidationError("instance published target mismatch")
    expected_cell_field: dict[str, bool] | str = (
        expected_matches
        if profile == "artifact_actual_10800"
        else "NOT_APPLICABLE_DIAGNOSTIC"
    )
    if row.get("published_cell_matches") != expected_cell_field:
        raise ArchiveValidationError("instance published-cell comparison mismatch")

    accounting_names = (
        "attempt_files",
        "files_with_restart",
        "restart_lines",
        "metadata_shifted_header_files",
    )
    if any(
        isinstance(row.get(name), bool)
        or not isinstance(row.get(name), int)
        or row[name] < 0
        for name in accounting_names
    ):
        raise ArchiveValidationError("instance file/restart accounting is invalid")
    if (
        row["attempt_files"] < row["retained_run_count"]
        or row["metadata_shifted_header_files"] != row["attempt_files"]
        or row["files_with_restart"] > row["attempt_files"]
        or row["restart_lines"] < row["files_with_restart"]
    ):
        raise ArchiveValidationError("instance file/restart accounting mismatch")


def aggregate_results(
    rows: Iterable[dict[str, Any]],
    profile: str = "artifact_actual_10800",
) -> dict[str, Any]:
    """Combine independently parsed instance results in frozen table order."""

    profiles, profile_config = _profile(profile)
    targets = _target_map()
    target_order = list(targets)
    by_instance: dict[str, dict[str, Any]] = {}
    for row in rows:
        if row.get("profile") != profile:
            raise ArchiveValidationError("cannot combine results from different profiles")
        instance = row.get("instance")
        if instance in by_instance:
            raise ArchiveValidationError(f"duplicate instance result: {instance}")
        if instance not in target_order:
            raise ArchiveValidationError(f"unexpected instance result: {instance}")
        _verify_instance_result(
            row, profile, profiles, profile_config, targets[instance]
        )
        by_instance[instance] = row
    ordered = [by_instance[name] for name in target_order if name in by_instance]
    missing = [name for name in target_order if name not in by_instance]
    complete = not missing and len(ordered) == 31
    if profile == "artifact_actual_10800":
        all_cells_match = complete and all(
            all(row["published_cell_matches"].values()) for row in ordered
        )
        status = (
            "PASS_AGGREGATE_EXACT" if all_cells_match else "FAIL_ARCHIVE_REPLAY"
        )
    else:
        all_cells_match = None
        status = "DIAGNOSTIC_ONLY"

    result = {
        "schema_version": "1.0.0",
        "profile": profile,
        "claim": profile_config["claim"],
        "status": status,
        "complete_31_instance_set": complete,
        "missing_instances": missing,
        "all_published_cells_match": all_cells_match,
        "instance_results": ordered,
        "total_attempt_files": sum(row["attempt_files"] for row in ordered),
        "total_retained_runs": sum(row["retained_run_count"] for row in ordered),
        "files_with_restart": sum(row["files_with_restart"] for row in ordered),
        "restart_lines": sum(row["restart_lines"] for row in ordered),
    }
    result["canonical_result_digest"] = canonical_sha256(
        ordered, domain="EU26-02-ALL-INSTANCES-V1"
    )
    return result


def validate_archive(
    archive_path: str | Path,
    profile: str = "artifact_actual_10800",
    instances: list[str] | None = None,
) -> dict[str, Any]:
    """Hash, parse and validate a complete or explicitly selected archive set."""

    profiles, profile_config = _profile(profile)
    path = Path(archive_path).resolve()
    if not path.is_file():
        raise ArchiveValidationError(f"archive does not exist: {path}")
    actual_sha256 = _sha256_file(path)
    if actual_sha256 != profiles["archive_sha256"]:
        raise ArchiveValidationError(
            f"archive SHA-256 mismatch: {actual_sha256} != {profiles['archive_sha256']}"
        )
    targets = _target_map()
    available = list(targets)
    selected = available if instances is None else list(instances)
    if len(selected) != len(set(selected)) or any(name not in available for name in selected):
        raise ArchiveValidationError("instances must be a unique subset of the frozen set")
    with tempfile.TemporaryDirectory(prefix="eu26-02-archive-") as directory:
        parse_path = Path(directory) / "deleter.tar"
        try:
            with gzip.open(path, "rb") as source, parse_path.open("wb") as target:
                shutil.copyfileobj(source, target, length=1024 * 1024)
        except (OSError, EOFError) as error:
            raise ArchiveValidationError(
                "cannot materialize the authenticated gzip archive"
            ) from error
        parse_sha256 = _sha256_file(parse_path)
        with tarfile.open(parse_path, "r:") as archive:
            groups = _group_members(_root_csv_members(archive), available)
            rows = [
                _validate_open_instance(
                    archive,
                    groups[name],
                    name,
                    profile,
                    profiles,
                    profile_config,
                    targets,
                )
                for name in selected
            ]
    result = aggregate_results(rows, profile)
    aggregate_status = result["status"]
    if profile == "artifact_actual_10800":
        result["aggregate_status"] = aggregate_status
        result["status"] = (
            "PASS_ARCHIVE_EXACT"
            if aggregate_status == "PASS_AGGREGATE_EXACT"
            else "FAIL_ARCHIVE_REPLAY"
        )
    result.update(
        {
            "archive_source_id": "outputs/gcp_hard_ahead_1h_deleter.tgz",
            "archive_bytes": path.stat().st_size,
            "archive_sha256": actual_sha256,
            "temporary_uncompressed_tar_sha256": parse_sha256,
        }
    )
    return result
