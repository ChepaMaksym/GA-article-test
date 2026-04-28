# Verification Guide

## Run From MATLAB
From the project folder:

```matlab
main
```

For focused checks:

```matlab
run_unit_tests
run_ga_npw_reproduction
run_sandbox_deviation_check
```

## Run From PowerShell
```powershell
cd "C:\Users\User\OneDrive\Документы\MATLAB\GA new version\GA-NPW Leak Localization Reproduction"
matlab -batch "main"
```

## Correct Pass
A correct run should show:

- structure checks passed;
- unit tests passed;
- reproduction report written to `sandbox/results/ga_npw_reproduction_report.md`;
- sandbox report written to `sandbox/results/sandbox_deviation_report.md`;
- GA-NPW mean localization error below NPW baseline on synthetic reproduction scenarios.

## Expected Limitations
If MATLAB reports a licensing error, run from your normal licensed MATLAB session.

If a function is not found, make sure the working directory is the project root. The root-level wrappers add `src/` automatically.

```matlab
pwd
```

If a result looks too good or too bad, inspect the report header. Reports clearly identify synthetic data and should not be interpreted as the article's private field measurements.

## How To Check Correctness
Use three levels:

1. Formula correctness: `run_unit_tests` checks that NPW forward and inverse equations are consistent.
2. Optimizer correctness: `run_unit_tests` checks that the GA improves best fitness and is reproducible with the same seed.
3. Workflow correctness: `main` checks that reports are generated and that GA-NPW improves over NPW baseline on deterministic synthetic scenarios.
