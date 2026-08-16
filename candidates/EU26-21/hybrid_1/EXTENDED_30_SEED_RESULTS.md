# Extended 30-seed OLD CHC-QX versus Hybrid 1 results

## Decision

Status: `PASS_EXTENDED_30_SEED_H1_H2_H3`.

The strengthened paired Census-Income experiment completed all 30 seeds and
closed the two previously open questions:

- H1 confidence-bound non-inferiority: **PASS**;
- H2 feature-subset sparsity: **PASS**;
- H3 exact logical-NFE efficiency: **PASS with a two-sided 95% BCa lower bound**.

This result concerns the complete Hybrid 1 search layer. It does not claim that
the reset transition alone caused every Census improvement. The earlier paired
reset/no-reset ablation remains the causal evidence for reset-specific effects.

## Frozen protocol

- Seeds: `1..30`.
- Census-Income: 199,523 observations, 41 input variables.
- Public-source contiguous 60/20/20 split and train-only normalization.
- Active training sample: exactly 14,964 instances for every seed, matching the
  authenticated executed author-notebook endpoint.
- Active indices are generated in the public progressive-halving random-stream
  order and authenticated by a per-seed SHA-256 digest.
- Common initial population: the same 50 source-density masks for OLD and
  Hybrid 1 within each seed, authenticated by a per-seed SHA-256 digest.
- H1 Hybrid budget: 400 logical objective evaluations, four evaluation workers.
- H3 Hybrid budget/censoring horizon: 2,500 logical objective evaluations, one
  evaluation worker for exact first-hit ordering.
- OLD source parameters: population 50, ten-generation CHC chunks, outer
  no-improvement limit two, source HUX, source distance adaptation, source
  history suppression, and source restart behavior.
- Targets: validation accuracy `0.945`, `0.946`, and `0.947`; primary target
  `0.946`.
- Statistics: paired median and 50,000 deterministic BCa bootstrap resamples.
- Primary confidence decision: lower endpoint of a two-sided 95% BCa interval.

Shared data preparation, active-sample construction, baseline scoring, and the
single final held-out test evaluation are excluded from optimizer NFE. They are
common protocol costs, not search decisions.

## Provenance

Immutable paired seed run:

```text
workflow: EU26-21 OLD vs Hybrid 1 thirty-seed matrix
run id: 31934321927
head commit: 6a9e9faba1fe4e7691fbb88cec1e5d2e84232a04
completed seed jobs: 30/30
```

Corrected analysis-only aggregation:

```text
workflow: EU26-21 aggregate existing thirty-seed OLD vs Hybrid results
run id: 31934816828
head commit: 62b267f850b9bdd09934ca27507c272c35cb34e3
job id: 95134969064
result: success
```

Final artifact:

```text
name: eu26-21-old-vs-hybrid-1-thirty-seed-v2-corrected
id: 9260332711
sha256: 8efc217b690f1c3e6698cb9aa0f55207d93f10e6390087c6e9f425d935bea21a
```

All protocol gates passed:

```text
P0_COMPLETE_30_SEEDS
P1_SEED_LEDGER
P2_FIXED_ACTIVE_SAMPLE
P3_COMMON_INITIAL_MASK_DIGESTS
P4_EXACT_OLD_NFE
P5_EXACT_HYBRID_FIRST_HIT
```

## Analysis correction

The 30 optimizer rows were not regenerated.

The first aggregator incorrectly rejected target hits with NFE in `1..49`.
Such values are valid: they mean one of the common initial-population masks
reached the target before all 50 masks had been evaluated. The corrected guard
accepts every positive first-hit NFE and still rejects zero or negative values.
The corrected aggregator downloaded the original immutable 30 row artifacts
from run `31934321927`, reran only tests and statistics, and recorded:

```text
seed_rows_regenerated: false
correction: allow positive first-hit NFE within initial population
```

A still earlier draft was abandoned before aggregate outcome inspection because
it reconstructed Hybrid target attainment from accepted-parent states while
OLD used evaluated masks. The final v2 protocol uses the same first-evaluated-
mask rule for both algorithms.

## H1 - confidence-bound non-inferiority

Frozen margin:

```text
Hybrid test accuracy - paired OLD test accuracy >= -0.001
```

`-0.001` probability equals `-0.10` percentage point.

| Metric | OLD CHC-QX | Hybrid 1 |
|---|---:|---:|
| Mean held-out test accuracy | 94.9153% | 94.9006% |
| Median held-out test accuracy | 94.9367% | 94.9016% |
| Median selected features | 5.5 | 5.0 |
| Runs beating the all-feature baseline by at least 1.50 pp | - | 30/30 |

Paired Hybrid-minus-OLD test-accuracy result:

```text
paired median difference: -0.0002631249 probability
paired median difference: -0.0263125 percentage point
95% BCa interval: [-0.0006766069, -0.0000125298]
95% BCa interval in percentage points: [-0.0676607, -0.0012530]
non-inferiority margin: -0.10 percentage point
```

The entire two-sided 95% BCa interval is above the predeclared `-0.10 pp`
margin. Therefore:

```text
H1 = PASS_CONFIDENCE_BOUND
```

Important interpretation: the interval is below zero, so Hybrid 1 is not shown
to be more accurate than OLD at budget 400. The supported statement is that its
small accuracy loss is within the predeclared non-inferiority margin.

