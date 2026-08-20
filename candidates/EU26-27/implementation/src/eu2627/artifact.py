from __future__ import annotations

import csv
import io
import zipfile
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path


@dataclass(frozen=True)
class RawEndpointReport:
    member_sha256: str
    algorithm: str
    function: str
    dimension: int
    front_rows: int
    run_count: int
    complete_runs: int
    endpoints: tuple[int | None, ...]
    endpoint_digest: str

    def finite_endpoints(self) -> tuple[int, ...]:
        return tuple(value for value in self.endpoints if value is not None)


def _success(value: str) -> bool:
    return value.strip().lower() in {"1", "1.0", "true", "yes"}


def parse_raw_endpoint(
    archive_path: str | Path,
    member: str = "csv/om/TwoRateL10P1HVOneMaxD100.csv",
) -> RawEndpointReport:
    path = Path(archive_path)
    if not path.is_file():
        raise FileNotFoundError(path)
    with zipfile.ZipFile(path) as archive:
        data = archive.read(member)
    rows = list(csv.reader(io.StringIO(data.decode("utf-8-sig"))))
    if not rows:
        raise ValueError("empty selected CSV")
    header = rows[0]
    expected = ["pareto", "algorithm", "func", "dimension"]
    for run in range(100):
        expected.extend([f"found{run}", f"First_hit{run}"])
    if header != expected:
        raise ValueError("unexpected selected CSV header")
    data_rows = [row for row in rows[1:] if row and any(value.strip() for value in row)]
    if len(data_rows) != 101:
        raise ValueError(f"expected 101 Pareto rows, got {len(data_rows)}")
    if any(len(row) != len(header) for row in data_rows):
        raise ValueError("ragged selected CSV")
    algorithms = {row[1].strip() for row in data_rows}
    functions = {row[2].strip() for row in data_rows}
    dimensions = {int(float(row[3])) for row in data_rows}
    if len(algorithms) != 1 or len(functions) != 1 or dimensions != {100}:
        raise ValueError("metadata drift across selected rows")
    endpoints: list[int | None] = []
    for run in range(100):
        found_index = 4 + 2 * run
        hit_index = found_index + 1
        found = [_success(row[found_index]) for row in data_rows]
        if not all(found):
            endpoints.append(None)
            continue
        hits = [int(float(row[hit_index])) for row in data_rows]
        if min(hits) < 0:
            raise ValueError("negative First_hit value")
        endpoints.append(max(hits))
    finite = [value for value in endpoints if value is not None]
    digest = sha256(
        ",".join("NA" if value is None else str(value) for value in endpoints).encode("ascii")
    ).hexdigest()
    return RawEndpointReport(
        member_sha256=sha256(data).hexdigest(),
        algorithm=next(iter(algorithms)),
        function=next(iter(functions)),
        dimension=100,
        front_rows=101,
        run_count=100,
        complete_runs=len(finite),
        endpoints=tuple(endpoints),
        endpoint_digest=digest,
    )
