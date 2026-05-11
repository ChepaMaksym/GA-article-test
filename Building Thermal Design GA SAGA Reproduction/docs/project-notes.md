# Project Notes

The project separates source-backed facts from executable surrogate experiments.

Source-backed layer:

- article metadata and DOI;
- reference building LCC and energy demand;
- discrete design options and cost data;
- seven optimization case masks;
- reported high-level savings for cooling and no-cooling variants.

Executable layer:

- a deterministic surrogate forward model replaces the unavailable EnergyPlus model;
- classical GA uses fixed `Pm`, `Pc`, and mutation strength;
- formal SAGA keeps `Pm`, `Pc`, and `sigma` inside each individual;
- reports label all executable results as `synthetic_surrogate`.

The main scientific check is not "SAGA always wins". The required check is that the SAGA implementation is formal: `theta_base` is encoded, varied, bounded, logged, and selected with `x` without external generation, stagnation, or diversity rules.
