# Verification Guide

Run the main flow:

```matlab
main
```

Expected outputs:

- `sandbox/results/matlab_ga_report.md`
- `sandbox/results/matlab_ga_result.mat`

Optional smoke tests:

```matlab
addpath(genpath('src'));
addpath('tests');
run_unit_tests_impl
```
