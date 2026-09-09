# EU26-21 - CHC-QX Census-Income and Hybrid 1

## Current status

```text
OLD public-source reproduction: PASS_SOURCE_NUMERIC_ALIGNMENT
Hybrid 1 core and mechanism verification: PASS
Source-compatible paired Census H1-H2-H3: PASS_EXTENDED_30_SEED_H1_H2_H3
Corrected official-UCI protocol: PASS_PROTOCOL_RESULTS_AVAILABLE
Corrected C-H1: FAIL_NONINFERIORITY
Corrected C-H2: BLOCKED_BY_H1
Corrected C-H8 reset ablation: NO_CLEAR_EFFECT
Common-objective bridge: PASS_STRICT_EVIDENCE_VALIDATION_30_PAIRS
Bridge quality: FAIL_NONINFERIORITY
Bridge efficiency and sparsity claims: BLOCKED_BY_QUALITY_NONINFERIORITY
PR state: open draft, not merged
```

EU26-21 retains three explicitly separated completed evidence profiles. They
answer different scientific questions and must not be collapsed into one
result.

The third bridge profile was frozen under
[`common_bridge/PROTOCOL.md`](common_bridge/PROTOCOL.md) before any seed
`41001..41030` outcome. Its 30 pairs now compare harmonized pinned-source CHC
with reset-disabled `(1+(lambda,lambda))` under one evaluator and exactly
400 calls per arm. Quality non-inferiority was not established: paired test-WBA
median difference -0.0001373392, 95% BCa [-0.0020872605, 0.0015180741],
margin -0.001. The positive validation-AUC contrast is descriptive because
the quality gate failed. This is valid negative scientific evidence, not CI failure.

