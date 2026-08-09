from __future__ import annotations

import argparse
import dataclasses
import json
import sys
from pathlib import Path

PYTHON_ROOT = Path(__file__).resolve().parent
if str(PYTHON_ROOT) not in sys.path:
    sys.path.insert(0, str(PYTHON_ROOT))

from eu2616.canonical import bind_report, write_new_json
from eu2616.contract import candidate_root, load_contract
from eu2616.dataset import EvidenceGapError, assert_table7_replay_ready, audit_yeast
from eu2616.source import assert_same_identity, authenticate_checkout, probe_alg_source
from eu2616.transition import ControlState, java_float, transition_generation


def _run_fixtures() -> dict[str, object]:
    fixture_path = candidate_root() / "fixtures" / "transition_cases.json"
    fixture = json.loads(fixture_path.read_text(encoding="utf-8"))
    tolerance = float(fixture["tolerance"])
    names: list[str] = []
    for case in fixture["cases"]:
        state = ControlState(**case["state"])
        next_state, event = transition_generation(
            state,
            generation=case["generation"],
            current_best_fitness=case["current_best_fitness"],
            current_average_fitness=case["current_average_fitness"],
            max_generations=case["max_generations"],
        )
        observed = {**dataclasses.asdict(next_state), **dataclasses.asdict(event)}
        for key, expected in case["expected"].items():
            actual = observed[key]
            if isinstance(expected, float):
                source_expected = (
                    java_float(expected)
                    if key in {"best_average_fitness", "best_fitness"}
                    else expected
                )
                if abs(actual - source_expected) > tolerance:
                    raise AssertionError(
                        f"{case['name']} {key}: {actual} != {source_expected}"
                    )
            elif actual != expected:
                raise AssertionError(f"{case['name']} {key}: {actual!r} != {expected!r}")
        if abs(next_state.crossover_probability + next_state.mutation_probability - 1.0) > tolerance:
            raise AssertionError(f"{case['name']} violates pc+pm=1")
        names.append(case["name"])
    return {"status": "PASS_SOURCE_TRANSITION", "case_count": len(names), "cases": names}


def run(checkout: Path) -> dict[str, object]:
    contract = load_contract()
    before = authenticate_checkout(checkout, contract)
    token_probe = probe_alg_source(checkout, contract)
    transitions = _run_fixtures()
    yeast = audit_yeast(checkout, contract)
    try:
        assert_table7_replay_ready(yeast, contract)
    except EvidenceGapError as error:
        blocked = {"status": "BLOCKED_AS_PREREGISTERED", "reason": str(error)}
    else:
        raise AssertionError("Table 7 replay readiness must fail closed")
    after = authenticate_checkout(checkout, contract)
    assert_same_identity(before, after)
    return bind_report(
        {
            "schema_version": "1.0.0",
            "candidate_id": "EU26-16",
            "status": "PASS_FORMULA_AND_SOURCE_TRANSITION_ONLY",
            "readiness": contract["readiness"],
            "paper_mapping": contract["paper_mapping"],
            "source_gate": "PASS_SOURCE_IDENTITY",
            "source": before,
            "source_token_probe": token_probe,
            "transition_gate": transitions,
            "dataset_gate": {
                "status": "PASS_DATASET_STRUCTURE",
                "inputs": len(yeast.input_names),
                "labels": len(yeast.label_names),
                "train_rows": yeast.train_rows,
                "test_rows": yeast.test_rows,
                "seeds": list(yeast.seeds),
                "missing_paths": list(yeast.missing_paths),
            },
            "table_7_gate": blocked,
            "blockers": list(yeast.gaps),
            "empirical_claim_made": False,
            "forbidden_claims": contract["forbidden_claims"],
        }
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--checkout", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args()
    report = run(arguments.checkout)
    write_new_json(arguments.output, report)
    print(
        f"EU26-16 source/formula validation: {report['status']}; "
        f"Table 7={report['table_7_gate']['status']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
