# Corrected applied methodology amendment

Date frozen: **2026-08-17**, before inspection of any valid corrected-profile
seed outcome.

## Why this additional track exists

The earlier OLD and Hybrid 1 campaigns remain immutable evidence for the
public-source protocol. They are not deleted or re-labelled. A later audit found
four limitations that prevent the source-compatible result from being the only
applied conclusion:

1. Census-Income is strongly class-imbalanced, but the original objective and
   H1 used accuracy only.
2. UCI states that raw column 24 is an instance weight and must not be supplied
   to a classifier as a predictive variable.
3. The public source used only its checked-in `census-income.data` and created a
   contiguous 60/20/20 split instead of using the official UCI test file.
4. The 30-seed OLD-versus-Hybrid result compared complete search layers and did
   not isolate reset on Census.

The corrected applied track addresses those issues without altering the
historical source-reproduction claims.

## Representation-compatibility amendment

The first corrected runner draft combined the upstream repository's checked-in
training file with the official UCI test file. Before any corrected optimizer
row completed, inspection showed that the upstream training file is already
fully numerically encoded, while the official UCI file retains raw categorical
values. Fitting an encoder on the former and transforming the latter would map
most test categories to the unknown sentinel and invalidate the applied result.

Therefore the final corrected profile uses **both official UCI files extracted
from one authenticated official archive**:

```text
census-income.data
census-income.test
```

The pinned upstream repository supplies only `Evolution.py` and its CHC
semantics. It supplies no corrected-profile data. The invalid pre-outcome run is
retained as an implementation/protocol failure; it generated no scientific
result and was not used to select parameters.

## Frozen data protocol

- Official UCI training file: `census-income.data`, 199,523 rows.
- Official UCI held-out file: `census-income.test`, 99,762 rows.
- Both files are extracted from the same authenticated current UCI ZIP archive.
- Raw file layout: 41 inputs plus one binary target.
- Raw index 24 (`instance weight`) is removed from the feature mask.
- Corrected mask dimension: 40.
- Instance weight is passed to Decision Tree fitting and weighted metrics.
- Each seed defines a stratified 80/20 train/validation split inside the official
  training file.
- Each seed defines one stratified active sample of exactly 14,964 training
  records.
- Preprocessing is fitted on the training partition only.
- Numeric variables use median imputation and standardization.
- Categorical variables use most-frequent imputation and train-fitted ordinal
  encoding; unseen validation/test values map to `-1`.
- The official test file is never used during feature-mask optimization.

The changing stratified split means the 30-seed uncertainty includes both search
randomness and train/validation split variability. The official test set remains
fixed.

## Frozen optimizer protocol

For every seed `1..30`:

- OLD and all Hybrid variants receive the same 50 initial 40-bit masks.
- OLD uses the pinned public-source CHC semantics on the corrected objective.
- Hybrid H1 uses reset self-adjusting `(1+(lambda,lambda))`, budget 400, four
  ordered evaluation workers.
- Reset ablation uses Hybrid reset and Hybrid no-reset, each with budget 2,500
  and one worker.
- Update factor remains `F=1.5`.
- No corrected-profile parameter may be changed after outcome inspection.

## Objective and reported metrics

Optimization objective:

```text
(weighted balanced accuracy on validation, -selected_feature_fraction)
```

Official-test reporting includes weighted and unweighted:

- accuracy;
- balanced accuracy;
- positive-class precision;
- positive-class recall;
- positive-class F1;
- Matthews correlation coefficient;
- ROC-AUC;
- average precision (PR-AUC summary);
- no-information rate;
- confusion matrix.

## Corrected hypotheses

### C-H1 - applied quality non-inferiority

Primary metric: **weighted balanced accuracy on the official UCI test file**.

```text
Hybrid H1 - OLD >= -0.001
```

The margin is retained at 0.10 percentage point so that the corrected track does
not loosen the criterion after seeing the earlier accuracy result. The primary
decision uses the lower endpoint of a two-sided 95% paired-median BCa interval
with 50,000 deterministic resamples.

A failure is a scientific result and does not make CI a protocol failure.
Sensitivity is also reported for margins 0.05, 0.10, 0.15, and 0.20 percentage
point.

### C-H2 - subset size

Only if C-H1 passes, the paired median of:

```text
Hybrid H1 selected features - OLD selected features
```

must be at most zero.

### C-H8 - reset-specific Census ablation

The paired reset-minus-no-reset weighted-balanced-accuracy interval is classified
without a preferred outcome:

- `POSITIVE_CONFIDENCE` if the two-sided 95% lower bound is above zero;
- `NEGATIVE_CONFIDENCE` if the upper bound is below zero;
- `NO_CLEAR_EFFECT` otherwise.

This result is the only corrected Census claim that may be attributed directly
to the reset transition.

## Claim boundary

The corrected track may support:

- a weight-aware, official-train/test, balanced-metric comparison;
- an applied Hybrid-versus-OLD conclusion for this frozen protocol;
- a reset-specific paired Census result.

It may not be used to erase the public-source reproduction, claim that the
printed CHC-QX paper equals the source, claim wall-clock speedup from logical
NFE, or claim worldwide novelty without a systematic review.
