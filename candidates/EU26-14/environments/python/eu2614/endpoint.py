"""Strict semantic and frozen-literal checks for the safely parsed endpoint."""

from __future__ import annotations

import math
from typing import Any

from .errors import VerificationError
from .safe_pickle import ArrayValue, ParseResult


_TOP_KEYS = {
    "suite",
    "dim",
    "func",
    "f_opt",
    "algorithm",
    "maxevals",
    "n_runs",
    "seeds",
    "errors",
    "improvements",
    "params",
    "meta",
    "cycles_per_seed",
    "pre_refine_errors_per_seed",
    "nfev_pre_refine_per_seed",
    "nfev_total_per_seed",
}
_CYCLE_KEYS = {
    "cycle",
    "nfev_start",
    "nfev_end",
    "best_f_start",
    "best_f_end",
    "improvement",
    "nfev_phase0",
    "n_basins_phase0",
    "phi_used",
    "sampling_method",
    "cycle_local_best",
    "mode",
}


def _dictionary(value: Any, keys: set[str], label: str) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != keys:
        raise VerificationError(f"{label} schema differs")
    return value


def _array(value: Any, dtype: str, shape: tuple[int, ...], label: str) -> ArrayValue:
    if not isinstance(value, ArrayValue) or value.dtype != dtype or value.shape != shape:
        raise VerificationError(f"{label} array schema differs")
    return value


def _exact_float(value: Any, literal: str, label: str) -> float:
    if not isinstance(value, float) or value != float(literal):
        raise VerificationError(f"{label} literal differs")
    return value


def _validate_params(value: Any) -> dict[str, Any]:
    params = _dictionary(value, {"cli_args", "mode", "config_C", "config_B"}, "params")
    if params["mode"] != "alt-CB":
        raise VerificationError("MSC schedule mode differs")
    cli = params["cli_args"]
    if not isinstance(cli, dict):
        raise VerificationError("MSC CLI record is absent")
    expected_cli = {
        "suite": "cec2020",
        "dim": 15,
        "runs": 51,
        "seed_start": 0,
        "maxevals": 3000000,
        "jobs": 51,
        "conly": False,
        "sampling_method": None,
    }
    for key, expected in expected_cli.items():
        if cli.get(key) != expected:
            raise VerificationError(f"MSC CLI field differs: {key}")
    for name, basins in (("config_C", 25), ("config_B", 5)):
        config = params[name]
        if not isinstance(config, dict):
            raise VerificationError(f"{name} is absent")
        if (
            config.get("n_phase0") != 4096
            or config.get("n_initial_basins") != basins
            or config.get("sampling_method") != "sobol"
        ):
            raise VerificationError(f"{name} structure-aware controls differ")
    return params


def _validate_meta(value: Any, contract: dict[str, Any]) -> dict[str, Any]:
    keys = {
        "timestamp",
        "hostname",
        "python_version",
        "numpy_version",
        "scipy_version",
        "cma_version",
        "minionpy_version",
    }
    meta = _dictionary(value, keys, "metadata")
    expected = contract["endpoint"]["environment"]
    mapping = {
        "python_version": "python",
        "numpy_version": "numpy",
        "scipy_version": "scipy",
        "cma_version": "cma",
        "minionpy_version": "minionpy",
    }
    for field, contract_field in mapping.items():
        if meta[field] != expected[contract_field]:
            raise VerificationError(f"metadata version differs: {field}")
    if not isinstance(meta["timestamp"], str) or not isinstance(meta["hostname"], str):
        raise VerificationError("metadata timestamp/hostname differs")
    return meta


