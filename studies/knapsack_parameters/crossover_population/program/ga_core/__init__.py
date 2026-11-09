"""Shared genetic algorithm for the knapsack problem."""
from .controllers import Controller, parameter_controller, tournament_controller
from .engine import run_search
from .operators import make_rngs as create_random_generators

# Keep the old short name available for existing examples.
make_rngs = create_random_generators


def run_ga(problem, initial_population, controller, random_generators, budget=5000,
           *, initial_parameters=None, configuration_contract=None):
    """Run the search from a known population without the reference optimum.

    problem: dictionary with n (item count), weights, profits, and capacity
        (in the same units as the weights).
    initial_population: dictionary with masks and scores; 30 initial masks
        historically, or target_mu masks for an explicit fixed configuration.
    controller: selects fixed parameters, enabled adaptations, or a schedule.
    random_generators: six isolated random number generators.
    budget: number of new evaluations, including duplicates and infeasible
        candidates; the initial scores are validated separately.
    initial_parameters: optional fixed configuration for population sizing.
        Requires parameter_controller(0); mutation is 1/n, crossover 90%,
        tournament size two and one elite. The caller accounts initial scores
        separately when imposing a total evaluation limit.
    configuration_contract: None preserves every historical route. The explicit
        "population-crossover-v1" contract additionally permits a fixed finite
        crossover probability from zero through one in initial_parameters.
        This contract requires fixed profile zero and an explicit population.

    Return a log containing candidates, generations, and a summary.
    """
    if not isinstance(controller, Controller):
        raise ValueError("Потрібний контролер, створений фабрикою")
    if type(initial_population) is not dict or set(initial_population) != {"masks", "scores"}:
        raise ValueError("Початок повинен містити masks і scores")
    return run_search(problem, initial_population["masks"], initial_population["scores"],
                      controller.profile, random_generators, budget,
                      tournament_schedule=controller.schedule,
                      initial_parameters=initial_parameters,
                      configuration_contract=configuration_contract)
