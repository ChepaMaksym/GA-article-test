"""CI-only wheel resolution; produces an exact hash-checked numerical lock."""

import argparse
import email
import os
from pathlib import Path
import subprocess
import sys
import zipfile

from ..contract import (MODULE_ROOT, authenticate, canonical_bytes, file_identity,
                        output_directory, require, sha256_bytes, write_file_manifest, write_json)


def freeze(expected_sha, output):
    identity = authenticate(expected_sha, scientific=False)
    output = output_directory(output)
    wheels = output / "wheels"
    wheels.mkdir()
    subprocess.run([sys.executable, "-m", "pip", "download", "--only-binary=:all:",
                    "--dest", str(wheels), "-r", str(MODULE_ROOT / "dependencies/requirements.in")], check=True)
    rows = []
    for wheel in sorted(wheels.glob("*.whl")):
        with zipfile.ZipFile(wheel) as archive:
            matches = [name for name in archive.namelist() if name.endswith(".dist-info/METADATA")]
            require(len(matches) == 1, "wheel must have one package metadata")
            metadata = email.message_from_bytes(archive.read(matches[0]))
        rows.append({"name": metadata["Name"].lower().replace("_", "-"), "version": metadata["Version"],
                     "wheel": wheel.name, **file_identity(wheel)})
    require(len({row["name"] for row in rows}) == len(rows), "duplicate package wheels")
    versions = {row["name"]: row["version"] for row in rows}
    require(versions.get("numpy") == "2.2.6" and versions.get("matplotlib") == "3.10.3", "wrong root resolution")
    raw = ("# Generated only in registered GitHub Actions lock stage.\n" +
           "\n".join(f"{row['name']}=={row['version']} --hash=sha256:{row['sha256']}" for row in sorted(rows, key=lambda item: item["name"])) + "\n").encode("utf-8")
    (output / "requirements.lock").write_bytes(raw)
    write_json(output / "environment.lock.json", {"schema_version": "ga-knapsack-environment-v1",
               "python_version": "3.12.14", "platform": "ubuntu-24.04-x86_64",
               "root_versions": {"numpy": "2.2.6", "matplotlib": "3.10.3"},
               "requirements_lock_sha256": sha256_bytes(raw), "packages": rows, "provenance": identity})
    write_file_manifest(output)
    return rows


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--expected-sha", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    rows = freeze(args.expected_sha, args.output)
    print(f"Frozen {len(rows)} exact wheel identities; no scientific calculations performed")


if __name__ == "__main__":
    main()
