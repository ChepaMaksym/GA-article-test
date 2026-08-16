# Hybrid 1 - CHC-QX Census objective with reset self-adjusting lambda control

Status: `PASS_EXTENDED_30_SEED_H1_H2_H3`.

## What is hybridized

`Hybrid 1` combines:

1. the applied Census-Income feature-selection protocol reproduced in `old/`;
2. Algorithm 3 reset parameter control from **Theoretical and Empirical
   Analysis of Parameter Control Mechanisms in the `(1+(lambda,lambda))`
   Genetic Algorithm**.

Only the feature-mask search layer changes. Data encoding, the author-source
60/20/20 split, train-only normalization, active sample, Decision Tree,
validation-only optimization, and held-out test remain frozen.

## Algorithm

For a 41-bit feature mask and real parameter `lambda`:

1. `m = round_half_up(lambda)`;
2. `p = lambda / 41`;
3. sample one `L ~ Bin(41, p)`;
4. create `m` mutants, each by flipping exactly `L` distinct bits;
5. select the best mutant;
6. create `m` biased-uniform crossover children with `c = 1/lambda`;
7. select from the best mutant plus crossover children, excluding exact parent
   copies;
8. accept a candidate if its lexicographic fitness is not worse;
9. on strict improvement set `lambda = max(1, lambda/F)`;
10. on failure at `lambda=41`, reset to `1`; otherwise grow by `F^(1/4)`.

Fitness is:

```text
(validation accuracy, - selected_feature_count / 41)
```

Accuracy therefore dominates. Sparsity can only decide an accuracy tie.

## Final 30-seed applied result

The paired experiment used seeds `1..30`, one fixed 14,964-instance active
sample size, identical 50-mask initial populations per seed, a budget of 400
for H1, and a budget/censoring horizon of 2,500 for H3.

- H1 confidence-bound non-inferiority: **PASS**;
- H2 smaller/equal feature subsets: **PASS**;
- H3 at least 20% fewer logical NFE: **PASS confidence-bound**.

Primary numbers:

```text
OLD median test accuracy: 94.9367%
Hybrid median test accuracy: 94.9016%
paired median difference: -0.0263 percentage point
95% BCa interval: -0.0677 to -0.0013 percentage point
non-inferiority margin: -0.10 percentage point

OLD median selected features: 5.5
Hybrid median selected features: 5.0
paired median difference: -1 feature

validation target: 0.946
OLD median capped NFE: 319.0
Hybrid median capped NFE: 141.5
paired median NFE reduction: 55.50%
95% BCa interval: 34.91% to 64.97%
```

The correct claim is **efficiency plus non-inferiority**, not accuracy
superiority. Full provenance, tables, confidence intervals, and the aggregation
correction are in `EXTENDED_30_SEED_RESULTS.md`.

## Files

- `core.py` - independent generic reset `(1+(lambda,lambda))` implementation;
- `benchmarks.py` - exact Jump and OneMax controls;
- `census.py` - validation-only Census objective and source-protocol bridge;
- `paired_comparison_v2.py` - exact paired OLD/Hybrid data and NFE protocol;
- `run_old_hybrid_seed_v2.py` - isolated paired seed runner;
- `aggregate_old_hybrid_v2_corrected.py` - immutable 30-row BCa aggregation;
- `run_jump_campaign.py` - reset-vs-no-reset Jump experiment;
- `run_census_hybrid.py` - one applied Hybrid 1 run;
- `run_census_worker_matrix.py` - exact 1/2/4-worker invariance check;
- `HYPOTHESES.md` - frozen hypotheses and gates;
- `AMENDMENT_30_SEED_V2.md` - pre-outcome first-hit and confidence amendment;
- `EXECUTION_MATRIX_30_SEED.md` - seed-parallel execution amendment;
- `RESULTS.md` - consolidated evidence;
- `EXTENDED_30_SEED_RESULTS.md` - final H1-H3 report.

Tests live in `../tests/test_hybrid_1_*.py`.

## Verification levels

- `V1_CORE` - formulas and boundaries: PASS;
- `V2_FIXED_TAPE` - mutation, crossover, final pool, acceptance, reset: PASS;
- `V3_WORKERS` - exact invariance for 1/2/4 evaluation and campaign workers: PASS;
- `V4_JUMP` - meaningful local-optimum improvement: PASS;
- `V5_ONEMAX` - no-regression control: PASS;
- `V6_CENSUS_SMOKE` - data boundary, subset, budget, held-out test: PASS;
- `V7_CENSUS_CAMPAIGN` - paired applied H1-H3: PASS.

## Reproduction examples

```bash
python candidates/EU26-21/hybrid_1/run_jump_campaign.py \
  --n 20 --k 3 --budget 10000 --seed-start 101 --runs 50 \
  --campaign-workers 4 --enforce
```

The final paired seed execution is defined by:

```text
.github/workflows/eu26-21-old-hybrid-30-matrix.yml
```

The immutable 30 seed artifacts were aggregated by:

```text
.github/workflows/eu26-21-old-hybrid-aggregate-only.yml
```

## Current claim boundary

Supported statement:

```text
Under the frozen 30-seed paired Census-Income protocol, Hybrid 1 is
confidence-bound non-inferior to reproduced OLD CHC-QX within a 0.10
percentage-point accuracy margin, selects one fewer feature by paired median,
and reaches validation target 0.946 with 55.5% fewer logical objective
evaluations by paired median; the 95% BCa lower bound for the NFE reduction is
34.9%.
```

Not supported:

```text
Hybrid 1 is more accurate than OLD, or reset alone caused the full Census NFE
improvement.
```
