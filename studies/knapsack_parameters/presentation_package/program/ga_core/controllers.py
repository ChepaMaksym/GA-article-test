"""Parameter update rules applied after a completed generation.

The controller computes the next parameters without creating offspring or
using random generators. Event records explain the decision; file logging
is handled outside this module.
"""
from dataclasses import dataclass
from fractions import Fraction
import math
from .operators import _integer, _require

# Names and keys are retained for compatibility with reference logs.
PROFILES = ("k2", "k3", "k4", "k5", "adaptive", "replay")
# New evaluations in consecutive completed generations without a strict record.
# With 29 offspring, this is five failed generations, not seconds or tournaments.
FAILED_QUERY_THRESHOLD = 145
# Order matches profile bits 1, 2, 4, 8, 16; their sum, 31, enables all rules.
PARAMETER_NAMES = ("p_m", "p_c", "target_mu", "tournament_size", "elite_count")
PARAMETER_BOUNDS = {
    "p_m": (0.01, 0.08),       # Independent probability of flipping each bit: 1-8%.
    "p_c": (0.1, 0.9),         # Probability of applying crossover: 10-90%.
    "target_mu": (10, 100),    # Next-generation size, including elite individuals.
    "tournament_size": (2, 5), # Participants per tournament, sampled with replacement.
    "elite_count": (1, 5),     # Best individuals copied without changing their bits.
}

def _parameter_profile(profile):
    """Validate the bit mask of enabled mechanisms: an integer from 0 to 31."""
    _require(type(profile) is int and 0 <= profile <= 31, "Profile must be an integer from 0 through 31")

def _parameter_default():
    """Return the shared initial values of the five parameters."""
    return {
        "p_m": 0.01,          # 1% per bit: one expected flip for a 100-bit offspring.
        "p_c": 0.9,           # 90% chance of applying crossover to the selected pair.
        "target_mu": 30,      # Next population: one elite and 29 new offspring.
        "tournament_size": 2, # Two participants when selecting each of the two parents.
        "elite_count": 1,     # One best individual is copied unchanged.
    }

def _parameter_parameters(parameters, profile):
    """Validate bounds and ensure disabled mechanisms remain unchanged."""
    _profile(profile)
    _require(type(parameters) is dict and set(parameters) == set(PARAMETER_NAMES), "Invalid parameter vector")
    initial_parameters = default_parameters()
    for parameter_bit, parameter_name in enumerate(PARAMETER_NAMES):
        parameter_value = parameters[parameter_name]
        minimum_value, maximum_value = PARAMETER_BOUNDS[parameter_name]
        if parameter_name in ("p_m", "p_c"):
            _require(type(parameter_value) in (int, float) and math.isfinite(parameter_value),
                     "Probability must be a finite number")
        else:
            _integer(parameter_value, parameter_name, 1)
        _require(minimum_value <= parameter_value <= maximum_value,
                 "Parameter outside registered bounds: " + parameter_name)
        _require(bool(profile & (1 << parameter_bit)) or parameter_value == initial_parameters[parameter_name],
                 "Disabled parameter changed: " + parameter_name)
    _require(parameters["elite_count"] < parameters["target_mu"], "No new offspring position")

def _tournament_profile(profile):
    """Validate the tournament control profile name."""
    _require(type(profile) is str and profile in PROFILES, "Unknown registered tournament profile")

def _tournament_default(profile="k2"):
    """Set the initial tournament size and keep the other four parameters fixed."""
    _profile(profile)
    return {"p_m": 0.01, "p_c": 0.9, "target_mu": 30,
            "tournament_size": int(profile[1:]) if profile.startswith("k") else 2, "elite_count": 1}

