"""Freeze prospective study bytes without executing numerical calculations."""
from hashlib import sha256
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPOSITORY = HERE.parents[2]


def main():
    original = REPOSITORY / "studies/knapsack_parameters/population_validation_100_main/source_manifest.json"
    for row in json.loads(original.read_text(encoding="utf-8"))["files"]:
        raw = (REPOSITORY / row["path"]).read_bytes()
        if len(raw) != row["bytes"] or sha256(raw).hexdigest() != row["sha256"]:
            raise ValueError("Historical source bytes differ: " + row["path"])
    files = [original, REPOSITORY / ".github/workflows/initial-grid-100-technical.yml"]
    files += [p for p in HERE.rglob("*") if p.is_file() and "__pycache__" not in p.parts
              and p.name != "source_manifest.json"]
    entries = [{"path": p.relative_to(REPOSITORY).as_posix(), "bytes": p.stat().st_size,
                "sha256": sha256(p.read_bytes()).hexdigest()} for p in sorted(files)]
    output = HERE / "source_manifest.json"
    if output.exists():
        raise ValueError("Preserve the previous source seal before recording an amendment")
    output.write_text(json.dumps({"schema": "initial-grid-100-source-v1", "files": entries,
                                 "scientific_calculations_performed": False}, indent=2), encoding="utf-8")
    print("Frozen prospective grid sources; no tests, exact solving, search or analysis executed.")


if __name__ == "__main__":
    main()
