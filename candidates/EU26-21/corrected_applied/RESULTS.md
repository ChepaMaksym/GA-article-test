# EU26-21 corrected applied 30-seed results

## Final status

```text
claim_status: PASS_PROTOCOL_RESULTS_AVAILABLE
C-H1: FAIL_NONINFERIORITY
C-H2: BLOCKED_BY_H1
C-H8: NO_CLEAR_EFFECT
```

This is a completed negative/null scientific result. The 30-row protocol is
complete and internally consistent; the hypotheses are not relabeled as passes.

## Immutable evidence

```text
secure matrix run: 32049437836
source artifact: 9297184026
artifact name: eu26-21-corrected-applied-secure-final
artifact SHA-256: 13d2f691eefb46067d3cdffbad4c22c032c429ce91600a33addbd3f5887bbdeb
seed ledger: 1..30
seed rows: 30/30
```

The source artifact contains all seed JSON files, logs, the aggregate report,
CSV, status JSON, and the plots produced before the original plotting call
encountered a Matplotlib keyword incompatibility. The report and rows were
already written before that plotting-only exception. Canonical strict
reaggregation is performed by:

```text
.github/workflows/eu26-21-corrected-secure-reaggregate.yml
python -m corrected_applied.secure_cli
```

That workflow downloads the single immutable source artifact, verifies its
fixed run ID, artifact ID, SHA-256, and 30-seed ledger, applies the stricter
secure row validator, regenerates all five plots, and records:

```text
seed_rows_regenerated: false
optimizer_rerun: false
```

## Protocol fingerprint

| Field | Value |
|---|---:|
| Official training rows | 199,523 |
| Official held-out test rows | 99,762 |
| Predictive dimension | 40 |
| Instance-weight raw index | 24 |
| Weight selectable as predictor | No |
| Weight used as sample weight | Yes |
| Primary metric | Weighted balanced accuracy |
| Runs | 30 paired seeds |
| Bootstrap | Paired-median BCa, 50,000 resamples |
| C-H1 margin | 0.001 = 0.10 percentage point |

```text
train SHA-256:
3676a81db7d3528f3f8b9f3c699d0f0aa28db45e6e994fa0b8ed38327539ee86

official test SHA-256:
98402b1ab879573d0a7f38a699a40258080e25e33d3401e7bf9c96d3fa0fab8c
```

Every seed uses a distinct stratified train/validation split and active-sample
ledger while retaining the same official training and held-out test files.

## Frozen secure environment

Every row records the same environment profile:

```text
environment_profile: corrected_secure_2026
Python: 3.11.15
NumPy: 2.4.6
pandas: 3.0.3
SciPy: 1.17.1
scikit-learn: 1.9.0
Matplotlib: 3.11.1
Pillow: 12.3.0
DEAP: 1.4.4
PySwarms: 1.3.0
```

Strict validation also confirms for baseline, OLD, Hybrid H1, reset, and
no-reset in every seed:

- exactly 40 binary mask positions;
- a non-empty selected subset;
- selected-mask, predictive-index, raw-index, name, and count agreement;
- no occurrence of forbidden raw index 24;
- finite weighted and unweighted metric blocks;
- exact H1 and reset/no-reset budgets and worker settings;
- zero reset events in every no-reset run.

## C-H1 - corrected quality non-inferiority

Primary paired contrast:

```text
Hybrid H1 weighted balanced accuracy - OLD weighted balanced accuracy
```

Results:

```text
paired median: -0.0035800477
paired median in percentage points: -0.3580048 pp
95% BCa: [-0.0069321962, -0.0021589194]
95% BCa in percentage points: [-0.6932196, -0.2158919] pp
one-sided 95% lower bound: -0.0064300073
preregistered margin: -0.001 = -0.10 pp
C-H1: FAIL_NONINFERIORITY
```

The entire two-sided 95% interval lies below the -0.10 pp non-inferiority
margin. Sensitivity checks also fail at 0.05, 0.10, 0.15, and 0.20 pp margins.
Therefore the corrected profile does not support the claim that Hybrid H1 is
non-inferior to OLD on official-test weighted balanced accuracy.

