# EU26-21 - CHC-QX Census-Income plus Hybrid 1

## Current status

```text
OLD public-source reproduction: PASS_SOURCE_NUMERIC_ALIGNMENT
Hybrid 1 core and mechanism verification: PASS
Extended paired Census H1-H2-H3: PASS_EXTENDED_30_SEED_H1_H2_H3
PR state: open draft, mergeable
```

The literal printed-paper/public-source reconciliation remains documented as
incomplete and is not silently treated as solved. The applied OLD reference is
the verified public-source CHC-QX profile.

Paper used for the applied OLD baseline:

Mohammed Ghaith Altarabichi, Sławomir Nowaczyk, Sepideh Pashami, and Peyman
Sheikholharam Mashhadi, **Fast Genetic Algorithm for feature selection - A
qualitative approximation approach**, Expert Systems with Applications 211
(2023) 118528, DOI `10.1016/j.eswa.2022.118528`.

Parameter-control paper used for Hybrid 1:

Mario Alejandro Hevia Fajardo and Dirk Sudholt, **Theoretical and Empirical
Analysis of Parameter Control Mechanisms in the `(1+(lambda,lambda))` Genetic
Algorithm**, ACM Transactions on Evolutionary Learning and Optimization 2(4),
DOI `10.1145/3564755`.

## Applied problem

- Census-Income income classification;
- 199,523 observations;
- 41 task features;
- binary search space of `2^41` feature masks;
- Decision Tree evaluation under the frozen public-source 60/20/20 protocol.

## OLD evidence

Pinned repository:

```text
Ghaith81/Fast-Genetic-Algorithm-For-Feature-Selection
commit 6ac5a7ec77f8a7c096ab4d019254fcc897988fd6
```

The ten-seed source campaign reproduced:

- all-feature baseline `92.8681%`;
- CHC-QX median test accuracy `94.9455%`;
- sample standard deviation `0.0336` percentage point;
- 10/10 completed runs plus exact seed-1 repeat.

Detailed OLD evidence:

- `old/SOURCE_STATUS.md`;
- `old/PAPER_SOURCE_DIVERGENCES.md`.

## Hybrid 1 intervention

Hybrid 1 preserves data, split, train-only normalization, active sample,
classifier, validation objective, and held-out test. It replaces only binary
feature-mask search with reset self-adjusting `(1+(lambda,lambda))`:

```text
m = round_half_up(lambda)
p = lambda/41
c = 1/lambda
strict success -> shrink
failure -> grow by F^(1/4)
failure at lambda=41 -> reset to 1
```

Fitness is lexicographic:

```text
(validation accuracy, -selected_feature_fraction)
```

Accuracy always dominates sparsity.

## Mechanism controls

Jump confirmation:

- reset `27/50` vs no reset `8/50` successes;
- success probability `54%` vs `16%`;
- `+38` percentage points;
- `3.375x` successes;
- solved-run median NFE `32.1%` lower.

OneMax and exact 1/2/4-worker scientific-signature tests passed.

## Final 30-seed applied experiment

Frozen paired protocol:

- seeds `1..30`;
- fixed active size 14,964;
- identical 50 initial masks for OLD and Hybrid within each seed;
- H1 budget 400;
- H3 budget/censoring horizon 2,500;
- validation targets 0.945, 0.946, and 0.947;
- primary target 0.946;
- exact logical-NFE instrumentation;
- 50,000 deterministic BCa resamples;
- lower endpoint of a two-sided 95% BCa interval as the confidence gate.

### H1

```text
OLD median test accuracy: 94.9367%
Hybrid median test accuracy: 94.9016%
paired median difference: -0.0263 percentage point
95% BCa interval: -0.0677 to -0.0013 percentage point
non-inferiority margin: -0.10 percentage point
```

Result: `PASS_CONFIDENCE_BOUND`.

This supports non-inferiority, not accuracy superiority.

### H2

```text
OLD median features: 5.5
Hybrid median features: 5.0
paired median difference: -1 feature
```

Result: `PASS`.

### H3

At primary validation target 0.946:

```text
OLD reached: 29/30
Hybrid reached: 30/30
OLD median capped NFE: 319.0
Hybrid median capped NFE: 141.5
paired median relative reduction: 55.50%
95% BCa interval: 34.91% to 64.97%
```

Result: `PASS_CONFIDENCE_BOUND` against the preregistered 20% requirement.

All three sensitivity targets also pass confidence-bound.

## Final provenance

```text
immutable 30-seed run: 31934321927
corrected aggregation run: 31934816828
aggregation job: 95134969064
final artifact: 9260332711
artifact sha256: 8efc217b690f1c3e6698cb9aa0f55207d93f10e6390087c6e9f425d935bea21a
```

The aggregation correction accepted valid first-hit NFE inside the common
initial population. No seed row was regenerated.

## Final claim boundary

Supported:

```text
Hybrid 1 is confidence-bound non-inferior to reproduced public-source OLD
CHC-QX within a 0.10 percentage-point accuracy margin, selects one fewer
feature by paired median, and reaches validation target 0.946 with 55.5% fewer
logical objective evaluations by paired median; the lower 95% BCa bound for the
NFE reduction is 34.9%.
```

Not supported:

```text
Hybrid 1 is more accurate than OLD, the public code is identical to the printed
paper, or reset alone caused the whole Census NFE improvement.
```

Full reports:

- `hybrid_1/RESULTS.md`;
- `hybrid_1/EXTENDED_30_SEED_RESULTS.md`;
- `hybrid_1/AMENDMENT_30_SEED_V2.md`.
