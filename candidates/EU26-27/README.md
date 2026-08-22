# EU26-27 — canonical source-native OLD for TwoRate GSEMO

Research tag: `RESEARCH_2`

## Scientific status

```text
candidate identity: PASS
EU affiliation: PASS_LEIDEN_UNIVERSITY_NETHERLANDS
dimension: PASS_N_100
Zenodo raw data: PASS_AUTHENTICATED
author repository: PASS_FurongYe/GSEMO
paper-era author commit: PASS_fbe1d3ed3064dedd85ba3c5eaf78fe4ea3d6b380
OLD implementation: SINGLE_SOURCE_NATIVE_AUTHOR_CODE
publication anchor: PASS_TABLE1_TWORATE_HV_61624
OLD: PASS_SOURCE_NATIVE_OLD
raw matrix: EXACT_101x100
endpoint vector: EXACT_100x1
HYBRID: AUTHORIZED_FOR_SEPARATE_PREREGISTERED_STAGE
PR #19 numerical evidence used for OLD: false
```

## Original study

*Towards Self-adaptive Mutation in Evolutionary Multi-Objective Algorithms*,
FOGA 2023.

For the relevant experiment the paper reports:

- OneMinMax with `n=100`;
- two-rate GSEMO;
- hypervolume adaptation metric;
- `lambda=10` for the presented results;
- 100 independent runs;
- running time as function evaluations until the entire Pareto front is obtained.

The matching Table-1 mean is `61624 FE`.

## Frozen OLD source

```text
FurongYe/GSEMO
commit fbe1d3ed3064dedd85ba3c5eaf78fe4ea3d6b380
2023-05-01, message: submission preparation
```

Frozen dependency:

```text
IOHprofiler/IOHexperimenter
v0.3.9
commit f223c682dff0749067d00b870f83ad754f7d96f5
```

The canonical replay command is:

```text
./gsemo 1 100 TwoRate 10 1 1 10000000 100
```

The `10000000` argument is not a paper claim. It is a deliberately non-binding
safety ceiling required by the author executable interface. The algorithm terminates
each run when the complete Pareto front has been obtained.

The authenticated reference is:

```text
Zenodo record: 7880836
member: csv/om/TwoRateL10P1HVOneMaxD100.csv
runs: 100
Pareto points: 101
raw endpoint mean: 61623.78 FE
maximum endpoint: 131875 FE
paper Table 1: 61624 FE
```

The nearby `61618 FE` value belongs to AGSEMO in Table 2 and is not the OLD anchor.

## Canonical exact replay

GitHub Actions run `32565217851` executed the unchanged author source with the frozen
paper-era dependency and produced:

```text
complete source runs: 100/100
incomplete source runs: []
paper/Zenodo mean FE: 61623.780000
source mean FE: 61623.78
max Zenodo endpoint FE: 131875
non-binding safety cap FE: 10000000
exact first-hit matrix: True
matrix mismatches: 0
exact endpoint vector: True
endpoint mismatches: 0
```

Comparator unit and negative controls also passed.

## Why the earlier PR #23 rejection was wrong

The previous freeze used:

```text
./gsemo 1 100 TwoRate 10 1 1 100000 100
```

The original paper does not state this 100000-FE cap for the experiment. The
authenticated endpoint vector contains values above it. Once a run is truncated,
the author's one-time global RNG stream enters all later runs in a different state,
so later stochastic trajectories diverge even though the source is unchanged.

The earlier compiler, dependency and source-revision recovery tables therefore tested
a different capped experiment. They remain in the branch as forensic evidence but do
not determine the canonical OLD decision.

## PASS rule

`PASS_SOURCE_NATIVE_OLD` requires all of:

1. exact upstream source identity;
2. exact frozen dependency identity;
3. build of unchanged author source;
4. comparator unit and negative controls;
5. non-binding safety ceiling;
6. exactly 100 complete sequential source-native runs;
7. exact 101×100 first-hit matrix equality with authenticated Zenodo data;
8. exact 100-run endpoint-vector equality;
9. Zenodo raw mean aligned with paper Table 1 `61624 FE`.

All conditions are satisfied.

## Current decision

```text
EU26-27 = PASS_SOURCE_NATIVE_OLD
```

This establishes a valid OLD baseline. It does not establish scientific novelty by
itself. The next stage is a separately preregistered HYBRID experiment using this exact
OLD as the control condition, with quality/non-inferiority and efficiency gates frozen
before outcomes are inspected.