def _tournament_parameters(parameters, profile):
    """Ensure the tournament profile does not change other parameters."""
    _profile(profile)
    _require(type(parameters) is dict and set(parameters) == set(PARAMETER_NAMES), "Invalid parameter vector")
    initial_parameters = default_parameters(profile)
    for parameter_name in PARAMETER_NAMES:
        parameter_value = parameters[parameter_name]
        minimum_value, maximum_value = PARAMETER_BOUNDS[parameter_name]
        if parameter_name in ("p_m", "p_c"):
            _require(type(parameter_value) in (int, float) and math.isfinite(parameter_value),
                     "Probability must be a finite number")
        else:
            _integer(parameter_value, parameter_name, 1)
        _require(minimum_value <= parameter_value <= maximum_value,
                 "Parameter outside registered bounds: " + parameter_name)
        _require((parameter_name == "tournament_size" and profile in ("adaptive", "replay"))
                 or parameter_value == initial_parameters[parameter_name],
                 "Fixed parameter changed: " + parameter_name)
    _require(parameters["elite_count"] < parameters["target_mu"], "No new offspring position")

def _profile(profile):
    """Distinguish an adaptation bit mask from a tournament profile name."""
    if type(profile) is int:
        return _parameter_profile(profile)
    return _tournament_profile(profile)


def default_parameters(profile=None):
    """Return initial parameters for a fixed or adaptive profile."""
    return _parameter_default() if profile is None or type(profile) is int else _tournament_default(profile)


def validate_initial_parameters(parameters, item_count):
    """Copy and validate the fixed population-size study configuration.

    This explicit route has a separate contract from historical adaptations.
    Only population size varies: mutation is 1/n, crossover is 90%, parents
    use two-entry tournaments, and one elite is retained. Bounds on historical
    controllers are deliberately not relaxed.
    """
    _integer(item_count, "item_count", 2)
    _require(type(parameters) is dict and set(parameters) == set(PARAMETER_NAMES),
             "Initial parameters must contain exactly the five GA parameters")
    copied = dict(parameters)
    for name in ("p_m", "p_c"):
        _require(type(copied[name]) in (int, float) and math.isfinite(copied[name]),
                 "Initial probabilities must be finite numbers")
    for name in ("target_mu", "tournament_size", "elite_count"):
        _integer(copied[name], name, 1)
    _require(2 <= copied["target_mu"] <= 25000,
             "Configured population size must be from 2 through 25000")
    _require(copied["p_m"] == 1 / item_count,
             "The population-size study requires bit mutation probability 1/n")
    _require(copied["p_c"] == 0.9 and copied["tournament_size"] == 2
             and copied["elite_count"] == 1,
             "The population-size study fixes crossover at 90%, tournament size two and one elite")
    return copied


def update_configured_fixed_parameters(
    parameters, failed_evaluation_count, record_improved, offspring_evaluation_count,
    mean_crossover_novelty_probability, item_count,
):
    """Record success or stagnation while leaving all configured values fixed.

    Failure events retain the historical observation convention. They never
    adapt a parameter, even when population size is outside historical bounds.
    """
    fixed_parameters = validate_initial_parameters(parameters, item_count)
    _integer(failed_evaluation_count, "failed_queries")
    _require(failed_evaluation_count < FAILED_QUERY_THRESHOLD and type(record_improved) is bool,
             "Invalid controller state")
    _integer(offspring_evaluation_count, "new_calls", 1)
    _require(offspring_evaluation_count == fixed_parameters["target_mu"] - 1,
             "Fixed controller observation requires a completed generation")
    _require(isinstance(mean_crossover_novelty_probability, Fraction)
             and 0 <= mean_crossover_novelty_probability <= 1,
             "An exact novelty mean is required")
    accumulated = 0 if record_improved else failed_evaluation_count + offspring_evaluation_count
    event = ("SUCCESS" if record_improved else "STAGNATION"
             if accumulated >= FAILED_QUERY_THRESHOLD else "NO_CHANGE")
    remaining = accumulated if event == "NO_CHANGE" else 0
    configured_bounds = {
        "p_m": (1 / item_count, 1 / item_count),
        "p_c": (0.9, 0.9),
        "target_mu": (2, 25000),
        "tournament_size": (2, 2),
        "elite_count": (1, 1),
    }
    return {
        "parameters": fixed_parameters,
        "event": event,
        "failed_queries_accumulated": accumulated,
        "failed_queries_after": remaining,
        "stagnation_overshoot": accumulated - FAILED_QUERY_THRESHOLD if event == "STAGNATION" else 0,
        "parameter_events": [
            {"field": name, "enabled": False, "before": fixed_parameters[name],
             "after": fixed_parameters[name], "direction": "unchanged",
             "at_boundary": fixed_parameters[name] in configured_bounds[name]}
            for name in PARAMETER_NAMES
        ],
    }


