"""Run one frozen holdout configuration through the single GA core."""
from copy import deepcopy

from studies.knapsack_parameters.mutation_grid_100.analysis import CONFIGS
from studies.knapsack_parameters.population_validation_100.common import require, require_ci


def make_log(problem, bank, configuration, seed, task_index, total=100000):
    """All variants share the 30-mask bank and six initial generator states."""
    require_ci()
    require(type(problem) is dict and set(problem) == {"n", "weights", "profits", "capacity"}
            and problem["n"] == 100, "Search must not receive exact reference metadata")
    require(type(configuration) is tuple and configuration in CONFIGS,
            "Validation accepts only configurations from the frozen tuning pool")
    mu, pc, mutation_bp = configuration
    require(type(total) is int and total > mu and type(seed) is int and type(task_index) is int,
            "Invalid holdout identity or evaluation count")
    require(type(bank) is dict and len(bank.get("masks", [])) == len(bank.get("scores", [])) == 30
            and bank["masks"][0] == "0" * 100 and bank.get("search_seed") == seed
            and bank.get("preparation_seed") == 160000 and bank.get("task_index") == task_index,
            "A matching paired holdout bank is required")
    from ..program.ga_core import create_random_generators, parameter_controller, run_ga
    generators = create_random_generators(seed, task_index, 0)
    require({name: deepcopy(rng.bit_generator.state) for name, rng in generators.items()} == bank["rng_states"],
            "The six initial search stream states differ")
    return run_ga(problem, {"masks": bank["masks"][:mu], "scores": bank["scores"][:mu]},
                  parameter_controller(0), generators, budget=total - mu,
                  initial_parameters={"p_m": mutation_bp / 10000, "p_c": pc / 100,
                                      "target_mu": mu, "tournament_size": 2, "elite_count": 1},
                  configuration_contract="fixed-mutation-grid-v1")
