from __future__ import annotations

import csv
import dataclasses
import re
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any


class DatasetFormatError(ValueError):
    """Raised when authenticated dataset bytes do not match their declared shape."""


class EvidenceGapError(RuntimeError):
    """Raised when an empirical Table 7 claim is requested from incomplete evidence."""


ATTRIBUTE_PATTERN = re.compile(
    r"^@attribute\s+(?P<name>'[^']+'|\"[^\"]+\"|\S+)\s+(?P<kind>.+?)\s*$",
    re.IGNORECASE,
)


@dataclasses.dataclass(frozen=True)
class ArffSummary:
    relation: str
    attributes: tuple[tuple[str, str], ...]
    row_count: int


@dataclasses.dataclass(frozen=True)
class YeastAudit:
    seeds: tuple[int, ...]
    referenced_paths: tuple[str, ...]
    missing_paths: tuple[str, ...]
    label_names: tuple[str, ...]
    input_names: tuple[str, ...]
    train_rows: int
    test_rows: int
    total_rows: int
    paper_replay_ready: bool
    gaps: tuple[str, ...]


def _strip_name(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "'\"":
        return value[1:-1]
    return value


def parse_arff(path: Path) -> ArffSummary:
    relation: str | None = None
    attributes: list[tuple[str, str]] = []
    rows = 0
    in_data = False
    width: int | None = None
    for line_number, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        line = raw_line.strip()
        if not line or line.startswith("%"):
            continue
        lower = line.lower()
        if not in_data and lower.startswith("@relation"):
            parts = line.split(maxsplit=1)
            if len(parts) != 2 or relation is not None:
                raise DatasetFormatError(f"invalid @relation at line {line_number}")
            relation = _strip_name(parts[1].strip())
        elif not in_data and lower.startswith("@attribute"):
            match = ATTRIBUTE_PATTERN.match(line)
            if match is None:
                raise DatasetFormatError(f"invalid @attribute at line {line_number}")
            attributes.append((_strip_name(match.group("name")), match.group("kind").strip()))
        elif not in_data and lower == "@data":
            if relation is None or not attributes:
                raise DatasetFormatError("@data appears before relation/attributes")
            in_data = True
            width = len(attributes)
        elif in_data:
            if line.startswith("{"):
                raise DatasetFormatError("sparse ARFF rows are outside this frozen parser")
            values = next(csv.reader([line], strict=True))
            if len(values) != width:
                raise DatasetFormatError(
                    f"row width mismatch at line {line_number}: {len(values)} != {width}"
                )
            rows += 1
        else:
            raise DatasetFormatError(f"unexpected ARFF directive at line {line_number}")
    if not in_data or relation is None or rows == 0:
        raise DatasetFormatError("incomplete ARFF file")
    return ArffSummary(relation=relation, attributes=tuple(attributes), row_count=rows)


def parse_label_xml(path: Path) -> tuple[str, ...]:
    try:
        root = ET.parse(path).getroot()
    except (OSError, ET.ParseError) as error:
        raise DatasetFormatError(f"invalid label XML: {error}") from error
    labels = tuple(
        element.attrib["name"]
        for element in root.iter()
        if element.tag.rsplit("}", 1)[-1] == "label" and "name" in element.attrib
    )
    if not labels or len(set(labels)) != len(labels):
        raise DatasetFormatError("label XML must contain unique named labels")
    return labels


def parse_yeast_config(path: Path) -> tuple[tuple[int, ...], tuple[str, ...]]:
    try:
        root = ET.parse(path).getroot()
    except (OSError, ET.ParseError) as error:
        raise DatasetFormatError(f"invalid Yeast config XML: {error}") from error
    seeds = tuple(int(element.attrib["seed"]) for element in root.iter() if "seed" in element.attrib)
    dataset_paths: list[str] = []
    for element in root.iter():
        local_name = element.tag.rsplit("}", 1)[-1]
        if local_name in {"train-dataset", "test-dataset", "xml"} and element.text:
            dataset_paths.append(element.text.strip())
    if not seeds or not dataset_paths:
        raise DatasetFormatError("Yeast config has no seeds or dataset paths")
    return seeds, tuple(dataset_paths)


def table7_gaps(
    *,
    checkout: Path,
    contract: dict[str, Any],
    seeds: tuple[int, ...],
    referenced_paths: tuple[str, ...],
) -> tuple[str, ...]:
    gaps: list[str] = []
    missing = tuple(path for path in referenced_paths if not (checkout / path).is_file())
    if missing:
        gaps.extend(["ONLY_FOLD_1_SHIPPED", "CONFIG_REFERENCES_ABSENT_FOLD_2"])
    if len(seeds) != contract["paper_protocol"]["random_seed_count"]:
        gaps.append("PAPER_TEN_SEEDS_NOT_ENUMERATED")
    if len([path for path in referenced_paths if "train" in path.lower()]) != 5:
        gaps.append("NO_FIVE_FOLD_DATA_MANIFEST")
    gaps.extend(
        [
            "NO_RAW_FIFTY_RUN_TABLE_7_LEDGER",
            "TABLE_7_VARIANT_CONFIG_NOT_FULLY_BOUND",
            "DATASET_LICENSE_UNRESOLVED",
        ]
    )
    mandatory_order = contract["blockers"]
    return tuple(code for code in mandatory_order if code in set(gaps))


def audit_yeast(checkout: Path, contract: dict[str, Any]) -> YeastAudit:
    checkout = checkout.resolve(strict=True)
    shipped = contract["shipped_yeast"]
    seeds, referenced_paths = parse_yeast_config(checkout / shipped["config_path"])
    missing_paths = tuple(path for path in referenced_paths if not (checkout / path).is_file())
    labels = parse_label_xml(checkout / "data/Yeast/Yeast.xml")
    train = parse_arff(checkout / "data/Yeast/Yeast-train1.arff")
    test = parse_arff(checkout / "data/Yeast/Yeast-test1.arff")
    if train.relation != "Yeast" or test.relation != "Yeast":
        raise DatasetFormatError("unexpected Yeast relation")
    if train.attributes != test.attributes:
        raise DatasetFormatError("train/test attribute declarations differ")
    attribute_names = tuple(name for name, _ in train.attributes)
    label_set = set(labels)
    input_names = tuple(name for name in attribute_names if name not in label_set)
    arff_labels = tuple(name for name in attribute_names if name in label_set)
    if set(arff_labels) != label_set:
        raise DatasetFormatError("ARFF and label XML disagree")
    attribute_types = dict(train.attributes)
    if any(attribute_types[name].lower() != "numeric" for name in input_names):
        raise DatasetFormatError("all frozen Yeast inputs must be numeric")
    if any(attribute_types[name].replace(" ", "") != "{0,1}" for name in arff_labels):
        raise DatasetFormatError("all frozen Yeast labels must be binary")
    if len(input_names) != shipped["input_attributes"] or len(labels) != shipped["labels"]:
        raise DatasetFormatError("Yeast dimension differs from the frozen contract")
    if train.row_count != shipped["train_rows_fold_1"]:
        raise DatasetFormatError("Yeast fold-1 train row count differs")
    if test.row_count != shipped["test_rows_fold_1"]:
        raise DatasetFormatError("Yeast fold-1 test row count differs")
    total = train.row_count + test.row_count
    if total != shipped["total_rows_fold_1"]:
        raise DatasetFormatError("Yeast fold-1 total row count differs")
    if seeds != tuple(shipped["config_seeds"]):
        raise DatasetFormatError("Yeast config seeds differ from the frozen contract")
    if missing_paths != tuple(shipped["missing_paths"]):
        raise DatasetFormatError("Yeast missing-path inventory differs from the frozen contract")
    gaps = table7_gaps(
        checkout=checkout,
        contract=contract,
        seeds=seeds,
        referenced_paths=referenced_paths,
    )
    return YeastAudit(
        seeds=seeds,
        referenced_paths=referenced_paths,
        missing_paths=missing_paths,
        label_names=labels,
        input_names=input_names,
        train_rows=train.row_count,
        test_rows=test.row_count,
        total_rows=total,
        paper_replay_ready=False,
        gaps=gaps,
    )


def assert_table7_replay_ready(audit: YeastAudit, contract: dict[str, Any]) -> None:
    if audit.paper_replay_ready or not audit.gaps:
        raise EvidenceGapError("invalid audit: blockers were unexpectedly cleared")
    mandatory = set(contract["blockers"])
    observed = set(audit.gaps)
    if not mandatory.issubset(observed):
        raise EvidenceGapError(
            "Table 7 replay blocked by incomplete manifest: " + ", ".join(audit.gaps)
        )
    raise EvidenceGapError(
        "Table 7 replay is contractually disabled: " + ", ".join(audit.gaps)
    )
