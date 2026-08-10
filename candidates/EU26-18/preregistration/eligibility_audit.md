# EU26-18 strict eligibility audit

Requirements tag: `STRICT_ADAPTIVE_GA_2026-08-10`

Decision: `UNKNOWN`

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
| Update is feedback-based/self-adaptive | PASS | Section 3.3 stores `eta_m` per individual, and selected-parent values enter the next shared update. NSGA-II rank/crowding selection supplies selection-mediated feedback, although exact child inheritance remains unknown. |
| No other GA control adapts | PASS | Section 4.2 fixes population size 300, evaluations 25000, `pc = 0.9`, crossover index 20, and `pm = 1/n`; it states the modified algorithm is otherwise configured exactly like baseline NSGA-II. |
| Update rule is specified | UNKNOWN | Algorithms 3 and 4 specify averaging, one Gaussian perturbation, a call to `repair`, parent update timing, and later child use. They do not define `repair`, parent copy/reference semantics, or exact `eta_m` inheritance through crossover. Algorithm 2 also uses undefined `x_c`. |
| Experimental use is demonstrated | PASS | The paper compares static PLM and SA-PLM over 25 benchmark problems and 30 independent executions per problem. |

## Exact adaptive state and update

The paper says that each individual extends its decision vector from

```text
<x_1, x_2, ..., x_n>
```

to

```text
<x_1, x_2, ..., x_n, eta_m>.
```

For selected parents `P`, Algorithm 4 literally applies the following update
before crossover:

```text
eta_shared = mean(parent.eta_m for parent in P) + Normal(0, 1)
eta_shared = repair(eta_shared, 1, 100)
for parent in P:
    parent.eta_m = eta_shared
```

The repaired value is written to every selected parent. Algorithm 3 then calls
crossover and later reads `child1.eta_m` and `child2.eta_m`. The paper does not
define how those child fields are inherited, whether parent objects are copies
or population references, or what `repair` does. Therefore the previously used
direct child equation is only a clean-room interpretation and is not primary
source fact. The literal parent equation is:

```text
eta_shared = repair(mean(eta_selected_parents) + epsilon, 1, 100)
epsilon ~ Normal(0, 1)
```

Subject to the unresolved exact semantics, this control is
`mutation_strength`, not `mutation_probability`:

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
3. The selected parents' current `eta_m` values are averaged and one shared
   updated value is written to them; exact child inheritance is unspecified.
4. Their children are evaluated with the current optimization objectives.
5. Selection in later generations determines which resulting `eta_m` values
   continue to reproduce.

Therefore the disclosed concept can propagate different values at the same
generation due to different selected population states. This is not
`eta_t = f(t)`, offline tuning, or an unselected random schedule. This feedback
classification does not resolve the missing execution semantics.

## Exhaustive dynamic-control inventory

| Control | Run behavior | Strict classification |
|---|---|---|
| Polynomial mutation distribution index `eta_m` | Stored per individual; selected-parent values are averaged, Gaussian-perturbed, passed to undefined `repair`, and written back before crossover | Dynamic `mutation_strength`; exact execution UNKNOWN |
| Population size | Fixed at 300 | Static allowed control |
| Crossover probability `pc` | Fixed at 0.9 | Static allowed control |
| Mutation probability `pm` | Fixed at `1/n` | Static allowed control |
| SBX crossover distribution index | Fixed at 20 | Static, not adapted |
| Maximum evaluations | Fixed at 25000 | Stopping budget, not adapted |
| Parent selection | NSGA-II `selectParents` call; Section 3.1 says binary tournament is usual, but the exact selector and tie-breaking are not specified | No disclosed numeric selection-pressure adaptation |
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
auxiliary claim is made. This field does not affect the strict decision.

## Source and claim limits

- The final article's detailed source code was not identified in the inspected
  primary records.
- Algorithm 2 line 11 uses `x_c`, although only the current coordinate `x` is
  introduced. Interpreting `x_c` as `x` is a clean-room assumption.
- Algorithm 4 calls `repair` without defining clamp, reflection, resampling, or
  another boundary procedure. It also contains a `mutP ar`/`mutpar` case typo.
- The paper says initial `eta_m` values are randomly chosen between their
  bounds; it does not state a uniform distribution or endpoint semantics.
- Selected-parent copy/reference behavior and child `eta_m` inheritance through
  SBX are not specified.
- `offspringSize`, terminal handling of the 25000-evaluation budget, exact
  jMetal/JDK revisions, author RNG/seeds, and raw runs are unavailable.
- Detailed pseudocode locators come from the author's UNED-hosted accepted
  manuscript of the 2023 article; the version-of-record abstract independently
  confirms the same self-adapted polynomial-mutation distribution index and
  25-problem experiment.
- The audit confirms the GA/non-hybrid/control classification, but the final
  strict status is `UNKNOWN`. It does not claim source-native execution, a
  reproduced table, author seeds, raw-run provenance, or `PASS_FULL`.
- If later evidence shows another in-run adaptive control or a second optimizer,
  the status must be downgraded to `CONFLICT` or `FAIL_HARD`.

## Primary-source locators

- Springer version of record: title page and abstract.
- UNED publication record: date, citation, institutional ownership, and DOI.
- UNED accepted manuscript, physical PDF page 9: mutation-strength mapping.
- UNED accepted manuscript, physical PDF page 10: individual representation
  and random initialization statement.
- UNED accepted manuscript, physical PDF page 11: Algorithm 2 equations and
  undefined `x_c`.
- UNED accepted manuscript, physical PDF page 12: Algorithm 3.
- UNED accepted manuscript, physical PDF page 13: Algorithm 4 and fixed
  experimental controls.
- UNED accepted manuscript, physical PDF page 14: `eta_m` bounds and 30-run
  protocol.
