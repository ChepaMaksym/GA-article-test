"""Freeze source bytes and retained references; never run scientific code."""
import argparse
from datetime import datetime, timezone
from pathlib import Path

from .common import REPOSITORY, ROOT, sha256, write_json


DEPENDENCIES = (
    "studies/knapsack_parameters/population_size_study/exact.py",
    "studies/knapsack_parameters/population_size_study/inputs.py",
    "studies/knapsack_parameters/ga_study/dependencies/requirements.lock",
)


def freeze():
    files = [path for path in ROOT.rglob("*") if path.is_file()
             and "__pycache__" not in path.parts and path.name != "source_manifest.json"]
    old_kernel = REPOSITORY / "studies/knapsack_parameters/mutation_grid_100/program/ga_core"
    dependencies = [REPOSITORY / relative for relative in DEPENDENCIES]
    dependencies.extend(sorted(old_kernel.glob("*.py")))
    dependencies.append(REPOSITORY / ".github/workflows/calibrated-selection-technical.yml")
    all_paths = sorted(set(files + dependencies))
    missing = [str(path) for path in all_paths if not path.is_file()]
    if missing:
        raise ValueError("Missing prospective sources: " + ", ".join(missing))
    write_json(ROOT / "source_manifest.json", {
        "schema": "calibrated-selection-source-v1",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "execution_status": "NOT_EXECUTED", "historical_sources_modified": False,
        "files": [{"path": path.relative_to(REPOSITORY).as_posix(),
                   "bytes": path.stat().st_size, "sha256": sha256(path)} for path in all_paths],
        "kernel_origin": "mutation_grid_100/program/ga_core",
        "adaptation": "New explicit calibrated selection contract; historical routes retained",
        "source_metadata": "data/source_registry.json",
        "technical_permission": "technical_authorization.json",
        "main_permission": "main_authorization.json"})


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true", required=True)
    parser.parse_args()
    freeze()
