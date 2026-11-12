"""Reproduce six retained logs with their original banks and RNG identities."""
import argparse
from copy import deepcopy
from pathlib import Path
from time import perf_counter

from .common import ROOT, guard_stage, read_json, read_log, require, sha256, write_json, write_log
from .configuration import CONTRACT, compatibility_cases


IGNORED_VERSION_FIELDS = frozenset({"timing_ns", "schema", "configuration_contract",
                                   "initial_parameters", "initial_population_size"})


def scientific_content(log):
    """Exclude only named version/measurement fields; retain all scientific data."""
    return {key: value for key, value in log.items() if key not in IGNORED_VERSION_FIELDS}


def run(output):
    guard_stage("technical")
    from .resources import require_enclosure
    require_enclosure(workers=1)
    from .program.ga_core import create_random_generators, run_ga, tournament_controller
    from .verification import verify_log
    output = Path(output)
    rows = []
    for case in compatibility_cases():
        destination = output / (case["case_id"] + ".json.gz")
        receipt = output / (case["case_id"] + ".receipt.json")
        reference_path = ROOT / "data/compatibility" / case["reference_file"]
        reference = read_log(reference_path)
        bank = read_json(ROOT / "data/compatibility" / (case["task_id"] + ".bank.json"))
        require(bank["seed"] == case["seed"] and bank["start_index"] == 1,
                "Retained bank identity differs")
        generators = create_random_generators(bank["seed"], bank["task_index"], bank["start_index"])
        require({name: deepcopy(rng.bit_generator.state) for name, rng in generators.items()}
                == reference["rng_initial"], "Retained six-stream initialization differs")
        started = perf_counter()
        if destination.exists():
            if receipt.exists():
                saved = read_json(receipt)
                require(saved["case"] == case and saved["log_sha256"] == sha256(destination)
                        and saved["reference_sha256"] == sha256(reference_path), "Mixed compatibility receipt")
            actual = read_log(destination)
        else:
            require(not receipt.exists(), "Compatibility receipt has lost its raw evidence")
            actual = run_ga(bank["problem"], bank["initial_population"],
                            tournament_controller(case["profile"]), generators,
                            budget=case["new_evaluations"], initial_parameters=case["initial_parameters"],
                            configuration_contract=CONTRACT)
            write_log(destination, actual, max_bytes=8 * 1024 ** 2)
        try:
            verification = verify_log(actual)
            require(scientific_content(actual) == scientific_content(reference),
                    "Retained scientific trace differs: " + case["case_id"])
        except Exception as error:
            write_json(output / (case["case_id"] + ".failure.json"),
                       {"case": case, "status": "FAILED_RETAINED", "error": str(error),
                        "error_type": type(error).__name__, "log_sha256": sha256(destination),
                        "reference_sha256": sha256(reference_path)}, max_bytes=1024 ** 2)
            raise
        row = {"case": case, "status": "EXACT_SCIENTIFIC_MATCH", "log_sha256": sha256(destination),
               "reference_sha256": sha256(reference_path), "new_evaluations": 5000,
               "known_initial_evaluations": 30, "total_logical_evaluations": 5030,
               "verification": {k: v for k, v in verification.items() if k != "derived_metrics"},
               "verification_seconds": perf_counter() - started,
               "excluded_fields": sorted(IGNORED_VERSION_FIELDS)}
        write_json(receipt, row, max_bytes=1024 ** 2)
        rows.append(row)
    require(len(rows) == 6, "Compatibility coverage differs")
    write_json(output / "compatibility_summary.json", {"status": "VERIFIED_6_OF_6", "cases": rows},
               max_bytes=1024 ** 2)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    run(parser.parse_args().output)
