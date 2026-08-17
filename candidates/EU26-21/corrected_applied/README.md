# EU26-21 corrected applied validation

Status: `PREREGISTERED_AND_IMPLEMENTED_RESULTS_PENDING`.

This directory is the canonical response to the post-experiment validity audit.
It adds a new applied track; it does not rewrite or discard the immutable OLD and
Hybrid 1 evidence.

## Corrections implemented

1. Uses the official UCI `census-income.test` file as the final held-out set.
2. Removes raw instance-weight index 24 from the predictive mask: 41 source
   inputs become 40 predictive inputs.
3. Supplies instance weights to Decision Tree fitting and weighted metrics.
4. Optimizes weighted balanced accuracy rather than accuracy.
5. Reports accuracy, balanced accuracy, positive precision/recall/F1, MCC,
   ROC-AUC, average precision, no-information rate, and confusion matrices.
6. Uses 30 stratified train/validation splits rather than one fixed contiguous
   split.
7. Runs a 30-seed reset/no-reset Census ablation.
8. Produces paired scatter, difference-with-margin, reset-ablation, feature-count
   boxplot, and balanced-metric figures instead of seed-connecting line charts.

## Canonical files

- `data_protocol.py` - weight-aware official-test protocol and metrics;
- `experiment.py` - one paired OLD/Hybrid/reset-ablation seed;
- `aggregate.py` - strict validation, BCa statistics, CSV, and plots;
- `METHODOLOGY_AMENDMENT.md` - frozen pre-outcome criteria.

Tests:

```text
candidates/EU26-21/tests/test_corrected_applied.py
```

Workflow:

```text
.github/workflows/eu26-21-corrected-applied-matrix.yml
```

## Outcome policy

Protocol or implementation defects fail CI. C-H1, C-H2, or C-H8 may be
negative or null while the workflow remains technically successful. Such an
outcome is written to the result artifact and analyzed without parameter tuning.

## Relationship to earlier results

- `old/` remains the authenticated public-source reproduction.
- `hybrid_1/` remains the source-compatible 41-bit comparison.
- `corrected_applied/` is the weight-aware 40-bit official-test profile.

No merge is part of this stage.
