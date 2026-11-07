"""Evaluate solutions, select parents, and create offspring.

This module implements GA operators. It does not write files or change
adaptation rules. Random-stream names are retained for log replay.
"""
from copy import deepcopy
import numpy as np

# Separate streams for initialization, selection, the crossover decision,
# crossover bits, mutation, and ties. Stream order determines initial states.
CHANNELS = ("initialization", "selection", "branch", "crossover", "mutation", "ties")

def _require(condition, message):
    """Stop execution if a required condition is false."""
    if not condition:
        raise ValueError(message)

def _integer(value, name, minimum=0):
    """Validate an integer parameter and its lower bound."""
    _require(type(value) is int and value >= minimum, f"{name} must be an integer >= {minimum}")

def _problem(problem):
    """Validate knapsack data; the search core does not receive the optimum."""
    _require(isinstance(problem, dict) and set(problem) == {"n", "weights", "profits", "capacity"},
             "Only n, weights, profits and capacity are accepted; oracle metadata is forbidden")
    _integer(problem["n"], "n", 2)
    _integer(problem["capacity"], "capacity")
    for name in ("weights", "profits"):
        _require(isinstance(problem[name], (list, tuple)) and len(problem[name]) == problem["n"],
                 "Wrong problem-vector length")
        for value in problem[name]:
            _integer(value, name, 1)

def _mask(mask, item_count):
    """Validate a binary string with one bit per item."""
    _require(isinstance(mask, str) and len(mask) == item_count and not set(mask) - {"0", "1"}, "Invalid binary mask")

def _evaluate(problem, mask):
    """Compute weight, profit, and feasibility for a validated mask."""
    total_weight = sum(item_weight for item_weight, bit in zip(problem["weights"], mask) if bit == "1")
    total_profit = sum(item_profit for item_profit, bit in zip(problem["profits"], mask) if bit == "1")
    return {"weight": total_weight, "profit": total_profit, "feasible": total_weight <= problem["capacity"]}

def evaluate(problem, mask):
    """Validate the input and evaluate one solution exactly without caching."""
    _problem(problem)
    _mask(mask, problem["n"])
    return _evaluate(problem, mask)

def _key(score, capacity):
    """Prioritize feasibility, then compare profit or capacity violation."""
    return (1, score["profit"]) if score["feasible"] else (0, capacity - score["weight"])

def _pick(winning_positions, generator):
    # A single winning position needs no random draw to resolve a tie.
    return (winning_positions[0] if len(winning_positions) == 1 else
            winning_positions[int(generator.integers(len(winning_positions)))])

def _states(random_generators):
    """Copy the states of all six random streams independently."""
    return {channel_name: deepcopy(random_generators[channel_name].bit_generator.state)
            for channel_name in CHANNELS}

def make_rngs(seed, task_index, start_index):
    """Create six generators from the run seed, task, and starting-bank index.

    seed: a nonnegative integer used to reproduce a search run.
    task_index: the task index, which separates random streams by task.
    start_index: the known starting-bank index, which separates streams by bank.
    Each operator uses its own stream. Fixed input integers reproduce the
    initial states; the control-profile name does not affect them.
    """
    for name, value in (("seed", seed), ("task_index", task_index), ("start_index", start_index)):
        _integer(value, name)
    return {channel_name: np.random.Generator(np.random.PCG64(np.random.SeedSequence(
        [seed, task_index, start_index, channel_index])))
            for channel_index, channel_name in enumerate(CHANNELS)}

def select_elites(population_references, parameters, fitness_keys, random_generators):
    """Copy the best positions; duplicate masks remain separate individuals."""
    available_positions = list(range(len(population_references)))
    elite_indices, elite_references = [], []
    for _ in range(parameters["elite_count"]):
        best_fitness_key = max(fitness_keys[index] for index in available_positions)
        elite_index = _pick(
            [index for index in available_positions if fitness_keys[index] == best_fitness_key],
            random_generators["ties"])
        elite_indices.append(elite_index)
        elite_references.append(population_references[elite_index])
        available_positions.remove(elite_index)
    return elite_indices, elite_references


def select_parents(parent_population_size, parameters, fitness_keys, random_generators):
    """Select two parents using separate tournaments with replacement.

    parent_population_size: the actual number of available parent individuals,
        rather than the target size of the next generation.
    parameters["tournament_size"]: the number of random entries in each
        tournament; the same index may be drawn more than once.
    fitness_keys: known fitness-order keys; no new evaluations are needed.
    """
    tournament_entries, parent_indices = [], []
    for _ in range(2):
        participant_indices = [int(random_generators["selection"].integers(parent_population_size))
                               for _ in range(parameters["tournament_size"])]
        tournament_entries.append(participant_indices)
        best_fitness_key = max(fitness_keys[index] for index in participant_indices)
        parent_indices.append(_pick(
            [index for index in participant_indices if fitness_keys[index] == best_fitness_key],
            random_generators["ties"]))
    return tournament_entries, parent_indices


def create_offspring(first_parent_mask, second_parent_mask, item_count, parameters, random_generators):
    """Apply uniform crossover and independent bitwise mutation.

    Return the crossover flag, the mask before mutation, the changed-bit
    positions, and the final offspring mask. The GA loop evaluates it separately.

    first_parent_mask, second_parent_mask: bit strings of length item_count.
    parameters["p_c"]: the probability of applying crossover to this pair.
        When applied, each bit is inherited from either parent with probability 1/2.
    parameters["p_m"]: the independent probability of flipping each offspring bit.
        A value of 0.01 means 1%; it does not force exactly one bit to change.
    """
    crossover_applied = bool(random_generators["branch"].random() < parameters["p_c"])
    if crossover_applied:
        inherit_from_first_parent = random_generators["crossover"].random(item_count) < 0.5
        mask_before_mutation = "".join(
            first_parent_mask[index] if inherit_from_first_parent[index] else second_parent_mask[index]
            for index in range(item_count))
    else:
        mask_before_mutation = first_parent_mask
    mutation_positions = [
        index for index, changed in enumerate(
            random_generators["mutation"].random(item_count) < parameters["p_m"])
        if changed]
    offspring_bits = list(mask_before_mutation)
    for index in mutation_positions:
        offspring_bits[index] = "0" if offspring_bits[index] == "1" else "1"
    return crossover_applied, mask_before_mutation, mutation_positions, "".join(offspring_bits)
