"""Seal source bytes only; this local administrative command performs no experiment."""
from hashlib import sha256
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPOSITORY = HERE.parents[2]


def main():
    dependencies = [REPOSITORY / ".github/workflows/population-validation-100.yml",
                    REPOSITORY / "studies/knapsack_parameters/crossover_population/__init__.py",
                    REPOSITORY / "studies/knapsack_parameters/crossover_population/program/__init__.py",
                    REPOSITORY / "studies/knapsack_parameters/crossover_population/verification.py",
                    REPOSITORY / "studies/knapsack_parameters/crossover_population/observations.py",
                    REPOSITORY / "studies/knapsack_parameters/population_size_study/__init__.py",
                    REPOSITORY / "studies/knapsack_parameters/population_size_study/exact.py",
                    REPOSITORY / "studies/knapsack_parameters/population_size_study/inputs.py",
                    REPOSITORY / "studies/knapsack_parameters/population_size_study/source_tree_manifest.json",
                    REPOSITORY / "studies/knapsack_parameters/ga_study/dependencies/requirements.lock"]
    dependencies += sorted((REPOSITORY / "studies/knapsack_parameters/crossover_population/program/ga_core").glob("*.py"))
    dependencies += sorted(p for p in HERE.rglob("*") if p.is_file() and (p.suffix in (".py", ".md", ".json") or p.name == ".gitattributes")
                           and p.name != "source_manifest.json" and "__pycache__" not in p.parts)
    rows = []
    for path in sorted(set(dependencies)):
        raw = path.read_bytes()
        rows.append({"path": path.relative_to(REPOSITORY).as_posix(), "bytes": len(raw), "sha256": sha256(raw).hexdigest()})
    destination = HERE / "source_manifest.json"
    if destination.exists():
        raise ValueError("Preserve the previous source seal before creating an amended seal")
    destination.write_text(json.dumps({"schema": "population-validation-100-source-v1", "files": rows,
                           "scientific_execution_performed": False}, indent=2), encoding="utf-8")
    print("Sealed", len(rows), "source/input files; no tests, search or numerical analysis performed.")


if __name__ == "__main__":
    main()
