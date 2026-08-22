# EU26-27 HYBRID v1 — confirmatory result

Date: 2026-08-22
Workflow: `EU26-27 HYBRID confirmatory`
Run: `32571460043`
Artifact: `9475506328`
Artifact SHA-256: `5ebd8d33ea5da63463427b2a821e3aa8a2c7e208903bd90dc70c0334daa9e8d0`

## Gate audit

- preregistered formula/statistics tests: PASS (9/9)
- exact upstream source/dependency identity: PASS
- additive HYBRID patch: PASS
- patched executable build: PASS
- patched `TwoRate` exact PR #23 / Zenodo regression: PASS
- canonical OLD matrix mismatches: 0
- canonical OLD endpoint mismatches: 0
- HYBRID_RESET smoke: PASS
- HYBRID_NO_RESET smoke: PASS
- confirmatory completion: 30/30 for every profile

## Frozen paired result

| Profile | Median FE | Mean FE |
|---|---:|---:|
| OLD | 55,425.0 | 58,284.77 |
| HYBRID_RESET | 62,489.0 | 64,208.00 |
| HYBRID_NO_RESET | 57,912.5 | 62,574.47 |

Primary H1 used the preregistered paired median relative FE reduction
`(FE_OLD - FE_HYBRID_RESET)/FE_OLD` with 50,000 deterministic bootstrap
resamples (`seed=27027`).

```text
H1 median relative reduction: -20.237076%
H1 95% percentile-bootstrap CI: [-32.412176%, +4.934754%]
H1: FAIL
```

Reset-specific secondary comparison:

```text
H2 median relative reduction NO_RESET -> RESET: -2.388751%
H2 95% percentile-bootstrap CI: [-15.523548%, +10.684546%]
H2: NO_CLEAR_EFFECT
```

The result does not support an efficiency-improvement claim for v1. It is kept as negative evidence and its thresholds/seeds are not reused to tune a replacement formula.

## Diagnostic observation (not a new confirmatory claim)

HYBRID_RESET beat OLD on 12/30 paired seeds and lost on 18/30. The benefit was concentrated in several expensive OLD runs while many easy OLD runs became more costly. This motivates a *new* baseline-preserving refinement, but no v1 seed may be reused as confirmatory evidence for that refinement.

## Literature boundary

Dynamic one-fifth-inspired `lambda` control in discrete multi-objective optimization is prior art: Doerr, El Hadri and Pinard (GECCO 2022) proposed a self-adjusting `(1+(lambda,lambda))` Global SEMO and proved an `O(n^2)` OneMinMax runtime. Therefore this project must not claim to be the first adaptive-population MOEA.

Bassin and Buzdalov (GECCO 2019 / arXiv:1904.07284) showed that ordinary one-fifth population-size adaptation can degrade performance when its assumptions are violated and proposed rollbacks to damp harmful parameter growth. That is the literature-grounded basis for the next, independently preregistered refinement.
