# Hybrid 1 consolidated verification results

## Final decision

Status: `PASS_EXTENDED_30_SEED_H1_H2_H3`.

Hybrid 1 is implemented, mechanism-tested, multicore-verified, and evaluated on
the applied Census-Income feature-selection task against reproduced OLD
CHC-QX. The final extended paired experiment closes the formerly pending H3 and
strengthens H1 from a point-estimate result to a confidence-bound result.

The correct overall conclusion is:

```text
Hybrid 1 is confidence-bound non-inferior in Census test accuracy within the
predeclared 0.10 percentage-point margin, selects fewer features by paired
median, and reaches matched validation targets with substantially fewer
logical objective evaluations.
```

It is not correct to claim accuracy superiority or to attribute the complete
OLD-versus-Hybrid efficiency difference solely to reset.

## Reproduced OLD reference

The pinned public CHC-QX source at commit
`6ac5a7ec77f8a7c096ab4d019254fcc897988fd6` previously passed its ten-seed
numerical reproduction:

```text
all-feature baseline test accuracy: 92.8681%
CHC-QX median test accuracy: 94.9455%
sample SD: 0.0336 percentage point
completed: 10/10 plus exact seed-1 repeat
```

The printed-paper/source divergences remain documented in
`../old/PAPER_SOURCE_DIVERGENCES.md`. The applied OLD reference is the verified
public-source profile, not an unsupported claim of literal Algorithm 1
identity.

## Implemented Hybrid 1

Only the binary feature-mask search layer changes. Census encoding, the public
60/20/20 split, train-only normalization, active training sample, Decision
Tree, validation objective, and final held-out test stay fixed.

For dimension `n=41`:

```text
m = round_half_up(lambda)
p = lambda / n
L ~ Binomial(n,p), shared by all mutants in one generation
c = 1/lambda
strict success -> max(1, lambda/F)
failure -> min(n, lambda * F^(1/4))
failure at lambda=n -> reset lambda to 1
```

Fitness is lexicographic:

```text
(validation accuracy, -selected_feature_fraction)
```

Accuracy dominates sparsity.

## Core and mechanism verification

All formula, mutation, crossover, final-pool, parameter-transition, data-boundary,
and budget tests passed. The test suite verifies:

- nearest-half-up offspring rounding;
- `p=lambda/n` and `c=1/lambda`;
- one shared binomial mutation strength per generation;
- exact-bit mutation without replacement;
- selected-best-mutant plus crossover final pool;
- exclusion of exact parent copies;
- neutral acceptance but strict-success parameter control;
- success shrink, failure growth, and cap reset;
- `1 <= lambda <= n`;
- no logical NFE overshoot;
- empty-mask penalty;
- validation-only search and one held-out test evaluation.

Evaluation workers `1`, `2`, and `4`, as well as campaign workers `1`, `2`, and
`4`, preserve complete scientific signatures: masks, fitness, logical NFE,
lambda trajectory, mutation strengths, acceptance sequence, strict-success
sequence, and reset count.

## Jump local-optimum control

Frozen `Jump_3`, `n=20`, exact local-optimum start, seeds `101..150`, and common
budget 10,000:

| Metric | Reset | No reset | Effect |
|---|---:|---:|---:|
| Successes | 27/50 | 8/50 | +19 |
| Success rate | 54% | 16% | +38 pp |
| Relative successes | - | - | 3.375x |
| Solved-run median NFE | 3,389 | 4,991 | 32.1% lower |
| Reset events | 783 | 0 | activated |

This is the strongest causal evidence for the reset transition because the two
Jump variants differ only at failure on maximum lambda.

## OneMax no-regression control

For `n=64`, seeds `1..20`, and budget 5,000, reset and no-reset variants solved
all runs with identical solutions and evaluation counts. The reset branch is
dormant when unnecessary.

## Original applied campaigns

The first practical Census campaign used ten seeds and budget 400. It passed
the preregistered point gates but its bootstrap lower bound narrowly crossed
the non-inferiority margin. A paired budget-2,500 reset/no-reset ablation then
showed that reset improved test accuracy in 2/10 runs, was identical in 8/10,
and was worse in 0/10. Thus the reset-specific Census effect was positive but
not robust by paired median.

Those results remain valid historical evidence. They motivated, but were not
silently mixed into, the final 30-seed controlled OLD-versus-Hybrid experiment.

## Extended 30-seed paired protocol

The final experiment froze before execution:

- seeds `1..30`;
- exactly 14,964 active training instances per seed;
- per-seed active-index SHA-256;
- identical 50-mask initial populations for OLD and Hybrid per seed;
- per-seed initial-mask SHA-256;
- H1 budget 400, four Hybrid evaluation workers;
- H3 budget/censoring horizon 2,500, one Hybrid worker for exact call order;
- validation targets `0.945`, `0.946`, and `0.947`;
- primary target `0.946`;
- 50,000 deterministic BCa bootstrap resamples;
- lower endpoint of a two-sided 95% BCa interval as the confidence gate.

