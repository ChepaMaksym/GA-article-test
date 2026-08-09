#!/usr/bin/env python3
"""Dependency-light EU26-17 test runner with optional integration paths."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import unittest


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--core-repo", type=Path)
    parser.add_argument("--experiment-repo", type=Path)
    parser.add_argument("--paper-pdf", type=Path)
    parser.add_argument("--uci-archive", type=Path)
    parser.add_argument("--octave-tsv", type=Path)
    parser.add_argument("--require-integration", action="store_true")
    parser.add_argument("--require-octave", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    environment = {
        "EU2617_CORE_REPO": args.core_repo,
        "EU2617_EXPERIMENT_REPO": args.experiment_repo,
        "EU2617_PAPER_PDF": args.paper_pdf,
        "EU2617_UCI_ARCHIVE": args.uci_archive,
        "EU2617_OCTAVE_TSV": args.octave_tsv,
    }
    required_inputs = (
        args.core_repo,
        args.experiment_repo,
        args.paper_pdf,
        args.uci_archive,
    )
    if args.require_integration and any(value is None for value in required_inputs):
        raise SystemExit("--require-integration needs all four authenticated input paths")
    if args.require_octave and args.octave_tsv is None:
        raise SystemExit("--require-octave needs --octave-tsv")
    for name, value in environment.items():
        if value is not None:
            os.environ[name] = str(value.resolve())
    test_dir = Path(__file__).resolve().parent / "python"
    suite = unittest.defaultTestLoader.discover(str(test_dir), pattern="test_*.py")
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    if (args.require_integration or args.require_octave) and result.skipped:
        print(f"verification mode forbids skipped tests: {result.skipped}")
        return 1
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
