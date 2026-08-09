"""Independent source-formula controls for the frozen EU26-13 fixtures."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Callable, Iterable

from .contract import exact, require
from .errors import VerificationError


@dataclass
class BIPOPState:
    lambda_init: int
    mu_factor: float
    budget: int
    used_budget: int = 0
    budget_small: int = 0
    budget_large: int = 0
    lambda_large: int = 0

    def large(self) -> bool:
        return self.budget_large >= self.budget_small and self.budget_large > 0

    def restart(
        self,
        total_evaluations: int,
        uniform_population: float,
        uniform_sigma: float,
        sigma0: float,
    ) -> dict[str, Any]:
        last_used_budget = total_evaluations - self.used_budget
        require(last_used_budget >= 0, "A7_CONTROLS", "BIPOP evaluation counter regressed")
        self.used_budget += last_used_budget
        remaining_budget = self.budget - self.used_budget
        require(remaining_budget >= 0, "A7_CONTROLS", "BIPOP budget underflow")

        previous_large = self.large()
        if self.lambda_large == 0:
            self.lambda_large = self.lambda_init * 2
            self.budget_small = remaining_budget // 2
            self.budget_large = remaining_budget - self.budget_small
        elif previous_large:
            require(self.budget_large >= last_used_budget, "A7_CONTROLS", "large-budget underflow")
            self.budget_large -= last_used_budget
            self.lambda_large *= 2
        else:
            require(self.budget_small >= last_used_budget, "A7_CONTROLS", "small-budget underflow")
            self.budget_small -= last_used_budget

        require(0.0 <= uniform_population < 1.0, "A7_CONTROLS", "invalid population draw")
        require(0.0 <= uniform_sigma < 1.0, "A7_CONTROLS", "invalid sigma draw")
        proposal = math.floor(
            self.lambda_init
            * math.pow(
                0.5 / self.lambda_large / self.lambda_init,
                math.pow(uniform_population, 2.0),
            )
        )
        lambda_small = proposal + (proposal % 2)
        selected_large = self.large()
        population = max(2, self.lambda_large if selected_large else lambda_small)
        mu = max(1, int(population * self.mu_factor))
        sigma = sigma0 if selected_large else sigma0 * math.pow(10.0, -2.0 * uniform_sigma)
        return {
            "last_used_budget": last_used_budget,
            "used_budget": self.used_budget,
            "remaining_budget": remaining_budget,
            "budget_small": self.budget_small,
            "budget_large": self.budget_large,
            "lambda_large": self.lambda_large,
            "lambda_small_floor": proposal,
            "lambda_small": lambda_small,
            "selected_large": selected_large,
            "lambda": population,
            "mu": mu,
            "sigma": sigma,
        }


def seed_schedule(instances: int, runs_per_instance: int, multiplier: int) -> list[list[int]]:
    return [
        [instance, run, multiplier * run]
        for instance in range(1, instances + 1)
        for run in range(runs_per_instance)
    ]


def repelling_radius(
    dimension: int,
    volume: float,
    sigma0: float,
    coverage: float,
    finalized_restarts: int,
    n_rep: int,
) -> tuple[float, float]:
    volume_per_n = volume / (sigma0 * coverage * finalized_restarts)
    gamma_factor = math.pow(math.gamma(dimension / 2.0 + 1.0), 1.0 / dimension) / math.sqrt(math.pi)
    radius = math.pow(volume_per_n * n_rep, 1.0 / dimension) * gamma_factor
    return gamma_factor, radius


def csa_update(sigma: float, cs: float, damps: float, ps_norm: float, chi_n: float) -> float:
    return sigma * math.exp((cs / damps) * ((ps_norm / chi_n) - 1.0))


def hill_valley(
    endpoint_y_a: float,
    endpoint_y_b: float,
    intermediate_values: Iterable[float],
) -> tuple[bool, int]:
    maximum = max(endpoint_y_a, endpoint_y_b)
    evaluations = 0
    for value in intermediate_values:
        evaluations += 1
        if maximum < value:
            return False, evaluations
    return True, evaluations


def _close(actual: float, expected: float, field: str, *, tolerance: float = 2e-15) -> None:
    require(math.isfinite(actual), "A7_CONTROLS", f"{field} is non-finite")
    if not math.isclose(actual, expected, rel_tol=tolerance, abs_tol=tolerance):
        raise VerificationError("A7_CONTROLS", f"{field}: expected {expected!r}, got {actual!r}")


def run_controls(contract: dict[str, Any]) -> dict[str, Any]:
    fixtures = contract["control_fixtures"]

    seed_cfg = fixtures["seed_schedule"]
    schedule = seed_schedule(
        seed_cfg["instances"], seed_cfg["runs_per_instance"], seed_cfg["seed_multiplier"]
    )
    exact(len(schedule), seed_cfg["expected_rows"], "A7_CONTROLS", "seed rows")
    exact(schedule[0], seed_cfg["expected_first"], "A7_CONTROLS", "first seed row")
    exact(
        schedule[seed_cfg["runs_per_instance"]],
        seed_cfg["expected_instance2_first"],
        "A7_CONTROLS",
        "instance-2 first seed row",
    )
    exact(schedule[-1], seed_cfg["expected_last"], "A7_CONTROLS", "last seed row")

    bipop = fixtures["bipop"]
    state = BIPOPState(
        lambda_init=bipop["lambda_init"],
        mu_factor=bipop["mu_init"] / bipop["lambda_init"],
        budget=bipop["budget"],
    )
    first_cfg = bipop["first_restart"]
    first = state.restart(
        first_cfg["evaluations"],
        first_cfg["uniform_population"],
        0.0,
        first_cfg["expected_sigma"],
    )
    for field, expected_key in (
        ("budget_small", "expected_budget_small"),
        ("budget_large", "expected_budget_large"),
        ("lambda_large", "expected_lambda_large"),
        ("lambda_small_floor", "expected_lambda_small_proposal"),
        ("lambda", "expected_lambda"),
        ("mu", "expected_mu"),
    ):
        exact(first[field], first_cfg[expected_key], "A7_CONTROLS", f"first BIPOP {field}")
    _close(first["sigma"], first_cfg["expected_sigma"], "first BIPOP sigma")

    second_cfg = bipop["second_restart"]
    second = state.restart(
        second_cfg["evaluations"],
        second_cfg["uniform_population"],
        second_cfg["uniform_sigma"],
        first_cfg["expected_sigma"],
    )
    for field, expected_key in (
        ("budget_small", "expected_budget_small"),
        ("budget_large", "expected_budget_large"),
        ("lambda_large", "expected_lambda_large"),
        ("lambda_small", "expected_lambda_small"),
        ("lambda", "expected_lambda"),
        ("mu", "expected_mu"),
    ):
        exact(second[field], second_cfg[expected_key], "A7_CONTROLS", f"second BIPOP {field}")
    _close(second["sigma"], second_cfg["expected_sigma"], "second BIPOP sigma")

    radius_cfg = fixtures["repelling_radius"]
    gamma_factor, radius = repelling_radius(
        radius_cfg["dimension"],
        float(radius_cfg["volume"]),
        radius_cfg["sigma0"],
        radius_cfg["coverage"],
        radius_cfg["finalized_restarts"],
        radius_cfg["n_rep"],
    )
    shrinkage = math.pow(0.99, 1.0 / radius_cfg["dimension"])
    effective = math.pow(shrinkage, radius_cfg["attempts"]) * radius
    _close(gamma_factor, radius_cfg["expected_gamma_factor"], "gamma factor")
    _close(radius, radius_cfg["expected_radius"], "repelling radius")
    _close(shrinkage, radius_cfg["expected_shrinkage"], "repelling shrinkage")
    _close(effective, radius_cfg["expected_effective_radius"], "effective radius")

    csa_cfg = fixtures["csa"]
    sigma = csa_update(
        csa_cfg["sigma"], csa_cfg["cs"], csa_cfg["damps"], csa_cfg["ps_norm"], csa_cfg["chi_n"]
    )
    _close(sigma, csa_cfg["expected_sigma"], "CSA sigma")

    hill_cfg = fixtures["hill_valley"]
    fractions = [k / (hill_cfg["n_evals"] + 1.0) for k in range(1, hill_cfg["n_evals"] + 1)]
    exact(
        fractions,
        hill_cfg["expected_interpolation_fractions"],
        "A7_CONTROLS",
        "hill-valley fractions",
    )
    same, count = hill_valley(1.0, 2.0, [2.0, 1.5, 2.0])
    exact(same, True, "A7_CONTROLS", "hill-valley equality semantics")
    exact(count, 3, "A7_CONTROLS", "hill-valley equality evaluation count")
    different, count = hill_valley(1.0, 2.0, [1.5, 2.0000000001, 1.0])
    exact(different, False, "A7_CONTROLS", "hill-valley strict barrier semantics")
    exact(count, 2, "A7_CONTROLS", "hill-valley early-stop evaluation count")

    return {
        "status": "PASS_INDEPENDENT_CONTROLS",
        "seed_schedule": {
            "rows": len(schedule),
            "first": schedule[0],
            "instance2_first": schedule[seed_cfg["runs_per_instance"]],
            "last": schedule[-1],
        },
        "bipop": {"first": first, "second": second},
        "repelling": {
            "gamma_factor": gamma_factor,
            "radius": radius,
            "shrinkage": shrinkage,
            "effective_radius_after_attempts": effective,
        },
        "csa": {"sigma": sigma},
        "hill_valley": {
            "fractions": fractions,
            "equality_same_basin": same,
            "barrier_different_basin": not different,
            "barrier_evaluations": count,
        },
    }