All 30 isolated seed jobs completed. All provenance and accounting gates passed.

Immutable seed execution:

```text
run id: 31934321927
head: 6a9e9faba1fe4e7691fbb88cec1e5d2e84232a04
```

Corrected analysis-only aggregation:

```text
run id: 31934816828
job id: 95134969064
head: 62b267f850b9bdd09934ca27507c272c35cb34e3
result: success
```

Final artifact:

```text
name: eu26-21-old-vs-hybrid-1-thirty-seed-v2-corrected
id: 9260332711
sha256: 8efc217b690f1c3e6698cb9aa0f55207d93f10e6390087c6e9f425d935bea21a
```

The aggregation correction accepted positive first-hit NFE within the common
initial population. No optimizer row was regenerated.

## H1 - strengthened confidence-bound non-inferiority

Margin:

```text
Hybrid - OLD >= -0.10 percentage point
```

| Metric | OLD CHC-QX | Hybrid 1 |
|---|---:|---:|
| Mean test accuracy | 94.9153% | 94.9006% |
| Median test accuracy | 94.9367% | 94.9016% |
| Runs improving all-feature baseline by >=1.50 pp | - | 30/30 |

Paired result:

```text
median Hybrid-minus-OLD: -0.0263125 percentage point
95% BCa interval: [-0.0676607, -0.0012530] percentage point
margin: -0.10 percentage point
```

The entire interval lies above the non-inferiority margin:

```text
H1 = PASS_CONFIDENCE_BOUND
```

The interval lies below zero, so the data support non-inferiority, not Hybrid
accuracy superiority.

## H2 - selected-feature count

```text
OLD median: 5.5 features
Hybrid median: 5.0 features
paired median Hybrid-minus-OLD: -1 feature
fewer/equal/more pairs: 16 / 7 / 7
```

```text
H2 = PASS
```

## H3 - exact logical-NFE efficiency

Every wrapper objective call is counted. OLD NFE contains active-sample CHC
calls plus earlier outer full-validation reevaluations. Hybrid NFE contains
initial masks plus mutation and crossover evaluations. Shared preparation and
the one final held-out test evaluation are excluded from both search counts.

Primary target `0.946`:

| Metric | OLD CHC-QX | Hybrid 1 |
|---|---:|---:|
| Reached target | 29/30 | 30/30 |
| Median capped NFE | 319.0 | 141.5 |
| Mean capped NFE | 391.97 | 228.00 |

```text
paired median relative reduction: 55.4990%
95% BCa interval: [34.9110%, 64.9701%]
restricted-mean reduction with censoring: 41.8318%
Hybrid faster/equal/slower: 26 / 0 / 4 pairs
```

The lower confidence bound exceeds the frozen 20% requirement:

```text
H3 = PASS_CONFIDENCE_BOUND
```

Sensitivity targets:

| Target | OLD reached | Hybrid reached | OLD median NFE | Hybrid median NFE | Median reduction | 95% BCa interval | Decision |
|---:|---:|---:|---:|---:|---:|---:|---|
| 0.945 | 29/30 | 30/30 | 278.0 | 109.5 | 56.3680% | 44.2155%-64.5112% | PASS confidence-bound |
| 0.946 | 29/30 | 30/30 | 319.0 | 141.5 | 55.4990% | 34.9110%-64.9701% | PASS confidence-bound |
| 0.947 | 28/30 | 30/30 | 475.0 | 211.5 | 55.4696% | 48.1734%-68.7529% | PASS confidence-bound |

At budget 2,500 reset activated in all 30 Hybrid runs, with 54 total reset
events. This confirms participation of the controller but does not isolate reset
as the sole cause of the whole-search efficiency difference.

## Final hypothesis decisions

| Hypothesis | Decision |
|---|---|
| H1 applied accuracy non-inferiority | `PASS_CONFIDENCE_BOUND` |
| H2 smaller/equal feature subsets | `PASS` |
| H3 at least 20% fewer logical NFE | `PASS_CONFIDENCE_BOUND` |
| H4 Jump local-optimum gain | `PASS` |
| H5 worker invariance | `PASS` |
| H6 OneMax no regression | `PASS` |
| H7 semantic correctness | `PASS` |

Full 30-seed tables, confidence intervals, provenance, and claim boundaries are
in `EXTENDED_30_SEED_RESULTS.md`.

## Supported master-thesis conclusion

Under the controlled paired Census-Income protocol, Hybrid 1 preserves
predictive accuracy within a 0.10 percentage-point confidence-bound
non-inferiority margin, reduces the selected subset by one feature at the
paired median, and reaches validation target 0.946 with 55.5% fewer logical
objective evaluations at the paired median. The lower 95% BCa bound for the NFE
reduction is 34.9%, above the preregistered 20% threshold.
