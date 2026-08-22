# Professor gate — EU26-27 canonical OLD

Research tag: `RESEARCH_2`

## Scope

The only scientific OLD is the unchanged author implementation
`FurongYe/GSEMO@fbe1d3ed3064dedd85ba3c5eaf78fe4ea3d6b380` with the frozen
paper-era IOHexperimenter dependency. A project reimplementation is not substituted
for the OLD decision.

## Paper identity

The matching original study is *Towards Self-adaptive Mutation in Evolutionary
Multi-Objective Algorithms* (FOGA 2023). For the relevant experiment the paper uses
100-dimensional OneMinMax, 100 independent runs and reports average function
evaluations required to obtain the entire Pareto front. The matching Table-1 profile is
two-rate GSEMO using hypervolume with `lambda=10`, reported as `61624 FE`.

The paper's experimental setup does not state a 100000-FE cap.

## Questions and verified answers

1. **Source identity** — exact author commit and critical blobs authenticated before
   and after build: **PASS**.
2. **Dependency identity** — IOHexperimenter `v0.3.9` / commit
   `f223c682dff0749067d00b870f83ad754f7d96f5`: **PASS**.
3. **Experimental unit** — exactly 100 sequential runs from the author's one-time
   `random::seed(10)` stream: **PASS**.
4. **Problem identity** — OneMinMax `n=100`, TwoRate, `lambda=10`, `p=1`, HV:
   **PASS**.
5. **Stop semantics** — FEs until the entire Pareto front is obtained, with a
   non-binding `10000000` implementation safety ceiling: **PASS**.
6. **Safety ceiling** — authenticated maximum endpoint is `131875 FE`, therefore the
   ceiling is non-binding: **PASS**.
7. **Raw equivalence** — generated 101×100 first-hit matrix equals authenticated
   Zenodo exactly: **PASS, 0 mismatches**.
8. **Endpoint vector** — all 100 run endpoints equal Zenodo exactly: **PASS,
   0 mismatches**.
9. **Published endpoint identity** — Zenodo/raw source mean `61623.78 FE` agrees with
   Table 1 `61624 FE`: **PASS**.
10. **Anchor audit** — `61618 FE` is excluded from OLD because it belongs to AGSEMO
    in Table 2: **PASS**.
11. **Comparator controls** — complete, missing-cell, single-value mutation,
    run-endpoint and non-binding-cap tests: **PASS**.
12. **CI honesty** — cross-OS jobs are portability build/smoke checks; the canonical
    historical batch remains sequential: **PASS**.

## Canonical decision

```text
PASS_SOURCE_NATIVE_OLD
```

Verified replay evidence from GitHub Actions run `32565217851`:

```text
complete source runs: 100/100
source mean FE: 61623.78
Zenodo mean FE: 61623.78
max Zenodo endpoint FE: 131875
exact first-hit matrix: True
matrix mismatches: 0
exact endpoint vector: True
endpoint mismatches: 0
```

## Why the former rejection is invalid

The earlier reconstruction imposed `budget=100000`. That ceiling becomes binding for
an authenticated run whose endpoint is `131875 FE`. Because the author seeds one global
RNG stream once for the whole sequential batch, truncating that run changes the RNG
state entering later runs. Later mismatches are therefore a consequence of a changed
experiment, not evidence that the paper source is irreproducible.

The earlier 100k recovery matrix remains diagnostic history only.

## Academic interpretation

The OLD result establishes an unusually strong baseline: exact source-native
reproduction of the authenticated raw experimental trajectory, not merely aggregate
agreement. This validates OLD as the control condition for Stage 2.

It is **not** itself the scientific novelty. Novelty must come from the separately
frozen HYBRID controller and evidence that it improves a preregistered efficiency
criterion without unacceptable quality degradation.

## Claims allowed now

Preferred wording:

> The unchanged paper-era author implementation exactly reproduced the authenticated
> Zenodo 101×100 first-hit matrix for the OneMinMax TwoRate+HV configuration. The
> source-native mean of 61623.78 function evaluations equals the Zenodo raw mean and
> is consistent with the paper's Table-1 value of 61624. This establishes the OLD
> baseline for the subsequent preregistered hybrid experiment.

Do not write:

- “10,000,000 FE is the paper budget”;
- “100,000 FE is the paper budget”;
- “cross-platform stochastic equality” based only on build/smoke tests;
- “workers 1/2/4 reproduce the historical OLD”;
- “HYBRID improves the paper” before the HYBRID primary gate passes;
- “OLD reproduction is the scientific novelty”.

## HYBRID boundary

OLD no longer blocks Stage 2. HYBRID is authorized to begin, but its protocol,
metrics, machines/workers/load matrix and ablations must be frozen before its outcomes
are inspected.
