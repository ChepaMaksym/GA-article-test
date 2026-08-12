# Hybrid 1 final verification results

## Decision

Status: `PASS_HYBRID_1_EXPERIMENT_WITH_MIXED_RESET_TRANSFER`.

The requested simple Hybrid 1 is implemented and verified. The complete
`(1+(lambda,lambda))` feature-mask search passed the preregistered applied H1-H2
gates on Census-Income, and the reset branch produced a large, repeatable gain
on the Jump local-optimum control. However, reset itself did **not** produce a
robust median improvement on Census: under a high budget it improved accuracy
in 2/10 paired runs, changed nothing in 8/10, and never reduced accuracy.

No claim is made that reset universally improves every applied landscape.

## Frozen evidence

- Hybrid commit under test: `c13bf493166f0cecda6d9fae17deda373d452e18`.
- GitHub Actions workflow run: `31587871151`.
- Environment: Python 3.9.25; NumPy 1.23.5; pandas 1.5.3; SciPy 1.10.1;
  scikit-learn 1.2.2; DEAP 1.3.3; PySwarms 1.3.0.
- Numerical-library threads were pinned to one. Hybrid evaluation workers were
  controlled separately.
- Applied OLD reference: `PASS_SOURCE_NUMERIC_ALIGNMENT` at upstream commit
  `6ac5a7ec77f8a7c096ab4d019254fcc897988fd6`.

## Implemented intervention

The applied data and model protocol remained frozen:

- Census-Income: 199,523 observations and 41 input variables;
- author-source contiguous 60/20/20 split;
- normalization fitted on training data only;
- source-compatible active training sample;
- Decision Tree with fixed classifier seed;
- optimization on validation data;
- one held-out test evaluation after search.

Only feature-mask search changed. Hybrid 1 uses:

```text
m = round_half_up(lambda)
p = lambda / 41
L ~ Binomial(41, p), shared by all mutants in the generation
c = 1 / lambda
strict improvement -> lambda / F
failure -> lambda * F^(1/4)
failure at lambda = 41 -> reset lambda to 1
```

Fitness is lexicographic:

```text
(validation accuracy, - selected_feature_fraction)
```

Accuracy therefore dominates sparsity.

## Reproducibility correction

The public CHC-QX active-sampling implementation contains a wall-clock-time
ratio. The first pilot confirmed that the selected sample size could change
between machines. Before the final campaigns, the experiment froze the sample
sizes from the already passing OLD seed ledger:

```text
seed: 1    2    3     4    5     6     7    8     9    10
size: 7482 7482 14964 7482 14964 14964 7482 14964 7482 14964
```

For every seed, the original random stream still generates the controlled
feature masks and candidate sample indices. Only the hardware-dependent timing
decision is replaced by the pre-frozen OLD size. Each row records a SHA-256
digest of the active-instance indices.

## Test matrix

All 15 unit and critical tests passed.

| Area | Verification | Result |
|---|---|---|
| Formulas | nearest-half-up `m`, `p=lambda/n`, `c=1/lambda` | PASS |
| Mutation | one shared binomial strength; exact-bit flips without replacement | PASS |
| Crossover | biased-uniform child construction | PASS |
| Final pool | selected best mutant plus crossover offspring; parent copies excluded | PASS |
| Control | neutral acceptance; strict-success shrink; failure growth; cap reset | PASS |
| Bounds | `1 <= lambda <= n`; no logical NFE overshoot | PASS |
| Census boundary | empty masks dominated; validation-only search; final held-out test | PASS |
| Frozen data | complete seed 1..10 active-size ledger | PASS |
| OneMax | 20 seeds, reset/no-reset exact no-regression | PASS |
| Workers | 1/2/4 evaluation workers and 1/2/4 campaign workers | PASS |

The worker tests preserved the complete scientific signature, not only final
accuracy: mask, fitness, logical NFE, lambda trajectory, mutation strengths,
acceptance sequence, strict-success sequence, and reset count were identical.
For the real Census worker matrix, the frozen seed-1 active-instance digest was
`5a5726d03fda76d40dd37372b9ad4e5bdf5c4377b6c414fa516aa62798ad94a8`.

## H4 - Jump local-optimum confirmation

Frozen configuration:

- `Jump_3`;
- `n=20`;
- every run starts at the exact local optimum with 17 one-bits;
- common budget: 10,000 logical fitness evaluations;
- confirmation seeds: 101..150;
- four campaign workers.

| Metric | Reset | No reset | Difference |
|---|---:|---:|---:|
| Successful runs | 27/50 | 8/50 | +19 runs |
| Success rate | 54% | 16% | **+38 percentage points** |
| Relative success | - | - | **3.375x** |
| Median NFE among solved runs | 3,389 | 4,991 | **32.1% lower** |
| Observed reset events | 783 | 0 | mechanism activated |

All preregistered Jump gates passed. This is the strongest causal evidence for
the transferred reset mechanism because reset and no-reset variants differ in
only the failure-at-cap transition.

Artifact:

```text
name: eu26-21-hybrid-1-jump-confirmation
id: 9137904197
sha256: ed955e1be82c3cfcfb3cc4d774654b6012d2bfb37e354a46e7bca17127d1d1bd
```

## H1-H2 - Census practical-budget campaign

Frozen configuration:

