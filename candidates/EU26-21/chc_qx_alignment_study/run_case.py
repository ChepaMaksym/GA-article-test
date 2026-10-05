#!/usr/bin/env python3
"""Run three QX searches from authenticated preparation, then diagnostics/test.

Training-only objects are the sole search inputs. All terminal masks and all
search results are persisted before the holdout loader is called. Diagnostics
have fresh uncached objectives and cannot feed information back into search.
"""
from __future__ import annotations

import argparse
from pathlib import Path
import sys
from typing import Any, Mapping

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np  # noqa: E402

from common_bridge.model_evidence import evaluate_and_persist  # noqa: E402
from chc_qx_alignment_study.contract import (  # noqa: E402
    CASE_SCHEMA, CASE_SEEDS, PROTOCOL_ID, PROTOCOL_SHA256, SEARCH_ARMS, THIS_DIRECTORY,
    add_class_metrics, authenticate, canonical_sha256, ensure_empty_output, file_sha256,
    load_registered_preparation, require, scalar_score, validate_mask,
    write_json, write_manifest,
)
from chc_qx_alignment_study.data import (  # noqa: E402
    array_sha256, load_terminal_holdout, objective_for, prepare_training,
    source_density_masks,
)


class CountedObjective:
    """Physical call counters, never a cache or a shared stochastic state."""

    def __init__(self, objective: Any) -> None:
        self.objective = objective
        self.calls = 0
        self.tree_fits = 0
        self.duplicate_queries = 0
        self.seen: set[tuple[int, ...]] = set()

    def __call__(self, mask: Any) -> float:
        normalized = validate_mask(list(mask))
        score = scalar_score(self.objective(normalized))
        self.calls += 1
        self.tree_fits += int(bool(sum(normalized)))
        self.duplicate_queries += int(normalized in self.seen)
        self.seen.add(normalized)
        return score

    def counts(self) -> dict[str, int]:
        return {"physical_calls": self.calls, "actual_tree_fits": self.tree_fits,
                "unique_masks": len(self.seen), "duplicate_queries": self.duplicate_queries}


def verify_reconstructed_training(prepared: Any, preparation: Mapping[str, Any]) -> tuple[tuple[tuple[int, ...], ...], list[float]]:
    require(prepared.metadata == preparation["training_data"], "reconstructed training/split/preprocessor identity mismatch")
    sampling = preparation["sampling"]
    rows = sampling["selected_rows"]
    require(isinstance(rows, list) and all(type(index) is int for index in rows), "invalid selected row positions")
    indices = np.asarray(rows, dtype=np.int64)
    require(indices.ndim == 1 and len(indices) > 5000 and len(indices) == sampling["selected_row_count"]
            and len(np.unique(indices)) == len(indices)
            and indices.min() >= 0 and indices.max() < len(prepared.y_train), "selected row positions invalid")
    require(array_sha256(indices) == sampling["selected_rows_sha256"], "selected row order hash mismatch")
    require(prepared.train_raw_indices[indices].tolist() == sampling["selected_raw_row_ids"], "selected raw row identity mismatch")
    masks = tuple(validate_mask(mask) for mask in preparation["initial_masks"])
    require(len(masks) == 50 and masks == source_density_masks(50, seed=preparation["seed"] + 3000003, nonempty=False),
            "initial mask bank differs from registered source-density stream")
    require(canonical_sha256(preparation["initial_masks"]) == preparation["initial_masks_sha256"], "initial mask hash mismatch")
    scores = [scalar_score(score) for score in preparation["initial_scores"]]
    require(len(scores) == 50 and canonical_sha256(preparation["initial_scores"]) == preparation["initial_scores_sha256"],
            "initial scalar score bank identity mismatch")
    require(all(score == 0.0 for mask, score in zip(masks, scores) if not sum(mask)), "empty initial mask score mismatch")
    return masks, scores


def _write_case(directory: Path, row: dict[str, Any], *, artifact_name: str) -> dict[str, Any]:
    write_json(directory / "case.json", row)
    write_json(directory / "status.json", {"schema": "eu26-21-qx-status-v1", "seed": row["seed"],
                                           "status": row["status"], "provenance": row["provenance"]})
    write_manifest(directory, seed=row["seed"], artifact_name=artifact_name, provenance=row["provenance"])
    return row


