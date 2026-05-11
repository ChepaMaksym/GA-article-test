# GA vs Formal SAGA Reproduction Report

## Article
- Title: Multi-Variable Optimization of Building Thermal Design Using Genetic Algorithms
- Authors: Joanna Ferdyn-Grygierek, Krzysztof Grygierek
- DOI: `10.3390/en10101570`
- URL: https://www.mdpi.com/1996-1073/10/10/1570

## Scope
This is a synthetic surrogate reproduction because the article page does not bundle the EnergyPlus model or source MATLAB code. The fuzzy SGA from the article is classified as `non_saga_external_adaptation` under the local formal SAGA plan.

Classification reason: The article states that k, Pc, S, and Pm are calculated automatically during the run from diversity, stage, and no-improvement count by a fuzzy controller. The local criterion requires theta_base to be part of the genotype and varied by genetic variation.

## Summary
- Runs: 42
- Mean classical GA LCC: 7825.614 EUR
- Mean formal SAGA LCC: 7870.173 EUR
- Mean SAGA minus GA delta: 0.540%
- SAGA win rate: 0.071
- All SAGA criteria passed: 1

## Run Table
| Case | Mode | Seed | GA LCC EUR | SAGA LCC EUR | GA evals | SAGA evals | SAGA criterion |
|---:|---|---:|---:|---:|---:|---:|---|
| 1 | cooling | 20260503 | 9712.278 | 9712.278 | 4050 | 4050 | PASS |
| 1 | cooling | 20260504 | 9712.278 | 9712.278 | 4050 | 4050 | PASS |
| 1 | cooling | 20260505 | 9712.278 | 9712.278 | 4050 | 4050 | PASS |
| 1 | no_cooling | 20260503 | 7877.998 | 7877.998 | 4050 | 4050 | PASS |
| 1 | no_cooling | 20260504 | 7877.998 | 7877.998 | 4050 | 4050 | PASS |
| 1 | no_cooling | 20260505 | 7877.998 | 7877.998 | 4050 | 4050 | PASS |
| 2 | cooling | 20260503 | 9379.080 | 9513.840 | 4050 | 4050 | PASS |
| 2 | cooling | 20260504 | 9379.080 | 9748.739 | 4050 | 4050 | PASS |
| 2 | cooling | 20260505 | 9379.080 | 9650.189 | 4050 | 4050 | PASS |
| 2 | no_cooling | 20260503 | 6934.585 | 6934.585 | 4050 | 4050 | PASS |
| 2 | no_cooling | 20260504 | 6934.585 | 6934.585 | 4050 | 4050 | PASS |
| 2 | no_cooling | 20260505 | 6934.585 | 6934.585 | 4050 | 4050 | PASS |
| 3 | cooling | 20260503 | 9891.036 | 9891.036 | 4050 | 4050 | PASS |
| 3 | cooling | 20260504 | 9891.036 | 9891.036 | 4050 | 4050 | PASS |
| 3 | cooling | 20260505 | 9891.036 | 9891.036 | 4050 | 4050 | PASS |
| 3 | no_cooling | 20260503 | 8901.922 | 8901.922 | 4050 | 4050 | PASS |
| 3 | no_cooling | 20260504 | 8901.922 | 8901.922 | 4050 | 4050 | PASS |
| 3 | no_cooling | 20260505 | 8901.922 | 8901.922 | 4050 | 4050 | PASS |
| 4 | cooling | 20260503 | 9232.187 | 9232.187 | 4050 | 4050 | PASS |
| 4 | cooling | 20260504 | 9232.187 | 9232.187 | 4050 | 4050 | PASS |
| 4 | cooling | 20260505 | 9232.187 | 9232.187 | 4050 | 4050 | PASS |
| 4 | no_cooling | 20260503 | 7596.013 | 7596.013 | 4050 | 4050 | PASS |
| 4 | no_cooling | 20260504 | 7596.013 | 7596.013 | 4050 | 4050 | PASS |
| 4 | no_cooling | 20260505 | 7596.013 | 7596.013 | 4050 | 4050 | PASS |
| 5 | cooling | 20260503 | 8323.673 | 8323.673 | 4050 | 4050 | PASS |
| 5 | cooling | 20260504 | 8323.673 | 8652.913 | 4050 | 4050 | PASS |
| 5 | cooling | 20260505 | 8323.673 | 8323.673 | 4050 | 4050 | PASS |
| 5 | no_cooling | 20260503 | 5931.953 | 5931.953 | 4050 | 4050 | PASS |
| 5 | no_cooling | 20260504 | 5931.953 | 5931.953 | 4050 | 4050 | PASS |
| 5 | no_cooling | 20260505 | 5931.953 | 5931.953 | 4050 | 4050 | PASS |
| 6 | cooling | 20260503 | 7908.875 | 8369.063 | 4050 | 4050 | PASS |
| 6 | cooling | 20260504 | 8118.100 | 8391.831 | 4050 | 4050 | PASS |
| 6 | cooling | 20260505 | 8272.946 | 8053.961 | 4050 | 4050 | PASS |
| 6 | no_cooling | 20260503 | 5651.617 | 5651.617 | 4050 | 4050 | PASS |
| 6 | no_cooling | 20260504 | 4821.245 | 4887.613 | 4050 | 4050 | PASS |
| 6 | no_cooling | 20260505 | 4821.245 | 4851.020 | 4050 | 4050 | PASS |
| 7 | cooling | 20260503 | 8161.375 | 8138.790 | 4050 | 4050 | PASS |
| 7 | cooling | 20260504 | 7701.187 | 7814.204 | 4050 | 4050 | PASS |
| 7 | cooling | 20260505 | 7822.111 | 7901.019 | 4050 | 4050 | PASS |
| 7 | no_cooling | 20260503 | 4669.438 | 4683.265 | 4050 | 4050 | PASS |
| 7 | no_cooling | 20260504 | 4716.020 | 4683.265 | 4050 | 4050 | PASS |
| 7 | no_cooling | 20260505 | 4669.438 | 4674.655 | 4050 | 4050 | PASS |

## Reported Article Savings Context
Cooling cases, LCC savings percent: [5.9, 6.8, 10.6, 11.1, 16.2, 16.7, 34.2]

No-cooling cases, LCC savings percent: [13.3, 15.5, 19.3, 20.9, 30.2, 31.7, 51.1]
