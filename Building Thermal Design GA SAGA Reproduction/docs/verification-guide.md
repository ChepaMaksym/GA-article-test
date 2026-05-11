# Verification Guide

Run:

```matlab
run_unit_tests
run_reproduction
run_sandbox
```

Expected outputs:

- unit tests pass the formal SAGA and classical GA checks;
- `sandbox/results/reproduction_report.md` is created;
- `sandbox/results/reproduction_result.mat` is created;
- `sandbox/results/saga_sandbox_report.md` is created;
- `sandbox/results/saga_sandbox_result.mat` is created.

Important interpretation rule: generated LCC values are surrogate results. They can be used to compare algorithm mechanics under shared budgets, but they are not EnergyPlus reproduction values.