def _parameters(parameters, profile):
    """Validate the parameter vector for the selected profile."""
    if type(profile) is int:
        return _parameter_parameters(parameters, profile)
    return _tournament_parameters(parameters, profile)


def novelty_probability(parent_hamming_distance):
    """Probability of a new mask after crossover, before mutation.

    Parent distance counts positions with different bits. A new mask differs
    from both parents; this does not guarantee an improvement.
    """
    _integer(parent_hamming_distance, "parent distance")
    return (Fraction(0) if parent_hamming_distance == 0 else
            Fraction(1) - Fraction(1, 1 << (parent_hamming_distance - 1)))

def novelty_statistics(parent_hamming_distances):
    """Compute the exact sum and mean probabilities over all parent pairs."""
    _require(isinstance(parent_hamming_distances, list) and bool(parent_hamming_distances),
             "Parent distances are required")
    novelty_probability_sum = sum(
        (novelty_probability(parent_hamming_distance) for parent_hamming_distance in parent_hamming_distances),
        Fraction(0),
    )
    mean_novelty_probability = novelty_probability_sum / len(parent_hamming_distances)
    return {"novelty_sum_numerator": novelty_probability_sum.numerator,
            "novelty_sum_denominator": novelty_probability_sum.denominator,
            "novelty_mean_numerator": mean_novelty_probability.numerator,
            "novelty_mean_denominator": mean_novelty_probability.denominator}

def scheduled_k(schedule, generation_index):
    """Read a tournament size from the fixed schedule without current search signals.

    After the final complete generation, hold the last value for bookkeeping.
    Do not invent another schedule entry beyond its end.
    """
    _require(type(schedule) in (list, tuple) and bool(schedule), "A nonempty frozen schedule is required")
    _integer(generation_index, "generation_index")
    _require(all(type(parameter_value) is int and 2 <= parameter_value <= 5 for parameter_value in schedule),
             "Schedule values must be integer tournament sizes from 2 through 5")
    return schedule[min(generation_index, len(schedule) - 1)]

def validate_schedule(schedule, budget):
    """Validate one tournament size per complete or partial generation."""
    _integer(budget, "budget", 1)
    _require(type(schedule) in (list, tuple) and len(schedule) == (budget + 28) // 29,
             "Schedule must contain exactly one applied value per full or partial generation")
    _require(scheduled_k(schedule, 0) == 2, "A donor schedule must start at tournament size two")
    return tuple(schedule)

