"""Independent legal-solution and turn-30 checks for the frozen r250.5 witness."""

from __future__ import annotations

import csv
import hashlib
import io
import json
import math
import tarfile
from pathlib import Path, PurePosixPath
from typing import Any

from .canonical import canonical_sha256


class WitnessValidationError(ValueError):
    """Raised when the selected source/archive witness differs from its contract."""


ARCHIVE_SHA256 = "1b7e8cf1ef637005bd994104f6e1ee520256ed387994b126bbe875a137632e41"
GRAPH_SHA256 = "1589cfc27c761c6014e3e6ff108270b49392ea300e9395015e28d535def57b39"
MAIN_MEMBER = "gcp_hard_ahead_1h_deleter/deleter/r250.5_15.csv"
MAIN_SHA256 = "8baa38bc27940fcbb7e470b2cfb13cc46a7de7950552c11dfa565323f412e787"
TBT_MEMBER = "gcp_hard_ahead_1h_deleter/deleter/tbt/r250.5_15.csv"
TBT_SHA256 = "8119fe034a1f8c8a9dbc99542ebd829c66a1e6e7178a1894c3987c52532da16b"
OPERATOR_NAMES = [
    "gpx_50_TabuColOptimized",
    "gpx_50_PartialCol",
    "gpx_75_TabuColOptimized",
    "gpx_75_PartialCol",
    "gpx_90_TabuColOptimized",
    "gpx_90_PartialCol",
]
EXPECTED_PRE_COUNTS = [15, 9, 10, 10, 11, 5]
EXPECTED_PRE_SUMS = [31, 26, 24, 19, 28, 11]
EXPECTED_SELECTED = [0, 5]
EXPECTED_SCORES = [2, 2]
EXPECTED_POST_COUNTS = [16, 9, 10, 10, 11, 6]
EXPECTED_POST_SUMS = [33, 26, 24, 19, 28, 13]


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while block := handle.read(1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


def parse_dimacs_graph(path: str | Path) -> dict[str, Any]:
    """Parse one strict undirected DIMACS ``p edge`` graph."""

    graph_path = Path(path)
    if _sha256_file(graph_path) != GRAPH_SHA256:
        raise WitnessValidationError("selected graph SHA-256 mismatch")
    vertices: int | None = None
    declared_edges: int | None = None
    edges: list[tuple[int, int]] = []
    seen: set[tuple[int, int]] = set()
    for line_number, raw in enumerate(
        graph_path.read_text(encoding="utf-8").splitlines(), 1
    ):
        line = raw.strip()
        if not line or line.startswith("c"):
            continue
        fields = line.split()
        if fields[:2] == ["p", "edge"] and len(fields) == 4:
            if vertices is not None:
                raise WitnessValidationError("DIMACS graph has multiple p lines")
            try:
                vertices, declared_edges = int(fields[2]), int(fields[3])
            except ValueError as error:
                raise WitnessValidationError("invalid DIMACS p line") from error
            if vertices < 1 or declared_edges < 0:
                raise WitnessValidationError("invalid DIMACS dimensions")
            continue
        if fields[:1] == ["e"] and len(fields) == 3:
            if vertices is None:
                raise WitnessValidationError("DIMACS edge precedes p line")
            try:
                left, right = int(fields[1]), int(fields[2])
            except ValueError as error:
                raise WitnessValidationError(
                    f"invalid DIMACS edge at line {line_number}"
                ) from error
            if left == right or not (1 <= left <= vertices and 1 <= right <= vertices):
                raise WitnessValidationError(
                    f"invalid DIMACS edge at line {line_number}"
                )
            edge = tuple(sorted((left - 1, right - 1)))
            if edge in seen:
                raise WitnessValidationError("duplicate DIMACS edge")
            seen.add(edge)
            edges.append(edge)
            continue
        raise WitnessValidationError(f"unrecognized DIMACS line {line_number}")
    if vertices != 235 or declared_edges != 13968 or len(edges) != declared_edges:
        raise WitnessValidationError("selected graph dimensions differ from p edge 235 13968")
    return {
        "vertices": vertices,
        "edges": edges,
        "declared_edges": declared_edges,
        "sha256": GRAPH_SHA256,
    }


def validate_coloring(
    colors: list[int], graph: dict[str, Any], declared_colors: int
) -> dict[str, Any]:
    """Check range, length and every graph edge independently."""

    if len(colors) != graph["vertices"]:
        raise WitnessValidationError("solution length differs from graph vertices")
    if declared_colors < 1 or any(
        isinstance(color, bool)
        or not isinstance(color, int)
        or color < 0
        or color >= declared_colors
        for color in colors
    ):
        raise WitnessValidationError("solution has an out-of-range color")
    conflicts = sum(1 for left, right in graph["edges"] if colors[left] == colors[right])
    return {
        "solution_length": len(colors),
        "declared_colors": declared_colors,
        "used_colors": len(set(colors)),
        "edge_count_checked": len(graph["edges"]),
        "conflicts": conflicts,
        "legal": conflicts == 0,
        "solution_sha256": canonical_sha256(
            colors, domain="EU26-02-R250-SOLUTION-V1"
        ),
    }


def _read_exact_member(
    archive: tarfile.TarFile, name: str, expected_sha256: str
) -> bytes:
    path = PurePosixPath(name)
    if path.is_absolute() or ".." in path.parts:
        raise WitnessValidationError("unsafe witness member name")
    try:
        member = archive.getmember(name)
    except KeyError as error:
        raise WitnessValidationError(f"missing witness member: {name}") from error
    if not member.isfile() or member.issym() or member.islnk():
        raise WitnessValidationError("witness member is not a regular file")
    handle = archive.extractfile(member)
    if handle is None:
        raise WitnessValidationError("cannot read witness member")
    raw = handle.read()
    if _sha256_bytes(raw) != expected_sha256:
        raise WitnessValidationError(f"witness member SHA-256 mismatch: {name}")
    return raw


def _parse_main(raw: bytes) -> dict[str, Any]:
    lines = raw.decode("utf-8").splitlines()
    try:
        header = lines.index("turn,time,nb_uncolored,penalty,nb_colors,solution")
    except ValueError as error:
        raise WitnessValidationError("main witness result header is missing") from error
    rows: list[dict[str, Any]] = []
    for line in lines[header + 1 :]:
        if not line or line.startswith("#") or line == "restart":
            continue
        fields = next(csv.reader([line]))
        if len(fields) != 6:
            raise WitnessValidationError("malformed main witness row")
        try:
            colors = [int(value) for value in fields[5].split(":")]
            row = {
                "turn": int(fields[0]),
                "time": int(fields[1]),
                "nb_uncolored": int(fields[2]),
                "penalty": int(fields[3]),
                "nb_colors": int(fields[4]),
                "colors": colors,
            }
        except ValueError as error:
            raise WitnessValidationError("non-integer main witness value") from error
        rows.append(row)
    if not rows:
        raise WitnessValidationError("main witness has no result rows")
    legal_rows = [
        row for row in rows if row["penalty"] == 0 and row["nb_uncolored"] == 0
    ]
    if not legal_rows:
        raise WitnessValidationError("main witness has no legal coloring")
    first_legal = legal_rows[0]
    final = rows[-1]
    if (first_legal["turn"], first_legal["time"], final["turn"], final["time"]) != (
        32,
        33,
        33,
        33,
    ):
        raise WitnessValidationError("main witness timing/turn sequence changed")
    if final["colors"] != first_legal["colors"] or final["nb_colors"] != 66:
        raise WitnessValidationError("final witness does not duplicate the legal k=66 state")
    return {"first_legal": first_legal, "final": final, "row_count": len(rows)}


def _parse_colon_ints(value: str, context: str) -> list[int]:
    try:
        result = [int(item) for item in value.split(":")]
    except ValueError as error:
        raise WitnessValidationError(f"invalid {context}") from error
    if len(result) != 2:
        raise WitnessValidationError(f"{context} must contain two values")
    return result


def _parse_tbt(raw: bytes) -> dict[str, Any]:
    lines = raw.decode("utf-8").splitlines()
    if len(lines) < 4 or lines[0] != "#operators":
        raise WitnessValidationError("TBT operator header is missing")
    if lines[1][1:].split(":") != OPERATOR_NAMES:
        raise WitnessValidationError("TBT operator order differs from the frozen mapping")
    reader = csv.DictReader(io.StringIO("\n".join(lines[2:]) + "\n"))
    rows = list(reader)
    if not rows:
        raise WitnessValidationError("TBT witness has no rows")
    counts = [0] * 6
    sums = [0] * 6
    turn_30: dict[str, Any] | None = None
    previous_turn = -1
    for row in rows:
        try:
            turn = int(row["turn"])
        except (KeyError, TypeError, ValueError) as error:
            raise WitnessValidationError("invalid TBT turn") from error
        if turn != previous_turn + 1:
            raise WitnessValidationError("TBT turns are not contiguous from zero")
        previous_turn = turn
        selected = _parse_colon_ints(row["selected"], "TBT selected")
        scores = _parse_colon_ints(
            row["fitness_post_mutation"], "TBT post-local-search penalties"
        )
        if turn == 30:
            turn_30 = {
                "pre_counts": list(counts),
                "pre_sums": list(sums),
                "selected": selected,
                "scores": scores,
            }
        for operator, score in zip(selected, scores):
            if operator < 0 or operator >= 6 or score < 0:
                raise WitnessValidationError("invalid TBT operator or score")
            counts[operator] += 1
            sums[operator] += score
        if turn == 30:
            assert turn_30 is not None
            turn_30["post_counts"] = list(counts)
            turn_30["post_sums"] = list(sums)
            turn_30["post_means"] = [
                sums[index] / counts[index] for index in range(6)
            ]
            turn_30["removed_operator"] = max(
                range(6), key=lambda operator: (turn_30["post_means"][operator], -operator)
            )
    if turn_30 is None:
        raise WitnessValidationError("TBT witness does not reach turn 30")
    expected = (
        EXPECTED_PRE_COUNTS,
        EXPECTED_PRE_SUMS,
        EXPECTED_SELECTED,
        EXPECTED_SCORES,
        EXPECTED_POST_COUNTS,
        EXPECTED_POST_SUMS,
        1,
    )
    actual = (
        turn_30["pre_counts"],
        turn_30["pre_sums"],
        turn_30["selected"],
        turn_30["scores"],
        turn_30["post_counts"],
        turn_30["post_sums"],
        turn_30["removed_operator"],
    )
    if actual != expected:
        raise WitnessValidationError("TBT turn-30 transition differs from the contract")
    if not all(math.isfinite(value) for value in turn_30["post_means"]):
        raise WitnessValidationError("non-finite TBT lifetime mean")
    return {"row_count": len(rows), "turn_30": turn_30}


def validate_selected_witness(
    archive_path: str | Path, graph_path: str | Path
) -> dict[str, Any]:
    """Validate member identity, legal coloring and the archived turn-30 update."""

    archive_path = Path(archive_path).resolve()
    graph_path = Path(graph_path).resolve()
    if _sha256_file(archive_path) != ARCHIVE_SHA256:
        raise WitnessValidationError("archive SHA-256 mismatch")
    with tarfile.open(archive_path, "r:*") as archive:
        main_raw = _read_exact_member(archive, MAIN_MEMBER, MAIN_SHA256)
        tbt_raw = _read_exact_member(archive, TBT_MEMBER, TBT_SHA256)
    main = _parse_main(main_raw)
    tbt = _parse_tbt(tbt_raw)
    graph = parse_dimacs_graph(graph_path)
    coloring = validate_coloring(main["final"]["colors"], graph, 66)
    if not coloring["legal"]:
        raise WitnessValidationError("selected archived coloring has a graph conflict")
    if coloring["used_colors"] != 66:
        raise WitnessValidationError(
            "selected archived coloring does not use all 66 declared colors"
        )

    report = {
        "schema_version": "1.0.0",
        "candidate_id": "EU26-02",
        "status": "PASS_SELECTED_WITNESS",
        "paper_level_status": "BLOCKED_MULTIPLE_SOURCE_CONFLICTS",
        "archive_sha256": ARCHIVE_SHA256,
        "members": {
            "main": {"path": MAIN_MEMBER, "bytes": len(main_raw), "sha256": MAIN_SHA256},
            "tbt": {"path": TBT_MEMBER, "bytes": len(tbt_raw), "sha256": TBT_SHA256},
        },
        "graph": {
            "source_path": "reduced_gcp/r250.5.col",
            "sha256": graph["sha256"],
            "vertices": graph["vertices"],
            "edges": graph["declared_edges"],
        },
        "legal_coloring": coloring,
        "first_legal": {
            "turn": main["first_legal"]["turn"],
            "time_seconds": main["first_legal"]["time"],
            "nb_colors": main["first_legal"]["nb_colors"],
        },
        "final_turn": main["final"]["turn"],
        "turn_30_transition": tbt["turn_30"],
        "claim": "selected archived artifact legality and source-formula transition only",
    }
    report["report_digest"] = canonical_sha256(
        report, domain="EU26-02-SELECTED-WITNESS-REPORT-V1"
    )
    return report
