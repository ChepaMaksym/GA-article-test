# Article Summary

## Source
- Article: **Application of New Modified Genetic Algorithm in Inverse Calculation of Strong Source Location**
- Authors: Jiming Yao, Yajing Liu, Zhengwen Feng, Tong Liu, Shuai Zhou, Hongjian Liu
- Journal: Atmosphere 2023, 14(1), 89
- DOI: `10.3390/atmos14010089`
- URL: https://www.mdpi.com/2073-4433/14/1/89

## Research Goal
The article improves inverse calculation of hazardous light-gas leakage sources. It combines monitoring concentrations with an atmospheric dispersion model and uses a **New Modified Genetic Algorithm (NMGA)** to estimate source position, release rate, and effective height.

## Article Method
- Forward model: Gaussian plume model for continuous point-source leakage.
- Search vector: source position and intensity parameters.
- Objective: maximize the reciprocal of squared concentration residuals between observed and calculated sensor concentrations.
- Baseline comparator: Modified Genetic Algorithm (MGA).
- Proposed method: NMGA with adaptive crossover/mutation and revised use of the elimination gene pool.

## Article Parameters
- Leakage rate: `Q = 15178.32 g/s`.
- Effective height: `Hr = 2 m`.
- Wind speed: `2.0 m/s`.
- Atmospheric stability: `E`.
- Source target near `x = -25 m`, `y = 16 m`.
- MGA fixed parameters include crossover `Pc = 0.6`, maternal inheritance ratio `beta = 0.7`, following rate `gamma = 0.5`, and `SetMax = 20`.
- NMGA uses dynamic crossover and mutation rates with `beta = 0.7`, `gamma = 0.5`, and `SetMax = 20`.

## Reported Table 1 Context
The article reports 100 independent calculations:

- MGA `100 x 2000`: mean x `49.86`, mean y `25.02`, mean Q `10442.96`.
- NMGA `100 x 1000`: mean x `-25`, mean y `16`, mean Q `15178.00`, mean Hr `2.00`.
- NMGA `100 x 500`: mean x `-24.9719`, mean y `16.0081`, mean Q `15173`, mean Hr `1.9981`.

The article concludes that NMGA improves convergence speed, inverse accuracy, and stability compared with MGA.
