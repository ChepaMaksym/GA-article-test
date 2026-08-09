"""Strict point-set parsing and an independent L2-star implementation."""

from __future__ import annotations

import math
import pickletools
import re
import struct
from dataclasses import dataclass
from typing import Iterable, Sequence


class ArtifactError(ValueError):
    """Raised when an artifact violates the frozen contract."""


@dataclass(frozen=True)
class PointSet:
    source_pool_size: int
    rows: int
    dimension: int
    construction_discrepancy: float
    construction_runtime: float
    points: tuple[tuple[float, ...], ...]


_HEADER = re.compile(
    r"n=(?P<n>[1-9][0-9]*),k=(?P<k>[1-9][0-9]*),dim=(?P<dim>[1-9][0-9]*), "
    r"discrepancy=(?P<discrepancy>[0-9]+\.[0-9]{6}), "
    r"runtime=(?P<runtime>[0-9]+\.[0-9]{6})"
)
_COORDINATE = re.compile(r"(?:0|1)\.[0-9]{6}")


def parse_point_set(
    payload: bytes,
    *,
    expected_header: str,
    expected_rows: int,
    expected_dimension: int,
) -> PointSet:
    """Parse the exact author text format and reject normalization drift."""

    if expected_rows < 1 or expected_dimension < 1:
        raise ArtifactError("expected shape must be positive")
    if not payload.endswith(b"\n"):
        raise ArtifactError("point-set member must end with LF")
    if b"\r" in payload or b"\t" in payload or b"\x00" in payload:
        raise ArtifactError("point-set member contains a forbidden control byte")
    try:
        text = payload.decode("ascii", errors="strict")
    except UnicodeDecodeError as error:
        raise ArtifactError("point-set member is not strict ASCII") from error

    lines = text.splitlines()
    if not lines or lines[0] != expected_header:
        raise ArtifactError("point-set header differs from the frozen header")
    header_match = _HEADER.fullmatch(lines[0])
    if header_match is None:
        raise ArtifactError("point-set header violates the frozen grammar")
    if len(lines) != expected_rows + 1:
        raise ArtifactError(
            f"expected {expected_rows} point rows, observed {len(lines) - 1}"
        )

    rows: list[tuple[float, ...]] = []
    for line_number, line in enumerate(lines[1:], start=2):
        tokens = line.split(" ")
        if not tokens or tokens[-1] != "":
            raise ArtifactError(f"line {line_number} lacks the frozen trailing space")
        tokens = tokens[:-1]
        if len(tokens) != expected_dimension:
            raise ArtifactError(
                f"line {line_number} has {len(tokens)} coordinates, "
                f"expected {expected_dimension}"
            )
        if any(_COORDINATE.fullmatch(token) is None for token in tokens):
            raise ArtifactError(
                f"line {line_number} contains a noncanonical coordinate"
            )
        values = tuple(float(token) for token in tokens)
        if any(not math.isfinite(value) or not 0.0 <= value <= 1.0 for value in values):
            raise ArtifactError(f"line {line_number} contains an out-of-range value")
        rows.append(values)

    header_values = header_match.groupdict()
    if int(header_values["k"]) != expected_rows:
        raise ArtifactError("header k does not equal the expected row count")
    if int(header_values["dim"]) != expected_dimension:
        raise ArtifactError("header dim does not equal the expected dimension")
    return PointSet(
        source_pool_size=int(header_values["n"]),
        rows=int(header_values["k"]),
        dimension=int(header_values["dim"]),
        construction_discrepancy=float(header_values["discrepancy"]),
        construction_runtime=float(header_values["runtime"]),
        points=tuple(rows),
    )


def _validated_points(
    points: Iterable[Sequence[float]],
) -> tuple[tuple[float, ...], ...]:
    result = tuple(tuple(float(value) for value in row) for row in points)
    if not result or not result[0]:
        raise ArtifactError("point set must be nonempty")
    dimension = len(result[0])
    if any(len(row) != dimension for row in result):
        raise ArtifactError("point set is not rectangular")
    if any(
        not math.isfinite(value) or not 0.0 <= value <= 1.0
        for row in result
        for value in row
    ):
        raise ArtifactError("point coordinates must be finite and in [0, 1]")
    return result


def l2_star_discrepancy(points: Iterable[Sequence[float]]) -> float:
    """Evaluate the defining L2-star equation without SciPy or artifact code."""

    rows = _validated_points(points)
    count = len(rows)
    dimension = len(rows[0])
    first = math.pow(3.0, -dimension)
    second = (math.pow(2.0, 1 - dimension) / count) * math.fsum(
        math.prod(1.0 - value * value for value in row) for row in rows
    )
    third = (1.0 / (count * count)) * math.fsum(
        math.prod(
            1.0 - max(rows[left][axis], rows[right][axis])
            for axis in range(dimension)
        )
        for left in range(count)
        for right in range(count)
    )
    squared = first - second + third
    if not math.isfinite(squared) or squared <= 0.0:
        raise ArtifactError(f"L2-star squared is not finite and positive: {squared}")
    return math.sqrt(squared)


def extract_numeric_table(
    payload: bytes,
    *,
    dimensions: Sequence[int],
    algorithms: Sequence[str],
    expected_block_bytes: int,
) -> dict[tuple[str, int], float]:
    """Extract one inert little-endian binary64 block without unpickling."""

    if len(set(dimensions)) != len(dimensions) or len(set(algorithms)) != len(algorithms):
        raise ArtifactError("numeric table labels must be unique")
    expected_values = len(dimensions) * len(algorithms)
    if expected_block_bytes != expected_values * 8:
        raise ArtifactError("numeric block size does not match the label matrix")
    try:
        blocks = [
            bytes(argument)
            for opcode, argument, _ in pickletools.genops(payload)
            if opcode.name == "BYTEARRAY8"
        ]
    except Exception as error:
        raise ArtifactError("numeric artifact is not a parseable pickle stream") from error
    if len(blocks) != 1:
        raise ArtifactError(f"expected one inert numeric block, observed {len(blocks)}")
    block = blocks[0]
    if len(block) != expected_block_bytes:
        raise ArtifactError(
            f"numeric block has {len(block)} bytes, expected {expected_block_bytes}"
        )
    values = struct.unpack(f"<{expected_values}d", block)
    if any(not math.isfinite(value) or value <= 0.0 for value in values):
        raise ArtifactError("numeric block contains a non-finite or nonpositive value")

    table: dict[tuple[str, int], float] = {}
    width = len(algorithms)
    for dimension_index, dimension in enumerate(dimensions):
        for algorithm_index, algorithm in enumerate(algorithms):
            table[(algorithm, dimension)] = values[
                dimension_index * width + algorithm_index
            ]
    return table
