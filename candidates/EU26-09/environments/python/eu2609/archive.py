"""Fail-closed parser for the non-vendored EU26-09 raw result artifact."""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Mapping

from .controls import round_ties_to_even_positive


class ArtifactError(ValueError):
    """Raised when a raw result violates the frozen grammar or endpoint."""


SEPARATOR = "------------------------------------------------------------------"
METADATA_LINES = (
    "Experiment configurations",
    "Seed: 885480221",
    "Problem: OneMax",
    "Size: 100\tk: 1\tExtra: None",
    "Runs: 500",
    "Stop criteria: solved",
    "Max generations (if aplicable): 1000",
    "Max evaluations (if aplicable): 10000",
    "Algorithm: JA.OnePlusLambdaCommaLambdaSAReset",
    "Initial mutation probability: 0.01",
    "Initial offspring population size: 100",
    "Initial crossover probability(if aplicable): 1.0",
    "Mutation updatefactor (if aplicable): 2",
    "Offspring population size update factor (if aplicable): 1.5",
    "Success ratio (if aplicable): 1",
)
CANONICAL_INT = r"(?:0|[1-9][0-9]*)"
CANONICAL_DECIMAL = r"(?:0|[1-9][0-9]*)\.[0-9]+"
RUN_PATTERN = re.compile(
    rf"Final results: Run: (?P<run>{CANONICAL_INT}) +"
    rf"Gens: (?P<generations>{CANONICAL_INT}) +"
    rf"Evals: (?P<evaluations>{CANONICAL_INT}) +"
    rf"λ: (?P<lambda>{CANONICAL_INT}) p: (?P<p>{CANONICAL_DECIMAL}) "
    rf"Solved: (?P<solved>True|False)"
)
FOOTER_PATTERN = re.compile(
    rf"(?P<label>Average generations to solve|Average evaluations to solve|"
    rf"Average fitness|Average lambda):(?P<value>{CANONICAL_DECIMAL})"
)


@dataclass(frozen=True)
class RunRecord:
    run_id: int
    generations: int
    evaluations: int
    final_lambda: int
    mutation_probability_text: str
    mutation_probability: float
    solved: bool

    def comparison_tuple(self) -> tuple[int, int, int, int, str, bool]:
        return (
            self.run_id,
            self.generations,
            self.evaluations,
            self.final_lambda,
            self.mutation_probability_text,
            self.solved,
        )


@dataclass(frozen=True)
class ArtifactResult:
    runs: tuple[RunRecord, ...]
    totals: Mapping[str, int]
    means: Mapping[str, str]
    footer_values: Mapping[str, str]
    bytes_count: int
    lf_count: int


def _canonical_int(token: str, *, field: str) -> int:
    try:
        value = int(token)
    except ValueError as error:
        raise ArtifactError(f"{field} is not an integer: {token!r}") from error
    if str(value) != token:
        raise ArtifactError(f"{field} is not canonical decimal: {token!r}")
    return value


def _exact_mean(total: int, runs: int) -> Decimal:
    return Decimal(total) / Decimal(runs)


def _format_mean(value: Decimal, *, places: int) -> str:
    return format(value, f".{places}f")