This does not mean every seed favored OLD. It means the paired central estimate
and confidence interval do not satisfy the preregistered non-inferiority rule.

## C-H2 - feature count

```text
paired median Hybrid H1 - OLD feature count: -1 feature
C-H2: BLOCKED_BY_H1
```

Hybrid H1 selected fewer features at the paired median, but C-H2 was
preregistered as conditional on C-H1. The feature-count observation is retained
descriptively and is not promoted to a successful joint quality/sparsity claim.

## C-H8 - reset-specific Census ablation

Primary paired contrast:

```text
Hybrid reset weighted balanced accuracy - Hybrid no-reset weighted balanced accuracy
```

Results:

```text
paired median: 0.0
95% BCa: [0.0, 0.0000959391]
95% BCa in percentage points: [0.0, 0.0095939] pp
runs with at least one reset event: 30/30
total reset events: 49
C-H8: NO_CLEAR_EFFECT
```

Reset events were exercised in every run, so the null result is not caused by an
inactive reset branch. The interval includes zero and provides no clear positive
or negative official-test effect under this paired Census protocol.

## Weighted official-test medians

| Method | Accuracy | Balanced accuracy | Precision+ | Recall+ | F1+ | MCC | ROC-AUC | PR-AUC | Features |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Baseline, all features | 0.930092 | 0.725849 | 0.452593 | 0.491351 | 0.471622 | 0.434850 | 0.725563 | 0.255834 | 40.0 |
| OLD corrected | 0.929937 | 0.725030 | 0.451891 | 0.490785 | 0.472437 | 0.435507 | 0.726229 | 0.258553 | 28.5 |
| Hybrid H1 | 0.930268 | 0.721790 | 0.453669 | 0.483032 | 0.468293 | 0.431063 | 0.725334 | 0.258290 | 27.0 |
| Hybrid reset | - | 0.722991 | - | - | - | - | - | - | 26.0 |
| Hybrid no reset | - | 0.722020 | - | - | - | - | - | - | 26.0 |

The table reports medians over the 30 paired seeds. Full weighted and unweighted
per-seed values, confusion matrices, selected masks, and provenance ledgers are
stored in the immutable JSON evidence.

## Plotting failure classification

The source matrix's final job returned a nonzero status only after writing the
report and CSV, when Matplotlib 3.11 rejected the legacy `labels=` argument to
`Axes.boxplot`. The three earlier plots were already present. This is classified
as a plotting API compatibility defect, not a row-generation, validation, or
statistical failure.

The canonical `secure_plots.py` path uses the supported tick-label API and
successfully regenerates:

1. paired OLD versus Hybrid H1 scatter;
2. paired H1 difference with non-inferiority margin;
3. reset versus no-reset scatter;
4. feature-count boxplot;
5. weighted metric-median profile.

## Relationship to source-compatible H1-H3

The earlier source-compatible profile remains valid for its own historical
question and evidence:

- upstream-compatible encoded data and 41-bit representation;
- historical accuracy objective and source-oriented split;
- source-compatible H1-H3 decisions.

The corrected applied profile changes the validity question by using official
raw train/test files, excluding the weight column from predictors, applying
sample weights, optimizing weighted balanced accuracy, and varying the
train/validation split across seeds.

Consequently, the positive source-compatible H1 result and the negative
corrected C-H1 result are not contradictory duplicates. They show that the
claim is protocol-dependent. The dissertation or report must present both and
must not substitute source-compatible accuracy non-inferiority for corrected
weighted balanced-accuracy non-inferiority.

## Final interpretation

The corrected experiment supports the following defensible statement:

> The hybrid implementation is reproducible and can select slightly smaller
> subsets, but under the official-UCI, weight-aware, 30-split applied protocol it
> did not meet the preregistered weighted balanced-accuracy non-inferiority
> margin relative to corrected OLD. A paired reset/no-reset ablation exercised
> reset events in all runs but found no clear official-test effect.

It does not support corrected quality superiority, corrected non-inferiority, or
a reset-specific Census improvement claim.