def normalize_terminal_metrics(metrics: Mapping[str, Any]) -> dict[str, Any]:
    """Present actual record counts as integers; weight sums remain floating."""
    result = add_class_metrics(metrics)
    block = result["unweighted"]
    matrix = block["confusion_matrix"]
    require(all(type(value) in (int, float) and float(value).is_integer() and value >= 0
                for row in matrix for value in row), "unweighted confusion counts must be integers")
    block["confusion_matrix"] = [[int(value) for value in row] for row in matrix]
    for name in ("negative_support", "positive_support"):
        if name in block:
            require(float(block[name]).is_integer(), "unweighted class support is fractional")
            block[name] = int(block[name])
    for item in block["classes"].values():
        item["support"] = int(item["support"])
    return result


def run_case(*, train: Path, test: Path, upstream: Path, seed: int,
             expected_sha: str, preparation_path: Path, registry_path: Path,
             output: Path, protocol_path: Path = THIS_DIRECTORY / "protocol.json",
             artifact_name: str | None = None) -> dict[str, Any]:
    ensure_empty_output(output)
    protocol, provenance = authenticate(protocol_path=protocol_path, expected_sha=expected_sha, upstream=upstream)
    require(type(seed) is int and seed in CASE_SEEDS, "case seed outside registered ledger")
    preparation, source = load_registered_preparation(preparation_path, registry_path, seed=seed, expected_sha=expected_sha)
    name = artifact_name or f"eu26-21-qx-case-{seed}-{provenance['run_id']}-{provenance['run_attempt']}"
    common = {"schema": CASE_SCHEMA, "seed": seed, "provenance": provenance,
              "protocol_id": PROTOCOL_ID, "protocol_sha256": PROTOCOL_SHA256,
              "artifact_name": name, "preparation": source,
              "registry_sha256": source["registry_sha256"],
              "preparation_sha256": source["preparation"]["sha256"],
              "initial_masks": preparation["initial_masks"], "initial_scores": preparation["initial_scores"],
              "sampler_summary": {key: value for key, value in preparation["sampling"].items()
                                  if key not in ("selected_rows", "selected_raw_row_ids")},
              "training_data": preparation["training_data"]}
    if preparation["status"] != "PASS_PREPARATION":
        return _write_case(output, {**common, "status": "NOT_EVALUABLE_SAMPLER", "arms": {},
                                    "counts": {"search_active_physical_calls": 0, "full_checkpoint_physical_calls": 0,
                                               "diagnostic_calls": 0, "test_evaluations": 0}}, artifact_name=name)

    require(file_sha256(train) == protocol["data"]["train_sha256"], "train data hash mismatch")
    prepared = prepare_training(train, seed=seed)
    masks, scores = verify_reconstructed_training(prepared, preparation)
    active = objective_for(prepared, preparation["sampling"]["selected_rows"])
    full = objective_for(prepared)
    # Imports occur only after upstream identity has been authenticated. The
    # source-gate module installs isolated native CHC globals, not a local copy.
    from chc_qx_alignment_study.search import run_qx_search
    from chc_qx_alignment_study.diagnostics import certify_snapshot
    from chc_qx_alignment_study.source_gate import load_evolution

    loaded = load_evolution(upstream)
    evolution, deap_creator = loaded.Evolution, loaded.creator
    results: dict[str, Any] = {}
    counts: dict[str, Any] = {}
    traces: dict[str, Any] = {}
    for arm in SEARCH_ARMS:
        active_counted, full_counted = CountedObjective(active), CountedObjective(full)
        result = run_qx_search(
            arm=arm, initial_masks=masks, initial_scores=scores,
            active_objective=active_counted, full_objective=full_counted,
            seed=seed, evolution=evolution, deap_creator=deap_creator,
            chunk_generations=10, no_change_limit=2, max_chunks=20,
        )
        require(result["active_physical_calls"] == active_counted.calls, "active physical ledger mismatch")
        require(result["active_logical_calls"] == active_counted.calls + 50, "active initialization replay mismatch")
        require(result["full_calls"] == full_counted.calls, "full checkpoint ledger mismatch")
        results[arm] = result
        counts[arm] = {"active": active_counted.counts(), "full_checkpoints": full_counted.counts()}
        trace_name = f"trace-{arm}.json"
        traces[arm] = {"file": trace_name, **write_json(output / trace_name,
            {"seed": seed, "arm": arm, "provenance": provenance, "preparation": source, **result})}
    terminal = {arm: {"mask": result["selected_mask"], "full_validation_wba": result["full_validation_wba"]}
                for arm, result in results.items()}
    freeze = {"schema": "eu26-21-qx-terminal-mask-freeze-v1", "seed": seed, "provenance": provenance,
              "preparation": source, "arms": terminal, "selected_by": "full_internal_training_validation_only",
              "test_evaluations_so_far": 0}
    freeze_identity = {"file": "terminal-masks.json", **write_json(output / "terminal-masks.json", freeze)}

    diagnostics: dict[str, Any] = {}
    diagnostic_files: dict[str, Any] = {}
    for arm, result in results.items():
        diagnostic_active, diagnostic_full = CountedObjective(active), CountedObjective(full)
        diagnostics[arm] = certify_snapshot(snapshot=result["snapshot"], active_objective=diagnostic_active,
                                             full_objective=diagnostic_full)
        require(diagnostic_active.calls == diagnostic_full.calls == 41, "snapshot certification must use 41 + 41 calls")
        require(diagnostics[arm]["approximate"]["center_wba"] == result["snapshot"]["active_wba"],
                "independent snapshot center did not reproduce its active WBA")
        counts[arm]["diagnostic_active"] = diagnostic_active.counts()
        counts[arm]["diagnostic_full"] = diagnostic_full.counts()
        diagnostic_name = f"diagnostic-{arm}.json"
        diagnostic_files[arm] = {"file": diagnostic_name, **write_json(output / diagnostic_name,
                                {"seed": seed, "arm": arm, "provenance": provenance, **diagnostics[arm]})}

    valid_arms = [arm for arm in SEARCH_ARMS if terminal[arm]["mask"] is not None]
    terminal_prepared = (load_terminal_holdout(prepared, test,
                         expected_test_sha256=protocol["data"]["test_sha256"]) if valid_arms else None)
    arms: dict[str, Any] = {}
    models: dict[str, Any] = {}
    for arm in SEARCH_ARMS:
        result = results[arm]
        summary = {key: value for key, value in result.items()
                   if key not in ("active_trace", "generation_trace", "checkpoints", "full_evaluations")}
        summary.update({"trace": traces[arm], "diagnostics": diagnostic_files[arm], "counts": counts[arm]})
        if arm in valid_arms:
            mask = validate_mask(result["selected_mask"])
            require(sum(mask) > 0, "registered full winner cannot be empty")
            metrics, model = evaluate_and_persist(terminal_prepared, mask,
                path=output / f"model-{arm}.joblib", seed=seed, arm=arm, provenance=provenance)
            summary.update({"test_metrics": normalize_terminal_metrics(metrics), "test_evaluations": 1,
                            "evaluation_status": "PASS_VALID_FINAL_MASK"})
            models[arm] = model
        else:
            summary.update({"test_metrics": None, "test_evaluations": 0,
                            "evaluation_status": "NOT_EVALUABLE_NO_FULL_WINNER"})
        arms[arm] = summary
    row = {**common, "status": "PASS_CASE_COMPLETE" if len(valid_arms) == 3 else "CASE_WITH_NOT_EVALUABLE_ARM",
           "arms": arms, "models": models, "terminal_masks_freeze": freeze_identity,
           "counts": {"shared_initial_physical_calls": 50,
                      "shared_initial_actual_tree_fits": preparation["counts"]["shared_initial_actual_tree_fits"],
                      "search_active_physical_calls": sum(counts[arm]["active"]["physical_calls"] for arm in SEARCH_ARMS),
                      "full_checkpoint_physical_calls": sum(counts[arm]["full_checkpoints"]["physical_calls"] for arm in SEARCH_ARMS),
                      "diagnostic_calls": 246, "test_evaluations": len(valid_arms)}}
    return _write_case(output, row, artifact_name=name)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--train", type=Path, required=True)
    parser.add_argument("--test", type=Path, required=True)
    parser.add_argument("--upstream", type=Path, required=True)
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--expected-sha", required=True)
    parser.add_argument("--expected-protocol-sha256", default=PROTOCOL_SHA256)
    parser.add_argument("--protocol", type=Path, default=THIS_DIRECTORY / "protocol.json")
    parser.add_argument("--preparation", type=Path, required=True)
    parser.add_argument("--registry", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--artifact-name")
    args = parser.parse_args()
    require(args.expected_protocol_sha256 == PROTOCOL_SHA256, "unregistered protocol requested")
    ensure_empty_output(args.output)
    try:
        row = run_case(train=args.train, test=args.test, upstream=args.upstream, seed=args.seed,
                       expected_sha=args.expected_sha, preparation_path=args.preparation,
                       registry_path=args.registry, output=args.output,
                       protocol_path=args.protocol, artifact_name=args.artifact_name)
    except Exception as error:
        write_json(args.output / "failure-status.json", {"schema": "eu26-21-qx-status-v1", "seed": args.seed,
                   "status": "FAIL_INFRASTRUCTURE_OR_SCHEMA", "error_type": type(error).__name__, "error": str(error)})
        raise
    print(f"seed={row['seed']} {row['status']}")


if __name__ == "__main__":
    main()
