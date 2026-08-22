# EU26-27 OLD profile freeze — canonical source-native author baseline

Date revised: 2026-08-22
Research tag: `RESEARCH_2`

There is one canonical OLD implementation only: the unchanged paper-era author code.

## Frozen author source

```text
repository: FurongYe/GSEMO
commit: fbe1d3ed3064dedd85ba3c5eaf78fe4ea3d6b380
date: 2023-05-01
message: submission preparation
```

Critical blobs:

```text
CMakeLists.txt     1e2cb211fc0cc36f9837232b0dee69aa5c1dab9c
src/gsemo.hpp      2693144bcfccff902343a02c6c8e48d7dd263257
src/main.cpp       22025e4680da85c98e3bb5ea30db8334ca25dff3
src/problems.cpp   cd9b520253e3b0b0390e35bf4fb86d4249c204de
```

CI fetches and executes the exact upstream SHA. The algorithm source is not copied
or modified as project-owned code.

## Frozen paper-era dependency

```text
repository: IOHprofiler/IOHexperimenter
release: v0.3.9
commit: f223c682dff0749067d00b870f83ad754f7d96f5
release date: 2023-03-13
VERSION: 0.3.9
VERSION blob: 940ac09aa677de91fee3cd51b88b8f0521d96cc0
```

This revision compiles the unchanged frozen GSEMO source and, under the corrected
paper stop semantics, reproduces the authenticated Zenodo raw trajectory exactly.

## Paper experiment identity

The original study is:

```text
Towards Self-adaptive Mutation in Evolutionary Multi-Objective Algorithms
FOGA 2023
```

For the relevant Table-1 OLD profile the paper states:

- 100-dimensional OneMinMax;
- 100 independent runs;
- `lambda=10` for the presented experiment;
- two-rate GSEMO guided by hypervolume;
- running time measured as function evaluations until the entire Pareto front is obtained.

The experimental setup does **not** state a 100000-FE cap.

## Canonical executable protocol

The author's `src/main.cpp` interface is:

```text
./gsemo problem_id dimension algorithm lambda p adapt_metric budget runs
random::seed(10)  # once before all runs
```

The canonical replay is:

```text
./gsemo 1 100 TwoRate 10 1 1 10000000 100
```

Configuration:

```text
problem: OneMinMax
n: 100
algorithm: TwoRate
lambda: 10
initial mutation probability: 1/100
adaptation metric: hypervolume
runs: 100 sequential runs
RNG: author's IOHexperimenter global stream seeded once with 10
stop quantity: FEs until complete Pareto front
safety ceiling: 10000000 FE
safety ceiling published by paper: no
```

The large budget argument is a deliberately non-binding implementation safety ceiling.
The author GSEMO checks whether the complete Pareto front has been found and terminates
the run at that point. The authenticated Zenodo maximum endpoint for this profile is
`131875 FE`, far below the ceiling.

No canonical OLD run is split across workers because parallelizing the author's single
global RNG stream changes the experiment.

## Reference artifact and publication anchor

```text
Zenodo record: 7880836
archive: csv.zip
member: csv/om/TwoRateL10P1HVOneMaxD100.csv
front rows: 101
runs: 100
Zenodo endpoint mean: 61623.78 FE
maximum endpoint: 131875 FE
paper Table 1, matching profile: 61624 FE
```

The matching paper row is **OneMinMax / two-rate GSEMO / HV / lambda=10**.
Table 1 reports `61 624` FE as the average over 100 runs. The Zenodo raw mean
`61623.78` rounds to that value.

`61618 FE` belongs to **AGSEMO in Table 2** and is not an OLD anchor.

## Historical reconstruction error: 100000 FE

The former freeze used:

```text
./gsemo 1 100 TwoRate 10 1 1 100000 100
```

That command is not paper-faithful because the authenticated endpoint vector contains
runs requiring more than 100000 FE. The first binding truncation changes the state of
the single global RNG stream entering later runs and creates cascading mismatches.

All compiler/dependency/source probes based on that cap are retained only as forensic
history. They are not admissible evidence against the corrected canonical replay.

## Canonical fail-closed PASS gate

`PASS_SOURCE_NATIVE_OLD` requires all of:

1. exact GSEMO and IOHexperimenter commits and frozen blob/version checks;
2. successful build without modifying GSEMO algorithm source;
3. comparator unit and negative-control tests pass;
4. safety ceiling proven non-binding against the authenticated endpoint vector;
5. 100/100 sequential source-native runs complete;
6. exact 101×100 first-hit matrix equality with Zenodo;
7. exact 100-run endpoint-vector equality with Zenodo;
8. Zenodo raw mean within ±1 FE of the matching paper Table-1 value `61624`;
9. machine-readable report and SHA-256-bound evidence.

There is no adjustable tolerance for raw trajectory equality. One mismatching first-hit
cell means `FAIL_SOURCE_NATIVE_OLD`.

## Verified result

GitHub Actions run `32565217851` established:

```text
100/100 complete
source mean FE = 61623.78
Zenodo mean FE = 61623.78
max endpoint = 131875
first-hit matrix mismatches = 0
endpoint mismatches = 0
```

Therefore the canonical OLD state is:

```text
PASS_SOURCE_NATIVE_OLD
```

## HYBRID boundary

The OLD prerequisite is now satisfied. HYBRID may proceed only under a separate frozen
protocol that preserves this OLD baseline and preregisters quality, efficiency, reset
and ablation gates before outcome inspection.
