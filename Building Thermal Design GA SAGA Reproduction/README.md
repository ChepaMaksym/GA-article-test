# Building Thermal Design GA + Formal SAGA Reproduction

This MATLAB project is a self-contained research sandbox for:

- Ferdyn-Grygierek, J.; Grygierek, K. "Multi-Variable Optimization of Building Thermal Design Using Genetic Algorithms." Energies 2017, 10, 1570. https://doi.org/10.3390/en10101570
- the local development rule in `plan/ga_inverse_research_development_plan.md`.

The article uses MATLAB plus EnergyPlus and describes a fuzzy self-adaptive GA controller. Under the local plan, that article method is not treated as formal SAGA because its parameters are calculated externally from diversity, simulation stage, and no-improvement count. This project therefore implements two valid algorithms only:

1. `classical GA`: x-only genotype with fixed GA parameters.
2. `formal SAGA`: individual genotype `I = (x, theta_base)`, where `theta_base = (Pm, Pc, sigma)` is varied and selected with the individual.

The EnergyPlus model and source code are not bundled with the article page, so executable runs use a clearly marked deterministic surrogate model. Reported article data are encoded for metadata, scope checks, and comparison context, not claimed as a full EnergyPlus reproduction.

## Run

From this folder:

```matlab
main
run_unit_tests
run_reproduction
run_sandbox
```

Batch examples:

```powershell
matlab -batch "main"
matlab -batch "run_unit_tests"
matlab -batch "run_reproduction"
matlab -batch "run_sandbox"
```

## Layout

- `src/data`: article metadata, reported values, design space, cases, sandbox scenarios.
- `src/models`: discrete building genome decoder, surrogate thermal/LCC model, fitness function.
- `src/optimization`: classical GA, formal SAGA, criterion checks, reproduction/sandbox runners.
- `src/metrics`: summary metrics for GA vs SAGA.
- `src/replication`: project structure verification.
- `tests`: unit tests for GA and formal SAGA rules.
- `sandbox/results`: generated `.mat` files and Markdown reports.

## Dependencies

Only base MATLAB is required. No Global Optimization Toolbox, Parallel Computing Toolbox, Statistics and Machine Learning Toolbox, or EnergyPlus installation is required for the sandbox runs.
