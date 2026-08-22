# EU26-27 HYBRID v2 — confirmatory result

Status: `H1_FAIL / H2_NO_CLEAR_EFFECT`.

## Gates

- exact upstream GSEMO source/blob authentication: PASS
- exact paper-era dependency revision: PASS
- additive rollback/floor patch: PASS
- build: PASS
- patched `TwoRate` exact PR #23 / Zenodo regression: PASS
- rollback/floor smoke tests: PASS
- disjoint 30-seed holdout `28001..28030`: PASS
- 30/30 complete Pareto-front runs for all profiles: PASS

## Confirmatory endpoints

```text
OLD median FE:             63,782.0
HYBRID_ROLLBACK median FE: 64,136.0
HYBRID_FLOOR median FE:    56,181.5

H1 paired median relative FE reduction OLD -> HYBRID_ROLLBACK: +1.575182%
H1 95% percentile-bootstrap CI: [-14.390699%, +19.145964%]
H1: FAIL

H2 paired median relative FE reduction HYBRID_FLOOR -> HYBRID_ROLLBACK: -11.055069%
H2 95% percentile-bootstrap CI: [-21.663500%, +9.532151%]
H2: NO_CLEAR_EFFECT

median rollback events/run: 55
median max lambda/run: 100
```

The workflow succeeded operationally; the scientific improvement hypothesis did not pass.

## Interpretation

Rollback did not establish an FE-efficiency improvement over exact-reproduced OLD on the independent holdout. The rollback-specific ablation also has an interval crossing zero.

`HYBRID_FLOOR` had a lower marginal median endpoint than OLD, but this is an ablation observation, not a preregistered primary success claim. A post-hoc paired check on the retired v2 development data gives only about +2.9% paired-median relative FE reduction OLD -> HYBRID_FLOOR and is not confirmatory. It may motivate development work, but these seeds must not be reused as a future confirmation set.

## Evidence identity

```text
workflow run: 32572161500
artifact: 9475683444
artifact SHA-256: 085a477d5594e4fedb465c5817ebf3e4c3183165456f5ea7a3205388481a2ef3
```

The full artifact retains raw `.dat` files, stdout/controller traces, paired endpoints, JSON report and SVG evidence.
