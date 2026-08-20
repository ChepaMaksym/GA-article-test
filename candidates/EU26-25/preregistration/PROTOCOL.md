# EU26-25 outcome-blind OLD-first protocol

Date frozen: 2026-08-20

## Research question

Can the exact PyVRP 0.5.0 research artifact reproduce the published
`X-n101-k25` cost endpoint under a deterministic iteration-normalised budget,
and, only after that succeeds, can PR #8 reset self-adjusting control reduce the
iterations required to reach matched solution quality without degrading final
cost or feasibility?

## Frozen identities

```text
paper DOI: 10.1287/ijoc.2023.0055
artifact DOI: 10.1287/ijoc.2023.0055.cd
artifact repository: INFORMSJoC/2023.0055
artifact commit: 7ed6a24a0f4275da53c68e3db9ef5af197017111
release: PyVRP v0.5.0
release commit: d4799a810a8cf7d16ea2c8871204bdfb3a896d06
paper config blob: 4685819a98e61f624b9fec03b405d023a81e5852
penalty source blob in artifact: b2e0f5ccc7bd55a1f4581f9d2a6cbd5c8eb01bdb
instance repository: PyVRP/Instances
instance commit: 7474b068a8effa7f39448b241314b615c9271525
instance path: CVRP/X-n101-k25.vrp
instance Git blob: ad4539d0b70cd60178601d7b3515d08945fdb3ad
BKS / published mean: 27591
```

No upstream source or data byte may be fetched from a moving branch.

## Named profiles

### P0 - paper runtime profile

Historical context only. The paper used CPU-scaled runtime and 10 seeds. This
profile is not rerun as a cross-machine endpoint because runner speed is not a
stable scientific budget.

### P1 - OLD iteration-normalised profile

```text
seed ledger: 1..10
maximum iterations: 120000 per seed
rounding: dimacs
instance format: vrplib
collect_statistics: true, instrumentation only
other config fields: exact initial_submission_ijoc_cvrp.toml
```

### P2 - portability smoke

```text
seed ledger: 901, 902
maximum iterations: 2000
operating systems: ubuntu, macos, windows
Python: 3.11
```

P2 can validate installation, deterministic schema and finite feasible search.
It cannot establish the published numerical endpoint.

### P3 - worker/load equivalence

The same smoke seeds are executed by batch workers 1, 2 and 4. Each seed owns
an independent solver process and random stream. Canonical per-seed scientific
fields must be identical after sorting by seed. Runtime and process IDs are
excluded from the scientific digest.

## Formula gates

For integer penalty `omega`, feasible fraction `f`, target `xi`, tolerance
`delta=0.05`, increase `a`, and decrease `b`, the released transition is:

```text
diff = xi - f

if -delta < diff < delta:
    omega_next = omega
elif diff > 0:
    omega_next = int(min(a * omega + 1, 1000))
else:
    omega_next = int(max(b * omega - 1, 1))
```

The source comparison is strict. In exact real arithmetic a difference equal to
`+/-0.05` would take an update branch. Under the actual paper cadence of 100
registrations, however, the relevant executable fractions are 0.38 and 0.48;
IEEE-754 evaluates their differences from 0.43 as approximately
`+/-0.04999999999999999`, so both take the unchanged branch. Tests must retain
this implementation-level numeric witness rather than silently idealising it.

With the paper config:

```text
target_feasible = 0.43
penalty_increase = 1.25
penalty_decrease = 0.85
update interval = 100 registrations
```

Tests must cover below, discrete 38% boundary, interior, discrete 48% boundary,
above, `+1`, `-1`, integer truncation, clipping to `[1,1000]`, update cadence,
history clearing and separate capacity/time-warp histories.

## OLD acceptance rule

All gates are conjunctive:

1. exact frozen source/config/instance/license identities;
2. formula and boundary tests pass;
3. source artifact installs and reports package version 0.5.0 on Python 3.11;
4. all ten seeds are present exactly once and complete;
5. every final solution is feasible;
6. every final cost is exactly `27591`;
7. arithmetic mean is exactly `27591.0`;
8. population standard deviation is exactly `0.0`;
9. first-hit iteration is present and in `[1,120000]` for every seed;
10. an exact repeated seed produces the same canonical scientific row;
11. P2 and P3 engineering gates pass without using their wall-clock times as
    evidence of quality or speed.

Allowed success label:

```text
PASS_SOURCE_NATIVE_ITERATION_NORMALISED_ENDPOINT
```

If any OLD gate fails:

```text
REJECTED_OLD_REPRODUCTION
HYBRID = BLOCKED_NOT_CREATED
```

Executable candidate files must then be removed, leaving only source,
preregistration, compact evidence and rejection rationale.

## HYBRID preregistration boundary

No executable HYBRID file may exist before OLD PASS.

After OLD PASS, exploratory seeds are `101..110`. Confirmatory paired seeds are
`1001..1030` and remain untouched during variant selection.

Frozen invariants for OLD versus HYBRID:

- exact instance and cost evaluator;
- initial random solutions per paired seed;
- population and local-search operators;
- penalty controller and its state;
- maximum iteration budget;
- same stopping semantics;
- same solution feasibility definition;
- same BKS and matched quality targets.

The intended intervention is one scalar reset self-adjusting `lambda` state
that controls the existing repair/intensification probability. Candidate
variants may differ only in the deterministic mapping from `lambda` to that
probability and the frozen PR #8 update constants.

## HYBRID confirmatory hypotheses

### H1 - final quality non-inferiority

Every paired HYBRID final cost must be no worse than OLD by more than 0.05%, and
the paired median relative cost difference must be `<= 0`.

### H2 - endpoint coverage

HYBRID BKS coverage must be at least OLD coverage and at least 24/30.

### H3 - iteration efficiency

At the primary matched target `27591`, both methods must reach the target in at
least 24/30 runs. Using right-censoring at the common budget, the paired median
relative first-hit iteration reduction must be at least 20%, and the lower
endpoint of a paired 95% BCa interval must be positive.

Secondary targets are frozen outcome-blind from BKS:

```text
1.01 * BKS
1.005 * BKS
1.00 * BKS
```

Logical iterations, not wall-clock time, are the primary efficiency unit.

## Statistical rules

- paired seed design;
- medians as primary location summaries;
- paired BCa bootstrap, 50000 resamples, bootstrap seed 26025;
- censored misses assigned budget+1 only for the predefined capped comparison;
- no seed deletion;
- no change to margins or targets after a confirmatory row exists;
- negative and null results remain scientific results rather than CI failures.

## Claim limits

Passing P1 does not establish historical CPU equivalence. Passing H3 does not
prove wall-clock acceleration or that reset alone caused every difference.
No single-instance result may be generalized to all CVRP, VRPTW, machines or
other classifiers/optimizers.
