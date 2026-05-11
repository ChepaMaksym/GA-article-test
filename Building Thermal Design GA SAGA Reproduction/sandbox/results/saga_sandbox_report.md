# Formal SAGA Sandbox Report

- Case: 7 (all_variables)
- All checks passed: 1

| Scenario | GA LCC EUR | SAGA LCC EUR | Criterion | Bounds | Theta bounds | Equal budget | Theta history | No external update |
|---|---:|---:|---|---|---|---|---|---|
| baseline_clean | 7701.187 | 7814.204 | PASS | PASS | PASS | PASS | PASS | PASS |
| low_noise | 7831.229 | 7719.355 | PASS | PASS | PASS | PASS | PASS | PASS |
| high_noise | 7657.121 | 7787.016 | PASS | PASS | PASS | PASS | PASS | PASS |
| small_population | 7931.603 | 8335.863 | PASS | PASS | PASS | PASS | PASS | PASS |
| short_run | 8176.078 | 7886.865 | PASS | PASS | PASS | PASS | PASS | PASS |
| wide_theta_bounds | 8161.375 | 8397.557 | PASS | PASS | PASS | PASS | PASS | PASS |
| boundary_optimum | 6722.278 | 6954.073 | PASS | PASS | PASS | PASS | PASS | PASS |
| ill_scaled_variables | 9324.195 | 9302.034 | PASS | PASS | PASS | PASS | PASS | PASS |

The sandbox passes only when formal SAGA mechanics are visible in logs and GA/SAGA share the same objective, bounds, population size, generation count, and seed policy.