def parse_artifact(
    payload: bytes,
    contract: Mapping[str, Any],
    *,
    require_frozen_container: bool = True,
    require_frozen_endpoint: bool = True,
) -> ArtifactResult:
    """Parse a frozen artifact or a structurally equivalent replay output."""

    raw_contract = contract["raw_member"]
    endpoint = contract["endpoint"]
    if not isinstance(payload, bytes):
        raise ArtifactError("artifact payload must be bytes")
    if require_frozen_container:
        if len(payload) != raw_contract["bytes"]:
            raise ArtifactError(
                f"artifact byte count differs: {len(payload)} != {raw_contract['bytes']}"
            )
        if payload.count(b"\n") != raw_contract["lf_count"]:
            raise ArtifactError("artifact LF count differs from the frozen member")
        if payload.endswith(b"\n") is not raw_contract["terminal_lf"]:
            raise ArtifactError("artifact terminal-LF policy differs")
    if b"\r" in payload or b"\x00" in payload:
        raise ArtifactError("artifact contains a CR or NUL byte")
    try:
        text = payload.decode("utf-8", errors="strict")
    except UnicodeDecodeError as error:
        raise ArtifactError("artifact is not strict UTF-8") from error

    lines = text.splitlines()
    expected_runs = endpoint["runs"]
    expected_line_count = len(METADATA_LINES) + 1 + 1 + expected_runs + 1 + 1 + 4
    if len(lines) != expected_line_count:
        raise ArtifactError(
            f"expected {expected_line_count} logical lines, observed {len(lines)}"
        )
    if tuple(lines[: len(METADATA_LINES)]) != METADATA_LINES:
        raise ArtifactError("metadata lines differ from the frozen configuration")
    position = len(METADATA_LINES)
    if lines[position] != "" or lines[position + 1] != SEPARATOR:
        raise ArtifactError("opening blank line or separator differs")
    position += 2

    records: list[RunRecord] = []
    dimension = endpoint["dimension"]
    for expected_run_id in range(1, expected_runs + 1):
        line_number = position + 1
        match = RUN_PATTERN.fullmatch(lines[position])
        if match is None:
            raise ArtifactError(f"run line {line_number} violates the exact grammar")
        run_id = _canonical_int(match.group("run"), field=f"line {line_number} run")
        generations = _canonical_int(
            match.group("generations"), field=f"line {line_number} generations"
        )
        evaluations = _canonical_int(
            match.group("evaluations"), field=f"line {line_number} evaluations"
        )
        final_lambda = _canonical_int(
            match.group("lambda"), field=f"line {line_number} lambda"
        )
        probability_text = match.group("p")
        probability = float(probability_text)
        solved = match.group("solved") == "True"
        if run_id != expected_run_id:
            raise ArtifactError(
                f"run IDs are not contiguous: expected {expected_run_id}, observed {run_id}"
            )
        if not 1 <= generations <= 1000:
            raise ArtifactError(f"run {run_id} generations outside 1..1000")
        if not 2 <= evaluations <= 10000 or evaluations % 2:
            raise ArtifactError(f"run {run_id} evaluations invalid or not even")
        if evaluations < 2 * generations:
            raise ArtifactError(f"run {run_id} violates the minimum source accounting")
        if not 1 <= final_lambda <= dimension:
            raise ArtifactError(f"run {run_id} final lambda outside 1..n")
        if not math.isfinite(probability) or not 0.0 < probability <= 1.0:
            raise ArtifactError(f"run {run_id} mutation probability outside (0, 1]")
        if round_ties_to_even_positive(probability * dimension) != final_lambda:
            raise ArtifactError(
                f"run {run_id} logged lambda is inconsistent with logged p"
            )
        if not solved:
            raise ArtifactError(f"run {run_id} is not solved")
        records.append(
            RunRecord(
                run_id=run_id,
                generations=generations,
                evaluations=evaluations,
                final_lambda=final_lambda,
                mutation_probability_text=probability_text,
                mutation_probability=probability,
                solved=solved,
            )
        )
        position += 1

    if lines[position] != "" or lines[position + 1] != SEPARATOR:
        raise ArtifactError("closing blank line or separator differs")
    position += 2
    footer_values: dict[str, str] = {}
    for line in lines[position:]:
        match = FOOTER_PATTERN.fullmatch(line)
        if match is None:
            raise ArtifactError(f"footer line violates the exact grammar: {line!r}")
        label = match.group("label")
        if label in footer_values:
            raise ArtifactError(f"duplicate footer label: {label}")
        footer_values[label] = match.group("value")
    expected_labels = (
        "Average generations to solve",
        "Average evaluations to solve",
        "Average fitness",
        "Average lambda",
    )
    if tuple(footer_values) != expected_labels:
        raise ArtifactError("footer labels or order differ")

    totals = {
        "generations": sum(record.generations for record in records),
        "evaluations": sum(record.evaluations for record in records),
        "fitness": dimension * expected_runs,
        "final_logged_lambda": sum(record.final_lambda for record in records),
    }
    means = {
        "generations": _format_mean(_exact_mean(totals["generations"], expected_runs), places=3),
        "evaluations": _format_mean(_exact_mean(totals["evaluations"], expected_runs), places=3),
        "fitness": _format_mean(_exact_mean(totals["fitness"], expected_runs), places=1),
        "final_logged_lambda": _format_mean(
            _exact_mean(totals["final_logged_lambda"], expected_runs), places=3
        ),
    }
    expected_footers = {
        "Average generations to solve": means["generations"],
        "Average evaluations to solve": means["evaluations"],
        "Average fitness": means["fitness"],
        "Average lambda": means["final_logged_lambda"],
    }
    if footer_values != expected_footers:
        raise ArtifactError(
            f"footer means do not equal recomputed exact means: {footer_values!r}"
        )
    if require_frozen_endpoint:
        if totals != endpoint["raw_totals"]:
            raise ArtifactError(f"artifact totals differ from frozen endpoint: {totals!r}")
        if means != endpoint["raw_means"]:
            raise ArtifactError(f"artifact means differ from frozen endpoint: {means!r}")
    return ArtifactResult(
        runs=tuple(records),
        totals=totals,
        means=means,
        footer_values=footer_values,
        bytes_count=len(payload),
        lf_count=payload.count(b"\n"),
    )


def first_run_difference(
    reference: ArtifactResult, replay: ArtifactResult
) -> Mapping[str, Any] | None:
    """Return a bounded first mismatch without copying upstream run data."""

    if len(reference.runs) != len(replay.runs):
        return {"field": "run_count", "reference": len(reference.runs), "replay": len(replay.runs)}
    fields = (
        "run_id",
        "generations",
        "evaluations",
        "final_lambda",
        "mutation_probability_text",
        "solved",
    )
    for reference_run, replay_run in zip(reference.runs, replay.runs):
        left = reference_run.comparison_tuple()
        right = replay_run.comparison_tuple()
        if left != right:
            for field, reference_value, replay_value in zip(fields, left, right):
                if reference_value != replay_value:
                    return {
                        "run_id": reference_run.run_id,
                        "field": field,
                        "reference": reference_value,
                        "replay": replay_value,
                    }
    if reference.footer_values != replay.footer_values:
        return {"field": "footer_values", "reference": dict(reference.footer_values), "replay": dict(replay.footer_values)}
    return None