def _update_parameter(
    parameters, failed_evaluation_count, record_improved, offspring_evaluation_count,
    mean_crossover_novelty_probability, profile,
):
    """Update all enabled parameters simultaneously after a complete generation.

    The event field ``at_boundary`` only marks a result at an allowed bound.
    It does not by itself indicate an attempted parameter change.
    """
    # Validate generation completion and controller signals.
    _parameters(parameters, profile)
    _integer(failed_evaluation_count, "failed_queries")
    _require(failed_evaluation_count < FAILED_QUERY_THRESHOLD and type(record_improved) is bool,
             "Invalid controller state")
    _integer(offspring_evaluation_count, "new_calls", 1)
    _require(offspring_evaluation_count == parameters["target_mu"] - parameters["elite_count"],
             "Controller update requires all registered offspring of a complete generation")
    _require(isinstance(mean_crossover_novelty_probability, Fraction)
             and 0 <= mean_crossover_novelty_probability <= 1, "An exact novelty mean is required")
    # Controller decision: success takes priority; stagnation counts evaluations.
    accumulated_failed_evaluations = 0 if record_improved else failed_evaluation_count + offspring_evaluation_count
    controller_event = ("SUCCESS" if record_improved else "STAGNATION"
                        if accumulated_failed_evaluations >= FAILED_QUERY_THRESHOLD else "NO_CHANGE")
    next_failed_evaluation_count = accumulated_failed_evaluations if controller_event == "NO_CHANGE" else 0
    stagnation_threshold_overshoot = (accumulated_failed_evaluations - FAILED_QUERY_THRESHOLD
                                     if controller_event == "STAGNATION" else 0)
    next_parameters = dict(parameters)
    if profile & 1:
        if controller_event == "SUCCESS":
            next_parameters["p_m"] = max(0.01, parameters["p_m"] / 2)
        elif controller_event == "STAGNATION":
            next_parameters["p_m"] = min(0.08, parameters["p_m"] * 2)
    if profile & 2:
        next_parameters["p_c"] = float(Fraction(1, 10) + Fraction(4, 5) * mean_crossover_novelty_probability)
    if profile & 4:
        if controller_event == "SUCCESS":
            next_parameters["target_mu"] = max(10, (parameters["target_mu"] + 1) // 2)
        elif controller_event == "STAGNATION":
            next_parameters["target_mu"] = min(100, parameters["target_mu"] * 2)
    if profile & 8:
        if controller_event == "SUCCESS":
            next_parameters["tournament_size"] = min(5, parameters["tournament_size"] + 1)
        elif controller_event == "STAGNATION":
            next_parameters["tournament_size"] = max(2, parameters["tournament_size"] - 1)
    if profile & 16:
        if controller_event == "SUCCESS":
            next_parameters["elite_count"] = min(5, parameters["elite_count"] + 1)
        elif controller_event == "STAGNATION":
            next_parameters["elite_count"] = max(1, parameters["elite_count"] - 1)
    _parameters(next_parameters, profile)
    # Decision monitoring: describe changes for the log without changing parameters.
    parameter_change_events = []
    for parameter_bit, parameter_name in enumerate(PARAMETER_NAMES):
        previous_value, next_value = parameters[parameter_name], next_parameters[parameter_name]
        parameter_change_events.append({
            "field": parameter_name, "enabled": bool(profile & (1 << parameter_bit)),
            "before": previous_value, "after": next_value,
            "direction": "increase" if next_value > previous_value else
                         "decrease" if next_value < previous_value else "unchanged",
            "at_boundary": next_value in PARAMETER_BOUNDS[parameter_name],
        })
    return {"parameters": next_parameters, "event": controller_event,
            "failed_queries_accumulated": accumulated_failed_evaluations,
            "failed_queries_after": next_failed_evaluation_count,
            "stagnation_overshoot": stagnation_threshold_overshoot,
            "parameter_events": parameter_change_events}

def _update_tournament(
    parameters, failed_evaluation_count, record_improved, offspring_evaluation_count,
    mean_crossover_novelty_probability, profile, *, schedule=None, completed_generation=1,
):
    """Determine the next tournament size after a complete generation.

    The adaptive profile responds to records and failures. Fixed profiles
    and replay do not use these signals to choose tournament sizes; their
    events are recorded only as observations.
    """
    # Validate signals and the complete offspring count.
    _parameters(parameters, profile)
    _integer(failed_evaluation_count, "failed_queries")
    _require(failed_evaluation_count < FAILED_QUERY_THRESHOLD and type(record_improved) is bool,
             "Invalid controller state")
    _integer(offspring_evaluation_count, "new_calls", 1)
    _require(offspring_evaluation_count == parameters["target_mu"] - parameters["elite_count"],
             "Controller update requires all registered offspring of a complete generation")
    _require(isinstance(mean_crossover_novelty_probability, Fraction)
             and 0 <= mean_crossover_novelty_probability <= 1, "An exact novelty mean is required")
    accumulated_failed_evaluations = 0 if record_improved else failed_evaluation_count + offspring_evaluation_count
    controller_event = ("SUCCESS" if record_improved else "STAGNATION"
                        if accumulated_failed_evaluations >= FAILED_QUERY_THRESHOLD else "NO_CHANGE")
    next_failed_evaluation_count = accumulated_failed_evaluations if controller_event == "NO_CHANGE" else 0
    stagnation_threshold_overshoot = (accumulated_failed_evaluations - FAILED_QUERY_THRESHOLD
                                     if controller_event == "STAGNATION" else 0)
    _integer(completed_generation, "completed_generation", 1)
    # Decision: adaptive rule, fixed schedule, or fixed tournament size.
    next_parameters = dict(parameters)
    if profile == "adaptive":
        if controller_event == "SUCCESS":
            next_parameters["tournament_size"] = min(5, parameters["tournament_size"] + 1)
        elif controller_event == "STAGNATION":
            next_parameters["tournament_size"] = max(2, parameters["tournament_size"] - 1)
    elif profile == "replay":
        next_parameters["tournament_size"] = scheduled_k(schedule, completed_generation)
    else:
        next_parameters["tournament_size"] = default_parameters(profile)["tournament_size"]
    _parameters(next_parameters, profile)
    # Decision monitoring; these records do not affect the next parameter values.
    parameter_change_events = []
    for parameter_name in PARAMETER_NAMES:
        previous_value, next_value = parameters[parameter_name], next_parameters[parameter_name]
        parameter_change_events.append({
            "field": parameter_name,
            "enabled": parameter_name == "tournament_size" and profile in ("adaptive", "replay"),
            "before": previous_value, "after": next_value,
            "direction": "increase" if next_value > previous_value else
                         "decrease" if next_value < previous_value else "unchanged",
            "at_boundary": next_value in PARAMETER_BOUNDS[parameter_name],
        })
    return {"parameters": next_parameters, "event": controller_event,
            "failed_queries_accumulated": accumulated_failed_evaluations,
            "failed_queries_after": next_failed_evaluation_count,
            "stagnation_overshoot": stagnation_threshold_overshoot,
            "parameter_events": parameter_change_events}

def update_parameters(
    parameters, failed_evaluation_count, record_improved, offspring_evaluation_count,
    mean_crossover_novelty_probability, profile, *, schedule=None, completed_generation=1,
):
    """Compute next-generation parameters and describe the decision.

    failed_evaluation_count: evaluations in preceding failed generations.
    record_improved: whether the completed generation achieved a strict record.
    offspring_evaluation_count: number of new offspring in this generation.
    mean_crossover_novelty_probability: exact mean of the crossover signal.
    profile: enabled adaptations or tournament profile name.
    schedule: fixed schedule, used only by the replay profile.
    completed_generation: index of the generation that has just completed.
    """
    if type(profile) is int:
        _require(schedule is None, "Для факторного профілю розклад не використовується")
        return _update_parameter(parameters, failed_evaluation_count, record_improved,
                                 offspring_evaluation_count, mean_crossover_novelty_probability, profile)
    return _update_tournament(parameters, failed_evaluation_count, record_improved,
                              offspring_evaluation_count, mean_crossover_novelty_probability, profile,
                              schedule=schedule, completed_generation=completed_generation)


@dataclass(frozen=True)
class Controller:
    """Control profile with a schedule fixed before the run."""
    profile: object
    schedule: tuple | None = None


def parameter_controller(profile):
    """Create a controller from the integer bit mask profile.

    0 keeps all parameters fixed; 1 enables mutation, 2 crossover,
    4 population size, 8 tournament size, and 16 elitism. Add values to
    enable combinations: 5 = mutation and population, 31 = all five rules.
    """
    _require(type(profile) is int, "Профіль параметрів має бути цілим числом")
    _profile(profile)
    return Controller(profile)


def tournament_controller(profile, schedule=None):
    """Create fixed, adaptive, or schedule-driven tournament selection.

    profile: k2-k5 use a fixed size; adaptive responds to success and
        stagnation; replay follows the fixed schedule in sequence.
    schedule: per-generation tournament sizes, used only by replay.
        Values count participants; they are not probabilities.
    """
    _require(type(profile) is str, "Назва турнірного профілю має бути рядком")
    _profile(profile)
    _require((profile == "replay") == (schedule is not None), "Розклад потрібен тільки replay")
    return Controller(profile, tuple(schedule) if schedule is not None else None)
