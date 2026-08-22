# EU26-27 HYBRID v3 — development-selected capped lambda

Status: `DEVELOPMENT_COMPLETE / INDEPENDENT_H1_FAIL`.

## Integrity gates

- v3 controller/selection unit tests: PASS
- independent holdout ledger exactly `29001..29030`: PASS
- holdout disjoint from v1/v2 ledgers: PASS
- exact upstream GSEMO / IOHexperimenter revisions and critical blobs: PASS
- additive source patch: PASS
- build: PASS
- patched `TwoRate` exact PR #23 / Zenodo regression: PASS
- all six frozen cap profiles smoke-run: PASS
- development grid completed for all caps and 30 retired v2 seeds: PASS
- selected cap persisted before first holdout run: PASS
- OLD and selected V3 full-Pareto completion on holdout: 30/30 and 30/30

## Development-only selection

Frozen cap grid:

```text
{15, 20, 30, 40, 60, 100}
```

Paired median relative FE reduction on retired v2 seeds `28001..28030`:

```text
cap 15:  +5.890756%
cap 20: +15.358279%  <- selected by the frozen rule
cap 30:  -7.224697%
cap 40: +10.231962%
cap 60:  +2.525843%
cap 100: +2.894851%
```

The deterministic rule selected `HybridCap20`. These values are development evidence only and are not counted as independent confirmation.

## Independent holdout

Holdout: `29001..29030`.

```text
selected controller: HybridCap20
OLD median FE:        57,563.5
V3 median FE:         53,974.5
OLD mean FE:          59,719.4
V3 mean FE:           57,832.0

H1 paired median relative FE reduction OLD -> V3: -1.263559%
H1 95% percentile-bootstrap CI: [-15.884593%, +13.258223%]
bootstrap resamples: 50,000
bootstrap seed: 29029
H1: FAIL
```

The lower marginal median of V3 does **not** establish improvement. The preregistered paired statistic is slightly negative and its interval crosses zero.

## Scientific interpretation

V3 is an explicit example of development-to-holdout generalization failure. The same deterministic cap-selection rule that chose cap 20 from a +15.36% paired-median development score did not reproduce an FE advantage on the independent ledger.

Post-hoc inspection may be used only to motivate later development. It cannot alter the v3 H1 decision, the bootstrap rule, or the holdout composition.

## Evidence identity

```text
workflow run: 32573546704
artifact: 9476099058
artifact SHA-256: 10dabff61802e9482d339742800949cacb25aad4298f87c35ad91b57d279bc98
```

The artifact retains the exact OLD regression report, all development and holdout raw `.dat` files, stdout/controller traces, selected-cap JSON, paired endpoint tables, statistical JSON and SVG evidence.
