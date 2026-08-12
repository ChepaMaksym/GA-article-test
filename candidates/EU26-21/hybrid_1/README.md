# Hybrid 1 - CHC-QX Census objective with reset self-adjusting lambda control

## What is hybridized

`Hybrid 1` is the deliberately simple first hybrid requested for EU26-21.
It combines:

1. the applied Census-Income feature-selection protocol reproduced in `old/`;
2. Algorithm 3 reset parameter control from **Theoretical and Empirical
   Analysis of Parameter Control Mechanisms in the `(1+(lambda,lambda))`
   Genetic Algorithm**.

Only the feature-mask search layer changes. Data encoding, the author-source
60/20/20 split, train-only normalization, active sample, Decision Tree, and
held-out test remain frozen.

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

## Files

- `core.py` - independent generic reset `(1+(lambda,lambda))` implementation;
- `benchmarks.py` - exact Jump and OneMax controls;
- `census.py` - validation-only Census objective and source-protocol bridge;
- `run_jump_campaign.py` - preregistered reset-vs-no-reset Jump experiment;
- `run_census_hybrid.py` - one applied Hybrid 1 run;
- `run_census_worker_matrix.py` - exact 1/2/4-worker invariance check;
- `HYPOTHESES.md` - hypotheses, acceptance gates, and claim boundaries.

Tests live in `../tests/test_hybrid_1_*.py`.

## Verification levels

- `V1_CORE` - formulas and boundaries;
- `V2_FIXED_TAPE` - mutation, crossover, final pool, acceptance, reset;
- `V3_WORKERS` - exact invariance for 1/2/4 evaluation and campaign workers;
- `V4_JUMP` - preregistered meaningful local-optimum improvement;
- `V5_ONEMAX` - no-regression control;
- `V6_CENSUS_SMOKE` - data boundary, nonempty subset, budget, held-out test;
- `V7_CENSUS_CAMPAIGN` - paired applied hypotheses H1-H3.

Passing Jump is evidence that the transferred mechanism works. It is not by
itself evidence that Census performance improved. That claim requires V7.

## Reproduction examples

```bash
python candidates/EU26-21/hybrid_1/run_jump_campaign.py \
  --n 20 --k 3 --budget 10000 --seed-start 101 --runs 50 \
  --campaign-workers 4 --enforce
```

```bash
python candidates/EU26-21/hybrid_1/run_census_hybrid.py \
  /path/to/pinned/Fast-Genetic-Algorithm-For-Feature-Selection \
  --seed 1 --budget 800 --workers 4 --output-json result.json
```

## Current claim boundary

Implementation and mechanism-control tests may pass before the full applied
campaign. Until V7 is complete, the allowed statement is:

```text
Hybrid 1 is implemented and its reset controller is verified on critical and
Jump controls; applied Census improvement remains under test.
```
