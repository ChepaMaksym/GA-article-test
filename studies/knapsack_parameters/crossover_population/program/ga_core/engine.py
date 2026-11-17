"""Single evolutionary loop for offspring creation and parameter control.

execution_timer.measure blocks measure elapsed time. Entries in run_log
record execution evidence; they do not select candidates or change search rules.
"""
from copy import deepcopy  # Independent copy of the known initial scores.
from fractions import Fraction  # Exact mean of the crossover signal.

import numpy as np  # Generator types and PCG64 validation.

from .operators import (
    CHANNELS as RANDOM_STREAM_NAMES,
    _require as require_condition,
    _integer as require_integer,
    _problem as validate_problem,
    _mask as validate_mask,
    _evaluate as evaluate_solution,
    _key as fitness_order_key,
    _states as capture_random_states,
    select_elites,
    select_parents,
    create_offspring,
)
from .controllers import (
    _profile as validate_control_profile,
    default_parameters,
    novelty_statistics,
    validate_schedule,
    update_parameters,
    validate_initial_parameters,
    update_configured_fixed_parameters,
)
from .monitoring import ExecutionTimer
from .trace import record_candidate, record_generation


# Log format versions. Keep these strings compatible with existing references.
PARAMETER_DYNAMICS_LOG_SCHEMA = "ga-knapsack-parameter-dynamics-log-v1"
TOURNAMENT_FEEDBACK_LOG_SCHEMA = "ga-knapsack-tournament-feedback-log-v1"
CONFIGURED_FIXED_LOG_SCHEMA = "ga-knapsack-configured-fixed-log-v1"
POPULATION_CROSSOVER_LOG_SCHEMA = "ga-knapsack-population-crossover-log-v1"
INITIAL_POPULATION_SIZE = 30


