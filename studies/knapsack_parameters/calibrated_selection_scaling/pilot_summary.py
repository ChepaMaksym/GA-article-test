"""Check exact technical coverage and forecast costs without ranking pilot quality."""
import argparse
from pathlib import Path

from .common import (ROOT, canonical_sha256, guard_stage, read_json, require,
                     safe_relative, sha256, write_json)
from .configuration import SOURCE_COMMIT, compatibility_cases, main_cases, technical_cases
from .resources import require_enclosure


def summarize(pilot_root, meta_root, compatibility_root, inputs_root, output):
    guard_stage("technical")
    require_enclosure(workers=1)
    expected = {row["case_id"]: row for row in technical_cases()}
    prepared_path = Path(inputs_root) / "registry.json"
    prepared = read_json(prepared_path)
    prepared_identity = {"bytes": prepared_path.stat().st_size, "sha256": sha256(prepared_path)}
    require(prepared.get("schema") == "calibrated-selection-prepared-inputs-v1"
            and prepared.get("status") == "PREPARED_CERTIFIED" and prepared.get("stage") == "technical"
            and prepared.get("source_commit") == SOURCE_COMMIT
            and prepared.get("case_identities") == list(expected.values())
            and len(prepared["tasks"]) == 66 and len(prepared["banks"]) == 6
            and prepared["search_evaluations"] == 0,
            "All 66 dual references and six technical banks must share the frozen preparation")
    found, locations = {}, {}
    for path in Path(pilot_root).rglob("*.receipt.json"):
        row = read_json(path)
        case = row.get("case", {})
        identifier = case.get("case_id")
        require(identifier in expected and identifier not in found and case == expected[identifier],
                "Missing, duplicated or foreign technical identity")
        require(row.get("status") == "VERIFIED_ATOMICALLY_RETAINED"
                and row.get("source_manifest_sha256") == sha256(ROOT / "source_manifest.json")
                and row.get("identity_sha256") == canonical_sha256(row["identity"])
                and row["identity"]["case"] == case
                and row["identity"].get("prepared_registry") == prepared_identity
                and row["identity"].get("source_manifest_sha256") == sha256(ROOT / "source_manifest.json"),
                "Mixed source revision or incomplete independent verification")
        for key in ("log", "observations"):
            descriptor = row[key]
            artifact = safe_relative(path.parent, descriptor["path"])
            require(artifact.is_file() and artifact.stat().st_size == descriptor["bytes"]
                    and sha256(artifact) == descriptor["sha256"], "Retained technical evidence differs")
        require(row["verification"].get("verification_status") == "VERIFIED"
                and row["logical_total_evaluations"] == 100000,
                "Technical replay or total evaluation count differs")
        found[identifier], locations[identifier] = row, path.parent
    require(set(found) == set(expected), "All 21 technical identities are required")
    tests = read_json(Path(meta_root) / "tests.json")
    require(tests.get("status") == "PASSED" and not tests.get("skipped") and tests.get("tests_run") == 60,
            "Technical tests are incomplete")
    compatibility = read_json(Path(compatibility_root) / "compatibility_summary.json")
    require(compatibility.get("status") == "VERIFIED_6_OF_6"
            and {row["case"]["case_id"] for row in compatibility["cases"]}
            == {row["case_id"] for row in compatibility_cases()}
            and len(compatibility["cases"]) == 6, "All six retained comparisons are required")
    for row in compatibility["cases"]:
        raw = Path(compatibility_root) / (row["case"]["case_id"] + ".json.gz")
        require(row["status"] == "EXACT_SCIENTIFIC_MATCH" and sha256(raw) == row["log_sha256"],
                "Compatibility raw evidence differs")
    groups = []
    for n in (100, 500):
        for role in ("k2", "k3", "adaptive", "common"):
            rows = [r for r in found.values() if r["case"]["n"] == n and r["case"]["role"] == role]
            count = sum(c["n"] == n and c["role"] == role for c in main_cases())
            if not count:
                continue
            require(len(rows) == 3, "Cost sample must include all three task types")
            durations = [r["timing_ns"]["total"] / 1e9 for r in rows]
            mean = sum(durations) / len(durations)
            largest = max(durations)
            byte_maximum = max(r["log"]["bytes"] + r["observations"]["bytes"] for r in rows)
            groups.append({"n": n, "role": role, "pilot_cases": len(rows), "main_cases": count,
                           "mean_measured_case_seconds": mean, "maximum_measured_case_seconds": largest,
                           "sum_case_runner_minutes_mean_scenario": count * mean / 60,
                           "sum_case_runner_minutes_maximum_scenario": count * largest / 60,
                           "maximum_case_evidence_bytes": byte_maximum,
                           "main_evidence_bytes_maximum_scenario": count * byte_maximum,
                           "measured_components_mean_seconds": {
                               key: sum(r["timing_ns"].get(key, 0) for r in rows) / (len(rows) * 1e9)
                               for key in ("search", "replay", "compression", "observation", "total")}})
    artifact_bytes = sum(path.stat().st_size for base in (pilot_root, meta_root, compatibility_root, inputs_root)
                         for path in Path(base).rglob("*") if path.is_file())
    require(artifact_bytes <= 2 * 1024 ** 3 - 64 * 1024 ** 2,
            "Combined retained technical materials leave no summary allowance")
    forecast = {"status": "PROVISIONAL_MEASURED_CASE_COSTS", "main_authorized": False,
                "physical_main_cases": 210, "total_logical_main_evaluations": 21000000,
                "groups": groups,
                "sequential_case_minutes_mean_scenario": sum(g["sum_case_runner_minutes_mean_scenario"] for g in groups),
                "sequential_case_minutes_maximum_scenario": sum(g["sum_case_runner_minutes_maximum_scenario"] for g in groups),
                "evidence_bytes_maximum_scenario": sum(g["main_evidence_bytes_maximum_scenario"] for g in groups),
                "prepared_seconds": prepared["preparation_ns"] / 1e9,
                "measured_retained_technical_bytes": artifact_bytes,
                "parallelism_assumption": "case times include pilot contention; no automatic division by two",
                "remaining_cost_measurements": ["GitHub job setup and runtime acquisition", "artifact upload/download",
                                                "statistics and figures", "fresh-task cost variability"],
                "safety_scenarios": [1.5, 2.0],
                "interpretation": "Three old task types estimate case cost, not final accuracy or a runtime guarantee",
                "next_gate": "Separate measured total estimate and explicit main-series resource permission"}
    output = Path(output)
    write_json(output / "forecast.json", forecast, max_bytes=16 * 1024 ** 2)
    write_json(output / "technical_summary.json",
               {"status": "TECHNICAL_EVIDENCE_VERIFIED", "pilot_cases": 21, "compatibility_cases": 6,
                "tests_run": tests["tests_run"], "certified_tasks": 66,
                "source_manifest_sha256": sha256(ROOT / "source_manifest.json"),
                "statistical_intervals_recomputed": False, "main_search_runs": 0,
                "main_authorized": False, "pilot_quality_used_for_selection": False},
               max_bytes=16 * 1024 ** 2)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("pilot-root", "meta-root", "compatibility-root", "inputs-root", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args()
    summarize(args.pilot_root, args.meta_root, args.compatibility_root, args.inputs_root, args.output)
