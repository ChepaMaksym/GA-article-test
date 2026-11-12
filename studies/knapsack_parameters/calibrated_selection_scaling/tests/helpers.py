"""Small deterministic CI fixtures with independently assessed initial masks."""
from copy import deepcopy
import os

from studies.knapsack_parameters.calibrated_selection_scaling.program import ga_core


CONTRACT = "calibrated-selection-v1"
CHANNELS = ("initialization", "selection", "branch", "crossover", "mutation", "ties")


def require_ci():
    if os.environ.get("GITHUB_ACTIONS") != "true":
        raise RuntimeError("Scientific tests require GitHub Actions")


def score(problem, mask):
    weight = sum(value for value, bit in zip(problem["weights"], mask, strict=True) if bit == "1")
    profit = sum(value for value, bit in zip(problem["profits"], mask, strict=True) if bit == "1")
    return {"weight": weight, "profit": profit, "feasible": weight <= problem["capacity"]}


def fixture(mu=10, n=6, *, identical=False, capacity=None):
    problem = {"n": n, "weights": list(range(1, n + 1)),
               "profits": list(range(2, n + 2)), "capacity": n + 1 if capacity is None else capacity}
    masks = (["0" * n] * mu if identical else
             [format(index % (1 << n), f"0{n}b") for index in range(mu)])
    return problem, {"masks": masks, "scores": [score(problem, mask) for mask in masks]}


def configured(mu=10, n=6, pc=.9, profile="k2"):
    return {"p_m": 1 / n, "p_c": pc, "target_mu": mu,
            "tournament_size": 3 if profile == "k3" else 2, "elite_count": 1}


def run_small(*, mu=10, n=6, pc=.9, budget=20, seed=17, profile="k2",
              problem=None, initial=None, parameters=None, contract=CONTRACT, schedule=None):
    require_ci()
    if problem is None:
        problem, initial = fixture(mu, n)
    if parameters is None:
        parameters = configured(mu, problem["n"], pc, profile)
    controller = (ga_core.parameter_controller(profile) if type(profile) is int
                  else ga_core.tournament_controller(profile, schedule))
    return ga_core.run_ga(
        problem, initial, controller, ga_core.create_random_generators(seed, 4, 0), budget,
        initial_parameters=parameters, configuration_contract=contract)


def scientific_trace(log):
    result = deepcopy(log)
    for field in ("timing_ns", "schema", "configuration_contract", "initial_parameters", "initial_population_size"):
        result.pop(field, None)
    return result
