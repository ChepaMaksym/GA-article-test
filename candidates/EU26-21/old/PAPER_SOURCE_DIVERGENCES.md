# EU26-21 paper/source divergence register

This register is frozen after the pinned author-source campaign passed and before the clean-room implementation is evaluated. It prevents the public Python implementation from being silently presented as a literal implementation of the printed paper.

## Claim boundary

The following claims are currently allowed:

- `PASS_NOTEBOOK_ARTIFACT_AUTHENTICATION`;
- `PASS_SOURCE_NUMERIC_ALIGNMENT` for the pinned public Python implementation under the auditor seed ledger;
- fixed-tape confirmation that the source contains Hamming-threshold adaptation and cataclysmic mutation.

The following claims are forbidden until separately demonstrated:

- `PASS_LITERAL_PAPER_PROFILE`;
- `PASS_OLD_FULL`;
- historical seed reproduction;
- equivalence between the public source, printed Algorithm 1, and the Table 2 experimental endpoint;
- any executable PR #8 hybrid.

## D1 - active-sampling algorithm

### Printed paper

Algorithm 1 describes an adaptive-sampling genetic algorithm whose chromosome is an instance-selection mask of length equal to the training-set size. Its objective combines:

- disagreement between the ranking of candidate feature-selection solutions on full and sampled training data, measured by Spearman rank correlation;
- a sample-size term proportional to the selected fraction of training instances.

The active-sampling GA itself has population, generation, tournament, crossover, mutation, and stopping inputs.

### Public source

`Evolution.CHCqx` does not call the source's instance-selection CHC. Instead, `select_instances`:

1. creates `q` random feature masks;
2. evaluates those masks on all training instances;
3. tests deterministic sample sizes `n/2`, `n/4`, `n/8`, ... while the size exceeds 5,000;
4. draws a fresh random training subset at each size;
5. computes `(1 - Spearman correlation) + approximation_time / original_fitness_time`;
6. retains the last strictly improving sample size.

This is progressive sample halving, not the printed instance-mask GA.

**Impact:** the source campaign can reproduce the source endpoint but cannot by itself authenticate Algorithm 1.

## D2 - number of controlled solutions `q`

- Printed experimental configuration: `q = 20` controlled individuals.
- Executed notebook and source endpoint: `q = 10`.

**Impact:** Spearman correlation, active-sample choice, evaluation cost, and variance all depend on `q`.

## D3 - active-sampling objective

- Printed equation: `(1 - rho) + |s|/n`.
- Public source: `(1 - rho) + approximation_time/original_fitness_time`.

The source contains a commented sample-fraction expression, but executes the timing ratio.

**Impact:** the selected sample size is hardware- and runtime-dependent in the public source, while the printed equation is deterministic given a sample.

## D4 - data order

- Paper methodology states that data are shuffled before the 60/20/20 split.
- Executed notebook calls `divide_dataset(..., shuffle=False)`.
- Source only shuffles when the argument is true, using `random_state=10`.

**Impact:** class composition and instance order in train, validation, and test differ between the printed description and notebook endpoint.

## D5 - CHC convergence semantics

- Printed paper describes convergence as ten consecutive generations without improvement.
- Executed notebook uses `f=10` generations per CHC chunk and `f_no_change=2` at the outer CHC-QX level.
- The inner source CHC uses its own `noChange` state and adaptive distance `d`, while the outer wrapper performs full-data reevaluation after each chunk.

**Impact:** printed generations and source chunks are not one-to-one equivalent. Notebook output `Gen = 60` means six ten-generation chunks, not necessarily the printed stopping rule.

## D6 - cataclysmic mutation rate

- Printed paper: 35% divergence/restart mutation.
- Public source: DEAP `mutFlipBit` with independent bit probability `1/3`.

**Impact:** restart distribution differs slightly and must be tracked separately.

## D7 - initial feature-mask distribution

- Printed CHC description uses a per-bit Bernoulli threshold near 0.5.
- Public source draws one `zero_p ~ Uniform(0,1)` per individual and then generates all bits using probabilities `[zero_p, 1-zero_p]`.

**Impact:** the source population is a mixture ranging from very sparse to very dense masks, rather than independent Bernoulli(0.5) masks.

## D8 - HUX implementation

- Standard HUX swaps a complementary half of the differing loci between the two parents.
- Public source independently samples half of the differing positions for child 1 and then independently samples another half for child 2.

The two selected position sets can overlap or differ, so source children are not guaranteed to be complementary standard-HUX offspring.

**Impact:** the exact offspring distribution differs from canonical HUX and must be preserved in the source-compatible track but explicitly resolved in the paper profile.

## D9 - adaptive distance and duplicate history

The public source adds every accepted child and every restart mutant to a global `populationHistory` and suppresses offspring previously seen at any earlier generation. This history behavior is not completely specified in the printed pseudocode.

**Impact:** source exploration and the rate at which `d` decreases depend on an implementation detail absent from the paper description.

## D10 - source parameterization not fully reported by the paper

A literal Census run of printed Algorithm 1 requires values or exact historical semantics for at least:

- instance-mask population size;
- active-sampling generations / evaluation budget;
- tournament size;
- crossover and mutation probabilities;
- active-sampling stopping parameters;
- exact HUX interpretation;
- exact random seed ledger;
- whether the timing term or selected-fraction term generated Table 2.

The paper does not authenticate a complete mapping from these printed inputs to the public notebook execution.

## Verification tracks going forward

### Track A - pinned source

The already passing source campaign remains frozen and may not be retuned.

### Track B - independent source-semantics clean room

Implement the behavior actually executed by the public source without importing `Dataset` or `Evolution`. Its purpose is to verify that the passing endpoint is not an artifact of invoking opaque upstream classes.

### Track C - literal printed-paper audit/profile

Implement unit-level printed CHC and Algorithm 1 semantics where adequately specified, and preregister a feasibility/parameter-authentication gate before any full Census campaign.

If Track C cannot be mapped to the historical endpoint without inventing material parameters, the final OLD status must remain blocked even if Tracks A and B pass.

## Hybrid prohibition

No executable file may be added under `hybrid/` until:

- Track B is complete and aligned with Track A within a frozen acceptance rule;
- Track C is either reproduced or the missing mapping is resolved from authenticated evidence;
- the candidate receives an explicit `PASS_OLD_FULL` decision.
