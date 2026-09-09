# Hybrid 1 - CHC-QX Census objective with reset self-adjusting lambda control

Source-compatible status:

```text
H1 quality non-inferiority: PASS_CONFIDENCE_BOUND
H2 composite search efficiency: SUPPORTED_SOURCE_COMPATIBLE_ONLY
H3 logical-NFE efficiency: PASS_CONFIDENCE_BOUND
```

The source-compatible conclusion is not transferred to the corrected
official-UCI profile, where C-H1 is `FAIL_NONINFERIORITY`.

## What is hybridized

`Hybrid 1` combines:

1. the applied Census-Income feature-selection protocol reproduced in `old/`;
2. Algorithm 3 reset parameter control from **Theoretical and Empirical
   Analysis of Parameter Control Mechanisms in the `(1+(lambda,lambda))`
   Genetic Algorithm**.

Only the feature-mask search layer changes. Data encoding, the author-source
60/20/20 split, train-only normalization, active sample, Decision Tree,
validation-only optimization, and held-out test remain frozen in this profile.

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

## Thesis-level H2 - source-compatible search efficiency

The academically precise H2 is:

> **Under the frozen source-compatible protocol, Hybrid 1 has higher search
> efficiency than OLD CHC-QX if it preserves predictive quality within the
> predeclared non-inferiority margin, does not increase the typical selected-
> feature count, and reaches the matched validation target with fewer logical
> fitness evaluations.**

Formally:

```text
H2 = quality preservation AND subset compactness AND logical-NFE economy
```

The paired experiment used seeds `1..30`, one fixed 14,964-instance active
sample size, identical 50-mask initial populations per seed, a budget of 400
for quality/subset analysis, and a budget/censoring horizon of 2,500 for exact
first-hit NFE.

### H2a - quality preservation

```text
OLD median test accuracy: 94.9367%
Hybrid median test accuracy: 94.9016%
paired median Hybrid - OLD: -0.0263125 percentage point
95% BCa: [-0.0676607, -0.0012530] percentage point
non-inferiority margin: -0.10 percentage point
baseline gains: 30/30
result: PASS_CONFIDENCE_BOUND
```

This is non-inferiority, not accuracy superiority.

### H2b - subset compactness

```text
OLD median selected features: 5.5
Hybrid median selected features: 5.0
paired median Hybrid - OLD: -1 feature
fewer / equal / more pairs: 16 / 7 / 7
result: PASS
```

### H2c - logical-NFE economy at validation target 0.946

```text
OLD reached: 29/30
Hybrid reached: 30/30
OLD median capped NFE: 319.0
Hybrid median capped NFE: 141.5
paired median NFE reduction: 55.4990%
95% BCa: [34.9110%, 64.9701%]
Hybrid faster: 26/30 pairs
result: PASS_CONFIDENCE_BOUND
```

All three components passed. Therefore:

```text
H2 = SUPPORTED_SOURCE_COMPATIBLE_ONLY
```

The formal definition, claim boundary, and machine-readable evidence are in:

- `H2_SOURCE_COMPATIBLE_EFFICIENCY.md`;
- `h2_source_compatible_evidence.csv`.

## Files

- `core.py` - independent generic reset `(1+(lambda,lambda))` implementation;
- `benchmarks.py` - exact Jump and OneMax controls;
- `census.py` - validation-only Census objective and source-protocol bridge;
- `paired_comparison_v2.py` - exact paired OLD/Hybrid data and NFE protocol;
- `run_old_hybrid_seed_v2.py` - isolated paired seed runner;
- `aggregate_old_hybrid_v2.py` - canonical strict 30-row aggregation;
- `run_jump_campaign.py` - reset-vs-no-reset Jump experiment;
- `run_census_hybrid.py` - one applied Hybrid 1 run;
- `run_census_worker_matrix.py` - exact 1/2/4-worker invariance check;
- `HYPOTHESES.md` - frozen experiment-level gates;
- `H2_SOURCE_COMPATIBLE_EFFICIENCY.md` - thesis-level H2 synthesis;
- `h2_source_compatible_evidence.csv` - H2 evidence table;
- `AMENDMENT_30_SEED_V2.md` - pre-outcome first-hit and confidence amendment;
- `EXECUTION_MATRIX_30_SEED.md` - seed-parallel execution amendment;
- `RESULTS.md` - consolidated evidence;
- `EXTENDED_30_SEED_RESULTS.md` - final source-compatible report.

Tests live in `../tests/test_hybrid_1_*.py`.

## Verification levels

- `V1_CORE` - formulas and boundaries: PASS;
- `V2_FIXED_TAPE` - mutation, crossover, final pool, acceptance, reset: PASS;
- `V3_WORKERS` - exact invariance for 1/2/4 evaluation and campaign workers: PASS;
- `V4_JUMP` - meaningful local-optimum improvement: PASS;
- `V5_ONEMAX` - no-regression control: PASS;
- `V6_CENSUS_SMOKE` - data boundary, subset, budget, held-out test: PASS;
- `V7_CENSUS_CAMPAIGN` - paired source-compatible experiment: PASS.

## Provenance

```text
immutable paired seed run: 31934321927
corrected aggregation run: 31934816828
final artifact id: 9260332711
artifact sha256:
8efc217b690f1c3e6698cb9aa0f55207d93f10e6390087c6e9f425d935bea21a
```

The canonical source-compatible matrix is defined by:

```text
.github/workflows/eu26-21-old-hybrid-30-matrix.yml
```

## Current claim boundary

Supported:

> Under the frozen source-compatible 30-seed protocol, Hybrid 1 satisfies the
> joint H2 search-efficiency criterion: quality is preserved within the 0.10
> percentage-point non-inferiority margin, the paired median subset contains
> one fewer feature, and validation target 0.946 is reached with a 55.5% paired
> median reduction in logical NFE; the lower 95% BCa bound is 34.9%.

Not supported:

- Hybrid 1 is more accurate than OLD;
- the H2 conclusion applies to the corrected official-UCI profile;
- reset alone caused the complete Census NFE difference;
- logical NFE is equivalent to wall-clock speedup;
- the result generalizes to other datasets or classifiers.