See the [Ukrainian thesis research report](common_bridge/THESIS_REPORT_UK.md),
[verified machine report](common_bridge/evidence/reaggregated-report.json),
[30-pair campaign](https://github.com/ChepaMaksym/GA-article-test/actions/runs/34233477859)
and [immutable reaggregation](https://github.com/ChepaMaksym/GA-article-test/actions/runs/34234286460).
Both historical archives were also separately authenticated and reaggregated
in [run 34233480959](https://github.com/ChepaMaksym/GA-article-test/actions/runs/34233480959).

## Source papers

Applied OLD baseline:

Mohammed Ghaith Altarabichi, Sławomir Nowaczyk, Sepideh Pashami, and Peyman
Sheikholharam Mashhadi, **Fast Genetic Algorithm for feature selection - A
qualitative approximation approach**, Expert Systems with Applications 211
(2023) 118528, DOI `10.1016/j.eswa.2022.118528`.

Parameter-control reference for Hybrid 1:

Mario Alejandro Hevia Fajardo and Dirk Sudholt, **Theoretical and Empirical
Analysis of Parameter Control Mechanisms in the `(1+(lambda,lambda))` Genetic
Algorithm**, ACM Transactions on Evolutionary Learning and Optimization 2(4),
DOI `10.1145/3564755`.

The literal printed-paper/public-source reconciliation remains incomplete and is
not silently treated as solved. The applied historical OLD reference is the
verified pinned public-source CHC-QX profile.

## Profile A - source-compatible reproduction and comparison

This profile preserves the upstream encoded Census data, the historical 41-bit
representation, the source-oriented 60/20/20 split, the accuracy objective, and
the public-source CHC behavior.

Pinned repository:

```text
Ghaith81/Fast-Genetic-Algorithm-For-Feature-Selection
commit 6ac5a7ec77f8a7c096ab4d019254fcc897988fd6
```

Hybrid 1 replaces only the binary feature-mask optimizer with reset
self-adjusting `(1+(lambda,lambda))` search:

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

### Mechanism controls

Jump confirmation:

```text
reset successes: 27/50
no-reset successes: 8/50
difference: +38 percentage points
success ratio: 3.375x
solved-run median NFE with reset: 32.1% lower
```

OneMax controls and exact 1/2/4-worker scientific-signature tests also pass.

### Source-compatible 30-seed H1-H3

Frozen paired protocol:

- seeds `1..30`;
- active size 14,964;
- identical 50 initial masks within each OLD/Hybrid pair;
- H1 budget 400;
- H3 budget/censoring horizon 2,500;
- validation targets 0.945, 0.946, and 0.947;
- primary target 0.946;
- logical-NFE instrumentation;
- 50,000 deterministic paired-median BCa resamples.

H1:

```text
OLD median test accuracy: 94.9367%
Hybrid median test accuracy: 94.9016%
paired median Hybrid - OLD: -0.0263 percentage point
95% BCa: [-0.0677, -0.0013] percentage point
margin: -0.10 percentage point
result: PASS_CONFIDENCE_BOUND
```

This supports historical-profile non-inferiority, not accuracy superiority.

H2:

```text
OLD median features: 5.5
Hybrid median features: 5.0
paired median difference: -1 feature
result: PASS
```

H3 at validation target 0.946:

```text
OLD reached: 29/30
Hybrid reached: 30/30
OLD median capped NFE: 319.0
Hybrid median capped NFE: 141.5
paired median relative reduction: 55.50%
95% BCa: [34.91%, 64.97%]
result: PASS_CONFIDENCE_BOUND
```

Logical NFE means wrapper-objective calls, not wall-clock time. The complete
search layers are compared; reset alone is not claimed as the sole cause.

Immutable source-compatible evidence:

```text
30-seed run: 31934321927
corrected aggregation run: 31934816828
final artifact: 9260332711
artifact SHA-256: 8efc217b690f1c3e6698cb9aa0f55207d93f10e6390087c6e9f425d935bea21a
```

No seed row was regenerated during the aggregation correction.

## Profile B - corrected official-UCI applied validation

This additional profile addresses applied-validity limitations of the historical
source-compatible experiment:

- official raw `census-income.data` is used for model development;
- official raw `census-income.test` is the final held-out set;
- raw instance-weight index 24 is excluded from the predictive mask;
- the search space has 40 predictive bits rather than 41 inputs;
- instance weights are supplied to model fitting and weighted metrics;
- weighted balanced accuracy replaces accuracy as the primary objective;
- 30 stratified train/validation splits vary across paired seeds;
- a reset/no-reset Census ablation is run at equal budget and sequential order.

Protocol fingerprint:

```text
training rows: 199,523
held-out test rows: 99,762
predictive dimension: 40
primary metric: weighted balanced accuracy
C-H1 non-inferiority margin: -0.10 percentage point
bootstrap: paired median BCa, 50,000 resamples
```

Dataset hashes:

```text
train: 3676a81db7d3528f3f8b9f3c699d0f0aa28db45e6e994fa0b8ed38327539ee86
test: 98402b1ab879573d0a7f38a699a40258080e25e33d3401e7bf9c96d3fa0fab8c
```

Immutable secure evidence:

```text
secure matrix run: 32049437836
source artifact: 9297184026
artifact SHA-256: 13d2f691eefb46067d3cdffbad4c22c032c429ce91600a33addbd3f5887bbdeb
seed rows: 30/30
```

### Corrected C-H1

```text
Hybrid H1 - corrected OLD paired median: -0.3580 percentage point
95% BCa: [-0.6932, -0.2159] percentage point
preregistered margin: -0.10 percentage point
result: FAIL_NONINFERIORITY
```

The complete interval is below the margin. The corrected profile therefore does
not support weighted balanced-accuracy non-inferiority.

### Corrected C-H2

```text
paired median Hybrid H1 - corrected OLD feature count: -1 feature
result: BLOCKED_BY_H1
```

The smaller subset is retained descriptively, but the preregistered joint claim
is blocked because C-H1 failed.

### Corrected C-H8 reset ablation

```text
reset - no-reset paired median: 0.0000 percentage point
95% BCa: [0.0000, 0.0096] percentage point
runs with reset events: 30/30
total reset events: 49
result: NO_CLEAR_EFFECT
```

Reset was exercised in every run, but the interval includes zero and provides no
clear positive or negative official-test effect.

## Combined interpretation

Supported:

```text
The implementation is reproducible and shows favorable H1-H3 behavior under the
historical source-compatible profile. Under the corrected official-UCI,
weight-aware, 30-split profile, Hybrid H1 does not meet the preregistered
weighted balanced-accuracy non-inferiority margin. It selects a slightly smaller
paired-median subset, but that conditional claim is blocked by C-H1. Reset is
active but has no clear paired official-test effect in the Census ablation.
```

Not supported:

```text
corrected quality superiority; corrected non-inferiority; a reset-specific
Census improvement; identity between printed Algorithm 1 and public code;
universal generalization; or wall-clock speedup inferred from logical NFE.
```

## Evidence and entry points

Source-compatible profile:

- `old/SOURCE_STATUS.md`;
- `old/PAPER_SOURCE_DIVERGENCES.md`;
- `hybrid_1/RESULTS.md`;
- `hybrid_1/EXTENDED_30_SEED_RESULTS.md`;
- `hybrid_1/TEST_AND_CI_AUDIT.md`.

Corrected applied profile:

- `corrected_applied/README.md`;
- `corrected_applied/METHODOLOGY_AMENDMENT.md`;
- `corrected_applied/RESULTS.md`;
- `corrected_applied/secure_cli.py`;
- `corrected_applied/secure_aggregate.py`;
- `corrected_applied/secure_plots.py`.

Canonical control workflows:

- `.github/workflows/eu26-21-corrected-secure-reaggregate.yml`;
- `.github/workflows/eu26-21-code-quality.yml`.
