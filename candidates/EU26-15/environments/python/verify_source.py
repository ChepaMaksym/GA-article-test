#!/usr/bin/env python3
"""CLI for the exact EU26-15 GARBO source and optional CSV probes."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from eu2615.source_probe import probe_source


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-dir", type=Path, required=True)
    parser.add_argument("--data-csv", type=Path)
    arguments = parser.parse_args()
    report = probe_source(arguments.source_dir, arguments.data_csv)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