- seeds 1..10;
- 50 common initial masks per seed;
- 400 logical evaluations;
- four evaluation workers;
- 20,000 bootstrap resamples.

| Metric | OLD CHC-QX | Hybrid 1 | Interpretation |
|---|---:|---:|---|
| Median test accuracy | 94.9455% | **94.8841%** | -0.0614 pp by aggregate medians |
| Hybrid median 95% bootstrap CI | - | 94.8428% to 94.9154% | narrow uncertainty band |
| Median paired accuracy difference | - | -0.0551 pp | CI -0.1177 to -0.0250 pp |
| Median selected features | 8 | **6** | 25% fewer by medians |
| Hybrid feature median 95% bootstrap CI | - | 5 to 7 | below OLD median 8 |
| Runs beating all-feature baseline by >=1.5 pp | - | **10/10** | baseline gate passed |

All frozen H1-H2 point-estimate gates passed:

- complete ten-seed ledger;
- exact frozen active-sample protocol;
- median accuracy above the allowed non-inferiority margin of 94.8455%;
- at least 8/10 baseline gains, observed 10/10;
- median feature count at most 8, observed 6.

Important statistical limitation: the bootstrap lower bound, 94.8428%, is
0.0027 percentage points below the non-inferiority threshold. Thus the
preregistered point-estimate gate passes, but a stronger confidence-bound
non-inferiority claim needs more seeds.

Reset was dormant in all ten budget-400 runs, so these applied results establish
the performance of the self-adjusting Hybrid 1 search as a whole. They do not
identify a separate reset effect.

Artifact:

```text
name: eu26-21-hybrid-1-census-final-budget-400
id: 9137988308
sha256: 7566e19f527bacc87dbd6db19af69e146d0e4211bd28f58fdf22940e052f1de9
```

## Reset-specific Census ablation

A second paired campaign used the same ten seeds and initial masks with a budget
of 2,500 evaluations so that lambda could reach the cap and the reset branch
could activate.

| Metric | Reset | No reset |
|---|---:|---:|
| Median test accuracy | **94.8954%** | 94.8741% |
| Mean test accuracy | **94.8891%** | 94.8828% |
| Median selected features | 5.5 | **4.5** |
| Runs with at least one reset | 10/10 | - |
| Total reset events | 17 | - |
| Median NFE of first reset | 1,257 | - |

Paired causal result:

- 2/10 runs obtained higher test accuracy with reset;
- 8/10 runs produced exactly the same final test accuracy and feature subset;
- 0/10 runs obtained lower test accuracy with reset;
- the two positive changes were +0.0100 and +0.0526 percentage points;
- paired median accuracy effect was 0.0000 percentage points;
- bootstrap 95% CI for the paired median effect was 0.0000 to +0.0050
  percentage points;
- one positive-accuracy run selected three additional features; all other
  paired feature counts were identical.

Therefore the appropriate conclusion is:

```text
Reset occasionally improves the Census endpoint after activation, but the
current ten-seed evidence does not show a robust median benefit. Its effect is
strong and repeatable on Jump, but landscape-dependent on Census.
```

The full high-budget Hybrid still passed the H1-H2 applied gates, with median
accuracy 94.8954% and median 5.5 features. Relative to OLD, its paired median
accuracy difference was -0.0576 percentage points and its paired median feature
difference was -3.5 features.

Artifact:

```text
name: eu26-21-hybrid-1-census-final-budget-2500
id: 9138194131
sha256: 2316763a49bd435aace3d8cd329d028b76bef11cff8c5b5d7371ffbcd70161a0
```

## Hypothesis decisions

| Hypothesis | Decision | Evidence |
|---|---|---|
| H1 applied accuracy non-inferiority | PASS by preregistered point gate | both Census budgets pass; confidence-bound caveat retained |
| H2 smaller subsets | PASS descriptive/preregistered gate | median 6 at budget 400 and 5.5 at budget 2500 vs OLD 8 |
| H3 at least 20% fewer NFE than OLD | PENDING | OLD source lacks equivalent exact logical NFE instrumentation |
| H4 Jump local-optimum gain | PASS strongly | +38 pp success; 3.375x successes; 32.1% lower solved-run median NFE |
| H5 1/2/4 worker invariance | PASS exactly | complete scientific signatures identical |
| H6 OneMax no regression | PASS exactly | all 20 paired runs solve identically |
| H7 critical semantics | PASS | formula, operator, transition, budget, and data-boundary tests |

## Final scientific interpretation

Hybrid 1 is a valid master-level experimental contribution because it provides:

1. a clearly isolated transfer of a published parameter-control mechanism to an
   applied feature-selection landscape;
2. an independently implemented and fixed-tape-tested algorithmic core;
3. an OLD reference reproduced before hybrid testing;
4. mechanism controls on Jump and OneMax;
5. exact multicore reproducibility checks;
6. paired reset/no-reset ablation;
7. two-budget applied evaluation with an honest positive, negative, and null
   result boundary.

The strongest positive finding is reset on Jump. The strongest applied finding
is that Hybrid 1 keeps Census accuracy within the frozen tolerance while using
fewer features. The central limitation is that the reset-specific Census effect
is sparse rather than robust, and H3 remains open until OLD receives equivalent
logical-NFE instrumentation.
