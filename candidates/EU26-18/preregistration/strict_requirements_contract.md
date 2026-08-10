# Strict adaptive-GA requirements contract

Requirements tag: `STRICT_ADAPTIVE_GA_2026-08-10`

Freeze date: 2026-08-10

This contract applies only to the selected algorithm variant and experiment.
Search snippets, titles, abstracts without method details, and the word
"adaptive" are not sufficient evidence.

## Allowed dynamic controls

Let the allowed set be:

```text
S = {
  crossover_probability,
  mutation_probability,
  mutation_strength,
  population_size,
  tournament_size,
  selection_pressure
}
```

Let `A` be the complete set of GA controls that change during one run. A
candidate receives `PASS_STRICT` only when all of the following are directly
supported by primary evidence:

```text
A is nonempty
A is a subset of S
algorithm_family is GA
hybrid_component_set is empty
the update occurs inside one run
the update is feedback-based or self-adaptive under selection
the update rule and its application point are specified
```

## Definitions used by this audit

- `mutation_strength` includes a scale, radius, amplitude, distribution index,
  or equivalent numeric control that changes the magnitude distribution of one
  fixed mutation operator.
- A time-only rule `theta_t = f(t)`, offline tuning, or an unselected random
  schedule does not qualify.
- Self-adaptation qualifies only when the control is represented in the evolving
  state, inherited, and exposed to fitness-based parent or survivor selection.
- Static elitism, replacement, offspring size, operator types, and operator
  weights are allowed. Dynamically changing any of them causes `FAIL_HARD`.
- Normal solution genes, fitness values, ranks, crowding distance, and population
  membership are state, not additional GA control parameters.
- Borrowing a formula from another evolutionary method is not automatically a
  hybrid. A hybrid requires an additional optimizer or controller that generates,
  improves, selects, or controls solutions outside the admitted GA pipeline.

## Statuses

- `PASS_STRICT`: every hard gate is directly supported.
- `FAIL_HARD`: a direct violation is found.
- `UNKNOWN`: required evidence is missing or ambiguous.
- `CONFLICT`: primary sources disagree on a hard gate.

Only `PASS_STRICT` is an admitted candidate. `UNKNOWN` is never upgraded through
an assumption.

## Auxiliary preference

"More than 10 other parameters" is recorded separately as `VERIFIED_11_PLUS`,
`VERIFIED_LE_10`, or `UNKNOWN`. It never changes the strict decision and is not
inferred from chromosome length or benchmark dimension.
