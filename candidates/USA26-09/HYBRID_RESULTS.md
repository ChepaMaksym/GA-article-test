# USA26-09 confirmatory OLD versus HYBRID result

## Primary decision

```text
PASS_HYBRID
```

All 30 pairs use the same fixed instance, search seed, initial population, target and logical-NFE budget.

## Quality

| Metric | OLD | HYBRID |
|---|---:|---:|
| Median final objective | 1.8290005 | 1.8288548 |
| Target 1.830 reached | 16/30 | 28/30 |
| Median capped target NFE | 1432.5 | 423.5 |

Paired final-quality effect:

```text
median(HYBRID - OLD) = -0.000145733
95% paired percentile bootstrap = [-0.002057988, 0.0]
non-inferiority margin = +0.010
result = PASS_NONINFERIORITY
```

This supports quality preservation. The thesis will not promote the small numerical shift to a preregistered superiority claim.

## Search efficiency

```text
paired median relative NFE reduction = 49.6597%
95% paired bootstrap = [34.3333%, 72.7667%]
required lower bound = 20%
result = PASS_EFFICIENCY
```

Hybrid reached the matched target in 28 runs versus 16 for OLD. Discordant pairs were 13 Hybrid-only versus 1 OLD-only; exact McNemar/binomial p = 0.001831.

## Load behavior

A secondary 10-seed load profile shows the mechanism is budget-dependent:

- budget 300: neither method has a stable efficiency advantage;
- budget 750: Hybrid has higher target coverage, but the efficiency interval remains inconclusive;
- budget 1500: the confirmatory-scale advantage becomes clear.

This guards against the simplistic statement that HYBRID is always better at every budget.

## Reset mechanism stress

Reset did not activate in the primary 50-node, 1500-NFE campaign because lambda did not reach its cap. A separate 20-node/4-salesman stress profile with budget 3000 exercised reset in 10/10 runs and produced 56 reset events. Its paired median reset-minus-no-reset quality difference was zero.

Therefore:

- the primary efficacy claim concerns the complete self-adjusting lambda controller;
- reset is verified as executable and safe;
- reset is not claimed as the sole cause of the primary NFE reduction.
