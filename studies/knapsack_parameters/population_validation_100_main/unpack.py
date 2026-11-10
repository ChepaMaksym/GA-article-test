"""Safely unpack the small, already certified technical input artifact in CI."""
import argparse
from pathlib import Path

from .common import HERE, guard_main, require, sha
from studies.knapsack_parameters.population_size_study.io_utils import extract_artifact


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    protocol = guard_main()
    archive = HERE / "data" / "certified_inputs_42780269269.zip"
    require(sha(archive) == protocol["certified_inputs_zip_sha256"], "Retained input artifact differs")
    extract_artifact(archive, args.out, compressed_limit=1024**2, expanded_limit=128 * 1024**2)
    require(sha(args.out / "manifest.json") == protocol["technical_input_manifest_sha256"], "Certified input manifest differs")
    print("Retained CI input artifact unpacked and authenticated; no GA executed.", flush=True)


if __name__ == "__main__":
    main()