def run_search(problem, initial_masks, initial_scores, control_profile,
               random_generators, evaluation_budget=5000, tournament_schedule=None,
               *, initial_parameters=None, configuration_contract=None):
    """Perform exactly evaluation_budget new evaluations.

    problem: dictionary with n, weights, profits, and capacity; weights and
        capacity share units, and profits use a common scale.
    initial_masks: known binary strings of length n; 30 for historical calls,
        or target_mu strings when explicit initial_parameters are supplied.
    initial_scores: matching weight, profit, and feasible values; feasible=True
        means the total weight does not exceed capacity.
    control_profile: integer adaptation mask 0-31 or a tournament profile name,
        such as k3, adaptive, or replay; this is not a fitness value.
    random_generators: six separate streams of random numbers.
    evaluation_budget: number of new offspring to evaluate; duplicates and
        infeasible candidates count, while the initial 30 are tracked separately.
    tournament_schedule: tournament sizes by generation, used only for replay;
        None for all other profiles.
    initial_parameters: optional fixed population-study configuration. This
        keyword requires profile 0 and no schedule; historical calls omit it.
        Initial scores remain outside evaluation_budget in both routes.
    configuration_contract: None preserves the old contract; the explicit
        "population-crossover-v1" contract permits configured fixed crossover.

    Return a log of candidates, populations, parameters, and generator states.
    A partial generation contributes to the record but does not replace the population.
    """
    execution_timer = ExecutionTimer()

    # 1. Validate inputs. Initial scores do not consume the search budget.
    with execution_timer.measure("validation"):
        validate_problem(problem)
        validate_control_profile(control_profile)
        require_integer(evaluation_budget, "evaluation_budget", 1)
        require_condition(configuration_contract is None or configuration_contract == "population-crossover-v1",
                          "Unknown fixed-configuration contract")
        require_condition(configuration_contract is None or initial_parameters is not None,
                          "The population-crossover contract requires explicit initial parameters")
        if initial_parameters is not None:
            require_condition(type(control_profile) is int and control_profile == 0
                              and tournament_schedule is None,
                              "Explicit initial parameters require fixed profile 0 without a schedule")
            configured_parameters = validate_initial_parameters(
                initial_parameters, problem["n"], configuration_contract=configuration_contract,
            )
            initial_population_size = configured_parameters["target_mu"]
        else:
            configured_parameters = None
            initial_population_size = INITIAL_POPULATION_SIZE
        if control_profile == "replay":
            tournament_schedule = validate_schedule(tournament_schedule, evaluation_budget)
        else:
            require_condition(tournament_schedule is None, "Розклад використовується тільки в replay")
        require_condition(
            isinstance(initial_masks, list) and isinstance(initial_scores, list)
            and len(initial_masks) == len(initial_scores) == initial_population_size,
            ("Потрібно рівно 30 відомих початкових наборів і їхніх оцінок"
             if configured_parameters is None else
             "The known initial population must match the configured population size"),
        )
        require_condition(
            isinstance(random_generators, dict) and set(random_generators) == set(RANDOM_STREAM_NAMES),
            "Потрібно рівно шість окремих потоків випадкових чисел",
        )
        require_condition(
            all(isinstance(random_generators[name], np.random.Generator)
                and isinstance(random_generators[name].bit_generator, np.random.PCG64)
                for name in RANDOM_STREAM_NAMES),
            "Кожний генератор повинен використовувати PCG64",
        )
        require_condition(
            len({id(random_generators[name]) for name in RANDOM_STREAM_NAMES}) == 6
            and len({id(random_generators[name].bit_generator) for name in RANDOM_STREAM_NAMES}) == 6,
            "Окремі потоки не можуть посилатися на спільний генератор",
        )
        item_count, capacity = problem["n"], problem["capacity"]
        evaluated_masks, evaluated_scores = list(initial_masks), []
        for initial_mask, known_score in zip(initial_masks, initial_scores):
            validate_mask(initial_mask, item_count)
            require_condition(
                type(known_score) is dict and set(known_score) == {"weight", "profit", "feasible"}
                and type(known_score["weight"]) is int and type(known_score["profit"]) is int
                and type(known_score["feasible"]) is bool
                and known_score["weight"] >= 0 and known_score["profit"] >= 0,
                "Некоректна відома оцінка початкового набору",
            )
            checked_score = evaluate_solution(problem, initial_mask)
            require_condition(checked_score == known_score, "Відома оцінка не відповідає предметам задачі")
            evaluated_scores.append(checked_score)
        problem_for_log = {"n": item_count, "weights": list(problem["weights"]),
                           "profits": list(problem["profits"]), "capacity": capacity}
        initial_random_states = capture_random_states(random_generators)
        current_parameters = (default_parameters(control_profile) if configured_parameters is None
                              else dict(configured_parameters))
        failed_evaluation_count = 0

    # 2. Initialize the population and record. References index evaluated masks.
    with execution_timer.measure("log_assembly"):
        run_log = {"schema": PARAMETER_DYNAMICS_LOG_SCHEMA, "profile": control_profile,
                   "problem": problem_for_log, "initial_masks": list(evaluated_masks),
                   "initial_scores": deepcopy(evaluated_scores), "rng_initial": initial_random_states,
                   "budget": evaluation_budget, "candidates": [], "generations": [],
                   "summary": None, "rng_final": None}
        if type(control_profile) is str:
            run_log["schema"] = TOURNAMENT_FEEDBACK_LOG_SCHEMA
            run_log["schedule"] = list(tournament_schedule) if tournament_schedule is not None else None
        if configured_parameters is not None:
            run_log["schema"] = CONFIGURED_FIXED_LOG_SCHEMA
            run_log["initial_parameters"] = dict(configured_parameters)
            run_log["initial_population_size"] = initial_population_size
            if configuration_contract is not None:
                run_log["schema"] = POPULATION_CROSSOVER_LOG_SCHEMA
                run_log["configuration_contract"] = configuration_contract
        population_references = list(range(initial_population_size))
        seen_masks = set(evaluated_masks)
        best_feasible_mask = best_feasible_value = best_evaluation_number = None
        for initial_mask, initial_score in zip(evaluated_masks, evaluated_scores):
            if initial_score["feasible"] and (
                best_feasible_value is None or initial_score["profit"] > best_feasible_value
            ):
                best_feasible_mask, best_feasible_value, best_evaluation_number = initial_mask, initial_score["profit"], 0
        evaluations_used = completed_generation_count = terminal_partial_offspring_count = 0
        generation_number = 0
        duplicate_candidate_count = infeasible_candidate_count = 0

    # 3. Use one generation loop for the fixed and all adaptive variants.
    while evaluations_used < evaluation_budget:
        with execution_timer.measure("log_assembly"):
            generation_number += 1
            parent_population_references = list(population_references)
            random_states_before_generation = capture_random_states(random_generators)
            parent_population_size = len(parent_population_references)
            parameters_for_generation = dict(current_parameters)
            # Count offspring evaluations in completed unsuccessful generations.
            failed_evaluations_before_generation = failed_evaluation_count
            best_value_before_generation = best_feasible_value
            fitness_keys = [fitness_order_key(evaluated_scores[reference], capacity)
                            for reference in parent_population_references]
            first_offspring_evaluation_number = evaluations_used + 1
            # target_mu is the next population size; elite_count is the number carried over.
            # New offspring fill the remaining slots. Select parents from the current population.
            offspring_quota = parameters_for_generation["target_mu"] - parameters_for_generation["elite_count"]
            offspring_references, selected_parent_distances = [], []

        # 3.1. Preserve elites without reevaluating their known scores.
        with execution_timer.measure("selection"):
            elite_indices, elite_references = select_elites(
                parent_population_references, parameters_for_generation, fitness_keys, random_generators,
            )

        # 3.2. Create and evaluate offspring within the remaining budget.
        for _ in range(min(offspring_quota, evaluation_budget - evaluations_used)):
            with execution_timer.measure("selection"):
                tournament_entries, parent_indices = select_parents(
                    parent_population_size, parameters_for_generation, fitness_keys, random_generators,
                )
                first_parent_mask = evaluated_masks[parent_population_references[parent_indices[0]]]
                second_parent_mask = evaluated_masks[parent_population_references[parent_indices[1]]]

            with execution_timer.measure("signal"):
                distance_between_parents = sum(
                    first_bit != second_bit for first_bit, second_bit in zip(first_parent_mask, second_parent_mask)
                )
                selected_parent_distances.append(distance_between_parents)

            with execution_timer.measure("variation"):
                crossover_applied, mask_before_mutation, mutated_bit_indices, offspring_mask = create_offspring(
                    first_parent_mask, second_parent_mask, item_count, parameters_for_generation, random_generators,
                )

            with execution_timer.measure("evaluation"):
                # feasible=True means the selected items fit within the capacity.
                offspring_score = evaluate_solution(problem, offspring_mask)

            with execution_timer.measure("log_assembly"):
                evaluations_used += 1
                is_duplicate = offspring_mask in seen_masks
                duplicate_candidate_count += int(is_duplicate)
                infeasible_candidate_count += int(not offspring_score["feasible"])
                # Flag duplicates only; every candidate has already been evaluated above.
                seen_masks.add(offspring_mask)
                if offspring_score["feasible"] and (
                    best_feasible_value is None or offspring_score["profit"] > best_feasible_value
                ):
                    best_feasible_mask, best_feasible_value = offspring_mask, offspring_score["profit"]
                    best_evaluation_number = evaluations_used
                offspring_reference = len(evaluated_masks)
                evaluated_masks.append(offspring_mask)
                evaluated_scores.append(offspring_score)
                offspring_references.append(offspring_reference)

                # Monitoring: record candidate creation without modifying the candidate.
                record_candidate(run_log, {
                    "call": evaluations_used, "generation": generation_number,
                    "tournaments": tournament_entries, "parent_indices": parent_indices,
                    "parent_distance": distance_between_parents, "crossover": crossover_applied,
                    "pre_mask": mask_before_mutation, "mutation_bits": mutated_bit_indices,
                    "mask": offspring_mask, **offspring_score, "duplicate": is_duplicate,
                    "record_profit": best_feasible_value, "record_call": best_evaluation_number,
                })

        # 3.3. Compute the crossover signal over all selected pairs using an exact mean.
        with execution_timer.measure("signal"):
            crossover_novelty_statistics = novelty_statistics(selected_parent_distances)
            mean_crossover_novelty_probability = Fraction(
                crossover_novelty_statistics["novelty_mean_numerator"],
                crossover_novelty_statistics["novelty_mean_denominator"],
            )

        generation_is_complete = len(offspring_references) == offspring_quota
        if generation_is_complete:
            # 3.4. Elites and all offspring form the next population, including worse offspring.
            with execution_timer.measure("log_assembly"):
                population_references = elite_references + offspring_references
                completed_generation_count += 1
                record_improved = best_feasible_value is not None and (
                    best_value_before_generation is None or best_feasible_value > best_value_before_generation
                )
            # Search control: apply parameter changes starting with the next generation.
            with execution_timer.measure("controller"):
                if configured_parameters is None:
                    controller_update = update_parameters(
                        parameters_for_generation, failed_evaluations_before_generation, record_improved,
                        offspring_quota, mean_crossover_novelty_probability, control_profile,
                        schedule=tournament_schedule, completed_generation=generation_number,
                    )
                else:
                    controller_update = update_configured_fixed_parameters(
                        parameters_for_generation, failed_evaluations_before_generation, record_improved,
                        offspring_quota, mean_crossover_novelty_probability, item_count,
                        configuration_contract=configuration_contract,
                    )
                current_parameters = controller_update["parameters"]
                failed_evaluation_count = controller_update["failed_queries_after"]
        else:
            # Budget remainder: evaluated offspring count toward the record;
            # retain the population and controller.
            terminal_partial_offspring_count = len(offspring_references)
            record_improved = None
            controller_update = {
                "event": "PARTIAL_NO_UPDATE",
                "failed_queries_accumulated": failed_evaluations_before_generation,
                "failed_queries_after": failed_evaluations_before_generation,
                "stagnation_overshoot": None, "parameter_events": [],
            }
            current_parameters = dict(parameters_for_generation)
            failed_evaluation_count = failed_evaluations_before_generation

        # Generation monitoring. Preserve existing log keys for reference compatibility.
        with execution_timer.measure("log_assembly"):
            record_generation(run_log, {
                "generation": generation_number,
                "start_call": first_offspring_evaluation_number, "end_call": evaluations_used,
                "complete": generation_is_complete, "population_before": parent_population_references,
                "actual_parent_mu": parent_population_size, "parameters_before": parameters_for_generation,
                "parameters_after": dict(current_parameters), "elite_indices": elite_indices,
                "elite_references": elite_references, "requested_offspring": offspring_quota,
                "failed_queries_before": failed_evaluations_before_generation,
                "failed_queries_accumulated": controller_update["failed_queries_accumulated"],
                "failed_queries_after": failed_evaluation_count,
                "stagnation_overshoot": controller_update["stagnation_overshoot"],
                "record_before": best_value_before_generation, "record_after": best_feasible_value,
                "success": record_improved, "controller_event": controller_update["event"],
                "population_after": list(population_references),
                "parent_distances": list(selected_parent_distances), **crossover_novelty_statistics,
                "parameter_events": controller_update["parameter_events"],
                "rng_before": random_states_before_generation,
                "rng_after": capture_random_states(random_generators),
            })

    # 4. Build the summary and final generator states without creating candidates.
    with execution_timer.measure("log_assembly"):
        run_log["summary"] = {
            "new_calls": evaluations_used, "physical_evaluations": evaluations_used,
            "known_score_validation_evaluations": initial_population_size,
            "duplicate_calls": duplicate_candidate_count, "infeasible_calls": infeasible_candidate_count,
            "full_generations": completed_generation_count, "partial_children": terminal_partial_offspring_count,
            "best_mask": best_feasible_mask, "best_profit": best_feasible_value,
            "best_call": best_evaluation_number, "final_population": list(population_references),
            "final_parameters": dict(current_parameters), "final_failed_queries": failed_evaluation_count,
        }
        run_log["rng_final"] = capture_random_states(random_generators)
    run_log["timing_ns"] = execution_timer.finish()
    return run_log
