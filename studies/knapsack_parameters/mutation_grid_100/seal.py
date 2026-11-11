"""Freeze source bytes only; never execute tests or scientific calculations."""
from hashlib import sha256
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPOSITORY = HERE.parents[2]


def main():
    old = REPOSITORY / "studies/knapsack_parameters/initial_grid_100/source_manifest.json"
    if sha256(old.read_bytes()).hexdigest() != "2ed212337b22706decd7123ab1111cbc4c62fbe357e29478c1c868acf3c2f44f":
        raise ValueError("The retained source seal differs")
    for row in json.loads(old.read_text(encoding="utf-8"))["files"]:
        data = (REPOSITORY / row["path"]).read_bytes()
        if len(data) != row["bytes"] or sha256(data).hexdigest() != row["sha256"]:
            raise ValueError("Historical source bytes differ: " + row["path"])
    files = [old, REPOSITORY / ".github/workflows/mutation-grid-100-technical.yml"]
    files += [p for p in HERE.rglob("*") if p.is_file() and "__pycache__" not in p.parts
              and p.name != "source_manifest.json"]
    output = HERE / "source_manifest.json"
    if output.exists():
        raise ValueError("Preserve the old seal before recording a prospective amendment")
    entries = [{"path": p.relative_to(REPOSITORY).as_posix(), "bytes": p.stat().st_size,
                "sha256": sha256(p.read_bytes()).hexdigest()} for p in sorted(files)]
    output.write_text(json.dumps({"schema": "mutation-grid-100-source-v1", "files": entries,
                                 "scientific_calculations_performed": False}, indent=2), encoding="utf-8")
    print("Mutation source bytes sealed; no scientific computation performed.")


if __name__ == "__main__":
    main()
