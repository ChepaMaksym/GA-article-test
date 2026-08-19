# EU26-23 - Pilcher SAGA-FSTSP clean-room OLD-first candidate

## Frozen status

`PREREGISTERED_OLD_CLEANROOM / HYBRID_BLOCKED_BY_OLD_NUMERIC_GATE`

EU26-23 is a fresh candidate branch from `research/EU26-07-reset-jump-verification`. It does not inherit implementation files, results, seeds, claims, or thesis conclusions from EU26-21 / PR #19. The earlier EU26-22 screen was deleted after an incomplete source audit. EU26-23 is opened only because the deeper audit found an exact public n=20 benchmark file and a literal 30-run numerical endpoint in the paper.

## Reference study

Ted Pilcher, *A Self-Adaptive Genetic Algorithm for the Flying Sidekick Travelling Salesman Problem*, arXiv:2310.14713v1, 23 October 2023, DOI `10.48550/arXiv.2310.14713`.

The study solves an applied last-mile delivery problem in which a truck and one drone jointly visit customers. The selected instance has 20 nodes and therefore exceeds the project threshold of 15 applied decision positions. The joint permutation and node-type representation is discrete, non-convex and contains many local optima.

## Frozen public data

Primary benchmark repository:

- repository: `pcbouman-eur/TSP-D-Instances`;
- pinned commit: `73c51b323b26605f9dea6f94c8f57d4204cd2f05`;
- instance: `singlecenter/singlecenter-63-n20.txt`;
- instance Git blob SHA-1: `55ca3a5f43821cc00c0e7c6856d55170a145264f`;
- instance-data license: CC BY-SA 4.0;
- customer count: 19 plus one depot, 20 positions in the paper representation.

The repository file is the exact instance named by the paper for its Taguchi experiment.

## Frozen OLD numerical endpoint

The primary OLD reproduction target is Table 2, configuration 7:

```text
instance: singlecenter-63-n20
independent trials: 30
generations per trial: 1,000,000
innovation rate: 7
initial drone percentage: 8
population size: 50,000
tournament size: 5
reported mean final fitness: 448.68
```

The paper describes population size in thousands; therefore Table 2 value `50` is interpreted as 50,000 individuals. The paper calls the fourth factor “tour size” in the table but defines `t` as tournament size in Section 4.5; EU26-23 freezes the operational interpretation as tournament size.

## OLD mathematical profile

For coordinates `(x_i, y_i)`, the symmetric distance matrix is

```text
d_ij = sqrt((x_i - x_j)^2 + (y_i - y_j)^2)
```

The paper fixes the truck speed to `1` and the drone speed ratio to `alpha = 2`:

```text
tT_ij = d_ij
tD_ij = d_ij / alpha
```

A synchronized truck/drone segment contributes the maximum of the truck and drone segment times, and tour fitness is the total makespan:

```text
t_T = sum_{s in T} t_S(s)
```

For predecessor `i`, node `j` and successor `k`, initial drone-selection saving is

```text
s_j = max(tT_ij + tT_jk - max(tD_ij + tD_jk, tT_ik), 1)
p_j = s_j / sum(s)
```

## Frozen adaptive state

Each candidate co-evolves an eight-option memeplex:

```text
M = (C, CP, CM, DM, TM, TP, TOM, TOP)
```

where:

- `C`: one of nine crossover variants;
- `CP`: crossover application probability on the integer 0-10 lattice;
- `CM`: one of four combined-node mutation operators;
- `DM`: one of six drone-node mutation operators;
- `TM`: one of two truck-only mutation operators;
- `TP`: node-type mutation probability on the integer 0-10 lattice;
- `TOM`: one of three tour mutation operators;
- `TOP`: tour mutation probability on the integer 0-10 lattice.

The offspring inherit the memeplex of the fitter parent. For every meme option, draw `r` uniformly from the integer set `0..10`; when `r < innovationRate`, replace that option with a new uniformly sampled valid value from its domain.

The paper does not state a separate initial memeplex distribution. The primary clean-room interpretation is therefore frozen **before outcomes** as independent uniform sampling over each valid domain, matching the paper’s “new random value” transition and giving every disclosed option nonzero initial support. A deterministic midpoint initialization is allowed only as a labelled sensitivity diagnostic and may not replace the primary result.

