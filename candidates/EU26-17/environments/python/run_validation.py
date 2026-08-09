#!/usr/bin/env python3
"""Run EU26-17 authenticated formula/source validation only."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

PYTHON_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PYTHON_ROOT))

from eu2617.validation import build_report, write_report  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--core-repo", type=Path, required=True)
    parser.add_argument("--experiment-repo", type=Path, required=True)
    parser.add_argument("--paper-pdf", type=Path, required=True)
    parser.add_argument("--uci-archive", type=Path, required=True)
    parser.add_argument("--octave-tsv", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    candidate_root = Path(__file__).resolve().parents[2]
    report = build_report(
        candidate_root,
        args.core_repo.resolve(),
        args.experiment_repo.resolve(),
        args.paper_pdf.resolve(),
        args.uci_archive.resolve(),
        args.octave_tsv.resolve() if args.octave_tsv else None,
    )
    write_report(args.output, report)
    print(
        "EU26-17 validation: "
        f"{', '.join(report['outcomes'])}; overall eligibility remains HARD_FAIL"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
