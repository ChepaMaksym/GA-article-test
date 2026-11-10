"""Seal prospective main-stage bytes; performs no search or statistical analysis."""
from hashlib import sha256
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPOSITORY = HERE.parents[2]
TECHNICAL = REPOSITORY / "studies/knapsack_parameters/population_validation_100"


def main():
    old_manifest = json.loads((TECHNICAL / "source_manifest.json").read_text(encoding="utf-8"))
    if old_manifest["schema"] != "population-validation-100-source-v1":
        raise ValueError("Technical source seal differs")
    dependencies = [REPOSITORY / row["path"] for row in old_manifest["files"]]
    for path, record in zip(dependencies, old_manifest["files"], strict=True):
        raw = path.read_bytes()
        if len(raw) != record["bytes"] or sha256(raw).hexdigest() != record["sha256"]:
            raise ValueError("Previously sealed technical input differs: " + record["path"])
    dependencies += [TECHNICAL / "source_manifest.json",
                     REPOSITORY / ".github/workflows/population-validation-100-main.yml",
                     REPOSITORY / ".github/workflows/population-validation-100-main-tests.yml",
                     REPOSITORY / "studies/knapsack_parameters/population_size_study/io_utils.py"]
    dependencies += sorted(path for path in HERE.rglob("*") if path.is_file() and "__pycache__" not in path.parts
                           and path.name != "source_manifest.json"
                           and (path.suffix in (".py", ".md", ".json", ".zip") or path.name == ".gitattributes"))
    records = []
    for path in sorted(set(dependencies)):
        raw = path.read_bytes()
        records.append({"path": path.relative_to(REPOSITORY).as_posix(), "bytes": len(raw), "sha256": sha256(raw).hexdigest()})
    destination = HERE / "source_manifest.json"
    if destination.exists():
        raise ValueError("Preserve the previous source seal before creating an amended seal")
    destination.write_text(json.dumps({"schema": "population-validation-100-main-source-v1", "files": records,
                                      "scientific_execution_performed": False}, indent=2), encoding="utf-8")
    print("Sealed", len(records), "prospective files; no tests, search or statistical analysis performed.")


if __name__ == "__main__":
    main()
