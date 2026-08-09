"""Write immutable JSON reports."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .errors import VerificationError


def write_json_once(path: Path | str, document: dict[str, Any]) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(document, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    try:
        with target.open("x", encoding="utf-8", newline="\n") as handle:
            handle.write(payload)
    except FileExistsError as exc:
        raise VerificationError("REPORT", f"refusing to overwrite {target}") from exc
    except OSError as exc:
        raise VerificationError("REPORT", f"cannot write {target}: {exc}") from exc
