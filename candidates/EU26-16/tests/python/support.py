from __future__ import annotations

import os
import sys
from pathlib import Path

CANDIDATE = Path(__file__).resolve().parents[2]
PYTHON_ROOT = CANDIDATE / "environments" / "python"
if str(PYTHON_ROOT) not in sys.path:
    sys.path.insert(0, str(PYTHON_ROOT))

from eu2616.contract import load_contract

CONTRACT = load_contract()


def upstream() -> Path:
    value = os.environ.get("EU2616_UPSTREAM")
    if not value:
        raise RuntimeError("EU2616_UPSTREAM is required")
    return Path(value).resolve(strict=True)