## Representation and operator order

The candidate chromosome is the depot-fixed permutation of all 20 nodes plus a node type at every locus:

```text
1 = combined
2 = drone-only
3 = truck-only
```

The generation order is frozen as:

1. tournament-select two parents;
2. use the fitter parent’s crossover operator and probability;
3. apply tour mutation first;
4. apply node-type mutation second;
5. repair connected drone tours and disconnected truck-only nodes;
6. mutate the inherited memeplex;
7. evaluate offspring;
8. retain the two lowest-fitness individuals among both parents and both offspring.

## Initial TSP tour

The paper initializes every chromosome from an optimal Concorde TSP tour. EU26-23 will not silently substitute a nearest-neighbour route. The implementation must produce and freeze an exact optimal Euclidean TSP tour for the 20-node instance, with an independently verified tour cost. A Held-Karp exact solver is permitted as a clean-room replacement for Concorde because it computes the same mathematical TSP optimum; tour orientation and rotation are canonicalized before hashing.

## Preregistered OLD gates

- `V0_SOURCE`: paper identity, data commit, instance blob and license match.
- `V1_PARSER`: exactly one depot and 19 customers; finite coordinates; speed fields authenticated.
- `V2_TSP`: exact optimal TSP cost independently verified; canonical tour hash frozen.
- `V3_OBJECTIVE`: distance, vehicle-time, synchronized-segment and complete makespan micro-oracles pass.
- `V4_REPAIR`: repair always returns a legal FSTSP chromosome and is idempotent.
- `V5_OPERATORS`: all 9 crossover variants, 3 tour mutations and 12 type mutations preserve representation invariants after repair.
- `V6_ADAPTATION`: meme inheritance, innovation branch/equality boundaries and domain closure pass fixed-tape tests.
- `V7_DETERMINISM`: a seed gives identical scientific rows for serial and 1/2/4 evaluation workers.
- `V8_OLD_NUMERIC`: the frozen 30-seed primary campaign completes without skipped rows.
- `V9_PORTABILITY`: accepted OLD scientific rows are reproduced on the declared Linux/macOS/Windows and Python matrix, allowing wall-clock differences but no objective/decision divergence.

## Preregistered OLD acceptance rule

For the 30 prespecified primary seeds `1..30`:

```text
reported mean = 448.68
absolute relative mean error <= 5%
and
448.68 lies inside a 95% BCa bootstrap interval for the reproduced mean
```

This is an aggregate paper-profile reproduction, not an author-seed or byte-for-byte trajectory replay. No parameter, seed, stopping rule, operator domain, initialization rule or tolerance may be changed after viewing the 30-seed outcome.

If the primary OLD gate fails, only source-grounded diagnostics frozen before the primary run may be executed. A diagnostic result cannot be promoted to PASS. On failure, the EU26-23 candidate files are removed and the search proceeds to EU26-24.

## HYBRID gate and planned formula

Executable HYBRID code is forbidden until `V8_OLD_NUMERIC=PASS` and `V9_PORTABILITY=PASS`.

After OLD passes, the instance, exact TSP tour, representation, repair, objective, seed ledger, initial population and evaluation budget remain frozen. The OLD eight-option control layer is replaced by the independently verified PR #8 reset self-adjusting `(1+(lambda,lambda))` control:

```text
p = lambda / n
c = 1 / lambda
```

with success-based lambda shrink/growth/reset semantics. The experiment will compare final makespan, logical objective evaluations to matched quality targets, completed iterations, success rate, reset activity and wall-clock time as a secondary machine-dependent measure.

## Scientific novelty boundary

The intended claim is conditional and testable:

> On a fixed applied FSTSP instance and objective, replacing the OLD co-evolved operator/probability memeplex with reset self-adjusting lambda control may improve search efficiency by reaching matched makespan targets in fewer logical evaluations or iterations without materially degrading final delivery makespan.

EU26-23 may not claim universal superiority, author-source equivalence, wall-clock speedup before multi-machine evidence, or reset-only causality without an ablation.
