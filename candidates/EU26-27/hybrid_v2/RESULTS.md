# EU26-27 HYBRID v2 — rollback-transfer result

Status: `T2_H1_FAIL / T2_H2_NO_CLEAR_EFFECT`.  
Study type: **source-grounded rollback transfer**, not numerical reproduction of the rollback paper.

## Source grounding

Primary source: Anton Bassin & Maxim Buzdalov, *The 1/5-th Rule with Rollbacks: On Self-Adjustment of the Population Size in the (1+(lambda,lambda)) GA*, GECCO 2019 Companion, DOI `10.1145/3319619.3322067`.

The source work identifies a failure mode of ordinary one-fifth control: `lambda` can grow too rapidly when the landscape violates the assumptions behind success-based adjustment. Rollback is introduced to limit the negative effect of this growth and is reported to improve behavior in the source experiments on random-weight linear functions and satisfiable MAX-SAT while retaining good OneMax behavior.

This PR transfers the rollback state machine to **offspring-count control inside exact-reproduced TwoRate GSEMO**. The algorithm, optimization problem and success signal differ from the source study, so the scientific question is whether the mechanism transfers, not whether the source paper is reproduced.

## Hypotheses

### T2-H1 — rollback transfer benefit

> The source-grounded rollback offspring controller reduces paired FE to complete Pareto-front discovery relative to exact-reproduced OLD.

### T2-H2 — rollback-specific contribution

> Rollback reduces paired FE relative to the corresponding floor-only controller.

## Gates

- exact upstream GSEMO source/blob authentication: PASS
- exact paper-era dependency revision: PASS
- additive rollback/floor patch: PASS
- build: PASS
- patched `TwoRate` exact PR #23 / Zenodo regression: PASS
- rollback/floor smoke tests: PASS
- disjoint 30-seed holdout `28001..28030`: PASS
- 30/30 complete Pareto-front runs for all profiles: PASS

These gates establish execution validity; T2-H1/T2-H2 are decided only by the frozen paired statistics.

## Confirmatory endpoints

```text
OLD median FE:             63,782.0
HYBRID_ROLLBACK median FE: 64,136.0
HYBRID_FLOOR median FE:    56,181.5

T2-H1 paired median relative FE reduction OLD -> HYBRID_ROLLBACK: +1.575182%
T2-H1 95% percentile-bootstrap CI: [-14.390699%, +19.145964%]
T2-H1: FAIL

T2-H2 paired median relative FE reduction HYBRID_FLOOR -> HYBRID_ROLLBACK: -11.055069%
T2-H2 95% percentile-bootstrap CI: [-21.663500%, +9.532151%]
T2-H2: NO_CLEAR_EFFECT

median rollback events/run: 55
median max lambda/run: 100
```

## Agreement with the source literature

Agreement class: **STRUCTURAL_SOURCE_ALIGNMENT_WITH_FAILED_PERFORMANCE_TRANSFER**.

The rollback controller is source-grounded and rollback events occurred during the experiment, so the intervention itself is not a fabricated heuristic. However, the source paper's favorable rollback performance does not carry over to this TwoRate GSEMO/OneMinMax/HV-success setting. The correct interpretation is a boundary of external validity, not a failed reproduction of Bassin & Buzdalov.

`HYBRID_FLOOR` has a lower marginal median than OLD, but this is an ablation observation. A post-hoc paired check on the retired v2 data gives only about `+2.9%` paired-median relative FE reduction OLD -> HYBRID_FLOOR and is not confirmatory.

## Scientific claim boundary

Supported:

- source-grounded rollback was transferred and exercised;
- exact OLD source-native behavior remained intact under regression;
- T2-H1 failed and T2-H2 produced no clear effect under an independent holdout;
- the experiment supplies evidence on the portability of rollback control across EA settings.

Not supported:

- numerical reproduction of the rollback paper;
- FE-efficiency superiority of rollback in TwoRate GSEMO;
- a claim that the floor-only marginal median is a validated improvement;
- universal conclusions beyond the frozen OneMinMax testbed.

## Evidence identity

```text
workflow run: 32572161500
artifact: 9475683444
artifact SHA-256: 085a477d5594e4fedb465c5817ebf3e4c3183165456f5ea7a3205388481a2ef3
```

The full artifact retains raw `.dat` files, stdout/controller traces, paired endpoints, JSON report and SVG evidence. The v2 ledger is retired from future confirmatory use.
