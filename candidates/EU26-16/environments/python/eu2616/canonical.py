from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from typing import Any


def _reject_nonfinite(value: Any) -> None:
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError("non-finite values are forbidden in reports")
    if isinstance(value, dict):
        for key, item in value.items():
            if not isinstance(key, str):
                raise ValueError("report object keys must be strings")
            _reject_nonfinite(item)
    elif isinstance(value, (list, tuple)):
        for item in value:
            _reject_nonfinite(item)


def canonical_bytes(value: Any) -> bytes:
    _reject_nonfinite(value)
    return json.dumps(
        value,
        ensure_ascii=True,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("ascii")


def bind_report(report: dict[str, Any]) -> dict[str, Any]:
    if "report_digest" in report:
        raise ValueError("report_digest is reserved")
    bound = dict(report)
    payload = b"EU26-16-FORMULA-SOURCE-REPORT-V1\0" + canonical_bytes(bound)
    bound["report_digest"] = hashlib.sha256(payload).hexdigest()
    return bound


def write_new_json(path: Path, value: Any) -> None:
    path = path.resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    data = json.dumps(value, ensure_ascii=True, allow_nan=False, indent=2, sort_keys=True) + "\n"
    with path.open("x", encoding="ascii", newline="\n") as handle:
        handle.write(data)
