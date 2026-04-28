# Verification Guide

## Run
From MATLAB inside this folder:

```matlab
main
```

Focused commands:

```matlab
run_unit_tests
run_spso_ga_reproduction
run_sandbox_deviation_check
```

## Correct Pass
A correct run should show:

- structure checks passed;
- unit tests passed;
- `spso_ga_reproduction_report.md` generated;
- `sandbox_deviation_report.md` generated;
- SPSO-GA accuracy is at least as good as PSO-GA on the synthetic reproduction set.

## Important Limitation
Generated results are synthetic workflow checks. They are not the original article's FTU upload data.