Across the 30 pairs, Hybrid test accuracy was higher in 9, equal in 1, and lower
in 20. The worst paired difference was `-0.11778 pp`, the best was
`+0.33329 pp`. A few individual outcomes outside the margin do not invalidate
the preregistered population-level paired-median confidence decision.

Reset remained dormant in every budget-400 H1 run. H1 therefore evaluates the
self-adjusting `(1+(lambda,lambda))` search as a whole, not a reset-specific
causal effect.

## H2 - feature-subset sparsity

| Metric | Value |
|---|---:|
| OLD median selected features | 5.5 |
| Hybrid median selected features | 5.0 |
| Paired median Hybrid-minus-OLD | -1 feature |
| Hybrid selected fewer features | 16/30 pairs |
| Equal feature count | 7/30 pairs |
| Hybrid selected more features | 7/30 pairs |

The frozen point gate required a paired median difference at most zero:

```text
H2 = PASS
```

This is a descriptive paired result. No confidence-bound sparsity claim was
preregistered.

## H3 - exact logical-NFE efficiency

Logical NFE is counted at the wrapper objective boundary.

OLD records:

```text
active NFE + prior outer full-validation reevaluations
```

Hybrid records every initial-mask, mutation-child, and crossover-child
objective call. A target is reached by the first **evaluated** mask whose
validation accuracy meets or exceeds it. Missing targets are censored at 2,500
rather than omitted.

### Primary target: 0.946

| Metric | OLD CHC-QX | Hybrid 1 |
|---|---:|---:|
| Target reached | 29/30 | 30/30 |
| Common reached pairs | 29/30 | 29/30 |
| Median capped NFE | 319.0 | 141.5 |
| Mean capped NFE | 391.97 | 228.00 |

Paired relative NFE reduction:

```text
median reduction: 55.4990%
95% BCa interval: [34.9110%, 64.9701%]
restricted-mean reduction with censoring: 41.8318%
Hybrid faster: 26/30 pairs
Hybrid slower: 4/30 pairs
```

The lower 95% BCa endpoint, `34.91%`, is above the preregistered `20%`
requirement. Coverage also exceeds the required 24 common pairs and Hybrid
coverage is not lower than OLD. Therefore:

```text
H3 primary = PASS_CONFIDENCE_BOUND
```

### Sensitivity targets

| Validation target | OLD reached | Hybrid reached | OLD median capped NFE | Hybrid median capped NFE | Paired median reduction | 95% BCa interval | Decision |
|---:|---:|---:|---:|---:|---:|---:|---|
| 0.945 | 29/30 | 30/30 | 278.0 | 109.5 | 56.3680% | 44.2155% to 64.5112% | PASS confidence-bound |
| 0.946 | 29/30 | 30/30 | 319.0 | 141.5 | 55.4990% | 34.9110% to 64.9701% | PASS confidence-bound |
| 0.947 | 28/30 | 30/30 | 475.0 | 211.5 | 55.4696% | 48.1734% to 68.7529% | PASS confidence-bound |

Hybrid 1 passed the 20% confidence-bound efficiency gate at all three targets.

At the H3 budget, reset activated in all 30 Hybrid runs, with 54 reset events in
total. This confirms that the transferred parameter-control branch participated
in the search. It does not isolate reset as the sole cause of the OLD-versus-
Hybrid NFE difference because the compared optimizers differ in their complete
search layers.

## Secondary H3 endpoint quality

At budget 2,500, Hybrid 1 had:

```text
median test accuracy: 94.9254%
median selected features: 4
paired median test-accuracy difference vs OLD: -0.002506 percentage point
paired median selected-feature difference vs OLD: -1 feature
```

This secondary endpoint is consistent with the main conclusion: more search
budget preserves practical accuracy while reducing the selected subset, but H1
remains defined by the frozen budget-400 protocol.

## Final hypothesis table

| Hypothesis | Final decision | Main evidence |
|---|---|---|
| H1 accuracy non-inferiority | `PASS_CONFIDENCE_BOUND` | paired median -0.0263 pp; 95% BCa lower -0.0677 pp > -0.10 pp margin; 30/30 baseline gains |
| H2 smaller/equal subsets | `PASS` | paired median -1 feature; Hybrid median 5 vs OLD 5.5 |
| H3 at least 20% fewer logical NFE | `PASS_CONFIDENCE_BOUND` | primary median reduction 55.50%; 95% BCa lower 34.91%; target coverage 30/30 vs 29/30 |
| H4 Jump local-optimum gain | `PASS` from earlier campaign | +38 pp success probability; 32.1% lower solved-run median NFE |
| H5 worker invariance | `PASS` from earlier tests | complete scientific signatures identical at 1/2/4 workers |
| H6 OneMax no-regression | `PASS` from earlier tests | all 20 paired seeds identical |
| H7 semantic correctness | `PASS` | formula, operator, transition, data-boundary, budget, and NFE tests |

## Supported master-thesis conclusion

Under a controlled 30-seed paired Census-Income protocol, Hybrid 1 is
confidence-bound non-inferior to reproduced OLD CHC-QX within a `0.10`
percentage-point accuracy margin, selects one fewer feature by paired median,
and reaches the primary validation target using `55.5%` fewer logical objective
evaluations by paired median. The lower endpoint of the 95% BCa interval for
NFE reduction is `34.9%`, substantially above the preregistered 20% threshold.

The correct claim is efficiency plus non-inferiority, not accuracy superiority.
