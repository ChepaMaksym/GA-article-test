# EU26-18 strict eligibility audit

Requirements tag: `STRICT_ADAPTIVE_GA_2026-08-10`

Decision: `PASS_STRICT`

## Candidate identity

- Authors: Jose L. Carles-Bou and Severino F. Galan.
- Title: "Self-adaptive polynomial mutation in NSGA-II".
- Venue: *Soft Computing* 27, 17711-17727.
- DOI: [`10.1007/s00500-023-09049-0`](https://doi.org/10.1007/s00500-023-09049-0).
- Published: 21 August 2023.
- Qualifying affiliation: Universidad Nacional de Educacion a Distancia
  (UNED), Madrid, Spain.
- Selected variant: NSGA-II with self-adaptive polynomial mutation, called
  `NSGA-II + SA-PLM` in the experimental comparison.

The publisher article page establishes the version-of-record identity, date,
authors, title, and the claim that the proposed mechanism controls the polynomial
mutation distribution index. The UNED repository supplies the institutional
record and the author's UNED-hosted accepted manuscript of the same 2023
article.

## Hard-gate matrix

| Gate | Status | Direct evidence |
|---|---|---|
| Publication year is 2020 or later | PASS | Springer version of record: published 21 August 2023. |
| At least one US or EU affiliation | PASS | Both authors are affiliated with UNED in Madrid, Spain. |
| Selected algorithm is a GA | PASS | The publisher identifies NSGA-II; the accepted manuscript's Section 3.1 and Algorithm 3 retain the NSGA-II genetic pipeline. |
| No hybrid optimizer/controller | PASS | Algorithm 3 contains only NSGA-II parent selection, distribution-index update, SBX crossover, polynomial mutation, evaluation, and NSGA-II survivor reduction. |
| At least one allowed control changes in-run | PASS | Individual polynomial-mutation distribution index `eta_m` changes before crossover and mutation during the loop. |
| Dynamic control is mutation strength | PASS | Section 3.2 states that `eta_m` controls whether mutations stay near the parent or make larger moves. |
| Update is feedback-based/self-adaptive | PASS | Section 3.3 stores `eta_m` in the genome. Selected parents provide inherited indices; NSGA-II rank/crowding selection closes the feedback loop. |
| No other GA control adapts | PASS | Section 4.2 fixes population size 300, evaluations 25000, `pc = 0.9`, crossover index 20, and `pm = 1/n`; it states the modified algorithm is otherwise configured exactly like baseline NSGA-II. |
| Update rule is specified | PASS | Algorithms 3 and 4 specify inheritance, averaging, Gaussian perturbation, repair to bounds, timing, and use by polynomial mutation. |
| Experimental use is demonstrated | PASS | The paper compares static PLM and SA-PLM over 25 benchmark problems and 30 independent executions per problem. |

## Exact adaptive state and update

Each individual extends its decision vector from

```text
<x_1, x_2, ..., x_n>
```

to

```text
<x_1, x_2, ..., x_n, eta_m>.
```

For selected parents `P`, Algorithm 4 applies the following update before the
children are mutated:

```text
eta_candidate = mean(parent.eta_m for parent in P) + Normal(0, 1)
eta_candidate = repair(eta_candidate, 1, 100)
```

The repaired value is written to the selected parent strategy state, inherited
through crossover, and supplied to the fixed polynomial mutation operator for
each child. In mathematical form:

```text
eta_child = repair(mean(eta_selected_parents) + epsilon, 1, 100)
epsilon ~ Normal(0, 1)
```

This is `mutation_strength`, not `mutation_probability`:

- `pm = 1/n` is static and decides whether a decision variable is mutated;
- `eta_m` changes the perturbation distribution when mutation occurs;
- lower `eta_m` yields broader/larger moves;
- higher `eta_m` yields narrower/smaller moves.

## Feedback proof

The Gaussian term alone would be an unqualified random change. The complete
mechanism is self-adaptive because:

1. `eta_m` is part of each evolving individual's genome.
2. Current NSGA-II non-domination rank and crowding distance determine which
   individuals become parents and survivors.
3. The selected parents' current `eta_m` values are averaged and inherited.
4. Their children are evaluated with the current optimization objectives.
5. Selection in later generations determines which resulting `eta_m` values
   continue to reproduce.

Therefore two runs at the same generation can propagate different new values due
to different selected population states. This is not `eta_t = f(t)`, offline
tuning, or an unselected random schedule.

## Exhaustive dynamic-control inventory

| Control | Run behavior | Strict classification |
|---|---|---|
| Polynomial mutation distribution index `eta_m` | Individual, inherited, averaged, Gaussian-perturbed, repaired to `[1, 100]` | Dynamic `mutation_strength` |
| Population size | Fixed at 300 | Static allowed control |
| Crossover probability `pc` | Fixed at 0.9 | Static allowed control |
| Mutation probability `pm` | Fixed at `1/n` | Static allowed control |
| SBX crossover distribution index | Fixed at 20 | Static, not adapted |
| Maximum evaluations | Fixed at 25000 | Stopping budget, not adapted |
| Parent selection | Fixed NSGA-II rank/crowding rule | No numeric selection-pressure adaptation |
| Survivor selection | Fixed NSGA-II sorting/reduction | No replacement adaptation |
| Operator choice/weights | One fixed SBX and one fixed PLM operator | No adaptive operator selection |

No evidence was found in the selected variant for dynamic elitism, replacement
rate, offspring size, archive size, operator choice, operator weights, penalty,
surrogate model, local search, or another optimizer.

## Hybrid screen

The selected pipeline does not contain PSO, DE, simulated annealing, local or
tabu search, fuzzy logic, reinforcement learning, a neural controller, genetic
programming, a meta-GA, or adaptive operator selection.

Section 3.3 says the representation idea follows a procedure used in evolutionary
programming and evolution strategies. This is a provenance statement about the
self-adaptation idea, not execution of a second optimizer. Algorithm 3 remains a
single NSGA-II pipeline, so the selected variant is classified `non_hybrid`.

## More-than-10 preference

Status: `UNKNOWN`.

The experiment table directly reports decision-vector dimensions up to 30 and
several benchmark instances with 12, 22, or 30 variables. The new protocol does
not equate those dimensions with "more than 10 other parameters", so no stronger
auxiliary claim is made. This field does not affect `PASS_STRICT`.

## Source and claim limits

- The final article's detailed source code was not identified in the inspected
  primary records.
- Detailed pseudocode locators come from the author's UNED-hosted accepted
  manuscript of the 2023 article; the version-of-record abstract independently
  confirms the same self-adapted polynomial-mutation distribution index and
  25-problem experiment.
- The audit establishes method eligibility only. It does not claim source-native
  execution, a reproduced table, author seeds, raw-run provenance, or
  `PASS_FULL`.
- If later evidence shows another in-run adaptive control or a second optimizer,
  the status must be downgraded to `CONFLICT` or `FAIL_HARD`.

## Primary-source locators

- Springer version of record: title page and abstract.
- UNED publication record: date, citation, institutional ownership, and DOI.
- UNED accepted manuscript, physical PDF page 9: mutation-strength mapping.
- UNED accepted manuscript, physical PDF page 12: Algorithm 3.
- UNED accepted manuscript, physical PDF page 13: Algorithm 4 and fixed
  experimental controls.
- UNED accepted manuscript, physical PDF page 14: `eta_m` bounds and 30-run
  protocol.
