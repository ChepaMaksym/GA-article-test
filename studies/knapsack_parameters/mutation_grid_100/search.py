"""Call the single active GA loop without exposing reference optima."""
from copy import deepcopy

from studies.knapsack_parameters.population_validation_100.common import require, require_ci

POPULATIONS = (10, 15, 20)
MUTATION_BASIS_POINTS = (25, 50, 75, 100, 150, 200)


def make_log(problem, bank, mu, mutation_basis_points, seed, task_index, total=100000):
    """Use a common bank prefix; one basis point means probability 1/10000."""
    require_ci()
    require(type(problem) is dict and set(problem) == {"n", "weights", "profits", "capacity"}
            and problem["n"] == 100, "Only the registered problem without optimum metadata is accepted")
    require(type(mu) is int and mu in POPULATIONS
            and type(mutation_basis_points) is int and mutation_basis_points in MUTATION_BASIS_POINTS,
            "Unregistered mutation grid configuration")
    require(type(total) is int and total > mu, "The total count must include a nonempty search")
    require(type(bank) is dict and len(bank.get("masks", [])) == len(bank.get("scores", [])) == 30
            and bank["masks"][0] == "0" * 100
            and bank.get("search_seed") == seed and bank.get("task_index") == task_index,
            "A matching common thirty-mask bank is required")
    from .program.ga_core import create_random_generators, parameter_controller, run_ga
    generators = create_random_generators(seed, task_index, 0)
    require({name: deepcopy(rng.bit_generator.state) for name, rng in generators.items()} == bank["rng_states"],
            "Initial states of the six random streams differ")
    return run_ga(problem, {"masks": bank["masks"][:mu], "scores": bank["scores"][:mu]},
                  parameter_controller(0), generators, budget=total - mu,
                  initial_parameters={"p_m": mutation_basis_points / 10000, "p_c": 1.0,
                                      "target_mu": mu, "tournament_size": 2, "elite_count": 1},
                  configuration_contract="fixed-mutation-grid-v1")