def _validate_protocol(root: dict[str, Any], n_runs: int, budget: int) -> dict[str, Any]:
    errors = _array(root["errors"], "f8", (n_runs,), "errors")
    pre_errors = _array(
        root["pre_refine_errors_per_seed"], "f8", (n_runs,), "pre-refine errors"
    )
    pre_counts = _array(
        root["nfev_pre_refine_per_seed"], "i8", (n_runs,), "pre-refine counts"
    )
    total_counts = _array(
        root["nfev_total_per_seed"], "i8", (n_runs,), "total counts"
    )
    for sequence, label in ((errors.values, "errors"), (pre_errors.values, "pre-errors")):
        if any(not isinstance(item, float) or not math.isfinite(item) for item in sequence):
            raise VerificationError(f"{label} contain non-finite values")
    if any(item < 0 for item in errors.values):
        raise VerificationError("errors contain a negative value")
    improvements = root["improvements"]
    cycles_per_seed = root["cycles_per_seed"]
    if not isinstance(improvements, list) or len(improvements) != n_runs:
        raise VerificationError("improvement ledger count differs")
    if not isinstance(cycles_per_seed, list) or len(cycles_per_seed) != n_runs:
        raise VerificationError("cycle ledger count differs")
    cycle_counts: list[int] = []
    for run_index in range(n_runs):
        pre_count = pre_counts.values[run_index]
        total_count = total_counts.values[run_index]
        if not (0 < pre_count <= total_count < budget):
            raise VerificationError("run evaluation counts violate the frozen stop conflict")
        ledger = improvements[run_index]
        if not isinstance(ledger, ArrayValue) or ledger.dtype != "f8":
            raise VerificationError("improvement ledger dtype differs")
        if len(ledger.shape) != 2 or ledger.shape[1] != 2 or ledger.shape[0] < 1:
            raise VerificationError("improvement ledger shape differs")
        prior_eval = 0
        prior_value = math.inf
        for row_index in range(ledger.shape[0]):
            evaluation, objective = ledger.row(row_index)
            if evaluation != float(int(evaluation)) or not prior_eval < evaluation <= total_count:
                raise VerificationError("improvement evaluation order differs")
            if not 0 <= objective < prior_value:
                raise VerificationError("improvement objective order differs")
            prior_eval = int(evaluation)
            prior_value = objective
        cycles = cycles_per_seed[run_index]
        if not isinstance(cycles, list) or not cycles:
            raise VerificationError("cycle ledger is empty")
        prior_end = 0
        prior_best = math.inf
        for cycle_index, raw_cycle in enumerate(cycles):
            cycle = _dictionary(raw_cycle, _CYCLE_KEYS, "cycle")
            if cycle["cycle"] != cycle_index or cycle["nfev_start"] != prior_end:
                raise VerificationError("cycle index/evaluation continuity differs")
            if not cycle["nfev_start"] <= cycle["nfev_end"] <= pre_count:
                raise VerificationError("cycle evaluation interval differs")
            expected_mode = f"alt-{cycle_index % 2}"
            expected_phase0 = 4096 if cycle_index % 2 == 0 else 0
            if (
                cycle["mode"] != expected_mode
                or cycle["nfev_phase0"] != expected_phase0
                or cycle["sampling_method"] != "sobol"
            ):
                raise VerificationError("cycle alternation/reuse differs")
            if not isinstance(cycle["n_basins_phase0"], int) or cycle["n_basins_phase0"] < 0:
                raise VerificationError("cycle basin count differs")
            if cycle["nfev_start"] == cycle["nfev_end"] and not (
                cycle_index % 2 == 1
                and cycle["n_basins_phase0"] == 0
                and cycle["best_f_start"] == cycle["best_f_end"]
                and cycle["improvement"] == 0.0
            ):
                raise VerificationError("zero-evaluation reused-cycle semantics differ")
            if not isinstance(cycle["phi_used"], float) or not math.isfinite(cycle["phi_used"]):
                raise VerificationError("cycle phi differs")
            if cycle_index == 0:
                if not math.isinf(cycle["best_f_start"]) or not math.isinf(
                    cycle["improvement"]
                ):
                    raise VerificationError("first-cycle infinity semantics differ")
            else:
                if cycle["best_f_start"] != prior_best:
                    raise VerificationError("cycle best continuity differs")
                expected_improvement = cycle["best_f_start"] - cycle["best_f_end"]
                if cycle["improvement"] != expected_improvement:
                    raise VerificationError("cycle improvement arithmetic differs")
            if not isinstance(cycle["best_f_end"], float) or not math.isfinite(
                cycle["best_f_end"]
            ):
                raise VerificationError("cycle best endpoint differs")
            if cycle["best_f_end"] > prior_best:
                raise VerificationError("cycle best is not monotone")
            prior_end = cycle["nfev_end"]
            prior_best = cycle["best_f_end"]
        if prior_end != pre_count:
            raise VerificationError("last cycle does not bind pre-refine count")
        cycle_counts.append(len(cycles))
    return {
        "runs_checked": n_runs,
        "seeds_contiguous": True,
        "improvements_strict": True,
        "cycles_contiguous": True,
        "alternation": "alt-0/alt-1",
        "phase0_reuse": "even=4096,odd=0",
        "cycle_count_min": min(cycle_counts),
        "cycle_count_max": max(cycle_counts),
        "all_nfev_total_below_budget": True,
    }


