# EU26-23 OLD failure - Pilcher SAGA-FSTSP

## Decision

`REJECTED_OLD_NUMERIC_GATE / HYBRID_NOT_PERMITTED`

EU26-23 is rejected after the preregistered primary OLD campaign. The candidate passed formula, implementation, determinism and completion checks, but failed the second numerical acceptance condition. No executable PR #8 hybrid was created.

## Study and frozen endpoint

- Study: Ted Pilcher, *A Self-Adaptive Genetic Algorithm for the Flying Sidekick Travelling Salesman Problem*.
- DOI: `10.48550/arXiv.2310.14713`.
- Applied instance: `singlecenter-63-n20`.
- Data source: `pcbouman-eur/TSP-D-Instances` commit `73c51b323b26605f9dea6f94c8f57d4204cd2f05`.
- Instance blob SHA-1: `55ca3a5f43821cc00c0e7c6856d55170a145264f`.
- Instance SHA-256: `c07c8c8e616b490ca3f9a4d59148e043a6ad71127a0dfc4ed3d43304d95f662c`.
- License: CC BY-SA 4.0.
- Published target: Table 2 configuration 7, 30 trials, mean final fitness `448.68`.
- Frozen primary configuration: population `50,000`, generations `1,000,000`, innovation rate `7`, initial drone percentage `8`, tournament size `5`, seeds `1..30`.

## OLD implementation verification

A standard-library Python clean-room implementation and an optimized C++20 implementation were developed from the outcome-blind preregistration and amendments.

Verified before the primary result was aggregated:

- authenticated parser and metadata checks;
- exact Held-Karp TSP oracle for the 20-node instance;
- exact optimal tour cost `744.79919093014144`;
- canonical optimal tour `[0,4,14,10,13,2,1,6,8,15,16,12,19,7,9,5,3,11,17,18]`;
- synchronized truck/drone makespan micro-oracles;
- legal and idempotent repair;
- nine crossover profiles;
- three tour-mutation profiles;
- twelve node-type mutation actions;
- eight-field memeplex inheritance and innovation boundaries;
- 1/2/4-worker scientific-row invariance in Python;
- Python/C++ fixed-tape identity for fitness, route, types, memeplex, event counts and convergence trace;
- Python unit suite: `15/15 PASS`.

Implementation hashes before deletion:

```text
Python OLD:     5e7a853802a990cb83ab75cb0acfe88b2bf29bc1a7b31c4821bb30a9562cf1df
C++ OLD:        e6fd89b3d1be732436ae3d59faf6b340c1d5e3428a095fa16b15e293dae77317
Held-Karp:      fc08535c65d1e20ff6c3a933197db61982597f9069c8cbcd3a3fc74ee2c570bc
TSP config:     fde776e0f0b39d8b64e95674d0695e82764be76787fe277a3468c7bcb624f645
Python tests:   4515b97111ff5171dc7367cceba2fd4a28f81923e7681b8f029bfa1ba643bf61
```

The implementations are not retained in the candidate folder because the user-specified loop requires deletion after rejection.

## Primary 30-seed result

All 30 prespecified seeds completed. No row was skipped, replaced or rerun with changed parameters.

```text
reported mean:                   448.68
reproduced mean:                 441.92107972516686
absolute relative mean error:    1.5064010597%
preregistered error limit:       5.0%
mean-error condition:            PASS

reproduced median:               444.07717381207965
sample SD:                       4.148652740896095
minimum:                         428.6580549245608
maximum:                         447.4335232098904

95% BCa interval for mean:       [440.1827934628145, 443.1632439467796]
BCa resamples:                   50,000
bootstrap seed:                  2623
reported 448.68 inside interval: false
confidence-interval condition:   FAIL
```

Final preregistered decision:

```text
V8_OLD_NUMERIC = FAIL
```

The clean-room result is numerically better because lower makespan is preferable, but that does not authorize a reproduction PASS. The systematic difference and narrow interval show that the clean-room stochastic profile is not statistically aligned with the reported aggregate under the frozen interpretation.

## Why no diagnostic can rescue the candidate

Before implementation, alternate rounding, probability-domain, innovation-draw and type-inheritance interpretations were classified as diagnostic-only. The preregistration explicitly forbids replacing the failed primary profile with an outcome-selected variant. Therefore no sensitivity run can promote EU26-23 to PASS.

Possible causes retained as unresolved rather than fitted:

- unpublished Visual Studio C++ source;
- original RNG engine, seeds and states;
- initial memeplex distribution;
- exact implementations of some prose-defined node-type operators;
- possible difference between the paper’s labelled “tour size” and the interpreted tournament size;
- author-specific tie and probability semantics.

## Evidence retained after candidate deletion

- `failure_logs/EU26-23_evidence/primary_rows.csv` - 30 immutable seed endpoints; SHA-256 `8dac262b2bee7ae55b73283a12b50b5baf9160327f44154a39d71562151c290b`.
- `failure_logs/EU26-23_evidence/primary_aggregate.json` - frozen statistical decision; SHA-256 `ff9e9b473b15ccc7d9cbae2075465c763c1389722706ebbcebabbfc5a8f54d9d`.

## Next-candidate rule

EU26-24 must branch from `research/EU26-07-reset-jump-verification`, not from EU26-23. It must pass its own OLD published-result gate before any hybrid, graphs, efficiency claim or thesis update is allowed.
