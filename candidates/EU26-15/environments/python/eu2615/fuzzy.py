"""Clean-room binary64 implementation of GARBO's sampled fuzzy system.

Only deterministic transitions are represented. No upstream module is
imported, no stochastic GARBO run is launched, and no paper endpoint is
evaluated.
"""

from __future__ import annotations

from bisect import bisect_left
from dataclasses import dataclass
import math
from typing import Any, Iterable, Mapping, Sequence

from .contract import ContractError, load_contract, validate_contract


class ZeroAreaError(ValueError):
    """Mirror scikit-fuzzy's zero-total-area defuzzification failure."""


@dataclass(frozen=True)
class PopulationStatistics:
    fv: float
    ft: float
    mlc: float
    ssc: float
    mean_fitness: float


@dataclass(frozen=True)
class Transition:
    branch: str
    cxpb: float
    mutpb: float
    mutop: tuple[float, float, float]

    def as_dict(self) -> dict[str, Any]:
        return {
            "branch": self.branch,
            "cxpb": self.cxpb,
            "mutpb": self.mutpb,
            "mutop": list(self.mutop),
        }


def source_arange(start: float, stop: float, step: float) -> tuple[float, ...]:
    """Reproduce NumPy arange's effective-step behavior for frozen inputs."""

    values = (float(start), float(stop), float(step))
    if not all(math.isfinite(value) for value in values):
        raise ValueError("arange arguments must be finite")
    if step <= 0.0 or stop <= start:
        raise ValueError("this verifier only accepts positive nonempty universes")
    count = int(math.ceil((stop - start) / step))
    effective_step = (start + step) - start
    return tuple(start + index * effective_step for index in range(count))


def _triangular_sample(x: float, parameters: Sequence[float]) -> float:
    a, b, c = parameters
    if not a <= b <= c:
        raise ContractError("invalid triangular membership parameters")
    value = 0.0
    if a != b and a < x < b:
        value = (x - a) / (b - a)
    if b != c and b < x < c:
        value = (c - x) / (c - b)
    if x == b:
        value = 1.0
    return value


def _trapezoidal_sample(x: float, parameters: Sequence[float]) -> float:
    a, b, c, d = parameters
    if not a <= b <= c <= d:
        raise ContractError("invalid trapezoidal membership parameters")
    value = 1.0
    if x <= b:
        value = _triangular_sample(x, (a, b, b))
    if x >= c:
        value = _triangular_sample(x, (c, c, d))
    if x < a or x > d:
        value = 0.0
    return value


def _sample_membership(
    universe: Sequence[float], specification: Sequence[Any]
) -> tuple[float, ...]:
    shape = specification[0]
    parameters = tuple(float(value) for value in specification[1:])
    if shape == "tri" and len(parameters) == 3:
        return tuple(_triangular_sample(x, parameters) for x in universe)
    if shape == "trap" and len(parameters) == 4:
        return tuple(_trapezoidal_sample(x, parameters) for x in universe)
    raise ContractError(f"unsupported membership specification: {specification!r}")


def _interp_zero_outside(
    universe: Sequence[float], sampled: Sequence[float], value: float
) -> float:
    if len(universe) != len(sampled) or not universe:
        raise ContractError("invalid sampled membership")
    if value < universe[0] or value > universe[-1]:
        return 0.0
    upper = bisect_left(universe, value)
    if upper < len(universe) and universe[upper] == value:
        return sampled[upper]
    if upper == 0 or upper == len(universe):
        return 0.0
    lower = upper - 1
    x0, x1 = universe[lower], universe[upper]
    y0, y1 = sampled[lower], sampled[upper]
    return y0 + (value - x0) * (y1 - y0) / (x1 - x0)


