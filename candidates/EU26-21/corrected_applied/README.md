# EU26-21 corrected applied validation

Status: `PASS_PROTOCOL_RESULTS_AVAILABLE`.

The corrected applied profile has completed its preregistered 30-seed campaign.
It is an additional validity track and does not rewrite or discard the immutable
OLD and source-compatible Hybrid 1 evidence.

## Scientific decisions

```text
C-H1 weighted balanced-accuracy non-inferiority: FAIL_NONINFERIORITY
C-H2 feature-count claim: BLOCKED_BY_H1
C-H8 reset/no-reset Census ablation: NO_CLEAR_EFFECT
```

The negative C-H1 outcome is a valid scientific result, not a protocol failure.
See `RESULTS.md` for the complete paired estimates, confidence intervals,
metrics, hashes, environment fingerprint, and interpretation.

## Corrections implemented

1. Uses both official UCI files: `census-income.data` for model development and
   `census-income.test` as the final held-out set. The pinned upstream
   repository supplies only CHC code because its checked-in data file is already
   numerically encoded and is not representation-compatible with raw UCI test
   categories.
2. Removes raw instance-weight index 24 from the predictive mask: 41 UCI inputs
   become 40 predictive inputs.
3. Supplies instance weights to Decision Tree fitting and weighted metrics.
4. Optimizes weighted balanced accuracy rather than accuracy.
5. Reports accuracy, balanced accuracy, positive precision/recall/F1, MCC,
   ROC-AUC, average precision, no-information rate, and confusion matrices.
6. Uses 30 stratified train/validation splits rather than one fixed contiguous
   split.
7. Runs a paired 30-seed reset/no-reset Census ablation.
8. Produces paired scatter, difference-with-margin, reset-ablation, feature-count
   boxplot, and balanced-metric figures instead of seed-connecting line charts.

## Canonical files

- `data_protocol.py` - weight-aware official-train/test protocol and metrics;
- `experiment.py` - one paired OLD/Hybrid/reset-ablation seed;
- `aggregate.py` - shared row validation and statistical calculations;
- `secure_aggregate.py` - exact environment, mask, index, and provenance gates;
- `secure_cli.py` - canonical strict aggregation entry point;
- `secure_plots.py` - Matplotlib 3.11-compatible scientific plots;
- `requirements.txt` - frozen modern corrected environment;
- `METHODOLOGY_AMENDMENT.md` - frozen pre-outcome criteria;
- `RESULTS.md` - completed 30-seed decisions and limitations.

Tests:

```text
candidates/EU26-21/tests/test_corrected_applied.py
candidates/EU26-21/tests/test_corrected_secure_aggregate.py
```

Workflows:

```text
.github/workflows/eu26-21-corrected-applied-secure-matrix.yml
.github/workflows/eu26-21-corrected-secure-reaggregate.yml
.github/workflows/eu26-21-code-quality.yml
```

The immutable reaggregation workflow consumes the complete secure-final artifact
from the 30-seed matrix, validates all 30 rows with `secure_cli`, regenerates the
CSV and five plots, and explicitly records that no optimizer was rerun.

## Outcome policy

Protocol or implementation defects fail CI. C-H1, C-H2, or C-H8 may be
negative or null while the evidence remains scientifically usable. Such an
outcome is written to the result artifact and analyzed without parameter tuning.

## Relationship to earlier results

- `old/` remains the authenticated public-source reproduction.
- `hybrid_1/` remains the source-compatible 41-bit comparison and supports its
  own H1-H3 claims under that historical profile.
- `corrected_applied/` is the weight-aware 40-bit official-UCI profile and does
  not support corrected non-inferiority at the preregistered 0.10 percentage-
  point margin.

The two profiles answer different questions. Results from one must not be
silently substituted for results from the other.

No merge is part of this stage.
