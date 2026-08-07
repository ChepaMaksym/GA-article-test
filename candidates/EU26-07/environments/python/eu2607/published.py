"""Authenticated parsing of the EU26-07 author result artifacts."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import math
from pathlib import Path
import re
import statistics
from typing import Any, Iterable


RAW_RELATIVE_PATH = Path(
    "Raw/results_20-09-28_08:20:44_Jump_n20_"
    "JA.OnePlusLambdaCommaLambdaSAResetJUMP_λ20.txt"
)
PROCESSED_RELATIVE_PATH = Path(
    "processed-results/SA (1+(λ,λ)) GA Reset_"
    "Jump_n20_k4_λ20_p1:20_c1_F1.5_extra-None"
)
RAW_SHA256 = "b2ac8c81efaf786823d49dcef26eeb20f0257ca7fe9e1e2394d02ca5e26dd9a6"
RAW_BYTES = 48_505
PROCESSED_SHA256 = (
    "2dc530fa995c6980fd064f422b97e15db967aaee2ed5625be43b4fc5e10e21ab"
)
PROCESSED_BYTES = 48_980
BASE_SEED = 816_114_841
EXPECTED_RUNS = 500


class PublishedDataError(ValueError):
    """Raised when an author artifact is missing, altered, or malformed."""


@dataclass(frozen=True)
class PublishedRow:
    run: int
    effective_seed: int
    generations: int
    evaluations: int
    final_lambda: int
    last_mutation_probability: float
    solved: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class PublishedSummary:
    runs: int
    mean_evaluations: float
    median_evaluations: float
    q1_evaluations: float
    q3_evaluations: float
    population_sd_evaluations: float
    sample_sd_evaluations: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


_ROW = re.compile(
    r"^Final results:\s*Run:\s*(?P<run>\d+)\s+"
    r"Gens:\s*(?P<generations>\d+)\s+"
    r"Evals:\s*(?P<evaluations>\d+)\s+"
    r"λ:\s*(?P<lambda>\d+)\s+"
    r"p:\s*(?P<probability>\S+)\s+"
    r"Solved:\s*(?P<solved>True|False)\s*$"
)


def _authenticated_bytes(path: Path, expected_size: int, expected_hash: str) -> bytes:
    try:
        payload = path.read_bytes()
    except OSError as exc:
        raise PublishedDataError(f"cannot read required artifact: {path}") from exc
    if len(payload) != expected_size:
        raise PublishedDataError(
            f"byte-count mismatch for {path}: {len(payload)} != {expected_size}"
        )
    digest = hashlib.sha256(payload).hexdigest()
    if digest != expected_hash:
        raise PublishedDataError(
            f"SHA-256 mismatch for {path}: {digest} != {expected_hash}"
        )
    return payload


def parse_raw_rows(repository: Path) -> list[PublishedRow]:
    """Authenticate and parse the ordered 500-row author ledger."""

    root = Path(repository).resolve()
    raw_path = root / RAW_RELATIVE_PATH
    payload = _authenticated_bytes(raw_path, RAW_BYTES, RAW_SHA256)
    try:
        text = payload.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise PublishedDataError("raw artifact is not valid UTF-8") from exc

    rows: list[PublishedRow] = []
    for line in text.splitlines():
        if not line.startswith("Final results:"):
            continue
        match = _ROW.fullmatch(line)
        if match is None:
            raise PublishedDataError(f"malformed raw result row: {line!r}")
        run = int(match.group("run"))
        rows.append(
            PublishedRow(
                run=run,
                effective_seed=BASE_SEED + run,
                generations=int(match.group("generations")),
                evaluations=int(match.group("evaluations")),
                final_lambda=int(match.group("lambda")),
                last_mutation_probability=float(match.group("probability")),
                solved=match.group("solved") == "True",
            )
        )

    if len(rows) != EXPECTED_RUNS:
        raise PublishedDataError(
            f"expected {EXPECTED_RUNS} raw rows, found {len(rows)}"
        )
    observed_runs = [row.run for row in rows]
    expected_runs = list(range(1, EXPECTED_RUNS + 1))
    if observed_runs != expected_runs:
        raise PublishedDataError("raw run numbers are not the ordered range 1..500")
    if not all(row.solved for row in rows):
        raise PublishedDataError("raw ledger contains an unsolved run")
    return rows


def _linear_quantile(values: list[int], probability: float) -> float:
    if not values:
        raise PublishedDataError("cannot summarize an empty ledger")
    ordered = sorted(values)
    position = (len(ordered) - 1) * probability
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return float(ordered[lower])
    fraction = position - lower
    return float(ordered[lower] + fraction * (ordered[upper] - ordered[lower]))


def summarize_rows(rows: Iterable[PublishedRow]) -> PublishedSummary:
    materialized = list(rows)
    values = [row.evaluations for row in materialized]
    if len(values) < 2:
        raise PublishedDataError("at least two rows are required for both SD diagnostics")
    return PublishedSummary(
        runs=len(values),
        mean_evaluations=float(statistics.fmean(values)),
        median_evaluations=float(statistics.median(values)),
        q1_evaluations=_linear_quantile(values, 0.25),
        q3_evaluations=_linear_quantile(values, 0.75),
        population_sd_evaluations=float(statistics.pstdev(values)),
        sample_sd_evaluations=float(statistics.stdev(values)),
    )


def parse_processed_targets(repository: Path) -> dict[str, float | int]:
    """Authenticate the processed file and read its five declared scalars."""

    root = Path(repository).resolve()
    path = root / PROCESSED_RELATIVE_PATH
    payload = _authenticated_bytes(path, PROCESSED_BYTES, PROCESSED_SHA256)
    text = payload.decode("utf-8")
    patterns: dict[str, tuple[str, type[int] | type[float]]] = {
        "runs": (r"^Number of runs:\s*(\d+)\s*$", int),
        "mean_evaluations": (r"^Average evaluations:\s*([0-9.]+)\s*$", float),
        "median_evaluations": (r"^Median evaluations:\s*([0-9.]+)\s*$", float),
        "q1_evaluations": (r"^25% quantile:\s*([0-9.]+)\s*$", float),
        "q3_evaluations": (r"^75% quantile:\s*([0-9.]+)\s*$", float),
    }
    result: dict[str, float | int] = {}
    for key, (pattern, converter) in patterns.items():
        matches = re.findall(pattern, text, flags=re.MULTILINE)
        if len(matches) != 1:
            raise PublishedDataError(
                f"processed artifact must contain exactly one {key}, found {len(matches)}"
            )
        result[key] = converter(matches[0])
    return result


def canonical_rows_sha256(rows: Iterable[PublishedRow]) -> str:
    """Return a stable digest without copying the upstream ledger into this repo."""

    lines = []
    for row in rows:
        lines.append(
            "\t".join(
                (
                    str(row.run),
                    str(row.effective_seed),
                    str(row.generations),
                    str(row.evaluations),
                    str(row.final_lambda),
                    repr(row.last_mutation_probability),
                    str(row.solved),
                )
            )
        )
    return hashlib.sha256(("\n".join(lines) + "\n").encode("utf-8")).hexdigest()
