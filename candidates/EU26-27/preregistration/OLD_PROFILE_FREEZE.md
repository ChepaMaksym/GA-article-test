# EU26-27 OLD profile freeze — single source-native author baseline

Date revised: 2026-08-21
Research tag: `RESEARCH_2`

There is one OLD implementation only: the unchanged paper-era author code.

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

The author repository has no root license at the frozen revision. CI therefore
fetches and executes the exact upstream SHA rather than copying it into this
project as project-owned source.

## Outcome-blind historical dependency resolution

The GSEMO tree records absolute symlinks to a developer-local
IOHexperimenter checkout but not its commit. Dependency selection is therefore
based on chronology and source API before any source-native numerical outcome
is observed.

Rejected dependency candidate:

```text
FurongYe/IOHexperimenter
d35fffe510b958aa2658c0b39ed7dd2d84c5553b
```

It is source-incompatible with the frozen GSEMO commit: compilation shows that
its API no longer provides the legacy `IntegerSingleObjective` and
`wrap_function` interfaces used directly by `src/problems.cpp`. This rejection
occurred before a 100-run OLD result existed.

Frozen replacement:

```text
repository: IOHprofiler/IOHexperimenter
release: v0.3.9
commit: f223c682dff0749067d00b870f83ad754f7d96f5
release date: 2023-03-13
VERSION: 0.3.9
VERSION blob: 940ac09aa677de91fee3cd51b88b8f0521d96cc0
```

`v0.3.9` is the latest public IOHexperimenter release before the 2023-05-01
GSEMO submission commit. Its release-era API is compatible with the legacy
problem types expected by GSEMO. No candidate dependency may be changed after
source-native outcome inspection merely to improve numerical agreement.

## Frozen experiment command

The author's `src/main.cpp` defines

```text
./gsemo problem_id dimension algorithm lambda p adapt_metric budget runs
random::seed(10)  # once before all runs
```

The single OLD profile is exactly

```text
./gsemo 1 100 TwoRate 10 1 1 100000 100
```

Configuration:

```text
problem: OneMinMax
n: 100
algorithm: TwoRate
lambda: 10
initial mutation probability: 1/100
adaptation metric: hypervolume contribution
budget: 100000 FE per run
runs: 100 sequential runs
RNG: author's IOHexperimenter global stream seeded once with 10
```

No OLD run is split across workers because parallelizing this one global RNG
stream changes the historical experiment.

## Reference artifact

```text
Zenodo record: 7880836
archive: csv.zip
member: csv/om/TwoRateL10P1HVOneMaxD100.csv
front rows: 101
runs: 100
published rounded mean endpoint: 61618 FE
```

The run endpoint is the maximum `First_hit_j` across all 101 Pareto points. The
primary source-native comparison retains the complete 101×100 first-hit matrix,
not only an aggregate.

## Fail-closed PASS gate

`PASS_SOURCE_NATIVE_OLD` requires all of:

1. exact GSEMO and IOHexperimenter commits and frozen blob/version checks;
2. successful build without modifying GSEMO algorithm source;
3. 100/100 complete sequential source-native runs;
4. exact 101×100 first-hit matrix equality with Zenodo;
5. exact 100-run endpoint-vector equality with Zenodo;
6. Zenodo raw mean within ±1 FE of published rounded `61618`;
7. SHA-256-bound report and SVG evidence;
8. professor review of source identity, accounting and claim limits.

There is no adjustable numerical tolerance for raw source-native replay. A
single first-hit mismatch means `FAIL_SOURCE_NATIVE_OLD` for the frozen
environment.

## CI/CD interpretation

Ubuntu, macOS and Windows compile the same author source and execute one-run
smokes. This tests portability of the reconstructed build environment. The
canonical 100-run historical replay runs sequentially on Ubuntu and is the only
job used for exact Zenodo equality.

## HYBRID prohibition

HYBRID remains `BLOCKED_NOT_AUTHORIZED` until the current source-native OLD gate
passes. Rejected reconstruction numbers from PR #22 or early PR #23 are not
admissible as Research 2 evidence.
