# EU26-18 formula and algorithm audit

Requirements tag: `STRICT_ADAPTIVE_GA_2026-08-10`

Audit outcome: `UNKNOWN`

## Source identity

The UNED accepted manuscript was downloaded again during this audit. It is
877981 bytes and has SHA-256
`d534e4a0d2612d409adea33f899133cf346cdeb6c5ef04e6820565d67e4a35f2`,
matching the pinned source manifest.

The official Springer version-of-record images for Algorithms 2, 3, and 4
match the accepted manuscript, including the undefined symbols and helper
described below:

- [Algorithm 2](https://media.springernature.com/full/springer-static/image/art%3A10.1007%2Fs00500-023-09049-0/MediaObjects/500_2023_9049_Figb_HTML.png)
- [Algorithm 3](https://media.springernature.com/full/springer-static/image/art%3A10.1007%2Fs00500-023-09049-0/MediaObjects/500_2023_9049_Figc_HTML.png)
- [Algorithm 4](https://media.springernature.com/full/springer-static/image/art%3A10.1007%2Fs00500-023-09049-0/MediaObjects/500_2023_9049_Figd_HTML.png)

## Algorithm 2 transcription

For a decision coordinate `x` with lower and upper bounds `x_l` and `x_u`, the
paper first applies the fixed gate `U(0,1) < p_m`. When the gate passes:

```text
delta_1 = (x - x_l) / (x_u - x_l)
delta_2 = (x_u - x) / (x_u - x_l)
r = U(0,1)
```

For `r <= 0.5`:

```text
delta_q = (
  2*r + (1 - 2*r)*(1 - delta_1)^(eta_m + 1)
)^(1/(eta_m + 1)) - 1
```

For `r > 0.5`:

```text
delta_q = 1 - (
  2*(1 - r) + 2*(r - 0.5)*(1 - delta_2)^(eta_m + 1)
)^(1/(eta_m + 1))
```

The paper then writes:

```text
x_m = x_c + delta_q*(x_u - x_l)
```

and clips `x_m` to the decision-variable bounds.

`x_c` is not defined in the Algorithm 2 inputs or body. The reference kernel
uses the current `x`, which matches the conventional polynomial-mutation
equation, but records this as a clean-room interpretation rather than a source
fact.

## Algorithm 4 literal behavior

For selected parents `P`, Algorithm 4 says:

```text
shared_eta = sum(parent.mutPar for parent in P) / size(P)
shared_eta = shared_eta + Normal(0, 1)
shared_eta = repair(shared_eta, eta_lower, eta_upper)
for parent in P:
    parent.mutPar = shared_eta
```

One Gaussian realization is used for the selected parent group. The paper sets
the experimental bounds to `[1, 100]`. It does not define whether `repair`
clips, reflects, resamples, wraps, or rejects an out-of-bounds value. Algorithm
4 also changes the capitalization of `mutPar` to `mutpar` in the repair call.

## Algorithm 3 ordering

The exact published order of the novel mating section is:

1. select parents;
2. update their distribution index;
3. call SBX crossover;
4. mutate child 1 with `child1.eta_m`;
5. mutate child 2 with `child2.eta_m`;
6. append the child pair.

After the offspring population is formed, NSGA-II joins parent and offspring
populations, evaluates rank and crowding distance, and reduces the joined
population.

The paper does not say whether selected parents are copies or references to
the current population. It also does not define whether `eta_m` is an SBX
coordinate, a separately copied attribute, or handled differently when
crossover is skipped. Consequently,

```text
eta_child = repair(mean(parent_eta) + epsilon)
```

is a plausible intended invariant, but is not a literal or fully specified
Algorithm 4 assignment.

## Fixed and dynamic controls

| Control | Source-supported behavior | Audit status |
|---|---|---|
| `eta_m` | Per-individual state updated inside the mating loop | Dynamic `mutation_strength` |
| `p_m` | `1/n`, where `n` is the decision-vector dimension | Static |
| `p_c` | `0.9` | Static |
| Population size | `300` | Static |
| SBX distribution index | `20` | Static |
| Maximum evaluations | `25000` | Static threshold, terminal-batch semantics unknown |
| Parent selection | `selectParents`; binary tournament is described as usual NSGA-II practice | Exact selector and tie-breaking unknown |

No published evidence shows dynamic elitism, operator weights, replacement
rate, archive size, local search, PSO, DE, fuzzy/RL/neural control, or another
optimizer. Thus the GA, non-hybrid, allowed-control, and within-run adaptation
gates remain `PASS`. The exact update/application gate is `UNKNOWN`, which
forces the overall strict decision to `UNKNOWN`.

## Executable evidence mapping

| Source item | Executable check |
|---|---|
| Algorithm 4 mean and shared update | `[10, 20] + 0.25 -> 15.25` for both parents |
| Declared clamp profile | lower and upper overflow fixtures |
| Algorithm 2 left/right branches | fixed `float.hex()` golden vectors |
| `r <= 0.5` boundary | exact midpoint and `nextafter` checks |
| Mutation-strength direction | equal random input at `eta_m=1` and `100` |
| Strict mutation gate | `U == p_m` does not mutate |
| `p_m = 1/n` | decision dimension excludes the strategy field |
| Algorithm 3 order | explicit event trace around the novelty kernel |
| Worker scheduling | exact digest for serial and 1/2/4 spawn processes |
| OS/runtime portability | aggregate quantized digest from five CI machines |
| Evaluation-budget ambiguity | full-300-batch sensitivity witness ends at 25200 |

These tests can reject incorrect transcriptions of the declared profile. They
cannot decide which missing semantics the authors actually used.
