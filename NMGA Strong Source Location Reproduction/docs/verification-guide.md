# Verification Guide

## Run From MATLAB
From the project folder:

```matlab
main
```

Focused commands:

```matlab
run_unit_tests
run_article_exact_reproduction
run_nmga_reproduction
run_nmga_adaptive_audit
run_sandbox_deviation_check
```

Longer article-like run:

```matlab
run_article_exact_reproduction('article_exact')
run_nmga_reproduction('full')
```

## Correct Pass
A correct default run should show:

- structure checks passed;
- unit tests passed;
- article exact smoke/unit reports written when `run_unit_tests` calls `run_article_exact_reproduction_impl('unit')`;
- reproduction report written to `sandbox/results/nmga_reproduction_report.md`;
- adaptive audit report written to `sandbox/results/nmga_adaptive_audit_report.md`;
- sandbox report written to `sandbox/results/sandbox_deviation_report.md`;
- NMGA has lower error or faster convergence than MGA on the synthetic sensor set.
- adaptive audit identifies the current NMGA as generation-scheduled control, not feedback-adaptive control.

`main` runs the adaptive audit with profile `unit` as a smoke check. Run `run_nmga_adaptive_audit` directly for the wider default quick audit.

## What To Inspect
- `docs/article-summary.md` for article-reported context.
- `docs/project-notes.md` for reproduction limits.
- `docs/replication-audit.md` for test coverage, logic risks, verification plan, and known errors.
- `sandbox/results/nmga_reproduction_report.md` for MGA/NMGA comparison.
- `sandbox/results/article_exact_report.md` for the separated public-text Table 1 protocol and raw-data limitation statement.
- `sandbox/results/operator_audit_report.md` for article operator -> local function -> test mapping.
- `sandbox/results/nmga_adaptive_audit_report.md` for Pc/Pm schedule, diversity, stagnation, noise, sensor sparsity, wind uncertainty, and MGA/NMGA same-budget checks.
- `sandbox/results/sandbox_deviation_report.md` for stress scenarios.

## Important Limitation
The reports are workflow validation using synthetic data. They are not the article authors' raw field/simulation data.
`run_article_exact_reproduction('article_exact')` uses article formulas, parameters, operators, and run counts, but still labels results `synthetic_reproduction` until exact sensor coordinates and observed concentrations are available.