def _piecewise_centroid(
    universe: Sequence[float], membership: Sequence[float]
) -> float:
    if len(universe) != len(membership) or not universe:
        raise ContractError("centroid arrays must be nonempty and aligned")
    if sum(membership) == 0.0:
        raise ZeroAreaError("total area is zero in defuzzification")

    sum_moment_area = 0.0
    sum_area = 0.0
    for index in range(1, len(universe)):
        x1, x2 = universe[index - 1], universe[index]
        y1, y2 = membership[index - 1], membership[index]
        if (y1 == 0.0 and y2 == 0.0) or x1 == x2:
            continue
        if y1 == y2:
            moment = 0.5 * (x1 + x2)
            area = (x2 - x1) * y1
        elif y1 == 0.0:
            moment = (2.0 / 3.0) * (x2 - x1) + x1
            area = 0.5 * (x2 - x1) * y2
        elif y2 == 0.0:
            moment = (1.0 / 3.0) * (x2 - x1) + x1
            area = 0.5 * (x2 - x1) * y1
        else:
            moment = (
                (2.0 / 3.0)
                * (x2 - x1)
                * (y2 + 0.5 * y1)
                / (y1 + y2)
                + x1
            )
            area = 0.5 * (x2 - x1) * (y1 + y2)
        sum_moment_area += moment * area
        sum_area += area
    if sum_area == 0.0:
        raise ZeroAreaError("piecewise centroid area is zero")
    return sum_moment_area / sum_area


