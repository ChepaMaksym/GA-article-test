# Project Notes

## What Is Faithful
This project keeps the main article structure:

- Gaussian plume forward model.
- Figure-eight style synthetic sensor layout.
- Real-coded genetic search vector `[x, y, Q, H]`.
- MGA and NMGA comparison.
- NMGA adaptive audit that logs scheduled `Pc`/`Pm`, diversity, stagnation, runtime, and generation-to-best.
- Article GA settings such as dynamic-rate parameters `P1 = 0.6`, `P2 = 0.01`, `b = 2`, `beta = 0.7`, `gamma = 0.5`, `SetMax = 20`, population `100`, and reported generation counts.
- Article Table 1 values stored as `article_reported`.

## What Is Synthetic
The article says data sharing is not applicable. Exact sensor coordinates and raw monitoring concentrations are not available in this workspace. Therefore:

- generated observations are `synthetic_reproduction`;
- the sensor grid is a documented dual-loop/figure-eight approximation;
- reports compare workflow behavior against article Table 1 but do not claim exact numerical reproduction.

## Runtime Policy
The full article repetition count is 100 runs, which can be slow in a local sandbox. The project supports `run_nmga_reproduction('full')`, but the default `main` uses a shorter deterministic profile for practical verification.

## Randomness Policy
Randomness is controlled:

- unit tests use fixed seeds and small deterministic runs;
- reproduction repeats use deterministic seed sequences;
- reports store profile and repeat count;
- sandbox scenarios are fixed tables rather than open-ended Monte Carlo.
- adaptive audit scenarios are deterministic practical benchmarks, not original article raw-data scenarios.

## Adaptive Control Interpretation
The implemented NMGA follows the article-style generation schedule: crossover probability follows `P1 * (1 - generation / maxGenerations)^b`, and mutation probability follows `P2 * (1 + generation / maxGenerations)^b`. The audit logs population diversity and stagnation to inspect behavior, but the current `nmga_adaptive_rates` function does not use diversity or stagnation as feedback signals. Therefore, reports should describe the current method as scheduled-adaptive control, not feedback-adaptive control.
