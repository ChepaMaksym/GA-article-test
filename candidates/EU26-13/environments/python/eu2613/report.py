"""Write immutable JSON reports."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .safe_paths import safe_write_text_once


def write_json_once(path: Path | str, document: dict[str, Any]) -> None:
    payload = json.dumps(document, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    safe_write_text_once(path, payload, stage="REPORT")
