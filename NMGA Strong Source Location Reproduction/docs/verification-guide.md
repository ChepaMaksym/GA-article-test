# Verification Guide

## Run From MATLAB
From the project folder:

```matlab
main
```

Focused commands:

```matlab
run_unit_tests
run_nmga_reproduction
run_sandbox_deviation_check
```

Longer article-like run:

```matlab
run_nmga_reproduction('full')
```

## Correct Pass
A correct default run should show:

- structure checks passed;
- unit tests passed;
- reproduction report written to `sandbox/results/nmga_reproduction_report.md`;
- sandbox report written to `sandbox/results/sandbox_deviation_report.md`;
- NMGA has lower error or faster convergence than MGA on the synthetic sensor set.

## What To Inspect
- `docs/article-summary.md` for article-reported context.
- `docs/project-notes.md` for reproduction limits.
- `sandbox/results/nmga_reproduction_report.md` for MGA/NMGA comparison.
- `sandbox/results/sandbox_deviation_report.md` for stress scenarios.

## Important Limitation
The reports are workflow validation using synthetic data. They are not the article authors' raw field/simulation data.
