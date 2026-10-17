"""Post-search record history; no reference target is passed to the GA."""
from __future__ import annotations

import numpy as np

from .contract import require


def record_history(result):
    """Retain every strictly increasing feasible record, including initialization."""
    rows = result["requests"]
    best = None
    history = []
    for ref, (feasible, profit) in enumerate(zip(rows["feasible"], rows["profit"], strict=True)):
        value = int(profit)
        if feasible and (best is None or value > best):
            best = value
            history.append({"request": ref + 1, "profit": value})
    verify_history(result, history)
    return history


def verify_history(result, history):
    """Independent dense cumulative reconstruction from oracle-verified requests."""
    rows, summary = result["requests"], result["summary"]
    count = summary["logical_requests"]
    require(len(rows["profit"]) == len(rows["feasible"]) == count, "Incomplete observation source")
    values = np.where(rows["feasible"], rows["profit"], -1)
    dense = np.maximum.accumulate(values)
    refs = np.flatnonzero(np.r_[True, dense[1:] > dense[:-1]])
    expected = [{"request": int(ref + 1), "profit": int(dense[ref])} for ref in refs if dense[ref] >= 0]
    require(history == expected and history and
            history[-1]["request"] == summary["best_request"] and
            history[-1]["profit"] == summary["best_profit"], "History differs from all evaluated candidates")
    require(all(type(point["request"]) is int and type(point["profit"]) is int for point in history), "Noninteger observation")
    return True
