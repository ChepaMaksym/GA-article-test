"""Population accounting and representation probabilities, without search."""
from __future__ import annotations

from fractions import Fraction
import math


def _integer(value, name, minimum=0):
    if type(value) is not int or value < minimum:
        raise ValueError(f"{name} must be an integer >= {minimum}")


def population_domain(total_evaluations=50000):
    """Allow one elite, at least one offspring, and one complete generation."""
    _integer(total_evaluations, "total_evaluations", 3)
    return 2, (total_evaluations + 1) // 2


def generation_accounting(population_size, total_evaluations=50000, elite_count=1):
    _integer(population_size, "population_size", 2)
    _integer(elite_count, "elite_count", 1)
    _integer(total_evaluations, "total_evaluations", 1)
    if elite_count >= population_size or population_size > total_evaluations:
        raise ValueError("Population or elite count cannot fit the evaluation limit")
    offspring_quota = population_size - elite_count
    full, partial = divmod(total_evaluations - population_size, offspring_quota)
    return {"initial_evaluations": population_size, "offspring_per_generation": offspring_quota,
            "new_evaluations": total_evaluations - population_size,
            "complete_generations": full, "partial_offspring": partial,
            "total_evaluations": total_evaluations}


def exact_representation_probability(item_count, population_size):
    """Exact small-instance probability with one empty mask and fair random bits."""
    _integer(item_count, "item_count", 1)
    _integer(population_size, "population_size", 2)
    exponent = population_size - 1
    if exponent * item_count > 1000000:
        raise ValueError("Use the stable floating-point function for large curves")
    return Fraction(((1 << exponent) - 1) ** item_count, 1 << (exponent * item_count))


def representation_probability(item_count, population_size):
    """Stable plot value; rounding near one is not a certainty guarantee."""
    _integer(item_count, "item_count", 1)
    _integer(population_size, "population_size", 2)
    missing_one_probability = math.ldexp(1.0, -(population_size - 1))
    return math.exp(item_count * math.log1p(-missing_one_probability))


def minimum_representation_population(item_count, confidence):
    """Find the exact minimum for a user-supplied representation confidence."""
    _integer(item_count, "item_count", 1)
    confidence = Fraction(str(confidence))
    if not 0 < confidence < 1:
        raise ValueError("Confidence must be strictly between zero and one")
    # The union bound supplies a starting point without rounding confidence to 1.
    failure = 1 - confidence
    value = 1 + math.log2(item_count) - (math.log2(failure.numerator) - math.log2(failure.denominator))
    candidate = max(2, math.ceil(value))
    while exact_representation_probability(item_count, candidate) < confidence:
        candidate += 1
    while candidate > 2 and exact_representation_probability(item_count, candidate - 1) >= confidence:
        candidate -= 1
    return candidate
