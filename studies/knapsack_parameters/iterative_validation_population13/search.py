"""Call the immutable public GA once using a known thirty-mask bank prefix."""
from copy import deepcopy

from studies.knapsack_parameters.population_validation_100.common import require, require_ci

POPULATIONS = (10, 13, 15, 20)
CHANNELS = ("initialization", "selection", "branch", "crossover", "mutation", "ties")


def make_log(problem, bank, mu, seed, task_index, total=100000):
    """Exclude all oracle metadata and account initial masks inside total."""
    require_ci()
    require(type(problem) is dict and set(problem) == {"n", "weights", "profits", "capacity"}
            and problem.get("n") == 100, "Search accepts only the registered problem without oracle metadata")
    require(type(mu) is int and mu in POPULATIONS, "Unregistered technical population")
    require(type(total) is int and total > mu, "Total evaluations must include a nonempty offspring budget")
    require(type(seed) is int and seed >= 0 and type(task_index) is int and task_index >= 0,
            "Invalid search stream identity")
    require(type(bank) is dict and len(bank.get("masks", [])) == len(bank.get("scores", [])) == 30
            and bank["masks"][0] == "0" * 100, "The common original thirty-mask bank is required")
    require(bank.get("search_seed") == seed and bank.get("task_index") == task_index
            and type(bank.get("rng_states")) is dict and set(bank["rng_states"]) == set(CHANNELS),
            "Bank and six-stream search identity differ")
    from studies.knapsack_parameters.crossover_population.program.ga_core import (
        create_random_generators, parameter_controller, run_ga,
    )
    generators = create_random_generators(seed, task_index, 0)
    require({name: deepcopy(generator.bit_generator.state) for name, generator in generators.items()}
            == bank["rng_states"], "Original six initial RNG states differ")
    return run_ga(problem, {"masks": bank["masks"][:mu], "scores": bank["scores"][:mu]},
                  parameter_controller(0), generators, budget=total - mu,
                  initial_parameters={"p_m": .01, "p_c": .9, "target_mu": mu,
                                      "tournament_size": 2, "elite_count": 1},
                  configuration_contract="population-crossover-v1")
