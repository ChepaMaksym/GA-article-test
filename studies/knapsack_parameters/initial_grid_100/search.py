"""Call the unchanged GA with one registered fixed population/crossover pair."""
from copy import deepcopy

from studies.knapsack_parameters.population_validation_100.common import require, require_ci

POPULATIONS = (10, 15, 20, 25)
CROSSOVER_PERCENTAGES = (70, 80, 90, 100)


def make_log(problem, bank, mu, pc_percentage, seed, task_index, total=100000):
    """Use a prefix of a known thirty-mask bank and exactly total evaluations.

    problem contains only n, weights, profits and capacity.  The reference
    optimum and certificates are deliberately absent from this interface.
    bank contains thirty masks, their known scores and six initial RNG states.
    mu selects the common prefix; pc_percentage is the application probability
    of uniform crossover, whose inheritance probability remains one half.
    seed/task_index identify the six search streams.  total includes initial
    masks and subsequent candidates, including duplicates and infeasible ones.
    """
    require_ci()
    require(type(problem) is dict and problem.get("n") == 100
            and set(problem) == {"n", "weights", "profits", "capacity"},
            "Search accepts only the registered 100-item problem without optimum metadata")
    require(type(mu) is int and mu in POPULATIONS, "Population is outside the registered grid")
    require(type(pc_percentage) is int and pc_percentage in CROSSOVER_PERCENTAGES,
            "Crossover is outside the registered grid")
    require(type(total) is int and total > mu, "Total evaluations must include a nonempty search")
    require(type(seed) is int and seed >= 0 and type(task_index) is int and task_index >= 0,
            "Invalid search stream identity")
    require(type(bank) is dict and len(bank.get("masks", [])) == len(bank.get("scores", [])) == 30
            and bank["masks"][0] == "0" * 100, "A common thirty-mask bank with the empty first mask is required")
    require(bank.get("search_seed") == seed and bank.get("task_index") == task_index,
            "Bank and search identity differ")
    from studies.knapsack_parameters.crossover_population.program.ga_core import (
        create_random_generators, parameter_controller, run_ga,
    )
    random_generators = create_random_generators(seed, task_index, 0)
    require({name: deepcopy(generator.bit_generator.state)
             for name, generator in random_generators.items()} == bank["rng_states"],
            "Initial search stream states differ from the common bank")
    return run_ga(problem, {"masks": bank["masks"][:mu], "scores": bank["scores"][:mu]},
                  parameter_controller(0), random_generators, budget=total - mu,
                  initial_parameters={"p_m": 0.01, "p_c": pc_percentage / 100,
                                      "target_mu": mu, "tournament_size": 2, "elite_count": 1},
                  configuration_contract="population-crossover-v1")
