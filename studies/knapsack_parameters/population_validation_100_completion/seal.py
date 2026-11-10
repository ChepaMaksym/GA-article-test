"""Freeze wrapper bytes and reference the unchanged historical source seal."""
from hashlib import sha256
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPOSITORY = HERE.parents[2]


def main():
    original = REPOSITORY / "studies/knapsack_parameters/population_validation_100_main/source_manifest.json"
    records = json.loads(original.read_text(encoding="utf-8"))["files"]
    for row in records:
        raw = (REPOSITORY / row["path"]).read_bytes()
        if len(raw) != row["bytes"] or sha256(raw).hexdigest() != row["sha256"]:
            raise ValueError("Historical sealed source differs")
    paths = [original, REPOSITORY / ".github/workflows/population-validation-100-completion.yml"]
    paths += [p for p in HERE.rglob("*") if p.is_file() and "__pycache__" not in p.parts
              and p.name != "source_manifest.json"]
    entries = [{"path": p.relative_to(REPOSITORY).as_posix(), "bytes": p.stat().st_size,
                "sha256": sha256(p.read_bytes()).hexdigest()} for p in sorted(paths)]
    destination = HERE / "source_manifest.json"
    if destination.exists():
        raise ValueError("Preserve the prior source seal before amendment")
    destination.write_text(json.dumps({"schema": "population-validation-100-completion-source-v1", "files": entries}, indent=2), encoding="utf-8")
    print("Frozen continuation sources; no tests, search or numerical analysis executed.")


if __name__ == "__main__":
    main()
