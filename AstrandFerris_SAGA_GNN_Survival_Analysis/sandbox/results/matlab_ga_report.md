# MATLAB GA Main Flow Report

## Source
- Title: Self-Adaptive Mutation Operators for Genetic Neural Networks in Survival Analysis
- Author: Jonatan Astrand-Ferris
- Local PDF: `article\AstrandFerris_BachelorThesis_PostPresentation_.pdf`

## Main Flow
1. `synthetic_survival_datasets`
2. `train_validation_split`
3. `optimoptions('ga')`
4. `ga(...)`
5. `gnn_fitness -> mlp_predict -> c_index_error`

## MATLAB GA Methods
- Selection: `selectionstochunif`
- Crossover: `crossoverscattered`
- Mutation: `mutationgaussian`

## Summary
- Runs: 8
- Mean train c-index error: 0.1233
- Mean validation c-index error: 0.1500
- Mean validation c-index: 0.8500
- Mean function evaluations: 1228.0

| Dataset | Seed | Train error | Validation error | Validation c-index | Function evals | Exitflag |
|---|---:|---:|---:|---:|---:|---:|
| PBC_MAYO | 20260503 | 0.1331 | 0.2341 | 0.7659 | 1228 | 0 |
| PBC_MAYO | 20260504 | 0.1405 | 0.1666 | 0.8334 | 1228 | 0 |
| LUNG | 20260503 | 0.1433 | 0.1187 | 0.8813 | 1228 | 0 |
| LUNG | 20260504 | 0.1120 | 0.1288 | 0.8712 | 1228 | 0 |
| FLCHAIN | 20260503 | 0.1144 | 0.1261 | 0.8739 | 1228 | 0 |
| FLCHAIN | 20260504 | 0.1178 | 0.1602 | 0.8398 | 1228 | 0 |
| NWTCO | 20260503 | 0.1127 | 0.1441 | 0.8559 | 1228 | 0 |
| NWTCO | 20260504 | 0.1129 | 0.1216 | 0.8784 | 1228 | 0 |
