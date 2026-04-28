# Project Notes

## What This Project Reproduces
This project reproduces the computational structure of the article's GA-NPW method:

- NPW time-difference equation;
- NPW baseline using nominal parameters;
- GA-NPW search over leak position, wave speed, fluid velocity, and time offset;
- article-reported GA settings;
- localization metrics used by the paper;
- stress cases for wave-speed bias, noise, flow variation, and synchronization error.

For controlled synthetic validation, the GA fitness also receives a known leak-position target. This mirrors controlled-test calibration logic, where the leak point is known for validation. It is not presented as a real-time deployment fitness for unknown field leaks.

## What This Project Does Not Reproduce
The project does not claim field-data reproduction. The following inputs are not available in this workspace:

- original pressure time series;
- exact leak valve event data;
- Pipeline Studio model;
- SCADA pipeline integration;
- authors' original GA implementation;
- pressure-distance profiles required for a faithful HGI implementation.

Therefore, HGI is recorded as an article-reported comparator but is not recomputed here.

## Synthetic Reproduction Policy
All generated scenarios are marked as `synthetic_reproduction`. They are deterministic and bounded by article-like conditions:

- pipeline length: `175000 m`;
- leak positions: `15-160 km`;
- wave speed bias: within about `+/-10%`;
- flow variation: `60-120%` of nominal;
- synchronization error: up to `2 s`.

The sandbox uses nonuniform weights to emphasize difficult operating cases. These weights are for verification pressure, not for claiming article field performance.

## Randomness Policy
Randomness is minimized:

- unit tests are deterministic;
- synthetic cases are fixed tables;
- GA uses a fixed seed;
- initial population includes deterministic low-discrepancy points and article-like parameter bounds;
- reports store seeds and scenario metadata.

## Naming
The previous SAA project was removed because SAA is not the optimizer used in the paper. This project uses only GA for the optimization layer.
