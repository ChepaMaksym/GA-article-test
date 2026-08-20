from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import inspect
import io
import json
import unittest
from pathlib import Path


def git_blob_sha(data: bytes) -> str:
    return hashlib.sha1(f"blob {len(data)}\0".encode() + data).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--expected-blob", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)

    report: dict = {
        "candidate_id": "EU26-25",
        "gate": "adaptive_penalty_formula",
        "pass": False,
    }
    try:
        from pyvrp import PenaltyManager

        version = importlib.metadata.version("pyvrp")
        source = Path(inspect.getsourcefile(PenaltyManager) or "")
        blob = git_blob_sha(source.read_bytes()) if source.is_file() else None
        suite = unittest.defaultTestLoader.discover(
            str(Path(__file__).parent), pattern="test_penalty.py"
        )
        stream = io.StringIO()
        result = unittest.TextTestRunner(stream=stream, verbosity=2).run(suite)
        report.update(
            {
                "source_version": version,
                "penalty_manager_git_blob": blob,
                "expected_blob": args.expected_blob,
                "tests_run": result.testsRun,
                "failures": len(result.failures),
                "errors": len(result.errors),
                "skipped": len(result.skipped),
                "test_log": stream.getvalue(),
                "pass": (
                    version == "0.5.0"
                    and blob == args.expected_blob
                    and result.wasSuccessful()
                    and result.testsRun == 10
                ),
            }
        )
    except Exception as exc:
        report["error"] = f"{type(exc).__name__}: {exc}"

    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
