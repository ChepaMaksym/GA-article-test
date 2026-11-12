"""Thin scientific adapter; the kernel never receives optimum certificates."""
from copy import deepcopy

from .common import ci_only, require
from .configuration import CONTRACT, TOTAL_EVALUATIONS, baseline_parameters


def execute_case(case, problem, bank):
    """Use a common twenty-mask bank prefix and count initialization in total."""
    ci_only()
    require(type(problem) is dict and set(problem) == {"n", "weights", "profits", "capacity"}
            and problem["n"] == case["n"] in (100, 500),
            "Only the four problem fields, without optimum metadata, are accepted")
    profile = case["profile"]
    expected = baseline_parameters(problem["n"], profile, case["role"] == "common")
    require(case["initial_parameters"] == expected and case["configuration_contract"] == CONTRACT
            and case["total_evaluations"] == TOTAL_EVALUATIONS,
            "The requested configuration differs from the frozen case")
    require(type(bank) is dict and len(bank.get("masks", [])) == len(bank.get("scores", [])) == 20
            and bank["masks"][0] == "0" * problem["n"]
            and bank.get("search_seed") == case["seed"]
            and bank.get("preparation_seed") == case["preparation_seed"]
            and bank.get("task_index") == case["task_index"],
            "A matching common bank of twenty individuals is required")
    from .program.ga_core import create_random_generators, run_ga, tournament_controller
    generators = create_random_generators(case["seed"], case["task_index"], 0)
    require({name: deepcopy(rng.bit_generator.state) for name, rng in generators.items()}
            == bank["rng_states"], "The six initial random states differ")
    mu = expected["target_mu"]
    return run_ga(problem, {"masks": bank["masks"][:mu], "scores": bank["scores"][:mu]},
                  tournament_controller(profile), generators, budget=TOTAL_EVALUATIONS - mu,
                  initial_parameters=expected, configuration_contract=CONTRACT)