def verify_endpoint(parsed: ParseResult, contract: dict[str, Any]) -> dict[str, Any]:
    root = _dictionary(parsed.value, _TOP_KEYS, "pickle root")
    expected = contract["endpoint"]
    scalar_pairs = {
        "suite": expected["suite"],
        "dim": expected["dimension"],
        "func": f"f{expected['function']}",
        "algorithm": expected["algorithm"],
        "maxevals": expected["budget"],
        "n_runs": expected["n_runs"],
    }
    for field, value in scalar_pairs.items():
        if root[field] != value:
            raise VerificationError(f"endpoint field differs: {field}")
    _exact_float(root["f_opt"], expected["f_opt"], "f_opt")
    seeds = _array(root["seeds"], "i8", (expected["n_runs"],), "seeds")
    if seeds.values != tuple(range(51)):
        raise VerificationError("seed ledger differs")
    params = _validate_params(root["params"])
    meta = _validate_meta(root["meta"], contract)
    protocol = _validate_protocol(root, expected["n_runs"], expected["budget"])

    run0 = expected["run0"]
    errors = root["errors"]
    _exact_float(errors.scalar(0), run0["error"], "run0 error")
    ledger0 = root["improvements"][0]
    if ledger0.shape != tuple(run0["improvements_shape"]):
        raise VerificationError("run0 improvement shape differs")
    first = ledger0.row(0)
    last = ledger0.row(-1)
    for index, literal in enumerate(run0["first_improvement"]):
        _exact_float(first[index], literal, f"run0 first improvement {index}")
    for index, literal in enumerate(run0["last_improvement"]):
        _exact_float(last[index], literal, f"run0 last improvement {index}")
    cycles0 = root["cycles_per_seed"][0]
    if len(cycles0) != run0["cycle_count"]:
        raise VerificationError("run0 cycle count differs")
    for frozen in run0["cycles"]:
        cycle = cycles0[frozen["index"]]
        for field in ("nfev_start", "nfev_end", "nfev_phase0"):
            contract_field = "phase0_evaluations" if field == "nfev_phase0" else field
            if cycle[field] != frozen[contract_field]:
                raise VerificationError(f"run0 cycle {frozen['index']} {field} differs")
        if cycle["n_basins_phase0"] != frozen["basins"] or cycle["mode"] != frozen["mode"]:
            raise VerificationError("run0 cycle basin/mode differs")
        _exact_float(cycle["best_f_end"], frozen["best_end"], "run0 cycle best_end")
        _exact_float(cycle["phi_used"], frozen["phi"], "run0 cycle phi")
        if "best_start" in frozen:
            _exact_float(cycle["best_f_start"], frozen["best_start"], "run0 cycle best_start")
        if "improvement" in frozen:
            _exact_float(cycle["improvement"], frozen["improvement"], "run0 cycle improvement")
    _exact_float(
        root["pre_refine_errors_per_seed"].scalar(0),
        run0["pre_refine_error"],
        "run0 pre-refine error",
    )
    if (
        root["nfev_pre_refine_per_seed"].scalar(0) != run0["nfev_pre_refine"]
        or root["nfev_total_per_seed"].scalar(0) != run0["nfev_total"]
    ):
        raise VerificationError("run0 pre/total evaluation count differs")
    return {
        "safe_pickle_gate": "PASS_SAFE_PICKLE_PARSE",
        "endpoint_gate": "PASS_FROZEN_ENDPOINT",
        "opcode_counts": parsed.opcode_counts,
        "symbolic_globals": list(parsed.symbolic_globals),
        "metadata": meta,
        "protocol": protocol,
        "params": {
            "mode": params["mode"],
            "phase0_C": params["config_C"]["n_phase0"],
            "phase0_B": params["config_B"]["n_phase0"],
            "basins_C": params["config_C"]["n_initial_basins"],
            "basins_B": params["config_B"]["n_initial_basins"],
        },
    }
