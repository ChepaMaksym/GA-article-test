# EU26-27 HYBRID v1 — reset-control transfer result

Date: 2026-08-22  
Study type: **source-grounded mechanism transfer**, not source-paper numerical reproduction.

Workflow: `EU26-27 HYBRID confirmatory`  
Run: `32571460043`  
Artifact: `9475506328`  
Artifact SHA-256: `5ebd8d33ea5da63463427b2a821e3aa8a2c7e208903bd90dc70c0334daa9e8d0`

## Source grounding

The transferred `lambda`-control idea is grounded in two prior research lines:

1. Hevia Fajardo & Sudholt, *Theoretical and Empirical Analysis of Parameter Control Mechanisms in the (1+(lambda,lambda)) Genetic Algorithm*, DOI `10.1145/3564755`. Their `Jump_k` analysis shows that uncontrolled `lambda` growth can be harmful, smaller caps can be beneficial, and reset to 1 can cycle the controller through parameter space.
2. Doerr, El Hadri & Pinard, *The (1+(lambda,lambda)) Global SEMO Algorithm*, DOI `10.1145/3512290.3528868`. They analyze one-fifth-inspired dynamic parameters in discrete multi-objective optimization and prove improved asymptotic runtime for their algorithm on OneMinMax.

Our experiment does **not** execute either source algorithm. It keeps the exact-reproduced TwoRate mutation-rate controller unchanged and transfers the success-based rule only to offspring count, with strict hypervolume improvement as the success signal. Therefore the valid question is external transfer, not reproduction of the source performance result.

## Hypotheses

### T1-H1 — transfer benefit

> Reset-based adaptive offspring-count control reduces paired FE to complete Pareto-front discovery relative to exact-reproduced OLD.

### T1-H2 — reset-specific contribution

> Reset reduces paired FE relative to the same transferred controller without reset.

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

Workflow completion establishes execution validity only; hypothesis status is determined by the frozen paired statistics below.

## Frozen paired result

| Profile | Median FE | Mean FE |
|---|---:|---:|
| OLD | 55,425.0 | 58,284.77 |
| HYBRID_RESET | 62,489.0 | 64,208.00 |
| HYBRID_NO_RESET | 57,912.5 | 62,574.47 |

Primary T1-H1 used the preregistered paired median relative FE reduction
`(FE_OLD - FE_HYBRID_RESET)/FE_OLD` with 50,000 deterministic bootstrap
resamples (`seed=27027`).

```text
T1-H1 median relative reduction: -20.237076%
T1-H1 95% percentile-bootstrap CI: [-32.412176%, +4.934754%]
T1-H1: FAIL
```

Reset-specific comparison:

```text
T1-H2 median relative reduction NO_RESET -> RESET: -2.388751%
T1-H2 95% percentile-bootstrap CI: [-15.523548%, +10.684546%]
T1-H2: NO_CLEAR_EFFECT
```

The result does not support an FE-efficiency improvement claim for this transferred reset controller.

## Agreement with the source literature

Agreement class: **MECHANISM_TRANSFER_WITH_PERFORMANCE_NONREPLICATION**.

The source mechanism is validly identified and the transferred controller is executed as intended. However, the favorable reset/dynamic-parameter performance reported in the source settings does not transfer to this TwoRate GSEMO experiment. This must not be described as a failed reproduction of Hevia Fajardo & Sudholt or Doerr et al., because algorithm, controlled role and success signal differ.

A weaker qualitative observation is consistent with the literature's warning about harmful `lambda` growth: HYBRID_RESET beat OLD on 12/30 paired seeds and lost on 18/30, with several expensive OLD runs improving while many easier runs became more costly. This observation is diagnostic, not a new confirmatory hypothesis.

## Scientific claim boundary

Supported:

- the reset mechanism was source-grounded and correctly transferred;
- the exact OLD baseline remained intact under regression;
- T1-H1 failed and T1-H2 had no clear effect under the frozen protocol;
- the result is evidence about the external validity of the transferred controller.

Not supported:

- numerical reproduction of either source paper;
- improvement of TwoRate GSEMO by reset;
- a reset-specific causal explanation for any seed-level improvements;
- universal conclusions beyond the frozen OneMinMax profile.

The v1 seed ledger is retired from future confirmation and may be used only as explicitly labeled development/diagnostic evidence.
