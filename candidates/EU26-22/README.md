# EU26-22 - SAGA-FSTSP OLD-first candidate

## Status

`OLD_IMPLEMENTATION_IN_PROGRESS / HYBRID_BLOCKED_BY_OLD`

This candidate starts a new research cycle after EU26-21. Results from PR #19 are not reused as evidence for this candidate.

## Reference study

Ted Pilcher, *A Self-Adaptive Genetic Algorithm for the Flying Sidekick Travelling Salesman Problem*, arXiv:2310.14713, 2023.

The study is an applied combinatorial optimisation problem for coordinated truck-drone delivery. The solution chromosome has one node entry per problem node and each entry carries both tour position and node type. The paper evaluates instances larger than 15 customer decisions, so the applied decision dimension exceeds the project threshold.

## Why this candidate

- publication year 2023;
- UK author/education provenance is recorded separately and is not used as an algorithmic claim;
- applied logistics problem rather than a synthetic fitness-only study;
- many local optima are expected from the joint ordering/type search space;
- self-adaptation occurs inside the run: an eight-entry memeplex is co-evolved with each candidate and controls crossover, mutation operators and their application probabilities;
- paper provides algorithm pseudocode, objective formulas, repair semantics and initialisation rules;
- benchmark families used by the FSTSP literature are public;
- the implementation can be written as a clean-room Python profile without proprietary solvers for the GA layer.

## Frozen OLD mathematical profile

For node coordinates `(x_i, y_i)`, the distance matrix is

`d_ij = sqrt((x_i - x_j)^2 + (y_i - y_j)^2)`.

The paper fixes drone speed ratio `alpha = 2`, with

`tT_ij = d_ij`

`tD_ij = d_ij / alpha`.

The tour objective is makespan

`t_T = sum_{s in T} t_S(s)`,

where each synchronized truck/drone segment contributes the maximum of the corresponding truck and drone travel times.

The initial-population node-saving score for predecessor `i`, candidate node `j`, successor `k` is

`s_j = max(tT_ij + tT_jk - max(tD_ij + tD_jk, tT_ik), 1)`.

The OLD adaptive state is the paper's eight-option memeplex:

`M = (C, CP, CM, DM, TM, TP, TOM, TOP)`

where operator identities and crossover/type/tour mutation probabilities are inherited from the fitter parent and may mutate during evolution. This candidate treats that co-evolutionary state as part of the algorithm, not as external hyper-parameter tuning.

## OLD-first gate

No executable HYBRID optimizer is allowed until all of the following pass:

1. `V0_SOURCE` - paper identity and frozen formulas;
2. `V1_OBJECTIVE` - distance, truck/drone time and synchronized makespan micro-oracles;
3. `V2_REPAIR` - no consecutive incompatible drone tours and no disconnected truck-only node after repair;
4. `V3_ADAPTIVE_STATE` - memeplex inheritance/mutation preserves valid operator/probability domains;
5. `V4_DETERMINISM` - a seed gives the same canonical trace for 1/2/4 evaluation workers;
6. `V5_PAPER_ENDPOINT` - selected published benchmark endpoint is reproduced under a preregistered acceptance rule;
7. `V6_PORTABILITY` - the accepted OLD profile is repeated across the declared OS/Python matrix.

If V5 cannot be passed without outcome-informed assumptions, EU26-22 is rejected and its candidate files are removed before starting EU26-23.

## Planned HYBRID after OLD PASS

The applied objective, instance, representation, repair rules, seed ledger and evaluation budget remain frozen. Only the search-control layer is changed to the independently verified PR #8 reset self-adjusting `(1+(lambda,lambda))` mechanism:

`p = lambda / n`

`c = 1 / lambda`

with success-based lambda update and reset semantics from PR #8.

The comparison will measure, at minimum:

- final makespan;
- first-hit logical evaluations to matched quality targets;
- iterations/generations;
- wall-clock time as a secondary hardware-dependent metric;
- success rate;
- lambda trajectory/reset activity;
- sensitivity to 1/2/4 workers and different CI machines.

## Scientific novelty boundary

The intended thesis claim is not that the PR #8 formula is universally better. The testable novelty is whether replacing the OLD co-evolved operator-control state with the reset self-adjusting lambda control can preserve or improve delivery quality while reducing the number of objective evaluations/iterations on a fixed applied FSTSP protocol.

Current state: OLD code and tests are being built; HYBRID remains blocked.