class GarboFuzzySystem:
    """Contract-bound deterministic GARBO fuzzy transition."""

    def __init__(self, contract: Mapping[str, Any] | None = None):
        if contract is None:
            loaded = load_contract()
        else:
            loaded = dict(contract)
            validate_contract(loaded)
        self.contract = loaded
        self._universes = {
            name: source_arange(spec["start"], spec["stop"], spec["step"])
            for name, spec in loaded["universes"].items()
        }
        for name, universe in self._universes.items():
            expected = loaded["universes"][name]
            if len(universe) != expected["length"] or universe[-1] != expected["last"]:
                raise ContractError(f"universe {name} does not match frozen arange")

        self._memberships: dict[str, dict[str, tuple[float, ...]]] = {}
        for variable, terms in loaded["memberships"].items():
            universe = self._universes[variable]
            self._memberships[variable] = {
                term: _sample_membership(universe, specification)
                for term, specification in terms.items()
            }

    def universe(self, name: str) -> tuple[float, ...]:
        return self._universes[name]

    def memberships(self, variable: str, value: float) -> dict[str, float]:
        numeric = float(value)
        if not math.isfinite(numeric):
            raise ValueError("membership input must be finite")
        universe = self._universes[variable]
        return {
            term: _interp_zero_outside(universe, sampled, numeric)
            for term, sampled in self._memberships[variable].items()
        }

    def _infer(
        self,
        rule_name: str,
        row_memberships: Mapping[str, float],
        column_memberships: Mapping[str, float],
    ) -> float:
        rules = self.contract["rule_matrices"][rule_name]
        output_name = rules["output"]
        aggregated = [0.0] * len(self._universes[output_name])
        for row_index, row_term in enumerate(rules["rows"]):
            for column_index, column_term in enumerate(rules["columns"]):
                activation = min(
                    row_memberships[row_term], column_memberships[column_term]
                )
                consequent_term = rules["terms"][row_index][column_index]
                consequent = self._memberships[output_name][consequent_term]
                for index, degree in enumerate(consequent):
                    aggregated[index] = max(
                        aggregated[index], min(activation, degree)
                    )
        return _piecewise_centroid(self._universes[output_name], aggregated)

    def crossover_probability(self, fv: float, mlc: float) -> float:
        return self._infer(
            "crossover", self.memberships("fv", fv), self.memberships("mlc", mlc)
        )

    def mutation_probability(self, ft: float, mlc: float) -> float:
        # Source-faithful quirk: GARBO.py calls intFV(ft_input), not intFT.
        return self._infer(
            "mutation", self.memberships("mlc", mlc), self.memberships("fv", ft)
        )

    def insertion_probability(self, ssc: float, mlc: float) -> float:
        return self._infer(
            "insertion",
            self.memberships("ssc", ssc),
            self.memberships("mlc", mlc),
        )

    def deletion_probability(self, ssc: float, mlc: float) -> float:
        return self._infer(
            "deletion",
            self.memberships("ssc", ssc),
            self.memberships("mlc", mlc),
        )

    def mutation_operator_probabilities(
        self, ssc: float, mlc: float
    ) -> tuple[float, float, float]:
        deletion = self.deletion_probability(ssc, mlc)
        insertion = self.insertion_probability(ssc, mlc)
        substitution = 1.0 - (deletion + insertion)
        return insertion, deletion, substitution

    def feature_rank_delta(self, usage: float, benefit: float) -> float:
        return self._infer(
            "feature_rank",
            self.memberships("eva", usage),
            self.memberships("eva", benefit),
        )

    def transition_from_statistics(
        self, fv: float, ft: float, mlc: float, ssc: float
    ) -> Transition:
        values = tuple(float(value) for value in (fv, ft, mlc, ssc))
        if not all(math.isfinite(value) for value in values):
            raise ValueError("transition statistics must be finite")
        fv, ft, mlc, ssc = values
        override = self.contract["override"]
        if ssc > override["threshold"]:
            return Transition(
                branch="similarity_override",
                cxpb=float(override["cxpb"]),
                mutpb=float(override["mutpb"]),
                mutop=tuple(float(value) for value in override["mutop"]),
            )
        return Transition(
            branch="fuzzy",
            cxpb=self.crossover_probability(fv, mlc),
            mutpb=self.mutation_probability(ft, mlc),
            mutop=self.mutation_operator_probabilities(ssc, mlc),
        )

    @staticmethod
    def population_statistics(
        fitness: Iterable[float],
        previous_mean_fitness: float,
        chromosomes: Sequence[Iterable[int]],
    ) -> PopulationStatistics:
        fitness_values = tuple(float(value) for value in fitness)
        previous = float(previous_mean_fitness)
        if not fitness_values or not math.isfinite(previous):
            raise ValueError("fitness and previous mean must be nonempty and finite")
        if not all(math.isfinite(value) for value in fitness_values):
            raise ValueError("fitness values must be finite")
        if len(fitness_values) != len(chromosomes):
            raise ValueError("fitness and chromosome counts must match")
        if len(chromosomes) < 2:
            raise ValueError("ssc requires at least two chromosomes")

        chromosome_sets: list[frozenset[int]] = []
        for chromosome in chromosomes:
            values = tuple(chromosome)
            as_set = frozenset(values)
            if len(as_set) != len(values):
                raise ValueError("chromosomes must use set semantics without duplicates")
            chromosome_sets.append(as_set)

        maximum = max(fitness_values)
        if maximum == 0.0:
            raise ValueError("fv is undefined when maximum fitness is zero")
        mean_fitness = sum(fitness_values) / len(fitness_values)
        fv = (maximum - mean_fitness) / maximum
        ft = abs(mean_fitness - previous)
        mlc = sum(len(chromosome) for chromosome in chromosome_sets) / len(
            chromosome_sets
        )

        similarity_sum = 0.0
        comparisons = 0
        for left_index in range(len(chromosome_sets)):
            for right_index in range(left_index):
                left = chromosome_sets[left_index]
                right = chromosome_sets[right_index]
                union = left | right
                if not union:
                    raise ValueError("Jaccard similarity is undefined for empty union")
                similarity_sum += len(left & right) / len(union)
                comparisons += 1
        if comparisons == 0:
            raise ValueError("ssc requires at least one pair")
        ssc = similarity_sum / comparisons
        return PopulationStatistics(fv, ft, mlc, ssc, mean_fitness)

    def transition_from_population(
        self,
        fitness: Iterable[float],
        previous_mean_fitness: float,
        chromosomes: Sequence[Iterable[int]],
    ) -> tuple[PopulationStatistics, Transition]:
        statistics = self.population_statistics(
            fitness, previous_mean_fitness, chromosomes
        )
        transition = self.transition_from_statistics(
            statistics.fv, statistics.ft, statistics.mlc, statistics.ssc
        )
        return statistics, transition
