# SPSO-GA Fault Location Reproduction

MATLAB replication package for:

**Faults locating of power distribution systems based on successive PSO-GA algorithm**

Source: https://www.nature.com/articles/s41598-024-61306-w  
DOI: `10.1038/s41598-024-61306-w`

This project reproduces the article workflow structure: IEEE33-node distribution-network fault signatures, FTU-style binary alarm observations, PSO-GA/SPSO-GA inverse fault-section search, deterministic tests, and sandbox deviation checks.

The original raw FTU datasets and full simulation files are not available in this workspace, so executable results are clearly labeled `synthetic_reproduction`.

## Structure
- `main.m` - full workflow entry point.
- `run_spso_ga_reproduction.m` - article-aligned PSO-GA/SPSO-GA comparison.
- `run_sandbox_deviation_check.m` - noisy/missing-FTU/stress sandbox.
- `run_unit_tests.m` - deterministic correctness tests.
- `article/` - source reference note.
- `docs/` - article summary, project notes, verification guide.
- `src/data/` - article-reported parameters and synthetic IEEE33 inputs.
- `src/models/` - network signatures, synthetic observations, objective function.
- `src/optimization/` - PSO-GA and SPSO-GA optimizer.
- `src/metrics/` - fault-location metrics.
- `sandbox/results/` - generated Markdown and MAT reports.

## Commands
Run from this folder in MATLAB:

```matlab
main
run_unit_tests
run_spso_ga_reproduction
run_sandbox_deviation_check
```
